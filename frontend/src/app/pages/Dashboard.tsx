import React from 'react';
import {
  KPI_DATA,
  FAILURE_CLASS_DISTRIBUTION,
  ACTIVITY_FEED,
} from '../data/mockData';

const TOTAL = FAILURE_CLASS_DISTRIBUTION.reduce((s, d) => s + d.count, 0);

const SAFETY_THRESHOLDS = [
  { label: 'Confidence Threshold', marker: 0.50, current: 0.67, suffix: '' },
  { label: 'Auto-patch Rate', marker: 0.80, current: 0.783, suffix: '%', displayMultiplier: 100 },
  { label: 'Human Approval Required', marker: 0.50, current: 0.33, suffix: '' },
];

export function Dashboard() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Page title */}
      <div>
        <h1
          style={{
            fontFamily: "'Syne', sans-serif",
            fontWeight: 800,
            fontSize: 20,
            color: '#d0d8e4',
            margin: 0,
            letterSpacing: '0.02em',
          }}
        >
          MISSION CONTROL
        </h1>
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            color: '#4a5a6a',
            letterSpacing: '0.2em',
            marginTop: 4,
          }}
        >
          REAL-TIME PIPELINE HEALTH · {new Date().toISOString().replace('T', ' ').slice(0, 19)} UTC
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        <KpiCard
          value="60"
          label="TOTAL EPISODES"
          sub="last 24h"
        />
        <KpiCard
          value="78.3%"
          label="AUTO-PATCH RATE"
          sub="↑ 3.1% from yesterday"
          subColor="#00d4aa"
        />
        <KpiCard
          value="4.2 min"
          label="MTTR"
          sub="mean time to repair"
        />
        <KpiCard
          value={String(KPI_DATA.pendingReview)}
          label="PENDING REVIEW"
          sub={KPI_DATA.pendingReview > 0 ? '⚠ requires attention' : 'queue clear'}
          subColor={KPI_DATA.pendingReview > 0 ? '#f59e0b' : '#10b981'}
          alert={KPI_DATA.pendingReview > 0}
        />
      </div>

      {/* Middle section */}
      <div style={{ display: 'grid', gridTemplateColumns: '60fr 40fr', gap: 16 }}>
        {/* Failure Class Distribution */}
        <Panel title="FAILURE CLASS DISTRIBUTION">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '4px 0' }}>
            {FAILURE_CLASS_DISTRIBUTION.map(item => {
              const pct = ((item.count / TOTAL) * 100).toFixed(1);
              return (
                <div key={item.class}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      marginBottom: 4,
                    }}
                  >
                    <span
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 9,
                        color: item.color,
                        letterSpacing: '0.15em',
                      }}
                    >
                      {item.class.toUpperCase()}
                    </span>
                    <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                      <span
                        style={{
                          fontFamily: "'JetBrains Mono', monospace",
                          fontSize: 9,
                          color: '#4a5a6a',
                        }}
                      >
                        {item.count} events
                      </span>
                      <span
                        style={{
                          fontFamily: "'JetBrains Mono', monospace",
                          fontSize: 9,
                          color: '#d0d8e4',
                          minWidth: 36,
                          textAlign: 'right',
                        }}
                      >
                        {pct}%
                      </span>
                    </div>
                  </div>
                  <div
                    style={{
                      height: 8,
                      backgroundColor: '#1e2530',
                      borderRadius: 0,
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${pct}%`,
                        backgroundColor: item.color,
                        opacity: 0.85,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>

        {/* Activity Feed */}
        <Panel title="RECENT ACTIVITY">
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 0,
              maxHeight: 260,
              overflowY: 'auto',
            }}
          >
            {ACTIVITY_FEED.map((event, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  gap: 8,
                  padding: '6px 0',
                  borderBottom: '1px solid #1e2530',
                  alignItems: 'flex-start',
                }}
              >
                <span style={{ fontSize: 10, flexShrink: 0, marginTop: 1 }}>{event.icon}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 10,
                      color: '#d0d8e4',
                      lineHeight: 1.4,
                      wordBreak: 'break-word',
                    }}
                  >
                    {event.text}
                  </div>
                </div>
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 9,
                    color: '#4a5a6a',
                    flexShrink: 0,
                    marginTop: 1,
                  }}
                >
                  {event.time}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {/* Safety Threshold Status */}
      <Panel title="SAFETY THRESHOLD STATUS">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20, padding: '4px 0' }}>
          {SAFETY_THRESHOLDS.map((t, i) => {
            const display = t.displayMultiplier
              ? (t.current * t.displayMultiplier).toFixed(1) + t.suffix
              : t.current.toFixed(2) + t.suffix;
            return (
              <div key={i}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span
                    style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 9,
                      color: '#4a5a6a',
                      letterSpacing: '0.15em',
                    }}
                  >
                    {t.label.toUpperCase()} ({t.displayMultiplier ? (t.marker * t.displayMultiplier).toFixed(0) + '%' : t.marker.toFixed(2)})
                  </span>
                  <span
                    style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 11,
                      color: '#00d4aa',
                    }}
                  >
                    {display}
                  </span>
                </div>
                <div
                  style={{
                    position: 'relative',
                    height: 6,
                    backgroundColor: '#1e2530',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${t.current * 100}%`,
                      backgroundColor: '#00d4aa',
                      opacity: 0.8,
                    }}
                  />
                  {/* Threshold marker */}
                  <div
                    style={{
                      position: 'absolute',
                      top: -4,
                      left: `${t.marker * 100}%`,
                      width: 1,
                      height: 14,
                      backgroundColor: '#f59e0b',
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}

function KpiCard({
  value,
  label,
  sub,
  subColor,
  alert,
}: {
  value: string;
  label: string;
  sub: string;
  subColor?: string;
  alert?: boolean;
}) {
  return (
    <div
      style={{
        backgroundColor: '#161b22',
        border: '1px solid #1e2530',
        borderTop: `2px solid #00d4aa`,
        padding: '20px 20px 16px',
      }}
    >
      <div
        style={{
          fontFamily: "'Syne', sans-serif",
          fontWeight: 800,
          fontSize: 36,
          color: alert ? '#f59e0b' : '#d0d8e4',
          lineHeight: 1,
          marginBottom: 8,
        }}
      >
        {value}
      </div>
      <div
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 9,
          color: '#4a5a6a',
          letterSpacing: '0.2em',
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 10,
          color: subColor || '#4a5a6a',
        }}
      >
        {sub}
      </div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        backgroundColor: '#111418',
        border: '1px solid #1e2530',
        padding: 20,
      }}
    >
      <div
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 9,
          color: '#4a5a6a',
          letterSpacing: '0.25em',
          marginBottom: 16,
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}
