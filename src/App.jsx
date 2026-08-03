import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Battery from './pages/Battery';
import Grid from './pages/Grid';
import Graphs from './pages/Graphs';
import Data from './pages/Data';
import Settings from './pages/Settings';
import { PocketBaseProvider } from './context/PocketBaseContext';
import { TelemetryProvider } from './context/TelemetryContext';

export default function App() {
  return (
    <PocketBaseProvider>
      <TelemetryProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="battery" element={<Battery />} />
              <Route path="grid" element={<Grid />} />
              <Route path="graphs" element={<Graphs />} />
              <Route path="data" element={<Data />} />
              <Route path="settings" element={<Settings />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </TelemetryProvider>
    </PocketBaseProvider>
  );
}
