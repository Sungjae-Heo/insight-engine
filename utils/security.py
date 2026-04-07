"""공통 보안 유틸리티 — SSRF 방지, 입력 검증, 페이지네이션"""
import ipaddress
import re
from urllib.parse import urlparse
from functools import wraps
from flask import request, jsonify


def is_safe_url(url: str, allow_localhost: bool = True) -> bool:
    """URL이 안전한지 검증합니다 (SSRF 방지).

    프라이빗 IP, 링크로컬, AWS 메타데이터 엔드포인트 차단.
    localhost는 기본 허용 (Ollama 등 로컬 서비스용).
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        if hostname in ('localhost', '127.0.0.1', '::1'):
            return allow_localhost
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_link_local or ip.is_loopback:
            return False
        # IPv4-mapped IPv6 우회 차단
        if hasattr(ip, 'ipv4_mapped') and ip.ipv4_mapped:
            if ip.ipv4_mapped.is_private or ip.ipv4_mapped.is_link_local:
                return False
        return True
    except ValueError:
        # 도메인 이름인 경우 허용 (DNS 레벨 검증은 별도)
        return True


def validate_pagination(page=None, per_page=None, max_per_page: int = 100, default_per_page: int = 20):
    """페이지네이션 파라미터를 검증하고 안전한 값으로 반환합니다.

    Returns:
        tuple: (page, per_page)
    """
    if page is None:
        page = request.args.get('page', 1, type=int)
    if per_page is None:
        per_page = request.args.get('per_page', default_per_page, type=int)
    return max(1, page), min(max_per_page, max(1, per_page))


# 프롬프트 인젝션 패턴
_INJECTION_PATTERNS = re.compile(
    r'(이전\s*지시를?\s*무시|ignore\s+previous\s+instructions?|'
    r'system\s*prompt|you\s+are\s+now|forget\s+(everything|all)|'
    r'disregard\s+(all|previous)|override\s+instructions?)',
    re.IGNORECASE
)


def is_prompt_injection(text: str) -> bool:
    """텍스트에 프롬프트 인젝션 패턴이 포함되어 있는지 확인합니다."""
    return bool(_INJECTION_PATTERNS.search(text))


def sanitize_error_for_client(error_msg: str) -> str:
    """내부 정보(경로, traceback 등)를 제거한 안전한 에러 메시지를 반환합니다."""
    # 파일 경로 패턴 제거
    sanitized = re.sub(r'[A-Za-z]:\\[^\s"\']+', '[경로 숨김]', error_msg)
    sanitized = re.sub(r'/[^\s"\']*(?:\.py|\.js|\.ts)', '[경로 숨김]', sanitized)
    # IP/포트 패턴 제거
    sanitized = re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?', '[주소 숨김]', sanitized)
    return sanitized
