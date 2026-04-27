import React from 'react';
import { NavLink, useLocation } from 'react-router';
import { REPAIR_PLANS } from '../data/mockData';

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/' },
  { label: 'Episodes', path: '/episodes' },
  { label: 'Repair Plans', path: '/plans' },
  { label: 'Review Queue', path: '/review' },
  { label: 'Audit Trail', path: '/audit' },
  { label: 'Rollback', path: '/rollback' },
  { label: 'Intelligence', path: '/intelligence' },
  { label: 'A/B Benchmark', path: '/benchmark' },
  { label: 'Settings', path: '/settings' },
];

const pendingCount = REPAIR_PLANS.filter(p => p.requiresHuman && p.status === 'pending').length;

export function Sidebar() {
  const location = useLocation();

  return (
    <aside
      style={{
        width: 220,
        minWidth: 220,
        backgroundColor: '#0d1014',
        borderRight: '1px solid #1e2530',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        position: 'sticky',
        top: 0,
        flexShrink: 0,
      }}
    >
      {/* Wordmark */}
      <div style={{ padding: '24px 20px 20px', borderBottom: '1px solid #1e2530' }}>
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontWeight: 700,
            fontSize: 14,
            color: '#00d4aa',
            letterSpacing: '0.05em',
          }}
        >
          SH-AI
        </div>
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            color: '#4a5a6a',
            letterSpacing: '0.2em',
            marginTop: 4,
          }}
        >
          SELF-HEALING v1.0
        </div>
      </div>

      {/* Nav items */}
      <nav style={{ flex: 1, padding: '12px 0', overflowY: 'auto' }}>
        {NAV_ITEMS.map(item => {
          const isActive = item.path === '/'
            ? location.pathname === '/'
            : location.pathname.startsWith(item.path);

          return (
            <NavLink
              key={item.path}
              to={item.path}
              style={{ textDecoration: 'none' }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '9px 20px',
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 11,
                  color: isActive ? '#00d4aa' : '#d0d8e4',
                  backgroundColor: isActive ? 'rgba(0,212,170,0.07)' : 'transparent',
                  borderLeft: isActive ? '2px solid #00d4aa' : '2px solid transparent',
                  cursor: 'pointer',
                  transition: 'all 0.1s ease',
                  letterSpacing: '0.02em',
                }}
                onMouseEnter={e => {
                  if (!isActive) {
                    (e.currentTarget as HTMLDivElement).style.backgroundColor = '#111418';
                    (e.currentTarget as HTMLDivElement).style.borderLeftColor = '#2a3540';
                  }
                }}
                onMouseLeave={e => {
                  if (!isActive) {
                    (e.currentTarget as HTMLDivElement).style.backgroundColor = 'transparent';
                    (e.currentTarget as HTMLDivElement).style.borderLeftColor = 'transparent';
                  }
                }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 9, color: isActive ? '#00d4aa' : '#4a5a6a' }}>⬡</span>
                  {item.label}
                </span>
                {item.path === '/review' && pendingCount > 0 && (
                  <span
                    style={{
                      backgroundColor: '#ef4444',
                      color: '#fff',
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 9,
                      fontWeight: 700,
                      padding: '1px 5px',
                      borderRadius: 2,
                      minWidth: 18,
                      textAlign: 'center',
                    }}
                  >
                    {pendingCount}
                  </span>
                )}
              </div>
            </NavLink>
          );
        })}
      </nav>

      {/* System status */}
      <div
        style={{
          padding: '16px 20px',
          borderTop: '1px solid #1e2530',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          <span style={{ color: '#10b981', fontSize: 8 }}>●</span>
          <span
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 9,
              color: '#10b981',
              letterSpacing: '0.15em',
            }}
          >
            OPERATIONAL
          </span>
        </div>
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            color: '#4a5a6a',
          }}
        >
          Last sync: 2 min ago
        </div>
      </div>
    </aside>
  );
}
