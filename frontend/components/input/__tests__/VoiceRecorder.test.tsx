import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import VoiceRecorder from '../VoiceRecorder';

// lucide-react 아이콘 모킹
vi.mock('lucide-react', () => ({
  Mic: (props: Record<string, unknown>) => <svg data-testid="mic-icon" {...props} />,
  Square: (props: Record<string, unknown>) => <svg data-testid="square-icon" {...props} />,
  Loader2: (props: Record<string, unknown>) => <svg data-testid="loader-icon" {...props} />,
}));

// Button 컴포넌트 모킹
vi.mock('@/components/ui/button', () => ({
  Button: ({
    children,
    ...props
  }: React.PropsWithChildren<Record<string, unknown>>) => (
    <button
      {...(props as React.ButtonHTMLAttributes<HTMLButtonElement>)}
    >
      {children}
    </button>
  ),
}));

describe('VoiceRecorder', () => {
  const mockOnRecordingComplete = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('초기 상태에서 "음성 녹음" 버튼을 렌더링한다', () => {
    render(<VoiceRecorder onRecordingComplete={mockOnRecordingComplete} />);

    expect(screen.getByText('음성 녹음')).toBeInTheDocument();
  });

  it('마이크 아이콘이 표시된다', () => {
    render(<VoiceRecorder onRecordingComplete={mockOnRecordingComplete} />);

    expect(screen.getByTestId('mic-icon')).toBeInTheDocument();
  });

  it('disabled 상태에서 버튼이 비활성화된다', () => {
    render(
      <VoiceRecorder
        onRecordingComplete={mockOnRecordingComplete}
        disabled={true}
      />,
    );

    const button = screen.getByText('음성 녹음').closest('button');
    expect(button).toBeDisabled();
  });

  it('초기 상태에서 "녹음 중지" 버튼이 보이지 않는다', () => {
    render(<VoiceRecorder onRecordingComplete={mockOnRecordingComplete} />);

    expect(screen.queryByText('녹음 중지')).not.toBeInTheDocument();
  });

  it('에러 메시지가 초기에는 표시되지 않는다', () => {
    const { container } = render(
      <VoiceRecorder onRecordingComplete={mockOnRecordingComplete} />,
    );

    const errorElement = container.querySelector('.text-destructive');
    expect(errorElement).not.toBeInTheDocument();
  });
});
