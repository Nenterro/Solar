import { useState, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { Power, Activity, Zap, Clock, ChevronLeft, ChevronRight, Calendar as CalendarIcon, AlertTriangle } from 'lucide-react';
import { format, addDays, subDays, isSameDay } from 'date-fns';
import { useTelemetry } from '../context/TelemetryContext';
import { fetchFromBackend } from '../utils/api';
import './Grid.css';

export default function Grid() {
  const { telemetry: liveData } = useTelemetry();
  
  const today = useMemo(() => new Date(), []);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [historyData, setHistoryData] = useState([]);
  const [dailyScrapedTotals, setDailyScrapedTotals] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hoveredBlock, setHoveredBlock] = useState(null);
  const [headerSlot, setHeaderSlot] = useState(null);

  useEffect(() => {
    setHeaderSlot(document.getElementById('mobile-header-slot'));
  }, []);

  // Live metrics from TelemetryContext
  const isOnline = liveData?.gridActive ?? false;
  const gridVoltage = liveData?.gridVoltage ?? 0;
  const gridFreq = liveData?.gridFrequency ?? 0;
  const gridPower = liveData?.gridPower ?? 0;

  // Fetch history and daily totals
  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);

    const fetchData = async () => {
      const dateStr = format(selectedDate, 'yyyy-MM-dd');
      try {
        const [histRes, totalsRes] = await Promise.all([
          fetchFromBackend(`/api/history?date=${dateStr}&inverter=all&_t=${Date.now()}`),
          fetchFromBackend(`/api/dess_totals?month=${dateStr.substring(0, 7)}&inverter=all`)
        ]);
        
        if (isMounted) {
          setHistoryData(histRes.records || []);
          
          let dayObj = null;
          if (Array.isArray(totalsRes.totals)) {
            dayObj = totalsRes.totals.find(item => item.time === dateStr);
          } else if (totalsRes.totals && totalsRes.totals.solar !== undefined) {
            dayObj = totalsRes.totals;
          }
          setDailyScrapedTotals(dayObj);
        }
      } catch (err) {
        console.error("Failed to fetch grid data", err);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    fetchData();
    // Auto refresh every 60s
    const interval = setInterval(fetchData, 60000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [selectedDate]);

  // Date Navigation
  const isNextDisabled = useMemo(() => isSameDay(selectedDate, today), [selectedDate, today]);
  
  const handlePrevDate = () => setSelectedDate(prev => subDays(prev, 1));
  const handleNextDate = () => {
    if (!isNextDisabled) setSelectedDate(prev => addDays(prev, 1));
  };
  const dateFormattedLabel = useMemo(() => format(selectedDate, 'EEEE, MMM d, yyyy'), [selectedDate]);

  // Process history data for Timeline and Total Load Shedding
  // Process Grid Activity Timeline with exact minute-of-day alignment & surrounding fill
  const { timelineBlocks, totalSheddingMins } = useMemo(() => {
    if (!historyData || historyData.length === 0) return { timelineBlocks: [], totalSheddingMins: 0 };

    // 1. Build a lookup map of minute-of-day (0 to 1439) -> record
    const minuteMap = new Map();
    historyData.forEach(r => {
      if (r.time && typeof r.time === 'string' && r.time.includes(':')) {
        const parts = r.time.split(':');
        const h = parseInt(parts[0], 10);
        const m = parseInt(parts[1], 10);
        if (!isNaN(h) && !isNaN(m)) {
          const minIdx = h * 60 + m;
          minuteMap.set(minIdx, r);
        }
      }
    });

    const recordedMins = Array.from(minuteMap.keys()).sort((a, b) => a - b);
    if (recordedMins.length === 0) return { timelineBlocks: [], totalSheddingMins: 0 };

    const isToday = isSameDay(selectedDate, today);
    const now = new Date();
    const currentMin = isToday ? (now.getHours() * 60 + now.getMinutes()) : 1439;

    // Helper to find nearest surrounding recorded reading for missing telemetry minutes
    const getEffectiveRecord = (m) => {
      if (minuteMap.has(m)) return minuteMap.get(m);
      
      // Find nearest recorded minute
      let closestMin = recordedMins[0];
      let minDiff = Math.abs(m - closestMin);

      for (let i = 1; i < recordedMins.length; i++) {
        const rMin = recordedMins[i];
        const diff = Math.abs(m - rMin);
        if (diff < minDiff) {
          minDiff = diff;
          closestMin = rMin;
        } else if (diff > minDiff) {
          break;
        }
      }
      return minuteMap.get(closestMin);
    };

    let blocks = [];
    let currentBlock = null;
    let sheddingMins = 0;

    // 2. Iterate minute by minute from 00:00 (0) up to current time (or 1439 for past dates)
    for (let m = 0; m <= currentMin; m++) {
      const rec = getEffectiveRecord(m);
      const isGridActive = rec ? Boolean(rec.gridActive) : true;
      const statusState = isGridActive ? 'online' : 'offline';

      if (!isGridActive) {
        sheddingMins++;
      }

      if (!currentBlock) {
        currentBlock = { statusState, startMin: m, endMin: m };
      } else if (currentBlock.statusState === statusState) {
        currentBlock.endMin = m;
      } else {
        blocks.push(currentBlock);
        currentBlock = { statusState, startMin: m, endMin: m };
      }
    }

    if (currentBlock) {
      blocks.push(currentBlock);
    }

    return { timelineBlocks: blocks, totalSheddingMins: sheddingMins };
  }, [historyData, selectedDate, today]);

  const formatDuration = (mins) => {
    if (mins === 0) return "0h 0m";
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${h}h ${m}m`;
  };

  return (
    <div className="grid-page">
      <div className="page-header glass-panel desktop-only">
        <div className="header-title-box">
          <Power className="header-icon" size={24} style={{ color: isOnline ? '#10b981' : '#ef4444' }} />
          <div>
            <h2>WAPDA Grid Status</h2>
            <p className="subtitle">Real-time Utility Monitoring & Export Statistics</p>
          </div>
        </div>
        <div className="header-controls">
          <div className={`status-badge ${isOnline ? 'online' : 'offline'}`}>
            <div className="status-dot"></div>
            <span>{isOnline ? 'Online' : 'Load Shedding (Offline)'}</span>
          </div>
        </div>
      </div>

      {/* Mobile-only status row */}
      <div className={`mobile-grid-status mobile-only glass-panel ${isOnline ? 'online' : 'offline'}`}>
        <Power size={20} />
        <span>{isOnline ? 'Grid — Online' : 'Grid — Load Shedding'}</span>
        <div className="status-dot"></div>
      </div>

      <div className="grid-dashboard">
        
        {/* Real-time Metrics Grid */}
        <div className="metrics-grid">
          <div className="metric-card glass-panel">
            <div className="metric-icon" style={{ background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6' }}>
              <Activity size={40} />
            </div>
            <div className="metric-info">
              <span className="metric-label">Voltage</span>
              <div className="metric-value">
                {gridVoltage.toFixed(1)} <span className="unit">V</span>
              </div>
            </div>
          </div>

          <div className="metric-card glass-panel">
            <div className="metric-icon" style={{ background: 'rgba(168, 85, 247, 0.1)', color: '#a855f7' }}>
              <Activity size={40} />
            </div>
            <div className="metric-info">
              <span className="metric-label">Frequency</span>
              <div className="metric-value">
                {gridFreq.toFixed(1)} <span className="unit">Hz</span>
              </div>
            </div>
          </div>

          <div className="metric-card glass-panel">
            <div className="metric-icon" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>
              <Zap size={40} />
            </div>
            <div className="metric-info">
              <span className="metric-label">
                Power {gridPower > 0.02 ? '(Importing)' : gridPower < -0.02 ? '(Exporting)' : ''}
              </span>
              <div className="metric-value">
                {Math.abs(gridPower).toFixed(2)} <span className="unit">kW</span>
              </div>
            </div>
          </div>
        </div>

        {/* Load Shedding Timeline Section */}
        <div className="timeline-section glass-panel">
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
            <h2 className="widget-title">Grid Activity Timeline</h2>
            
            {/* Date Navigator (Reused concept from Graphs) */}
            <div className="date-navigator-card glass-panel" style={{ margin: 0, padding: '8px 16px', background: 'rgba(0,0,0,0.2)' }}>
              <button className="nav-arrow-btn" onClick={handlePrevDate} title="Previous">
                <ChevronLeft size={18} />
              </button>
              <div className="date-display-box" style={{ padding: '0 12px' }}>
                <CalendarIcon size={16} className="calendar-icon" />
                <span className="date-label-text" style={{ fontSize: '0.9rem' }}>{dateFormattedLabel}</span>
              </div>
              <button 
                className={`nav-arrow-btn ${isNextDisabled ? 'disabled' : ''}`} 
                onClick={handleNextDate} 
                disabled={isNextDisabled}
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </div>

          {isLoading && historyData.length === 0 ? (
            <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading timeline...</div>
          ) : (
            <>
              {/* Timeline Track */}
              <div className="timeline-container">
                <div className="timeline-track">
                  {timelineBlocks.map((block, i) => {
                    // Total minutes in a day is 1440
                    const leftPct = (block.startMin / 1440) * 100;
                    const widthPct = ((block.endMin - block.startMin + 1) / 1440) * 100;
                    
                    return (
                      <div 
                        key={i}
                        className={`timeline-segment ${block.statusState}`}
                        style={{
                          left: `${leftPct}%`,
                          width: `${widthPct}%`
                        }}
                        onMouseEnter={(e) => {
                          const rect = e.currentTarget.parentNode.getBoundingClientRect();
                          setHoveredBlock({
                            statusState: block.statusState,
                            start: `${Math.floor(block.startMin/60).toString().padStart(2,'0')}:${(block.startMin%60).toString().padStart(2,'0')}`,
                            end: `${Math.floor(block.endMin/60).toString().padStart(2,'0')}:${(block.endMin%60).toString().padStart(2,'0')}`,
                            x: e.clientX - rect.left
                          });
                        }}
                        onMouseMove={(e) => {
                          const rect = e.currentTarget.parentNode.getBoundingClientRect();
                          setHoveredBlock(prev => prev ? { ...prev, x: e.clientX - rect.left } : null);
                        }}
                        onMouseLeave={() => setHoveredBlock(null)}
                      />
                    );
                  })}
                </div>
                
                {hoveredBlock && (
                  <div className="timeline-tooltip glass-panel" style={{ left: `${hoveredBlock.x}px` }}>
                    <div className="tooltip-status">
                      <div className={`status-dot ${hoveredBlock.statusState === 'online' ? 'online' : hoveredBlock.statusState === 'offline' ? 'error' : 'offline'}`} />
                      {hoveredBlock.statusState === 'online' ? 'Grid Online' : hoveredBlock.statusState === 'offline' ? 'Load Shedding' : 'No Telemetry'}
                    </div>
                    <div className="tooltip-time">
                      {hoveredBlock.start} - {hoveredBlock.end}
                    </div>
                  </div>
                )}

                <div className="timeline-labels">
                  <span>00:00</span>
                  <span>06:00</span>
                  <span>12:00</span>
                  <span>18:00</span>
                  <span>23:59</span>
                </div>
              </div>

              {/* 3 Pills Row */}
              <div className="timeline-pills-row">
                <div className="timeline-pill shedding">
                  <AlertTriangle size={24} />
                  <div className="pill-info">
                    <span className="pill-label">Total Load Shedding</span>
                    <span className="pill-val">{formatDuration(totalSheddingMins)}</span>
                  </div>
                </div>
                
                <div className="timeline-pills-sub-row">
                  <div className="timeline-pill import">
                    <Zap size={24} />
                    <div className="pill-info">
                      <span className="pill-label">Total Grid Import</span>
                      <span className="pill-val">
                        {dailyScrapedTotals ? (dailyScrapedTotals.gridImport || 0).toFixed(1) : '0.0'} <span className="pill-unit">kWh</span>
                      </span>
                    </div>
                  </div>

                  <div className="timeline-pill export">
                    <Activity size={24} />
                    <div className="pill-info">
                      <span className="pill-label">Total Grid Export</span>
                      <span className="pill-val">
                        {dailyScrapedTotals ? (dailyScrapedTotals.gridExport || 0).toFixed(1) : '0.0'} <span className="pill-unit">kWh</span>
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}

        </div>
      </div>
    </div>
  );
}
