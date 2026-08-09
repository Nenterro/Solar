import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import { 
  Sliders, 
  Cpu, 
  Zap, 
  BatteryCharging, 
  ArrowUpRight, 
  RefreshCw, 
  CheckCircle2, 
  AlertCircle, 
  Save, 
  Power,
  ShieldAlert,
  ChevronDown
} from 'lucide-react';
import InverterSelector from '../components/InverterSelector';
import { fetchFromBackend } from '../utils/api';
import UnifiedGlassDropdown from '../components/UnifiedGlassDropdown';
import { useTelemetry } from '../context/TelemetryContext';
import './InverterSettings.css';

function cleanLabel(str) {
  return str ? str.replace(/\s*\([^)]*\)/g, '').trim() : '';
}

export default function InverterSettings() {
  const { telemetry } = useTelemetry() || { telemetry: {} };
  const [selectedInverter, setSelectedInverter] = useState(() => {
    return localStorage.getItem('solar_selected_inverter') || 'inv3';
  });

  const handleInverterChange = (val) => {
    const target = val === 'all' ? 'inv3' : val;
    setSelectedInverter(target);
    localStorage.setItem('solar_selected_inverter', target);
  };

  const [settingsData, setSettingsData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [toast, setToast] = useState(null);

  // Portal target for mobile top bar
  const [headerSlot, setHeaderSlot] = useState(null);

  useEffect(() => {
    setHeaderSlot(document.getElementById('mobile-header-slot'));
  }, []);

  // Pull to Refresh Touch Gesture State
  const [pullDistance, setPullDistance] = useState(0);
  const [isPulling, setIsPulling] = useState(false);
  const touchStartY = useRef(0);

  const handleTouchStart = (e) => {
    if (window.scrollY === 0) {
      touchStartY.current = e.touches[0].clientY;
      setIsPulling(true);
    }
  };

  const handleTouchMove = (e) => {
    if (!isPulling || window.scrollY > 0) return;
    const touchY = e.touches[0].clientY;
    const diff = touchY - touchStartY.current;
    if (diff > 0) {
      setPullDistance(Math.min(diff * 0.5, 90));
    }
  };

  const handleTouchEnd = () => {
    if (pullDistance > 60 && !isLoading) {
      loadSettings();
    }
    setPullDistance(0);
    setIsPulling(false);
  };

  // Form State for Voltage Threshold Edits
  const [voltageForm, setVoltageForm] = useState({
    back_to_grid_voltage: 52.0,
    back_to_discharge_voltage: 54.0,
    battery_cut_off_voltage: 46.0,
    battery_voltage_turn_off_ac2: 56.5,
    battery_voltage_turn_on_ac2: 57.0,
  });

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  // Load inverter settings from backend
  const loadSettings = async () => {
    setIsLoading(true);
    try {
      const data = await fetchFromBackend(`/api/inverter_settings?inverter=${selectedInverter}&_t=${Date.now()}`);
      if (data && !data.error) {
        setSettingsData(data);
        if (data.voltage_thresholds) {
          setVoltageForm({
            back_to_grid_voltage: data.voltage_thresholds.back_to_grid_voltage?.value || 52.0,
            back_to_discharge_voltage: data.voltage_thresholds.back_to_discharge_voltage?.value || 54.0,
            battery_cut_off_voltage: data.voltage_thresholds.battery_cut_off_voltage?.value || 46.0,
            battery_voltage_turn_off_ac2: data.voltage_thresholds.battery_voltage_turn_off_ac2?.value || 56.5,
            battery_voltage_turn_on_ac2: data.voltage_thresholds.battery_voltage_turn_on_ac2?.value || 57.0,
          });
        }
      } else {
        showToast(data?.error || 'Failed to query inverter settings', 'error');
      }
    } catch (err) {
      showToast('Error connecting to inverter serial interface', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, [selectedInverter]);

  // Handle setting updates via backend POST API
  const handleUpdateCommand = async (command, label) => {
    setIsSaving(true);
    try {
      const res = await fetchFromBackend('/api/inverter_settings/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ inverter: selectedInverter, command })
      });

      if (res && res.success) {
        showToast(`Successfully updated ${label} (${command})!`, 'success');
        await loadSettings();
      } else {
        showToast(`Hardware rejected setting: ${res?.response || res?.detail || 'NAK'}`, 'error');
      }
    } catch (err) {
      showToast(`Error applying command: ${err.message}`, 'error');
    } finally {
      setIsSaving(false);
    }
  };

  const handleVoltageApply = (key, cmdPrefix, label) => {
    const val = parseFloat(voltageForm[key]);
    if (isNaN(val) || val <= 0) {
      showToast(`Invalid voltage value for ${label}`, 'error');
      return;
    }
    const formattedVal = val.toFixed(1);
    const cmd = `${cmdPrefix}${formattedVal}`;
    handleUpdateCommand(cmd, label);
  };

  // Render top bar InverterSelector into mobile header slot
  const mobileHeaderSelector = headerSlot ? createPortal(
    <InverterSelector 
      selectedInverter={selectedInverter === 'all' ? 'inv3' : selectedInverter}
      onChange={handleInverterChange}
    />,
    headerSlot
  ) : null;

  return (
    <motion.div 
      className="inverter-settings-container page-container"
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {/* Mobile Top Bar Inverter Selector Portal */}
      {mobileHeaderSelector}

      {/* Pull to Refresh Indicator */}
      {pullDistance > 0 && (
        <div className="pull-to-refresh-indicator" style={{ height: `${pullDistance}px`, opacity: pullDistance / 60 }}>
          <RefreshCw className={pullDistance > 60 ? 'spin' : ''} size={20} />
          <span>{pullDistance > 60 ? 'Release to refresh settings...' : 'Pull to refresh...'}</span>
        </div>
      )}

      {/* Desktop Header */}
      <div className="page-header glass-panel desktop-only">
        <div className="header-title-box">
          <Sliders className="header-icon" size={24} />
          <div>
            <h2>Inverter Parameters & Control</h2>
            <p className="subtitle">Real-time hardware registers, priority source, feed-to-grid, and AC2 voltage thresholds</p>
          </div>
        </div>

        <div className="header-controls">
          <InverterSelector 
            selectedInverter={selectedInverter === 'all' ? 'inv3' : selectedInverter}
            onChange={handleInverterChange}
          />
          <button 
            className="refresh-btn glass-btn" 
            onClick={loadSettings}
            disabled={isLoading}
            title="Re-query hardware parameters"
          >
            <RefreshCw size={16} className={isLoading ? 'spin' : ''} />
            <span>Reload</span>
          </button>
        </div>
      </div>

      {/* Toast Feedback Banner */}
      {toast && (
        <motion.div 
          className={`settings-toast glass-panel ${toast.type}`}
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          {toast.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <span>{toast.msg}</span>
        </motion.div>
      )}

      {isLoading ? (
        <div className="loading-container glass-panel">
          <RefreshCw className="spin" size={32} />
          <p>Querying live hardware registers via RS232...</p>
        </div>
      ) : settingsData ? (
        <div className="settings-layout-sections">
          
          {/* Row 1: Hardware Info & Solar Feed to Grid (2 Equal Cards) */}
          <div className="cards-row two-columns">
            
            {/* Card 1: Machine Mode & System Info */}
            <div className="settings-card glass-panel">
              <div className="card-header">
                <Cpu size={20} className="card-icon" />
                <h3>Hardware Information</h3>
              </div>
              <div className="info-list">
                <div className="info-item">
                  <span className="info-label">Active Inverter:</span>
                  <span className="info-value badge">{settingsData.inverter_id?.toUpperCase()}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Serial Port:</span>
                  <span className="info-value code">{settingsData.port}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Operating Mode:</span>
                  <span className="info-value highlight">{settingsData.machine_type}</span>
                </div>
              </div>
            </div>

            {/* Card 2: Solar Feed To Grid Control */}
            <div className="settings-card glass-panel">
              <div className="card-header">
                <ArrowUpRight size={20} className="card-icon export" />
                <h3>Solar Feed to Grid</h3>
              </div>
              <p className="card-desc">
                Controls if excess solar power is exported to the grid.
              </p>

              {/* Desktop Button Group View */}
              <div className="setting-control-row desktop-only">
                <div className="status-badge-box">
                  <span className={`status-pill ${settingsData.feed_to_grid?.enabled ? 'enabled' : 'disabled'}`}>
                    {settingsData.feed_to_grid?.label}
                  </span>
                </div>
                <div className="toggle-btn-group">
                  <button
                    className={`action-btn ${settingsData.feed_to_grid?.enabled ? 'active' : ''}`}
                    onClick={() => handleUpdateCommand(settingsData.feed_to_grid?.enable_cmd, 'Enable Feed-to-Grid')}
                    disabled={isSaving}
                  >
                    Enable Export
                  </button>
                  <button
                    className={`action-btn danger ${!settingsData.feed_to_grid?.enabled ? 'active' : ''}`}
                    onClick={() => handleUpdateCommand(settingsData.feed_to_grid?.disable_cmd, 'Disable Feed-to-Grid')}
                    disabled={isSaving}
                  >
                    Disable Export
                  </button>
                </div>
              </div>

              {/* Mobile Unified Glass Dropdown View */}
              <div className="mobile-only mobile-dropdown-container">
                <UnifiedGlassDropdown 
                  options={[
                    { value: 'PEd', label: 'Enable Export' },
                    { value: 'PDd', label: 'Disable Export' }
                  ]}
                  value={settingsData.feed_to_grid?.enabled ? 'PEd' : 'PDd'}
                  onChange={(cmd) => {
                    handleUpdateCommand(cmd, cmd === 'PEd' ? 'Enable Export' : 'Disable Export');
                  }}
                  disabled={isSaving}
                  icon={ArrowUpRight}
                />
              </div>
            </div>

          </div>

          {/* Row 2: Source Priority Controls */}
          <div className="cards-row two-columns">
            
            {/* Card 3: Output Source Priority */}
            <div className="settings-card glass-panel">
              <div className="card-header">
                <Power size={20} className="card-icon output" />
                <h3>Output Source Priority</h3>
              </div>
              <p className="card-desc">
                Sets output load power source priority.
              </p>

              {/* Desktop Button Group View */}
              <div className="desktop-only priority-container-desktop">
                <div className="current-badge">
                  Current Setting: <strong>{cleanLabel(settingsData.output_source_priority?.label)}</strong>
                </div>
                <div className="options-grid three-single-row">
                  {settingsData.output_source_priority?.options?.map(opt => (
                    <button
                      key={opt.code}
                      className={`option-btn tall-btn ${settingsData.output_source_priority?.code === opt.code ? 'selected' : ''}`}
                      onClick={() => handleUpdateCommand(opt.cmd, `Output Priority: ${cleanLabel(opt.label)}`)}
                      disabled={isSaving}
                    >
                      <span>{cleanLabel(opt.label)}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Mobile Unified Glass Dropdown View */}
              <div className="mobile-only mobile-dropdown-container">
                <UnifiedGlassDropdown 
                  options={settingsData.output_source_priority?.options?.map(o => ({ value: o.cmd, label: cleanLabel(o.label) })) || []}
                  value={settingsData.output_source_priority?.options?.find(o => o.code === settingsData.output_source_priority?.code)?.cmd || 'POP01'}
                  onChange={(cmd) => {
                    const opt = settingsData.output_source_priority?.options?.find(o => o.cmd === cmd);
                    handleUpdateCommand(cmd, `Output Priority: ${cleanLabel(opt?.label || cmd)}`);
                  }}
                  disabled={isSaving}
                  icon={Power}
                />
              </div>
            </div>

            {/* Card 4: Charging Source Priority */}
            <div className="settings-card glass-panel">
              <div className="card-header">
                <BatteryCharging size={20} className="card-icon charger" />
                <h3>Charging Source Priority</h3>
              </div>
              <p className="card-desc">
                Sets battery charging priority.
              </p>

              {/* Desktop Button Group View */}
              <div className="desktop-only priority-container-desktop">
                <div className="current-badge">
                  Current Setting: <strong>{cleanLabel(settingsData.charging_source_priority?.label)}</strong>
                </div>
                <div className="options-grid three-single-row">
                  {settingsData.charging_source_priority?.options?.map(opt => (
                    <button
                      key={opt.code}
                      className={`option-btn tall-btn ${settingsData.charging_source_priority?.code === opt.code ? 'selected' : ''}`}
                      onClick={() => handleUpdateCommand(opt.cmd, `Charger Priority: ${cleanLabel(opt.label)}`)}
                      disabled={isSaving}
                    >
                      <span>{cleanLabel(opt.label)}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Mobile Unified Glass Dropdown View */}
              <div className="mobile-only mobile-dropdown-container">
                <UnifiedGlassDropdown 
                  options={settingsData.charging_source_priority?.options?.map(o => ({ value: o.cmd, label: cleanLabel(o.label) })) || []}
                  value={settingsData.charging_source_priority?.options?.find(o => o.code === settingsData.charging_source_priority?.code)?.cmd || 'PCP01'}
                  onChange={(cmd) => {
                    const opt = settingsData.charging_source_priority?.options?.find(o => o.cmd === cmd);
                    handleUpdateCommand(cmd, `Charger Priority: ${cleanLabel(opt?.label || cmd)}`);
                  }}
                  disabled={isSaving}
                  icon={BatteryCharging}
                />
              </div>
            </div>

          </div>

          {/* Row 3: System Battery & Grid Thresholds (Full Width Card) */}
          <div className="settings-card glass-panel full-width">
            <div className="card-header">
              <ShieldAlert size={20} className="card-icon battery-v" />
              <h3>System Battery Voltage Thresholds</h3>
            </div>
            <p className="card-desc">
              System low battery cut-off and grid switchover limits.
            </p>

            <div className="voltage-thresholds-grid three-cols">
              <div className="voltage-input-card">
                <div className="vol-title-box">
                  <span className="vol-title">Back to Grid Voltage</span>
                  <span className="vol-sub">Switch from battery to utility</span>
                </div>
                <div className="vol-input-group">
                  <input
                    type="number"
                    step="0.1"
                    className="vol-input"
                    value={voltageForm.back_to_grid_voltage}
                    onChange={(e) => setVoltageForm({ ...voltageForm, back_to_grid_voltage: e.target.value })}
                  />
                  <span className="vol-unit">V</span>
                  <button 
                    className="apply-btn"
                    onClick={() => handleVoltageApply('back_to_grid_voltage', 'PBCV', 'Back to Grid Voltage')}
                    disabled={isSaving}
                  >
                    <Save size={14} />
                    <span>Set</span>
                  </button>
                </div>
              </div>

              <div className="voltage-input-card">
                <div className="vol-title-box">
                  <span className="vol-title">Back to Discharge Voltage</span>
                  <span className="vol-sub">Switch from utility to battery</span>
                </div>
                <div className="vol-input-group">
                  <input
                    type="number"
                    step="0.1"
                    className="vol-input"
                    value={voltageForm.back_to_discharge_voltage}
                    onChange={(e) => setVoltageForm({ ...voltageForm, back_to_discharge_voltage: e.target.value })}
                  />
                  <span className="vol-unit">V</span>
                  <button 
                    className="apply-btn"
                    onClick={() => handleVoltageApply('back_to_discharge_voltage', 'PBDV', 'Back to Discharge Voltage')}
                    disabled={isSaving}
                  >
                    <Save size={14} />
                    <span>Set</span>
                  </button>
                </div>
              </div>

              <div className="voltage-input-card">
                <div className="vol-title-box">
                  <span className="vol-title">Low Battery Cut-Off Voltage</span>
                  <span className="vol-sub">Emergency shutdown threshold</span>
                </div>
                <div className="vol-input-group">
                  <input
                    type="number"
                    step="0.1"
                    className="vol-input"
                    value={voltageForm.battery_cut_off_voltage}
                    onChange={(e) => setVoltageForm({ ...voltageForm, battery_cut_off_voltage: e.target.value })}
                  />
                  <span className="vol-unit">V</span>
                  <button 
                    className="apply-btn"
                    onClick={() => handleVoltageApply('battery_cut_off_voltage', 'PSDV', 'Battery Cut-Off Voltage')}
                    disabled={isSaving}
                  >
                    <Save size={14} />
                    <span>Set</span>
                  </button>
                </div>
              </div>

            </div>
          </div>

        </div>
      ) : (
        <div className="error-panel glass-panel">
          <AlertCircle size={32} />
          <p>Failed to retrieve inverter settings from backend</p>
          <button className="glass-btn" onClick={loadSettings}>Retry</button>
        </div>
      )}
    </motion.div>
  );
}
