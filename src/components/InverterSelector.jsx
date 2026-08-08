import { Cpu } from 'lucide-react';
import UnifiedGlassDropdown from './UnifiedGlassDropdown';

export const INVERTER_OPTIONS = [
  { value: 'all', label: 'All Inverters' },
  { value: 'inv1', label: 'Inverter 1' },
  { value: 'inv2', label: 'Inverter 2' },
  { value: 'inv3', label: 'Inverter 3' },
];

export default function InverterSelector({ selectedInverter, onChange }) {
  return (
    <div style={{ minWidth: '150px' }}>
      <UnifiedGlassDropdown 
        options={INVERTER_OPTIONS}
        value={selectedInverter}
        onChange={onChange}
        icon={Cpu}
      />
    </div>
  );
}
