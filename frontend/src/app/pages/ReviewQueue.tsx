import React, { useState } from 'react';
import { REPAIR_PLANS, RepairPlan } from '../data/mockData';
import { StatusBadge } from '../components/StatusBadge';
import { ConfidenceBar } from '../components/ConfidenceGauge';

const pendingPlans = REPAIR_PLANS.filter(p => p.requiresHuman && p.status === 'pending');

export function ReviewQueue() {
  const [plans, setPlans] = useState<RepairPlan[]>(pendingPlans);
  const [selected, setSelected] = useState<string[]>([]);
  const [showConfirmModal, setShowConfirmModal] = useState<'approve_all' | 'reject_all' | null>(null);
  const [toast, setToast] = useState<{ msg: string; undoId?: string } | null>(null);

  const showToast = (msg: string, undoId?: string) => {
    setToast({ msg, undoId });
    setTimeout(() => setToast(null), 4000);
  };

  const toggleSelect = (id: string) => {
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  const selectAll = () => {
    setSelected(plans.length === selected.length ? [] : plans.map(p => p.id));
  };

  const handleApprove = (id: string) => {
    setPlans(prev => prev.filter(p => p.id !== id));
    showToast(`APPROVED: ${id}`, id);
  };

  const handleReject = (id: string) => {
    setPlans(prev => prev.filter(p => p.id !== id));
    showToast(`REJECTED: ${id}`);
  };

  const handleApproveAll = () => {
    const ids = selected.length > 0 ? selected : plans.map(p => p.id);
    setPlans(prev => prev.filter(p => !ids.includes(p.id)));
    setSelected([]);
    setShowConfirmModal(null);
    showToast(`APPROVED ${ids.length} plans`);
  };

  const handleRejectAll = () => {
    const ids = selected.length > 0 ? selected : plans.map(p => p.id);
    setPlans(prev => prev.filter(p => !ids.includes(p.id)));
    setSelected([]);
    setShowConfirmModal(null);
    showToast(`REJECTED ${ids.length} plans`);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4', margin: 0 }}>
          REVIEW QUEUE
        </h1>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginTop: 4 }}>
          PLANS REQUIRING HUMAN APPROVAL
        </div>
      </div>

      {plans.length === 0 ? (
        /* Empty state */
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 320,
          gap: 16,
        }}>
          <div style={{ fontSize: 48, color: '#00d4aa' }}>✓</div>
          <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4' }}>
            NO PENDING REVIEWS
          </div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', textAlign: 'center' }}>
            All repair plans have been reviewed.<br />New plans requiring human approval will appear here.
          </div>
        </div>
      ) : (
        <>
          {/* Bulk action bar */}
          <div style={{
            backgroundColor: '#161b22',
            border: '1px solid #1e2530',
            padding: '10px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}>
            <input
              type="checkbox"
              checked={selected.length === plans.length && plans.length > 0}
              onChange={selectAll}
              style={{ width: 14, height: 14, accentColor: '#00d4aa', cursor: 'pointer' }}
            />
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a' }}>
              {selected.length > 0 ? `${selected.length} selected` : 'Select all'}
            </span>
            {(selected.length > 0 || plans.length > 0) && (
              <>
                <span style={{ width: 1, height: 16, backgroundColor: '#1e2530' }} />
                <button
                  onClick={() => setShowConfirmModal('approve_all')}
                  style={{
                    backgroundColor: 'rgba(0,212,170,0.1)',
                    border: '1px solid #00d4aa',
                    color: '#00d4aa',
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 9,
                    padding: '4px 12px',
                    cursor: 'pointer',
                    letterSpacing: '0.1em',
                  }}
                >
                  APPROVE {selected.length > 0 ? `(${selected.length})` : 'ALL'}
                </button>
                <button
                  onClick={() => setShowConfirmModal('reject_all')}
                  style={{
                    backgroundColor: 'transparent',
                    border: '1px solid #ef4444',
                    color: '#ef4444',
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 9,
                    padding: '4px 12px',
                    cursor: 'pointer',
                    letterSpacing: '0.1em',
                  }}
                >
                  REJECT {selected.length > 0 ? `(${selected.length})` : 'ALL'}
                </button>
              </>
            )}
          </div>

          {/* Plan cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {plans.map(plan => (
              <ReviewPlanCard
                key={plan.id}
                plan={plan}
                isSelected={selected.includes(plan.id)}
                onToggle={() => toggleSelect(plan.id)}
                onApprove={() => handleApprove(plan.id)}
                onReject={() => handleReject(plan.id)}
              />
            ))}
          </div>
        </>
      )}

      {/* Confirm modal */}
      {showConfirmModal && (
        <>
          <div onClick={() => setShowConfirmModal(null)} style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.7)', zIndex: 40 }} />
          <div style={{
            position: 'fixed',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            backgroundColor: '#161b22',
            border: '1px solid #1e2530',
            padding: 28,
            zIndex: 50,
            width: 420,
          }}>
            <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 16, color: showConfirmModal === 'approve_all' ? '#00d4aa' : '#ef4444', marginBottom: 12 }}>
              CONFIRM {showConfirmModal === 'approve_all' ? 'BULK APPROVE' : 'BULK REJECT'}
            </div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', lineHeight: 1.6, marginBottom: 20 }}>
              {showConfirmModal === 'approve_all'
                ? `You are about to approve ${selected.length || plans.length} repair plans. This will apply patches to production DAG files.`
                : `You are about to reject ${selected.length || plans.length} repair plans. This action cannot be undone.`
              }
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={showConfirmModal === 'approve_all' ? handleApproveAll : handleRejectAll}
                style={{
                  flex: 1,
                  backgroundColor: showConfirmModal === 'approve_all' ? '#00d4aa' : '#ef4444',
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
                CONFIRM
              </button>
              <button
                onClick={() => setShowConfirmModal(null)}
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
          borderLeft: '3px solid #00d4aa',
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
          <span style={{ color: '#00d4aa' }}>✓</span>
          {toast.msg}
          <button onClick={() => setToast(null)} style={{ background: 'none', border: 'none', color: '#4a5a6a', cursor: 'pointer', fontSize: 14 }}>×</button>
        </div>
      )}
    </div>
  );
}

function ReviewPlanCard({ plan, isSelected, onToggle, onApprove, onReject }: {
  plan: RepairPlan;
  isSelected: boolean;
  onToggle: () => void;
  onApprove: () => void;
  onReject: () => void;
}) {
  return (
    <div style={{
      backgroundColor: '#111418',
      border: `1px solid ${isSelected ? '#00d4aa' : '#1e2530'}`,
      display: 'flex',
      gap: 0,
    }}>
      {/* Checkbox column */}
      <div style={{ padding: '16px 16px', display: 'flex', alignItems: 'flex-start', borderRight: '1px solid #1e2530' }}>
        <input
          type="checkbox"
          checked={isSelected}
          onChange={onToggle}
          style={{ width: 14, height: 14, accentColor: '#00d4aa', cursor: 'pointer', marginTop: 2 }}
        />
      </div>

      {/* Content */}
      <div style={{ flex: 1, padding: '16px 20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
          <div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: '#d0d8e4', marginBottom: 6 }}>{plan.id}</div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <StatusBadge type="failure_class" value={plan.failureClass} />
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a' }}>ep: {plan.episodeId}</span>
            </div>
          </div>
          <div>
            <ConfidenceBar value={plan.confidence} />
          </div>
        </div>

        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', lineHeight: 1.6, marginBottom: 12, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
          {plan.reasoning}
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={onApprove}
            style={{
              backgroundColor: '#00d4aa',
              border: 'none',
              color: '#0a0c0f',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 10,
              fontWeight: 700,
              padding: '7px 20px',
              cursor: 'pointer',
              letterSpacing: '0.15em',
            }}
          >
            ✓ APPROVE
          </button>
          <button
            onClick={onReject}
            style={{
              backgroundColor: 'transparent',
              border: '1px solid #ef4444',
              color: '#ef4444',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 10,
              fontWeight: 700,
              padding: '7px 20px',
              cursor: 'pointer',
              letterSpacing: '0.15em',
            }}
          >
            ✗ REJECT
          </button>
        </div>
      </div>
    </div>
  );
}
