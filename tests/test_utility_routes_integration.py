"""유틸리티 라우트 통합 테스트 — routes/utility_routes.py"""
import unittest
from unittest.mock import patch, MagicMock

from app import create_app

_HEADERS = {'Origin': 'http://localhost:3000'}

# require_auth 데코레이터는 supabase_service 내부에서 is_supabase_enabled 호출
_SB_ENABLED = 'services.data.supabase_service.is_supabase_enabled'
# require_usage 데코레이터는 자체 import된 is_supabase_enabled 사용
_SB_ENABLED_USAGE = 'services.usage.usage_decorator.is_supabase_enabled'


class TestUtilityRoutesIntegration(unittest.TestCase):
    """utility_routes.py 핵심 엔드포인트 통합 테스트."""

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    # ─── GET /health ───

    def test_health_returns_200(self):
        """헬스체크 엔드포인트가 200과 status=healthy를 반환해야 한다."""
        resp = self.client.get('/health', headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'healthy')

    def test_health_contains_required_fields(self):
        """헬스체크 응답에 environment, api_version 필드가 포함되어야 한다."""
        resp = self.client.get('/health', headers=_HEADERS)
        data = resp.get_json()
        self.assertIn('environment', data)
        self.assertIn('api_version', data)
        self.assertIn('request_count', data)
        self.assertIn('error_rate', data)

    # ─── POST /api/heartbeat ───

    def test_heartbeat_success(self):
        """clientId 포함 시 heartbeat 성공."""
        resp = self.client.post('/api/heartbeat',
                                json={'clientId': 'test-client-123'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()['ok'])

    def test_heartbeat_missing_client_id_returns_400(self):
        """clientId 누락 시 400."""
        resp = self.client.post('/api/heartbeat',
                                json={},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()['ok'])

    # ─── GET /api/providers ───

    def test_providers_returns_200(self):
        """프로바이더 목록이 200으로 반환되어야 한다."""
        resp = self.client.get('/api/providers', headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('providers', data)
        self.assertIn('styles', data)

    def test_providers_styles_structure(self):
        """스타일 목록에 id와 name 필드가 있어야 한다."""
        resp = self.client.get('/api/providers', headers=_HEADERS)
        data = resp.get_json()
        styles = data.get('styles', [])
        if styles:
            self.assertIn('id', styles[0])
            self.assertIn('name', styles[0])

    def test_providers_has_auto_fallback_flag(self):
        """프로바이더 응답에 hasAutoFallback 플래그가 있어야 한다."""
        resp = self.client.get('/api/providers', headers=_HEADERS)
        data = resp.get_json()
        self.assertIn('hasAutoFallback', data)
        self.assertTrue(data['hasAutoFallback'])

    # ─── DELETE /api/cache ───

    @patch(_SB_ENABLED_USAGE, return_value=True)
    @patch(_SB_ENABLED, return_value=True)
    def test_clear_cache_requires_auth(self, _m1, _m2):
        """Supabase 활성화 시 인증 없이 캐시 삭제 요청하면 401."""
        resp = self.client.delete('/api/cache',
                                  json={},
                                  headers=_HEADERS)
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertEqual(data.get('code'), 'AUTH_REQUIRED')

    @patch('services.core.content_service.clear_cache', return_value=5)
    @patch(_SB_ENABLED_USAGE, return_value=False)
    @patch(_SB_ENABLED, return_value=False)
    def test_clear_cache_success_all(self, _m1, _m2, mock_clear):
        """인증 우회 후 전체 캐시 삭제 성공."""
        resp = self.client.delete('/api/cache',
                                  json={},
                                  headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertIn('전체', data['message'])

    @patch('services.core.content_service.clear_cache', return_value=1)
    @patch(_SB_ENABLED_USAGE, return_value=False)
    @patch(_SB_ENABLED, return_value=False)
    def test_clear_cache_by_video_id(self, _m1, _m2, mock_clear):
        """특정 video_id로 캐시 삭제."""
        resp = self.client.delete('/api/cache',
                                  json={'videoId': 'abc123'},
                                  headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertIn('abc123', data['message'])

    # ─── POST /api/fact-check ───

    @patch(_SB_ENABLED_USAGE, return_value=True)
    @patch(_SB_ENABLED, return_value=True)
    def test_fact_check_requires_auth(self, _m1, _m2):
        """Supabase 활성화 시 인증 없이 팩트체크 요청하면 401."""
        resp = self.client.post('/api/fact-check',
                                json={'content': '테스트 콘텐츠'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 401)

    @patch(_SB_ENABLED_USAGE, return_value=False)
    @patch(_SB_ENABLED, return_value=False)
    def test_fact_check_missing_content_returns_400(self, _m1, _m2):
        """콘텐츠 없이 팩트체크 시 400."""
        resp = self.client.post('/api/fact-check',
                                json={'content': ''},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.get_json())

    # ─── GET / ───

    def test_root_returns_status(self):
        """루트 경로가 API 서버 상태를 반환해야 한다."""
        resp = self.client.get('/', headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'ok')

    # ─── GET /api/providers/campaign-packs ───

    def test_campaign_packs_returns_200(self):
        """캠페인 팩 목록이 200으로 반환되어야 한다."""
        resp = self.client.get('/api/providers/campaign-packs', headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('packs', data)


if __name__ == '__main__':
    unittest.main()
