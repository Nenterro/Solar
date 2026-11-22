import { useEffect, useMemo, useState } from 'react';
import { CloudSun, Satellite, TriangleAlert, CircleCheck, RefreshCw } from 'lucide-react';
import {
  ResponsiveContainer, ComposedChart, BarChart, Bar, Line, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ErrorBar, ReferenceArea, Legend,
} from 'recharts';
import { format, parseISO, subDays, addDays } from 'date-fns';
import { fetchFromBackend } from '../utils/api';
import { SERIES } from '../utils/chartColors';
import './Forecast.css';

// First day of the current array (DESSMonitor plant record). Days before the
// app's own first day are estimates: the model run on that day's sunlight.
const INSTALL_DATE = '2026-01-21';
const SLOW = { timeout: 60000 };

const SOURCE_LABEL = {
  sat: 'Satellite sunlight',
  ukmo: 'UK Met Office forecast',
  bm: 'Forecast model',
};

const VERDICT = {
  normal: { label: 'As expected', tone: 'good' },
  explained: { label: 'Explained shortfall', tone: 'warn' },
  under: { label: 'Below expected', tone: 'bad' },
  cloudier: { label: 'Cloudier than forecast', tone: 'info' },
  sunnier: { label: 'Sunnier than forecast', tone: 'info' },
  above: { label: 'Above expected', tone: 'info' },
};

const RANGES = [
  { id: '30', label: '30 days' },
  { id: '90', label: '90 days' },
  { id: 'install', label: 'Since install' },
];

const kwh = (v, d = 1) => (v == null ? '-' : `${Number(v).toFixed(d)} kWh`);
const fmtDay = (iso) => format(parseISO(iso), 'EEE d MMM');
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function Tile({ label, value, sub, accent }) {
  return (
    <div className="fc-tile glass-panel">
      <div className="fc-tile-label">{label}</div>
      <div className="fc-tile-value" style={accent ? { color: accent } : undefined}>{value}</div>
      {sub && <div className="fc-tile-sub">{sub}</div>}
    </div>
  );
}

function DayTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const v = d.verdict && VERDICT[d.verdict.status];
  return (
    <div className="fc-tooltip">
      <div className="fc-tooltip-title">{fmtDay(d.date)}</div>
      <div className="fc-tooltip-row"><span className="fc-swatch" style={{ background: SERIES.expected }} />Expected <b>{kwh(d.expected_kwh)}</b></div>
      <div className="fc-tooltip-muted">Likely range {kwh(d.low_kwh, 0)} to {kwh(d.high_kwh, 0)}</div>
      {d.actual_kwh != null && (
        <div className="fc-tooltip-row"><span className="fc-swatch" style={{ background: SERIES.actual }} />Actual <b>{kwh(d.actual_kwh)}</b></div>
      )}
      <div className="fc-tooltip-muted">{SOURCE_LABEL[d.sunlight_source]} · {d.sky} sky</div>
      {d.kind === 'estimated' && <div className="fc-tooltip-muted">Before the app: estimate only</div>}
      {v && <div className={`fc-tooltip-verdict tone-${v.tone}`}>{v.label}</div>}
      {d.verdict?.reasons?.map((r) => <div key={r} className="fc-tooltip-reason">{r}</div>)}
    </div>
  );
}

function YearTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const m = payload[0].payload;
  return (
    <div className="fc-tooltip">
      <div className="fc-tooltip-title">{MONTHS[m.month - 1]}</div>
      <div className="fc-tooltip-row"><span className="fc-swatch" style={{ background: SERIES.expected }} />Typical <b>{m.value.toLocaleString()} kWh</b></div>
      <div className="fc-tooltip-muted">Range across 2022-2025: {m.lo.toLocaleString()} to {m.hi.toLocaleString()} kWh</div>
      <div className="fc-tooltip-muted">{m.corrected ? `Satellite-corrected (x${m.factor})` : 'No satellite correction yet'}</div>
    </div>
  );
}

export default function Forecast() {
  const [range, setRange] = useState('30');
  const [history, setHistory] = useState(null);
  const [ahead, setAhead] = useState(null);
  const [year, setYear] = useState(null);
  const [model, setModel] = useState(null);
  const [error, setError] = useState(null);

  const [today] = useState(() => new Date());

  // Today and the days ahead: one fetch, refreshed every 10 minutes so the
  // intraday correction follows the day.
  useEffect(() => {
    let live = true;
    const load = async () => {
      try {
        const r = await fetchFromBackend(
          `/api/forecast/days?start=${format(today, 'yyyy-MM-dd')}&end=${format(addDays(today, 15), 'yyyy-MM-dd')}`, SLOW);
        if (live) setAhead(r.days);
      } catch {
        if (live) setError('Could not reach the forecast service.');
      }
    };
    load();
    const t = setInterval(load, 10 * 60 * 1000);
    return () => { live = false; clearInterval(t); };
  }, [today]);

  useEffect(() => {
    let live = true;
    const start = range === 'install' ? INSTALL_DATE : format(subDays(today, Number(range)), 'yyyy-MM-dd');
    const end = format(subDays(today, 1), 'yyyy-MM-dd');
    fetchFromBackend(`/api/forecast/days?start=${start}&end=${end}`, SLOW)
      .then((r) => live && setHistory({ ...r, range }))
      .catch(() => live && setError('Could not reach the forecast service.'));
    return () => { live = false; };
  }, [range, today]);

  useEffect(() => {
    fetchFromBackend('/api/forecast/year', SLOW).then(setYear).catch(() => {});
    fetchFromBackend('/api/forecast/model', SLOW).then(setModel).catch(() => {});
  }, []);

  const todayRow = ahead?.find((d) => d.kind === 'today');
  // The forecast runs out partway through the last day; drop days it does not fully cover.
  const upcoming = ahead?.filter((d) => d.kind === 'forecast' && d.weather_complete) ?? [];
  const tomorrow = upcoming[0];
  const week = upcoming.slice(0, 7);

  const aheadData = upcoming.map((d) => ({
    ...d, err: [d.expected_kwh - d.low_kwh, d.high_kwh - d.expected_kwh], label: format(parseISO(d.date), 'EEE d'),
  }));

  // A range switch keeps the old data until the new answer arrives; show it as loading meanwhile.
  const histReady = history && history.range === range;
  const histData = useMemo(() => (histReady ? history.days : []).map((d) => ({
    ...d, band: [d.low_kwh, d.high_kwh], label: format(parseISO(d.date), 'd MMM'),
  })), [history, histReady]);

  const firstAppDay = history?.first_app_day;
  const firstAppLabel = histData.find((d) => d.date >= firstAppDay)?.label;
  const hasEstimated = histData.some((d) => d.kind === 'estimated');

  const summary = useMemo(() => {
    const measured = histData.filter((d) => d.kind === 'measured');
    const sum = (f) => measured.reduce((a, d) => a + (f(d) || 0), 0);
    return {
      days: measured.length,
      actual: sum((d) => d.actual_kwh),
      expected: sum((d) => d.expected_kwh),
      outage: sum((d) => d.lost?.outage_kwh),
      inverterOff: sum((d) => Object.values(d.lost?.inverter_off_kwh || {}).reduce((a, b) => a + b, 0)),
      under: measured.filter((d) => d.verdict?.status === 'under').length,
    };
  }, [histData]);

  const flagged = histData
    .filter((d) => d.verdict && d.verdict.status !== 'normal')
    .sort((a, b) => b.date.localeCompare(a.date));

  const yearData = (year?.typical ?? []).map((m) => {
    const f = m.satellite_factor || 1;
    const value = m.corrected_mean_kwh;
    const lo = Math.round(m.min_kwh * f);
    const hi = Math.round(m.max_kwh * f);
    return { month: m.month, name: MONTHS[m.month - 1], value, lo, hi, err: [value - lo, hi - value],
      corrected: !!m.satellite_factor, factor: m.satellite_factor };
  });

  const val = model?.validation?.by_source;

  return (
    <div className="fc-page">
      <div className="page-header desktop-only">
        <div className="header-title-box">
          <CloudSun size={28} className="header-icon" />
          <div>
            <h2>Solar Forecast</h2>
            <p className="subtitle">Expected output from weather and satellite sunlight, calibrated on this system</p>
          </div>
        </div>
      </div>

      {error && <div className="fc-error glass-panel"><TriangleAlert size={18} /> {error}</div>}

      <div className="fc-tiles">
        <Tile
          label="Today"
          value={todayRow ? kwh(todayRow.expected_kwh) : '…'}
          accent={SERIES.actual}
          sub={todayRow && (
            <>
              {kwh(todayRow.intraday?.actual_so_far_kwh)} so far · range {todayRow.low_kwh.toFixed(0)}-{todayRow.high_kwh.toFixed(0)}
              {todayRow.intraday?.ratio_so_far != null && (
                <> · running at {Math.round(todayRow.intraday.ratio_so_far * 100)}% of forecast</>
              )}
            </>
          )}
        />
        <Tile
          label="Tomorrow"
          value={tomorrow ? kwh(tomorrow.expected_kwh) : '…'}
          sub={tomorrow && `${tomorrow.sky} sky · range ${tomorrow.low_kwh.toFixed(0)}-${tomorrow.high_kwh.toFixed(0)} kWh`}
        />
        <Tile
          label="Next 7 days"
          value={week.length ? kwh(week.reduce((a, d) => a + d.expected_kwh, 0), 0) : '…'}
          sub={week.length ? `about ${(week.reduce((a, d) => a + d.expected_kwh, 0) / week.length).toFixed(0)} kWh a day` : null}
        />
        <Tile
          label="Typical year"
          value={year ? `${(year.corrected_total_kwh / 1000).toFixed(1)} MWh` : '…'}
          sub={year && `satellite-corrected · ${(year.typical_total_kwh / 1000).toFixed(1)} MWh uncorrected`}
        />
      </div>

      <section className="fc-card glass-panel">
        <div className="fc-card-head">
          <h3>Next {upcoming.length || 15} days</h3>
          <span className="fc-muted">Bars: expected output · whiskers: likely range (10th to 90th percentile)</span>
        </div>
        <div className="fc-chart" style={{ height: 260 }}>
          {aheadData.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={aheadData} margin={{ top: 10, right: 8, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="label" stroke="var(--text-secondary)" fontSize={11} tickLine={false} />
                <YAxis stroke="var(--text-secondary)" fontSize={11} tickLine={false} axisLine={false} unit=" kWh" width={70} />
                <Tooltip content={<DayTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                <Bar dataKey="expected_kwh" fill={SERIES.expected} radius={[4, 4, 0, 0]} maxBarSize={28}>
                  <ErrorBar dataKey="err" width={6} stroke="var(--text-secondary)" strokeWidth={1.5} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <div className="fc-loading">Loading forecast…</div>}
        </div>
        <p className="fc-note">
          The next 2-3 days use the UK Met Office forecast, later days Open-Meteo's. Cloudy days carry a much
          wider range: forecasting cloud days ahead is the hard limit, not the panel model.
        </p>
      </section>

      <section className="fc-card glass-panel">
        <div className="fc-card-head">
          <h3>Expected vs actual</h3>
          <div className="fc-seg">
            {RANGES.map((r) => (
              <button key={r.id} className={range === r.id ? 'active' : ''} onClick={() => setRange(r.id)}>{r.label}</button>
            ))}
          </div>
        </div>
        <div className="fc-chart" style={{ height: 300 }}>
          {histReady ? (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={histData} margin={{ top: 10, right: 8, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="label" stroke="var(--text-secondary)" fontSize={11} tickLine={false} minTickGap={24} />
                <YAxis stroke="var(--text-secondary)" fontSize={11} tickLine={false} axisLine={false} unit=" kWh" width={70} />
                {hasEstimated && firstAppLabel && (
                  <ReferenceArea x1={histData[0].label} x2={firstAppLabel} fill="rgba(255,255,255,0.03)"
                    label={{ value: 'Before the app: estimates', position: 'insideTopLeft', fill: 'var(--text-muted)', fontSize: 11 }} />
                )}
                <Tooltip content={<DayTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.2)' }} />
                <Legend verticalAlign="top" height={28} iconType="plainline" wrapperStyle={{ fontSize: 12, color: 'var(--text-secondary)' }} />
                <Area dataKey="band" name="Likely range" stroke="none" fill={SERIES.expected} fillOpacity={0.15}
                  isAnimationActive={false} legendType="square" />
                <Bar dataKey="actual_kwh" name="Actual" fill={SERIES.actual} radius={[4, 4, 0, 0]} maxBarSize={14} />
                <Line dataKey="expected_kwh" name="Expected" stroke={SERIES.expected} strokeWidth={2} dot={false}
                  isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          ) : <div className="fc-loading">Loading history…</div>}
        </div>
        {histReady && (
          <div className="fc-stats">
            <div><span>Days measured</span><b>{summary.days}</b></div>
            <div><span>Actual</span><b>{summary.actual.toFixed(0)} kWh</b></div>
            <div><span>Expected</span><b>{summary.expected.toFixed(0)} kWh</b></div>
            <div><span>Lost to grid outages</span><b>{summary.outage.toFixed(0)} kWh</b></div>
            <div><span>Lost to an inverter off</span><b>{summary.inverterOff.toFixed(0)} kWh</b></div>
            <div><span>Unexplained low days</span><b>{summary.under}</b></div>
          </div>
        )}
      </section>

      {flagged.length > 0 && (
        <section className="fc-card glass-panel">
          <div className="fc-card-head">
            <h3>Days that differed</h3>
            <span className="fc-muted">{flagged.length} in this range, newest first</span>
          </div>
          <div className="fc-flags">
            {flagged.map((d) => {
              const v = VERDICT[d.verdict.status];
              return (
                <div key={d.date} className="fc-flag">
                  <div className="fc-flag-top">
                    <span className="fc-flag-date">{fmtDay(d.date)}</span>
                    <span className={`fc-pill tone-${v.tone}`}>
                      {v.tone === 'good' ? <CircleCheck size={13} /> : <TriangleAlert size={13} />} {v.label}
                    </span>
                  </div>
                  <div className="fc-flag-nums">
                    {kwh(d.actual_kwh)} actual vs {kwh(d.expected_kwh)} expected
                    <span className="fc-muted"> · {d.sunlight_observed ? <><Satellite size={12} /> satellite</> : 'forecast'}</span>
                  </div>
                  {d.verdict.reasons.map((r) => <div key={r} className="fc-flag-reason">{r}</div>)}
                </div>
              );
            })}
          </div>
        </section>
      )}

      <div className="fc-two">
        <section className="fc-card glass-panel">
          <div className="fc-card-head">
            <h3>Typical year</h3>
            <span className="fc-muted">Expected per month · whiskers: best and worst year, 2022-2025</span>
          </div>
          <div className="fc-chart" style={{ height: 240 }}>
            {yearData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={yearData} margin={{ top: 10, right: 8, left: -6, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="name" stroke="var(--text-secondary)" fontSize={11} tickLine={false} />
                  <YAxis stroke="var(--text-secondary)" fontSize={11} tickLine={false} axisLine={false} width={50} />
                  <Tooltip content={<YearTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                  <Bar dataKey="value" fill={SERIES.expected} radius={[4, 4, 0, 0]} maxBarSize={28}>
                    <ErrorBar dataKey="err" width={6} stroke="var(--text-secondary)" strokeWidth={1.5} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : <div className="fc-loading">Loading…</div>}
          </div>
          <p className="fc-note">
            kWh per month. Winter is lowest partly because surrounding buildings shade the panels whenever the sun is
            below about 25°. December and January have lower sun than the app has measured yet, so they are the least certain.
          </p>
        </section>

        <section className="fc-card glass-panel">
          <div className="fc-card-head">
            <h3>How accurate is it?</h3>
            <span className="fc-muted">Scored on the last 30 days, which the model was not fitted on</span>
          </div>
          {val ? (
            <table className="fc-table">
              <thead>
                <tr><th>Sunlight source</th><th>Used for</th><th>Clear</th><th>Partly</th><th>Cloudy</th></tr>
              </thead>
              <tbody>
                {[['sat', 'Past days'], ['ukmo', 'Next 2-3 days'], ['bm', 'Later days']].map(([s, use]) => val[s] && (
                  <tr key={s}>
                    <td>{SOURCE_LABEL[s]}</td>
                    <td className="fc-muted">{use}</td>
                    {['clear', 'partly', 'cloudy'].map((b) => (
                      <td key={b}>{val[s].by_sky[b] ? `${val[s].by_sky[b].mape_pct}%` : '-'}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <div className="fc-loading">Loading…</div>}
          <p className="fc-note">Average daily error. Days with a grid outage or an inverter off are left out.</p>
          {model?.health && (
            <>
              <h4 className="fc-subhead">Panels vs their rating</h4>
              <div className="fc-health">
                {Object.entries(model.health).map(([inv, h]) => (
                  <div key={inv}>
                    <span>{inv.replace('inv', 'Inverter ')}</span>
                    <b>{h.effective_kwp} of {h.rated_kwp} kWp</b>
                    <span className="fc-muted">{Math.round(h.performance_ratio * 100)}%</span>
                  </div>
                ))}
              </div>
            </>
          )}
          {model && (
            <p className="fc-note"><RefreshCw size={12} /> Recalibrated {format(parseISO(model.fitted_at), 'd MMM, HH:mm')} · weather refreshed every 3 hours</p>
          )}
        </section>
      </div>
    </div>
  );
}
