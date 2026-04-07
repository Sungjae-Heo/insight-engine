"""인증 라우트 통합 테스트 — routes/auth_routes.py"""
import unittest
from unittest.mock import patch, MagicMock

from app import create_app

_HEADERS = {'Origin': 'http://localhost:3000'}

# auth_routes.py는 is_supabase_enabled를 모듈 레벨에서 import하므로
# 반드시 routes.auth_routes 네임스페이스에서 mock해야 한다.
_SB_ENABLED_AUTH = 'routes.auth_routes.is_supabase_enabled'
_SB_ENABLED_SVC = 'services.data.supabase_service.is_supabase_enabled'
_SB_GET = 'routes.auth_routes.get_supabase'


class TestAuthRoutesIntegration(unittest.TestCase):
    """auth_routes.py 핵심 엔드포인트 통합 테스트."""

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    # ─── GET /api/auth/status ───

    @patch(_SB_ENABLED_AUTH, return_value=False)
    @patch(_SB_ENABLED_SVC, return_value=False)
    def test_auth_status_returns_enabled_flag(self, _m1, _m2):
        """Supabase 비활성화 상태에서 enabled=false 반환."""
        resp = self.client.get('/api/auth/status', headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('enabled', data)
        self.assertFalse(data['enabled'])

    @patch(_SB_ENABLED_AUTH, return_value=True)
    @patch(_SB_ENABLED_SVC, return_value=True)
    def test_auth_status_returns_enabled_true(self, _m1, _m2):
        """Supabase 활성화 상태에서 enabled=true 반환."""
        resp = self.client.get('/api/auth/status', headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()['enabled'])

    # ─── GET /api/auth/config ───

    @patch(_SB_ENABLED_AUTH, return_value=False)
    @patch(_SB_ENABLED_SVC, return_value=False)
    def test_auth_config_returns_structure(self, _m1, _m2):
        """인증 config에 enabled, url, anonKey 필드가 포함되어야 한다."""
        resp = self.client.get('/api/auth/config', headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('enabled', data)
        self.assertIn('url', data)
        self.assertIn('anonKey', data)

    # ─── POST /api/auth/signup ───

    @patch(_SB_ENABLED_AUTH, return_value=True)
    @patch(_SB_ENABLED_SVC, return_value=True)
    @patch(_SB_GET)
    def test_signup_success(self, mock_get_sb, _m1, _m2):
        """정상 회원가입 시 성공 응답."""
        mock_user = MagicMock()
        mock_user.id = 'test-user-id'
        mock_user.email = 'test@example.com'
        mock_result = MagicMock()
        mock_result.user = mock_user
        mock_get_sb.return_value.auth.sign_up.return_value = mock_result

        resp = self.client.post('/api/auth/signup',
                                json={'email': 'test@example.com', 'password': 'password123'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('user', data)

    @patch(_SB_ENABLED_AUTH, return_value=True)
    @patch(_SB_ENABLED_SVC, return_value=True)
    def test_signup_missing_email_returns_400(self, _m1, _m2):
        """이메일 누락 시 400."""
        resp = self.client.post('/api/auth/signup',
                                json={'password': 'password123'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.get_json())

    @patch(_SB_ENABLED_AUTH, return_value=True)
    @patch(_SB_ENABLED_SVC, return_value=True)
    def test_signup_missing_password_returns_400(self, _m1, _m2):
        """비밀번호 누락 시 400."""
        resp = self.client.post('/api/auth/signup',
                                json={'email': 'test@example.com'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.get_json())

    @patch(_SB_ENABLED_AUTH, return_value=True)
    @patch(_SB_ENABLED_SVC, return_value=True)
    def test_signup_short_password_returns_400(self, _m1, _m2):
        """8자 미만 비밀번호 시 400."""
        resp = self.client.post('/api/auth/signup',
                                json={'email': 'test@example.com', 'password': 'short'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn('error', data)
        self.assertIn('8자', data['error'])

    @patch(_SB_ENABLED_AUTH, return_value=False)
    @patch(_SB_ENABLED_SVC, return_value=False)
    def test_signup_supabase_disabled_returns_400(self, _m1, _m2):
        """Supabase 비활성화 시 400."""
        resp = self.client.post('/api/auth/signup',
                                json={'email': 'test@example.com', 'password': 'password123'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Supabase', resp.get_json()['error'])

    # ─── POST /api/auth/login ───

    @patch(_SB_ENABLED_AUTH, return_value=True)
    @patch(_SB_ENABLED_SVC, return_value=True)
    @patch(_SB_GET)
    def test_login_success(self, mock_get_sb, _m1, _m2):
        """정상 로그인 시 세션 토큰 포함 응답."""
        mock_user = MagicMock()
        mock_user.id = 'test-user-id'
        mock_user.email = 'test@example.com'
        mock_session = MagicMock()
        mock_session.access_token = 'access-token-123'
        mock_session.refresh_token = 'refresh-token-123'
        mock_session.expires_at = 9999999999
        mock_result = MagicMock()
        mock_result.user = mock_user
        mock_result.session = mock_session
        mock_get_sb.return_value.auth.sign_in_with_password.return_value = mock_result

        resp = self.client.post('/api/auth/login',
                                json={'email': 'test@example.com', 'password': 'password123'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('session', data)
        self.assertEqual(data['session']['access_token'], 'access-token-123')

    @patch(_SB_ENABLED_AUTH, return_value=True)
    @patch(_SB_ENABLED_SVC, return_value=True)
    def test_login_missing_fields_returns_400(self, _m1, _m2):
        """이메일/비밀번호 누락 시 400."""
        resp = self.client.post('/api/auth/login',
                                json={},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.get_json())

    @patch(_SB_ENABLED_AUTH, return_value=False)
    @patch(_SB_ENABLED_SVC, return_value=False)
    def test_login_supabase_disabled_returns_400(self, _m1, _m2):
        """Supabase 비활성화 시 400."""
        resp = self.client.post('/api/auth/login',
                                json={'email': 'test@example.com', 'password': 'password123'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)

    # ─── GET /api/user/history ───

    @patch(_SB_ENABLED_AUTH, return_value=True)
    @patch(_SB_ENABLED_SVC, return_value=True)
    def test_user_history_requires_auth(self, _m1, _m2):
        """인증 없이 히스토리 조회 시 401."""
        resp = self.client.get('/api/user/history', headers=_HEADERS)
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertIn('error', data)
        self.assertEqual(data.get('code'), 'AUTH_REQUIRED')

    # ─── PUT /api/user/password ───

    @patch(_SB_ENABLED_AUTH, return_value=True)
    @patch(_SB_ENABLED_SVC, return_value=True)
    def test_change_password_requires_auth(self, _m1, _m2):
        """인증 없이 비밀번호 변경 시 401."""
        resp = self.client.put('/api/user/password',
                               json={'current_password': 'old', 'new_password': 'newpass123'},
                               headers=_HEADERS)
        self.assertEqual(resp.status_code, 401)

    @patch(_SB_ENABLED_AUTH, return_value=False)
    @patch(_SB_ENABLED_SVC, return_value=False)
    def test_change_password_missing_current_password_returns_400(self, _m1, _m2):
        """현재 비밀번호 누락 시 400 (Supabase 비활성화 = 인증 우회)."""
        resp = self.client.put('/api/user/password',
                               json={'new_password': 'newpassword123'},
                               headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('현재 비밀번호', resp.get_json()['error'])

    @patch(_SB_ENABLED_AUTH, return_value=False)
    @patch(_SB_ENABLED_SVC, return_value=False)
    def test_change_password_short_new_password_returns_400(self, _m1, _m2):
        """새 비밀번호가 8자 미만이면 400."""
        resp = self.client.put('/api/user/password',
                               json={'current_password': 'oldpass123', 'new_password': 'short'},
                               headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('8자', resp.get_json()['error'])


if __name__ == '__main__':
    unittest.main()
