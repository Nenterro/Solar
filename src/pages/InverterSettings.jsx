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
  });

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  // Load inverter settings from backend with automatic retry
  const loadSettings = async () => {
    setIsLoading(true);
    let success = false;

    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        const data = await fetchFromBackend(`/api/inverter_settings?inverter=${selectedInverter}&_t=${Date.now()}`);
        if (data && !data.error) {
          setSettingsData(data);
          if (data.voltage_thresholds) {
            setVoltageForm({
              back_to_grid_voltage: data.voltage_thresholds.back_to_grid_voltage?.value || 52.0,
              back_to_discharge_voltage: data.voltage_thresholds.back_to_discharge_voltage?.value || 54.0,
              battery_cut_off_voltage: data.voltage_thresholds.battery_cut_off_voltage?.value || 46.0,
            });
          }
          success = true;
          break;
        }
      } catch (err) {
        console.warn(`Attempt ${attempt} to fetch inverter settings failed:`, err);
      }
      if (attempt < 3) {
        await new Promise(r => setTimeout(r, 600));
      }
    }

    if (!success && !settingsData) {
      showToast('Error connecting to inverter serial interface', 'error');
    }
    setIsLoading(false);
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
        showToast(`Successfully updated ${label}`, 'success');
        loadSettings();
      } else {
        showToast(res?.detail || res?.error || `Failed to update ${label}`, 'error');
      }
    } catch (err) {
      showToast(`Error communicating with inverter: ${err.message}`, 'error');
    } finally {
      setIsSaving(false);
    }
  };

  // Handle Voltage Input Apply
  const handleVoltageApply = (key, cmdPrefix, label) => {
    const val = parseFloat(voltageForm[key]);
    if (isNaN(val) || val < 40.0 || val > 65.0) {
      showToast('Please enter a valid voltage between 40.0V and 65.0V', 'error');
      return;
    }
    const formattedVal = val.toFixed(1);
    const command = `${cmdPrefix}${formattedVal}`;
    handleUpdateCommand(command, `${label} (${formattedVal}V)`);
  };

  // Render top bar InverterSelector into mobile header slot
  const mobileHeaderSelector = headerSlot ? createPortal(
    <div className="mobile-header-inverter-selector">
      <UnifiedGlassDropdown 
        options={[
          { id: 'inv1', label: 'Inverter 1' },
          { id: 'inv2', label: 'Inverter 2' },
          { id: 'inv3', label: 'Inverter 3' }
        ]}
        value={selectedInverter === 'all' ? 'inv3' : selectedInverter}
        onChange={handleInverterChange}
        prefixIcon={Cpu}
        compact={true}
      />
    </div>,
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
            <p className="subtitle">Real-time hardware registers, priority source, feed-to-grid, and voltage thresholds</p>
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
                  <span className="info-value">{settingsData.machine_type}</span>
                </div>
              </div>
            </div>

            {/* Card 2: Solar Feed-to-Grid Control */}
            <div className="settings-card glass-panel">
              <div className="card-header">
                <ArrowUpRight size={20} className="card-icon" />
                <h3>Solar Feed-to-Grid</h3>
              </div>
              <p className="card-desc">Enable or disable excess solar energy export to the electrical grid</p>
              
              <div className="control-block">
                <div className="status-indicator">
                  <span className="status-label">Current Export Status:</span>
                  <span className={`status-pill ${settingsData.feed_to_grid?.enabled ? 'enabled' : 'disabled'}`}>
                    {settingsData.feed_to_grid?.label}
                  </span>
                </div>

                <div className="btn-toggle-group">
                  <button 
                    className={`toggle-btn ${settingsData.feed_to_grid?.enabled ? 'active' : ''}`}
                    onClick={() => handleUpdateCommand(settingsData.feed_to_grid?.enable_cmd, 'Solar Feed to Grid Export')}
                    disabled={isSaving || settingsData.feed_to_grid?.enabled}
                  >
                    Enable Export
                  </button>
                  <button 
                    className={`toggle-btn ${!settingsData.feed_to_grid?.enabled ? 'active-off' : ''}`}
                    onClick={() => handleUpdateCommand(settingsData.feed_to_grid?.disable_cmd, 'Disable Grid Export')}
                    disabled={isSaving || !settingsData.feed_to_grid?.enabled}
                  >
                    Disable Export
                  </button>
                </div>
              </div>
            </div>

          </div>

          {/* Row 2: Priorities (Output Source Priority & Charging Source Priority) */}
          <div className="cards-row two-columns">
            
            {/* Card 3: Output Source Priority */}
            <div className="settings-card glass-panel">
              <div className="card-header">
                <Zap size={20} className="card-icon" />
                <h3>Output Source Priority</h3>
              </div>
              <p className="card-desc">Configure load power sourcing order (USB / SUB / SBU)</p>

              <div className="priority-options">
                {settingsData.output_source_priority?.options?.map((opt) => {
                  const isSelected = settingsData.output_source_priority.code === opt.code;
                  return (
                    <div 
                      key={opt.code} 
                      className={`priority-item ${isSelected ? 'selected' : ''}`}
                      onClick={() => !isSelected && !isSaving && handleUpdateCommand(opt.cmd, `Output Source Priority to ${opt.label}`)}
                    >
                      <div className="radio-circle">{isSelected && <div className="inner-dot" />}</div>
                      <div className="opt-details">
                        <span className="opt-label">{opt.label}</span>
                        <span className="opt-sub">
                          {opt.label === 'USB' && 'Utility power first, solar/battery backup'}
                          {opt.label === 'SUB' && 'Solar first, Utility second, Battery backup'}
                          {opt.label === 'SBU' && 'Solar first, Battery second, Utility backup'}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Card 4: Charging Source Priority */}
            <div className="settings-card glass-panel">
              <div className="card-header">
                <BatteryCharging size={20} className="card-icon" />
                <h3>Charging Source Priority</h3>
              </div>
              <p className="card-desc">Configure battery charger power sources</p>

              <div className="priority-options">
                {settingsData.charging_source_priority?.options?.map((opt) => {
                  const isSelected = settingsData.charging_source_priority.code === opt.code;
                  return (
                    <div 
                      key={opt.code} 
                      className={`priority-item ${isSelected ? 'selected' : ''}`}
                      onClick={() => !isSelected && !isSaving && handleUpdateCommand(opt.cmd, `Charging Source Priority to ${opt.label}`)}
                    >
                      <div className="radio-circle">{isSelected && <div className="inner-dot" />}</div>
                      <div className="opt-details">
                        <span className="opt-label">{opt.label}</span>
                        <span className="opt-sub">
                          {opt.label === 'Solar First' && 'Solar charges battery first, utility if solar absent'}
                          {opt.label === 'Solar and Utility' && 'Solar & Utility charge battery simultaneously'}
                          {opt.label === 'Solar Only' && 'Solar charges battery exclusively, utility never charges'}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

          </div>

          {/* Row 3: Operating Voltage Thresholds */}
          <div className="cards-row full-width">
            <div className="settings-card glass-panel">
              <div className="card-header">
                <ShieldAlert size={20} className="card-icon" />
                <h3>Voltage Cut-off & Discharge Thresholds</h3>
              </div>
              <p className="card-desc">Set custom battery voltage transition levels</p>

              <div className="voltage-grid">
                
                <div className="voltage-input-card">
                  <div className="vol-title-box">
                    <span className="vol-title">Back to Grid Voltage</span>
                    <span className="vol-sub">Switch load from battery to utility</span>
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
