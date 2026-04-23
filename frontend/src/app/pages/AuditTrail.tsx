import React, { useState } from 'react';
import { AUDIT_EVENTS, AuditEvent } from '../data/mockData';

const EVENT_COLORS: Record<string, string> = {
  failure_detected: '#ef4444',
  plan_generated: '#f59e0b',
  patch_applied: '#00d4aa',
  human_approved: '#d0d8e4',
  rollback_executed: '#3b82f6',
};

const EVENT_LABELS: Record<string, string> = {
  failure_detected: 'FAILURE DETECTED',
  plan_generated: 'PLAN GENERATED',
  patch_applied: 'PATCH APPLIED',
  human_approved: 'HUMAN APPROVED',
  rollback_executed: 'ROLLBACK EXECUTED',
};

export function AuditTrail() {
  const [filterDag, setFilterDag] = useState('all');
  const [filterType, setFilterType] = useState('all');
  const [events, setEvents] = useState(AUDIT_EVENTS);

  const dags = Array.from(new Set(AUDIT_EVENTS.map(e => e.dag).filter(Boolean)));

  const filtered = events.filter(e => {
    if (filterDag !== 'all' && e.dag !== filterDag) return false;
    if (filterType !== 'all' && e.type !== filterType) return false;
    return true;
  });

  const handleExport = () => {
    const lines = [
      '# SH-AI Audit Report',
      `Generated: ${new Date().toISOString()}`,
      '',
      ...filtered.map(e =>
        `## ${e.timestamp}\n- **Event:** ${EVENT_LABELS[e.type]}\n- **Entity:** ${e.entityId}\n- **Description:** ${e.description}${e.commitHash ? `\n- **Commit:** \`${e.commitHash}\`` : ''}`
      ),
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'audit_report.md';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4', margin: 0 }}>
            AUDIT TRAIL
          </h1>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginTop: 4 }}>
            {filtered.length} EVENTS · IMMUTABLE LOG
          </div>
        </div>
        <button
          onClick={handleExport}
          style={{
            backgroundColor: 'transparent',
            border: '1px solid #2a3540',
            color: '#d0d8e4',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            padding: '8px 14px',
            cursor: 'pointer',
            letterSpacing: '0.15em',
          }}
        >
          ↓ EXPORT MARKDOWN REPORT
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <SelectFilter
          value={filterDag}
          onChange={setFilterDag}
          options={[{ v: 'all', l: 'ALL DAGS' }, ...dags.map(d => ({ v: d!, l: d! }))]}
        />
        <SelectFilter
          value={filterType}
          onChange={setFilterType}
          options={[
            { v: 'all', l: 'ALL EVENTS' },
            { v: 'failure_detected', l: 'FAILURE' },
            { v: 'plan_generated', l: 'PLAN' },
            { v: 'patch_applied', l: 'PATCH' },
            { v: 'human_approved', l: 'APPROVED' },
            { v: 'rollback_executed', l: 'ROLLBACK' },
          ]}
        />
      </div>

      {/* Timeline */}
      <div style={{ position: 'relative', paddingLeft: 32 }}>
        {filtered.map((event, i) => (
          <TimelineEvent
            key={event.id}
            event={event}
            isLast={i === filtered.length - 1}
          />
        ))}
      </div>
    </div>
  );
}

function TimelineEvent({ event, isLast }: { event: AuditEvent; isLast: boolean }) {
  const color = EVENT_COLORS[event.type];

  return (
    <div style={{ position: 'relative', paddingBottom: isLast ? 0 : 20, display: 'flex', gap: 0 }}>
      {/* Timeline line */}
      {!isLast && (
        <div style={{
          position: 'absolute',
          left: -22,
          top: 16,
          width: 1,
          height: 'calc(100% + 4px)',
          backgroundColor: '#1e2530',
        }} />
      )}

      {/* Dot */}
      <div style={{
        position: 'absolute',
        left: -28,
        top: 6,
        width: 10,
        height: 10,
        borderRadius: '50%',
        backgroundColor: color,
        border: `1px solid ${color}`,
        boxShadow: `0 0 6px ${color}60`,
        flexShrink: 0,
      }} />

      {/* Content */}
      <div
        style={{
          flex: 1,
          backgroundColor: '#111418',
          border: '1px solid #1e2530',
          padding: '10px 16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 16,
          transition: 'border-color 0.1s ease',
        }}
        onMouseEnter={e => (e.currentTarget.style.borderColor = '#2a3540')}
        onMouseLeave={e => (e.currentTarget.style.borderColor = '#1e2530')}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <span style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 8,
              color,
              border: `1px solid ${color}`,
              padding: '1px 6px',
              letterSpacing: '0.1em',
              backgroundColor: `${color}15`,
              whiteSpace: 'nowrap',
            }}>
              {EVENT_LABELS[event.type]}
            </span>
          </div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#d0d8e4', lineHeight: 1.5 }}>
            {event.description}
          </div>
          <div style={{ marginTop: 4 }}>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#00d4aa', cursor: 'pointer' }}>
              {event.entityId}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a' }}>
            {event.timestamp.replace('T', ' ').replace('Z', ' UTC')}
          </span>
          {event.commitHash && (
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#3b82f6' }}>
              {event.commitHash}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function SelectFilter({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: { v: string; l: string }[] }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      style={{
        backgroundColor: '#111418',
        border: '1px solid #1e2530',
        color: '#d0d8e4',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10,
        padding: '6px 10px',
        outline: 'none',
        cursor: 'pointer',
        letterSpacing: '0.05em',
      }}
    >
      {options.map(o => (
        <option key={o.v} value={o.v} style={{ backgroundColor: '#111418' }}>{o.l}</option>
      ))}
    </select>
  );
}
