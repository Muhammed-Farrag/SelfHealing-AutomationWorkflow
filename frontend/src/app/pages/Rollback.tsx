import React, { useEffect, useState } from 'react';
import { fetchRollbackList, executeRollback, ApiAuditEntry } from '../services/api';

export function Rollback() {
  const [patches, setPatches] = useState<ApiAuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rollbackTarget, setRollbackTarget] = useState<ApiAuditEntry | null>(null);
  const [dryRunResult, setDryRunResult] = useState<any | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 5000); };

  const load = () => {
    setLoading(true); setError(null);
    fetchRollbackList()
      .then(r => setPatches(r.rollback_eligible))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const handleDryRun = async (entry: ApiAuditEntry) => {
    setBusy(true);
    try {
      const result = await executeRollback(entry.plan_id, true) as any;
      setDryRunResult(result);
    } catch (e: any) { showToast(`⚠ DRY RUN FAILED: ${e.message}`); }
    finally { setBusy(false); }
  };

  const handleRollback = async (entry: ApiAuditEntry) => {
    setBusy(true);
    try {
      const result = await executeRollback(entry.plan_id, false) as any;
      showToast(`↺ ROLLBACK COMPLETE: ${entry.plan_id} — reverted ${entry.git_commit_hash}`);
      setRollbackTarget(null);
      setDryRunResult(null);
      load();
    } catch (e: any) { showToast(`⚠ ROLLBACK FAILED: ${e.message}`); }
    finally { setBusy(false); }
  };

  if (loading) return <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', padding: 32, textAlign: 'center' }}>LOADING ROLLBACK HISTORY...</div>;
  if (error) return (
    <div style={{ backgroundColor: '#1a0a0a', border: '1px solid #ef4444', padding: 24 }}>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#ef4444', marginBottom: 8 }}>⚠ FAILED TO LOAD ROLLBACK LIST</div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', marginBottom: 12 }}>{error}</div>
      <button onClick={load} style={{ backgroundColor: 'transparent', border: '1px solid #ef4444', color: '#ef4444', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, padding: '6px 14px', cursor: 'pointer' }}>RETRY</button>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4', margin: 0 }}>ROLLBACK MANAGER</h1>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginTop: 4 }}>
          {patches.length} ROLLBACK-ELIGIBLE PATCHES · LIVE DATA
        </div>
      </div>

      {patches.length === 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 240, gap: 12 }}>
          <div style={{ fontSize: 40, color: '#3b82f6' }}>↺</div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#4a5a6a' }}>NO ROLLBACK-ELIGIBLE PATCHES FOUND</div>
        </div>
      ) : (
        <div style={{ border: '1px solid #1e2530', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ backgroundColor: '#161b22', borderBottom: '1px solid #1e2530' }}>
                {['PLAN ID', 'FAILURE CLASS', 'APPLIED AT', 'GIT COMMIT', 'APPLIED BY', 'ACTIONS'].map(col => (
                  <th key={col} style={{ padding: '10px 14px', textAlign: 'left', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', fontWeight: 700, whiteSpace: 'nowrap' }}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {patches.map((entry, i) => (
                <PatchRow key={i} entry={entry} onDryRun={() => { setRollbackTarget(entry); handleDryRun(entry); }} onRollback={() => setRollbackTarget(entry)} busy={busy} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Confirmation Modal */}
      {rollbackTarget && (
        <>
          <div onClick={() => { setRollbackTarget(null); setDryRunResult(null); }} style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.7)', zIndex: 40 }} />
          <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', backgroundColor: '#161b22', border: '1px solid #1e2530', padding: 28, zIndex: 50, width: 520 }}>
            <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 16, color: '#ef4444', marginBottom: 16 }}>CONFIRM ROLLBACK</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', marginBottom: 12 }}>
              You are about to revert: <span style={{ color: '#f59e0b' }}>{rollbackTarget.plan_id}</span>
            </div>
            <div style={{ backgroundColor: '#0a0c0f', border: '1px solid #1e2530', padding: '10px 14px', marginBottom: 12, fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#00d4aa' }}>
              $ git revert {rollbackTarget.git_commit_hash}
            </div>

            {dryRunResult && (
              <div style={{ backgroundColor: '#111418', border: '1px solid #3b82f6', padding: '10px 14px', marginBottom: 16 }}>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#3b82f6', marginBottom: 6, letterSpacing: '0.15em' }}>DRY RUN PREVIEW</div>
                {dryRunResult.would_revert && dryRunResult.would_revert.length > 0
                  ? dryRunResult.would_revert.map((f: string, i: number) => <div key={i} style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#3b82f6' }}>{f}</div>)
                  : <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a' }}>No file changes tracked in diff.</div>
                }
              </div>
            )}

            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => handleRollback(rollbackTarget)} disabled={busy} style={{ flex: 1, backgroundColor: '#ef4444', border: 'none', color: '#fff', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, fontWeight: 700, padding: 10, cursor: busy ? 'not-allowed' : 'pointer', letterSpacing: '0.1em', opacity: busy ? 0.6 : 1 }}>
                {busy ? '...' : 'CONFIRM ROLLBACK'}
              </button>
              <button onClick={() => { setRollbackTarget(null); setDryRunResult(null); }} style={{ flex: 1, backgroundColor: 'transparent', border: '1px solid #2a3540', color: '#4a5a6a', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, padding: 10, cursor: 'pointer' }}>CANCEL</button>
            </div>
          </div>
        </>
      )}

      {toast && (
        <div style={{ position: 'fixed', bottom: 24, right: 24, backgroundColor: '#111418', border: '1px solid #1e2530', borderLeft: '3px solid #3b82f6', padding: '12px 20px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#d0d8e4', zIndex: 9999, display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ color: '#3b82f6' }}>↺</span>{toast}
          <button onClick={() => setToast(null)} style={{ background: 'none', border: 'none', color: '#4a5a6a', cursor: 'pointer', fontSize: 14 }}>×</button>
        </div>
      )}
    </div>
  );
}

function PatchRow({ entry, onDryRun, onRollback, busy }: { entry: ApiAuditEntry; onDryRun: () => void; onRollback: () => void; busy: boolean }) {
  const [hovered, setHovered] = useState(false);
  return (
    <tr onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} style={{ borderBottom: '1px solid #1e2530', backgroundColor: hovered ? '#161b22' : 'transparent', height: 40, transition: 'background-color 0.1s ease' }}>
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#d0d8e4' }}>{entry.plan_id}</td>
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#f59e0b' }}>{entry.failure_class || '—'}</td>
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', whiteSpace: 'nowrap' }}>{entry.applied_at?.slice(0, 19).replace('T', ' ')}</td>
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#3b82f6' }}>{entry.git_commit_hash || '—'}</td>
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#4a5a6a' }}>{entry.applied_by || 'system'}</td>
      <td style={{ padding: '0 14px' }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={onDryRun} disabled={busy} style={{ background: 'transparent', border: '1px solid #2a3540', color: '#4a5a6a', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, padding: '3px 8px', cursor: busy ? 'not-allowed' : 'pointer', letterSpacing: '0.1em' }}>DRY RUN</button>
          <button onClick={onRollback} disabled={busy} style={{ background: 'transparent', border: '1px solid #ef4444', color: '#ef4444', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, padding: '3px 8px', cursor: busy ? 'not-allowed' : 'pointer', letterSpacing: '0.1em' }}>ROLLBACK</button>
        </div>
      </td>
    </tr>
  );
}
