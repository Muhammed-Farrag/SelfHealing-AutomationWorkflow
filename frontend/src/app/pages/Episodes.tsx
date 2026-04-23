import React, { useEffect, useState } from 'react';
import { fetchEpisodes, ApiEpisode } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { ConfidenceBar, ConfidenceGauge } from '../components/ConfidenceGauge';

const FAILURE_COLORS: Record<string, string> = {
  timeout: '#f59e0b',
  http_error: '#ef4444',
  missing_file: '#3b82f6',
  missing_column: '#8b5cf6',
  missing_db: '#f97316',
};

const OPERATOR_COLORS: Record<string, string> = {
  set_env: '#3b82f6',
  set_retry: '#f59e0b',
  set_timeout: '#f59e0b',
  replace_path: '#3b82f6',
  add_precheck: '#8b5cf6',
};

const PAGE_SIZE = 10;

function getActions(ep: ApiEpisode): any[] {
  const ra = (ep as any).repair_actions;
  if (Array.isArray(ra)) return ra;
  if (typeof ra === 'string' && ra.trim()) {
    try { return JSON.parse(ra); } catch { return []; }
  }
  return [];
}

export function Episodes() {
  const [episodes, setEpisodes] = useState<ApiEpisode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterClass, setFilterClass] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<ApiEpisode | null>(null);

  const load = () => {
    setLoading(true); setError(null);
    fetchEpisodes()
      .then(data => setEpisodes(data))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const fc = (ep: ApiEpisode) => ep.failure_class || (ep as any).failure_type || 'unknown';
  const conf = (ep: ApiEpisode) => (ep as any).confidence ?? ep.ml_confidence ?? 0;

  const filtered = episodes.filter(ep => {
    if (filterClass !== 'all' && fc(ep) !== filterClass) return false;
    if (filterStatus !== 'all' && (ep.status || 'unknown') !== filterStatus) return false;
    if (search && !ep.episode_id?.toLowerCase().includes(search.toLowerCase())
      && !ep.dag_id?.toLowerCase().includes(search.toLowerCase())
      && !ep.task_id?.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState msg={error} onRetry={load} />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4', margin: 0, letterSpacing: '0.02em' }}>
          EPISODES
        </h1>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginTop: 4 }}>
          {filtered.length} FAILURE EPISODES · LIVE DATA
        </div>
      </div>

      {/* Filter bar */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1); }}
          placeholder="Search episode, DAG, task..."
          style={{ flex: 1, minWidth: 200, background: '#0e1218', border: '1px solid #1e2530', color: '#d0d8e4', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, padding: '7px 12px', outline: 'none' }}
        />
        <Select value={filterClass} onChange={v => { setFilterClass(v); setPage(1); }}
          options={[{ v: 'all', l: 'ALL CLASSES' }, { v: 'timeout', l: 'TIMEOUT' }, { v: 'http_error', l: 'HTTP ERROR' }, { v: 'missing_file', l: 'MISSING FILE' }, { v: 'missing_column', l: 'MISSING COL' }, { v: 'missing_db', l: 'MISSING DB' }]}
        />
        <Select value={filterStatus} onChange={v => { setFilterStatus(v); setPage(1); }}
          options={[{ v: 'all', l: 'ALL STATUS' }, { v: 'applied', l: 'APPLIED' }, { v: 'pending', l: 'PENDING' }, { v: 'rejected', l: 'REJECTED' }, { v: 'dry_run', l: 'DRY RUN' }]}
        />
      </div>

      {/* Table */}
      <div style={{ border: '1px solid #1e2530', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: '#111418', borderBottom: '1px solid #1e2530' }}>
              {['EPISODE ID', 'DAG', 'TASK', 'CLASS', 'CONFIDENCE', 'ML/REGEX', 'STATUS', 'ACTIONS'].map(col => (
                <th key={col} style={{ padding: '10px 14px', textAlign: 'left', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.15em', fontWeight: 700, whiteSpace: 'nowrap' }}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.map(ep => (
              <EpisodeRow
                key={ep.episode_id}
                ep={ep}
                onClick={() => setSelected(ep)}
                isSelected={selected?.episode_id === ep.episode_id}
                fc={fc(ep)}
                conf={conf(ep)}
              />
            ))}
            {paged.length === 0 && (
              <tr>
                <td colSpan={8} style={{ padding: 32, textAlign: 'center', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a' }}>
                  NO EPISODES MATCH FILTER
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a' }}>
          {filtered.length > 0
            ? `Showing ${Math.min((page - 1) * PAGE_SIZE + 1, filtered.length)}–${Math.min(page * PAGE_SIZE, filtered.length)} of ${filtered.length}`
            : '0 results'}
        </span>
        <div style={{ display: 'flex', gap: 4 }}>
          {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => i + 1).map(p => (
            <button key={p} onClick={() => setPage(p)} style={{ width: 28, height: 28, backgroundColor: p === page ? '#00d4aa' : '#111418', border: `1px solid ${p === page ? '#00d4aa' : '#1e2530'}`, color: p === page ? '#0a0c0f' : '#d0d8e4', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, cursor: 'pointer' }}>{p}</button>
          ))}
        </div>
      </div>

      {/* Detail panel */}
      {selected && (
        <EpisodeDetailPanel
          ep={selected}
          fc={fc(selected)}
          conf={conf(selected)}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

/* ─── Table Row ─────────────────────────────────────────────────── */
function EpisodeRow({ ep, onClick, isSelected, fc, conf }: { ep: ApiEpisode; onClick: () => void; isSelected: boolean; fc: string; conf: number }) {
  const [hovered, setHovered] = useState(false);
  const color = FAILURE_COLORS[fc] || '#4a5a6a';
  const agree = (ep as any).classifiers_agree;

  return (
    <tr
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        borderBottom: '1px solid #1e2530',
        backgroundColor: isSelected ? 'rgba(0,212,170,0.04)' : hovered ? '#111418' : 'transparent',
        borderLeft: `2px solid ${isSelected ? '#00d4aa' : 'transparent'}`,
        cursor: 'pointer',
        transition: 'all 0.1s ease',
        height: 44,
      }}
    >
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#4a5a6a' }}>{ep.episode_id}</td>
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#d0d8e4', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ep.dag_id}</td>
      <td style={{ padding: '0 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#d0d8e4', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ep.task_id}</td>
      <td style={{ padding: '0 14px' }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color, border: `1px solid ${color}`, padding: '2px 7px', letterSpacing: '0.1em', backgroundColor: `${color}18` }}>
          {fc.replace('_', ' ').toUpperCase()}
        </span>
      </td>
      <td style={{ padding: '0 14px', width: 160 }}>
        <ConfidenceBar value={conf} />
      </td>
      <td style={{ padding: '0 14px', textAlign: 'center' }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: agree === true ? '#00d4aa' : agree === false ? '#f59e0b' : '#4a5a6a' }}>
          {agree === true ? '✓' : agree === false ? '~' : '—'}
        </span>
      </td>
      <td style={{ padding: '0 14px' }}>
        <StatusBadge type="status" value={ep.status || 'unknown'} />
      </td>
      <td style={{ padding: '0 14px' }}>
        <button
          onClick={e => { e.stopPropagation(); onClick(); }}
          style={{ background: 'transparent', border: '1px solid #2a3540', color: '#00d4aa', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, padding: '4px 10px', cursor: 'pointer', letterSpacing: '0.1em' }}
        >
          VIEW
        </button>
      </td>
    </tr>
  );
}

/* ─── Detail Panel ──────────────────────────────────────────────── */
function EpisodeDetailPanel({ ep, fc, conf, onClose }: { ep: ApiEpisode; fc: string; conf: number; onClose: () => void }) {
  const color = FAILURE_COLORS[fc] || '#4a5a6a';
  const actions = getActions(ep);
  const logLines = ((ep as any).log_excerpt || ep.log_excerpt || '').split('\n').filter(Boolean);
  const playbook: any[] = (ep as any).playbook_matches || [];
  const regexClass: string = (ep as any).regex_class || fc;
  const mlClass: string = (ep as any).ml_class || fc;
  const agree: boolean = (ep as any).classifiers_agree;
  const reasoning: string = (ep as any).reasoning || '';

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 40 }} />
      <div style={{
        position: 'fixed', top: 0, right: 0, width: 500, height: '100vh',
        backgroundColor: '#0e1218', borderLeft: '1px solid #1e2530',
        zIndex: 50, overflowY: 'auto', display: 'flex', flexDirection: 'column',
      }}>

        {/* Header */}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #1e2530', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginBottom: 4 }}>
              {ep.dag_id} / {ep.task_id}
            </div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 14, color: '#d0d8e4' }}>{ep.episode_id}</div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: '1px solid #1e2530', color: '#4a5a6a', fontSize: 16, cursor: 'pointer', width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>×</button>
        </div>

        <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 24 }}>

          {/* Confidence gauge + classifier info — matches design screenshot */}
          <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
            <div style={{ flexShrink: 0 }}>
              <ConfidenceGauge value={conf} size={90} />
            </div>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {/* Failure class badge */}
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color, border: `1px solid ${color}`, padding: '3px 8px', backgroundColor: `${color}18`, letterSpacing: '0.1em', alignSelf: 'flex-start' }}>
                {fc.replace('_', ' ').toUpperCase()}
              </span>

              {/* Regex classifier */}
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: '#00d4aa', fontSize: 9 }}>✓</span>
                <span style={{ color: '#4a5a6a' }}>Regex Classifier:</span>{' '}
                <span style={{ color: '#d0d8e4' }}>{regexClass}</span>
              </div>

              {/* ML classifier */}
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: '#00d4aa', fontSize: 9 }}>✓</span>
                <span style={{ color: '#4a5a6a' }}>ML Classifier:</span>{' '}
                <span style={{ color: '#00d4aa' }}>{mlClass}</span>
                <span style={{ color: '#4a5a6a' }}>({(conf * 100).toFixed(0)}%)</span>
              </div>

              {/* Agreement */}
              <div style={{
                fontFamily: "'JetBrains Mono', monospace", fontSize: 9,
                color: agree ? '#00d4aa' : '#f59e0b',
                letterSpacing: '0.1em', marginTop: 2,
              }}>
                {agree ? '✓ BOTH CLASSIFIERS AGREE' : '~ CLASSIFIERS DISAGREE'}
              </div>
            </div>
          </div>

          {/* Repair Status */}
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <StatusBadge type="status" value={ep.status || 'unknown'} />
            {(ep as any).requires_human_approval && (
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: '#f59e0b', border: '1px solid #f59e0b', padding: '2px 8px' }}>
                ⚠ HUMAN REQUIRED
              </span>
            )}
            {(ep as any).plan_id && (
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a' }}>
                {(ep as any).plan_id}
              </span>
            )}
          </div>

          {/* AI Reasoning */}
          {reasoning && (
            <div>
              <SectionLabel>AI REASONING</SectionLabel>
              <div style={{ marginTop: 8, backgroundColor: 'rgba(139,92,246,0.06)', borderLeft: '2px solid #8b5cf6', padding: '10px 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', lineHeight: 1.7 }}>
                {reasoning}
              </div>
            </div>
          )}

          {/* Drain template */}
          {(ep as any).template && (
            <div>
              <SectionLabel>DRAIN TEMPLATE</SectionLabel>
              <div style={{ marginTop: 8, backgroundColor: '#111418', border: '1px solid #1e2530', padding: '10px 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#00d4aa', lineHeight: 1.6, wordBreak: 'break-all' }}>
                {(ep as any).template}
              </div>
            </div>
          )}

          {/* Log excerpt */}
          {logLines.length > 0 && (
            <div>
              <SectionLabel>LOG EXCERPT</SectionLabel>
              <div style={{ marginTop: 8, backgroundColor: '#080b0e', border: '1px solid #1e2530', padding: '12px 14px', maxHeight: 200, overflowY: 'auto' }}>
                {logLines.map((line, i) => {
                  let lc = '#4a5a6a';
                  if (/CRITICAL|FATAL/.test(line)) lc = '#ef4444';
                  else if (/ERROR/.test(line)) lc = '#f59e0b';
                  else if (/WARN/.test(line)) lc = '#f59e0b';
                  else if (/INFO/.test(line)) lc = '#d0d8e4';
                  return (
                    <div key={i} style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, lineHeight: 1.7, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: lc }}>
                      {line}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Repair actions */}
          {actions.length > 0 && (
            <div>
              <SectionLabel>REPAIR ACTIONS ({actions.length})</SectionLabel>
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {actions.map((action: any, i: number) => {
                  const op = action.operator || action.op || 'unknown';
                  const clr = OPERATOR_COLORS[op] || '#4a5a6a';
                  return (
                    <div key={i} style={{ backgroundColor: '#111418', border: '1px solid #1e2530', padding: '8px 12px', display: 'flex', gap: 10, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: clr, border: `1px solid ${clr}`, padding: '2px 6px', letterSpacing: '0.1em', backgroundColor: `${clr}15`, flexShrink: 0 }}>
                        {op.toUpperCase()}
                      </span>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', flexShrink: 0 }}>
                        {action.param || action.key || ''}
                      </span>
                      {(action.value || action.new_value || action.newValue) && (
                        <>
                          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a' }}>=</span>
                          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#00d4aa' }}>
                            {action.value ?? action.new_value ?? action.newValue}
                          </span>
                        </>
                      )}
                      {action.justification && (
                        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', fontStyle: 'italic', flex: 1, minWidth: 160 }}>
                          — {action.justification}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Playbook matches */}
          {playbook.length > 0 && (
            <div>
              <SectionLabel>TOP PLAYBOOK MATCHES (FAISS)</SectionLabel>
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {playbook.slice(0, 5).map((match: any, i: number) => {
                  const score = match.score ?? match.similarity ?? 1 - (i * 0.08);
                  const pct = Math.round((score > 1 ? 1 : score) * 100);
                  const text = match.content || match.text || match.description || JSON.stringify(match);
                  return (
                    <div key={i} style={{ backgroundColor: '#111418', border: '1px solid #1e2530', padding: '8px 12px', display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#00d4aa', flexShrink: 0, minWidth: 36 }}>{pct}%</span>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', lineHeight: 1.5 }}>{text}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

/* ─── Shared helpers ────────────────────────────────────────────── */
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em' }}>
      {children}
    </div>
  );
}

function Select({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: { v: string; l: string }[] }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)} style={{ backgroundColor: '#111418', border: '1px solid #1e2530', color: '#d0d8e4', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, padding: '7px 10px', outline: 'none', cursor: 'pointer' }}>
      {options.map(o => <option key={o.v} value={o.v} style={{ backgroundColor: '#111418' }}>{o.l}</option>)}
    </select>
  );
}

function LoadingState() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {[1, 2, 3, 4, 5].map(i => (
        <div key={i} style={{ height: 44, backgroundColor: '#111418', border: '1px solid #1e2530', opacity: 0.5 + i * 0.1 }} />
      ))}
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', textAlign: 'center', marginTop: 8 }}>
        LOADING EPISODES...
      </div>
    </div>
  );
}

function ErrorState({ msg, onRetry }: { msg: string; onRetry: () => void }) {
  return (
    <div style={{ backgroundColor: '#1a0a0a', border: '1px solid #ef4444', padding: 24, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#ef4444' }}>⚠ FAILED TO LOAD EPISODES</div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a' }}>{msg}</div>
      <button onClick={onRetry} style={{ width: 100, backgroundColor: 'transparent', border: '1px solid #ef4444', color: '#ef4444', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, padding: '6px 14px', cursor: 'pointer' }}>RETRY</button>
    </div>
  );
}
