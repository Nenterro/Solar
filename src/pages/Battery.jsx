import { useState, useEffect } from 'react';
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
  const [selectedDate, setSelectedDate] = useState(new Date());
  const today = new Date();

  useEffect(() => {
    let isMounted = true;
    const fetchHistory = async () => {
      const dateStr = format(selectedDate, 'yyyy-MM-dd');
      try {
        const res = await fetchFromBackend(`/api/history?date=${dateStr}&inverter=all`);
        if (isMounted && res.records) {
          setHistoryData(res.records);
        }
      } catch (err) {
        console.error("Failed to fetch battery history", err);
      }
    };
    fetchHistory();
    const histInterval = setInterval(fetchHistory, 60000);
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
  let totalChargeKwh = 0;
  let totalDischargeKwh = 0;
  let timeOnBatteryMins = 0;

  historyData.forEach(record => {
    // record.battery_w or batteryPowerKw. db.py returns bat_kw or batteryPowerKw?
    // Wait, backend/db.py returns `bat_kw`. But the frontend history processor (like in Dashboard/Grid) might expect `batteryPowerKw`.
    // Actually, `fetchFromBackend('/api/history')` returns `bat_kw`. 
    const batKw = record.bat_kw || record.batteryPowerKw || 0;
    const isGridActive = record.grid_v > 90.0 || record.gridActive;
    
    if (batKw > 0) {
      totalChargeKwh += batKw / 60; // kW per minute -> kWh
    } else if (batKw < 0) {
      totalDischargeKwh += Math.abs(batKw) / 60;
    }

    if (!isGridActive) {
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
  const radius = 120;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (data.soc / 100) * circumference;
  
  // Color code based on SOC
  const getSocColor = () => {
    if (data.soc > 60) return '#10b981'; // Green
    if (data.soc > 20) return '#f59e0b'; // Yellow
    return '#ef4444'; // Red
  };

  return (
    <div className="battery-page">
      <div className="battery-header glass-panel">
        <div className="title-wrapper">
          <BatteryIcon size={32} style={{ color: getSocColor() }} />
          <div>
            <h1 className="page-title">Knox Powerwall</h1>
            <p className="subtitle">Direct BMS Telemetry</p>
          </div>
        </div>
        <div className={`status-badge ${data.status.includes('Error') ? 'error' : 'active'}`}>
          <div className="status-dot"></div>
          {data.status}
        </div>
      </div>

      <div className="battery-dashboard">
        
        {/* SOC Circular Widget */}
        <div className="soc-widget glass-panel">
          <h2 className="widget-title">State of Charge</h2>
          <div className="progress-ring-container">
            <svg
              className="progress-ring"
              width="300"
              height="300"
            >
              <circle
                className="progress-ring__circle-bg"
                strokeWidth="20"
                fill="transparent"
                r={radius}
                cx="150"
                cy="150"
              />
              <circle
                className="progress-ring__circle"
                strokeWidth="20"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                stroke={getSocColor()}
                fill="transparent"
                r={radius}
                cx="150"
                cy="150"
              />
            </svg>
            <div className="soc-text-container">
              <span className="soc-value">{data.soc}%</span>
              <span className="soc-label">{data.state}</span>
              <span className="soc-units">{((data.soc / 100) * 10.24).toFixed(2)} kWh</span>
            </div>
          </div>
        </div>

        {/* Real-time Metrics Grid */}
        <div className="metrics-grid">
          
          <div className="metric-card glass-panel">
            <div className="metric-icon" style={{ background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6' }}>
              <Activity size={48} />
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
              <Activity size={48} />
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
              <Zap size={48} />
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
              <Thermometer size={48} />
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
              <Zap size={36} />
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
