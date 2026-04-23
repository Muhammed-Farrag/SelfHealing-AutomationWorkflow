import React, { useEffect, useRef, useState } from 'react';

interface ConfidenceGaugeProps {
  value: number; // 0 to 1
  size?: number; // diameter in px
  strokeWidth?: number;
  showLabel?: boolean;
}

function getColor(value: number): string {
  if (value < 0.3) return '#ef4444';
  if (value < 0.5) return '#f59e0b';
  return '#00d4aa';
}

export function ConfidenceGauge({ value, size = 80, strokeWidth = 6, showLabel = true }: ConfidenceGaugeProps) {
  const [animated, setAnimated] = useState(0);
  const radius = (size - strokeWidth * 2) / 2;
  const circumference = 2 * Math.PI * radius;
  const color = getColor(value);

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(value), 100);
    return () => clearTimeout(timer);
  }, [value]);

  const dashOffset = circumference * (1 - animated);

  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#1e2530"
          strokeWidth={strokeWidth}
        />
        {/* Progress */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          strokeLinecap="butt"
          style={{ transition: 'stroke-dashoffset 0.8s ease-out, stroke 0.3s ease' }}
        />
      </svg>
      {showLabel && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: size > 80 ? '18px' : '11px',
            fontWeight: 700,
            color,
          }}
        >
          {Math.round(value * 100)}%
        </div>
      )}
    </div>
  );
}

// Mini horizontal confidence bar
export function ConfidenceBar({ value }: { value: number }) {
  const color = getColor(value);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div
        style={{
          width: 60,
          height: 4,
          backgroundColor: '#1e2530',
          borderRadius: 1,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${value * 100}%`,
            height: '100%',
            backgroundColor: color,
            transition: 'width 0.5s ease',
          }}
        />
      </div>
      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color, minWidth: 34 }}>
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );
}
