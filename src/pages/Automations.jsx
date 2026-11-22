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
  Check,
  Sunset,
  LifeBuoy,
  XCircle
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
    { label: 'Solar First', cmd: 'PCP01' },
    { label: 'Solar and Utility', cmd: 'PCP02' },
    { label: 'Solar Only', cmd: 'PCP03' }
  ]},
  { id: 'back_to_grid', label: 'Back to Grid Voltage', icon: ShieldAlert, type: 'number', prefix: 'PBCV', defaultVal: '52.0', unit: 'V' },
  { id: 'back_to_discharge', label: 'Back to Discharge Voltage', icon: ShieldAlert, type: 'number', prefix: 'PBDV', defaultVal: '54.0', unit: 'V' },
  { id: 'cut_off_v', label: 'Low Battery Cut-Off Voltage', icon: ShieldAlert, type: 'number', prefix: 'PSDV', defaultVal: '48.0', unit: 'V' },
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

// Automation times are "HH:MM", or relative to IESCO peak hours: "peak_start",
// "peak_end", optionally with a minute offset ("peak_start-5", "peak_end+10").
// The server resolves them against each day's window, so they follow the
// seasonal changes on their own.
const PEAK_RE = /^(peak_start|peak_end)(?:([+-])(\d{1,3}))?$/;

function parseScheduleTime(t) {
  const m = PEAK_RE.exec(t || '');
  if (!m) return { mode: 'fixed', offset: 0 };
  return { mode: m[1], offset: (m[2] === '-' ? -1 : 1) * Number(m[3] || 0) };
}

function buildScheduleTime(mode, offset, fixed) {
  if (mode === 'fixed') return fixed;
  const o = Math.round(Number(offset) || 0);
  return o === 0 ? mode : `${mode}${o > 0 ? '+' : '-'}${Math.abs(o)}`;
}

function resolvePeakTime(t, peak) {
  const { mode, offset } = parseScheduleTime(t);
  if (mode === 'fixed') return t;
  if (!peak?.today) return null;
  const base = mode === 'peak_start' ? peak.today.start : peak.today.end;
  const [h, m] = base.split(':').map(Number);
  const total = Math.max(0, Math.min(23 * 60 + 59, h * 60 + m + offset));
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

function scheduleLabel(t, peak) {
  const { mode, offset } = parseScheduleTime(t);
  if (mode === 'fixed') return format12hTime(t);
  const name = mode === 'peak_start' ? 'Peak start' : 'Peak end';
  const off = offset ? ` ${offset > 0 ? '+' : '-'}${Math.abs(offset)}m` : '';
  const at = resolvePeakTime(t, peak);
  return `${name}${off}${at ? ` · ${format12hTime(at)}` : ''}`;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function PeakHoursCard({ peak, onSaved, showToast }) {
  const [editing, setEditing] = useState(false);
  const [table, setTable] = useState(null);
  const [length, setLength] = useState(4);
  if (!peak) return null;

  const startEdit = () => {
    setTable({ ...peak.peak_start_by_month });
    setLength(peak.peak_hours);
    setEditing(true);
  };
  const save = async () => {
    try {
      await fetchFromBackend('/api/peak_hours', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          peak_start_by_month: Object.fromEntries(Object.entries(table).map(([k, v]) => [k, Number(v)])),
          peak_hours: Number(length),
        }),
      });
      setEditing(false);
      onSaved();
      showToast('Peak hours saved', 'success');
    } catch {
      showToast('Could not save peak hours (needs the API token in this browser)', 'error');
    }
  };

  return (
    <div className="ctrl-card glass-panel">
      <div className="ctrl-card-head">
        <div className="ctrl-title"><Sunset size={18} /> <span>Peak hours</span></div>
        {peak.today.peak_now && <span className="ctrl-badge live">Peak now</span>}
      </div>
      <div className="ctrl-big">{format12hTime(peak.today.start)} – {format12hTime(peak.today.end)}</div>
      <p className="ctrl-sub">
        Today's IESCO peak window. Automations set to <b>Peak start</b> or <b>Peak end</b> follow it as it changes through the year.
      </p>
      {!editing ? (
        <>
          <div className="peak-months">
            {MONTHS.map((m, i) => {
              const st = peak.peak_start_by_month[String(i + 1)];
              return (
                <span key={m} className={i === new Date().getMonth() ? 'current' : ''}>
                  {m} {st}–{(st + peak.peak_hours) % 24}
                </span>
              );
            })}
          </div>
          <button type="button" className="ctrl-link" onClick={startEdit}>Edit peak hours</button>
        </>
      ) : (
        <>
          <div className="peak-edit">
            {MONTHS.map((m, i) => (
              <label key={m}>
                <span>{m}</span>
                <input type="number" min="0" max="23" value={table[String(i + 1)]}
                  onChange={(e) => setTable({ ...table, [String(i + 1)]: e.target.value })} />
              </label>
            ))}
            <label>
              <span>Hours</span>
              <input type="number" min="1" max="8" value={length} onChange={(e) => setLength(e.target.value)} />
            </label>
          </div>
          <p className="ctrl-sub">Start hour (0–23) for each month, and the window's length.</p>
          <div className="ctrl-actions">
            <button type="button" className="cancel-btn" onClick={() => setEditing(false)}>Cancel</button>
            <button type="button" className="save-btn" onClick={save}><Check size={16} /><span>Save</span></button>
          </div>
        </>
      )}
    </div>
  );
}

const RESCUE_FIELDS = [
  { key: 'trigger_soc', label: 'Start at or below', unit: '%' },
  { key: 'target_soc', label: 'Stop at', unit: '%' },
  { key: 'max_hours', label: 'Longest rescue', unit: 'h' },
  { key: 'cooldown_hours', label: 'Cooldown', unit: 'h' },
  { key: 'max_forecast_error_pct', label: 'Max forecast error', unit: '%' },
  { key: 'decide_by_hour', label: 'Decide by (hour)', unit: ':00' },
];

function RescueCard({ rescue, onChanged, showToast }) {
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  if (!rescue) return null;
  const s = rescue.settings;
  const now = rescue.now || {};
  const st = rescue.state || {};
  const f = form || s;

  const post = async (url, body) => fetchFromBackend(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined, timeout: 60000,
  });

  const save = async (changes, msg) => {
    setBusy(true);
    try {
      await post('/api/rescue/settings', changes);
      setForm(null);
      onChanged();
      showToast(msg, 'success');
    } catch {
      showToast('Not saved: check the values, and that the API token is set in this browser', 'error');
    } finally {
      setBusy(false);
    }
  };

  const checkNow = async () => {
    setBusy(true);
    try {
      const ev = await post('/api/rescue/check');
      onChanged();
      showToast(`Checked: ${ev.reason}`, 'success');
    } catch {
      showToast('Check failed (needs the API token in this browser)', 'error');
    } finally {
      setBusy(false);
    }
  };

  const active = !!st.active;
  return (
    <div className={`ctrl-card glass-panel ${active ? 'rescue-active' : ''}`}>
      <div className="ctrl-card-head">
        <div className="ctrl-title"><LifeBuoy size={18} /> <span>Battery rescue</span></div>
        <button type="button" className={`toggle-switch ${s.enabled ? 'active' : ''}`} disabled={busy}
          onClick={() => save({ enabled: !s.enabled }, s.enabled ? 'Battery rescue turned off' : 'Battery rescue turned on')}
          title={s.enabled ? 'Turn off' : 'Turn on'}>
          <div className="switch-thumb" />
        </button>
      </div>

      <div className="ctrl-big">
        {active ? 'Charging from grid' : s.enabled ? 'Watching' : 'Off'}
        {now.soc != null && <span className="ctrl-soc"> · battery {Math.round(now.soc)}%</span>}
      </div>
      <p className="ctrl-sub">
        After a deep discharge, switches every inverter to <b>Solar and Utility</b> so the grid tops the battery up
        to the stop level, then puts the previous charging setting back. It waits for the sun instead if even the
        low end of the forecast covers that same refill (to the stop level, not a full battery), and while the
        forecast is less certain than the max error it waits for the day to firm it up, deciding by the set hour.
      </p>
      {active && st.since && (
        <p className="ctrl-sub">Started {st.since.slice(11, 16)} at {Math.round(st.start_soc)}% · {now.reason}</p>
      )}
      {!active && st.last_event && <p className="ctrl-sub">Last rescue: {st.last_event}</p>}

      {!active && now.checks && (
        <ul className="rescue-checks">
          {now.checks.map((c) => (
            <li key={c.check} className={c.ok ? 'ok' : 'no'}>
              {c.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />} {c.check}
            </li>
          ))}
        </ul>
      )}

      <div className="rescue-fields">
        {RESCUE_FIELDS.map((fd) => (
          <label key={fd.key}>
            <span>{fd.label}</span>
            <div><input type="number" value={f[fd.key]} onChange={(e) => setForm({ ...f, [fd.key]: e.target.value })} /> {fd.unit}</div>
          </label>
        ))}
      </div>
      <label className="rescue-check-opt">
        <input type="checkbox" checked={!!f.use_forecast} onChange={(e) => setForm({ ...f, use_forecast: e.target.checked })} />
        Wait for the sun if the forecast says it will refill the battery
      </label>
      <label className="rescue-check-opt">
        <input type="checkbox" checked={!!f.allow_during_peak} onChange={(e) => setForm({ ...f, allow_during_peak: e.target.checked })} />
        Allow grid charging during peak hours
      </label>

      <div className="ctrl-actions">
        <button type="button" className="cancel-btn" onClick={checkNow} disabled={busy}>Check now</button>
        {form && (
          <button type="button" className="save-btn" disabled={busy}
            onClick={() => save({
              trigger_soc: Number(form.trigger_soc), target_soc: Number(form.target_soc),
              max_hours: Number(form.max_hours), cooldown_hours: Number(form.cooldown_hours),
              max_forecast_error_pct: Number(form.max_forecast_error_pct), decide_by_hour: Number(form.decide_by_hour),
              use_forecast: !!form.use_forecast, allow_during_peak: !!form.allow_during_peak,
            }, 'Rescue settings saved')}>
            <Check size={16} /><span>Save settings</span>
          </button>
        )}
      </div>
    </div>
  );
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
  const [formMode, setFormMode] = useState('fixed');
  const [formOffset, setFormOffset] = useState(0);
  const [peak, setPeak] = useState(null);
  const [rescue, setRescue] = useState(null);
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

  const loadControls = async () => {
    fetchFromBackend('/api/peak_hours').then(setPeak).catch(() => {});
    fetchFromBackend('/api/rescue', { timeout: 30000 }).then(setRescue).catch(() => {});
  };

  useEffect(() => {
    loadAutomations();
    loadControls();
    const t = setInterval(loadControls, 60000);
    return () => clearInterval(t);
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
    setFormMode('fixed');
    setFormOffset(0);
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
    const sched = parseScheduleTime(auto.time_of_day);
    setFormMode(sched.mode);
    setFormOffset(sched.offset);
    setFormTime(sched.mode === 'fixed' ? auto.time_of_day : '18:00');
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
          // The server accepts exactly one decimal place (PSDV48.0, not PSDV48).
          command: `${st.prefix}${num.toFixed(1)}`,
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
      time_of_day: buildScheduleTime(formMode, formOffset, formTime),
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

      <div className="ctrl-cards">
        <PeakHoursCard peak={peak} onSaved={loadControls} showToast={showToast} />
        <RescueCard rescue={rescue} onChanged={loadControls} showToast={showToast} />
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
            {[...automations]
              // In the order they run today (peak-relative times resolved).
              .sort((a, b) => (resolvePeakTime(a.time_of_day, peak) || '99').localeCompare(resolvePeakTime(b.time_of_day, peak) || '99'))
              .map((auto) => (
              <motion.div 
                key={auto.id} 
                className={`automation-card glass-panel ${!auto.enabled ? 'disabled' : ''}`}
                layout
              >
                {/* Left Section: Time Badge & Title */}
                <div className="card-left-section">
                  <div className="time-badge desktop-only">
                    <Clock size={16} />
                    <span>{scheduleLabel(auto.time_of_day, peak)}</span>
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
                    <span>{scheduleLabel(auto.time_of_day, peak)}</span>
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

                {/* Row 2: When it runs: a fixed time, or relative to the peak window */}
                <div className="form-row">
                  <div className="form-group flex-1">
                    <UnifiedGlassDropdown
                      label="Runs At"
                      options={[
                        { value: 'fixed', label: 'Fixed time' },
                        { value: 'peak_start', label: 'Peak start' },
                        { value: 'peak_end', label: 'Peak end' },
                      ]}
                      value={formMode}
                      onChange={setFormMode}
                    />
                  </div>
                  <div className="form-group flex-1">
                    {formMode === 'fixed' ? (
                      <PopupTimePickerField value={formTime} onChange={setFormTime} />
                    ) : (
                      <div className="embedded-field-box">
                        <span className="embedded-field-label">Offset (minutes, - for before)</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', width: '100%' }}>
                          <input type="number" step="5" className="embedded-field-input" value={formOffset}
                            onChange={e => setFormOffset(e.target.value)} />
                          <span className="num-unit">min</span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
                {formMode !== 'fixed' && (
                  <p className="peak-hint">
                    Today this runs at {format12hTime(resolvePeakTime(buildScheduleTime(formMode, formOffset, formTime), peak) || '00:00')}.
                    It moves with the peak window through the year.
                  </p>
                )}

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
