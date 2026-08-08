import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { LayoutDashboard } from 'lucide-react';
import EnergyFlowDiagram from '../components/EnergyFlowDiagram';
import InverterSelector from '../components/InverterSelector';
import { usePocketBase } from '../context/PocketBaseContext';
import { useTelemetry } from '../context/TelemetryContext';
import './Dashboard.css';

export const CANDIDATE_BACKEND_URLS = [
  'https://huz-solar.duckdns.org:8888',
  'http://192.168.18.49:8000'
].filter(Boolean);

export default function Dashboard() {
  const { isConnected: isPbConnected } = usePocketBase();
  const { telemetry, selectedInverter, handleInverterChange } = useTelemetry();

  const [headerSlot, setHeaderSlot] = useState(null);

  // Find the portal target after mount
  useEffect(() => {
    setHeaderSlot(document.getElementById('mobile-header-slot'));
  }, []);

  // Portal: inject inverter selector INTO the SolarDash mobile header
  const mobileHeaderControls = headerSlot ? createPortal(
    <InverterSelector 
      selectedInverter={selectedInverter} 
      onChange={handleInverterChange} 
    />,
    headerSlot
  ) : null;

  return (
    <div className="dashboard-main-container">
      {/* Portal renders into the Layout mobile header */}
      {mobileHeaderControls}

      {/* Desktop-only header */}
      <div className="page-header glass-panel desktop-only">
        <div className="header-title-box">
          <LayoutDashboard className="header-icon" size={24} />
          <div>
            <h2>Solar Command Matrix</h2>
            <p className="subtitle">
              Real-time Live Vector Flow {telemetry.connectedUrl && `(${telemetry.connectedUrl.includes('192.168') ? 'LAN' : telemetry.connectedUrl.includes('100.97') ? 'Tailscale' : 'DuckDNS'})`}
            </p>
          </div>
        </div>

        <div className="header-controls">
          <InverterSelector 
            selectedInverter={selectedInverter} 
            onChange={handleInverterChange} 
          />
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
