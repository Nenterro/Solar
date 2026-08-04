import { createContext, useContext, useState, useEffect, useRef } from 'react';

const TelemetryContext = createContext();

export const getCandidateBackendUrls = () => {
  const custom = localStorage.getItem('solar_custom_backend_url');
  return Array.from(new Set([
    custom,
    'https://huz-solar.duckdns.org:8888',
    'http://192.168.18.49:8000',
    import.meta.env.VITE_BACKEND_URL,
    'http://localhost:8000',
    'http://100.97.146.42:8000'
  ])).filter(Boolean);
};

export function TelemetryProvider({ children }) {
  const [selectedInverter, setSelectedInverter] = useState(() => {
    return localStorage.getItem('solar_selected_inverter') || 'all';
  });

  const telemetryCache = useRef({});

  const [telemetry, setTelemetry] = useState({
    solarPower: 0.0,
    batteryPower: 0.0,
    batteryLevel: 0,
    gridPower: 0.0,
    homeLoad: 0.0,
    gridVoltage: 0.0,
    gridFrequency: 0.0,
    gridActive: false,
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
        solarPower: typeof cached.solar_power_kw === 'number' ? cached.solar_power_kw : 0.0,
        batteryPower: typeof cached.battery_power_kw === 'number' ? cached.battery_power_kw : 0.0,
        batteryLevel: typeof cached.battery_capacity_pct === 'number' ? cached.battery_capacity_pct : 0,
        gridPower: typeof cached.grid_power_kw === 'number' ? cached.grid_power_kw : 0.0,
        homeLoad: typeof cached.ac_output_power_kw === 'number' ? cached.ac_output_power_kw : 0.0,
        gridVoltage: typeof cached.grid_voltage === 'number' ? cached.grid_voltage : 0.0,
        gridFrequency: typeof cached.grid_frequency === 'number' ? cached.grid_frequency : 0.0,
        gridActive: typeof cached.grid_active === 'boolean' ? cached.grid_active : false,
      }));
    } else {
        setTelemetry(prev => ({
            ...prev,
            solarPower: 0.0,
            batteryPower: 0.0,
            gridPower: 0.0,
            homeLoad: 0.0,
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
                batteryLevel: typeof data.battery_capacity_pct === 'number' ? data.battery_capacity_pct : 0,
                gridPower: typeof data.grid_power_kw === 'number' ? data.grid_power_kw : 0.0,
                homeLoad: typeof data.ac_output_power_kw === 'number' ? data.ac_output_power_kw : 0.0,
                gridVoltage: typeof data.grid_voltage === 'number' ? data.grid_voltage : 0.0,
                gridFrequency: typeof data.grid_frequency === 'number' ? data.grid_frequency : 0.0,
                gridActive: typeof data.grid_active === 'boolean' ? data.grid_active : false,
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
          connectedUrl: '',
          solarPower: 0.0,
          batteryPower: 0.0,
          gridPower: 0.0,
          homeLoad: 0.0
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

  return (
    <TelemetryContext.Provider value={{ telemetry, selectedInverter, handleInverterChange }}>
      {children}
    </TelemetryContext.Provider>
  );
}

export function useTelemetry() {
  return useContext(TelemetryContext);
}
