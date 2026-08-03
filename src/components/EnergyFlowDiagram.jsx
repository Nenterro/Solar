import { useState, useEffect } from 'react';
import { Sun } from 'lucide-react';
import './EnergyFlowDiagram.css';

export const formatPower = (valInKw) => {
  if (valInKw === undefined || valInKw === null || isNaN(valInKw)) return '0 W';
  const absKw = Math.abs(valInKw);
  if (absKw < 1.0) {
    const watts = Math.round(absKw * 1000);
    return `${watts} W`;
  }
  return `${absKw.toFixed(2)} kW`;
};

/* Reusable SVG icon components */
function SvgFilters() {
  return (
    <>
      <filter id="glow-solar" x="-30%" y="-30%" width="160%" height="160%">
        <feGaussianBlur stdDeviation="4" result="blur" />
        <feComposite in="SourceGraphic" in2="blur" operator="over" />
      </filter>
      <filter id="glow-battery" x="-30%" y="-30%" width="160%" height="160%">
        <feGaussianBlur stdDeviation="4" result="blur" />
        <feComposite in="SourceGraphic" in2="blur" operator="over" />
      </filter>
      <filter id="glow-grid" x="-30%" y="-30%" width="160%" height="160%">
        <feGaussianBlur stdDeviation="4" result="blur" />
        <feComposite in="SourceGraphic" in2="blur" operator="over" />
      </filter>
      <filter id="glow-home" x="-30%" y="-30%" width="160%" height="160%">
        <feGaussianBlur stdDeviation="4" result="blur" />
        <feComposite in="SourceGraphic" in2="blur" operator="over" />
      </filter>
    </>
  );
}

function HubIcon({ x, y }) {
  return (
    <g transform={`translate(${x}, ${y})`}>
      <circle r="34" className="hub-outer-ring" />
      <circle r="27" className="hub-inner-core" />
      <g transform="translate(-12, -12) scale(1.2)">
        <rect x="3" y="3" width="14" height="14" rx="2" fill="none" stroke="#f59e0b" strokeWidth="1.8" />
        <rect x="7" y="7" width="6" height="6" fill="#f59e0b" />
        <line x1="6" y1="0" x2="6" y2="3" stroke="#f59e0b" strokeWidth="1.5" />
        <line x1="10" y1="0" x2="10" y2="3" stroke="#f59e0b" strokeWidth="1.5" />
        <line x1="14" y1="0" x2="14" y2="3" stroke="#f59e0b" strokeWidth="1.5" />
        <line x1="6" y1="17" x2="6" y2="20" stroke="#f59e0b" strokeWidth="1.5" />
        <line x1="10" y1="17" x2="10" y2="20" stroke="#f59e0b" strokeWidth="1.5" />
        <line x1="14" y1="17" x2="14" y2="20" stroke="#f59e0b" strokeWidth="1.5" />
        <line x1="0" y1="6" x2="3" y2="6" stroke="#f59e0b" strokeWidth="1.5" />
        <line x1="0" y1="10" x2="3" y2="10" stroke="#f59e0b" strokeWidth="1.5" />
        <line x1="0" y1="14" x2="3" y2="14" stroke="#f59e0b" strokeWidth="1.5" />
        <line x1="17" y1="6" x2="20" y2="6" stroke="#f59e0b" strokeWidth="1.5" />
        <line x1="17" y1="10" x2="20" y2="10" stroke="#f59e0b" strokeWidth="1.5" />
        <line x1="17" y1="14" x2="20" y2="14" stroke="#f59e0b" strokeWidth="1.5" />
      </g>
    </g>
  );
}

function SolarIcon({ x, y, scale = 1.65 }) {
  return (
    <g transform={`translate(${x}, ${y}) scale(${scale})`}>
      <circle r="6" fill="none" stroke="#f59e0b" strokeWidth="2" />
      <line x1="0" y1="-11" x2="0" y2="-8" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
      <line x1="0" y1="8" x2="0" y2="11" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
      <line x1="-11" y1="0" x2="-8" y2="0" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
      <line x1="8" y1="0" x2="11" y2="0" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
      <line x1="-7.5" y1="-7.5" x2="-5.5" y2="-5.5" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
      <line x1="5.5" y1="5.5" x2="7.5" y2="7.5" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
      <line x1="-7.5" y1="7.5" x2="-5.5" y2="5.5" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
      <line x1="5.5" y1="-5.5" x2="7.5" y2="-7.5" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
    </g>
  );
}

function ZapIcon({ x, y, scale = 1.6, color }) {
  return (
    <g transform={`translate(${x}, ${y}) scale(${scale})`}>
      <path d="M -2 -11 L -9 1 L -2 1 L -4 11 L 8 -1 L 1 -1 Z" fill={color} />
    </g>
  );
}

function BatteryIcon({ x, y, scale = 1.6 }) {
  return (
    <g transform={`translate(${x}, ${y}) scale(${scale})`}>
      <rect x="-8" y="-6" width="14" height="12" rx="2" fill="none" stroke="#a855f7" strokeWidth="1.8" />
      <rect x="6" y="-3" width="2" height="6" fill="#a855f7" />
      <rect x="-6" y="-4" width="7" height="8" fill="#a855f7" />
    </g>
  );
}

function HomeIcon({ x, y, scale = 1.65 }) {
  return (
    <g transform={`translate(${x}, ${y}) scale(${scale})`}>
      <path d="M -8 3 L -8 8 L 8 8 L 8 3 M -10 2 L 0 -7 L 10 2" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </g>
  );
}


export default function EnergyFlowDiagram({ 
  solarPower = 0.0,
  batteryPower = 0.0,
  batteryLevel = 70,
  gridPower = 0.0,
  homeLoad = 0.0
}) {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);

  const isSolarGenerating = solarPower > 0.02;
  const isBatteryCharging = batteryPower > 0.02;
  const isBatteryDischarging = batteryPower < -0.02;
  const isGridImporting = gridPower > 0.02;
  const isGridExporting = gridPower < -0.02;

  const ANIM_DUR = "4.8s";

  const makeOrbs = (sources) => {
    return [0, 1, 2, 3, 4, 5].map((idx) => ({
      id: idx,
      color: sources[idx % sources.length],
      delay: `${(idx * 0.8).toFixed(2)}s`
    }));
  };

  const activeHomeSources = [];
  if (isSolarGenerating) activeHomeSources.push('#fbbf24');
  if (isBatteryDischarging) activeHomeSources.push('#a855f7');
  if (isGridImporting) activeHomeSources.push('#ef4444');
  if (activeHomeSources.length === 0) activeHomeSources.push('#60a5fa');
  const homeOrbs = makeOrbs(activeHomeSources);

  const batteryChargeSources = [];
  if (isSolarGenerating) batteryChargeSources.push('#fbbf24');
  if (isGridImporting) batteryChargeSources.push('#ef4444');
  if (batteryChargeSources.length === 0) batteryChargeSources.push('#fbbf24');
  const batteryChargeOrbs = makeOrbs(batteryChargeSources);

  const gridExportSources = [];
  if (isSolarGenerating) gridExportSources.push('#fbbf24');
  if (isBatteryDischarging) gridExportSources.push('#a855f7');
  if (gridExportSources.length === 0) gridExportSources.push('#fbbf24');
  const gridExportOrbs = makeOrbs(gridExportSources);

  const solarOrbs = makeOrbs(['#fbbf24']);
  const gridImportOrbs = makeOrbs(['#ef4444']);
  const batteryDischargeOrbs = makeOrbs(['#a855f7']);

  /* ==============================================
     MOBILE: Cross layout with VERTICAL side nodes
     Grid/Battery are tall+narrow (icon on top, text below)
     viewBox: 0 0 420 520
     ============================================== */
  if (isMobile) {
    // Center & positions
    const CX = 210;
    const HY = 265;  // Hub center Y
    const SY = 75;   // Solar Y
    const LY = 455;  // Load Y
    const GX = 78;   // Grid X
    const BX = 342;  // Battery X
    // All nodes use vertical layout on mobile
    const VNW = 120; // node width
    const VNH = 130; // node height
    const IBW = 56;  // icon box size

    return (
      <div className="energy-flow-card glass-panel">
        <div className="energy-flow-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sun size={18} className="header-icon" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: '700', whiteSpace: 'nowrap' }}>Live Energy Matrix</h3>
          </div>
          <div className="status-pill">
            <span className="live-dot" />
            REALTIME
          </div>
        </div>

        <div className="svg-canvas-wrapper">
          <svg viewBox="0 0 420 520" className="energy-svg-canvas">
            <defs><SvgFilters /></defs>

            {/* Motion paths — cross layout */}
            <path id="m-solar-hub" d={`M ${CX} ${SY+VNH/2} L ${CX} ${HY-34}`} fill="none" stroke="none" />
            <path id="m-grid-hub" d={`M ${GX+VNW/2} ${HY} L ${CX-34} ${HY}`} fill="none" stroke="none" />
            <path id="m-hub-grid" d={`M ${CX-34} ${HY} L ${GX+VNW/2} ${HY}`} fill="none" stroke="none" />
            <path id="m-hub-bat" d={`M ${CX+34} ${HY} L ${BX-VNW/2} ${HY}`} fill="none" stroke="none" />
            <path id="m-bat-hub" d={`M ${BX-VNW/2} ${HY} L ${CX+34} ${HY}`} fill="none" stroke="none" />
            <path id="m-hub-load" d={`M ${CX} ${HY+34} L ${CX} ${LY-VNH/2}`} fill="none" stroke="none" />

            {/* Background cables */}
            <line x1={CX} y1={SY+VNH/2} x2={CX} y2={HY-34} className="cable-base" />
            <line x1={GX+VNW/2} y1={HY} x2={CX-34} y2={HY} className="cable-base" />
            <line x1={CX+34} y1={HY} x2={BX-VNW/2} y2={HY} className="cable-base" />
            <line x1={CX} y1={HY+34} x2={CX} y2={LY-VNH/2} className="cable-base" />

            {/* Active cables */}
            {isSolarGenerating && <line x1={CX} y1={SY+VNH/2} x2={CX} y2={HY-34} className="cable-active solar-cable" filter="url(#glow-solar)" />}
            {(isGridImporting || isGridExporting) && <line x1={GX+VNW/2} y1={HY} x2={CX-34} y2={HY} className={`cable-active ${isGridExporting ? 'export-cable' : 'grid-cable'}`} filter="url(#glow-grid)" />}
            {(isBatteryCharging || isBatteryDischarging) && <line x1={CX+34} y1={HY} x2={BX-VNW/2} y2={HY} className="cable-active battery-cable" filter="url(#glow-battery)" />}
            <line x1={CX} y1={HY+34} x2={CX} y2={LY-VNH/2} className="cable-active home-cable" filter="url(#glow-home)" />

            {/* Animated orbs — distance-based dot count for consistent spacing */}
            {(() => {
              // Cable lengths in SVG units
              const solarHubLen = (HY - 34) - (SY + VNH/2);   // ~91px
              const gridHubLen = (CX - 34) - (GX + VNW/2);    // ~38px
              const hubBatLen = (BX - VNW/2) - (CX + 34);     // ~38px
              const hubLoadLen = (LY - VNH/2) - (HY + 34);    // ~91px

              const DOT_GAP = 24;     // desired pixels between dots
              const DOT_SPEED = 18;   // pixels per second — consistent across all cables

              const mobileOrbs = (sources, pathLen) => {
                const count = Math.max(1, Math.round(pathLen / DOT_GAP));
                const dur = Math.max(1.5, pathLen / DOT_SPEED);
                const delayStep = dur / count;
                return {
                  orbs: Array.from({ length: count }, (_, i) => ({
                    id: i,
                    color: sources[i % sources.length],
                    delay: `${(i * delayStep).toFixed(2)}s`
                  })),
                  dur: `${dur.toFixed(1)}s`
                };
              };

              const solar = mobileOrbs(['#fbbf24'], solarHubLen);
              const gridIn = mobileOrbs(['#ef4444'], gridHubLen);
              const gridEx = mobileOrbs(gridExportSources, gridHubLen);
              const batCh = mobileOrbs(batteryChargeSources, hubBatLen);
              const batDis = mobileOrbs(['#a855f7'], hubBatLen);
              const home = mobileOrbs(activeHomeSources, hubLoadLen);

              return (
                <>
                  {isSolarGenerating && solar.orbs.map(o => (
                    <circle key={`ms-${o.id}`} r="3.5" fill={o.color} filter="url(#glow-solar)">
                      <animateMotion dur={solar.dur} begin={o.delay} repeatCount="indefinite"><mpath href="#m-solar-hub" /></animateMotion>
                    </circle>
                  ))}
                  {isGridImporting && gridIn.orbs.map(o => (
                    <circle key={`mgi-${o.id}`} r="3.5" fill={o.color} filter="url(#glow-grid)">
                      <animateMotion dur={gridIn.dur} begin={o.delay} repeatCount="indefinite"><mpath href="#m-grid-hub" /></animateMotion>
                    </circle>
                  ))}
                  {isGridExporting && gridEx.orbs.map(o => (
                    <circle key={`mge-${o.id}`} r="3.5" fill={o.color} filter="url(#glow-solar)">
                      <animateMotion dur={gridEx.dur} begin={o.delay} repeatCount="indefinite"><mpath href="#m-hub-grid" /></animateMotion>
                    </circle>
                  ))}
                  {isBatteryCharging && batCh.orbs.map(o => (
                    <circle key={`mbc-${o.id}`} r="3.5" fill={o.color} filter="url(#glow-battery)">
                      <animateMotion dur={batCh.dur} begin={o.delay} repeatCount="indefinite"><mpath href="#m-hub-bat" /></animateMotion>
                    </circle>
                  ))}
                  {isBatteryDischarging && batDis.orbs.map(o => (
                    <circle key={`mbd-${o.id}`} r="3.5" fill={o.color} filter="url(#glow-battery)">
                      <animateMotion dur={batDis.dur} begin={o.delay} repeatCount="indefinite"><mpath href="#m-bat-hub" /></animateMotion>
                    </circle>
                  ))}
                  {home.orbs.map(o => (
                    <circle key={`mh-${o.id}`} r="3.5" fill={o.color} filter="url(#glow-home)">
                      <animateMotion dur={home.dur} begin={o.delay} repeatCount="indefinite"><mpath href="#m-hub-load" /></animateMotion>
                    </circle>
                  ))}
                </>
              );
            })()}

            {/* Hub */}
            <HubIcon x={CX} y={HY} />

            {/* SOLAR — vertical node (top) */}
            <g transform={`translate(${CX}, ${SY})`}>
              <rect x={-VNW/2} y={-VNH/2} width={VNW} height={VNH} rx="18" fill="#18181b"
                stroke={isSolarGenerating ? "#f59e0b" : "rgba(255,255,255,0.12)"} strokeWidth="2"
                filter={isSolarGenerating ? "url(#glow-solar)" : undefined} />
              <rect x={-IBW/2} y={-VNH/2+12} width={IBW} height={IBW} rx="15" fill="rgba(245,158,11,0.18)" />
              <SolarIcon x={0} y={-VNH/2+12+IBW/2} />
              <text x={0} y={VNH/2-36} fill="#94a3b8" fontSize="13" fontWeight="600" fontFamily="sans-serif" textAnchor="middle">Solar</text>
              <text x={0} y={VNH/2-14} fill="#fbbf24" fontSize="22" fontWeight="800" fontFamily="sans-serif" textAnchor="middle">{formatPower(solarPower)}</text>
            </g>

            {/* GRID — vertical tall node (left) */}
            <g transform={`translate(${GX}, ${HY})`}>
              <rect x={-VNW/2} y={-VNH/2} width={VNW} height={VNH} rx="18" fill="#18181b"
                stroke={isGridImporting ? "#ef4444" : isGridExporting ? "#10b981" : "rgba(255,255,255,0.12)"} strokeWidth="2"
                filter={isGridImporting ? "url(#glow-grid)" : isGridExporting ? "url(#glow-battery)" : undefined} />
              <rect x={-IBW/2} y={-VNH/2+12} width={IBW} height={IBW} rx="15" fill={isGridExporting ? "rgba(16,185,129,0.18)" : "rgba(239,68,68,0.18)"} />
              <ZapIcon x={0} y={-VNH/2+12+IBW/2} scale={1.6} color={isGridExporting ? "#10b981" : "#ef4444"} />
              <text x={0} y={VNH/2-46} fill="#94a3b8" fontSize="13" fontWeight="600" fontFamily="sans-serif" textAnchor="middle">Grid</text>
              <text x={0} y={VNH/2-26} fill={isGridExporting ? "#10b981" : "#ef4444"} fontSize="20" fontWeight="800" fontFamily="sans-serif" textAnchor="middle">{formatPower(gridPower)}</text>
              <text x={0} y={VNH/2-10} fill="#64748b" fontSize="11" fontWeight="600" fontFamily="sans-serif" textAnchor="middle">{isGridExporting ? "Exporting" : isGridImporting ? "Importing" : "Idle"}</text>
            </g>

            {/* BATTERY — vertical tall node (right) */}
            <g transform={`translate(${BX}, ${HY})`}>
              <rect x={-VNW/2} y={-VNH/2} width={VNW} height={VNH} rx="18" fill="#18181b"
                stroke={isBatteryCharging || isBatteryDischarging ? "#a855f7" : "rgba(255,255,255,0.12)"} strokeWidth="2"
                filter={isBatteryCharging || isBatteryDischarging ? "url(#glow-battery)" : undefined} />
              <rect x={-IBW/2} y={-VNH/2+12} width={IBW} height={IBW} rx="15" fill="rgba(168,85,247,0.18)" />
              <BatteryIcon x={0} y={-VNH/2+12+IBW/2} scale={1.6} />
              <text x={0} y={VNH/2-46} fill="#94a3b8" fontSize="13" fontWeight="600" fontFamily="sans-serif" textAnchor="middle">Battery</text>
              <text x={0} y={VNH/2-26} fill="#a855f7" fontSize="20" fontWeight="800" fontFamily="sans-serif" textAnchor="middle">{formatPower(batteryPower)}</text>
              <text x={0} y={VNH/2-10} fill="#64748b" fontSize="11" fontWeight="600" fontFamily="sans-serif" textAnchor="middle">{isBatteryCharging ? "Charging" : isBatteryDischarging ? "Discharging" : "Idle"}</text>
            </g>

            {/* LOAD — vertical node (bottom) */}
            <g transform={`translate(${CX}, ${LY})`}>
              <rect x={-VNW/2} y={-VNH/2} width={VNW} height={VNH} rx="18" fill="#18181b"
                stroke="#3b82f6" strokeWidth="2" filter="url(#glow-home)" />
              <rect x={-IBW/2} y={-VNH/2+12} width={IBW} height={IBW} rx="15" fill="rgba(59,130,246,0.18)" />
              <HomeIcon x={0} y={-VNH/2+12+IBW/2} />
              <text x={0} y={VNH/2-36} fill="#94a3b8" fontSize="13" fontWeight="600" fontFamily="sans-serif" textAnchor="middle">Load</text>
              <text x={0} y={VNH/2-14} fill="#60a5fa" fontSize="22" fontWeight="800" fontFamily="sans-serif" textAnchor="middle">{formatPower(homeLoad)}</text>
            </g>
          </svg>
        </div>
      </div>
    );
  }

  /* ==============================================
     DESKTOP: Original cross layout
     viewBox: 0 0 700 400
     ============================================== */
  return (
    <div className="energy-flow-card glass-panel">
      <div className="energy-flow-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sun size={20} className="header-icon" />
          <h3 style={{ fontSize: '1.05rem', fontWeight: '700', whiteSpace: 'nowrap' }}>Live Energy Matrix</h3>
        </div>
        <div className="status-pill">
          <span className="live-dot" />
          REALTIME
        </div>
      </div>

      <div className="svg-canvas-wrapper">
        <svg viewBox="0 0 700 400" className="energy-svg-canvas">
          <defs><SvgFilters /></defs>

          <path id="path-solar-to-hub" d="M 350 58 L 350 200" fill="none" stroke="none" />
          <path id="path-grid-to-hub" d="M 135 200 L 350 200" fill="none" stroke="none" />
          <path id="path-hub-to-grid" d="M 350 200 L 135 200" fill="none" stroke="none" />
          <path id="path-hub-to-battery" d="M 350 200 L 565 200" fill="none" stroke="none" />
          <path id="path-battery-to-hub" d="M 565 200 L 350 200" fill="none" stroke="none" />
          <path id="path-hub-to-home" d="M 350 200 L 350 342" fill="none" stroke="none" />

          <line x1="350" y1="58" x2="350" y2="200" className="cable-base" />
          <line x1="135" y1="200" x2="350" y2="200" className="cable-base" />
          <line x1="350" y1="200" x2="565" y2="200" className="cable-base" />
          <line x1="350" y1="200" x2="350" y2="342" className="cable-base" />

          {isSolarGenerating && <line x1="350" y1="58" x2="350" y2="200" className="cable-active solar-cable" filter="url(#glow-solar)" />}
          {(isGridImporting || isGridExporting) && <line x1="135" y1="200" x2="350" y2="200" className={`cable-active ${isGridExporting ? 'export-cable' : 'grid-cable'}`} filter="url(#glow-grid)" />}
          {(isBatteryCharging || isBatteryDischarging) && <line x1="350" y1="200" x2="565" y2="200" className="cable-active battery-cable" filter="url(#glow-battery)" />}
          <line x1="350" y1="200" x2="350" y2="342" className="cable-active home-cable" filter="url(#glow-home)" />

          {isSolarGenerating && solarOrbs.map(o => (
            <circle key={`s-${o.id}`} r="3.5" fill={o.color} filter="url(#glow-solar)">
              <animateMotion dur={ANIM_DUR} begin={o.delay} repeatCount="indefinite"><mpath href="#path-solar-to-hub" /></animateMotion>
            </circle>
          ))}
          {isGridImporting && gridImportOrbs.map(o => (
            <circle key={`gi-${o.id}`} r="3.5" fill={o.color} filter="url(#glow-grid)">
              <animateMotion dur={ANIM_DUR} begin={o.delay} repeatCount="indefinite"><mpath href="#path-grid-to-hub" /></animateMotion>
            </circle>
          ))}
          {isGridExporting && gridExportOrbs.map(o => (
            <circle key={`ge-${o.id}`} r="3.5" fill={o.color} filter="url(#glow-solar)">
              <animateMotion dur={ANIM_DUR} begin={o.delay} repeatCount="indefinite"><mpath href="#path-hub-to-grid" /></animateMotion>
            </circle>
          ))}
          {isBatteryCharging && batteryChargeOrbs.map(o => (
            <circle key={`bc-${o.id}`} r="3.5" fill={o.color} filter="url(#glow-battery)">
              <animateMotion dur={ANIM_DUR} begin={o.delay} repeatCount="indefinite"><mpath href="#path-hub-to-battery" /></animateMotion>
            </circle>
          ))}
          {isBatteryDischarging && batteryDischargeOrbs.map(o => (
            <circle key={`bd-${o.id}`} r="3.5" fill={o.color} filter="url(#glow-battery)">
              <animateMotion dur={ANIM_DUR} begin={o.delay} repeatCount="indefinite"><mpath href="#path-battery-to-hub" /></animateMotion>
            </circle>
          ))}
          {homeOrbs.map(o => (
            <circle key={`h-${o.id}`} r="3.5" fill={o.color} filter="url(#glow-home)">
              <animateMotion dur={ANIM_DUR} begin={o.delay} repeatCount="indefinite"><mpath href="#path-hub-to-home" /></animateMotion>
            </circle>
          ))}

          <HubIcon x={350} y={200} />

          {/* SOLAR */}
          <g transform="translate(350, 58)">
            <rect x="-110" y="-39" width="220" height="78" rx="18" fill="#18181b"
              stroke={isSolarGenerating ? "#f59e0b" : "rgba(255,255,255,0.12)"} strokeWidth="2"
              filter={isSolarGenerating ? "url(#glow-solar)" : undefined} />
            <rect x="-96" y="-28" width="56" height="56" rx="15" fill="rgba(245,158,11,0.18)" />
            <SolarIcon x={-68} y={0} />
            <text x="-24" y="-7" fill="#94a3b8" fontSize="14" fontWeight="600" fontFamily="sans-serif">Solar</text>
            <text x="-24" y="18" fill="#fbbf24" fontSize="22" fontWeight="800" fontFamily="sans-serif">{formatPower(solarPower)}</text>
          </g>

          {/* GRID */}
          <g transform="translate(135, 200)">
            <rect x="-95" y="-39" width="190" height="78" rx="18" fill="#18181b"
              stroke={isGridImporting ? "#ef4444" : isGridExporting ? "#10b981" : "rgba(255,255,255,0.12)"} strokeWidth="2"
              filter={isGridImporting ? "url(#glow-grid)" : isGridExporting ? "url(#glow-battery)" : undefined} />
            <rect x="-81" y="-28" width="56" height="56" rx="15" fill={isGridExporting ? "rgba(16,185,129,0.18)" : "rgba(239,68,68,0.18)"} />
            <ZapIcon x={-53} y={0} color={isGridExporting ? "#10b981" : "#ef4444"} />
            <text x="-12" y="-10" fill="#94a3b8" fontSize="13" fontWeight="600" fontFamily="sans-serif">Grid</text>
            <text x="-12" y="13" fill={isGridExporting ? "#10b981" : "#ef4444"} fontSize="20" fontWeight="800" fontFamily="sans-serif">{formatPower(gridPower)}</text>
            <text x="-12" y="28" fill="#64748b" fontSize="11" fontWeight="600" fontFamily="sans-serif">{isGridExporting ? "Exporting" : isGridImporting ? "Importing" : "Idle"}</text>
          </g>

          {/* BATTERY */}
          <g transform="translate(565, 200)">
            <rect x="-95" y="-39" width="190" height="78" rx="18" fill="#18181b"
              stroke={isBatteryCharging || isBatteryDischarging ? "#a855f7" : "rgba(255,255,255,0.12)"} strokeWidth="2"
              filter={isBatteryCharging || isBatteryDischarging ? "url(#glow-battery)" : undefined} />
            <rect x="-81" y="-28" width="56" height="56" rx="15" fill="rgba(168,85,247,0.18)" />
            <BatteryIcon x={-53} y={0} />
            <text x="-10" y="-10" fill="#94a3b8" fontSize="13" fontWeight="600" fontFamily="sans-serif">Battery</text>
            <text x="-10" y="13" fill="#a855f7" fontSize="20" fontWeight="800" fontFamily="sans-serif">{formatPower(batteryPower)}</text>
            <text x="-10" y="28" fill="#64748b" fontSize="11" fontWeight="600" fontFamily="sans-serif">{isBatteryCharging ? "Charging" : isBatteryDischarging ? "Discharging" : "Idle"}</text>
          </g>

          {/* LOAD */}
          <g transform="translate(350, 342)">
            <rect x="-110" y="-39" width="220" height="78" rx="18" fill="#18181b"
              stroke="#3b82f6" strokeWidth="2" filter="url(#glow-home)" />
            <rect x="-96" y="-28" width="56" height="56" rx="15" fill="rgba(59,130,246,0.18)" />
            <HomeIcon x={-68} y={0} />
            <text x="-24" y="-7" fill="#94a3b8" fontSize="14" fontWeight="600" fontFamily="sans-serif">Load</text>
            <text x="-24" y="18" fill="#60a5fa" fontSize="22" fontWeight="800" fontFamily="sans-serif">{formatPower(homeLoad)}</text>
          </g>
        </svg>
      </div>
    </div>
  );
}
