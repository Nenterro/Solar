import { BatteryCharging, Zap, Trash2 } from 'lucide-react';
import { formatPower } from '../EnergyFlowDiagram';
import './DashboardWidgets.css';

export const WIDGET_TYPES = [
  { id: 'battery_telemetry', title: 'Battery Storage Telemetry', icon: BatteryCharging, defaultSize: 'half' },
  { id: 'grid_status', title: 'Grid & Load Shedding Status', icon: Zap, defaultSize: 'half' }
];

export default function DashboardWidgetCard({ widget, onRemove, batteryPower, batteryLevel, gridPower }) {
  const typeDef = WIDGET_TYPES.find(t => t.id === widget.type) || { title: 'Unknown Widget' };

  const renderWidget = () => {
    switch (widget.type) {
      case 'battery_telemetry':
        return <BatteryTelemetryWidget batteryPower={batteryPower} batteryLevel={batteryLevel} />;
      case 'grid_status':
        return <GridStatusWidget gridPower={gridPower} />;
      default:
        return <div style={{ color: 'var(--text-secondary)' }}>Widget not available</div>;
    }
  };

  return (
    <div className="widget-card-wrapper glass-panel">
      <div className="widget-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {typeDef.icon && <typeDef.icon size={18} className="widget-header-icon" />}
          <h3 className="widget-title">{typeDef.title}</h3>
        </div>
        <button className="widget-remove-btn" onClick={onRemove} title="Remove widget">
          <Trash2 size={16} />
        </button>
      </div>
      <div className="widget-body">
        {renderWidget()}
      </div>
    </div>
  );
}

/* WIDGET 1: BATTERY STORAGE TELEMETRY WITH GLOWING SOC BAR */
function BatteryTelemetryWidget({ batteryPower, batteryLevel }) {
  const isCharging = batteryPower > 0.02;
  const isDischarging = batteryPower < -0.02;

  return (
    <div className="widget-telemetry-container">
      {/* Top Banner with Integrated Glowing SOC Bar */}
      <div className="status-banner banner-purple">
        <div className="status-indicator" style={{ justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="status-glow-dot dot-purple" />
            <span className="status-main-lbl">
              {isCharging ? 'BATTERY CHARGING' : isDischarging ? 'BATTERY DISCHARGING' : 'BATTERY STANDBY'}
            </span>
          </div>
          <span style={{ fontSize: '0.9rem', fontWeight: '800', color: '#a855f7' }}>{batteryLevel}% SOC</span>
        </div>

        {/* Glowing SOC Progress Bar */}
        <div className="soc-progress-track">
          <div 
            className="soc-progress-fill" 
            style={{ width: `${batteryLevel}%` }}
          />
        </div>

        <span className="status-sub-lbl">
          {isCharging ? `Charging at +${formatPower(batteryPower)} from Solar` : isDischarging ? `Powering Household at ${formatPower(batteryPower)}` : 'Battery Fully Charged'}
        </span>
      </div>

      {/* 2x2 Telemetry Grid */}
      <div className="telemetry-stats-grid">
        <div className="t-stat-item">
          <span className="t-label">Power Flow</span>
          <span className="t-val" style={{ color: '#a855f7' }}>
            {isCharging ? `+${formatPower(batteryPower)}` : isDischarging ? `-${formatPower(batteryPower)}` : '0 W'}
          </span>
        </div>
        <div className="t-stat-item">
          <span className="t-label">Usable Energy</span>
          <span className="t-val" style={{ color: '#a855f7' }}>
            8.4 / 10.2 kWh
          </span>
        </div>
        <div className="t-stat-item">
          <span className="t-label">Cell Voltage</span>
          <span className="t-val">53.3 V</span>
        </div>
        <div className="t-stat-item">
          <span className="t-label">Battery Health</span>
          <span className="t-val" style={{ color: '#10b981' }}>100% (Healthy)</span>
        </div>
      </div>
    </div>
  );
}

/* WIDGET 2: GRID STATUS & LOAD SHEDDING WIDGET */
function GridStatusWidget({ gridPower }) {
  const isLoadShedding = false; // Default active grid
  const isExporting = gridPower < -0.02;
  const isImporting = gridPower > 0.02;

  return (
    <div className="widget-telemetry-container">
      {/* Top Banner - Identical height & padding to Battery Banner */}
      <div className={`status-banner ${isLoadShedding ? 'banner-outage' : 'banner-active'}`}>
        <div className="status-indicator">
          <span className={`status-glow-dot ${isLoadShedding ? 'dot-red' : 'dot-green'}`} />
          <span className="status-main-lbl">
            {isLoadShedding ? 'LOAD SHEDDING ACTIVE' : 'GRID ACTIVE (NORMAL)'}
          </span>
        </div>

        {/* Dummy spacer line so banner height matches Battery SOC bar banner height */}
        <div className="grid-status-spacer" />

        <span className="status-sub-lbl">
          {isLoadShedding 
            ? 'Grid Power Outage Detected' 
            : isExporting 
              ? 'Exporting Excess Solar Power to Grid' 
              : isImporting 
                ? 'Importing Utility Grid Power' 
                : 'Grid Standby'}
        </span>
      </div>

      {/* 2x2 Telemetry Grid */}
      <div className="telemetry-stats-grid">
        <div className="t-stat-item">
          <span className="t-label">Grid Flow</span>
          <span className="t-val" style={{ color: isExporting ? '#10b981' : isImporting ? '#ef4444' : '#94a3b8' }}>
            {isExporting ? `-${formatPower(gridPower)}` : isImporting ? `+${formatPower(gridPower)}` : '0 W'}
          </span>
        </div>
        <div className="t-stat-item">
          <span className="t-label">Line Voltage</span>
          <span className="t-val" style={{ color: isLoadShedding ? '#ef4444' : '#fff' }}>
            {isLoadShedding ? '0.0 V' : '223.5 V'}
          </span>
        </div>
        <div className="t-stat-item">
          <span className="t-label">AC Frequency</span>
          <span className="t-val">{isLoadShedding ? '0.0 Hz' : '50.0 Hz'}</span>
        </div>
        <div className="t-stat-item">
          <span className="t-label">Outage Status</span>
          <span className="t-val" style={{ color: isLoadShedding ? '#ef4444' : '#10b981' }}>
            {isLoadShedding ? 'Outage Active' : 'Healthy Grid'}
          </span>
        </div>
      </div>
    </div>
  );
}
