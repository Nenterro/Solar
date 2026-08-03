import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  DatabaseBackup, 
  Play, 
  Calendar, 
  RefreshCw, 
  CheckCircle2, 
  Clock, 
  Server,
  Activity,
  Terminal,
  Wifi,
  AlertTriangle,
  Check,
  X,
  ExternalLink
} from 'lucide-react';
import { format, subDays, startOfMonth } from 'date-fns';
import { fetchFromBackend, getCandidateUrls, resetCachedUrl } from '../utils/api';
import './Settings.css';

const DEFAULT_CANDIDATES = [
  'http://192.168.18.49:8000',
  'http://localhost:8000',
  'http://100.97.146.42:8000',
  'https://huz-solar.duckdns.org'
];

export default function Settings() {
  const [activeTab, setActiveTab] = useState('troubleshooter'); // 'troubleshooter' | 'backfill' | 'general'
  
  // Custom Backend URL state
  const [customUrl, setCustomUrl] = useState(() => {
    return localStorage.getItem('solar_custom_backend_url') || 'http://192.168.18.49:8000';
  });

  // Backfill Date Range Form State
  const [startDate, setStartDate] = useState(format(subDays(new Date(), 7), 'yyyy-MM-dd'));
  const [endDate, setEndDate] = useState(format(new Date(), 'yyyy-MM-dd'));

  // Diagnostic Logs & Test State
  const [isDiagnosing, setIsDiagnosing] = useState(false);
  const [diagnosticLogs, setDiagnosticLogs] = useState([]);
  const [probeResults, setProbeResults] = useState([]);
  const [toastMessage, setToastMessage] = useState(null);

  // Active / Mock Queued Jobs
  const [jobs, setJobs] = useState([
    {
      id: 'BF-1092',
      startDate: '2026-07-01',
      endDate: '2026-07-15',
      status: 'completed',
      progress: 100,
      recordsFetched: 4320,
      timestamp: 'Today at 18:30'
    }
  ]);

  const [isSubmitting, setIsSubmitting] = useState(false);

  const addLog = (msg, level = 'INFO') => {
    const time = format(new Date(), 'HH:mm:ss');
    setDiagnosticLogs(prev => [...prev, { time, level, msg }]);
  };

  const [backfillLogs, setBackfillLogs] = useState([
    { time: format(new Date(), 'HH:mm:ss'), level: 'INFO', msg: 'Backfill telemetry console ready. Select a date range to trigger the scraper.' }
  ]);

  const addBackfillLog = (msg, level = 'INFO') => {
    const time = format(new Date(), 'HH:mm:ss');
    setBackfillLogs(prev => [...prev, { time, level, msg }]);
  };

  // Run Network Diagnostic Suite
  const runDiagnostics = async () => {
    setIsDiagnosing(true);
    setDiagnosticLogs([]);
    setProbeResults([]);

    const timeStart = format(new Date(), 'HH:mm:ss');
    addLog(`=== SOLAR DASHBOARD NETWORK & BACKEND DIAGNOSTIC TEST STARTED AT ${timeStart} ===`, 'HEADER');
    addLog(`Client Browser Context: Protocol = ${window.location.protocol}, Host = ${window.location.host}`, 'INFO');

    if (window.location.protocol === 'https:') {
      addLog(`[WARNING] Client browser is running on HTTPS (${window.location.origin}). Chrome/Safari block unencrypted HTTP fetches (Mixed Content) unless SSL or local IP bypass is enabled!`, 'WARN');
    }

    const testUrls = Array.from(new Set([customUrl, ...DEFAULT_CANDIDATES])).filter(Boolean);
    const results = [];

    for (const baseUrl of testUrls) {
      addLog(`Probing Candidate: ${baseUrl}...`, 'PROBE');
      const startMs = performance.now();
      try {
        const res = await fetch(`${baseUrl}/api/telemetry?inverter=all`, {
          method: 'GET',
          signal: AbortSignal.timeout(4000)
        });
        const elapsedMs = Math.round(performance.now() - startMs);

        if (res.ok) {
          const data = await res.json();
          addLog(`[SUCCESS 200 OK] ${baseUrl} responded in ${elapsedMs}ms`, 'SUCCESS');
          addLog(`  Payload: Solar=${data.solar_power_kw ?? 0}kW | Load=${data.ac_output_power_kw ?? 0}kW | Battery=${data.battery_power_kw ?? 0}kW | USB HID Connected=${data.connected ?? false}`, 'SUCCESS');

          results.push({
            url: baseUrl,
            status: 'ONLINE',
            latency: elapsedMs,
            hidConnected: data.connected ?? false,
            isSimulated: data.is_simulated ?? false,
            data
          });
        } else {
          addLog(`[HTTP ${res.status}] ${baseUrl} returned status ${res.statusText}`, 'ERROR');
          results.push({ url: baseUrl, status: `HTTP ${res.status}`, latency: elapsedMs });
        }
      } catch (err) {
        const elapsedMs = Math.round(performance.now() - startMs);
        addLog(`[FAILED] ${baseUrl} -> ${err.name}: ${err.message}`, 'ERROR');
        results.push({ url: baseUrl, status: 'FAILED / BLOCKED', latency: elapsedMs, error: err.message });
      }
    }

    setProbeResults(results);
    const onlineCount = results.filter(r => r.status === 'ONLINE').length;
    addLog(`=== DIAGNOSTIC COMPLETE: ${onlineCount}/${testUrls.length} candidate URLs reachable ===`, 'HEADER');
    setIsDiagnosing(false);
  };

  // Run diagnostics automatically when tab is opened
  useEffect(() => {
    if (activeTab === 'troubleshooter' && probeResults.length === 0) {
      runDiagnostics();
    }
  }, [activeTab]);

  const handleSaveCustomUrl = () => {
    let formatted = customUrl.trim();
    if (formatted && !formatted.startsWith('http://') && !formatted.startsWith('https://')) {
      formatted = `http://${formatted}`;
    }
    setCustomUrl(formatted);
    localStorage.setItem('solar_custom_backend_url', formatted);
    resetCachedUrl();
    setToastMessage(`Custom Backend URL saved: ${formatted}`);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const handlePreset = (preset) => {
    const todayStr = format(new Date(), 'yyyy-MM-dd');
    setEndDate(todayStr);

    if (preset === '7days') setStartDate(format(subDays(new Date(), 7), 'yyyy-MM-dd'));
    else if (preset === '30days') setStartDate(format(subDays(new Date(), 30), 'yyyy-MM-dd'));
    else if (preset === 'current_month') setStartDate(format(startOfMonth(new Date()), 'yyyy-MM-dd'));
  };

  const handleStartBackfill = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);

    const newJobId = `BF-${Math.floor(1000 + Math.random() * 9000)}`;
    setToastMessage(`[JOB ${newJobId}] Initiating backfill from ${startDate} to ${endDate}...`);

    addBackfillLog(`=== STARTING HISTORICAL BACKFILL JOB ${newJobId} ===`, 'HEADER');
    addBackfillLog(`Target Date Range: ${startDate} to ${endDate}`, 'INFO');
    addBackfillLog(`Target Inverters: All System Units (inv1, inv2, inv3)`, 'INFO');

    // Add running job to queue list
    const runningJob = {
      id: newJobId,
      startDate,
      endDate,
      status: 'in_progress',
      progress: 0,
      recordsFetched: 'Scraping DESS cloud...',
      timestamp: format(new Date(), 'HH:mm:ss')
    };
    setJobs(prev => [runningJob, ...prev]);

    // Find working candidate URL
    let activeBaseUrl = null;
    const candidateUrls = getCandidateUrls();

    for (const baseUrl of candidateUrls) {
      addBackfillLog(`Testing candidate endpoint: ${baseUrl}/api/telemetry...`, 'PROBE');
      try {
        const testRes = await fetch(`${baseUrl}/api/telemetry?inverter=all`, { signal: AbortSignal.timeout(3000) });
        if (testRes.ok) {
          activeBaseUrl = baseUrl;
          addBackfillLog(`[ONLINE] Active backend host selected: ${baseUrl}`, 'SUCCESS');
          break;
        }
      } catch (err) {
        addBackfillLog(`Candidate ${baseUrl} unreachable: ${err.message}`, 'WARN');
      }
    }

    if (!activeBaseUrl) {
      addBackfillLog(`[ERROR] No reachable backend found. Aborting backfill.`, 'ERROR');
      setToastMessage('ERROR: No reachable backend server found.');
      setJobs(prev => prev.map(j => j.id === newJobId ? { ...j, status: 'failed', recordsFetched: 'No backend reachable' } : j));
      setIsSubmitting(false);
      return;
    }

    addBackfillLog(`Dispatching POST to ${activeBaseUrl}/api/backfill?start_date=${startDate}&end_date=${endDate}...`, 'PROBE');
    const startMs = performance.now();

    try {
      const res = await fetch(`${activeBaseUrl}/api/backfill?start_date=${startDate}&end_date=${endDate}&inverter=all`, {
        method: 'POST',
        signal: AbortSignal.timeout(120000)  // 2 minute timeout for large backfills
      });
      const elapsedMs = Math.round(performance.now() - startMs);

      if (res.ok) {
        const data = await res.json();
        const msg = data.message || 'Backfill completed successfully!';
        const totalRecords = data.total_records || 0;
        const monthsScraped = data.months_scraped || [];

        addBackfillLog(`[SUCCESS ${res.status} OK] Backend responded in ${elapsedMs}ms`, 'SUCCESS');
        addBackfillLog(`  Result: ${msg}`, 'SUCCESS');
        if (monthsScraped.length > 0) {
          addBackfillLog(`  Months Scraped: ${monthsScraped.join(', ')}`, 'SUCCESS');
        }
        addBackfillLog(`[DATABASE COMMIT] ${totalRecords} daily records saved to SQLite daily_totals table.`, 'SUCCESS');
        addBackfillLog(`=== BACKFILL JOB ${newJobId} COMPLETED SUCCESSFULLY ===`, 'HEADER');

        setToastMessage(`SUCCESS: ${msg}`);
        setJobs(prev => prev.map(j => j.id === newJobId ? {
          ...j,
          status: 'completed',
          progress: 100,
          recordsFetched: `${totalRecords} daily records`
        } : j));
      } else {
        const errText = await res.text();
        addBackfillLog(`[HTTP ${res.status}] Backfill failed: ${res.statusText}`, 'ERROR');
        addBackfillLog(`  Response: ${errText.substring(0, 200)}`, 'ERROR');
        setToastMessage(`ERROR: Backend returned HTTP ${res.status}`);
        setJobs(prev => prev.map(j => j.id === newJobId ? {
          ...j,
          status: 'failed',
          recordsFetched: `HTTP ${res.status}`
        } : j));
      }
    } catch (err) {
      const elapsedMs = Math.round(performance.now() - startMs);
      addBackfillLog(`[FETCH FAILED] ${err.name}: ${err.message} (${elapsedMs}ms)`, 'ERROR');
      setToastMessage(`ERROR: ${err.message}`);
      setJobs(prev => prev.map(j => j.id === newJobId ? {
        ...j,
        status: 'failed',
        recordsFetched: err.message
      } : j));
    }

    setIsSubmitting(false);
    setTimeout(() => setToastMessage(null), 6000);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="settings-page-container"
    >
      {/* Top Header */}
      <div className="settings-header-row">
        <div>
          <h2 className="page-title">Settings & Diagnostics</h2>
          <p className="page-subtitle">Network Troubleshooter & Historical Data Backfill Engine</p>
        </div>

        {/* Sub-Navigation Tabs */}
        <div className="timeframe-pill-selector">
          <button 
            className={`timeframe-btn ${activeTab === 'troubleshooter' ? 'active' : ''}`}
            onClick={() => setActiveTab('troubleshooter')}
          >
            <Activity size={16} />
            Troubleshooter
          </button>
          <button 
            className={`timeframe-btn ${activeTab === 'backfill' ? 'active' : ''}`}
            onClick={() => setActiveTab('backfill')}
          >
            <DatabaseBackup size={16} />
            Data Backfill
          </button>
          <button 
            className={`timeframe-btn ${activeTab === 'general' ? 'active' : ''}`}
            onClick={() => setActiveTab('general')}
          >
            <Server size={16} />
            Server IP & API
          </button>
        </div>
      </div>

      {/* Toast Notification */}
      {toastMessage && (
        <div className="settings-toast-banner glass-panel">
          <CheckCircle2 size={18} className="toast-icon" />
          <span>{toastMessage}</span>
        </div>
      )}

      {activeTab === 'troubleshooter' ? (
        <div className="troubleshooter-layout-grid">
          {/* Top Status & Probe Controls */}
          <div className="trouble-card glass-panel">
            <div className="card-header-row">
              <div className="card-header-icon amber">
                <Wifi size={20} />
              </div>
              <div>
                <h3 className="card-title">Backend Connection Diagnostic</h3>
                <p className="card-subtitle">Test connection routes across LAN (192.168.18.49), Tailscale, and DuckDNS</p>
              </div>
              <button 
                className="submit-backfill-btn" 
                style={{ marginLeft: 'auto', width: 'auto', padding: '8px 16px' }}
                onClick={runDiagnostics}
                disabled={isDiagnosing}
              >
                <RefreshCw size={16} className={isDiagnosing ? 'spin-icon' : ''} />
                {isDiagnosing ? 'Running Probe...' : 'Run Live Diagnostic'}
              </button>
            </div>

            {/* Custom URL Input & Override */}
            <div className="custom-url-box glass-panel" style={{ marginTop: '16px', padding: '14px' }}>
              <label className="input-label" style={{ fontSize: '0.85rem' }}>Primary Custom Backend URL (Priority #1)</label>
              <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
                <input 
                  type="text" 
                  value={customUrl}
                  onChange={(e) => setCustomUrl(e.target.value)}
                  placeholder="http://192.168.18.49:8000"
                  className="custom-text-input"
                  style={{ flex: 1 }}
                />
                <button className="csv-export-btn" onClick={handleSaveCustomUrl}>
                  Save & Set Priority
                </button>
              </div>
            </div>
          </div>

          {/* Diagnostic Results Table */}
          <div className="trouble-card glass-panel" style={{ marginTop: '16px' }}>
            <div className="card-header-row">
              <div className="card-header-icon green">
                <CheckCircle2 size={20} />
              </div>
              <div>
                <h3 className="card-title">Backend Connectivity Matrix</h3>
                <p className="card-subtitle">Status of candidate backend API URLs</p>
              </div>
            </div>

            <div className="probe-grid" style={{ marginTop: '14px' }}>
              {probeResults.map((r, idx) => (
                <div key={idx} className={`probe-item ${r.status === 'ONLINE' ? 'online' : 'offline'}`}>
                  <div className="probe-main-row">
                    <span className="probe-url">{r.url}</span>
                    <span className={`probe-badge ${r.status === 'ONLINE' ? 'online' : 'offline'}`}>
                      {r.status} ({r.latency}ms)
                    </span>
                  </div>
                  {r.error && (
                    <div className="probe-err-msg">
                      <AlertTriangle size={12} /> {r.error}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Real-time Terminal Log Console */}
          <div className="trouble-card glass-panel" style={{ marginTop: '16px' }}>
            <div className="card-header-row">
              <div className="card-header-icon blue">
                <Terminal size={20} />
              </div>
              <div>
                <h3 className="card-title">Live Connection Diagnostic Terminal</h3>
                <p className="card-subtitle">Detailed HTTP status codes, CORS headers, and payload logs</p>
              </div>
            </div>

            <div className="terminal-console-box" style={{ marginTop: '14px' }}>
              {diagnosticLogs.length > 0 ? (
                diagnosticLogs.map((item, idx) => (
                  <div key={idx} className={`log-line ${item.level.toLowerCase()}`}>
                    <span className="log-time">[{item.time}]</span>
                    <span className={`log-level ${item.level.toLowerCase()}`}>{item.level}</span>
                    <span className="log-msg">{item.msg}</span>
                  </div>
                ))
              ) : (
                <div className="empty-terminal">
                  Click "Run Live Diagnostic" above to inspect network connection logs.
                </div>
              )}
            </div>
          </div>
        </div>
      ) : activeTab === 'backfill' ? (
        <div className="backfill-layout-grid">
          {/* Left Column: Form & Presets */}
          <div className="backfill-form-card glass-panel">
            <div className="card-header-row">
              <div className="card-header-icon amber">
                <DatabaseBackup size={20} />
              </div>
              <div>
                <h3 className="card-title">Queue New Backfill Job</h3>
                <p className="card-subtitle">Select date range to trigger backend telemetry scraper</p>
              </div>
            </div>

            <form onSubmit={handleStartBackfill} className="backfill-form">
              <div className="form-group">
                <label className="input-label">Quick Presets</label>
                <div className="presets-row">
                  <button type="button" className="preset-chip" onClick={() => handlePreset('7days')}>Last 7 Days</button>
                  <button type="button" className="preset-chip" onClick={() => handlePreset('30days')}>Last 30 Days</button>
                  <button type="button" className="preset-chip" onClick={() => handlePreset('current_month')}>This Month</button>
                </div>
              </div>

              <div className="form-row-2col">
                <div className="form-group">
                  <label className="input-label">Start Date</label>
                  <div className="input-with-icon">
                    <Calendar size={16} className="field-icon" />
                    <input 
                      type="date" 
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="custom-date-input"
                      required
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="input-label">End Date</label>
                  <div className="input-with-icon">
                    <Calendar size={16} className="field-icon" />
                    <input 
                      type="date" 
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="custom-date-input"
                      required
                    />
                  </div>
                </div>
              </div>

              <button type="submit" className="submit-backfill-btn" disabled={isSubmitting} style={{ opacity: isSubmitting ? 0.7 : 1 }}>
                {isSubmitting ? (
                  <>
                    <RefreshCw size={18} className="spin-icon" /> Scraping & Backfilling DESS Cloud...
                  </>
                ) : (
                  <>
                    <Play size={18} /> Queue & Start Backfill
                  </>
                )}
              </button>
            </form>
          </div>

          <div className="backfill-queue-card glass-panel">
            <div className="card-header-row">
              <div className="card-header-icon blue">
                <Clock size={20} />
              </div>
              <div>
                <h3 className="card-title">Backfill History</h3>
                <p className="card-subtitle">Recent backend tasks</p>
              </div>
            </div>
            <div className="jobs-list">
              {jobs.map((job) => (
                <div key={job.id} className="job-item-card">
                  <div className="job-header">
                    <span className="job-id-text">{job.id}</span>
                    <span className={`status-tag ${job.status}`}>
                      {job.status === 'in_progress' ? (
                        <>
                          <RefreshCw size={12} className="spin-icon" /> IN PROGRESS
                        </>
                      ) : (
                        'COMPLETED'
                      )}
                    </span>
                  </div>
                  <span className="detail-val">{job.startDate} → {job.endDate}</span>
                  <span className="detail-sub" style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px', display: 'block' }}>
                    {job.recordsFetched}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Live Backfill Execution Terminal Log Console */}
          <div className="trouble-card glass-panel" style={{ marginTop: '20px', gridColumn: '1 / -1' }}>
            <div className="card-header-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div className="card-header-icon blue">
                  <Terminal size={20} />
                </div>
                <div>
                  <h3 className="card-title">Live Backfill Terminal Console</h3>
                  <p className="card-subtitle">Real-time HTTP requests, DESS cloud API responses, & SQLite DB commit logs</p>
                </div>
              </div>
              {backfillLogs.length > 0 && (
                <button 
                  className="preset-chip" 
                  onClick={() => setBackfillLogs([])}
                  style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                >
                  Clear Logs
                </button>
              )}
            </div>

            <div className="terminal-console-box" style={{ marginTop: '14px', maxHeight: '250px', overflowY: 'auto' }}>
              {backfillLogs.length > 0 ? (
                backfillLogs.map((item, idx) => (
                  <div key={idx} className={`log-line ${item.level.toLowerCase()}`}>
                    <span className="log-time">[{item.time}]</span>
                    <span className={`log-level ${item.level.toLowerCase()}`}>{item.level}</span>
                    <span className="log-msg">{item.msg}</span>
                  </div>
                ))
              ) : (
                <div className="empty-terminal">
                  Queue a backfill job above to view live real-time execution logs.
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        /* General Backend Server Settings */
        <div className="general-settings-card glass-panel">
          <div className="card-header-row">
            <div className="card-header-icon amber">
              <Server size={20} />
            </div>
            <div>
              <h3 className="card-title">Backend Server & API Configuration</h3>
              <p className="card-subtitle">IP address, ports, and PocketBase telemetry endpoints</p>
            </div>
          </div>

          <div className="settings-form">
            <div className="form-group">
              <label className="input-label">Custom Backend URL</label>
              <input 
                type="text" 
                value={customUrl} 
                onChange={(e) => setCustomUrl(e.target.value)}
                className="custom-text-input" 
                placeholder="http://192.168.18.49:8000"
              />
            </div>

            <button className="submit-backfill-btn" onClick={handleSaveCustomUrl}>
              Save Configuration
            </button>
          </div>
        </div>
      )}

      {/* Mobile Scroll Clearance Spacer */}
      <div className="settings-bottom-spacer" />
    </motion.div>
  );
}
