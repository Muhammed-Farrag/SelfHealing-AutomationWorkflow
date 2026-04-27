import React, { useEffect, useState } from 'react';
import { fetchBenchmark, BenchmarkResponse } from '../services/api';

const FAILURE_COLORS: Record<string, string> = {
  timeout: '#f59e0b',
  http_error: '#ef4444',
  missing_file: '#3b82f6',
  missing_column: '#8b5cf6',
  missing_db: '#f97316',
};

export function Benchmark() {
  const [res, setRes] = useState<BenchmarkResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBenchmark()
      .then(setRes)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState msg={error} onRetry={() => { setLoading(true); setError(null); }} />;
  if (!res) return null;

  const { selfhealing, baseline, deltas, criteria_met, total_episodes, evaluated_at } = res.data;

  // Render Metric Comparisons
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4', margin: 0, letterSpacing: '0.02em' }}>
          A/B EVALUATION BENCHMARK
        </h1>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginTop: 4 }}>
          SYSTEM VALIDATION · BASELINE VS SELF-HEALING AI · {evaluated_at.slice(0, 19).replace('T', ' ')} UTC
        </div>
      </div>

      {/* VERDICT HERO */}
      <div
        style={{
          backgroundColor: criteria_met.all_met ? 'rgba(16, 185, 129, 0.05)' : 'rgba(239, 68, 68, 0.05)',
          border: `1px solid ${criteria_met.all_met ? '#10b981' : '#ef4444'}`,
          borderLeft: `4px solid ${criteria_met.all_met ? '#10b981' : '#ef4444'}`,
          padding: '24px',
        }}
      >
        <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 24, color: criteria_met.all_met ? '#10b981' : '#ef4444', marginBottom: 8 }}>
          {criteria_met.all_met ? 'ALL CRITERIA MET — SYSTEM VALIDATED' : 'CRITERIA NOT MET'}
        </div>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4' }}>
          {Object.values(criteria_met).filter(x => x).length - 1} / 4 success criteria met.
        </div>
      </div>

      {/* Overall Metric Comparison */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 16 }}>
        <Panel title="OVERALL METRIC COMPARISON">
          <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', borderBottom: '1px solid #1e2530' }}>
                <th style={{ padding: '12px 0' }}>METRIC</th>
                <th>SELF-HEALING</th>
                <th>BASELINE</th>
                <th>DELTA</th>
                <th>TARGET</th>
                <th>STATUS</th>
              </tr>
            </thead>
            <tbody style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#d0d8e4' }}>
              <tr style={{ borderBottom: '1px solid #1e2530' }}>
                <td style={{ padding: '12px 0', color: '#00d4aa' }}>Repair Success Rate (RSR)</td>
                <td>{(selfhealing.rsr * 100).toFixed(1)}%</td>
                <td>{(baseline.rsr * 100).toFixed(1)}%</td>
                <td style={{ color: deltas.rsr_improvement > 0 ? '#10b981' : '#ef4444' }}>
                  +{deltas.rsr_improvement.toFixed(1)}%
                </td>
                <td>&gt; 70.0%</td>
                <td>{criteria_met.rsr ? '✅' : '❌'}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #1e2530' }}>
                <td style={{ padding: '12px 0', color: '#00d4aa' }}>Mean Time To Repair (MTTR)</td>
                <td>{selfhealing.mttr_mean.toFixed(1)}s</td>
                <td>{baseline.mttr_mean.toFixed(1)}s</td>
                <td style={{ color: deltas.mttr_reduction_pct > 0 ? '#10b981' : '#ef4444' }}>
                  -{deltas.mttr_reduction_pct.toFixed(1)}%
                </td>
                <td>&gt; 40.0% reduction</td>
                <td>{criteria_met.mttr_reduction ? '✅' : '❌'}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #1e2530' }}>
                <td style={{ padding: '12px 0', color: '#00d4aa' }}>False Repair Rate (FRR)</td>
                <td>{(selfhealing.frr * 100).toFixed(1)}%</td>
                <td>{(baseline.frr * 100).toFixed(1)}%</td>
                <td>0.0%</td>
                <td>&lt; 10.0%</td>
                <td>{criteria_met.frr ? '✅' : '❌'}</td>
              </tr>
              <tr>
                <td style={{ padding: '12px 0', color: '#00d4aa' }}>Guardrail Violations (GV)</td>
                <td>{selfhealing.gv}</td>
                <td>{baseline.gv}</td>
                <td>0</td>
                <td>0</td>
                <td>{criteria_met.gv ? '✅' : '❌'}</td>
              </tr>
            </tbody>
          </table>
        </Panel>
      </div>

      {/* Per-Class Breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: 16 }}>
        <Panel title="PER-CLASS BREAKDOWN">
          <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', borderBottom: '1px solid #1e2530' }}>
                <th style={{ padding: '12px 0' }}>FAILURE CLASS</th>
                <th>SH MTTR</th>
                <th>SH BAR</th>
                <th>BL MTTR</th>
                <th>BL BAR</th>
                <th>WINNER</th>
              </tr>
            </thead>
            <tbody style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#d0d8e4' }}>
              {Object.keys(selfhealing.per_class).map((cls) => {
                const shData = selfhealing.per_class[cls];
                const blData = baseline.per_class[cls];
                const shMttr = shData.count > 0 ? shData.mttr_mean : 0;
                const blMttr = blData.count > 0 ? blData.mttr_mean : 600; // default cap visual
                const winner = (!blData.count || shMttr < blMttr) ? 'SH' : 'BL';
                const color = FAILURE_COLORS[cls] || '#4a5a6a';

                return (
                  <tr key={cls} style={{ borderBottom: '1px solid #1e2530' }}>
                    <td style={{ padding: '16px 0', color }}>{cls.toUpperCase()}</td>
                    <td>{shData.count > 0 ? `${shMttr.toFixed(1)}s` : 'N/A'}</td>
                    <td style={{ width: 200, paddingRight: 20 }}>
                      <div style={{ backgroundColor: '#1e2530', height: 10, width: '100%' }}>
                        <div style={{ backgroundColor: winner === 'SH' ? '#00d4aa' : '#4a5a6a', height: '100%', width: `${Math.min((shMttr / 600) * 100, 100)}%` }}></div>
                      </div>
                    </td>
                    <td>{blData.count > 0 ? `${blMttr.toFixed(1)}s` : 'N/A'}</td>
                    <td style={{ width: 200, paddingRight: 20 }}>
                      <div style={{ backgroundColor: '#1e2530', height: 10, width: '100%' }}>
                        <div style={{ backgroundColor: winner === 'BL' ? '#00d4aa' : '#4a5a6a', height: '100%', width: `${Math.min((blMttr / 600) * 100, 100)}%` }}></div>
                      </div>
                    </td>
                    <td style={{ color: winner === 'SH' ? '#00d4aa' : '#ef4444' }}>{winner}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Panel>
      </div>

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
      <div style={{ height: 100, backgroundColor: '#111418', border: '1px solid #1e2530', animation: 'pulse 1.5s ease-in-out infinite', opacity: 0.6 }} />
      <div style={{ height: 300, backgroundColor: '#111418', border: '1px solid #1e2530', animation: 'pulse 1.5s ease-in-out infinite', opacity: 0.6 }} />
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', textAlign: 'center' }}>RUNNING DETERMINISTIC BENCHMARK SIMULATION...</div>
    </div>
  );
}

function ErrorState({ msg, onRetry }: { msg: string; onRetry: () => void }) {
  return (
    <div style={{ backgroundColor: '#1a0a0a', border: '1px solid #ef4444', padding: 24, display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'flex-start' }}>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#ef4444' }}>⚠ BENCHMARK EXECUTION FAILED</div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a' }}>{msg}</div>
      <button onClick={onRetry} style={{ backgroundColor: 'transparent', border: '1px solid #ef4444', color: '#ef4444', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, padding: '6px 14px', cursor: 'pointer' }}>
        RETRY
      </button>
    </div>
  );
}
