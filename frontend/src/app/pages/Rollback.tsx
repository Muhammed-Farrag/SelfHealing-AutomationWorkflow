import React, { useState } from 'react';
import { PATCH_RECORDS, PatchRecord } from '../data/mockData';

export function Rollback() {
  const [patches, setPatches] = useState(PATCH_RECORDS);
  const [rollbackTarget, setRollbackTarget] = useState<PatchRecord | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const handleRollback = (patch: PatchRecord) => {
    setPatches(prev => prev.map(p => p.id === patch.id ? { ...p, status: 'rolled_back' as const } : p));
    setRollbackTarget(null);
    showToast(`ROLLBACK COMPLETE: ${patch.planId} — git revert ${patch.commitHash}`);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4', margin: 0 }}>
          ROLLBACK MANAGER
        </h1>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginTop: 4 }}>
          {patches.length} PATCHES · {patches.filter(p => p.status === 'applied').length} ACTIVE
        </div>
      </div>

      {/* Table */}
      <div style={{ border: '1px solid #1e2530', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: '#161b22', borderBottom: '1px solid #1e2530' }}>
              {['PATCH ID', 'PLAN', 'FILE MODIFIED', 'APPLIED AT', 'GIT HASH', 'STATUS', 'ACTIONS'].map(col => (
                <th
                  key={col}
                  style={{
                    padding: '10px 14px',
                    textAlign: 'left',
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 9,
                    color: '#4a5a6a',
                    letterSpacing: '0.2em',
                    fontWeight: 700,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {patches.map(patch => (
              <PatchRow
                key={patch.id}
                patch={patch}
                onRollback={() => setRollbackTarget(patch)}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Rollback Confirmation Modal */}
      {rollbackTarget && (
        <>
          <div
            onClick={() => setRollbackTarget(null)}
            style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.7)', zIndex: 40 }}
          />
          <div style={{
            position: 'fixed',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            backgroundColor: '#161b22',
            border: '1px solid #1e2530',
            padding: 28,
            zIndex: 50,
            width: 480,
          }}>
            <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 16, color: '#ef4444', marginBottom: 16 }}>
              CONFIRM ROLLBACK
            </div>

            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', marginBottom: 12 }}>
              You are about to revert:{' '}
              <span style={{ color: '#f59e0b' }}>{rollbackTarget.planId}</span>
            </div>

            <div style={{ backgroundColor: '#111418', border: '1px solid #1e2530', padding: '10px 14px', marginBottom: 12 }}>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.15em', marginBottom: 6 }}>
                AFFECTED FILES
              </div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#3b82f6' }}>
                {rollbackTarget.fileModified}
              </div>
            </div>

            <div style={{ backgroundColor: '#0a0c0f', border: '1px solid #1e2530', padding: '10px 14px', marginBottom: 20 }}>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.15em', marginBottom: 6 }}>
                GIT COMMAND PREVIEW
              </div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#00d4aa' }}>
                $ git revert {rollbackTarget.commitHash}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={() => handleRollback(rollbackTarget)}
                style={{
                  flex: 1,
                  backgroundColor: '#ef4444',
                  border: 'none',
                  color: '#fff',
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 11,
                  fontWeight: 700,
                  padding: 10,
                  cursor: 'pointer',
                  letterSpacing: '0.1em',
                }}
              >
                CONFIRM ROLLBACK
              </button>
              <button
                onClick={() => setRollbackTarget(null)}
                style={{
                  flex: 1,
                  backgroundColor: 'transparent',
                  border: '1px solid #2a3540',
                  color: '#4a5a6a',
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 11,
                  padding: 10,
                  cursor: 'pointer',
                }}
              >
                CANCEL
              </button>
            </div>
          </div>
        </>
      )}

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          backgroundColor: '#111418',
          border: '1px solid #1e2530',
          borderLeft: '3px solid #3b82f6',
          padding: '12px 20px',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          color: '#d0d8e4',
          zIndex: 9999,
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          animation: 'fadeIn 0.2s ease',
        }}>
          <span style={{ color: '#3b82f6' }}>↺</span>
          {toast}
          <button onClick={() => setToast(null)} style={{ background: 'none', border: 'none', color: '#4a5a6a', cursor: 'pointer', fontSize: 14 }}>×</button>
        </div>
      )}
    </div>
  );
}

function PatchRow({ patch, onRollback }: { patch: PatchRecord; onRollback: () => void }) {
  const [hovered, setHovered] = useState(false);

  return (
    <tr
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        borderBottom: '1px solid #1e2530',
        backgroundColor: hovered ? '#161b22' : 'transparent',
        height: 40,
        transition: 'background-color 0.1s ease',
      }}
    >
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#4a5a6a' }}>
        {patch.id}
      </td>
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#d0d8e4' }}>
        {patch.planId}
      </td>
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#3b82f6' }}>
        {patch.fileModified}
      </td>
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', whiteSpace: 'nowrap' }}>
        {patch.appliedAt.replace('T', ' ').replace('Z', '')}
      </td>
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#f59e0b' }}>
        {patch.commitHash}
      </td>
      <td style={{ padding: '0 14px' }}>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 8,
          letterSpacing: '0.15em',
          color: patch.status === 'applied' ? '#10b981' : '#3b82f6',
          border: `1px solid ${patch.status === 'applied' ? '#10b981' : '#3b82f6'}`,
          padding: '2px 8px',
          backgroundColor: `${patch.status === 'applied' ? '#10b981' : '#3b82f6'}15`,
        }}>
          {patch.status.toUpperCase().replace('_', ' ')}
        </span>
      </td>
      <td style={{ padding: '0 14px' }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            style={{
              background: 'transparent',
              border: '1px solid #2a3540',
              color: '#4a5a6a',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 9,
              padding: '3px 8px',
              cursor: 'pointer',
              letterSpacing: '0.1em',
            }}
          >
            DRY RUN
          </button>
          {patch.status === 'applied' && (
            <button
              onClick={onRollback}
              style={{
                background: 'transparent',
                border: '1px solid #ef4444',
                color: '#ef4444',
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 9,
                padding: '3px 8px',
                cursor: 'pointer',
                letterSpacing: '0.1em',
              }}
            >
              ROLLBACK
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}
