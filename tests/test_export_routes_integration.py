"""내보내기 라우트 통합 테스트 — routes/export_routes.py"""
import unittest
from unittest.mock import patch, MagicMock

from app import create_app

_HEADERS = {'Origin': 'http://localhost:3000'}


class TestExportRoutesIntegration(unittest.TestCase):
    """export_routes.py 핵심 엔드포인트 통합 테스트."""

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    # ─── POST /api/export/docx ───

    @patch('services.data.supabase_service.is_supabase_enabled', return_value=False)
    def test_export_docx_success(self, _mock_sb):
        """마크다운 콘텐츠로 DOCX 변환 성공."""
        resp = self.client.post('/api/export/docx',
                                json={'title': '테스트 제목', 'content': '# 헤딩\n\n본문 내용입니다.'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.content_type,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        # 파일 크기가 0보다 크다
        self.assertGreater(len(resp.data), 0)

    @patch('services.data.supabase_service.is_supabase_enabled', return_value=False)
    def test_export_docx_missing_content_returns_400(self, _mock_sb):
        """콘텐츠 없이 DOCX 변환 시 400."""
        resp = self.client.post('/api/export/docx',
                                json={'title': '테스트'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.get_json())

    @patch('services.data.supabase_service.is_supabase_enabled', return_value=False)
    def test_export_docx_empty_content_returns_400(self, _mock_sb):
        """빈 문자열 콘텐츠로 DOCX 변환 시 400."""
        resp = self.client.post('/api/export/docx',
                                json={'title': '테스트', 'content': ''},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)

    @patch('services.data.supabase_service.is_supabase_enabled', return_value=True)
    def test_export_docx_requires_auth(self, _mock_enabled):
        """Supabase 활성화 시 인증 없이 401."""
        resp = self.client.post('/api/export/docx',
                                json={'title': '테스트', 'content': '내용'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 401)

    @patch('services.data.supabase_service.is_supabase_enabled', return_value=False)
    def test_export_docx_with_toc(self, _mock_sb):
        """목차 포함 DOCX 변환 성공."""
        resp = self.client.post('/api/export/docx',
                                json={
                                    'title': '목차 테스트',
                                    'content': '## 섹션 1\n\n내용\n\n## 섹션 2\n\n내용',
                                    'include_toc': True,
                                },
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)

    @patch('services.data.supabase_service.is_supabase_enabled', return_value=False)
    def test_export_docx_has_page_count_header(self, _mock_sb):
        """DOCX 응답에 X-Page-Count 헤더가 포함되어야 한다."""
        resp = self.client.post('/api/export/docx',
                                json={'title': '테스트', 'content': '본문 내용'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('X-Page-Count', resp.headers)

    # ─── POST /api/export/markdown ───

    @patch('services.data.supabase_service.is_supabase_enabled', return_value=False)
    @patch('services.export.export_service.export_markdown')
    def test_export_markdown_success(self, mock_export_md, _mock_sb):
        """마크다운 내보내기 성공."""
        import io
        mock_buf = io.BytesIO(b'# Test\n\nContent')
        mock_buf.seek(0)
        mock_export_md.return_value = mock_buf

        resp = self.client.post('/api/export/markdown',
                                json={'title': '테스트', 'content': '# 테스트 콘텐츠'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/markdown', resp.content_type)

    @patch('services.data.supabase_service.is_supabase_enabled', return_value=False)
    def test_export_markdown_missing_content_returns_400(self, _mock_sb):
        """콘텐츠 없이 마크다운 내보내기 시 400."""
        resp = self.client.post('/api/export/markdown',
                                json={'title': '테스트', 'content': ''},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.get_json())

    @patch('services.data.supabase_service.is_supabase_enabled', return_value=True)
    def test_export_markdown_requires_auth(self, _mock_enabled):
        """Supabase 활성화 시 인증 없이 401."""
        resp = self.client.post('/api/export/markdown',
                                json={'title': '테스트', 'content': '내용'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 401)

    # ─── POST /api/export/html ───

    @patch('services.data.supabase_service.is_supabase_enabled', return_value=False)
    def test_export_html_success(self, _mock_sb):
        """HTML 내보내기 성공."""
        resp = self.client.post('/api/export/html',
                                json={'title': '테스트', 'html': '<p>내용</p>'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/html', resp.content_type)

    @patch('services.data.supabase_service.is_supabase_enabled', return_value=False)
    def test_export_html_missing_content_returns_400(self, _mock_sb):
        """콘텐츠 없이 HTML 내보내기 시 400."""
        resp = self.client.post('/api/export/html',
                                json={'title': '테스트'},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)

    # ─── POST /api/export/epub ───

    @patch('services.data.supabase_service.is_supabase_enabled', return_value=False)
    def test_export_epub_missing_content_returns_400(self, _mock_sb):
        """콘텐츠 없이 EPUB 변환 시 400."""
        resp = self.client.post('/api/export/epub',
                                json={'title': '테스트', 'content': ''},
                                headers=_HEADERS)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.get_json())


if __name__ == '__main__':
    unittest.main()
