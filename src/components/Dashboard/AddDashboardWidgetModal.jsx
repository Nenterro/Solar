import { motion } from 'framer-motion';
import { X, Plus, Check } from 'lucide-react';
import { WIDGET_TYPES } from './DashboardWidgets';
import './AddDashboardWidgetModal.css';

export default function AddDashboardWidgetModal({ onClose, onAdd, activeWidgets }) {
  const activeWidgetTypes = new Set(activeWidgets.map(w => w.type));

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <motion.div 
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="add-widget-modal glass-panel"
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header">
          <h3>Add Dashboard Widget</h3>
          <button className="close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="widget-options-list">
          {WIDGET_TYPES.map(widget => {
            const isAdded = activeWidgetTypes.has(widget.id);
            const Icon = widget.icon;

            return (
              <div key={widget.id} className={`widget-option-card ${isAdded ? 'added' : ''}`}>
                <div className="option-icon-box">
                  <Icon size={24} />
                </div>
                <div className="option-info">
                  <span className="option-title">{widget.title}</span>
                  <span className="option-desc">
                    {widget.defaultSize === 'full' ? 'Full-width Chart' : 'Compact Grid Card'}
                  </span>
                </div>

                <button 
                  className={`option-action-btn ${isAdded ? 'added-btn' : 'add-btn'}`}
                  onClick={() => !isAdded && onAdd(widget.id)}
                  disabled={isAdded}
                >
                  {isAdded ? (
                    <>
                      <Check size={16} /> Added
                    </>
                  ) : (
                    <>
                      <Plus size={16} /> Add
                    </>
                  )}
                </button>
              </div>
            );
          })}
        </div>
      </motion.div>
    </div>
  );
}
