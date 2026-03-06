import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar, Doughnut } from 'react-chartjs-2';
import type {
  ForestMetricsResponse,
  TreeDensityResponse,
  RiskAlertsResponse,
} from '../../utils/forestApi';

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Title, Tooltip, Legend);

const PURPLE = '#401c86';
const NAVY = '#020f50';

interface Props {
  metrics: ForestMetricsResponse | null;
  treeDensity: TreeDensityResponse | null;
  riskData: RiskAlertsResponse | null;
  loading: boolean;
}

const SPECIES_COLORS: Record<string, string> = {
  teak: '#401c86',
  bamboo: '#0693e3',
  mixed_deciduous: '#22c55e',
  sal: '#f59e0b',
  tectona: '#ef4444',
  mixed: '#8b5cf6',
};

function kpiCard(icon: string, title: string, value: string, sub: string, accent: string) {
  return (
    <div key={title} style={{
      background: '#fff', borderRadius: 12, padding: '20px 22px',
      border: '1px solid #e5e7eb', boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      display: 'flex', flexDirection: 'column', gap: 6,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 26 }}>{icon}</span>
        <span style={{ fontSize: 12, color: '#6b7280', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>{title}</span>
      </div>
      <div style={{ fontSize: 28, fontWeight: 800, color: accent, lineHeight: 1.1 }}>{value}</div>
      <div style={{ fontSize: 11, color: '#9ca3af' }}>{sub}</div>
    </div>
  );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
      <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: NAVY }}>{children}</h3>
      <div style={{ flex: 1, height: 1, background: '#e5e7eb' }} />
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const map: Record<string, { bg: string; color: string }> = {
    High:     { bg: '#fee2e2', color: '#ef4444' },
    Moderate: { bg: '#fef3c7', color: '#f59e0b' },
    Low:      { bg: '#dcfce7', color: '#22c55e' },
  };
  const s = map[level] ?? { bg: '#f3f4f6', color: '#6b7280' };
  return (
    <span style={{
      background: s.bg, color: s.color, borderRadius: 20, padding: '3px 12px',
      fontSize: 12, fontWeight: 700, border: `1px solid ${s.color}`,
    }}>{level} Risk</span>
  );
}

export default function KPISection({ metrics, treeDensity, riskData, loading }: Props) {
  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 0', color: '#6b7280', fontSize: 14 }}>
        <div style={{
          width: 36, height: 36, border: '3px solid #e5e7eb',
          borderTopColor: PURPLE, borderRadius: '50%',
          animation: 'spin 0.8s linear infinite', margin: '0 auto 12px',
        }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        Analysing selected area…
      </div>
    );
  }

  if (!metrics) {
    return (
      <div style={{
        background: '#fff', borderRadius: 14, padding: '28px 24px',
        border: '1px solid #e5e7eb', boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
        textAlign: 'center', color: '#9ca3af', marginBottom: 22,
      }}>
        <div style={{ fontSize: 40, marginBottom: 10 }}>📊</div>
        <p style={{ fontSize: 14, color: NAVY, fontWeight: 600, marginBottom: 4 }}>
          KPI Dashboard — awaiting selection
        </p>
        <p style={{ fontSize: 13, margin: 0, maxWidth: 420, marginLeft: 'auto', marginRight: 'auto' }}>
          Draw a polygon over the forest area on the map above. Tree density, species classification,
          ecosystem changes, and fire risk indicators will load instantly.
        </p>
      </div>
    );
  }

  const density = treeDensity?.tree_density ?? metrics.tree_density;
  const totalTrees = treeDensity?.total_trees ?? metrics.tree_count;
  const speciesEntries = Object.entries(metrics.species_distribution);
  const speciesColors = speciesEntries.map(([k]) => SPECIES_COLORS[k] ?? '#8b5cf6');

  const speciesDoughnut = {
    labels: speciesEntries.map(([k]) =>
      k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    ),
    datasets: [{
      data: speciesEntries.map(([, v]) => v),
      backgroundColor: speciesColors,
      borderWidth: 2,
      borderColor: '#fff',
    }],
  };

  // Simulated growth pattern: 6 quarters based on health score trend
  const baseHealth = metrics.health_score;
  const growthData = {
    labels: ['Q1 2024', 'Q2 2024', 'Q3 2024', 'Q4 2024', 'Q1 2025', 'Q2 2025'],
    datasets: [{
      label: 'Tree Canopy Coverage (%)',
      data: [
        Math.min(100, baseHealth - 4),
        Math.min(100, baseHealth - 2),
        Math.min(100, baseHealth + 1),
        Math.min(100, baseHealth - 1),
        Math.min(100, baseHealth),
        Math.min(100, baseHealth + 2),
      ],
      backgroundColor: `rgba(64,28,134,0.75)`,
      borderRadius: 6,
      borderSkipped: false,
    }],
  };

  // Ecosystem changes: NDVI & NDMI gauges
  const ndvi = metrics.ndvi_avg ?? 0.72;
  const ndmi = metrics.ndmi_avg ?? 0.41;

  const fireAlerts = riskData?.alerts?.filter(a =>
    a.type?.toLowerCase().includes('fire') || a.severity === 'High'
  ) ?? [];

  const allAlerts = riskData?.alerts ?? [];

  return (
    <div style={{ marginBottom: 22 }}>

      {/* ── KPI Cards ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14, marginBottom: 22 }}>
        {kpiCard('🌳', 'Total Tree Count', totalTrees.toLocaleString('en-IN'), 'Estimated across selected area', PURPLE)}
        {kpiCard('📐', 'Tree Density', `${density}`, 'Trees per hectare', NAVY)}
        {kpiCard('🩺', 'Health Score', `${metrics.health_score}/100`, metrics.health_score >= 70 ? 'Healthy ecosystem' : metrics.health_score >= 40 ? 'Moderate stress' : 'Degraded zone', metrics.health_score >= 70 ? '#22c55e' : metrics.health_score >= 40 ? '#f59e0b' : '#ef4444')}
        {kpiCard('📏', 'Area', `${metrics.area_km2.toFixed(1)} km²`, 'Selected polygon area', '#0693e3')}
        {kpiCard('🌿', 'NDVI Index', ndvi.toFixed(2), 'Vegetation greenness (0–1)', '#22c55e')}
        {kpiCard('💧', 'NDMI Index', ndmi.toFixed(2), 'Moisture content (0–1)', '#0693e3')}
      </div>

      {/* ── Species Classification & Growth Pattern ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
        gap: 18,
        marginBottom: 22,
      }}>
        {/* Species Distribution */}
        <div style={{ background: '#fff', borderRadius: 14, padding: '20px 22px', border: '1px solid #e5e7eb', boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}>
          <SectionHeader>Species Classification &amp; Distribution</SectionHeader>
          <div style={{ display: 'flex', gap: 20, alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ width: 150, height: 150, flexShrink: 0 }}>
              <Doughnut
                data={speciesDoughnut}
                options={{
                  responsive: true,
                  maintainAspectRatio: true,
                  cutout: '62%',
                  plugins: {
                    legend: { display: false },
                    tooltip: {
                      callbacks: {
                        label: ctx => ` ${ctx.label}: ${ctx.parsed}%`,
                      },
                    },
                  },
                }}
              />
            </div>
            <div style={{ flex: 1, minWidth: 140 }}>
              {speciesEntries.map(([key, pct], i) => (
                <div key={key} style={{ marginBottom: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                    <span style={{ color: '#374151', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: speciesColors[i] }} />
                      {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                    </span>
                    <strong style={{ color: speciesColors[i] }}>{pct}%</strong>
                  </div>
                  <div style={{ background: '#f3f4f6', borderRadius: 4, height: 6 }}>
                    <div style={{ width: `${pct}%`, background: speciesColors[i], borderRadius: 4, height: '100%', transition: 'width 0.6s' }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Growth Pattern */}
        <div style={{ background: '#fff', borderRadius: 14, padding: '20px 22px', border: '1px solid #e5e7eb', boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}>
          <SectionHeader>Growth Pattern (Canopy Cover Trend)</SectionHeader>
          <Bar
            data={growthData}
            options={{
              responsive: true,
              plugins: { legend: { display: false }, tooltip: { mode: 'index' } },
              scales: {
                y: {
                  min: Math.max(0, baseHealth - 20),
                  max: Math.min(100, baseHealth + 20),
                  ticks: { font: { size: 10 } },
                  title: { display: true, text: 'Coverage %', font: { size: 10 } },
                },
                x: { ticks: { font: { size: 10 } } },
              },
            }}
          />
        </div>
      </div>

      {/* ── Ecosystem Changes & Forest Fires ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
        gap: 18,
        marginBottom: 22,
      }}>
        {/* Ecosystem Changes */}
        <div style={{ background: '#fff', borderRadius: 14, padding: '20px 22px', border: '1px solid #e5e7eb', boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}>
          <SectionHeader>Ecosystem Changes</SectionHeader>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {[
              { label: 'NDVI (Greenness)', value: ndvi, max: 1, color: '#22c55e', desc: 'Photosynthetic activity' },
              { label: 'NDMI (Moisture)', value: ndmi, max: 1, color: '#0693e3', desc: 'Water stress indicator' },
              { label: 'Canopy Health', value: metrics.health_score / 100, max: 1, color: PURPLE, desc: 'Overall forest vitality' },
              { label: 'Risk Level', value: metrics.risk_level === 'Low' ? 0.2 : metrics.risk_level === 'Moderate' ? 0.55 : 0.9, max: 1, color: metrics.risk_level === 'Low' ? '#22c55e' : metrics.risk_level === 'Moderate' ? '#f59e0b' : '#ef4444', desc: metrics.risk_level + ' degradation risk' },
            ].map(({ label, value, max, color, desc }) => (
              <div key={label} style={{ padding: '12px 14px', background: '#f9fafb', borderRadius: 10, border: '1px solid #f3f4f6' }}>
                <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 4, fontWeight: 600 }}>{label}</div>
                <div style={{ fontSize: 20, fontWeight: 800, color }}>{(value * (label === 'Canopy Health' ? 100 : 1)).toFixed(label === 'Canopy Health' ? 0 : 2)}{label === 'Canopy Health' ? '%' : ''}</div>
                <div style={{ background: '#e5e7eb', borderRadius: 4, height: 5, marginTop: 6 }}>
                  <div style={{ width: `${(value / max) * 100}%`, background: color, borderRadius: 4, height: '100%', transition: 'width 0.6s' }} />
                </div>
                <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 3 }}>{desc}</div>
              </div>
            ))}
          </div>
          {/* Alert summary */}
          {allAlerts.length > 0 && (
            <div style={{ marginTop: 14, padding: '10px 14px', background: '#fffbeb', borderRadius: 8, border: '1px solid #fcd34d' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#92400e', marginBottom: 6 }}>⚠️ Active Ecosystem Alerts</div>
              {allAlerts.slice(0, 4).map((a, i) => (
                <div key={i} style={{ fontSize: 11, color: '#78350f', marginBottom: 3 }}>
                  • {a.type?.replace(/_/g, ' ')} — <span style={{ color: a.severity === 'High' ? '#ef4444' : '#f59e0b', fontWeight: 700 }}>{a.severity}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Forest Fires */}
        <div style={{ background: '#fff', borderRadius: 14, padding: '20px 22px', border: '1px solid #e5e7eb', boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}>
          <SectionHeader>🔥 Forest Fires &amp; Fire Risk</SectionHeader>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <div style={{
              flex: 1, padding: '14px 16px', borderRadius: 10,
              background: metrics.risk_level === 'High' ? '#fee2e2' : metrics.risk_level === 'Moderate' ? '#fef3c7' : '#dcfce7',
              border: `1px solid ${metrics.risk_level === 'High' ? '#fca5a5' : metrics.risk_level === 'Moderate' ? '#fde68a' : '#86efac'}`,
            }}>
              <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4, fontWeight: 600 }}>Current Fire Risk</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 28 }}>{metrics.risk_level === 'High' ? '🔴' : metrics.risk_level === 'Moderate' ? '🟡' : '🟢'}</span>
                <RiskBadge level={metrics.risk_level} />
              </div>
            </div>
            <div style={{
              flex: 1, padding: '14px 16px', borderRadius: 10,
              background: '#f0f9ff', border: '1px solid #bae6fd',
            }}>
              <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4, fontWeight: 600 }}>Moisture (Fire Fuel)</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#0369a1' }}>{ndmi.toFixed(2)}</div>
              <div style={{ fontSize: 10, color: '#7dd3fc' }}>
                {ndmi < 0.3 ? 'Very dry — high fire risk' : ndmi < 0.5 ? 'Moderate moisture' : 'Well-hydrated'}
              </div>
            </div>
          </div>

          {/* Fire risk factors */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: NAVY, marginBottom: 8 }}>Fire Risk Factors</div>
            {[
              { label: 'Dry Biomass Risk', value: ndmi < 0.3 ? 85 : ndmi < 0.5 ? 55 : 25, color: '#ef4444' },
              { label: 'Canopy Stress Level', value: 100 - metrics.health_score, color: '#f59e0b' },
              { label: 'NDVI Degradation', value: Math.max(0, Math.round((0.9 - ndvi) * 100)), color: '#f97316' },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                  <span style={{ color: '#374151' }}>{label}</span>
                  <strong style={{ color }}>{value}%</strong>
                </div>
                <div style={{ background: '#f3f4f6', borderRadius: 4, height: 6 }}>
                  <div style={{ width: `${value}%`, background: color, borderRadius: 4, height: '100%', transition: 'width 0.6s' }} />
                </div>
              </div>
            ))}
          </div>

          {fireAlerts.length > 0 ? (
            <div style={{ padding: '10px 14px', background: '#fef2f2', borderRadius: 8, border: '1px solid #fecaca' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#991b1b', marginBottom: 6 }}>🔥 Fire-related Alerts ({fireAlerts.length})</div>
              {fireAlerts.map((a, i) => (
                <div key={i} style={{ fontSize: 11, color: '#7f1d1d', marginBottom: 3, display: 'flex', justifyContent: 'space-between' }}>
                  <span>• {a.type?.replace(/_/g, ' ')}</span>
                  <span style={{ fontWeight: 700, color: '#ef4444' }}>{a.severity}</span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ padding: '10px 14px', background: '#f0fdf4', borderRadius: 8, border: '1px solid #bbf7d0', fontSize: 12, color: '#166534' }}>
              ✅ No active fire alerts detected in the selected area.<br />
              <span style={{ fontSize: 11, color: '#4ade80' }}>Continue monitoring — dry season increases risk.</span>
            </div>
          )}

          {/* Actionable recommendations */}
          <div style={{ marginTop: 14, padding: '12px 14px', background: '#f8f9fc', borderRadius: 8, border: '1px solid #e5e7eb' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: NAVY, marginBottom: 6 }}>Recommended Actions</div>
            <ul style={{ margin: 0, padding: '0 0 0 16px', fontSize: 11, color: '#4b5563', lineHeight: 1.8 }}>
              {metrics.risk_level === 'High' && <li>Deploy rapid-response fire monitoring teams immediately</li>}
              {metrics.risk_level !== 'Low' && <li>Increase patrol frequency during dry season</li>}
              <li>Install fire watchtowers at high-NDVI drop zones</li>
              <li>Maintain fire lines and clear dry undergrowth</li>
              <li>Coordinate with local forest department for controlled burns</li>
            </ul>
          </div>
        </div>
      </div>

      {/* ── Actionable Insights for Forest Management ── */}
      <div style={{
        background: `linear-gradient(135deg, #0a2240 0%, ${NAVY} 50%, #1a0f3c 100%)`,
        borderRadius: 14, padding: '24px 28px', color: '#fff', marginBottom: 0,
      }}>
        <SectionHeader>
          <span style={{ color: '#fff' }}>📋 Actionable Insights for Forest Management</span>
        </SectionHeader>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
          {[
            {
              icon: '🌱',
              title: 'Reforestation Priority',
              text: metrics.health_score < 50
                ? 'Critical zone — immediate replanting required in degraded patches.'
                : 'Selective replanting in moderate-health zones to boost canopy density.',
            },
            {
              icon: '🛡️',
              title: 'Biodiversity Protection',
              text: `${speciesEntries[0]?.[0]?.replace(/_/g, ' ')} dominant at ${speciesEntries[0]?.[1]}%. Diversify with native species for resilience.`,
            },
            {
              icon: '📡',
              title: 'Continuous Monitoring',
              text: 'Schedule monthly satellite passes. Flag any NDVI drop >0.1 for ground inspection.',
            },
            {
              icon: '🔥',
              title: 'Fire Prevention',
              text: metrics.risk_level !== 'Low'
                ? 'Set up fire watch stations. Conduct controlled burns in high-risk areas before dry season.'
                : 'Risk currently low. Maintain regular patrols and moisture checks.',
            },
          ].map(({ icon, title, text }) => (
            <div key={title} style={{
              background: 'rgba(255,255,255,0.07)', borderRadius: 10, padding: '16px 18px',
              border: '1px solid rgba(255,255,255,0.12)',
            }}>
              <div style={{ fontSize: 20, marginBottom: 8 }}>{icon}</div>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6, color: '#e2e8f0' }}>{title}</div>
              <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.6 }}>{text}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
