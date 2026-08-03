import { Cpu } from 'lucide-react';
import './InverterSelector.css';

export const INVERTER_OPTIONS = [
  { id: 'all', label: 'All Inverters' },
  { id: 'inv1', label: 'Inverter 1' },
  { id: 'inv2', label: 'Inverter 2' },
  { id: 'inv3', label: 'Inverter 3' },
];

export default function InverterSelector({ selectedInverter, onChange }) {
  return (
    <div className="inverter-selector-wrapper">
      <Cpu size={16} className="inverter-selector-icon" />
      <select 
        value={selectedInverter} 
        onChange={(e) => onChange(e.target.value)}
        className="inverter-selector-dropdown"
      >
        {INVERTER_OPTIONS.map(opt => (
          <option key={opt.id} value={opt.id} className="inverter-option">
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
