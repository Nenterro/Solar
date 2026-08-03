import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Sliders } from 'lucide-react';
import DashboardWidgetCard, { WIDGET_TYPES } from '../components/Dashboard/DashboardWidgets';
import AddDashboardWidgetModal from '../components/Dashboard/AddDashboardWidgetModal';
import InverterSelector from '../components/InverterSelector';
import { CANDIDATE_BACKEND_URLS } from './Dashboard';
import './Widgets.css';

const DEFAULT_WIDGETS = [
  { id: '1', type: 'battery_telemetry' },
  { id: '2', type: 'grid_status' }
];

export default function Widgets() {
  const [selectedInverter, setSelectedInverter] = useState(() => {
    return localStorage.getItem('solar_selected_inverter') || 'all';
  });

  const handleInverterChange = (val) => {
    setSelectedInverter(val);
    localStorage.setItem('solar_selected_inverter', val);
  };

  const [activeWidgets, setActiveWidgets] = useState(() => {
    const saved = localStorage.getItem('solar_dashboard_widgets_v2');
    return saved ? JSON.parse(saved) : DEFAULT_WIDGETS;
  });

  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  const [telemetry, setTelemetry] = useState({
    batteryPower: 0.0,
    batteryLevel: 70,
    gridPower: 0.0
  });

  useEffect(() => {
    localStorage.setItem('solar_dashboard_widgets_v2', JSON.stringify(activeWidgets));
  }, [activeWidgets]);

  useEffect(() => {
    let isMounted = true;

    const fetchTelemetry = async () => {
      for (const baseUrl of CANDIDATE_BACKEND_URLS) {
        try {
          const res = await fetch(`${baseUrl}/api/telemetry?inverter=${selectedInverter}`, {
            signal: AbortSignal.timeout(3000)
          });
          if (res.ok) {
            const data = await res.json();
            if (isMounted) {
              setTelemetry({
                batteryPower: data.battery_power_kw ?? 0.0,
                batteryLevel: data.battery_capacity_pct ?? 70,
                gridPower: data.grid_power_kw ?? 0.0
              });
            }
            break;
          }
        } catch (err) {
          // Try next URL
        }
      }
    };

    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 5000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [selectedInverter]);

  const handleAddWidget = (widgetType) => {
    const newWidget = { id: Date.now().toString(), type: widgetType };
    setActiveWidgets([...activeWidgets, newWidget]);
    setIsAddModalOpen(false);
  };

  const handleRemoveWidget = (id) => {
    setActiveWidgets(activeWidgets.filter(w => w.id !== id));
  };

  return (
    <motion.div
      className="widgets-page-container"
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* Header */}
      <div className="widgets-header-row">
        <div>
          <h2 className="page-title">System Telemetry & Widgets</h2>
          <p className="page-subtitle">Detailed Battery Storage, Grid Outage & Custom Telemetry Cards</p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <InverterSelector selectedInverter={selectedInverter} onChange={handleInverterChange} />
          {activeWidgets.length < WIDGET_TYPES.length && (
            <button className="add-widget-header-btn" onClick={() => setIsAddModalOpen(true)}>
              <Plus size={16} /> Add Widget
            </button>
          )}
        </div>
      </div>

      {/* Grid of Widget Cards */}
      <div className="widgets-grid-layout">
        {activeWidgets.map(widget => (
          <DashboardWidgetCard 
            key={widget.id} 
            widget={widget} 
            onRemove={() => handleRemoveWidget(widget.id)}
            batteryPower={telemetry.batteryPower}
            batteryLevel={telemetry.batteryLevel}
            gridPower={telemetry.gridPower}
          />
        ))}

        {activeWidgets.length < WIDGET_TYPES.length && (
          <div className="add-widget-card glass-panel" onClick={() => setIsAddModalOpen(true)}>
            <div className="add-icon-circle">
              <Plus size={28} />
            </div>
            <span className="add-card-text">Add Telemetry Widget</span>
          </div>
        )}
      </div>

      <div className="widgets-bottom-spacer" />

      <AnimatePresence>
        {isAddModalOpen && (
          <AddDashboardWidgetModal
            onClose={() => setIsAddModalOpen(false)}
            onAdd={handleAddWidget}
            activeWidgets={activeWidgets}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}
