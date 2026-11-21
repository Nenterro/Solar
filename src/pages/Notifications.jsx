import { useEffect, useState } from 'react';
import { Bell, BellOff, Send } from 'lucide-react';
import { getApiToken, setApiToken } from '../utils/api';
import { pushSupport, pushStatus, enablePush, disablePush, savePushPrefs, sendTestPush } from '../utils/push';

// The thresholds the hub lets this app change, in the order shown.
const SETTINGS = [
  { id: 'lowSoc', label: 'Battery low warning', unit: '%', min: 5, max: 90, read: (v) => v?.[0] ?? 30, write: (n, v) => [n, Math.min(v?.[1] ?? 15, n - 1)] },
  { id: 'lowSoc', key: 'critical', label: 'Battery critical warning', unit: '%', min: 1, max: 80, read: (v) => v?.[1] ?? 15, write: (n, v) => [Math.max(v?.[0] ?? 30, n + 1), n] },
  { id: 'runtimeHours', label: 'Runtime warning under', unit: 'hours', min: 0.5, max: 24, step: 0.5 },
  { id: 'reservePct', label: 'Battery counted as empty at', unit: '%', min: 0, max: 50 },
  { id: 'heavyLoadKw', label: 'Heavy load on battery over', unit: 'kW', min: 0.5, max: 20, step: 0.5 },
  { id: 'quietStart', label: 'Quiet hours start', unit: ':00', min: 0, max: 23 },
  { id: 'quietEnd', label: 'Quiet hours end', unit: ':00', min: 0, max: 23 }
];

const row = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', padding: '14px 16px' };
const divider = { borderTop: '1px solid rgba(255,255,255,0.05)' };

export default function Notifications() {
  const [support, setSupport] = useState(pushSupport);
  const [token, setToken] = useState(getApiToken);
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const run = async (work, done = '') => {
    setBusy(true);
    setMessage('');
    try {
      const next = await work();
      if (next?.types) setStatus(next);
      setMessage(done);
    } catch (err) {
      setMessage(err.message || 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (support.supported && support.hasToken) run(pushStatus);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const on = Boolean(status?.subscribed) && support.permission !== 'denied';
  const saveToken = () => {
    setApiToken(token.trim());
    setSupport(pushSupport());
    if (token.trim()) run(pushStatus, 'Token saved.');
  };

  const blocker = !support.hasToken
    ? 'Enter the server token below first. It proves this device belongs to the house.'
    : support.needsInstall
      ? 'Add this app to your Home Screen first (Share, then Add to Home Screen). iPhone only allows notifications for Home Screen apps.'
      : !support.supported
        ? 'This browser does not support notifications.'
        : '';

  return (
    <div className="page-container" style={{ padding: '16px', boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '640px', margin: '0 auto' }}>
        <div className="page-header glass-panel">
          <div className="header-title-box">
            <Bell className="header-icon" size={24} />
            <div>
              <h2>Notifications</h2>
              <p className="subtitle">Grid, battery and automation alerts on this phone</p>
            </div>
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px', borderRadius: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ padding: '12px', borderRadius: '12px', background: on ? 'rgba(245,158,11,0.12)' : 'rgba(255,255,255,0.06)', color: on ? 'var(--accent-color, #f59e0b)' : 'var(--text-secondary)' }}>
              {on ? <Bell size={24} /> : <BellOff size={24} />}
            </div>
            <div style={{ flex: 1 }}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>{on ? 'On for this device' : 'Off for this device'}</h2>
              <div style={{ color: 'var(--text-secondary, #94a3b8)', fontSize: '14px', marginTop: '4px' }}>
                {blocker || 'Grid outages, battery warnings and automation results, sent to this phone.'}
              </div>
            </div>
          </div>
          {!blocker && (
            <div style={{ display: 'flex', gap: '10px', marginTop: '16px' }}>
              <button
                className="btn-primary"
                disabled={busy}
                style={{ flex: 1, padding: '12px', borderRadius: '12px', border: 'none', fontWeight: 600, cursor: 'pointer', background: on ? 'rgba(255,255,255,0.08)' : 'var(--accent-color, #f59e0b)', color: on ? 'white' : '#09090b' }}
                onClick={() => (on ? run(async () => { await disablePush(); return pushStatus(); }, 'Notifications turned off.') : run(enablePush, 'Notifications turned on.'))}
              >
                {on ? 'Turn off' : 'Turn on'}
              </button>
              {on && (
                <button
                  disabled={busy}
                  style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px 16px', borderRadius: '12px', border: 'none', cursor: 'pointer', background: 'rgba(255,255,255,0.08)', color: 'white' }}
                  onClick={() => run(sendTestPush, 'Test sent.')}
                >
                  <Send size={16} /> Send test
                </button>
              )}
            </div>
          )}
          {message && <div style={{ marginTop: '12px', fontSize: '14px', color: 'var(--text-secondary, #94a3b8)' }}>{message}</div>}
        </div>

        <div className="glass-panel" style={{ padding: '16px', borderRadius: '16px' }}>
          <div style={{ fontSize: '14px', color: 'var(--text-secondary, #94a3b8)', marginBottom: '8px' }}>
            Server token (SOLAR_API_TOKEN on the home server). Also used when this device changes inverter settings.
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Paste the token"
              autoComplete="off"
              style={{ flex: 1, minWidth: 0, padding: '10px 12px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)', color: 'white', fontSize: '16px' }}
            />
            <button
              disabled={busy || token.trim() === getApiToken()}
              onClick={saveToken}
              style={{ padding: '10px 16px', borderRadius: '10px', border: 'none', cursor: 'pointer', background: 'rgba(255,255,255,0.08)', color: 'white' }}
            >
              Save
            </button>
          </div>
        </div>

        {on && status && (
          <>
            <div className="glass-panel" style={{ borderRadius: '16px', overflow: 'hidden' }}>
              {status.types.map((t, i) => (
                <label key={t.id} style={{ ...row, ...(i ? divider : {}), cursor: 'pointer' }}>
                  <span style={{ fontSize: '16px' }}>{t.label}</span>
                  <input
                    type="checkbox"
                    checked={t.on}
                    disabled={busy}
                    onChange={(e) => run(() => savePushPrefs({ types: { [t.id]: e.target.checked } }))}
                    style={{ width: '20px', height: '20px', accentColor: 'var(--accent-color, #f59e0b)' }}
                  />
                </label>
              ))}
            </div>

            <div className="glass-panel" style={{ borderRadius: '16px', overflow: 'hidden' }}>
              {SETTINGS.map((s, i) => {
                const stored = status.settings[s.id];
                const current = s.read ? s.read(stored) : stored;
                return (
                  <div key={s.key || s.id} style={{ ...row, ...(i ? divider : {}) }}>
                    <span style={{ fontSize: '16px' }}>{s.label}</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary, #94a3b8)', fontSize: '14px' }}>
                      <input
                        type="number"
                        inputMode="decimal"
                        min={s.min}
                        max={s.max}
                        step={s.step || 1}
                        defaultValue={current}
                        key={`${s.key || s.id}-${current}`}
                        disabled={busy}
                        onBlur={(e) => {
                          const value = Number(e.target.value);
                          if (!Number.isFinite(value) || value < s.min || value > s.max || value === current) {
                            e.target.value = current;
                            return;
                          }
                          run(() => savePushPrefs({ settings: { [s.id]: s.write ? s.write(value, stored) : value } }));
                        }}
                        style={{ width: '64px', padding: '8px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)', color: 'white', textAlign: 'right', fontSize: '16px' }}
                      />
                      {s.unit}
                    </span>
                  </div>
                );
              })}
            </div>
            <p style={{ color: 'var(--text-secondary, #94a3b8)', fontSize: '13px', margin: '0 12px' }}>
              During quiet hours, notifications wait and arrive together once they end. The switches are for this device; the numbers apply to everyone in the house.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
