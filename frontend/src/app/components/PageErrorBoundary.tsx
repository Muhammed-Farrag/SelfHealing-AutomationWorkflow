import React from 'react';

interface State {
  hasError: boolean;
  error: Error | null;
}

interface Props {
  children: React.ReactNode;
  /** Optional custom fallback. If omitted, the default styled fallback is used. */
  fallback?: React.ReactNode;
  /** Page/section name shown in the fallback header */
  pageName?: string;
}

/**
 * PageErrorBoundary — catches any React render error inside a page component
 * and shows a clean, branded fallback instead of the default React error screen.
 *
 * Usage:
 *   <PageErrorBoundary pageName="Intelligence">
 *     <Intelligence />
 *   </PageErrorBoundary>
 */
export class PageErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // In production you'd send this to Sentry / Datadog
    console.error('[PageErrorBoundary]', error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      const { error, } = this.state;
      const { pageName = 'Page' } = this.props;

      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-start',
          gap: 20,
          padding: 32,
        }}>
          {/* Header */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}>
            <div style={{
              width: 40, height: 40,
              backgroundColor: 'rgba(239,68,68,0.1)',
              border: '1px solid #ef4444',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 18,
            }}>
              ⚠
            </div>
            <div>
              <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 16, color: '#ef4444' }}>
                {pageName.toUpperCase()} CRASHED
              </div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.15em', marginTop: 2 }}>
                COMPONENT RENDER ERROR · SELF-HEALING UI v1.0
              </div>
            </div>
          </div>

          {/* Error message box */}
          <div style={{
            width: '100%',
            backgroundColor: '#0e1218',
            border: '1px solid #1e2530',
            borderLeft: '2px solid #ef4444',
            padding: '16px 20px',
          }}>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.15em', marginBottom: 8 }}>
              ERROR MESSAGE
            </div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#ef4444', lineHeight: 1.6, wordBreak: 'break-word' }}>
              {error?.name}: {error?.message}
            </div>
          </div>

          {/* Stack trace (collapsed-style) */}
          {error?.stack && (
            <details style={{ width: '100%' }}>
              <summary style={{
                fontFamily: "'JetBrains Mono', monospace", fontSize: 9,
                color: '#4a5a6a', letterSpacing: '0.15em', cursor: 'pointer',
                userSelect: 'none', padding: '4px 0',
              }}>
                STACK TRACE (click to expand)
              </summary>
              <div style={{
                marginTop: 8,
                backgroundColor: '#080b0e',
                border: '1px solid #1e2530',
                padding: '12px 16px',
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 9,
                color: '#4a5a6a',
                lineHeight: 1.8,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
                maxHeight: 200,
                overflowY: 'auto',
              }}>
                {error.stack}
              </div>
            </details>
          )}

          {/* Actions */}
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              onClick={this.handleReset}
              style={{
                backgroundColor: '#00d4aa',
                border: 'none',
                color: '#0a0c0f',
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 10,
                fontWeight: 700,
                padding: '8px 20px',
                cursor: 'pointer',
                letterSpacing: '0.15em',
              }}
            >
              ↺ RETRY
            </button>
            <button
              onClick={() => window.location.reload()}
              style={{
                backgroundColor: 'transparent',
                border: '1px solid #2a3540',
                color: '#4a5a6a',
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 10,
                padding: '8px 20px',
                cursor: 'pointer',
                letterSpacing: '0.15em',
              }}
            >
              RELOAD PAGE
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
