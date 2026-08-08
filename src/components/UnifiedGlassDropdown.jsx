import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, Check } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import './UnifiedGlassDropdown.css';

export default function UnifiedGlassDropdown({
  label,
  options = [],
  value,
  onChange,
  icon: PrefixIcon,
  placeholder = 'Select option...',
  disabled = false,
  className = ''
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0, width: 0 });
  const containerRef = useRef(null);
  const triggerRef = useRef(null);

  const selectedOpt = options.find(opt => opt.value === value || opt.id === value || opt.cmd === value);

  // Compute position on open or window resize/scroll
  const updatePosition = () => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setCoords({
        top: rect.bottom + window.scrollY + 6,
        left: rect.left + window.scrollX,
        width: Math.max(rect.width, 160)
      });
    }
  };

  useEffect(() => {
    if (isOpen) {
      updatePosition();
      window.addEventListener('resize', updatePosition);
      window.addEventListener('scroll', updatePosition, true);
    }
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [isOpen]);

  // Close dropdown on click outside or Escape key
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        containerRef.current && !containerRef.current.contains(e.target) &&
        !e.target.closest('.unified-glass-dropdown-portal-menu')
      ) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') setIsOpen(false);
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const handleSelect = (optValue) => {
    onChange(optValue);
    setIsOpen(false);
  };

  const menuMarkup = (
    <AnimatePresence>
      {isOpen && (
        <motion.ul
          className="unified-glass-dropdown-menu unified-glass-dropdown-portal-menu"
          style={{
            position: 'absolute',
            top: `${coords.top}px`,
            left: `${coords.left}px`,
            width: `${coords.width}px`,
            zIndex: 999999
          }}
          initial={{ opacity: 0, y: -6, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -6, scale: 0.98 }}
          transition={{ duration: 0.15 }}
        >
          {options.map((opt) => {
            const optVal = opt.value !== undefined ? opt.value : (opt.id !== undefined ? opt.id : opt.cmd);
            const isSelected = optVal === value;
            const ItemIcon = opt.icon;

            return (
              <li
                key={optVal}
                className={`dropdown-item ${isSelected ? 'selected' : ''}`}
                onClick={() => handleSelect(optVal)}
              >
                <div className="dropdown-item-left">
                  {ItemIcon && <ItemIcon size={16} className="dropdown-item-icon" />}
                  <span>{opt.label || opt.name}</span>
                </div>
                {isSelected && <Check size={14} className="item-check-icon" />}
              </li>
            );
          })}
        </motion.ul>
      )}
    </AnimatePresence>
  );

  return (
    <div className={`unified-glass-dropdown ${isOpen ? 'open' : ''} ${className}`} ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        className="unified-glass-dropdown-trigger"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
      >
        {label && <span className="embedded-field-label">{label}</span>}
        <div className="dropdown-trigger-body">
          {PrefixIcon && <PrefixIcon size={14} className="select-prefix-icon" />}
          <span className="dropdown-selected-label">
            {selectedOpt ? (selectedOpt.label || selectedOpt.name) : placeholder}
          </span>
        </div>
        <ChevronDown size={14} className={`dropdown-chevron-icon ${isOpen ? 'rotate' : ''}`} />
      </button>

      {createPortal(menuMarkup, document.body)}
    </div>
  );
}
