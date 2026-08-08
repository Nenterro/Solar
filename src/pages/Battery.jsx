import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Battery as BatteryIcon, Zap, Thermometer, Activity, Calendar as CalendarIcon, ChevronLeft, ChevronRight, BatteryCharging, BatteryWarning } from 'lucide-react';
import { format, addDays, subDays, isSameDay } from 'date-fns';
import { fetchFromBackend } from '../utils/api';
import './Battery.css';

export default function Battery() {
  const [data, setData] = useState({
    soc: 0,
    voltage: 0.0,
    current: 0.0,
    power: 0.0,
    temperature: 0.0,
    state: "Loading...",
    status: "Connecting..."
  });
  const [historyData, setHistoryData] = useState([]);
  const [dailyScrapedTotals, setDailyScrapedTotals] = useState(null);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [headerSlot, setHeaderSlot] = useState(null);
  const today = new Date();

  useEffect(() => {
    setHeaderSlot(document.getElementById('mobile-header-slot'));
  }, []);

  useEffect(() => {
    let isMounted = true;
    const fetchHistoryAndTotals = async () => {
      const dateStr = format(selectedDate, 'yyyy-MM-dd');
      try {
        const [histRes, totalsRes] = await Promise.all([
          fetchFromBackend(`/api/history?date=${dateStr}&inverter=all&_t=${Date.now()}`),
          fetchFromBackend(`/api/dess_totals?month=${dateStr.substring(0, 7)}&inverter=all`)
        ]);
        
        if (isMounted) {
          if (histRes.records) setHistoryData(histRes.records);
          
          let dayObj = null;
          if (Array.isArray(totalsRes.totals)) {
            dayObj = totalsRes.totals.find(item => item.time === dateStr);
          } else if (totalsRes.totals && totalsRes.totals.solar !== undefined) {
            dayObj = totalsRes.totals;
          }
          setDailyScrapedTotals(dayObj);
        }
      } catch (err) {
        console.error("Failed to fetch battery history or totals", err);
      }
    };
    fetchHistoryAndTotals();
    const histInterval = setInterval(fetchHistoryAndTotals, 60000);
    return () => {
      isMounted = false;
      clearInterval(histInterval);
    };
  }, [selectedDate]);

  useEffect(() => {
    // Poll the new RS485 endpoint every 5 seconds
    const fetchBatteryData = async () => {
      try {
        const json = await fetchFromBackend('/api/battery');
        setData(json);
      } catch (err) {
        console.error("Failed to fetch battery data", err);
      }
    };
    
    fetchBatteryData();
    const interval = setInterval(fetchBatteryData, 5000);
    return () => clearInterval(interval);
  }, []);

  // Date Navigation
  const isNextDisabled = isSameDay(selectedDate, today);
  const handlePrevDate = () => setSelectedDate(prev => subDays(prev, 1));
  const handleNextDate = () => {
    if (!isNextDisabled) setSelectedDate(prev => addDays(prev, 1));
  };
  const dateFormattedLabel = format(selectedDate, 'EEEE, MMM d, yyyy');

  // Calculate History Metrics
  const totalChargeKwh = dailyScrapedTotals ? (dailyScrapedTotals.batteryCharge || 0) : 0;
  const totalDischargeKwh = dailyScrapedTotals ? (dailyScrapedTotals.batteryDischarge || 0) : 0;
  let timeOnBatteryMins = 0;

  historyData.forEach(record => {
    const solarKw = (record.solar_w || 0) / 1000.0;
    const gridKw = (record.grid_w || 0) / 1000.0;
    const batKw = (record.battery_w || 0) / 1000.0;
    
    // Battery net power is negative when discharging. 
    // The user's definition of "time on battery":
    // Solar is 0 (<= 0.02 to handle floating noise), Grid Import is 0 (<= 0.02), Battery is discharging (< -0.02)
    if (solarKw <= 0.02 && gridKw <= 0.02 && batKw < -0.02) {
      timeOnBatteryMins++;
    }
  });

  const formatDuration = (mins) => {
    if (mins === 0) return "0h 0m";
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${h}h ${m}m`;
  };

  // Calculate circular progress dash array
  const radius = 72;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (data.soc / 100) * circumference;
  
  // Color code based on SOC
  const getSocColor = () => {
    if (data.soc > 60) return '#10b981'; // Green
    if (data.soc > 20) return '#f59e0b'; // Yellow
    return '#ef4444'; // Red
  };

  const isError = data.status.includes('Error');

  return (
    <div className="battery-page">
      <div className="page-header glass-panel desktop-only">
        <div className="header-title-box">
          <BatteryIcon className="header-icon" size={24} style={{ color: getSocColor() }} />
          <div>
            <h2>Knox Powerwall</h2>
            <p className="subtitle">Direct BMS Telemetry & Voltage Limits</p>
          </div>
        </div>
      </div>

      <div className="battery-dashboard">
        
        {/* SOC Circular Widget */}
        <div className="soc-widget glass-panel">
          <h2 className="widget-title desktop-only">State of Charge</h2>
          <div className="soc-content">
            
            {/* Desktop Circular Ring */}
            <div className="progress-ring-container desktop-only">
              <svg
                className="progress-ring"
                width="180"
                height="180"
              >
                <circle
                  className="progress-ring__circle-bg"
                  strokeWidth="12"
                  fill="transparent"
                  r={radius}
                  cx="90"
                  cy="90"
                />
                <circle
                  className="progress-ring__circle"
                  strokeWidth="12"
                  strokeDasharray={circumference}
                  strokeDashoffset={strokeDashoffset}
                  strokeLinecap="round"
                  stroke={getSocColor()}
                  fill="transparent"
                  r={radius}
                  cx="90"
                  cy="90"
                />
              </svg>
              <div className="soc-text-container">
                <span className="soc-value">{data.soc}%</span>
              </div>
            </div>

            {/* Mobile Horizontal Pill */}
            <div className="mobile-only soc-horizontal-wrapper">
              <div className="soc-header-mobile">
                <span className="soc-mobile-title">State of Charge</span>
                <span className="soc-mobile-value" style={{ color: getSocColor() }}>{data.soc}%</span>
              </div>
              <div className="soc-progress-track">
                <div 
                  className="soc-progress-fill" 
                  style={{ width: `${data.soc}%`, backgroundColor: getSocColor() }}
                ></div>
              </div>
              <div className="soc-footer-mobile">
                <span>{data.state}</span>
                <span>{((data.soc / 100) * 10.24).toFixed(2)} kWh Avail</span>
              </div>
            </div>

            <div className="soc-details desktop-only">
              <div className="detail-item">
                <span className="detail-label">Status</span>
                <span className="detail-value" style={{ color: getSocColor() }}>
                  {data.state}
                </span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Available Energy</span>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                  <span className="detail-value">
                    {((data.soc / 100) * 10.24).toFixed(2)}
                  </span>
                  <span className="detail-unit">kWh</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Real-time Metrics Grid */}
        <div className="metrics-grid">
          
          <div className="metric-card glass-panel">
            <div className="metric-icon" style={{ background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6' }}>
              <Activity size={28} />
            </div>
            <div className="metric-info">
              <span className="metric-label">Voltage</span>
              <div className="metric-value">
                {data.voltage.toFixed(1)} <span className="unit">V</span>
              </div>
            </div>
          </div>

          <div className="metric-card glass-panel">
            <div className="metric-icon" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>
              <Activity size={28} />
            </div>
            <div className="metric-info">
              <span className="metric-label">Current</span>
              <div className="metric-value">
                {data.current.toFixed(1)} <span className="unit">A</span>
              </div>
            </div>
          </div>

          <div className="metric-card glass-panel">
            <div className="metric-icon" style={{ background: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b' }}>
              <Zap size={28} />
            </div>
            <div className="metric-info">
              <span className="metric-label">Power Flow</span>
              <div className="metric-value">
                {data.power.toFixed(0)} <span className="unit">W</span>
              </div>
            </div>
          </div>

          <div className="metric-card glass-panel">
            <div className="metric-icon" style={{ background: 'rgba(16, 185, 129, 0.1)', color: '#10b981' }}>
              <Thermometer size={28} />
            </div>
            <div className="metric-info">
              <span className="metric-label">Temperature</span>
              <div className="metric-value">
                {data.temperature.toFixed(1)} <span className="unit">°C</span>
              </div>
            </div>
          </div>

        </div>
      </div>

      <div className="battery-history-section glass-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', marginBottom: '24px' }}>
          <h2 className="widget-title" style={{ margin: 0 }}>Daily Battery Analytics</h2>
          
          {/* Date Navigator */}
          <div className="date-navigator-card glass-panel" style={{ margin: 0, padding: '8px 16px', background: 'rgba(0,0,0,0.2)' }}>
            <button className="nav-arrow-btn" onClick={handlePrevDate} title="Previous">
              <ChevronLeft size={18} />
            </button>
            <div className="date-display-box" style={{ padding: '0 12px' }}>
              <CalendarIcon size={16} className="calendar-icon" />
              <span className="date-label-text" style={{ fontSize: '0.9rem' }}>{dateFormattedLabel}</span>
            </div>
            <button 
              className={`nav-arrow-btn ${isNextDisabled ? 'disabled' : ''}`} 
              onClick={handleNextDate} 
              disabled={isNextDisabled}
            >
              <ChevronRight size={18} />
            </button>
          </div>
        </div>

        <div className="analytics-grid">
          <div className="metric-card glass-panel">
            <div className="metric-icon" style={{ background: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b' }}>
              <BatteryWarning size={48} />
            </div>
            <div className="metric-info">
              <span className="metric-label">Time on Battery</span>
              <div className="metric-value">
                {formatDuration(timeOnBatteryMins)}
              </div>
            </div>
          </div>

          <div className="metric-card glass-panel">
            <div className="metric-icon" style={{ background: 'rgba(16, 185, 129, 0.1)', color: '#10b981' }}>
              <BatteryCharging size={48} />
            </div>
            <div className="metric-info">
              <span className="metric-label">Total Charge</span>
              <div className="metric-value">
                {totalChargeKwh.toFixed(2)} <span className="unit">kWh</span>
              </div>
            </div>
          </div>

          <div className="metric-card glass-panel">
            <div className="metric-icon" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>
              <Zap size={48} />
            </div>
            <div className="metric-info">
              <span className="metric-label">Total Discharge</span>
              <div className="metric-value">
                {totalDischargeKwh.toFixed(2)} <span className="unit">kWh</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
