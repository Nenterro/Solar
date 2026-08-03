import { useState, useMemo, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  ChevronLeft, 
  ChevronRight, 
  Calendar as CalendarIcon, 
  Sun, 
  Zap, 
  BatteryCharging, 
  Gauge, 
  ArrowUpRight, 
  ArrowDownLeft 
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  AreaChart, 
  Area, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip 
} from 'recharts';
import { 
  format, 
  addDays, 
  subDays, 
  addMonths, 
  subMonths, 
  addYears, 
  subYears, 
  isSameDay, 
  isSameMonth, 
  isSameYear 
} from 'date-fns';
import InverterSelector from '../components/InverterSelector';
import { fetchFromBackend } from '../utils/api';
import './Graphs.css';

// 6 Core Energy Metrics
const METRICS_CONFIG = [
  { id: 'solar', label: 'Solar Yield', color: '#fbbf24', icon: Sun, unit: 'kW' },
  { id: 'load', label: 'Home Load', color: '#60a5fa', icon: Gauge, unit: 'kW' },
  { id: 'gridImport', label: 'Grid Import', color: '#ef4444', icon: ArrowDownLeft, unit: 'kW' },
  { id: 'gridExport', label: 'Grid Export', color: '#10b981', icon: ArrowUpRight, unit: 'kW' },
  { id: 'batteryCharge', label: 'Battery Charge', color: '#a855f7', icon: BatteryCharging, unit: 'kW' },
  { id: 'batteryDischarge', label: 'Battery Discharge', color: '#c084fc', icon: Zap, unit: 'kW' },
];

/**
 * Generate hourly tick marks from actual data range instead of fixed 24h.
 * This makes the graph scale to only show the time range with data.
 */
function computeHourlyTicks(data) {
  if (!data || data.length === 0) return [];
  const firstTime = data[0].time || '00:00';
  const lastTime = data[data.length - 1].time || '23:59';
  const startHour = parseInt(firstTime.split(':')[0], 10);
  const endHour = parseInt(lastTime.split(':')[0], 10);
  const ticks = [];
  for (let h = startHour; h <= endHour; h++) {
    ticks.push(`${h.toString().padStart(2, '0')}:00`);
  }
  return ticks;
}

/**
 * Trim zero-padded entries from the start of the daily history so the graph
 * scales to only the time range that has real recorded data.
 * Once we find the first point with any non-zero value, keep everything after it
 * (including legitimate zeros during the active recording period).
 */
function processDaily24hRecords(rawRecords) {
  if (!Array.isArray(rawRecords) || rawRecords.length === 0) return [];

  // Find the index of the first point with any non-zero energy value
  const firstNonZero = rawRecords.findIndex(r =>
    (r.solar || 0) > 0 || (r.load || 0) > 0 || 
    (r.gridImport || 0) > 0 || (r.gridExport || 0) > 0 ||
    (r.batteryCharge || 0) > 0 || (r.batteryDischarge || 0) > 0
  );

  // If no non-zero data found, return empty (nothing to graph)
  if (firstNonZero === -1) return [];

  // Return from first real data point onwards
  return rawRecords.slice(firstNonZero);
}

export default function Graphs() {
  const today = useMemo(() => new Date(), []);
  const [viewMode, setViewMode] = useState('daily');
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [chartData, setChartData] = useState([]);
  const [dailyScrapedTotals, setDailyScrapedTotals] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  // Active inverter selection (persisted across pages)
  const [selectedInverter, setSelectedInverter] = useState(() => {
    return localStorage.getItem('solar_selected_inverter') || 'all';
  });

  const handleInverterChange = (val) => {
    setSelectedInverter(val);
    localStorage.setItem('solar_selected_inverter', val);
  };

  // Active Metric Toggles
  const [activeMetrics, setActiveMetrics] = useState({
    solar: true,
    load: true,
    gridImport: true,
    gridExport: true,
    batteryCharge: true,
    batteryDischarge: true,
  });

  const toggleMetric = (id) => {
    setActiveMetrics(prev => ({ ...prev, [id]: !prev[id] }));
  };

  // Fetch real data from backend SQLite DB (for Daily Line Graph) or DESS Scraper (for Monthly/Yearly)
  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);

    const fetchData = async () => {
      const dateStr = format(selectedDate, 'yyyy-MM-dd');
      try {
        if (viewMode === 'daily') {
          const data = await fetchFromBackend(`/api/history?date=${dateStr}&inverter=${selectedInverter}`);
          if (isMounted) {
            const formatted = processDaily24hRecords(data.records);
            setChartData(formatted);
            
            // Fetch exact scraped daily totals for bottom pills
            try {
              const totalsData = await fetchFromBackend(`/api/dess_totals?month=${dateStr.substring(0, 7)}&inverter=${selectedInverter}`);
              let dayObj = null;
              if (Array.isArray(totalsData.totals)) {
                dayObj = totalsData.totals.find(item => item.time === dateStr);
              } else if (totalsData.totals && totalsData.totals.solar !== undefined) {
                dayObj = totalsData.totals;
              }
              if (isMounted && dayObj) {
                setDailyScrapedTotals(dayObj);
              }
            } catch (tErr) {
              // Fallback — no scraped totals for this day yet
            }
          }
        } else if (viewMode === 'monthly') {
          const monthStr = format(selectedDate, 'yyyy-MM');
          const data = await fetchFromBackend(`/api/dess_totals?month=${monthStr}&inverter=${selectedInverter}`);
          if (isMounted) {
            setChartData(data.totals || []);
          }
        } else if (viewMode === 'yearly') {
          const yearStr = format(selectedDate, 'yyyy');
          const data = await fetchFromBackend(`/api/dess_totals?year=${yearStr}&inverter=${selectedInverter}`);
          if (isMounted) {
            setChartData(data.totals || []);
          }
        }
      } catch (err) {
        console.warn('Failed to fetch graph data:', err.message);
      }
      if (isMounted) setIsLoading(false);
    };

    fetchData();
    // Refresh daily line graph every 60s to pull newly logged 1-min telemetry points
    const interval = setInterval(fetchData, viewMode === 'daily' ? 60000 : 300000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [viewMode, selectedDate, selectedInverter]);

  // Date Navigation Constraints
  const isNextDisabled = useMemo(() => {
    if (viewMode === 'daily') return isSameDay(selectedDate, today);
    if (viewMode === 'monthly') return isSameMonth(selectedDate, today);
    if (viewMode === 'yearly') return isSameYear(selectedDate, today);
    return false;
  }, [viewMode, selectedDate, today]);

  const handlePrevDate = () => {
    if (viewMode === 'daily') setSelectedDate(prev => subDays(prev, 1));
    else if (viewMode === 'monthly') setSelectedDate(prev => subMonths(prev, 1));
    else if (viewMode === 'yearly') setSelectedDate(prev => subYears(prev, 1));
  };

  const handleNextDate = () => {
    if (isNextDisabled) return;
    if (viewMode === 'daily') setSelectedDate(prev => addDays(prev, 1));
    else if (viewMode === 'monthly') setSelectedDate(prev => addMonths(prev, 1));
    else if (viewMode === 'yearly') setSelectedDate(prev => addYears(prev, 1));
  };

  const dateFormattedLabel = useMemo(() => {
    if (viewMode === 'daily') return format(selectedDate, 'EEEE, MMM d, yyyy');
    if (viewMode === 'monthly') return format(selectedDate, 'MMMM yyyy');
    if (viewMode === 'yearly') return format(selectedDate, 'yyyy');
  }, [viewMode, selectedDate]);

  const summaryTotals = useMemo(() => {
    if (viewMode === 'daily' && dailyScrapedTotals) {
      return dailyScrapedTotals;
    }

    const totals = { solar: 0, load: 0, gridImport: 0, gridExport: 0, batteryCharge: 0, batteryDischarge: 0 };
    if (!Array.isArray(chartData)) return totals;
    chartData.forEach(item => {
      totals.solar += (item.solar || 0);
      totals.load += (item.load || 0);
      totals.gridImport += (item.gridImport || 0);
      totals.gridExport += (item.gridExport || 0);
      totals.batteryCharge += (item.batteryCharge || 0);
      totals.batteryDischarge += (item.batteryDischarge || 0);
    });
    return totals;
  }, [chartData, viewMode, dailyScrapedTotals]);

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="graphs-tooltip">
          <p className="tooltip-header">{label}</p>
          {payload.map((item, idx) => {
            const config = METRICS_CONFIG.find(m => m.id === item.dataKey);
            if (!config) return null;
            return (
              <div key={idx} className="tooltip-row">
                <span className="tooltip-dot" style={{ backgroundColor: item.color }} />
                <span className="tooltip-lbl">{config.label}:</span>
                <span className="tooltip-val">{item.value} {viewMode === 'daily' ? 'kW' : 'kWh'}</span>
              </div>
            );
          })}
        </div>
      );
    }
    return null;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="graphs-page-container"
    >
      {/* Top Header & Timeframe Selector */}
      <div className="graphs-header-row">
        <div>
          <h2 className="page-title">Analytics & History</h2>
          <p className="page-subtitle">Real 1-Minute SQLite Power Curves & DESS Scraped Totals</p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          {/* Global Inverter Selector */}
          <InverterSelector 
            selectedInverter={selectedInverter} 
            onChange={handleInverterChange} 
          />

          {/* View Mode Selector (Daily / Monthly / Yearly) */}
          <div className="timeframe-pill-selector">
            <button 
              className={`timeframe-btn ${viewMode === 'daily' ? 'active' : ''}`}
              onClick={() => setViewMode('daily')}
            >
              Daily
            </button>
            <button 
              className={`timeframe-btn ${viewMode === 'monthly' ? 'active' : ''}`}
              onClick={() => setViewMode('monthly')}
            >
              Monthly
            </button>
            <button 
              className={`timeframe-btn ${viewMode === 'yearly' ? 'active' : ''}`}
              onClick={() => setViewMode('yearly')}
            >
              Yearly
            </button>
          </div>
        </div>
      </div>

      {/* Date Navigator Bar */}
      <div className="date-navigator-card glass-panel">
        <button className="nav-arrow-btn" onClick={handlePrevDate} title="Previous">
          <ChevronLeft size={20} />
        </button>

        <div className="date-display-box">
          <CalendarIcon size={18} className="calendar-icon" />
          <span className="date-label-text">{dateFormattedLabel}</span>
        </div>

        <button 
          className={`nav-arrow-btn ${isNextDisabled ? 'disabled' : ''}`} 
          onClick={handleNextDate} 
          disabled={isNextDisabled}
          title={isNextDisabled ? "Cannot navigate to future date" : "Next"}
        >
          <ChevronRight size={20} />
        </button>
      </div>

      {/* Metric Toggle Legend Buttons */}
      <div className="metric-toggles-bar">
        {METRICS_CONFIG.map(metric => {
          const isActive = activeMetrics[metric.id];
          const Icon = metric.icon;

          return (
            <button
              key={metric.id}
              className={`metric-toggle-chip ${isActive ? 'active' : 'inactive'}`}
              style={{
                '--chip-color': metric.color,
                borderColor: isActive ? metric.color : 'rgba(255,255,255,0.08)',
                background: isActive ? `${metric.color}15` : 'rgba(255,255,255,0.02)',
              }}
              onClick={() => toggleMetric(metric.id)}
            >
              <Icon size={14} style={{ color: isActive ? metric.color : 'var(--text-secondary)' }} />
              <span style={{ color: isActive ? '#fff' : 'var(--text-secondary)' }}>{metric.label}</span>
              <div 
                className="chip-status-dot" 
                style={{ backgroundColor: isActive ? metric.color : 'rgba(255,255,255,0.2)' }} 
              />
            </button>
          );
        })}
      </div>

      {/* Main Interactive Recharts View */}
      <div className="chart-wrapper-card glass-panel">
        <div className="chart-header-info">
          <span className="chart-type-badge">
            {viewMode === 'daily' ? '1-Minute SQLite Power Curve (Line Chart)' : `${viewMode === 'monthly' ? 'Daily Energy Breakdown (Scraped)' : 'Monthly Totals (Scraped)'}`}
          </span>
        </div>

        <div className="chart-canvas-container">
          {chartData && chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              {viewMode === 'daily' ? (
                /* DAILY VIEW: SLEEK AREA / LINE CHART WITH 1440 UNIFORM MINUTE POINTS & 24 HOURLY TICKS */
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    {METRICS_CONFIG.map(m => (
                      <linearGradient key={m.id} id={`grad-${m.id}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={m.color} stopOpacity={0.35}/>
                        <stop offset="95%" stopColor={m.color} stopOpacity={0}/>
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis 
                    dataKey="time" 
                    ticks={computeHourlyTicks(chartData)}
                    stroke="var(--text-secondary)" 
                    fontSize={11} 
                    tickLine={false} 
                    axisLine={false}
                    interval="preserveStartEnd"
                  />
                  <YAxis 
                    stroke="var(--text-secondary)" 
                    fontSize={11} 
                    tickLine={false} 
                    axisLine={false} 
                    unit=" kW"
                    domain={[0, (dataMax) => (dataMax <= 0 ? 1 : Math.ceil(dataMax * 1.15))]}
                  />
                  <Tooltip content={<CustomTooltip />} />

                  {METRICS_CONFIG.map(m => (
                    activeMetrics[m.id] && (
                      <Area 
                        key={m.id}
                        type="monotone" 
                        dataKey={m.id} 
                        name={m.label}
                        stroke={m.color} 
                        strokeWidth={2.5} 
                        fillOpacity={1} 
                        fill={`url(#grad-${m.id})`}
                        connectNulls={true}
                        isAnimationActive={false}
                      />
                    )
                  ))}
                </AreaChart>
              ) : (
                /* MONTHLY & YEARLY VIEWS: BAR CHART */
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="time" stroke="var(--text-secondary)" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis 
                    stroke="var(--text-secondary)" 
                    fontSize={11} 
                    tickLine={false} 
                    axisLine={false} 
                    unit=" kWh"
                    domain={[0, (dataMax) => (dataMax <= 0 ? 10 : Math.ceil(dataMax * 1.15))]}
                  />
                  <Tooltip content={<CustomTooltip />} />

                  {METRICS_CONFIG.map(m => (
                    activeMetrics[m.id] && (
                      <Bar 
                        key={m.id}
                        dataKey={m.id} 
                        name={m.label}
                        fill={m.color} 
                        radius={[4, 4, 0, 0]} 
                        maxBarSize={16}
                      />
                    )
                  ))}
                </BarChart>
              )}
            </ResponsiveContainer>
          ) : (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: 'var(--text-secondary)',
              gap: '8px'
            }}>
              <CalendarIcon size={32} style={{ opacity: 0.4 }} />
              <p style={{ margin: 0, fontSize: '0.95rem' }}>
                {isLoading ? 'Loading telemetry data...' : `No logged data recorded for ${dateFormattedLabel}`}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Summary Totals Grid Card */}
      <div className="totals-summary-grid">
        {METRICS_CONFIG.map(metric => {
          const val = summaryTotals[metric.id] || 0;
          const Icon = metric.icon;

          return (
            <div key={metric.id} className="total-stat-card glass-panel">
              <div className="total-card-header">
                <div className="total-icon-box" style={{ background: `${metric.color}18`, color: metric.color }}>
                  <Icon size={18} />
                </div>
                <span className="total-lbl">{metric.label}</span>
              </div>
              <div className="total-val" style={{ color: metric.color }}>
                {val > 1000 ? `${(val / 1000).toFixed(2)} MWh` : `${val.toFixed(1)} kWh`}
              </div>
            </div>
          );
        })}
      </div>

      {/* Physical mobile scroll spacer to clear bottom nav bar */}
      <div className="graphs-bottom-spacer" />
    </motion.div>
  );
}
