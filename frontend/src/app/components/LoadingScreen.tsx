import React, { useEffect, useState, useRef } from 'react';

interface Stage {
  label: string;
  detail: string;
  duration: number;
}

const STAGES: Stage[] = [
  { label: 'INITIALIZING DOCKER SERVICES', detail: 'airflow-webserver · scheduler · postgres · redis', duration: 2200 },
  { label: 'LOADING ML CLASSIFIER', detail: 'pipeline.pkl — 2.3 MB · accuracy: 96.7%', duration: 1800 },
  { label: 'BUILDING FAISS INDEX', detail: 'playbook.faiss — 847 vectors · dim: 384', duration: 1600 },
  { label: 'CONNECTING LLM API', detail: 'Provider: Groq · llama-3.3-70b-versatile · latency: 312ms', duration: 1400 },
];

interface LoadingScreenProps {
  onComplete: () => void;
}

interface StageState {
  progress: number;
  done: boolean;
  active: boolean;
}

export function LoadingScreen({ onComplete }: LoadingScreenProps) {
  const [stages, setStages] = useState<StageState[]>(
    STAGES.map(() => ({ progress: 0, done: false, active: false }))
  );
  const [allDone, setAllDone] = useState(false);
  const [logoScale, setLogoScale] = useState(false);
  const [fadeOut, setFadeOut] = useState(false);
  const animRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let stageIndex = 0;

    const runStage = (idx: number) => {
      if (idx >= STAGES.length) {
        // All done
        setLogoScale(true);
        setTimeout(() => {
          setAllDone(true);
          setTimeout(() => {
            setFadeOut(true);
            setTimeout(onComplete, 600);
          }, 1200);
        }, 400);
        return;
      }

      setStages(prev => prev.map((s, i) => i === idx ? { ...s, active: true } : s));

      const duration = STAGES[idx].duration;
      const startTime = performance.now();

      const tick = () => {
        const elapsed = performance.now() - startTime;
        const progress = Math.min(elapsed / duration, 1);

        setStages(prev =>
          prev.map((s, i) => i === idx ? { ...s, progress } : s)
        );

        if (progress < 1) {
          animRef.current = setTimeout(tick, 16);
        } else {
          setStages(prev =>
            prev.map((s, i) => i === idx ? { ...s, progress: 1, done: true, active: false } : s)
          );
          setTimeout(() => runStage(idx + 1), 300);
        }
      };

      tick();
    };

    runStage(0);

    return () => {
      if (animRef.current) clearTimeout(animRef.current);
    };
  }, []);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: '#0a0c0f',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        opacity: fadeOut ? 0 : 1,
        transition: 'opacity 0.6s ease',
        overflow: 'hidden',
      }}
    >
      {/* Animated grid background */}
      <AnimatedGrid />

      {/* Logo */}
      <div
        style={{
          textAlign: 'center',
          marginBottom: 64,
          transform: logoScale ? 'scale(1.06)' : 'scale(1)',
          transition: 'transform 0.5s ease',
        }}
      >
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontWeight: 700,
            fontSize: 72,
            color: '#00d4aa',
            letterSpacing: '-0.02em',
            lineHeight: 1,
          }}
        >
          SH-AI
        </div>
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
            color: '#4a5a6a',
            letterSpacing: '0.4em',
            marginTop: 12,
          }}
        >
          SELF-HEALING WORKFLOW AI
        </div>
      </div>

      {/* Stage rows */}
      <div
        style={{
          width: 520,
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
          opacity: allDone ? 0 : 1,
          transition: 'opacity 0.4s ease',
        }}
      >
        {STAGES.map((stage, i) => (
          <StageRow
            key={i}
            label={stage.label}
            detail={stage.detail}
            progress={stages[i].progress}
            done={stages[i].done}
            active={stages[i].active}
          />
        ))}
      </div>

      {/* System Ready */}
      {allDone && (
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 13,
            color: '#00d4aa',
            letterSpacing: '0.4em',
            marginTop: 32,
            animation: 'fadeIn 0.5s ease forwards',
          }}
        >
          ● SYSTEM READY
        </div>
      )}
    </div>
  );
}

function StageRow({ label, detail, progress, done, active }: {
  label: string;
  detail: string;
  progress: number;
  done: boolean;
  active: boolean;
}) {
  const visible = active || done || progress > 0;

  return (
    <div
      style={{
        opacity: visible ? 1 : 0.25,
        transition: 'opacity 0.3s ease',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
            color: done ? '#d0d8e4' : active ? '#d0d8e4' : '#4a5a6a',
            letterSpacing: '0.15em',
          }}
        >
          {label}
        </span>
        <StatusIndicator done={done} active={active} />
      </div>

      {/* Progress bar */}
      <div
        style={{
          height: 2,
          backgroundColor: '#1e2530',
          borderRadius: 0,
          overflow: 'hidden',
          marginBottom: 5,
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${progress * 100}%`,
            backgroundColor: done ? '#10b981' : '#f59e0b',
            transition: done ? 'background-color 0.3s ease' : 'none',
          }}
        />
      </div>

      {/* Detail line */}
      <div
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 9,
          color: '#4a5a6a',
          letterSpacing: '0.05em',
        }}
      >
        {detail}
      </div>
    </div>
  );
}

function StatusIndicator({ done, active }: { done: boolean; active: boolean }) {
  if (done) {
    return (
      <span style={{ color: '#10b981', fontSize: 12 }}>✓</span>
    );
  }
  if (active) {
    return (
      <span
        style={{
          display: 'inline-block',
          width: 8,
          height: 8,
          border: '2px solid #f59e0b',
          borderTopColor: 'transparent',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }}
      />
    );
  }
  return <span style={{ color: '#1e2530', fontSize: 12 }}>○</span>;
}

function AnimatedGrid() {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        overflow: 'hidden',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: '-100px',
          backgroundImage: `
            linear-gradient(rgba(0, 212, 170, 0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 212, 170, 0.04) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
          animation: 'gridDrift 12s ease-in-out infinite',
        }}
      />
    </div>
  );
}
