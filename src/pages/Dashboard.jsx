import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import EnergyFlowDiagram from '../components/EnergyFlowDiagram';
import InverterSelector from '../components/InverterSelector';
import { usePocketBase } from '../context/PocketBaseContext';
import { useTelemetry } from '../context/TelemetryContext';
import './Dashboard.css';

export const CANDIDATE_BACKEND_URLS = [
  'http://192.168.18.49:8000',
  import.meta.env.VITE_BACKEND_URL,
  'http://localhost:8000',
  'http://100.97.146.42:8000',
  'https://huz-solar.duckdns.org'
].filter(Boolean);

export default function Dashboard() {
  const { isConnected: isPbConnected } = usePocketBase();
  const { telemetry, selectedInverter, handleInverterChange } = useTelemetry();

  const [headerSlot, setHeaderSlot] = useState(null);

  // Find the portal target after mount
  useEffect(() => {
    setHeaderSlot(document.getElementById('mobile-header-slot'));
  }, []);

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
              {telemetry.isBackendOnline ? 'Backend Connected' : 'Disconnected'}
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
