import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useKeyboardShortcuts } from '../useKeyboardShortcuts';

// uiStore 모킹
const mockSetSettingsModalOpen = vi.fn();
const mockToggleSidebar = vi.fn();
const mockSetActiveView = vi.fn();

vi.mock('@/stores/uiStore', () => ({
  useUIStore: () => ({
    setSettingsModalOpen: mockSetSettingsModalOpen,
    toggleSidebar: mockToggleSidebar,
    setActiveView: mockSetActiveView,
  }),
}));

describe('useKeyboardShortcuts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('mount 시 keydown 리스너를 등록한다', () => {
    const addSpy = vi.spyOn(window, 'addEventListener');
    const { unmount } = renderHook(() => useKeyboardShortcuts());

    expect(addSpy).toHaveBeenCalledWith('keydown', expect.any(Function));

    unmount();
    addSpy.mockRestore();
  });

  it('Ctrl+, 입력 시 설정 모달을 연다', () => {
    renderHook(() => useKeyboardShortcuts());

    act(() => {
      window.dispatchEvent(
        new KeyboardEvent('keydown', {
          key: ',',
          ctrlKey: true,
          shiftKey: false,
          altKey: false,
          bubbles: true,
        }),
      );
    });

    expect(mockSetSettingsModalOpen).toHaveBeenCalledWith(true);
  });

  it('Ctrl+B 입력 시 사이드바를 토글한다', () => {
    renderHook(() => useKeyboardShortcuts());

    act(() => {
      window.dispatchEvent(
        new KeyboardEvent('keydown', {
          key: 'b',
          ctrlKey: true,
          shiftKey: false,
          altKey: false,
          bubbles: true,
        }),
      );
    });

    expect(mockToggleSidebar).toHaveBeenCalled();
  });

  it('Alt+1 입력 시 메인 뷰로 전환한다', () => {
    renderHook(() => useKeyboardShortcuts());

    act(() => {
      window.dispatchEvent(
        new KeyboardEvent('keydown', {
          key: '1',
          altKey: true,
          ctrlKey: false,
          shiftKey: false,
          bubbles: true,
        }),
      );
    });

    expect(mockSetActiveView).toHaveBeenCalledWith('main');
  });

  it('Alt+2 입력 시 캘린더 뷰로 전환한다', () => {
    renderHook(() => useKeyboardShortcuts());

    act(() => {
      window.dispatchEvent(
        new KeyboardEvent('keydown', {
          key: '2',
          altKey: true,
          ctrlKey: false,
          shiftKey: false,
          bubbles: true,
        }),
      );
    });

    expect(mockSetActiveView).toHaveBeenCalledWith('calendar');
  });

  it('unmount 시 keydown 리스너를 제거한다', () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener');
    const { unmount } = renderHook(() => useKeyboardShortcuts());

    unmount();

    expect(removeSpy).toHaveBeenCalledWith('keydown', expect.any(Function));
    removeSpy.mockRestore();
  });

  it('정의된 단축키 목록을 반환한다', () => {
    const { result } = renderHook(() => useKeyboardShortcuts());

    expect(result.current).toHaveLength(4);
    expect(result.current[0]).toMatchObject({ key: ',', ctrl: true, label: '설정 열기' });
  });
});
