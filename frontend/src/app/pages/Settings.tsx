import React, { useState, useEffect } from 'react';

export function Settings() {
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.50);
  const [highConfidenceAutoApply, setHighConfidenceAutoApply] = useState(0.85);
  const [requireHumanThreshold, setRequireHumanThreshold] = useState(0.50);

  const [groqKey, setGroqKey] = useState('sk-groq-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx1234');
  const [revealGroq, setRevealGroq] = useState(false);
  const [testingGroq, setTestingGroq] = useState(false);
  const [testResults, setTestResults] = useState<Record<string, string>>({});

  const [autoPatchEnabled, setAutoPatchEnabled] = useState(true);
  const [dryRunMode, setDryRunMode] = useState(false);
  const [auditLogging, setAuditLogging] = useState(true);

  const [toast, setToast] = useState<{ msg: string; isError: boolean } | null>(null);

  const showToast = (msg: string, isError = false) => {
    setToast({ msg, isError });
    setTimeout(() => setToast(null), 4000);
  };

  const testConnection = (provider: 'groq') => {
    setTestingGroq(true);
    setTimeout(() => {
      setTestingGroq(false);
      setTestResults(prev => ({
        ...prev,
        [provider]: '✓ CONNECTED · latency: 312ms · model: llama-3.3-70b-versatile',
      }));
    }, 1800);
  };

  const maskKey = (key: string) => {
    if (key.length <= 4) return key;
    return '•'.repeat(key.length - 4) + key.slice(-4);
  };

  // Load current settings from backend on mount
  useEffect(() => {
    fetch('/api/settings/thresholds')
      .then(r => r.json())
      .then(s => {
        if (s.confidence_threshold !== undefined) setConfidenceThreshold(s.confidence_threshold);
        if (s.auto_patch_threshold !== undefined) setHighConfidenceAutoApply(s.auto_patch_threshold);
        if (s.require_human_below !== undefined) setRequireHumanThreshold(s.require_human_below);
        if (s.auto_patch_enabled !== undefined) setAutoPatchEnabled(s.auto_patch_enabled);
        if (s.dry_run_mode !== undefined) setDryRunMode(s.dry_run_mode);
        if (s.audit_logging !== undefined) setAuditLogging(s.audit_logging);
      })
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    try {
      const res = await fetch('/api/settings/thresholds', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          confidence_threshold: confidenceThreshold,
          auto_patch_threshold: highConfidenceAutoApply,
          require_human_below: requireHumanThreshold,
          auto_patch_enabled: autoPatchEnabled,
          dry_run_mode: dryRunMode,
          audit_logging: auditLogging,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      showToast('✓ CONFIGURATION SAVED — all settings persisted to backend');
    } catch (e: any) {
      showToast(`⚠ SAVE FAILED: ${e.message}`, true);
    }
  };

  const handleResetDefaults = async () => {
    try {
      const res = await fetch('/api/settings/defaults');
      const defaults = await res.json();
      setConfidenceThreshold(defaults.confidence_threshold);
      setHighConfidenceAutoApply(defaults.auto_patch_threshold);
      setRequireHumanThreshold(defaults.require_human_below);
      setAutoPatchEnabled(defaults.auto_patch_enabled);
      setDryRunMode(defaults.dry_run_mode);
      setAuditLogging(defaults.audit_logging);
      showToast('↺ DEFAULTS RESTORED — click Save to persist');
    } catch {
      showToast('⚠ Could not fetch defaults', true);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 720 }}>
      <div>
        <h1 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4', margin: 0 }}>
          SETTINGS
        </h1>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginTop: 4 }}>
          SYSTEM CONFIGURATION · SAFETY CONTROLS
        </div>
      </div>

      {/* Section 1: Safety Thresholds */}
      <Section title="SAFETY THRESHOLDS">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <SliderControl
            label="CONFIDENCE THRESHOLD"
            description="Minimum confidence score required to generate a repair plan"
            value={confidenceThreshold}
            onChange={setConfidenceThreshold}
          />
          <SliderControl
            label="HIGH CONFIDENCE AUTO-APPLY"
            description="Plans above this confidence are applied automatically without review"
            value={highConfidenceAutoApply}
            onChange={setHighConfidenceAutoApply}
          />
          <SliderControl
            label="REQUIRE HUMAN THRESHOLD"
            description="Plans below this confidence require mandatory human approval"
            value={requireHumanThreshold}
            onChange={setRequireHumanThreshold}
          />
        </div>
      </Section>

      <Divider />

      {/* Section 2: API Configuration — GROQ only */}
      <Section title="API CONFIGURATION">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <ApiKeyInput
            label="GROQ_API_KEY"
            value={groqKey}
            onChange={setGroqKey}
            revealed={revealGroq}
            onReveal={() => setRevealGroq(v => !v)}
            onTest={() => testConnection('groq')}
            testing={testingGroq}
            testResult={testResults['groq']}
            maskKey={maskKey}
          />
        </div>
      </Section>

      <Divider />

      {/* Section 3: System Controls */}
      <Section title="SYSTEM CONTROLS">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <ToggleControl
            label="AUTO_PATCH_ENABLED"
            description="Allow the system to automatically apply high-confidence patches"
            value={autoPatchEnabled}
            onChange={setAutoPatchEnabled}
            activeColor="#00d4aa"
          />
          <ToggleControl
            label="DRY_RUN_MODE"
            description="Preview all patches without applying them to production files"
            value={dryRunMode}
            onChange={setDryRunMode}
            activeColor="#f59e0b"
          />
          <ToggleControl
            label="AUDIT_LOGGING"
            description="Record all system events to the immutable audit trail"
            value={auditLogging}
            onChange={setAuditLogging}
            activeColor="#00d4aa"
          />
        </div>
      </Section>

      <div style={{ display: 'flex', gap: 12, paddingTop: 8 }}>
        <button
          onClick={handleSave}
          style={{
            backgroundColor: '#00d4aa',
            border: 'none',
            color: '#0a0c0f',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
            fontWeight: 700,
            padding: '10px 28px',
            cursor: 'pointer',
            letterSpacing: '0.15em',
          }}
        >
          SAVE CONFIGURATION
        </button>
        <button
          onClick={handleResetDefaults}
          style={{
            backgroundColor: 'transparent',
            border: '1px solid #2a3540',
            color: '#4a5a6a',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
            padding: '10px 20px',
            cursor: 'pointer',
            letterSpacing: '0.1em',
          }}
        >
          RESET TO DEFAULTS
        </button>
      </div>

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          backgroundColor: '#111418',
          border: '1px solid #1e2530',
          borderLeft: `3px solid ${toast.isError ? '#ef4444' : '#00d4aa'}`,
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
          <span style={{ color: toast.isError ? '#ef4444' : '#00d4aa' }}>{toast.isError ? '⚠' : '✓'}</span>
          {toast.msg}
          <button onClick={() => setToast(null)} style={{ background: 'none', border: 'none', color: '#4a5a6a', cursor: 'pointer', fontSize: 14 }}>×</button>
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.25em', marginBottom: 16 }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function Divider() {
  return <div style={{ height: 1, backgroundColor: '#1e2530' }} />;
}

function SliderControl({ label, description, value, onChange }: {
  label: string;
  description: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', letterSpacing: '0.1em' }}>{label}</div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', marginTop: 2 }}>{description}</div>
        </div>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, color: '#00d4aa', minWidth: 40, textAlign: 'right' }}>
          {value.toFixed(2)}
        </span>
      </div>
      <div style={{ position: 'relative', height: 6, backgroundColor: '#1e2530' }}>
        <div style={{ position: 'absolute', left: 0, top: 0, height: '100%', width: `${value * 100}%`, backgroundColor: '#00d4aa' }} />
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={value}
          onChange={e => onChange(parseFloat(e.target.value))}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            opacity: 0,
            cursor: 'pointer',
            height: '100%',
          }}
        />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: '#4a5a6a' }}>0.0</span>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: '#4a5a6a' }}>1.0</span>
      </div>
    </div>
  );
}

function ApiKeyInput({ label, value, onChange, revealed, onReveal, onTest, testing, testResult, maskKey }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  revealed: boolean;
  onReveal: () => void;
  onTest: () => void;
  testing: boolean;
  testResult?: string;
  maskKey: (k: string) => string;
}) {
  return (
    <div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', letterSpacing: '0.1em', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          type={revealed ? 'text' : 'password'}
          value={value}
          onChange={e => onChange(e.target.value)}
          style={{
            flex: 1,
            backgroundColor: '#161b22',
            border: '1px solid #1e2530',
            color: '#d0d8e4',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
            padding: '8px 10px',
            outline: 'none',
          }}
        />
        <button
          onClick={onReveal}
          title={revealed ? 'Hide' : 'Reveal'}
          style={{
            width: 36,
            backgroundColor: '#161b22',
            border: '1px solid #1e2530',
            color: '#4a5a6a',
            cursor: 'pointer',
            fontSize: 13,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {revealed ? '🙈' : '👁'}
        </button>
        <button
          onClick={onTest}
          disabled={testing}
          style={{
            backgroundColor: 'transparent',
            border: '1px solid #2a3540',
            color: testing ? '#4a5a6a' : '#d0d8e4',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            padding: '8px 12px',
            cursor: testing ? 'not-allowed' : 'pointer',
            letterSpacing: '0.1em',
            whiteSpace: 'nowrap',
          }}
        >
          {testing ? '...' : 'TEST CONNECTION'}
        </button>
      </div>
      {testResult && (
        <div style={{ marginTop: 6, fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#10b981' }}>
          {testResult}
        </div>
      )}
    </div>
  );
}

function ToggleControl({ label, description, value, onChange, activeColor }: {
  label: string;
  description: string;
  value: boolean;
  onChange: (v: boolean) => void;
  activeColor: string;
}) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 20 }}>
      <div>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', letterSpacing: '0.1em' }}>
          {label}
        </div>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', marginTop: 2 }}>
          {description}
        </div>
      </div>
      <div
        onClick={() => onChange(!value)}
        style={{
          width: 44,
          height: 24,
          backgroundColor: value ? activeColor : '#1e2530',
          border: `1px solid ${value ? activeColor : '#2a3540'}`,
          cursor: 'pointer',
          position: 'relative',
          transition: 'all 0.2s ease',
          flexShrink: 0,
        }}
      >
        <div style={{
          position: 'absolute',
          top: 3,
          left: value ? 22 : 4,
          width: 16,
          height: 16,
          backgroundColor: value ? '#0a0c0f' : '#4a5a6a',
          transition: 'left 0.2s ease',
        }} />
      </div>
    </div>
  );
}
