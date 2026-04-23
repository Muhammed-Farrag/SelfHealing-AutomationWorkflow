import React, { useState } from 'react';
import { REPAIR_PLANS, RepairPlan } from '../data/mockData';
import { StatusBadge } from '../components/StatusBadge';
import { ConfidenceBar, ConfidenceGauge } from '../components/ConfidenceGauge';

const OPERATOR_COLORS: Record<string, string> = {
  set_env: '#3b82f6',
  set_retry: '#f59e0b',
  set_timeout: '#f59e0b',
  replace_path: '#3b82f6',
  add_precheck: '#8b5cf6',
};

export function RepairPlans() {
  const [selected, setSelected] = useState<RepairPlan | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [rejectInput, setRejectInput] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4', margin: 0 }}>
          REPAIR PLANS
        </h1>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginTop: 4 }}>
          {REPAIR_PLANS.length} PLANS GENERATED · {REPAIR_PLANS.filter(p => p.status === 'applied').length} APPLIED
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
        {REPAIR_PLANS.map(plan => (
          <PlanCard
            key={plan.id}
            plan={plan}
            onClick={() => setSelected(plan)}
            isSelected={selected?.id === plan.id}
          />
        ))}
      </div>

      {selected && (
        <PlanDetailOverlay
          plan={selected}
          onClose={() => { setSelected(null); setRejectInput(false); setRejectReason(''); }}
          onApprove={() => { showToast(`PATCH APPLIED: ${selected.id}`); setSelected(null); }}
          onReject={() => { setRejectInput(true); }}
          rejectInput={rejectInput}
          rejectReason={rejectReason}
          setRejectReason={setRejectReason}
          onConfirmReject={() => {
            showToast(`REJECTED: ${selected.id}`);
            setSelected(null);
            setRejectInput(false);
            setRejectReason('');
          }}
        />
      )}

      {toast && (
        <div style={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          backgroundColor: '#111418',
          border: '1px solid #1e2530',
          borderLeft: '3px solid #00d4aa',
          padding: '12px 20px',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          color: '#d0d8e4',
          zIndex: 9999,
          display: 'flex',
          alignItems: 'center',
          gap: 16,
        }}>
          <span style={{ color: '#00d4aa' }}>✓</span>
          {toast}
          <button onClick={() => setToast(null)} style={{ background: 'none', border: 'none', color: '#4a5a6a', cursor: 'pointer', fontSize: 14 }}>×</button>
        </div>
      )}
    </div>
  );
}

function PlanCard({ plan, onClick, isSelected }: { plan: RepairPlan; onClick: () => void; isSelected: boolean }) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        backgroundColor: '#111418',
        border: `1px solid ${isSelected ? '#00d4aa' : hovered ? '#2a3540' : '#1e2530'}`,
        cursor: 'pointer',
        transition: 'border-color 0.1s ease',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #1e2530', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#161b22' }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#4a5a6a' }}>{plan.id}</span>
        <StatusBadge type="failure_class" value={plan.failureClass} />
      </div>

      <div style={{ padding: '12px 16px', flex: 1 }}>
        <div style={{ marginBottom: 10 }}>
          <ConfidenceBar value={plan.confidence} />
        </div>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', lineHeight: 1.6, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
          {plan.reasoning}
        </div>
      </div>

      <div style={{ padding: '10px 16px', borderTop: '1px solid #1e2530', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a' }}>
            {plan.actions.length} actions
          </span>
          {plan.requiresHuman && (
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: '#f59e0b', border: '1px solid #f59e0b', padding: '1px 6px' }}>
              ⚠ HUMAN REQUIRED
            </span>
          )}
        </div>
        <StatusBadge type="status" value={plan.status} />
      </div>
    </div>
  );
}

function PlanDetailOverlay({
  plan, onClose, onApprove, onReject, rejectInput, rejectReason, setRejectReason, onConfirmReject,
}: {
  plan: RepairPlan;
  onClose: () => void;
  onApprove: () => void;
  onReject: () => void;
  rejectInput: boolean;
  rejectReason: string;
  setRejectReason: (v: string) => void;
  onConfirmReject: () => void;
}) {
  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.7)', zIndex: 40 }} />
      <div style={{
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        width: 760,
        maxHeight: '90vh',
        backgroundColor: '#111418',
        border: '1px solid #1e2530',
        zIndex: 50,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {/* Zone A - Plan Header */}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #1e2530', backgroundColor: '#161b22' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, color: '#d0d8e4', marginBottom: 6 }}>{plan.id}</div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <StatusBadge type="failure_class" value={plan.failureClass} size="md" />
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a' }}>{plan.timestamp}</span>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <ConfidenceGauge value={plan.confidence} size={80} />
              <button onClick={onClose} style={{ background: 'none', border: '1px solid #1e2530', color: '#4a5a6a', fontSize: 16, cursor: 'pointer', width: 28, height: 28 }}>×</button>
            </div>
          </div>

          {plan.requiresHuman && (
            <div style={{ marginTop: 12, backgroundColor: 'rgba(239,68,68,0.08)', border: '1px solid #ef4444', padding: '8px 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#ef4444' }}>
              ⚠ REQUIRES HUMAN APPROVAL — Confidence below auto-patch threshold
            </div>
          )}

          <div style={{ marginTop: 12, backgroundColor: 'rgba(139,92,246,0.06)', borderLeft: '2px solid #8b5cf6', padding: '10px 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', lineHeight: 1.6 }}>
            {plan.reasoning}
          </div>
        </div>

        {/* Zone B - Repair Actions */}
        <div style={{ padding: '16px 24px', borderBottom: '1px solid #1e2530' }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginBottom: 12 }}>REPAIR ACTIONS</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {plan.actions.map((action, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '8px 12px', backgroundColor: '#161b22', border: '1px solid #1e2530', flexWrap: 'wrap' }}>
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 8,
                  color: OPERATOR_COLORS[action.operator] || '#4a5a6a',
                  border: `1px solid ${OPERATOR_COLORS[action.operator] || '#4a5a6a'}`,
                  padding: '2px 6px',
                  letterSpacing: '0.1em',
                  flexShrink: 0,
                  backgroundColor: `${OPERATOR_COLORS[action.operator] || '#4a5a6a'}15`,
                }}>
                  {action.operator.toUpperCase()}
                </span>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4' }}>{action.param}</span>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a' }}>=</span>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#00d4aa' }}>{action.newValue}</span>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', fontStyle: 'italic', flex: 1, minWidth: 200 }}>
                  — {action.justification}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Zone C - Diff Viewer */}
        <div style={{ padding: '16px 24px', borderBottom: '1px solid #1e2530' }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginBottom: 12 }}>FILE DIFF VIEWER</div>
          <div style={{ border: '1px solid #1e2530', overflow: 'hidden' }}>
            <div style={{ padding: '6px 14px', backgroundColor: '#1e2530', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a' }}>
              {plan.diffFile}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
              <div style={{ backgroundColor: '#1a0808', borderRight: '1px solid #2a1010', padding: '8px 0' }}>
                {plan.diffOld.map((line, i) => (
                  <div key={i} style={{ padding: '1px 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: line.trim() === '' ? '#1a0808' : '#ef4444', whiteSpace: 'pre' }}>
                    {line.trim() !== '' ? `− ${line}` : ' '}
                  </div>
                ))}
              </div>
              <div style={{ backgroundColor: '#081a0e', padding: '8px 0' }}>
                {plan.diffNew.map((line, i) => (
                  <div key={i} style={{ padding: '1px 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: line.trim() === '' ? '#081a0e' : '#00d4aa', whiteSpace: 'pre' }}>
                    {line.trim() !== '' ? `+ ${line}` : ' '}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Action bar */}
        <div style={{ padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              onClick={onApprove}
              style={{
                flex: 1,
                backgroundColor: '#00d4aa',
                border: 'none',
                color: '#0a0c0f',
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
                fontWeight: 700,
                padding: '10px',
                cursor: 'pointer',
                letterSpacing: '0.15em',
              }}
            >
              ✓ APPROVE
            </button>
            <button
              onClick={onReject}
              style={{
                flex: 1,
                backgroundColor: 'transparent',
                border: '1px solid #ef4444',
                color: '#ef4444',
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
                fontWeight: 700,
                padding: '10px',
                cursor: 'pointer',
                letterSpacing: '0.15em',
              }}
            >
              ✗ REJECT
            </button>
            <button
              style={{
                flex: 1,
                backgroundColor: 'transparent',
                border: '1px solid #2a3540',
                color: '#4a5a6a',
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
                padding: '10px',
                cursor: 'pointer',
                letterSpacing: '0.15em',
              }}
            >
              DRY RUN
            </button>
          </div>
          {rejectInput && (
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                value={rejectReason}
                onChange={e => setRejectReason(e.target.value)}
                placeholder="Rejection reason..."
                style={{
                  flex: 1,
                  backgroundColor: '#161b22',
                  border: '1px solid #ef4444',
                  color: '#d0d8e4',
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10,
                  padding: '8px 10px',
                  outline: 'none',
                }}
              />
              <button
                onClick={onConfirmReject}
                style={{
                  backgroundColor: '#ef4444',
                  border: 'none',
                  color: '#fff',
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10,
                  padding: '8px 14px',
                  cursor: 'pointer',
                  letterSpacing: '0.1em',
                }}
              >
                CONFIRM
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
