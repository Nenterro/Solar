import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { PiggyBank, TriangleAlert, CircleCheck } from 'lucide-react';
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine,
} from 'recharts';
import { fetchFromBackend } from '../utils/api';
import { SERIES } from '../utils/chartColors';
import './Forecast.css';

const SLOW = { timeout: 90000 };
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const STRATEGY = { peak_only: 'Peak hours only', all_night: 'All night' };
const STRAT_COLOR = { peak_only: SERIES.expected, all_night: SERIES.third };
const SCHEMES = { net_metering: 'Net metering (now)', net_billing: 'Net billing (future)' };

const rs = (v) => {
  if (v == null) return '-';
  const a = Math.abs(v);
  const s = a >= 1e6 ? `${(a / 1e6).toFixed(2)}M` : a >= 1e3 ? `${Math.round(a / 1e3)}k` : `${Math.round(a)}`;
  return `${v < 0 ? '-' : ''}Rs ${s}`;
};
const signedRs = (v) => (v == null ? '-' : `${v > 0 ? '+' : ''}${rs(v)}`);
const yrs = (v) => (v == null || !isFinite(v) ? '-' : `${v.toFixed(1)} yrs`);
const near = (a, b) => Math.abs(a - b) < 0.01;

// Payback against a battery's realistic life: green within 10 years, amber
// within its 10-15 year calendar life, red beyond.
const paybackTone = (y) => (y == null ? '' : y <= 10 ? 'good' : y <= 15 ? 'warn' : 'bad');
const netTone = (v) => (v == null ? '' : v > 0 ? 'good' : 'bad');

function buildRows(report) {
  const s = report.settings;
  const find = (strategy, cap) => report.results.find((r) => r.strategy === strategy && near(r.battery_kwh, cap));
  const basePacks = Math.round(s.current_battery_kwh / s.pack_kwh);
  const life = s.calendar_life_years;
  const rows = [];
  const add = (scheme, strategy, packs, prev) => {
    const cap = Math.round((s.current_battery_kwh + (packs - basePacks) * s.pack_kwh) * 100) / 100;
    const r = find(strategy, cap);
    if (!r) return null;
    const saving = r.saving_vs_none[`${scheme}_pkr`];
    const cost = packs * s.pack_price_pkr;
    const row = {
      scheme, strategy, packs, cap, import: r.import_kwh, saving, cost,
      payback: saving > 0 ? cost / saving : null,
      cycles: r.rated_cycles_per_year, cycleLife: r.cycle_life_years,
      net: saving * life - cost,
    };
    if (prev) {
      row.lastSaving = saving - prev.saving;
      row.lastPayback = row.lastSaving > 0 ? s.pack_price_pkr / row.lastSaving : null;
      row.lastNet = row.lastSaving * life - s.pack_price_pkr;
    }
    rows.push(row);
    return row;
  };
  add('net_metering', 'peak_only', basePacks, null);
  let prev = add('net_billing', 'all_night', basePacks, null);
  for (let n = basePacks + 1; n <= basePacks + s.max_extra_packs; n++) prev = add('net_billing', 'all_night', n, prev);
  return rows;
}

function Progress({ prog, report }) {
  const s = report.settings;
  const cur = report.results.find((r) => r.strategy === 'peak_only' && near(r.battery_kwh, s.current_battery_kwh));
  const simYear = cur?.saving_vs_none?.net_metering_pkr;
  // Where the year-round simulation says the bank should be by now, for comparison.
  const simSoFar = simYear != null ? (simYear * prog.days_elapsed) / 365 : null;
  const pct = (v) => Math.max(0, Math.min(100, (100 * v) / prog.cost_pkr));
  const gross = Math.max(prog.peak_saving_pkr, 1);
  const e = prog.energy;
  const roundTrip = e.charge_kwh ? Math.round((100 * (e.peak_discharge_kwh + e.offpeak_discharge_kwh)) / e.charge_kwh) : null;
  return (
    <section className="fc-card glass-panel">
      <div className="fc-card-head">
        <h3>Your {prog.packs} packs: payback so far</h3>
        <span className="fc-muted">Measured since {prog.since} ({prog.days_elapsed} days) · net metering</span>
      </div>

      <div className="pb-headline">
        <span className="pb-big" style={{ color: SERIES.actual }}>{rs(prog.saved_pkr)}</span>
        <span className="fc-muted">saved of {rs(prog.cost_pkr)} ({prog.progress_pct}%)</span>
      </div>
      <div className="pb-bar" role="img" aria-label={`${prog.progress_pct}% of the battery cost recovered`}>
        <div className="pb-fill" style={{ width: `${pct(prog.saved_pkr)}%`, background: SERIES.actual }} />
        {simSoFar != null && (
          <div className="pb-marker" style={{ left: `${pct(simSoFar)}%` }} title={`Simulation: ${rs(simSoFar)} expected by now`} />
        )}
      </div>
      <div className="pb-scale">
        <span>Rs 0</span>
        {simSoFar != null && <span className="fc-muted">marker: {rs(simSoFar)}, what the simulation expected by now</span>}
        <span>{rs(prog.cost_pkr)}</span>
      </div>

      <div className="pb-split">
        <div className="pb-row">
          <div className="pb-row-head">
            <span>Peak hours</span>
            <b className="tone-good">+{rs(prog.peak_saving_pkr)}</b>
          </div>
          <div className="pb-mini"><div style={{ width: '100%', background: SERIES.expected }} /></div>
          <div className="fc-muted">
            {e.peak_discharge_kwh.toLocaleString()} kWh from the battery in peak hours: grid imports at the peak rate avoided
          </div>
        </div>
        <div className="pb-row">
          <div className="pb-row-head">
            <span>Off-peak hours</span>
            <b className={prog.offpeak_saving_pkr < 0 ? 'tone-bad' : 'tone-good'}>
              {prog.offpeak_saving_pkr < 0 ? '' : '+'}{rs(prog.offpeak_saving_pkr)}
            </b>
          </div>
          <div className="pb-mini">
            <div style={{ width: `${Math.min(100, (100 * Math.abs(prog.offpeak_saving_pkr)) / gross)}%`, background: SERIES.third }} />
          </div>
          <div className="fc-muted">
            {e.charge_kwh.toLocaleString()} kWh of solar stored instead of exported (export credit given up),
            less {e.offpeak_discharge_kwh.toLocaleString()} kWh discharged off-peak
          </div>
        </div>
      </div>

      <div className="fc-table-wrap">
        <table className="fc-table">
          <thead>
            <tr>
              <th>Month</th><th>From battery, peak</th><th>Stored from solar</th><th>Peak saving</th>
              <th>Off-peak</th><th>Net saving</th><th>If net billing</th>
            </tr>
          </thead>
          <tbody>
            {prog.monthly.map((m) => (
              <tr key={m.month}>
                <td>{m.month}</td>
                <td>{m.peak_discharge_kwh} kWh</td>
                <td>{m.charge_kwh} kWh</td>
                <td>{rs(m.peak_saving_pkr)}</td>
                <td>{rs(m.offpeak_saving_pkr)}</td>
                <td><b>{rs(m.saving_pkr)}</b></td>
                <td className="fc-muted">{rs(m.net_billing_saving_pkr)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="fc-stats pb-proj">
        <div><span>At the rate so far</span><b>{rs(prog.per_year_at_recent_rate_pkr)} / yr</b></div>
        <div><span>Payback at that rate</span><b>{yrs(prog.payback_years_at_recent_rate)}</b></div>
        <div><span>Simulated full year</span><b>{rs(simYear)} / yr</b></div>
        <div><span>Payback, simulated</span><b>{yrs(simYear > 0 ? prog.cost_pkr / simYear : null)}</b></div>
        <div><span>Round trip, measured</span><b>{roundTrip != null ? `${roundTrip}%` : '-'}</b></div>
        <div><span>Same hours, net billing</span><b>{rs(prog.net_billing_saving_pkr)}</b></div>
      </div>
      <p className="fc-note">
        Each month is billed twice from the measured hours: as it happened, and with the battery's charge and discharge
        removed. Under net metering, stored solar is solar not exported, so charging costs the excess-export credit
        (Rs {s.net_metering_excess_rate}/unit). If your excess exports earn less, or roll forward as units, the battery is
        doing better than shown. So far this covers autumn; summer evenings are heavier, which the simulated full year includes.
      </p>
    </section>
  );
}

function CurveTooltip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="fc-tooltip">
      <div className="fc-tooltip-title">{label} kWh battery</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="fc-tooltip-row">
          <span className="fc-swatch" style={{ background: p.color }} />{p.name}
          <b>{unit === 'rs' ? rs(p.value) : `${Math.round(p.value).toLocaleString()} kWh`}</b>
        </div>
      ))}
    </div>
  );
}

function SettingsForm({ settings, onSaved }) {
  // Remounted (via key) whenever a new report arrives, so it starts from the saved values.
  const [form, setForm] = useState(settings);
  const [state, setState] = useState('');

  const num = (k, label, step = 'any', note) => (
    <label className="fc-field">
      <span>{label}</span>
      <input type="number" step={step} value={form[k] ?? ''} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
      {note && <small>{note}</small>}
    </label>
  );

  const save = async () => {
    setState('saving');
    const keys = ['peak_rate', 'offpeak_rate', 'net_billing_export_rate', 'net_metering_excess_rate',
      'pack_price_pkr', 'min_soc', 'calendar_life_years'];
    const body = Object.fromEntries(keys.map((k) => [k, Number(form[k])]));
    body.peak_start_by_month = Object.fromEntries(
      Object.entries(form.peak_start_by_month).map(([m, h]) => [m, Number(h)]));
    try {
      await fetchFromBackend('/api/forecast/battery/settings', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), timeout: 20000,
      });
      setState('saved');
      onSaved();
    } catch {
      setState('failed');
    }
  };

  return (
    <div>
      <div className="fc-fields">
        {num('peak_rate', 'Peak rate (Rs/unit)')}
        {num('offpeak_rate', 'Off-peak rate (Rs/unit)')}
        {num('net_billing_export_rate', 'Net-billing buy-back (Rs/unit)')}
        {num('net_metering_excess_rate', 'Net-metering excess credit (Rs/unit)')}
        {num('pack_price_pkr', 'Price per pack (Rs)', '1000')}
        {num('min_soc', 'Battery floor (0-1)', '0.01', 'Measured hand-over at 51.0 V: about 0.25')}
        {num('calendar_life_years', 'Battery life (years)', '1')}
      </div>
      <div className="fc-subhead">Peak window start hour by month (4 hours long)</div>
      <div className="fc-months">
        {MONTHS.map((m, i) => (
          <label key={m} className="fc-field small">
            <span>{m}</span>
            <input type="number" min="0" max="23" value={form.peak_start_by_month[String(i + 1)]}
              onChange={(e) => setForm({ ...form, peak_start_by_month: { ...form.peak_start_by_month, [String(i + 1)]: e.target.value } })} />
          </label>
        ))}
      </div>
      <div className="fc-actions">
        <button className="fc-btn" onClick={save} disabled={state === 'saving'}>
          {state === 'saving' ? 'Saving and re-running…' : 'Save and re-run'}
        </button>
        {state === 'saved' && <span className="tone-good"><CircleCheck size={14} /> Saved</span>}
        {state === 'failed' && (
          <span className="tone-bad"><TriangleAlert size={14} /> Not saved. Changing settings needs the API token
            set in this browser.</span>
        )}
      </div>
    </div>
  );
}

export default function Payback() {
  const [report, setReport] = useState(null);
  const [prog, setProg] = useState(null);
  // A late failure (a retry, or React's double effect in development) must not
  // hide a report that has already arrived.
  const loaded = useRef(false);
  const [error, setError] = useState(null);
  const [scheme, setScheme] = useState('net_billing');

  const load = useCallback(() => {
    fetchFromBackend('/api/forecast/battery', SLOW)
      .then((r) => { loaded.current = true; setReport(r); setError(null); })
      .catch(() => {
        if (!loaded.current) setError('Could not load the battery simulation. It takes a few seconds the first time.');
      });
    fetchFromBackend('/api/forecast/battery/progress', SLOW).then(setProg).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const rows = useMemo(() => (report ? buildRows(report) : []), [report]);

  const curve = useMemo(() => {
    if (!report) return [];
    const by = {};
    for (const r of report.results) {
      const k = r.battery_kwh;
      by[k] = by[k] || { kwh: k };
      by[k][`import_${r.strategy}`] = r.import_kwh;
      by[k][`net_metering_${r.strategy}`] = r.cost_net_metering_pkr;
      by[k][`net_billing_${r.strategy}`] = r.cost_net_billing_pkr;
    }
    return Object.values(by).sort((a, b) => a.kwh - b.kwh);
  }, [report]);

  const s = report?.settings;
  const cur = s && report.results.filter((r) => near(r.battery_kwh, s.current_battery_kwh));
  const curPeak = cur?.find((r) => r.strategy === 'peak_only');
  const curNight = cur?.find((r) => r.strategy === 'all_night');
  const monthly = curPeak && curNight ? MONTHS.map((m, i) => ({
    name: m,
    peak_only: curPeak.monthly[i].import_kwh,
    all_night: curNight.monthly[i].import_kwh,
    measured: report.load_months[String(i + 1)]?.measured,
  })) : [];

  const best = (sch) => cur && [...cur].sort((a, b) => a[`cost_${sch}_pkr`] - b[`cost_${sch}_pkr`])[0];
  const check = report?.simulator_check;

  return (
    <div className="fc-page">
      <div className="page-header desktop-only">
        <div className="header-title-box">
          <PiggyBank size={28} className="header-icon" />
          <div>
            <h2>Battery Payback</h2>
            <p className="subtitle">A year simulated hour by hour on your recorded load, for each battery size</p>
          </div>
        </div>
      </div>

      {error && <div className="fc-error glass-panel"><TriangleAlert size={18} /> {error}</div>}
      {!report && !error && <div className="fc-card glass-panel"><div className="fc-loading">Running the simulation…</div></div>}

      {report && (
        <>
          <div className="fc-tiles">
            <div className="fc-tile glass-panel">
              <div className="fc-tile-label">Your bank</div>
              <div className="fc-tile-value">{s.current_battery_kwh} kWh</div>
              <div className="fc-tile-sub">
                {Math.round(s.current_battery_kwh / s.pack_kwh)} packs · about {(s.current_battery_kwh * (1 - s.min_soc)).toFixed(0)} kWh usable above {Math.round(s.min_soc * 100)}%
              </div>
            </div>
            <div className="fc-tile glass-panel">
              <div className="fc-tile-label">Now: net metering</div>
              <div className="fc-tile-value" style={{ color: SERIES.actual }}>{STRATEGY[best('net_metering').strategy]}</div>
              <div className="fc-tile-sub">
                {best('net_metering').cost_net_metering_pkr < 0 ? 'credit of ' : 'bill of '}{rs(Math.abs(best('net_metering').cost_net_metering_pkr))} a year · peak import {curPeak.peak_import_kwh} kWh/yr
              </div>
            </div>
            <div className="fc-tile glass-panel">
              <div className="fc-tile-label">Under net billing</div>
              <div className="fc-tile-value" style={{ color: SERIES.actual }}>{STRATEGY[best('net_billing').strategy]}</div>
              <div className="fc-tile-sub">
                saves {rs(curPeak.cost_net_billing_pkr - curNight.cost_net_billing_pkr)} a year over peak-only, with the same packs
              </div>
            </div>
            <div className="fc-tile glass-panel">
              <div className="fc-tile-label">Simulator check</div>
              <div className="fc-tile-value">{check.simulated_with_overhead_kwh.toLocaleString()} kWh</div>
              <div className="fc-tile-sub">
                simulated grid import vs {check.actual_import_kwh.toLocaleString()} kWh measured, {check.days} days since {check.since}
              </div>
            </div>
          </div>

          {prog && <Progress prog={prog} report={report} />}

          <section className="fc-card glass-panel">
            <div className="fc-card-head">
              <h3>Packs: savings and payback</h3>
              <span className="fc-muted">
                Rs {Math.round(s.pack_price_pkr / 1000)}k per {s.pack_kwh} kWh pack · judged over a {s.calendar_life_years}-year life
              </span>
            </div>
            <div className="fc-table-wrap">
              <table className="fc-table fc-payback">
                <thead>
                  <tr>
                    <th>Billing</th><th>Packs (kWh)</th><th>Battery use</th><th>Grid import / yr</th>
                    <th>Saving / yr vs no battery</th><th>Total cost</th><th>Payback</th>
                    <th className="sep">Cycles / yr</th><th>Life at {s.rated_cycles.toLocaleString()} cycles</th>
                    <th>Net over {s.calendar_life_years} yrs</th>
                    <th className="sep">Last pack: saving / yr</th><th>Last pack: payback</th>
                    <th>Last pack: net over {s.calendar_life_years} yrs</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i} className={r.scheme === 'net_metering' ? 'nm' : ''}>
                      <td><b>{r.scheme === 'net_metering' ? 'Net metering' : 'Net billing'}</b></td>
                      <td>{r.packs} <span className="fc-muted">({(r.cap + 1e-9).toFixed(1)})</span></td>
                      <td>{STRATEGY[r.strategy]}</td>
                      <td>{r.import.toLocaleString()} kWh</td>
                      <td>{rs(r.saving)}</td>
                      <td>{rs(r.cost)}</td>
                      <td className={`cell-${paybackTone(r.payback)}`}><b>{yrs(r.payback)}</b></td>
                      <td className="sep">{r.cycles}</td>
                      <td>{r.cycleLife ? `${Math.round(r.cycleLife)} yrs` : '-'}</td>
                      <td className={`cell-${netTone(r.net)}`}><b>{signedRs(r.net)}</b></td>
                      <td className="sep">{r.lastSaving != null ? rs(r.lastSaving) : '-'}</td>
                      <td className={`cell-${paybackTone(r.lastPayback)}`}><b>{r.lastSaving != null ? yrs(r.lastPayback) : '-'}</b></td>
                      <td className={`cell-${netTone(r.lastNet)}`}><b>{r.lastSaving != null ? signedRs(r.lastNet) : '-'}</b></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="fc-legend">
              <span><i className="cell-good" /> Pays back within 10 years / gains money</span>
              <span><i className="cell-warn" /> Payback 10-15 years (a battery's typical life)</span>
              <span><i className="cell-bad" /> Payback over 15 years / loses money</span>
            </div>
            <p className="fc-note">
              Saving is per year against having no battery under the same billing. The "Last pack" columns show what the one
              added pack earns on its own, which decides whether buying it is worth it. Under net metering more packs save
              nothing: two already cover every peak window. Age, not cycling, ends these packs: even emptying them every
              night stays far under the rated cycles.
            </p>
          </section>

          <div className="fc-two">
            <section className="fc-card glass-panel">
              <div className="fc-card-head">
                <h3>Grid import by battery size</h3>
                <span className="fc-muted">kWh per year · line marks your bank</span>
              </div>
              <div className="fc-chart" style={{ height: 260 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={curve} margin={{ top: 10, right: 12, left: -4, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                    <XAxis dataKey="kwh" type="number" domain={[0, 'dataMax']} stroke="var(--text-secondary)" fontSize={11} tickLine={false} unit=" kWh" />
                    <YAxis stroke="var(--text-secondary)" fontSize={11} tickLine={false} axisLine={false} width={56} />
                    <Tooltip content={<CurveTooltip />} />
                    <Legend verticalAlign="top" height={28} iconType="plainline" wrapperStyle={{ fontSize: 12 }} />
                    <ReferenceLine x={s.current_battery_kwh} stroke="var(--text-muted)" strokeDasharray="4 4" />
                    {Object.keys(STRATEGY).map((k) => (
                      <Line key={k} dataKey={`import_${k}`} name={STRATEGY[k]} stroke={STRAT_COLOR[k]} strokeWidth={2}
                        dot={{ r: 3 }} isAnimationActive={false} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="fc-card glass-panel">
              <div className="fc-card-head">
                <h3>Yearly energy cost by size</h3>
                <div className="fc-seg">
                  {Object.entries(SCHEMES).map(([k, l]) => (
                    <button key={k} className={scheme === k ? 'active' : ''} onClick={() => setScheme(k)}>{l}</button>
                  ))}
                </div>
              </div>
              <div className="fc-chart" style={{ height: 260 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={curve} margin={{ top: 10, right: 12, left: 4, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                    <XAxis dataKey="kwh" type="number" domain={[0, 'dataMax']} stroke="var(--text-secondary)" fontSize={11} tickLine={false} unit=" kWh" />
                    <YAxis stroke="var(--text-secondary)" fontSize={11} tickLine={false} axisLine={false} width={64}
                      tickFormatter={(v) => rs(v)} />
                    <Tooltip content={<CurveTooltip unit="rs" />} />
                    <Legend verticalAlign="top" height={28} iconType="plainline" wrapperStyle={{ fontSize: 12 }} />
                    <ReferenceLine y={0} stroke="rgba(255,255,255,0.25)" />
                    <ReferenceLine x={s.current_battery_kwh} stroke="var(--text-muted)" strokeDasharray="4 4" />
                    {Object.keys(STRATEGY).map((k) => (
                      <Line key={k} dataKey={`${scheme}_${k}`} name={STRATEGY[k]} stroke={STRAT_COLOR[k]} strokeWidth={2}
                        dot={{ r: 3 }} isAnimationActive={false} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <p className="fc-note">Energy charges only, before fixed charges and taxes. Below zero is a credit.</p>
            </section>
          </div>

          <section className="fc-card glass-panel">
            <div className="fc-card-head">
              <h3>Grid import by month, your bank</h3>
              <span className="fc-muted">kWh · the two ways of using the same {s.current_battery_kwh} kWh</span>
            </div>
            <div className="fc-chart" style={{ height: 240 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={monthly} margin={{ top: 10, right: 8, left: -10, bottom: 0 }} barGap={2}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="name" stroke="var(--text-secondary)" fontSize={11} tickLine={false} />
                  <YAxis stroke="var(--text-secondary)" fontSize={11} tickLine={false} axisLine={false} width={50} />
                  <Tooltip cursor={{ fill: 'rgba(255,255,255,0.04)' }} contentStyle={{ background: '#1e1e28', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10 }}
                    formatter={(v, n) => [`${v.toLocaleString()} kWh`, n]} />
                  <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 12 }} />
                  {Object.keys(STRATEGY).map((k) => (
                    <Bar key={k} dataKey={k} name={STRATEGY[k]} fill={STRAT_COLOR[k]} radius={[4, 4, 0, 0]} maxBarSize={18} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="fc-months-note">
              {monthly.map((m, i) => (
                <span key={m.name} className={m.measured ? 'measured' : 'borrowed'}
                  title={m.measured ? 'Recorded load' : `Borrows ${MONTHS[report.load_months[String(i + 1)].uses - 1]}'s recorded load`}>
                  {m.name}{m.measured ? '' : ` ← ${MONTHS[report.load_months[String(i + 1)].uses - 1]}`}
                </span>
              ))}
            </div>
            <p className="fc-note">
              Load comes only from days the app has recorded. Months not yet recorded borrow their seasonal twin (shown with
              an arrow) until real data replaces them. Summer rests on {report.load_months['8']?.days} days of late August,
              so the summer bars, and the value of extra packs, are the least certain part of this page.
            </p>
          </section>

          <section className="fc-card glass-panel">
            <div className="fc-card-head">
              <h3>Tariffs and battery assumptions</h3>
              <span className="fc-muted">IESCO rates change; edit them here and the whole page re-runs</span>
            </div>
            <SettingsForm key={report.generated_at} settings={s} onSaved={load} />
          </section>
        </>
      )}
    </div>
  );
}
