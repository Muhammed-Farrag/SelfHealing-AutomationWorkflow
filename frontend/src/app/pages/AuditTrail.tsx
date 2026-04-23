import React, { useEffect, useState } from 'react';
import { fetchAudit, exportAudit, ApiAuditEntry } from '../services/api';

const STATUS_COLORS: Record<string, string> = {
  applied: '#00d4aa', rejected: '#ef4444', rolled_back: '#3b82f6', dry_run: '#8b5cf6',
};

const STATUS_LABELS: Record<string, string> = {
  applied: 'PATCH APPLIED', rejected: 'REJECTED', rolled_back: 'ROLLBACK EXECUTED',
  dry_run: 'DRY RUN', unknown: 'UNKNOWN',
};

export function AuditTrail() {
  const [entries, setEntries] = useState<ApiAuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState('all');

  const load = () => {
    setLoading(true); setError(null);
    fetchAudit({ limit: 200 })
      .then(r => setEntries(r.entries))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const filtered = entries.filter(e => filterStatus === 'all' || e.status === filterStatus);

  if (loading) return <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', padding: 32, textAlign: 'center' }}>LOADING AUDIT TRAIL...</div>;
  if (error) return (
    <div style={{ backgroundColor: '#1a0a0a', border: '1px solid #ef4444', padding: 24 }}>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#ef4444', marginBottom: 8 }}>⚠ FAILED TO LOAD AUDIT LOG</div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', marginBottom: 12 }}>{error}</div>
      <button onClick={load} style={{ backgroundColor: 'transparent', border: '1px solid #ef4444', color: '#ef4444', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, padding: '6px 14px', cursor: 'pointer' }}>RETRY</button>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4', margin: 0 }}>AUDIT TRAIL</h1>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginTop: 4 }}>
            {filtered.length} EVENTS · LIVE DATA
          </div>
        </div>
        <button onClick={exportAudit} style={{ backgroundColor: 'transparent', border: '1px solid #2a3540', color: '#d0d8e4', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, padding: '8px 14px', cursor: 'pointer', letterSpacing: '0.15em' }}>
          ↓ EXPORT MARKDOWN REPORT
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 10 }}>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} style={{ backgroundColor: '#111418', border: '1px solid #1e2530', color: '#d0d8e4', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, padding: '6px 10px', outline: 'none', cursor: 'pointer' }}>
          {[{ v: 'all', l: 'ALL EVENTS' }, { v: 'applied', l: 'APPLIED' }, { v: 'rejected', l: 'REJECTED' }, { v: 'rolled_back', l: 'ROLLBACK' }, { v: 'dry_run', l: 'DRY RUN' }].map(o => (
            <option key={o.v} value={o.v} style={{ backgroundColor: '#111418' }}>{o.l}</option>
          ))}
        </select>
      </div>

      {/* Timeline */}
      <div style={{ position: 'relative', paddingLeft: 32 }}>
        {filtered.length === 0 ? (
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', padding: 24, textAlign: 'center' }}>NO AUDIT ENTRIES FOUND</div>
        ) : (
          filtered.map((entry, i) => {
            const color = STATUS_COLORS[entry.status] || '#4a5a6a';
            const label = STATUS_LABELS[entry.status] || entry.status?.toUpperCase();
            const ts = entry.applied_at ? entry.applied_at.replace('T', ' ').slice(0, 19) + ' UTC' : '';
            return (
              <div key={i} style={{ position: 'relative', paddingBottom: i === filtered.length - 1 ? 0 : 20, display: 'flex', gap: 0 }}>
                {i < filtered.length - 1 && <div style={{ position: 'absolute', left: -22, top: 16, width: 1, height: 'calc(100% + 4px)', backgroundColor: '#1e2530' }} />}
                <div style={{ position: 'absolute', left: -28, top: 6, width: 10, height: 10, borderRadius: '50%', backgroundColor: color, border: `1px solid ${color}`, boxShadow: `0 0 6px ${color}60` }} />
                <div style={{ flex: 1, backgroundColor: '#111418', border: '1px solid #1e2530', padding: '10px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color, border: `1px solid ${color}`, padding: '1px 6px', letterSpacing: '0.1em', backgroundColor: `${color}15`, whiteSpace: 'nowrap' }}>{label}</span>
                    </div>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#d0d8e4', lineHeight: 1.5 }}>
                      Plan: {entry.plan_id}{entry.failure_class ? ` — ${entry.failure_class}` : ''}
                    </div>
                    {entry.rejection_reason && <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#ef4444', marginTop: 4 }}>Reason: {entry.rejection_reason}</div>}
                    <div style={{ marginTop: 4 }}>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#00d4aa' }}>{entry.episode_id || ''}</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a' }}>{ts}</span>
                    {entry.git_commit_hash && <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#3b82f6' }}>{entry.git_commit_hash}</span>}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
