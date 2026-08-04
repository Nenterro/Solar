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
  const { timelineBlocks, totalSheddingMins } = useMemo(() => {
    if (!historyData || historyData.length === 0) return { timelineBlocks: [], totalSheddingMins: 0 };

    let blocks = [];
    let currentBlock = null;
    let sheddingMins = 0;

    // We assume 1440 points (1 per min) for a full day. 
    // The history API usually returns a full array filled with 0s for missing future data, 
    // but gridActive might be false for future data. We should only count up to the current time if it's 'today'.
    
    // To properly calculate percentages for the timeline, we map to 0-1440 minutes.
    historyData.forEach((record, index) => {
      // If it's today and the record time is in the future, we should probably stop or treat it as empty.
      // But let's keep it simple: the backend backfills future data with 0s, and gridActive=False.
      // We will only process up to the last known valid timestamp if it's today.
      
      const isActive = record.gridActive;
      
      if (!isActive && record.solar !== undefined) {
        // If it's literally undefined/empty (future), we shouldn't count it as load shedding.
        // Actually, db.py backfills with solar:0, load:0, etc. 
        // We will just assume if the backend provided it, it's a valid minute.
      }
      
      if (!isActive) {
        sheddingMins++;
      }

      if (!currentBlock) {
        currentBlock = { isActive, startIdx: index, endIdx: index };
      } else if (currentBlock.isActive === isActive) {
        currentBlock.endIdx = index;
      } else {
        blocks.push(currentBlock);
        currentBlock = { isActive, startIdx: index, endIdx: index };
      }
    });

    if (currentBlock) blocks.push(currentBlock);

    // If viewing today, we should subtract the future minutes from load shedding calculation
    if (isSameDay(selectedDate, today)) {
      const now = new Date();
      const currentMin = now.getHours() * 60 + now.getMinutes();
      
      // Filter out blocks that are entirely in the future
      blocks = blocks.filter(b => b.startIdx <= currentMin);
      
      // Cap the last block to current time
      if (blocks.length > 0) {
        const lastBlock = blocks[blocks.length - 1];
        if (lastBlock.endIdx > currentMin) {
          lastBlock.endIdx = currentMin;
        }
      }
      
      // Recalculate shedding mins strictly up to current time
      sheddingMins = 0;
      for (let i = 0; i <= currentMin; i++) {
        if (historyData[i] && !historyData[i].gridActive) sheddingMins++;
      }
    }

    return { timelineBlocks: blocks, totalSheddingMins: sheddingMins };
  }, [historyData, selectedDate, today]);

  const formatDuration = (mins) => {
    if (mins === 0) return "0h 0m";
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${h}h ${m}m`;
  };

  // Mobile Header Dot Portal
  const mobileHeaderControls = headerSlot ? createPortal(
    <div className={`status-badge glass-panel`} style={{ padding: '4px 12px' }}>
      <div className="status-dot" style={{ backgroundColor: isOnline ? '#10b981' : '#ef4444', boxShadow: `0 0 8px ${isOnline ? '#10b981' : '#ef4444'}` }}></div>
    </div>,
    headerSlot
  ) : null;

  return (
    <div className="grid-page">
      {mobileHeaderControls}
      <div className="grid-header glass-panel desktop-only">
        <div className="title-wrapper">
          <Power size={32} style={{ color: isOnline ? '#10b981' : '#ef4444' }} />
          <div>
            <h1 className="page-title">WAPDA Grid Status</h1>
            <p className="subtitle">Real-time Utility Monitoring</p>
          </div>
        </div>
        <div className={`status-badge ${isOnline ? 'online' : 'offline'}`}>
          <div className="status-dot"></div>
          {isOnline ? 'Online' : 'Load Shedding (Offline)'}
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
                    const leftPct = (block.startIdx / 1440) * 100;
                    const widthPct = ((block.endIdx - block.startIdx + 1) / 1440) * 100;
                    
                    return (
                      <div 
                        key={i}
                        className={`timeline-segment ${block.isActive ? 'active' : 'inactive'}`}
                        style={{
                          left: `${leftPct}%`,
                          width: `${widthPct}%`
                        }}
                        onMouseEnter={(e) => {
                          const rect = e.currentTarget.parentNode.getBoundingClientRect();
                          setHoveredBlock({
                            isActive: block.isActive,
                            start: `${Math.floor(block.startIdx/60).toString().padStart(2,'0')}:${(block.startIdx%60).toString().padStart(2,'0')}`,
                            end: `${Math.floor(block.endIdx/60).toString().padStart(2,'0')}:${(block.endIdx%60).toString().padStart(2,'0')}`,
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
                      <div className={`status-dot ${hoveredBlock.isActive ? 'online' : 'offline'}`} />
                      {hoveredBlock.isActive ? 'Online' : 'Offline'}
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
