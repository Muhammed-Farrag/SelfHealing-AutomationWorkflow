import React, { useEffect, useState } from 'react';
import { fetchPlans, approvePlan, rejectPlan, ApiPlan } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { ConfidenceBar, ConfidenceGauge } from '../components/ConfidenceGauge';

const OPERATOR_COLORS: Record<string, string> = {
  set_env: '#3b82f6', set_retry: '#f59e0b', set_timeout: '#f59e0b',
  replace_path: '#3b82f6', add_precheck: '#8b5cf6',
};

const FAILURE_COLORS: Record<string, string> = {
  timeout: '#f59e0b', http_error: '#ef4444', missing_file: '#3b82f6',
  missing_column: '#8b5cf6', missing_db: '#f97316',
};

function getActions(plan: ApiPlan) {
  if (Array.isArray(plan.repair_actions)) return plan.repair_actions;
  if (typeof plan.repair_actions === 'string' && plan.repair_actions.trim()) {
    try { return JSON.parse(plan.repair_actions); } catch { return []; }
  }
  return [];
}

export function RepairPlans() {
  const [plans, setPlans] = useState<ApiPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ApiPlan | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [rejectInput, setRejectInput] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [busy, setBusy] = useState(false);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 4000); };

  const load = () => {
    setLoading(true); setError(null);
    fetchPlans({ limit: 100 })
      .then(r => setPlans(r.plans))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const handleApprove = async (plan: ApiPlan) => {
    setBusy(true);
    try {
      await approvePlan(plan.plan_id, 'ui_user');
      showToast(`✓ PATCH APPLIED: ${plan.plan_id}`);
      setSelected(null);
      load();
    } catch (e: any) { showToast(`⚠ APPROVE FAILED: ${e.message}`); }
    finally { setBusy(false); }
  };

  const handleReject = async (plan: ApiPlan, reason: string) => {
    setBusy(true);
    try {
      await rejectPlan(plan.plan_id, 'ui_user', reason || 'Rejected via UI');
      showToast(`✗ REJECTED: ${plan.plan_id}`);
      setSelected(null);
      setRejectInput(false);
      setRejectReason('');
      load();
    } catch (e: any) { showToast(`⚠ REJECT FAILED: ${e.message}`); }
    finally { setBusy(false); }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState msg={error} onRetry={load} />;

  const pendingCount = plans.filter(p => p.status === 'pending').length;
  const appliedCount = plans.filter(p => p.status === 'applied').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4', margin: 0 }}>REPAIR PLANS</h1>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginTop: 4 }}>
          {plans.length} PLANS · {appliedCount} APPLIED · {pendingCount} PENDING · LIVE DATA
        </div>
      </div>

      {/* Contextual info banner */}
      <div style={{ backgroundColor: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.25)', padding: '10px 16px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        <span style={{ color: '#3b82f6', fontSize: 14, flexShrink: 0 }}>ℹ</span>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', lineHeight: 1.7 }}>
          <span style={{ color: '#d0d8e4' }}>REPAIR PLANS</span> — full history of all AI-generated plans (applied, pending, dry run). <br />
          Approve/Reject actions are only available for <span style={{ color: '#f59e0b' }}>PENDING</span> plans.
          Plans flagged <span style={{ color: '#f59e0b' }}>⚠ HUMAN REQUIRED</span> also appear in the{' '}
          <span style={{ color: '#00d4aa' }}>REVIEW QUEUE</span> for focused human review.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
        {plans.map(plan => (
          <PlanCard key={plan.plan_id} plan={plan} onClick={() => { setSelected(plan); setRejectInput(false); setRejectReason(''); }} isSelected={selected?.plan_id === plan.plan_id} />
        ))}
      </div>

      {selected && (
        <PlanDetailOverlay
          plan={selected}
          busy={busy}
          onClose={() => { setSelected(null); setRejectInput(false); setRejectReason(''); }}
          onApprove={() => handleApprove(selected)}
          onReject={() => setRejectInput(true)}
          rejectInput={rejectInput}
          rejectReason={rejectReason}
          setRejectReason={setRejectReason}
          onConfirmReject={() => handleReject(selected, rejectReason)}
        />
      )}

      {toast && (
        <div style={{ position: 'fixed', bottom: 24, right: 24, backgroundColor: '#111418', border: '1px solid #1e2530', borderLeft: '3px solid #00d4aa', padding: '12px 20px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#d0d8e4', zIndex: 9999, display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ color: '#00d4aa' }}>✓</span>{toast}
          <button onClick={() => setToast(null)} style={{ background: 'none', border: 'none', color: '#4a5a6a', cursor: 'pointer', fontSize: 14 }}>×</button>
        </div>
      )}
    </div>
  );
}

function PlanCard({ plan, onClick, isSelected }: { plan: ApiPlan; onClick: () => void; isSelected: boolean }) {
  const [hovered, setHovered] = useState(false);
  const actions = getActions(plan);
  const color = FAILURE_COLORS[plan.failure_class] || '#4a5a6a';
  return (
    <div onClick={onClick} onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}
      style={{ backgroundColor: '#111418', border: `1px solid ${isSelected ? '#00d4aa' : hovered ? '#2a3540' : '#1e2530'}`, cursor: 'pointer', transition: 'border-color 0.1s ease', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #1e2530', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#161b22' }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#4a5a6a' }}>{plan.plan_id}</span>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color, border: `1px solid ${color}`, padding: '2px 7px', backgroundColor: `${color}15` }}>{plan.failure_class?.toUpperCase()}</span>
      </div>
      <div style={{ padding: '12px 16px', flex: 1 }}>
        <div style={{ marginBottom: 10 }}><ConfidenceBar value={plan.confidence} /></div>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', lineHeight: 1.6, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{plan.reasoning}</div>
      </div>
      <div style={{ padding: '10px 16px', borderTop: '1px solid #1e2530', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a' }}>{actions.length} actions</span>
          {plan.requires_human_approval && <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: '#f59e0b', border: '1px solid #f59e0b', padding: '1px 6px' }}>⚠ HUMAN REQUIRED</span>}
        </div>
        <StatusBadge type="status" value={plan.status} />
      </div>
    </div>
  );
}

function PlanDetailOverlay({ plan, busy, onClose, onApprove, onReject, rejectInput, rejectReason, setRejectReason, onConfirmReject }: {
  plan: ApiPlan; busy: boolean; onClose: () => void; onApprove: () => void; onReject: () => void;
  rejectInput: boolean; rejectReason: string; setRejectReason: (v: string) => void; onConfirmReject: () => void;
}) {
  const actions = getActions(plan);
  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.7)', zIndex: 40 }} />
      <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: 760, maxHeight: '90vh', backgroundColor: '#111418', border: '1px solid #1e2530', zIndex: 50, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #1e2530', backgroundColor: '#161b22' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, color: '#d0d8e4', marginBottom: 6 }}>{plan.plan_id}</div>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: FAILURE_COLORS[plan.failure_class] || '#4a5a6a', border: `1px solid ${FAILURE_COLORS[plan.failure_class] || '#4a5a6a'}`, padding: '2px 7px' }}>{plan.failure_class?.toUpperCase()}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <ConfidenceGauge value={plan.confidence} size={80} />
              <button onClick={onClose} style={{ background: 'none', border: '1px solid #1e2530', color: '#4a5a6a', fontSize: 16, cursor: 'pointer', width: 28, height: 28 }}>×</button>
            </div>
          </div>
          {plan.requires_human_approval && <div style={{ marginTop: 12, backgroundColor: 'rgba(239,68,68,0.08)', border: '1px solid #ef4444', padding: '8px 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#ef4444' }}>⚠ REQUIRES HUMAN APPROVAL</div>}
          <div style={{ marginTop: 12, backgroundColor: 'rgba(139,92,246,0.06)', borderLeft: '2px solid #8b5cf6', padding: '10px 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', lineHeight: 1.6 }}>{plan.reasoning}</div>
        </div>

        <div style={{ padding: '16px 24px', borderBottom: '1px solid #1e2530' }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginBottom: 12 }}>REPAIR ACTIONS</div>
          {actions.length === 0 ? (
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a' }}>
              {plan.fallback_action === 'escalate_to_human' ? '⚠ ESCALATED TO HUMAN — no automated actions defined' : 'No structured actions available.'}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {actions.map((action: any, i: number) => {
                const op = action.operator || action.op || 'unknown';
                const clr = OPERATOR_COLORS[op] || '#4a5a6a';
                return (
                  <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '8px 12px', backgroundColor: '#161b22', border: '1px solid #1e2530', flexWrap: 'wrap' }}>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: clr, border: `1px solid ${clr}`, padding: '2px 6px', letterSpacing: '0.1em', backgroundColor: `${clr}15` }}>{op.toUpperCase()}</span>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4' }}>{action.param || action.key}</span>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a' }}>=</span>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#00d4aa' }}>{action.new_value ?? action.newValue ?? action.value}</span>
                    {action.justification && <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', fontStyle: 'italic', flex: 1, minWidth: 200 }}>— {action.justification}</span>}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div style={{ padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {/* Status-aware action explanation */}
          {plan.status !== 'pending' && (
            <div style={{ backgroundColor: '#161b22', border: '1px solid #1e2530', padding: '8px 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', lineHeight: 1.6 }}>
              {plan.status === 'applied' && '✓ This plan has been applied — no further actions available.'}
              {plan.status === 'dry_run' && '⚙ This was a dry run — apply manually or re-run to commit changes.'}
              {plan.status === 'rejected' && '✗ This plan was rejected — it is archived as read-only.'}
            </div>
          )}
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              onClick={onApprove}
              disabled={busy || plan.status !== 'pending'}
              title={plan.status !== 'pending' ? `Cannot approve: plan is already "${plan.status}"` : 'Approve and apply this repair plan'}
              style={{ flex: 1, backgroundColor: plan.status === 'pending' ? '#00d4aa' : '#1e2530', border: 'none', color: plan.status === 'pending' ? '#0a0c0f' : '#4a5a6a', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, fontWeight: 700, padding: 10, cursor: plan.status !== 'pending' ? 'not-allowed' : 'pointer', letterSpacing: '0.15em' }}>
              {busy ? '...' : plan.status === 'applied' ? '✓ ALREADY APPLIED' : plan.status === 'rejected' ? '✗ REJECTED' : plan.status === 'dry_run' ? '⚙ DRY RUN ONLY' : '✓ APPROVE & APPLY'}
            </button>
            <button
              onClick={onReject}
              disabled={busy || plan.status !== 'pending'}
              title={plan.status !== 'pending' ? `Cannot reject: plan is already "${plan.status}"` : 'Reject this repair plan'}
              style={{ flex: 1, backgroundColor: 'transparent', border: `1px solid ${plan.status === 'pending' ? '#ef4444' : '#2a3540'}`, color: plan.status === 'pending' ? '#ef4444' : '#4a5a6a', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, fontWeight: 700, padding: 10, cursor: plan.status !== 'pending' ? 'not-allowed' : 'pointer', letterSpacing: '0.15em', opacity: plan.status !== 'pending' ? 0.4 : 1 }}>
              ✗ REJECT
            </button>
          </div>
          {rejectInput && (
            <div style={{ display: 'flex', gap: 8 }}>
              <input value={rejectReason} onChange={e => setRejectReason(e.target.value)} placeholder="Rejection reason..." style={{ flex: 1, backgroundColor: '#161b22', border: '1px solid #ef4444', color: '#d0d8e4', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, padding: '8px 10px', outline: 'none' }} />
              <button onClick={onConfirmReject} disabled={busy} style={{ backgroundColor: '#ef4444', border: 'none', color: '#fff', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, padding: '8px 14px', cursor: 'pointer', letterSpacing: '0.1em' }}>CONFIRM</button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function LoadingState() {
  return <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', padding: 32, textAlign: 'center' }}>LOADING REPAIR PLANS...</div>;
}
function ErrorState({ msg, onRetry }: { msg: string; onRetry: () => void }) {
  return (
    <div style={{ backgroundColor: '#1a0a0a', border: '1px solid #ef4444', padding: 24, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#ef4444' }}>⚠ FAILED TO LOAD PLANS</div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a' }}>{msg}</div>
      <button onClick={onRetry} style={{ width: 100, backgroundColor: 'transparent', border: '1px solid #ef4444', color: '#ef4444', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, padding: '6px 14px', cursor: 'pointer' }}>RETRY</button>
    </div>
  );
}
