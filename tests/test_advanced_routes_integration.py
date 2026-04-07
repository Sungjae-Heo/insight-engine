"""고급 생성 라우트 통합 테스트 — routes/advanced_routes.py"""
import unittest
from unittest.mock import patch, MagicMock

from app import create_app

_HEADERS = {'Origin': 'http://localhost:3000'}

# require_auth는 supabase_service 내부에서 호출
_SB_ENABLED = 'services.data.supabase_service.is_supabase_enabled'
# require_usage는 자체 import된 is_supabase_enabled 사용
_SB_ENABLED_USAGE = 'services.usage.usage_decorator.is_supabase_enabled'


class TestAdvancedRoutesIntegration(unittest.TestCase):
    """advanced_routes.py 핵심 엔드포인트 통합 테스트."""

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    # ─── POST /api/mindmap ───

    @patch(_SB_ENABLED_USAGE, return_value=True)
    @patch(_SB_ENABLED, return_value=True)
    def test_mindmap_requires_auth(self, _m1, _m2):
        """Supabase 활성화 시 인증 없이 마인드맵 생성 요청하면 401."""
        resp = self.client.post('/api/mindmap',
                                json={'content': '테스트 콘텐츠'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertIn('error', data)
        self.assertEqual(data.get('code'), 'AUTH_REQUIRED')

    @patch(_SB_ENABLED_USAGE, return_value=False)
    @patch(_SB_ENABLED, return_value=False)
    def test_mindmap_missing_content_returns_400(self, _m1, _m2):
        """콘텐츠 없이 마인드맵 생성 시 400."""
        resp = self.client.post('/api/mindmap',
                                json={},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn('error', data)
        self.assertIn('콘텐츠', data['error'])

    @patch('services.core.ai_service.create_content')
    @patch('services.core.content_service.truncate_text', side_effect=lambda text, n: text[:n])
    @patch(_SB_ENABLED_USAGE, return_value=False)
    @patch(_SB_ENABLED, return_value=False)
    def test_mindmap_success(self, _m1, _m2, _mock_trunc, mock_ai):
        """정상 마인드맵 생성 시 성공 응답."""
        mock_ai.return_value = {
            'content': '- 주제\n  - 하위1\n  - 하위2',
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50}
        }
        # STYLE_PROMPTS에 mindmap 키가 있어야 함
        with self.client.application.app_context():
            self.client.application.config['STYLE_PROMPTS']['mindmap'] = '마인드맵 프롬프트입니다.'

        resp = self.client.post('/api/mindmap',
                                json={'content': '테스트 콘텐츠 ' * 50},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('markdown', data)

    # ─── POST /api/generate-multi ───

    @patch(_SB_ENABLED_USAGE, return_value=True)
    @patch(_SB_ENABLED, return_value=True)
    def test_generate_multi_requires_auth(self, _m1, _m2):
        """Supabase 활성화 시 인증 없이 멀티 생성 요청하면 401."""
        resp = self.client.post('/api/generate-multi',
                                json={
                                    'url': 'https://www.youtube.com/watch?v=test123',
                                    'styles': ['blog_seo', 'summary'],
                                },
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 401)

    @patch(_SB_ENABLED_USAGE, return_value=False)
    @patch(_SB_ENABLED, return_value=False)
    def test_generate_multi_missing_url_returns_400(self, _m1, _m2):
        """URL 없이 멀티 생성 시 400."""
        resp = self.client.post('/api/generate-multi',
                                json={'styles': ['blog_seo']},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.get_json())

    @patch(_SB_ENABLED_USAGE, return_value=False)
    @patch(_SB_ENABLED, return_value=False)
    def test_generate_multi_missing_styles_returns_400(self, _m1, _m2):
        """스타일 없이 멀티 생성 시 400."""
        resp = self.client.post('/api/generate-multi',
                                json={'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn('error', data)
        self.assertIn('스타일', data['error'])

    @patch(_SB_ENABLED_USAGE, return_value=False)
    @patch(_SB_ENABLED, return_value=False)
    def test_generate_multi_too_many_styles_returns_400(self, _m1, _m2):
        """스타일 6개 이상 시 400."""
        resp = self.client.post('/api/generate-multi',
                                json={
                                    'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                                    'styles': ['a', 'b', 'c', 'd', 'e', 'f'],
                                },
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('최대 5개', resp.get_json()['error'])

    @patch(_SB_ENABLED_USAGE, return_value=False)
    @patch(_SB_ENABLED, return_value=False)
    def test_generate_multi_invalid_url_returns_400(self, _m1, _m2):
        """유효하지 않은 YouTube URL로 멀티 생성 시 400."""
        resp = self.client.post('/api/generate-multi',
                                json={
                                    'url': 'https://www.example.com/not-youtube',
                                    'styles': ['blog_seo'],
                                },
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('YouTube', resp.get_json()['error'])


if __name__ == '__main__':
    unittest.main()
