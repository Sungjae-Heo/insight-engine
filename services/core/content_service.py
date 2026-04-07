"""
YouTube 콘텐츠 서비스
자막, 댓글, 제목 추출 기능 제공

자막 추출 로직은 services.transcript.transcript_fetcher 모듈로 분리되었습니다.
이 모듈은 하위 호환성을 위해 기존 심볼을 re-export 합니다.
"""
from __future__ import annotations

import functools
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from flask import current_app

# ── 자막 추출 파사드 import ──
# 기존에 이 모듈에서 직접 정의되던 자막 관련 함수/상수를 facade에서 가져옵니다.
# 하위 호환성: 다른 모듈이 `from services.core.content_service import get_transcript` 등으로
# 사용하던 코드가 그대로 동작합니다.
from services.transcript.transcript_fetcher import (
    # Constants (re-export for backward compatibility)
    SUPADATA_API_URL,
    PREFERRED_LANGUAGES,
    MAX_RETRY_ATTEMPTS,
    USER_AGENT,
    TIMEOUT_CONNECT,
    TIMEOUT_READ_SHORT,
    TIMEOUT_READ_MEDIUM,
    TIMEOUT_READ_LONG,
    HTTP_TIMEOUT,
    VIDEO_ID_PATTERN,
    CACHE_DIR,
    # Cache functions (re-export)
    _sanitize_video_id,
    _get_cache_path,
    _ensure_cache_dir,
    _load_cache,
    _save_cache,
    # Transcript extraction functions (re-export)
    get_transcript_via_supadata,
    _build_ytt_api,
    _order_transcript_tracks,
    _fetch_transcript_with_api,
    _extract_text_from_transcript,
    _extract_segments_from_transcript,
    _extract_yt_initial_player_response,
    _extract_caption_tracks,
    _pick_caption_track,
    _parse_vtt,
    _parse_timedtext_xml,
    _is_safe_caption_url,
    _download_caption_from_url,
    _get_transcript_from_watch_page,
    _detect_auto_caption,
    _detect_language_from_text,
    _try_watch_page_fallback,
    _try_ytdlp_fallback,
    _try_nlm_fallback,
    _run_parallel_fallbacks,
    _build_transcript_result,
    # HTTP client (re-export)
    _create_http_session,
    _get_proxy_config,
    # Logging (re-export)
    _log_info,
    _log_warning,
    # Main function - aliased below
    fetch_transcript as _fetch_transcript,
    # Type aliases (re-export)
    TranscriptResult,
    CaptionTrack,
)


@functools.lru_cache(maxsize=1)
def _get_youtube_build():
    """googleapiclient를 지연 로딩합니다 (cold start 최적화)."""
    from googleapiclient.discovery import build
    return build


# YouTube URL Patterns
YOUTUBE_URL_REGEX = re.compile(
    r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
    r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
)
VIDEO_ID_PATTERNS = [
    re.compile(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'),
    re.compile(r'(?:embed\/)([0-9A-Za-z_-]{11})'),
    re.compile(r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})')
]


# ==================== Cache Management ====================

def clear_cache(video_id: Optional[str] = None) -> int:
    """캐시를 삭제합니다. video_id가 None이면 전체 삭제."""
    if not os.path.exists(CACHE_DIR):
        return 0

    # video_id가 지정된 경우 형식 검증 (Path Traversal 방지)
    if video_id is not None:
        _sanitize_video_id(video_id)

    deleted = 0
    for filename in os.listdir(CACHE_DIR):
        if video_id is None or filename.startswith(f"{video_id}_"):
            try:
                os.remove(os.path.join(CACHE_DIR, filename))
                deleted += 1
            except IOError:
                pass
    return deleted


def purge_expired_cache(max_age_hours: int = 24) -> dict:
    """만료된 캐시 파일만 선택적으로 삭제합니다.

    Args:
        max_age_hours: 이 시간(시)보다 오래된 캐시 삭제 (기본 24시간)

    Returns:
        {'purged': 삭제 수, 'remaining': 남은 수, 'freed_bytes': 삭제로 확보된 바이트}
    """
    if not os.path.exists(CACHE_DIR):
        return {'purged': 0, 'remaining': 0, 'freed_bytes': 0}

    now = time.time()
    cutoff = now - (max_age_hours * 3600)
    purged = 0
    remaining = 0
    freed_bytes = 0

    for filename in os.listdir(CACHE_DIR):
        filepath = os.path.join(CACHE_DIR, filename)
        if not os.path.isfile(filepath):
            continue
        try:
            mtime = os.path.getmtime(filepath)
            if mtime < cutoff:
                try:
                    freed_bytes += os.path.getsize(filepath)
                except OSError:
                    pass
                os.remove(filepath)
                purged += 1
            else:
                remaining += 1
        except IOError:
            remaining += 1

    return {'purged': purged, 'remaining': remaining, 'freed_bytes': freed_bytes}


# ==================== URL Utilities ====================

def is_youtube_url(url: str) -> bool:
    """URL이 유효한 YouTube URL인지 확인합니다."""
    return bool(YOUTUBE_URL_REGEX.match(url))


def get_video_id(url: str) -> Optional[str]:
    """URL에서 YouTube 비디오 ID를 추출합니다."""
    if not url:
        return None

    for pattern in VIDEO_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


# ==================== Main Transcript Function ====================

def get_transcript(video_id: str) -> TranscriptResult:
    """
    YouTube 자막을 가져옵니다.
    Supadata API 키는 환경변수(SUPADATA_API_KEY)에서 로드됩니다.

    Args:
        video_id: YouTube 비디오 ID

    Returns:
        성공: {'text': '자막 내용', 'source': 'api'|'watch'|'supadata'|'cache'}
        실패: {'error': '에러 메시지'}

    우선순위:
    0. 캐시 (있으면 바로 반환)
    1. youtube-transcript-api 라이브러리 (무료)
    2. watch 페이지 직접 파싱 (무료)
    2.5. yt-dlp 자막 직접 추출 (무료, 음성인식 없이)
    3. Supadata API (유료)
    4. Whisper 음성 인식 (로컬, 느림)
    """
    return _fetch_transcript(video_id)


# ==================== YouTube API Functions ====================

def get_youtube_title(video_id: str) -> Optional[str]:
    """YouTube 영상 제목을 가져옵니다."""
    try:
        from googleapiclient.errors import HttpError
        api_key = current_app.config.get('YOUTUBE_API_KEY')
        if not api_key:
            return None

        youtube = _get_youtube_build()('youtube', 'v3', developerKey=api_key)
        results = youtube.videos().list(part="snippet", id=video_id).execute()

        items = results.get("items", [])
        if items:
            return items[0]["snippet"]["title"]
        return None

    except HttpError as e:
        _log_warning(f"YouTube API error getting title: {e}")
        return None
    except Exception as e:
        _log_warning(f"Error getting YouTube title: {e}")
        return None


def get_content_title(url: str) -> Optional[str]:
    """URL에서 콘텐츠 제목을 가져옵니다."""
    if not is_youtube_url(url):
        return None

    video_id = get_video_id(url)
    if video_id:
        return get_youtube_title(video_id)
    return None


def get_top_comments(video_id: str) -> List[str]:
    """YouTube 영상의 인기 댓글을 가져옵니다."""
    # 캐시 확인
    cached = _load_cache(video_id, 'comments')
    if cached is not None:
        _log_info(f"Comments loaded from cache for video_id={video_id}")
        return cached

    try:
        from googleapiclient.errors import HttpError
        api_key = current_app.config.get('YOUTUBE_API_KEY')
        if not api_key:
            _log_warning("YouTube API key not configured, skipping comments")
            return []

        youtube = _get_youtube_build()('youtube', 'v3', developerKey=api_key)
        results = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            textFormat="plainText",
            order="relevance",
            maxResults=50
        ).execute()

        comments: List[str] = []
        for item in results.get("items", []):
            comment = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
            comments.append(comment)

        # 댓글이 있으면 캐시에 저장
        if comments:
            _save_cache(video_id, 'comments', comments)

        return comments

    except HttpError as e:
        if e.resp.status == 403:
            _log_warning("YouTube API quota exceeded or comments disabled")
        else:
            _log_warning(f"YouTube API error: {e}")
        return []
    except Exception as e:
        _log_warning(f"Error getting comments: {e}")
        return []


# ==================== Playlist / Channel ====================

# URL 패턴
PLAYLIST_URL_PATTERNS = [
    re.compile(r'[?&]list=(PL[\w-]+)'),
    re.compile(r'playlist\?list=(PL[\w-]+)'),
]

CHANNEL_URL_PATTERNS = [
    re.compile(r'youtube\.com/@([\w.-]+)'),
    re.compile(r'youtube\.com/channel/(UC[\w-]+)'),
    re.compile(r'youtube\.com/c/([\w.-]+)'),
]


def is_playlist_url(url: str) -> bool:
    """URL이 YouTube 재생목록 URL인지 확인합니다."""
    if not url:
        return False
    return any(p.search(url) for p in PLAYLIST_URL_PATTERNS)


def is_channel_url(url: str) -> bool:
    """URL이 YouTube 채널 URL인지 확인합니다."""
    if not url:
        return False
    return any(p.search(url) for p in CHANNEL_URL_PATTERNS)


def _get_playlist_id(url: str) -> Optional[str]:
    """URL에서 재생목록 ID를 추출합니다."""
    for pattern in PLAYLIST_URL_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def _get_channel_identifier(url: str) -> Optional[Dict[str, str]]:
    """URL에서 채널 식별자를 추출합니다.

    Returns:
        {'type': 'handle'|'id'|'custom', 'value': '...'} 또는 None
    """
    # @handle
    match = re.search(r'youtube\.com/@([\w.-]+)', url)
    if match:
        return {'type': 'handle', 'value': match.group(1)}

    # /channel/UCxxxx
    match = re.search(r'youtube\.com/channel/(UC[\w-]+)', url)
    if match:
        return {'type': 'id', 'value': match.group(1)}

    # /c/CustomName
    match = re.search(r'youtube\.com/c/([\w.-]+)', url)
    if match:
        return {'type': 'custom', 'value': match.group(1)}

    return None


def get_playlist_videos(url: str, max_results: int = 10) -> Dict[str, Any]:
    """재생목록에서 영상 목록을 가져옵니다.

    Args:
        url: YouTube 재생목록 URL
        max_results: 최대 결과 수 (기본 10, 최대 50)

    Returns:
        {'videos': [{'videoId': '...', 'title': '...', 'thumbnail': '...'}], 'total': N}
    """
    api_key = os.getenv('YOUTUBE_API_KEY', '')
    if not api_key:
        return {'error': 'YouTube API 키가 설정되지 않았습니다.'}

    playlist_id = _get_playlist_id(url)
    if not playlist_id:
        return {'error': '유효한 재생목록 URL이 아닙니다.'}

    max_results = min(max_results, 50)

    try:
        from googleapiclient.errors import HttpError
        youtube = _get_youtube_build()('youtube', 'v3', developerKey=api_key)
        response = youtube.playlistItems().list(
            part='snippet',
            playlistId=playlist_id,
            maxResults=max_results
        ).execute()

        videos = []
        for item in response.get('items', []):
            snippet = item.get('snippet', {})
            vid = snippet.get('resourceId', {}).get('videoId')
            if vid:
                videos.append({
                    'videoId': vid,
                    'title': snippet.get('title', ''),
                    'thumbnail': snippet.get('thumbnails', {}).get('medium', {}).get('url', '')
                })

        total = response.get('pageInfo', {}).get('totalResults', len(videos))
        return {'videos': videos, 'total': total}

    except HttpError as e:
        _log_warning(f"Playlist API error: {e}")
        return {'error': f'재생목록 조회 실패: {e.resp.status}'}
    except Exception as e:
        _log_warning(f"Playlist fetch error: {e}")
        return {'error': '재생목록 영상 목록을 가져올 수 없습니다.'}


def get_channel_videos(url: str, max_results: int = 10) -> Dict[str, Any]:
    """채널에서 최신 영상 목록을 가져옵니다.

    Args:
        url: YouTube 채널 URL
        max_results: 최대 결과 수 (기본 10, 최대 50)

    Returns:
        {'videos': [{'videoId': '...', 'title': '...', 'thumbnail': '...'}], 'total': N}
    """
    api_key = os.getenv('YOUTUBE_API_KEY', '')
    if not api_key:
        return {'error': 'YouTube API 키가 설정되지 않았습니다.'}

    identifier = _get_channel_identifier(url)
    if not identifier:
        return {'error': '유효한 채널 URL이 아닙니다.'}

    max_results = min(max_results, 50)

    try:
        from googleapiclient.errors import HttpError
        youtube = _get_youtube_build()('youtube', 'v3', developerKey=api_key)

        # 채널 ID 조회
        channel_id = None
        if identifier['type'] == 'id':
            channel_id = identifier['value']
        else:
            # handle 또는 custom name으로 채널 검색
            if identifier['type'] == 'handle':
                search_query = f"@{identifier['value']}"
            else:
                search_query = identifier['value']

            search_resp = youtube.search().list(
                part='snippet',
                q=search_query,
                type='channel',
                maxResults=1
            ).execute()
            items = search_resp.get('items', [])
            if items:
                channel_id = items[0]['snippet']['channelId']

        if not channel_id:
            return {'error': '채널을 찾을 수 없습니다.'}

        # 채널의 uploads 재생목록 ID 조회
        channel_resp = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()
        channel_items = channel_resp.get('items', [])
        if not channel_items:
            return {'error': '채널 정보를 가져올 수 없습니다.'}

        uploads_id = channel_items[0]['contentDetails']['relatedPlaylists']['uploads']

        # uploads 재생목록에서 영상 목록 조회
        playlist_resp = youtube.playlistItems().list(
            part='snippet',
            playlistId=uploads_id,
            maxResults=max_results
        ).execute()

        videos = []
        for item in playlist_resp.get('items', []):
            snippet = item.get('snippet', {})
            vid = snippet.get('resourceId', {}).get('videoId')
            if vid:
                videos.append({
                    'videoId': vid,
                    'title': snippet.get('title', ''),
                    'thumbnail': snippet.get('thumbnails', {}).get('medium', {}).get('url', '')
                })

        total = playlist_resp.get('pageInfo', {}).get('totalResults', len(videos))
        return {'videos': videos, 'total': total}

    except HttpError as e:
        _log_warning(f"Channel API error: {e}")
        return {'error': f'채널 조회 실패: {e.resp.status}'}
    except Exception as e:
        _log_warning(f"Channel fetch error: {e}")
        return {'error': '채널 영상 목록을 가져올 수 없습니다.'}


# ==================== Utilities ====================

def truncate_text(text: str, max_tokens: int) -> str:
    """텍스트를 최대 토큰 수로 자릅니다."""
    if not isinstance(text, str):
        return ""

    tokens = text.split()
    if len(tokens) > max_tokens:
        return " ".join(tokens[:max_tokens]) + "..."
    return text
