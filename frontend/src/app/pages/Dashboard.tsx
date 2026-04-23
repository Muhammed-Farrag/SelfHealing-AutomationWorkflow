import React, { useEffect, useState } from 'react';
import { fetchDashboardStats, fetchSettings, DashboardStats, ThresholdSettings } from '../services/api';

const FAILURE_COLORS: Record<string, string> = {
  timeout: '#f59e0b',
  http_error: '#ef4444',
  missing_file: '#3b82f6',
  missing_column: '#8b5cf6',
  missing_db: '#f97316',
};

export function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [settings, setSettings] = useState<ThresholdSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchDashboardStats(), fetchSettings()])
      .then(([s, t]) => { setStats(s); setSettings(t); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState msg={error} onRetry={() => { setLoading(true); setError(null); }} />;
  if (!stats) return null;

  const dist = Object.entries(stats.failure_distribution);
  const distTotal = dist.reduce((s, [, v]) => s + v, 0);

  const safetyRows = settings ? [
    { label: 'Confidence Threshold', marker: settings.confidence_threshold, current: settings.confidence_threshold },
    { label: 'Auto-patch Threshold', marker: settings.auto_patch_threshold, current: stats.auto_patch_rate / 100 },
    { label: 'Require Human Below', marker: settings.require_human_below, current: settings.require_human_below },
  ] : [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4', margin: 0, letterSpacing: '0.02em' }}>
          MISSION CONTROL
        </h1>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginTop: 4 }}>
          REAL-TIME PIPELINE HEALTH · {new Date().toISOString().replace('T', ' ').slice(0, 19)} UTC
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        <KpiCard value={String(stats.total_episodes)} label="TOTAL EPISODES" sub="classified episodes" />
        <KpiCard value={`${stats.auto_patch_rate}%`} label="AUTO-PATCH RATE" sub="unique patches applied" subColor="#00d4aa" />
        <KpiCard value={`${stats.mttr_minutes} min`} label="MTTR" sub="mean time to repair" />
        <KpiCard
          value={String(stats.pending_review_count)}
          label="PENDING REVIEW"
          sub={stats.pending_review_count > 0 ? '⚠ requires attention' : 'queue clear'}
          subColor={stats.pending_review_count > 0 ? '#f59e0b' : '#10b981'}
          alert={stats.pending_review_count > 0}
        />
      </div>

      {/* Middle section */}
      <div style={{ display: 'grid', gridTemplateColumns: '60fr 40fr', gap: 16 }}>
        {/* Failure Class Distribution */}
        <Panel title="FAILURE CLASS DISTRIBUTION">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '4px 0' }}>
            {dist.map(([cls, count]) => {
              const pct = distTotal > 0 ? ((count / distTotal) * 100).toFixed(1) : '0.0';
              const color = FAILURE_COLORS[cls] || '#4a5a6a';
              return (
                <div key={cls}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color, letterSpacing: '0.15em' }}>
                      {cls.toUpperCase()}
                    </span>
                    <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a' }}>{count} events</span>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#d0d8e4', minWidth: 36, textAlign: 'right' }}>{pct}%</span>
                    </div>
                  </div>
                  <div style={{ height: 8, backgroundColor: '#1e2530', borderRadius: 0, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${pct}%`, backgroundColor: color, opacity: 0.85 }} />
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>

        {/* Activity Feed */}
        <Panel title="RECENT ACTIVITY">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0, maxHeight: 260, overflowY: 'auto' }}>
            {stats.recent_activity.map((ev, i) => {
              const icon = ev.event_type === 'applied' ? '🟢' : ev.event_type === 'rejected' ? '🔴' : '🟡';
              return (
                <div key={i} style={{ display: 'flex', gap: 8, padding: '6px 0', borderBottom: '1px solid #1e2530', alignItems: 'flex-start' }}>
                  <span style={{ fontSize: 10, flexShrink: 0, marginTop: 1 }}>{icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', lineHeight: 1.4, wordBreak: 'break-word' }}>
                      {ev.description}
                    </div>
                  </div>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', flexShrink: 0, marginTop: 1 }}>
                    {ev.timestamp ? ev.timestamp.slice(11, 19) : ''}
                  </span>
                </div>
              );
            })}
          </div>
        </Panel>
      </div>

      {/* Safety Threshold Status */}
      {safetyRows.length > 0 && (
        <Panel title="SAFETY THRESHOLD STATUS">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20, padding: '4px 0' }}>
            {safetyRows.map((t, i) => (
              <div key={i}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.15em' }}>
                    {t.label.toUpperCase()} (threshold: {t.marker.toFixed(2)})
                  </span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#00d4aa' }}>
                    {t.current.toFixed(2)}
                  </span>
                </div>
                <div style={{ position: 'relative', height: 6, backgroundColor: '#1e2530' }}>
                  <div style={{ height: '100%', width: `${Math.min(t.current * 100, 100)}%`, backgroundColor: '#00d4aa', opacity: 0.8 }} />
                  <div style={{ position: 'absolute', top: -4, left: `${t.marker * 100}%`, width: 1, height: 14, backgroundColor: '#f59e0b' }} />
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

function KpiCard({ value, label, sub, subColor, alert }: { value: string; label: string; sub: string; subColor?: string; alert?: boolean }) {
  return (
    <div style={{ backgroundColor: '#161b22', border: '1px solid #1e2530', borderTop: '2px solid #00d4aa', padding: '20px 20px 16px' }}>
      <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 36, color: alert ? '#f59e0b' : '#d0d8e4', lineHeight: 1, marginBottom: 8 }}>{value}</div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginBottom: 6 }}>{label}</div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: subColor || '#4a5a6a' }}>{sub}</div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ backgroundColor: '#111418', border: '1px solid #1e2530', padding: 20 }}>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.25em', marginBottom: 16 }}>{title}</div>
      {children}
    </div>
  );
}

function LoadingState() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {[1, 2, 3].map(i => (
        <div key={i} style={{ height: 80, backgroundColor: '#111418', border: '1px solid #1e2530', animation: 'pulse 1.5s ease-in-out infinite', opacity: 0.6 }} />
      ))}
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', textAlign: 'center' }}>LOADING REAL-TIME DATA...</div>
    </div>
  );
}

function ErrorState({ msg, onRetry }: { msg: string; onRetry: () => void }) {
  return (
    <div style={{ backgroundColor: '#1a0a0a', border: '1px solid #ef4444', padding: 24, display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'flex-start' }}>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#ef4444' }}>⚠ BACKEND CONNECTION ERROR</div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a' }}>{msg}</div>
      <button onClick={onRetry} style={{ backgroundColor: 'transparent', border: '1px solid #ef4444', color: '#ef4444', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, padding: '6px 14px', cursor: 'pointer' }}>
        RETRY
      </button>
    </div>
  );
}
