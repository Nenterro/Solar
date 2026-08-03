import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import EnergyFlowDiagram from '../components/EnergyFlowDiagram';
import InverterSelector from '../components/InverterSelector';
import { usePocketBase } from '../context/PocketBaseContext';
import './Dashboard.css';

export const getCandidateBackendUrls = () => {
  const custom = localStorage.getItem('solar_custom_backend_url');
  return Array.from(new Set([
    custom,
    'http://192.168.18.49:8000',
    import.meta.env.VITE_BACKEND_URL,
    'http://localhost:8000',
    'http://100.97.146.42:8000',
    'https://huz-solar.duckdns.org'
  ])).filter(Boolean);
};

export const CANDIDATE_BACKEND_URLS = [
  'http://192.168.18.49:8000',
  import.meta.env.VITE_BACKEND_URL,
  'http://localhost:8000',
  'http://100.97.146.42:8000',
  'https://huz-solar.duckdns.org'
].filter(Boolean);

export default function Dashboard() {
  const { isConnected: isPbConnected } = usePocketBase();

  const [selectedInverter, setSelectedInverter] = useState(() => {
    return localStorage.getItem('solar_selected_inverter') || 'all';
  });

  const telemetryCache = useRef({});
  const [headerSlot, setHeaderSlot] = useState(null);

  // Find the portal target after mount
  useEffect(() => {
    setHeaderSlot(document.getElementById('mobile-header-slot'));
  }, []);

  const [telemetry, setTelemetry] = useState({
    solarPower: 0.0,
    batteryPower: 0.0,
    batteryLevel: 70,
    gridPower: 0.0,
    homeLoad: 0.0,
    isBackendOnline: false,
    connectedUrl: ''
  });

  const handleInverterChange = (val) => {
    setSelectedInverter(val);
    localStorage.setItem('solar_selected_inverter', val);

    if (telemetryCache.current[val]) {
      const cached = telemetryCache.current[val];
      setTelemetry(prev => ({
        ...prev,
        solarPower: cached.solar_power_kw ?? 0.0,
        batteryPower: cached.battery_power_kw ?? 0.0,
        batteryLevel: cached.battery_capacity_pct ?? 70,
        gridPower: cached.grid_power_kw ?? 0.0,
        homeLoad: cached.ac_output_power_kw ?? 0.0,
      }));
    }
  };

  useEffect(() => {
    let isMounted = true;

    const fetchBackendTelemetry = async () => {
      let fetchedSuccess = false;
      const candidates = getCandidateBackendUrls();

      for (const baseUrl of candidates) {
        try {
          const res = await fetch(`${baseUrl}/api/telemetry?inverter=${selectedInverter}`, {
            signal: AbortSignal.timeout(3500)
          });
          if (res.ok) {
            const data = await res.json();
            if (isMounted) {
              telemetryCache.current[selectedInverter] = data;
              setTelemetry({
                solarPower: typeof data.solar_power_kw === 'number' ? data.solar_power_kw : 0.0,
                batteryPower: typeof data.battery_power_kw === 'number' ? data.battery_power_kw : 0.0,
                batteryLevel: typeof data.battery_capacity_pct === 'number' ? data.battery_capacity_pct : 70,
                gridPower: typeof data.grid_power_kw === 'number' ? data.grid_power_kw : 0.0,
                homeLoad: typeof data.ac_output_power_kw === 'number' ? data.ac_output_power_kw : 0.0,
                isBackendOnline: true,
                connectedUrl: baseUrl
              });
            }
            fetchedSuccess = true;
            break;
          }
        } catch (err) {
          // Try next candidate URL
        }
      }

      if (!fetchedSuccess && isMounted) {
        setTelemetry(prev => ({ 
          ...prev, 
          isBackendOnline: false, 
          connectedUrl: '' 
        }));
      }
    };

    fetchBackendTelemetry();
    const interval = setInterval(fetchBackendTelemetry, 5000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [selectedInverter]);

  // Portal: inject inverter selector + dot INTO the SolarDash mobile header
  const mobileHeaderControls = headerSlot ? createPortal(
    <>
      <InverterSelector 
        selectedInverter={selectedInverter} 
        onChange={handleInverterChange} 
      />
      <div className={`conn-dot ${telemetry.isBackendOnline ? 'online' : 'offline'}`} />
    </>,
    headerSlot
  ) : null;

  return (
    <div className="dashboard-main-container">
      {/* Portal renders into the Layout mobile header */}
      {mobileHeaderControls}

      {/* Desktop-only header */}
      <div className="dashboard-header-row desktop-only">
        <div>
          <h2 className="dash-title">Solar Command Matrix</h2>
          <p className="dash-subtitle">
            Real-time Live Vector Flow {telemetry.connectedUrl && `(${telemetry.connectedUrl.includes('192.168') ? 'LAN' : telemetry.connectedUrl.includes('100.97') ? 'Tailscale' : 'DuckDNS'})`}
          </p>
        </div>

        <div className="header-status-group">
          <InverterSelector 
            selectedInverter={selectedInverter} 
            onChange={handleInverterChange} 
          />
          <div className="status-badge glass-panel">
            <div className={`conn-dot ${telemetry.isBackendOnline ? 'online' : 'offline'}`} />
            <span>
              {telemetry.isBackendOnline ? 'Backend Connected' : 'Demo Mode'}
            </span>
          </div>
        </div>
      </div>

      {/* Main Energy Flow Matrix */}
      <div className="matrix-canvas-wrapper">
        <EnergyFlowDiagram 
          solarPower={telemetry.solarPower}
          batteryPower={telemetry.batteryPower}
          batteryLevel={telemetry.batteryLevel}
          gridPower={telemetry.gridPower}
          homeLoad={telemetry.homeLoad}
        />
      </div>
    </div>
  );
}
