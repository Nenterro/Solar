import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Clock, 
  Plus, 
  Trash2, 
  Edit3, 
  Power, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  X, 
  ArrowUpRight, 
  BatteryCharging, 
  Zap, 
  ShieldAlert,
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Check
} from 'lucide-react';
import { fetchFromBackend } from '../utils/api';
import UnifiedGlassDropdown from '../components/UnifiedGlassDropdown';
import { useTelemetry } from '../context/TelemetryContext';
import './Automations.css';

const AVAILABLE_SETTING_TYPES = [
  { id: 'feed_to_grid', label: 'Solar Feed to Grid', icon: ArrowUpRight, type: 'select', options: [
    { label: 'Enable Export', cmd: 'PEd' },
    { label: 'Disable Export', cmd: 'PDd' }
  ]},
  { id: 'output_priority', label: 'Output Source Priority', icon: Power, type: 'select', options: [
    { label: 'USB', cmd: 'POP00' },
    { label: 'SUB', cmd: 'POP01' },
    { label: 'SBU', cmd: 'POP02' }
  ]},
  { id: 'charger_priority', label: 'Charging Source Priority', icon: BatteryCharging, type: 'select', options: [
    { label: 'CSO', cmd: 'PCP01' },
    { label: 'SNU', cmd: 'PCP02' },
    { label: 'OSO', cmd: 'PCP03' }
  ]},
  { id: 'turn_off_ac2', label: 'Turn Off AC2 Voltage', icon: Zap, type: 'number', prefix: 'PAC2OFF', defaultVal: '56.5', unit: 'V' },
  { id: 'turn_on_ac2', label: 'Turn On AC2 Voltage', icon: Zap, type: 'number', prefix: 'PAC2ON', defaultVal: '57.0', unit: 'V' },
  { id: 'back_to_grid', label: 'Back to Grid Voltage', icon: ShieldAlert, type: 'number', prefix: 'PBCV', defaultVal: '52.0', unit: 'V' },
  { id: 'back_to_discharge', label: 'Back to Discharge Voltage', icon: ShieldAlert, type: 'number', prefix: 'PBDV', defaultVal: '54.0', unit: 'V' },
  { id: 'cut_off_v', label: 'Low Battery Cut-Off Voltage', icon: ShieldAlert, type: 'number', prefix: 'PSDV', defaultVal: '46.0', unit: 'V' },
];

// Helper: Convert 24h string "18:30" to 12h formatted string "06:30 PM"
function format12hTime(time24) {
  if (!time24) return '12:00 AM';
  const parts = time24.split(':');
  let h = parseInt(parts[0], 10);
  const m = parts[1] || '00';
  const period = h >= 12 ? 'PM' : 'AM';
  h = h % 12;
  if (h === 0) h = 12;
  return `${h.toString().padStart(2, '0')}:${m} ${period}`;
}

// Helper: Convert 12h parts (h: 1-12, m: 0-59, period: 'AM'/'PM') to 24h string "18:30"
function convertTo24h(h12, m, period) {
  let h = parseInt(h12, 10);
  if (period === 'PM' && h < 12) h += 12;
  if (period === 'AM' && h === 12) h = 0;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

// Custom Pop-Up Wheel Time Picker Field Component
function PopupTimePickerField({ value, onChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef(null);

  // Parse initial 24h value
  const parseVal = (val24) => {
    if (!val24) return { hour: 8, minute: 0, period: 'AM' };
    const parts = val24.split(':');
    let h = parseInt(parts[0], 10);
    const m = parseInt(parts[1] || '0', 10);
    const period = h >= 12 ? 'PM' : 'AM';
    h = h % 12;
    if (h === 0) h = 12;
    return { hour: h, minute: m, period };
  };

  const [state, setState] = useState(() => parseVal(value));

  useEffect(() => {
    setState(parseVal(value));
  }, [value]);

  // Close popup when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('touchstart', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, [isOpen]);

  const updateState = (newH, newM, newPeriod) => {
    setState({ hour: newH, minute: newM, period: newPeriod });
    const val24 = convertTo24h(newH, newM, newPeriod);
    onChange(val24);
  };

  const handleHourStep = (delta) => {
    let nextH = state.hour + delta;
    if (nextH > 12) nextH = 1;
    if (nextH < 1) nextH = 12;
    updateState(nextH, state.minute, state.period);
  };

  const handleMinuteStep = (delta) => {
    let nextM = state.minute + delta;
    if (nextM >= 60) nextM = 0;
    if (nextM < 0) nextM = 55;
    updateState(state.hour, nextM, state.period);
  };

  const togglePeriod = () => {
    const nextPeriod = state.period === 'AM' ? 'PM' : 'AM';
    updateState(state.hour, state.minute, nextPeriod);
  };

  return (
    <div className="popup-time-picker-wrapper" ref={containerRef}>
      <button 
        type="button"
        className={`embedded-field-box ${isOpen ? 'active-open' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
        style={{ cursor: 'pointer' }}
      >
        <span className="embedded-field-label">Execution Time</span>
        <div className="dropdown-trigger-body">
          <Clock size={14} className="select-prefix-icon" />
          <span className="dropdown-selected-label">{format12hTime(value)}</span>
        </div>
        <ChevronDown size={14} className={`dropdown-chevron-icon ${isOpen ? 'rotate' : ''}`} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div 
            className="time-picker-popup glass-panel"
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
            transition={{ duration: 0.2 }}
          >
            <div className="picker-main-display">
              <div className="time-column">
                <button type="button" className="step-btn" onClick={() => handleHourStep(1)}>
                  <ChevronUp size={18} />
                </button>
                <div className="time-digit-box">
                  <span>{state.hour.toString().padStart(2, '0')}</span>
                </div>
                <button type="button" className="step-btn" onClick={() => handleHourStep(-1)}>
                  <ChevronDown size={18} />
                </button>
                <span className="column-label">Hour</span>
              </div>

              <div className="time-colon">:</div>

              <div className="time-column">
                <button type="button" className="step-btn" onClick={() => handleMinuteStep(5)}>
                  <ChevronUp size={18} />
                </button>
                <div className="time-digit-box">
                  <span>{state.minute.toString().padStart(2, '0')}</span>
                </div>
                <button type="button" className="step-btn" onClick={() => handleMinuteStep(-1)}>
                  <ChevronDown size={18} />
                </button>
                <span className="column-label">Minute</span>
              </div>

              <div className="time-column period-column">
                <button 
                  type="button" 
                  className={`period-toggle-btn ${state.period === 'AM' ? 'active-am' : 'active-pm'}`}
                  onClick={togglePeriod}
                >
                  <span>{state.period}</span>
                </button>
                <span className="column-label">Period</span>
              </div>
            </div>

            <button type="button" className="popup-set-btn" onClick={() => setIsOpen(false)}>
              <Check size={16} />
              <span>Set Time</span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function Automations() {
  const { telemetry } = useTelemetry() || { telemetry: {} };
  const [automations, setAutomations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [toast, setToast] = useState(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formName, setFormName] = useState('');
  const [formTime, setFormTime] = useState('08:00');
  const [formInverter, setFormInverter] = useState('all');
  const [formActions, setFormActions] = useState([]);
  const [activeActionIndex, setActiveActionIndex] = useState(0);

  const [touchStart, setTouchStart] = useState(0);
  const [touchEnd, setTouchEnd] = useState(0);

  const handleTouchStart = (e) => setTouchStart(e.targetTouches[0].clientX);
  const handleTouchMove = (e) => setTouchEnd(e.targetTouches[0].clientX);
  const handleTouchEnd = () => {
    if (!touchStart || !touchEnd) return;
    const distance = touchStart - touchEnd;
    if (distance > 50 && activeActionIndex < formActions.length - 1) {
      setActiveActionIndex(prev => prev + 1);
    }
    if (distance < -50 && activeActionIndex > 0) {
      setActiveActionIndex(prev => prev - 1);
    }
    setTouchStart(0);
    setTouchEnd(0);
  };

  const [headerSlot, setHeaderSlot] = useState(null);
  useEffect(() => {
    setHeaderSlot(document.getElementById('mobile-header-slot'));
  }, []);

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const loadAutomations = async () => {
    setIsLoading(true);
    try {
      const res = await fetchFromBackend('/api/automations');
      if (res && res.automations) {
        setAutomations(res.automations);
      }
    } catch (err) {
      showToast('Error loading automations', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAutomations();
  }, []);

  const handleToggle = async (autoId) => {
    try {
      const res = await fetchFromBackend(`/api/automations/${autoId}/toggle`, { method: 'POST' });
      if (res && res.success) {
        setAutomations(prev => prev.map(a => a.id === autoId ? { ...a, enabled: res.enabled } : a));
        showToast(`Automation ${res.enabled ? 'enabled' : 'disabled'}`, 'success');
      }
    } catch (err) {
      showToast('Failed to toggle automation', 'error');
    }
  };

  const handleDelete = async (autoId) => {
    if (!window.confirm('Are you sure you want to delete this scheduled automation?')) return;
    try {
      const res = await fetchFromBackend(`/api/automations/${autoId}`, { method: 'DELETE' });
      if (res && res.success) {
        setAutomations(prev => prev.filter(a => a.id !== autoId));
        showToast('Automation deleted', 'success');
      }
    } catch (err) {
      showToast('Failed to delete automation', 'error');
    }
  };

  const openCreateModal = () => {
    setEditingId(null);
    setFormName('');
    setFormTime('08:00');
    setFormInverter('all');
    setFormActions([
      { setting_id: 'feed_to_grid', label: 'Solar Feed to Grid', command: 'PEd', value_display: 'Enable Export' }
    ]);
    setActiveActionIndex(0);
    setIsModalOpen(true);
  };

  const openEditModal = (auto) => {
    setEditingId(auto.id);
    setFormName(auto.name);
    setFormTime(auto.time_of_day);
    setFormInverter(auto.inverter_id);
    setFormActions(auto.actions || []);
    setActiveActionIndex(0);
    setIsModalOpen(true);
  };

  const handleAddAction = () => {
    const firstType = AVAILABLE_SETTING_TYPES[0];
    setFormActions(prev => {
      const updated = [
        ...prev,
        {
          setting_id: firstType.id,
          label: firstType.label,
          command: firstType.options[0].cmd,
          value_display: firstType.options[0].label
        }
      ];
      setActiveActionIndex(updated.length - 1);
      return updated;
    });
  };

  const handleRemoveAction = (index) => {
    setFormActions(prev => {
      const updated = prev.filter((_, i) => i !== index);
      if (activeActionIndex >= updated.length) {
        setActiveActionIndex(Math.max(0, updated.length - 1));
      }
      return updated;
    });
  };

  const handleActionTypeChange = (index, settingId) => {
    const st = AVAILABLE_SETTING_TYPES.find(s => s.id === settingId);
    if (!st) return;

    let cmd = '';
    let valDisp = '';

    if (st.type === 'select') {
      cmd = st.options[0].cmd;
      valDisp = st.options[0].label;
    } else {
      cmd = `${st.prefix}${st.defaultVal}`;
      valDisp = `${st.defaultVal} ${st.unit}`;
    }

    setFormActions(prev => prev.map((act, i) => i === index ? {
      setting_id: st.id,
      label: st.label,
      command: cmd,
      value_display: valDisp,
      num_value: st.defaultVal
    } : act));
  };

  const handleActionValueChange = (index, val) => {
    setFormActions(prev => prev.map((act, i) => {
      if (i !== index) return act;
      const st = AVAILABLE_SETTING_TYPES.find(s => s.id === act.setting_id);
      if (!st) return act;

      if (st.type === 'select') {
        const opt = st.options.find(o => o.cmd === val);
        return {
          ...act,
          command: val,
          value_display: opt ? opt.label : val
        };
      } else {
        const num = parseFloat(val) || 0;
        return {
          ...act,
          command: `${st.prefix}${num}`,
          value_display: `${num} ${st.unit}`,
          num_value: num
        };
      }
    }));
  };

  const handleSaveAutomation = async () => {
    if (!formName.trim()) {
      showToast('Please enter an automation title', 'error');
      return;
    }
    if (!formActions.length) {
      showToast('Please add at least one setting action', 'error');
      return;
    }

    const payload = {
      id: editingId,
      name: formName.trim(),
      time_of_day: formTime,
      inverter_id: formInverter,
      enabled: true,
      actions: formActions
    };

    try {
      const res = await fetchFromBackend('/api/automations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res && res.success) {
        showToast(`Automation ${editingId ? 'updated' : 'created'} successfully`, 'success');
        setIsModalOpen(false);
        loadAutomations();
      } else {
        showToast(res.error || 'Failed to save automation', 'error');
      }
    } catch (err) {
      showToast('Error saving automation', 'error');
    }
  };

  return (
    <div className="automations-container page-container">
      <AnimatePresence>
        {toast && (
          <motion.div 
            className={`toast-notification ${toast.type}`}
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
          >
            {toast.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            <span>{toast.msg}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Mobile Top Header Portal Slot */}
      {headerSlot && createPortal(
        <button type="button" className="add-automation-btn mini-btn" onClick={openCreateModal}>
          <Plus size={14} />
          <span>Add</span>
        </button>,
        headerSlot
      )}

      {/* Desktop Standard Top Header Bar */}
      <div className="page-header desktop-only">
        <div className="header-title-box">
          <Clock size={24} className="page-icon" />
          <div>
            <h2>Scheduled Automations</h2>
            <p className="subtitle">Automate inverter modes, grid exports, and power limits by time of day</p>
          </div>
        </div>
        <div className="header-controls">
          <button type="button" className="add-automation-btn" onClick={openCreateModal}>
            <Plus size={18} />
            <span>Create Automation</span>
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="automations-content">
        {isLoading ? (
          <div className="loading-state">
            <RefreshCw size={28} className="spin-icon" />
            <p>Loading scheduled automations...</p>
          </div>
        ) : automations.length === 0 ? (
          <div className="empty-state glass-panel">
            <Clock size={48} className="empty-icon" />
            <h3>No Scheduled Automations Yet</h3>
            <p>Set up automatic schedules to change inverter priorities or toggle grid export at specific times of day.</p>
            <button type="button" className="add-automation-btn" onClick={openCreateModal}>
              <Plus size={16} />
              <span>Create First Automation</span>
            </button>
          </div>
        ) : (
          <div className="automations-list">
            {automations.map((auto) => (
              <motion.div 
                key={auto.id} 
                className={`automation-card glass-panel ${!auto.enabled ? 'disabled' : ''}`}
                layout
              >
                {/* Left Section: Time Badge & Title */}
                <div className="card-left-section">
                  <div className="time-badge desktop-only">
                    <Clock size={16} />
                    <span>{format12hTime(auto.time_of_day)}</span>
                  </div>
                  <h3 className="auto-name">{auto.name}</h3>
                </div>

                {/* Actions Pills Section */}
                <div className="actions-pills-list">
                  {auto.actions?.map((act, i) => (
                    <div key={i} className="action-pill">
                      <span className="pill-label">{act.label}:</span>
                      <strong className="pill-value">{act.value_display || act.command}</strong>
                    </div>
                  ))}
                </div>

                {/* Right Section: Time (Mobile), Inverter Tag, Toggle, Edit, Delete */}
                <div className="card-right-section">
                  <div className="time-badge mobile-only">
                    <Clock size={14} />
                    <span>{format12hTime(auto.time_of_day)}</span>
                  </div>

                  <span className="inverter-tag">{auto.inverter_id.toUpperCase()}</span>
                  
                  {/* Toggle Switch */}
                  <button 
                    type="button"
                    className={`toggle-switch ${auto.enabled ? 'active' : ''}`}
                    onClick={() => handleToggle(auto.id)}
                    title={auto.enabled ? 'Disable Automation' : 'Enable Automation'}
                  >
                    <div className="switch-thumb" />
                  </button>

                  <button type="button" className="icon-action-btn" onClick={() => openEditModal(auto)} title="Edit">
                    <Edit3 size={16} />
                  </button>
                  <button type="button" className="icon-action-btn danger" onClick={() => handleDelete(auto.id)} title="Delete">
                    <Trash2 size={16} />
                  </button>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Create / Edit Automation Modal (Portalled to document.body) */}
      {isModalOpen && createPortal(
        <AnimatePresence>
          <div className="modal-overlay" key="automation-modal-overlay">
            <motion.div 
              className="automation-modal glass-panel"
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
            >
              <div className="modal-header">
                <h3>{editingId ? 'Edit Scheduled Automation' : 'Create Scheduled Automation'}</h3>
                <button type="button" className="close-btn" onClick={() => setIsModalOpen(false)}>
                  <X size={20} />
                </button>
              </div>

              <div className="modal-body">
                {/* Row 1: Title & Target Inverter Side-by-Side */}
                <div className="form-row">
                  <div className="form-group flex-1">
                    <div className="embedded-field-box">
                      <span className="embedded-field-label">Title</span>
                      <input 
                        type="text" 
                        className="embedded-field-input" 
                        placeholder="e.g. Evening Switch" 
                        value={formName} 
                        onChange={e => setFormName(e.target.value)} 
                      />
                    </div>
                  </div>

                  <div className="form-group flex-1">
                    <UnifiedGlassDropdown 
                      label="Target Inverter"
                      options={[
                        { value: 'all', label: 'All Inverters' },
                        { value: 'inv1', label: 'Inverter 1' },
                        { value: 'inv2', label: 'Inverter 2' },
                        { value: 'inv3', label: 'Inverter 3' },
                      ]}
                      value={formInverter}
                      onChange={setFormInverter}
                    />
                  </div>
                </div>

                {/* Row 2: Scheduled Execution Time */}
                <div className="form-group">
                  <PopupTimePickerField 
                    value={formTime} 
                    onChange={setFormTime} 
                  />
                </div>

                {/* Row 3: Configured Action Settings Carousel */}
                <div className="form-group">
                  <div 
                    className="splits-carousel-viewport"
                    onTouchStart={handleTouchStart}
                    onTouchMove={handleTouchMove}
                    onTouchEnd={handleTouchEnd}
                  >
                    <div 
                      className="splits-carousel-track"
                      style={{ transform: `translateX(-${activeActionIndex * 100}%)` }}
                    >
                      {formActions.map((act, idx) => {
                        const currentType = AVAILABLE_SETTING_TYPES.find(s => s.id === act.setting_id) || AVAILABLE_SETTING_TYPES[0];

                        return (
                          <div key={idx} className="split-card">
                            <div className="action-card-box">
                              <div className="action-card-header">
                                <span className="action-card-title">Setting {idx + 1} of {formActions.length}</span>
                                {formActions.length > 1 && (
                                  <button 
                                    type="button" 
                                    className="delete-action-btn"
                                    onClick={() => handleRemoveAction(idx)}
                                    title="Remove Setting"
                                  >
                                    <Trash2 size={16} />
                                  </button>
                                )}
                              </div>

                              <div className="form-row">
                                <div className="form-group flex-1">
                                  <UnifiedGlassDropdown 
                                    label="Type"
                                    options={AVAILABLE_SETTING_TYPES.map(st => ({ value: st.id, label: st.label, icon: st.icon }))}
                                    value={act.setting_id}
                                    onChange={val => handleActionTypeChange(idx, val)}
                                  />
                                </div>

                                <div className="form-group flex-1">
                                  {currentType.type === 'select' ? (
                                    <UnifiedGlassDropdown 
                                      label="Target Value"
                                      options={currentType.options.map(opt => ({ value: opt.cmd, label: opt.label }))}
                                      value={act.command}
                                      onChange={val => handleActionValueChange(idx, val)}
                                    />
                                  ) : (
                                    <div className="embedded-field-box">
                                      <span className="embedded-field-label">Target Value</span>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', width: '100%' }}>
                                        <input 
                                          type="number" 
                                          step="0.1" 
                                          className="embedded-field-input"
                                          value={act.num_value !== undefined ? act.num_value : currentType.defaultVal}
                                          onChange={e => handleActionValueChange(idx, e.target.value)}
                                        />
                                        <span className="num-unit">{currentType.unit}</span>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Horizontal Pagination Controls Bar */}
                  <div className="splits-pagination">
                    <button 
                      type="button" 
                      onClick={() => setActiveActionIndex(Math.max(0, activeActionIndex - 1))}
                      disabled={activeActionIndex === 0}
                      className="pagination-btn"
                    >
                      <ChevronLeft size={18} />
                    </button>
                    
                    <div className="splits-dots">
                      {formActions.map((_, i) => (
                        <div 
                          key={i} 
                          className={`split-dot ${i === activeActionIndex ? 'active' : ''}`} 
                          onClick={() => setActiveActionIndex(i)}
                        />
                      ))}
                    </div>

                    <button 
                      type="button" 
                      onClick={() => setActiveActionIndex(Math.min(formActions.length - 1, activeActionIndex + 1))}
                      disabled={activeActionIndex === formActions.length - 1}
                      className="pagination-btn"
                    >
                      <ChevronRight size={18} />
                    </button>

                    <button 
                      type="button" 
                      onClick={handleAddAction}
                      className="add-split-btn-pagination"
                    >
                      <Plus size={15} /> Add Setting
                    </button>
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="cancel-btn" onClick={() => setIsModalOpen(false)}>
                  Cancel
                </button>
                <button type="button" className="save-btn" onClick={handleSaveAutomation}>
                  <Check size={18} />
                  <span>{editingId ? 'Update Automation' : 'Save Automation'}</span>
                </button>
              </div>
            </motion.div>
          </div>
        </AnimatePresence>,
        document.body
      )}
    </div>
  );
}
