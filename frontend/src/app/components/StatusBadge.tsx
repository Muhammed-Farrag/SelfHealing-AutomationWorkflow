import React from 'react';
import { FailureClass, PlanStatus, EpisodeStatus, FAILURE_CLASS_COLORS } from '../data/mockData';

interface StatusBadgeProps {
  type: 'status' | 'failure_class';
  value: string;
  size?: 'sm' | 'md';
}

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  pending: { color: '#f59e0b', label: 'PENDING' },
  applied: { color: '#10b981', label: 'APPLIED' },
  rejected: { color: '#ef4444', label: 'REJECTED' },
  dry_run: { color: '#3b82f6', label: 'DRY RUN' },
  in_progress: { color: '#f59e0b', label: 'IN PROGRESS' },
};

const FAILURE_CLASS_LABELS: Record<string, string> = {
  timeout: 'TIMEOUT',
  http_error: 'HTTP ERROR',
  missing_file: 'MISSING FILE',
  missing_column: 'MISSING COL',
  missing_db: 'MISSING DB',
};

export function StatusBadge({ type, value, size = 'sm' }: StatusBadgeProps) {
  // Guard: real API data may return null/undefined for optional fields
  const safeValue = value ?? '';

  let color: string;
  let label: string;

  if (type === 'status') {
    const cfg = STATUS_CONFIG[safeValue] || { color: '#4a5a6a', label: safeValue ? safeValue.toUpperCase() : '—' };
    color = cfg.color;
    label = cfg.label;
  } else {
    color = FAILURE_CLASS_COLORS[safeValue as FailureClass] || '#4a5a6a';
    label = FAILURE_CLASS_LABELS[safeValue] || (safeValue ? safeValue.toUpperCase() : '—');
  }

  const padding = size === 'sm' ? '2px 8px' : '4px 12px';
  const fontSize = size === 'sm' ? '8px' : '10px';

  return (
    <span
      style={{
        display: 'inline-block',
        padding,
        fontSize,
        letterSpacing: '0.15em',
        fontFamily: "'JetBrains Mono', monospace",
        fontWeight: 700,
        color,
        border: `1px solid ${color}`,
        borderRadius: '2px',
        backgroundColor: `${color}18`,
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </span>
  );
}
