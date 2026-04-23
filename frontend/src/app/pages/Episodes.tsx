import React, { useState } from 'react';
import { EPISODES, Episode, FAILURE_CLASS_COLORS, FailureClass } from '../data/mockData';
import { StatusBadge } from '../components/StatusBadge';
import { ConfidenceBar } from '../components/ConfidenceGauge';
import { ConfidenceGauge } from '../components/ConfidenceGauge';

const PAGE_SIZE = 8;

export function Episodes() {
  const [filterClass, setFilterClass] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterDag, setFilterDag] = useState('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [selectedEpisode, setSelectedEpisode] = useState<Episode | null>(null);
  const [sortCol, setSortCol] = useState<string>('timestamp');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const dags = Array.from(new Set(EPISODES.map(e => e.dag)));

  const filtered = EPISODES.filter(e => {
    if (filterClass !== 'all' && e.failureClass !== filterClass) return false;
    if (filterStatus !== 'all' && e.status !== filterStatus) return false;
    if (filterDag !== 'all' && e.dag !== filterDag) return false;
    if (search && !e.id.includes(search) && !e.dag.includes(search) && !e.task.includes(search)) return false;
    return true;
  });

  const sorted = [...filtered].sort((a, b) => {
    let va: any = a[sortCol as keyof Episode];
    let vb: any = b[sortCol as keyof Episode];
    if (sortDir === 'asc') return va > vb ? 1 : -1;
    return va < vb ? 1 : -1;
  });

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const paged = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const handleSort = (col: string) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortCol(col); setSortDir('desc'); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4', margin: 0 }}>
          EPISODES
        </h1>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginTop: 4 }}>
          {filtered.length} FAILURE EPISODES · LAST 24H
        </div>
      </div>

      {/* Filter bar */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1); }}
          placeholder="Search episode, DAG, task..."
          style={{
            flex: 1,
            minWidth: 180,
            background: '#111418',
            border: '1px solid #1e2530',
            color: '#d0d8e4',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
            padding: '6px 10px',
            outline: 'none',
          }}
        />
        <Select value={filterClass} onChange={v => { setFilterClass(v); setPage(1); }}
          options={[{ v: 'all', l: 'ALL CLASSES' }, { v: 'timeout', l: 'TIMEOUT' }, { v: 'http_error', l: 'HTTP ERROR' }, { v: 'missing_file', l: 'MISSING FILE' }, { v: 'missing_column', l: 'MISSING COL' }, { v: 'missing_db', l: 'MISSING DB' }]}
        />
        <Select value={filterStatus} onChange={v => { setFilterStatus(v); setPage(1); }}
          options={[{ v: 'all', l: 'ALL STATUS' }, { v: 'pending', l: 'PENDING' }, { v: 'applied', l: 'APPLIED' }, { v: 'rejected', l: 'REJECTED' }, { v: 'dry_run', l: 'DRY RUN' }]}
        />
        <Select value={filterDag} onChange={v => { setFilterDag(v); setPage(1); }}
          options={[{ v: 'all', l: 'ALL DAGS' }, ...dags.map(d => ({ v: d, l: d }))]}
        />
      </div>

      {/* Table */}
      <div style={{ border: '1px solid #1e2530', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: '#161b22', borderBottom: '1px solid #1e2530' }}>
              {[
                { key: 'id', label: 'EPISODE ID', w: 100 },
                { key: 'dag', label: 'DAG', w: 160 },
                { key: 'task', label: 'TASK', w: 160 },
                { key: 'failureClass', label: 'CLASS', w: 120 },
                { key: 'confidence', label: 'CONFIDENCE', w: 140 },
                { key: 'mlAgrees', label: 'ML∩REGEX', w: 90 },
                { key: 'status', label: 'STATUS', w: 100 },
                { key: 'actions', label: 'ACTIONS', w: 80 },
              ].map(col => (
                <th
                  key={col.key}
                  onClick={() => col.key !== 'actions' && handleSort(col.key)}
                  style={{
                    padding: '10px 14px',
                    textAlign: 'left',
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 9,
                    color: '#4a5a6a',
                    letterSpacing: '0.2em',
                    fontWeight: 700,
                    cursor: col.key !== 'actions' ? 'pointer' : 'default',
                    userSelect: 'none',
                    whiteSpace: 'nowrap',
                    width: col.w,
                  }}
                >
                  {col.label}
                  {sortCol === col.key && (
                    <span style={{ marginLeft: 4, color: '#00d4aa' }}>
                      {sortDir === 'asc' ? '↑' : '↓'}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.map(ep => (
              <EpisodeRow
                key={ep.id}
                episode={ep}
                onSelect={() => setSelectedEpisode(ep)}
                isSelected={selectedEpisode?.id === ep.id}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a' }}>
          Showing {Math.min((page - 1) * PAGE_SIZE + 1, filtered.length)}–{Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length}
        </span>
        <div style={{ display: 'flex', gap: 4 }}>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
            <button
              key={p}
              onClick={() => setPage(p)}
              style={{
                width: 28,
                height: 28,
                backgroundColor: p === page ? '#00d4aa' : '#111418',
                border: `1px solid ${p === page ? '#00d4aa' : '#1e2530'}`,
                color: p === page ? '#0a0c0f' : '#d0d8e4',
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 10,
                cursor: 'pointer',
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Slide-in detail panel */}
      {selectedEpisode && (
        <EpisodeDetailPanel
          episode={selectedEpisode}
          onClose={() => setSelectedEpisode(null)}
        />
      )}
    </div>
  );
}

function EpisodeRow({ episode: ep, onSelect, isSelected }: {
  episode: Episode;
  onSelect: () => void;
  isSelected: boolean;
}) {
  const [hovered, setHovered] = useState(false);
  return (
    <tr
      onClick={onSelect}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        borderBottom: '1px solid #1e2530',
        backgroundColor: isSelected ? 'rgba(0,212,170,0.04)' : hovered ? '#161b22' : 'transparent',
        borderLeft: `2px solid ${isSelected ? '#00d4aa' : hovered ? '#2a3540' : 'transparent'}`,
        cursor: 'pointer',
        transition: 'all 0.1s ease',
        height: 40,
      }}
    >
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#4a5a6a' }}>
        {ep.id}
      </td>
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#d0d8e4', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {ep.dag}
      </td>
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#d0d8e4', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {ep.task}
      </td>
      <td style={{ padding: '0 14px' }}>
        <StatusBadge type="failure_class" value={ep.failureClass} />
      </td>
      <td style={{ padding: '0 14px' }}>
        <ConfidenceBar value={ep.confidence} />
      </td>
      <td style={{ padding: '0 14px', textAlign: 'center' }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: ep.mlAgrees && ep.regexAgrees ? '#10b981' : ep.mlAgrees || ep.regexAgrees ? '#f59e0b' : '#ef4444' }}>
          {ep.mlAgrees && ep.regexAgrees ? '✓' : ep.mlAgrees || ep.regexAgrees ? '~' : '✗'}
        </span>
      </td>
      <td style={{ padding: '0 14px' }}>
        <StatusBadge type="status" value={ep.status} />
      </td>
      <td style={{ padding: '0 14px' }}>
        <button
          onClick={e => { e.stopPropagation(); onSelect(); }}
          style={{
            background: 'transparent',
            border: '1px solid #2a3540',
            color: '#00d4aa',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            padding: '3px 8px',
            cursor: 'pointer',
            letterSpacing: '0.1em',
          }}
        >
          VIEW
        </button>
      </td>
    </tr>
  );
}

function EpisodeDetailPanel({ episode: ep, onClose }: { episode: Episode; onClose: () => void }) {
  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(0,0,0,0.4)',
          zIndex: 40,
        }}
      />
      {/* Panel */}
      <div
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          width: 480,
          height: '100vh',
          backgroundColor: '#111418',
          borderLeft: '1px solid #1e2530',
          zIndex: 50,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          animation: 'slideIn 0.2s ease-out',
        }}
      >
        {/* Header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #1e2530', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, color: '#00d4aa' }}>{ep.id}</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', marginTop: 2 }}>{ep.dag} / {ep.task}</div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: '1px solid #1e2530', color: '#4a5a6a', fontSize: 16, cursor: 'pointer', width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>×</button>
        </div>

        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Classification result */}
          <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
            <ConfidenceGauge value={ep.confidence} size={80} />
            <div style={{ flex: 1 }}>
              <StatusBadge type="failure_class" value={ep.failureClass} size="md" />
              <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <ClassifierBadge label="Regex Classifier" value={ep.regexAgrees} class_={ep.failureClass} />
                <ClassifierBadge label="ML Classifier" value={ep.mlAgrees} class_={ep.failureClass} score={ep.confidence} />
                {ep.mlAgrees && ep.regexAgrees && (
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#00d4aa', letterSpacing: '0.15em', marginTop: 4 }}>
                    ✓ BOTH CLASSIFIERS AGREE
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Drain template */}
          <div>
            <SectionLabel>DRAIN TEMPLATE</SectionLabel>
            <div style={{ backgroundColor: '#161b22', borderLeft: '2px solid #8b5cf6', padding: '10px 14px', marginTop: 8 }}>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', lineHeight: 1.6 }}>
                {ep.drainTemplate.split('<*>').map((part, i, arr) => (
                  <React.Fragment key={i}>
                    <span style={{ color: '#d0d8e4' }}>{part}</span>
                    {i < arr.length - 1 && <span style={{ color: '#8b5cf6', backgroundColor: 'rgba(139,92,246,0.12)', padding: '0 3px' }}>&lt;*&gt;</span>}
                  </React.Fragment>
                ))}
              </span>
            </div>
          </div>

          {/* Log viewer */}
          <div>
            <SectionLabel>LOG EXCERPT</SectionLabel>
            <div style={{ backgroundColor: '#080b0e', border: '1px solid #1e2530', padding: '12px 14px', marginTop: 8, overflowX: 'auto' }}>
              {ep.logExcerpt.split('\n').map((line, i) => (
                <div key={i} style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, lineHeight: 1.7, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  <HighlightedLog line={line} />
                </div>
              ))}
            </div>
          </div>

          {/* FAISS matches */}
          <div>
            <SectionLabel>TOP PLAYBOOK MATCHES (FAISS)</SectionLabel>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
              {ep.faissMatches.map((m, i) => (
                <div key={i} style={{ backgroundColor: '#161b22', border: '1px solid #1e2530', padding: '8px 12px', display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#8b5cf6', flexShrink: 0, marginTop: 2 }}>
                    {(m.score * 100).toFixed(0)}%
                  </span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', lineHeight: 1.5 }}>
                    {m.text}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function HighlightedLog({ line }: { line: string }) {
  let color = '#4a5a6a';
  if (line.includes('ERROR') || line.includes('CRITICAL')) color = '#ef4444';
  else if (line.includes('WARN')) color = '#f59e0b';
  else if (line.includes('INFO')) color = '#d0d8e4';

  return <span style={{ color }}>{line}</span>;
}

function ClassifierBadge({ label, value, class_, score }: { label: string; value: boolean; class_: string; score?: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: value ? '#10b981' : '#ef4444' }}>
        {value ? '✓' : '✗'}
      </span>
      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a' }}>{label}:</span>
      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: FAILURE_CLASS_COLORS[class_ as FailureClass] }}>
        {class_}
      </span>
      {score !== undefined && (
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a' }}>
          ({score.toFixed(2)})
        </span>
      )}
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em' }}>
      {children}
    </div>
  );
}

function Select({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: { v: string; l: string }[] }) {
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
