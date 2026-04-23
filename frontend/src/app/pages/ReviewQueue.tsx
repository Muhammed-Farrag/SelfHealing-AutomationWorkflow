import React, { useEffect, useState } from 'react';
import { fetchReviewQueue, approvePlan, rejectPlan, ApiPlan } from '../services/api';
import { ConfidenceBar } from '../components/ConfidenceGauge';

const FAILURE_COLORS: Record<string, string> = {
  timeout: '#f59e0b', http_error: '#ef4444', missing_file: '#3b82f6',
  missing_column: '#8b5cf6', missing_db: '#f97316',
};

export function ReviewQueue() {
  const [plans, setPlans] = useState<ApiPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 4000); };

  const load = () => {
    setLoading(true); setError(null);
    fetchReviewQueue()
      .then(r => setPlans(r.queue))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const toggleSelect = (id: string) =>
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);

  const handleApprove = async (id: string) => {
    setBusy(true);
    try {
      await approvePlan(id, 'ui_user');
      showToast(`✓ APPROVED: ${id}`);
      load();
    } catch (e: any) { showToast(`⚠ ERROR: ${e.message}`); }
    finally { setBusy(false); }
  };

  const handleReject = async (id: string) => {
    setBusy(true);
    try {
      await rejectPlan(id, 'ui_user', 'Rejected via Review Queue UI');
      showToast(`✗ REJECTED: ${id}`);
      load();
    } catch (e: any) { showToast(`⚠ ERROR: ${e.message}`); }
    finally { setBusy(false); }
  };

  if (loading) return <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', padding: 32, textAlign: 'center' }}>LOADING REVIEW QUEUE...</div>;
  if (error) return (
    <div style={{ backgroundColor: '#1a0a0a', border: '1px solid #ef4444', padding: 24 }}>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#ef4444', marginBottom: 8 }}>⚠ FAILED TO LOAD REVIEW QUEUE</div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', marginBottom: 12 }}>{error}</div>
      <button onClick={load} style={{ backgroundColor: 'transparent', border: '1px solid #ef4444', color: '#ef4444', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, padding: '6px 14px', cursor: 'pointer' }}>RETRY</button>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4', margin: 0 }}>REVIEW QUEUE</h1>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginTop: 4 }}>
          {plans.length} PLANS REQUIRING HUMAN APPROVAL · LIVE DATA
        </div>
      </div>

      {plans.length === 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 320, gap: 16 }}>
          <div style={{ fontSize: 48, color: '#00d4aa' }}>✓</div>
          <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4' }}>NO PENDING REVIEWS</div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', textAlign: 'center' }}>All repair plans have been reviewed.</div>
        </div>
      ) : (
        <>
          {/* Bulk action bar */}
          <div style={{ backgroundColor: '#161b22', border: '1px solid #1e2530', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
            <input type="checkbox" checked={selected.length === plans.length && plans.length > 0} onChange={() => setSelected(selected.length === plans.length ? [] : plans.map(p => p.plan_id))} style={{ width: 14, height: 14, accentColor: '#00d4aa', cursor: 'pointer' }} />
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a' }}>{selected.length > 0 ? `${selected.length} selected` : 'Select all'}</span>
          </div>

          {/* Plan cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {plans.map(plan => (
              <ReviewPlanCard key={plan.plan_id} plan={plan} isSelected={selected.includes(plan.plan_id)} onToggle={() => toggleSelect(plan.plan_id)} onApprove={() => handleApprove(plan.plan_id)} onReject={() => handleReject(plan.plan_id)} busy={busy} />
            ))}
          </div>
        </>
      )}

      {toast && (
        <div style={{ position: 'fixed', bottom: 24, right: 24, backgroundColor: '#111418', border: '1px solid #1e2530', borderLeft: '3px solid #00d4aa', padding: '12px 20px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#d0d8e4', zIndex: 9999, display: 'flex', alignItems: 'center', gap: 16, animation: 'fadeIn 0.2s ease' }}>
          <span style={{ color: '#00d4aa' }}>✓</span>{toast}
          <button onClick={() => setToast(null)} style={{ background: 'none', border: 'none', color: '#4a5a6a', cursor: 'pointer', fontSize: 14 }}>×</button>
        </div>
      )}
    </div>
  );
}

function ReviewPlanCard({ plan, isSelected, onToggle, onApprove, onReject, busy }: {
  plan: ApiPlan; isSelected: boolean; onToggle: () => void; onApprove: () => void; onReject: () => void; busy: boolean;
}) {
  const color = FAILURE_COLORS[plan.failure_class] || '#4a5a6a';
  return (
    <div style={{ backgroundColor: '#111418', border: `1px solid ${isSelected ? '#00d4aa' : '#1e2530'}`, display: 'flex', gap: 0 }}>
      <div style={{ padding: '16px 16px', display: 'flex', alignItems: 'flex-start', borderRight: '1px solid #1e2530' }}>
        <input type="checkbox" checked={isSelected} onChange={onToggle} style={{ width: 14, height: 14, accentColor: '#00d4aa', cursor: 'pointer', marginTop: 2 }} />
      </div>
      <div style={{ flex: 1, padding: '16px 20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
          <div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: '#d0d8e4', marginBottom: 6 }}>{plan.plan_id}</div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color, border: `1px solid ${color}`, padding: '2px 7px', backgroundColor: `${color}15` }}>{plan.failure_class?.toUpperCase()}</span>
              {plan.episode_id && <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a' }}>ep: {plan.episode_id}</span>}
            </div>
          </div>
          <ConfidenceBar value={plan.confidence} />
        </div>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', lineHeight: 1.6, marginBottom: 12, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{plan.reasoning}</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={onApprove} disabled={busy} style={{ backgroundColor: '#00d4aa', border: 'none', color: '#0a0c0f', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, fontWeight: 700, padding: '7px 20px', cursor: busy ? 'not-allowed' : 'pointer', letterSpacing: '0.15em', opacity: busy ? 0.6 : 1 }}>
            {busy ? '...' : '✓ APPROVE'}
          </button>
          <button onClick={onReject} disabled={busy} style={{ backgroundColor: 'transparent', border: '1px solid #ef4444', color: '#ef4444', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, fontWeight: 700, padding: '7px 20px', cursor: busy ? 'not-allowed' : 'pointer', letterSpacing: '0.15em', opacity: busy ? 0.6 : 1 }}>
            ✗ REJECT
          </button>
        </div>
      </div>
    </div>
  );
}
