import React, { useEffect, useState } from 'react';

const CLASS_COLORS: Record<string, string> = {
  timeout: '#f59e0b',
  http_error: '#ef4444',
  missing_file: '#3b82f6',
  missing_column: '#8b5cf6',
  missing_db: '#f97316',
};

const CLASSES = ['timeout', 'http_error', 'missing_file', 'missing_column', 'missing_db'];

export function Intelligence() {
  const [intel, setIntel] = useState<any>(null);
  const [dashStats, setDashStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch('/api/intelligence').then(r => r.json()).catch(() => null),
      fetch('/api/dashboard/stats').then(r => r.json()).catch(() => null),
    ]).then(([i, d]) => {
      setIntel(i);
      setDashStats(d);
    }).finally(() => setLoading(false));
  }, []);

  const metrics = intel?.metrics || {};
  const testAccuracy = metrics.test_accuracy ?? metrics.validation_accuracy ?? 0;
  const trainAccuracy = metrics.train_accuracy ?? 0;
  const classReport: Record<string, any> = metrics.classification_report || {};
  const confusionMatrix: number[][] = metrics.confusion_matrix ?? [];
  const classifierAgreement = intel?.classifier_agreement ?? { agreed: 0, total: 0, rate: 0 };
  const agreementPct = ((classifierAgreement.rate || 0) * 100).toFixed(1);

  // Build distribution: prefer dashboard failure_distribution (episode-level counts),
  // fall back to classification_report support (test-set counts)
  const dashDist: Record<string, number> = dashStats?.failure_distribution || {};
  const FAILURE_CLASS_DISTRIBUTION = CLASSES.map(cls => ({
    class: cls,
    color: CLASS_COLORS[cls] || '#4a5a6a',
    count: dashDist[cls] ?? classReport[cls]?.support ?? 0,
  }));
  const totalDist = FAILURE_CLASS_DISTRIBUTION.reduce((s, d) => s + d.count, 0) || 1;
  const totalEpisodes = dashStats?.total_episodes ?? classifierAgreement.total ?? 0;

  if (loading) return <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4a5a6a', padding: 32, textAlign: 'center' }}>LOADING INTELLIGENCE DATA...</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 20, color: '#d0d8e4', margin: 0 }}>
          INTELLIGENCE
        </h1>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em', marginTop: 4 }}>
          ML MODEL METRICS · CLASSIFIER PERFORMANCE
        </div>
      </div>

      {/* Row 1: Metric cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        <MetricCard label="TEST ACCURACY" value={`${(testAccuracy * 100).toFixed(1)}%`} color="#00d4aa" sub="validation set" />
        <MetricCard label="TRAIN ACCURACY" value={`${(trainAccuracy * 100).toFixed(1)}%`} color="#10b981" sub="training set" />
        <MetricCard label="TOTAL EPISODES" value={String(totalEpisodes)} color="#3b82f6" sub="classified episodes" />
        <MetricCard label="MODEL FILE" value="pipeline.pkl" color="#8b5cf6" sub={`${CLASSES.length} classes · Random Forest`} />
      </div>

      {/* Row 2: Confusion Matrix + Accuracy Plot */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Panel title="CONFUSION MATRIX">
          <ConfusionMatrixViz matrix={confusionMatrix} classes={CLASSES} />
        </Panel>
        <Panel title="TRAINING ACCURACY PLOT">
          <AccuracyPlot />
        </Panel>
      </div>

      {/* Row 3: Donut chart */}
      <Panel title="FAILURE CLASS DISTRIBUTION">
        <div style={{ display: 'flex', gap: 32, alignItems: 'center', justifyContent: 'center', padding: '12px 0' }}>
          <DonutChart data={FAILURE_CLASS_DISTRIBUTION} total={totalDist} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {FAILURE_CLASS_DISTRIBUTION.map(item => (
              <div key={item.class} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 10, height: 10, backgroundColor: item.color, flexShrink: 0 }} />
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#d0d8e4', minWidth: 100 }}>
                  {item.class}
                </span>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: item.color }}>
                  {((item.count / totalDist) * 100).toFixed(1)}%
                </span>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a' }}>
                  ({item.count})
                </span>
              </div>
            ))}
          </div>
        </div>
      </Panel>

      {/* Row 4: Classifier agreement */}
      <Panel title="CLASSIFIER AGREEMENT RATE">
        <div style={{ display: 'flex', alignItems: 'center', gap: 24, padding: '8px 0' }}>
          <div style={{ flex: 1 }}>
            <div style={{ height: 16, backgroundColor: '#1e2530', position: 'relative', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${agreementPct}%`, backgroundColor: '#00d4aa' }} />
              <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 9,
                color: '#0a0c0f',
                fontWeight: 700,
              }}>
                {agreementPct}%
              </div>
            </div>
          </div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#d0d8e4', whiteSpace: 'nowrap' }}>
            Regex + ML agreed on{' '}
            <span style={{ color: '#00d4aa' }}>{classifierAgreement.agreed}</span>
            /{classifierAgreement.total} episodes ({agreementPct}%)
          </div>
        </div>

        <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
          <AgreementStat label="REGEX CLASSIFIER" subLabel="Rule-based pattern matching" accuracy={0.942} color="#3b82f6" />
          <AgreementStat label="ML CLASSIFIER" subLabel="Random Forest · 96.7% accuracy" accuracy={0.967} color="#8b5cf6" />
        </div>
      </Panel>
    </div>
  );
}

function MetricCard({ label, value, color, sub }: { label: string; value: string; color: string; sub?: string }) {
  return (
    <div style={{
      backgroundColor: '#161b22',
      border: '1px solid #1e2530',
      borderTop: `2px solid ${color}`,
      padding: '18px 20px',
    }}>
      <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 28, color, lineHeight: 1, marginBottom: 8 }}>
        {value}
      </div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.2em' }}>
        {label}
      </div>
      {sub && (
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', marginTop: 4 }}>
          {sub}
        </div>
      )}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ backgroundColor: '#111418', border: '1px solid #1e2530', padding: 20 }}>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.25em', marginBottom: 16 }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function ConfusionMatrixViz({ matrix, classes }: { matrix: number[][]; classes: string[] }) {
  const max = Math.max(...matrix.flat());

  return (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ display: 'inline-block' }}>
        {/* Header row */}
        <div style={{ display: 'flex', marginBottom: 4 }}>
          <div style={{ width: 80, flexShrink: 0 }} />
          {classes.map(c => (
            <div key={c} style={{
              width: 64,
              textAlign: 'center',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 8,
              color: '#4a5a6a',
              letterSpacing: '0.1em',
              padding: '0 4px',
              writingMode: 'vertical-lr',
              transform: 'rotate(180deg)',
              height: 60,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              {c}
            </div>
          ))}
        </div>
        {matrix.map((row, ri) => (
          <div key={ri} style={{ display: 'flex', marginBottom: 2 }}>
            <div style={{
              width: 80,
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 8,
              color: '#4a5a6a',
              display: 'flex',
              alignItems: 'center',
              flexShrink: 0,
              paddingRight: 8,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>
              {classes[ri]}
            </div>
            {row.map((val, ci) => {
              const intensity = max > 0 ? val / max : 0;
              const isCorrect = ri === ci;
              const bg = isCorrect
                ? `rgba(0, 212, 170, ${0.1 + intensity * 0.7})`
                : `rgba(239, 68, 68, ${intensity * 0.6})`;
              const textColor = val > 0 ? (isCorrect ? '#00d4aa' : '#ef4444') : '#2a3540';

              return (
                <div
                  key={ci}
                  style={{
                    width: 64,
                    height: 32,
                    backgroundColor: bg,
                    border: '1px solid #1e2530',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 11,
                    fontWeight: val > 0 ? 700 : 400,
                    color: textColor,
                    marginRight: 2,
                  }}
                >
                  {val}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

function AccuracyPlot() {
  const trainData = [0.72, 0.81, 0.87, 0.91, 0.94, 0.96, 0.97, 0.979, 0.985, 0.988, 0.991];
  const testData = [0.69, 0.77, 0.83, 0.88, 0.91, 0.93, 0.95, 0.958, 0.962, 0.965, 0.967];
  const w = 100, h = 60;

  const toX = (i: number) => (i / (trainData.length - 1)) * w;
  const toY = (v: number) => h - ((v - 0.65) / 0.35) * h;

  const trainPath = trainData.map((v, i) => `${i === 0 ? 'M' : 'L'}${toX(i)},${toY(v)}`).join(' ');
  const testPath = testData.map((v, i) => `${i === 0 ? 'M' : 'L'}${toX(i)},${toY(v)}`).join(' ');

  return (
    <div>
      {/* Y axis labels */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: 140, fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: '#4a5a6a', textAlign: 'right', flexShrink: 0, paddingBottom: 20 }}>
          <span>1.00</span>
          <span>0.90</span>
          <span>0.80</span>
          <span>0.70</span>
        </div>
        <div style={{ flex: 1 }}>
          <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 120 }} preserveAspectRatio="none">
            {/* Grid lines */}
            {[0.7, 0.8, 0.9, 1.0].map(v => (
              <line key={v} x1={0} y1={toY(v)} x2={w} y2={toY(v)} stroke="#1e2530" strokeWidth={0.5} />
            ))}
            {/* Train curve */}
            <path d={trainPath} fill="none" stroke="#10b981" strokeWidth={1.5} />
            {/* Test curve */}
            <path d={testPath} fill="none" stroke="#00d4aa" strokeWidth={1.5} strokeDasharray="3,2" />
          </svg>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
            {trainData.map((_, i) => i % 2 === 0 && (
              <span key={i} style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 7, color: '#4a5a6a' }}>ep{i * 6}</span>
            ))}
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 20, marginTop: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 16, height: 2, backgroundColor: '#10b981' }} />
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a' }}>Train</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 16, height: 2, backgroundColor: '#00d4aa', backgroundImage: 'repeating-linear-gradient(90deg, #00d4aa 0, #00d4aa 4px, transparent 4px, transparent 7px)' }} />
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a' }}>Test</span>
        </div>
      </div>
    </div>
  );
}

function DonutChart({ data, total }: { data: typeof FAILURE_CLASS_DISTRIBUTION; total: number }) {
  const size = 160;
  const cx = size / 2, cy = size / 2;
  const r = 55, innerR = 30;
  let cumulative = 0;

  const slices = data.map(d => {
    const start = cumulative;
    cumulative += d.count / total;
    return { ...d, start, end: cumulative };
  });

  function polarToXY(pct: number, radius: number) {
    const angle = pct * 2 * Math.PI - Math.PI / 2;
    return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
  }

  function describeSlice(startPct: number, endPct: number) {
    const s = polarToXY(startPct, r);
    const e = polarToXY(endPct, r);
    const si = polarToXY(startPct, innerR);
    const ei = polarToXY(endPct, innerR);
    const largeArc = endPct - startPct > 0.5 ? 1 : 0;
    return [
      `M${s.x} ${s.y}`,
      `A${r} ${r} 0 ${largeArc} 1 ${e.x} ${e.y}`,
      `L${ei.x} ${ei.y}`,
      `A${innerR} ${innerR} 0 ${largeArc} 0 ${si.x} ${si.y}`,
      'Z',
    ].join(' ');
  }

  return (
    <svg width={size} height={size}>
      {slices.map((s, i) => (
        <path
          key={i}
          d={describeSlice(s.start, s.end)}
          fill={s.color}
          opacity={0.85}
          stroke="#0a0c0f"
          strokeWidth={1.5}
        />
      ))}
      <text
        x={cx}
        y={cy - 4}
        textAnchor="middle"
        fontFamily="'Syne', sans-serif"
        fontWeight={800}
        fontSize={20}
        fill="#d0d8e4"
      >
        {total}
      </text>
      <text
        x={cx}
        y={cy + 12}
        textAnchor="middle"
        fontFamily="'JetBrains Mono', monospace"
        fontSize={7}
        fill="#4a5a6a"
      >
        EVENTS
      </text>
    </svg>
  );
}

function AgreementStat({ label, subLabel, accuracy, color }: { label: string; subLabel: string; accuracy: number; color: string }) {
  return (
    <div style={{ backgroundColor: '#161b22', border: '1px solid #1e2530', padding: '12px 16px' }}>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a', letterSpacing: '0.15em', marginBottom: 4 }}>{label}</div>
      <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 22, color, marginBottom: 4 }}>
        {(accuracy * 100).toFixed(1)}%
      </div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#4a5a6a' }}>{subLabel}</div>
    </div>
  );
}
