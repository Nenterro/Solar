import { useState, useEffect } from 'react';
import { Battery as BatteryIcon, Zap, Thermometer, Activity } from 'lucide-react';
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
            </div>
          </div>
        </div>

        {/* Real-time Metrics Grid */}
        <div className="metrics-grid">
          
          <div className="metric-card glass-panel">
            <div className="metric-icon" style={{ background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6' }}>
              <Activity size={24} />
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
              <Activity size={24} />
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
              <Zap size={24} />
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
              <Thermometer size={24} />
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
    </div>
  );
}
