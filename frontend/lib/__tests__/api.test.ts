import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { apiUrl } from '../api';

// fetch를 전역 모킹
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

// sse-parser 모킹 (api.ts가 import하므로)
vi.mock('@/lib/sse-parser', () => ({
  parseSSEStream: vi.fn(),
}));

describe('apiUrl', () => {
  it('NEXT_PUBLIC_API_URL이 비어있으면 path만 반환한다', () => {
    // API_BASE는 모듈 로드 시점에 결정되므로 기본값 '' 사용
    const result = apiUrl('/api/providers');
    expect(result).toBe('/api/providers');
  });

  it('path를 API_BASE에 이어붙인다', () => {
    const result = apiUrl('/generate');
    expect(result).toBe('/generate');
  });
});

describe('request (fetchProviders를 통한 간접 테스트)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('성공 응답을 JSON으로 파싱한다', async () => {
    const mockData = { providers: [{ id: 'gemini', name: 'Gemini' }] };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockData),
    });

    // fetchProviders는 request('/api/providers')를 호출
    const { fetchProviders } = await import('../api');
    const result = await fetchProviders();

    expect(result).toEqual(mockData);
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/providers',
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it('HTTP 에러 시 에러 메시지를 throw한다', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: '서버 내부 오류' }),
    });

    const { fetchProviders } = await import('../api');
    await expect(fetchProviders()).rejects.toThrow('서버 내부 오류');
  });

  it('HTTP 에러 body 파싱 실패 시 상태코드 메시지를 throw한다', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 502,
      json: () => Promise.reject(new Error('not json')),
    });

    const { fetchProviders } = await import('../api');
    await expect(fetchProviders()).rejects.toThrow('HTTP 502');
  });

  it('타임아웃 시 AbortError를 한국어 메시지로 변환한다', async () => {
    // fetch가 AbortError를 throw하도록 설정
    const abortError = new DOMException('The operation was aborted', 'AbortError');
    mockFetch.mockRejectedValueOnce(abortError);

    const { fetchProviders } = await import('../api');
    await expect(fetchProviders()).rejects.toThrow('요청 시간이 초과되었습니다');
  });

  it('Content-Type: application/json 헤더를 설정한다', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ providers: [] }),
    });

    const { fetchProviders } = await import('../api');
    await fetchProviders();

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/providers',
      expect.objectContaining({
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
      }),
    );
  });
});
