import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Battery from './pages/Battery';
import Graphs from './pages/Graphs';
import Data from './pages/Data';
import Settings from './pages/Settings';
import { PocketBaseProvider } from './context/PocketBaseContext';

export default function App() {
  return (
    <PocketBaseProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="battery" element={<Battery />} />
            <Route path="graphs" element={<Graphs />} />
            <Route path="data" element={<Data />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </PocketBaseProvider>
  );
}
