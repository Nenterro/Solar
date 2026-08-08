import { useState, useMemo, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  ChevronLeft, 
  ChevronRight, 
  Calendar as CalendarIcon, 
  Download, 
  Search, 
  ArrowUpDown, 
  Sun, 
  Gauge, 
  ArrowDownLeft, 
  ArrowUpRight, 
  BatteryCharging, 
  Zap,
  Database
} from 'lucide-react';
import { 
  format, 
  subMonths, 
  addMonths, 
  subYears, 
  addYears, 
  isSameMonth, 
  isSameYear 
} from 'date-fns';
import InverterSelector from '../components/InverterSelector';
import { useTelemetry } from '../context/TelemetryContext';
import { fetchFromBackend } from '../utils/api';
import './Data.css';

const METRICS_COLUMNS = [
  { id: 'time', label: 'Date / Period', icon: CalendarIcon, color: '#94a3b8' },
  { id: 'solar', label: 'Solar Yield', icon: Sun, color: '#fbbf24' },
  { id: 'load', label: 'Home Load', icon: Gauge, color: '#60a5fa' },
  { id: 'gridImport', label: 'Grid Import', icon: ArrowDownLeft, color: '#ef4444' },
  { id: 'gridExport', label: 'Grid Export', icon: ArrowUpRight, color: '#10b981' },
  { id: 'batteryCharge', label: 'Battery Charge', icon: BatteryCharging, color: '#a855f7' },
  { id: 'batteryDischarge', label: 'Battery Discharge', icon: Zap, color: '#c084fc' },
];

export default function Data() {
  const { telemetry } = useTelemetry() || { telemetry: {} };
  const today = useMemo(() => new Date(), []);
  const [viewMode, setViewMode] = useState('monthly'); 
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [tableData, setTableData] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  // Active inverter selection (persisted across pages)
  const [selectedInverter, setSelectedInverter] = useState(() => {
    return localStorage.getItem('solar_selected_inverter') || 'all';
  });

  const handleInverterChange = (val) => {
    setSelectedInverter(val);
    localStorage.setItem('solar_selected_inverter', val);
  };

  const [searchTerm, setSearchTerm] = useState('');
  const [sortColumn, setSortColumn] = useState('time');
  const [sortDirection, setSortDirection] = useState('desc');

  // Fetch DESSMonitor Scraped Daily & Monthly Totals from Backend (/api/dess_totals)
  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);

    const fetchDessTotals = async () => {
      try {
        let endpoint = '';
        if (viewMode === 'monthly') {
          const monthStr = format(selectedDate, 'yyyy-MM');
          endpoint = `/api/dess_totals?month=${monthStr}&inverter=${selectedInverter}`;
        } else {
          const yearStr = format(selectedDate, 'yyyy');
          endpoint = `/api/dess_totals?year=${yearStr}&inverter=${selectedInverter}`;
        }
        const data = await fetchFromBackend(endpoint);
        if (isMounted) {
          setTableData(data.totals || []);
        }
      } catch (err) {
        console.warn('Failed to fetch DESS totals:', err.message);
      }
      if (isMounted) setIsLoading(false);
    };

    fetchDessTotals();
  }, [viewMode, selectedDate, selectedInverter]);

  // Date Navigation Constraints
  const isNextDisabled = useMemo(() => {
    if (viewMode === 'monthly') return isSameMonth(selectedDate, today);
    if (viewMode === 'yearly') return isSameYear(selectedDate, today);
    return false;
  }, [viewMode, selectedDate, today]);

  const handlePrevDate = () => {
    if (viewMode === 'monthly') setSelectedDate(prev => subMonths(prev, 1));
    else if (viewMode === 'yearly') setSelectedDate(prev => subYears(prev, 1));
  };

  const handleNextDate = () => {
    if (isNextDisabled) return;
    if (viewMode === 'monthly') setSelectedDate(prev => addMonths(prev, 1));
    else if (viewMode === 'yearly') setSelectedDate(prev => addYears(prev, 1));
  };

  // Filtered & Sorted Table Rows
  const processedRows = useMemo(() => {
    if (!Array.isArray(tableData)) return [];

    let rows = tableData.filter(row => {
      const s = row.solar || 0;
      const l = row.load || 0;
      const gi = row.gridImport || 0;
      const ge = row.gridExport || 0;
      const bc = row.batteryCharge || 0;
      const bd = row.batteryDischarge || 0;

      // Skip empty zero rows
      if (s === 0 && l === 0 && gi === 0 && ge === 0 && bc === 0 && bd === 0) return false;

      return row.time && row.time.toLowerCase().includes(searchTerm.toLowerCase());
    });

    rows.sort((a, b) => {
      let aVal = a[sortColumn];
      let bVal = b[sortColumn];

      if (typeof aVal === 'string') {
        return sortDirection === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDirection === 'asc' ? (aVal || 0) - (bVal || 0) : (bVal || 0) - (aVal || 0);
    });

    return rows;
  }, [tableData, searchTerm, sortColumn, sortDirection]);

  // Total Row Calculations
  const totals = useMemo(() => {
    const sum = { solar: 0, load: 0, gridImport: 0, gridExport: 0, batteryCharge: 0, batteryDischarge: 0 };
    if (!Array.isArray(processedRows)) return sum;
    processedRows.forEach(row => {
      sum.solar += (row.solar || 0);
      sum.load += (row.load || 0);
      sum.gridImport += (row.gridImport || 0);
      sum.gridExport += (row.gridExport || 0);
      sum.batteryCharge += (row.batteryCharge || 0);
      sum.batteryDischarge += (row.batteryDischarge || 0);
    });
    return sum;
  }, [processedRows]);

  const handleSort = (colId) => {
    if (sortColumn === colId) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(colId);
      setSortDirection('asc');
    }
  };

  // Export Table Data to CSV
  const exportToCSV = () => {
    const headers = ['Date/Period', 'Solar Yield (kWh)', 'Home Load (kWh)', 'Grid Import (kWh)', 'Grid Export (kWh)', 'Battery Charge (kWh)', 'Battery Discharge (kWh)'].join(',');
    const rows = processedRows.map(r => 
      [r.time, r.solar, r.load, r.gridImport, r.gridExport, r.batteryCharge, r.batteryDischarge].join(',')
    );
    const csvContent = "data:text/csv;charset=utf-8," + [headers, ...rows].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `solar_telemetry_${selectedInverter}_${viewMode}_${format(selectedDate, 'yyyy-MM-dd')}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const dateFormattedLabel = useMemo(() => {
    if (viewMode === 'monthly') return format(selectedDate, 'MMMM yyyy');
    if (viewMode === 'yearly') return format(selectedDate, 'yyyy');
  }, [viewMode, selectedDate]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="stats-page-container"
    >
      {/* Desktop Header Panel */}
      <div className="page-header glass-panel desktop-only" style={{ marginBottom: '16px' }}>
        <div className="header-title-box">
          <Database className="header-icon" size={24} />
          <div>
            <h2>Historical Energy Data</h2>
            <p className="subtitle">Daily and monthly production and consumption records</p>
          </div>
        </div>

        <div className="header-controls">
          <InverterSelector 
            selectedInverter={selectedInverter} 
            onChange={handleInverterChange} 
          />

          <div className="timeframe-pill-selector">
            <button 
              className={`timeframe-btn ${viewMode === 'monthly' ? 'active' : ''}`}
              onClick={() => setViewMode('monthly')}
            >
              Daily Totals
            </button>
            <button 
              className={`timeframe-btn ${viewMode === 'yearly' ? 'active' : ''}`}
              onClick={() => setViewMode('yearly')}
            >
              Monthly Totals
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Mode Controls */}
      <div className="mobile-only" style={{ marginBottom: '12px', justifyContent: 'center' }}>
        <div className="timeframe-pill-selector">
          <button 
            className={`timeframe-btn ${viewMode === 'monthly' ? 'active' : ''}`}
            onClick={() => setViewMode('monthly')}
          >
            Daily Totals
          </button>
          <button 
            className={`timeframe-btn ${viewMode === 'yearly' ? 'active' : ''}`}
            onClick={() => setViewMode('yearly')}
          >
            Monthly Totals
          </button>
        </div>
      </div>

      {/* Date Navigator Bar & Actions */}
      <div className="date-navigator-card glass-panel">
        <button className="nav-arrow-btn" onClick={handlePrevDate} title="Previous">
          <ChevronLeft size={20} />
        </button>

        <div className="date-display-box">
          <CalendarIcon size={18} className="calendar-icon" />
          <span className="date-label-text">{dateFormattedLabel}</span>
        </div>

        <button 
          className={`nav-arrow-btn ${isNextDisabled ? 'disabled' : ''}`} 
          onClick={handleNextDate} 
          disabled={isNextDisabled}
          title={isNextDisabled ? "Cannot navigate to future date" : "Next"}
        >
          <ChevronRight size={20} />
        </button>
      </div>

      {/* Search & CSV Export Toolbar */}
      <div className="table-toolbar">
        <div className="table-search-box">
          <Search size={16} className="search-icon" />
          <input 
            type="text" 
            placeholder="Search date or day..." 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="table-search-input"
          />
        </div>

        <button className="csv-export-btn" onClick={exportToCSV}>
          <Download size={16} />
          Export CSV
        </button>
      </div>

      {/* Data Table Card */}
      <div className="table-card glass-panel">
        <div className="table-scroll-wrapper">
          <table className="telemetry-table">
            <thead>
              <tr>
                {METRICS_COLUMNS.map(col => {
                  const Icon = col.icon;
                  const isSorted = sortColumn === col.id;

                  return (
                    <th key={col.id} onClick={() => handleSort(col.id)} className="table-header-cell">
                      <div className="header-cell-content">
                        <Icon size={14} style={{ color: col.color }} />
                        <span>{col.label} {col.id !== 'time' ? '(kWh)' : ''}</span>
                        <ArrowUpDown size={12} className={`sort-icon ${isSorted ? 'active' : ''}`} />
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {/* Summary Totals Row */}
              <tr className="totals-row">
                <td className="period-cell font-bold">Total Sum ({processedRows.length} periods)</td>
                <td className="metric-cell val-amber">{totals.solar.toFixed(1)} kWh</td>
                <td className="metric-cell val-blue">{totals.load.toFixed(1)} kWh</td>
                <td className="metric-cell val-red">{totals.gridImport.toFixed(1)} kWh</td>
                <td className="metric-cell val-green">{totals.gridExport.toFixed(1)} kWh</td>
                <td className="metric-cell val-purple">{totals.batteryCharge.toFixed(1)} kWh</td>
                <td className="metric-cell val-light-purple">{totals.batteryDischarge.toFixed(1)} kWh</td>
              </tr>

              {/* Data Rows */}
              {processedRows.length > 0 ? (
                processedRows.map((row, idx) => (
                  <tr key={idx} className="data-row">
                    <td className="period-cell">{row.time}</td>
                    <td className="metric-cell val-amber">{row.solar}</td>
                    <td className="metric-cell val-blue">{row.load}</td>
                    <td className="metric-cell val-red">{row.gridImport}</td>
                    <td className="metric-cell val-green">{row.gridExport}</td>
                    <td className="metric-cell val-purple">{row.batteryCharge}</td>
                    <td className="metric-cell val-light-purple">{row.batteryDischarge}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="empty-table-cell">
                    {isLoading ? 'Fetching DESSMonitor totals...' : `No scraped totals found for ${dateFormattedLabel}`}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Mobile Scroll Clearance Spacer */}
      <div className="data-bottom-spacer" />
    </motion.div>
  );
}
