import { useState, useEffect } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { LayoutDashboard, Sliders, LineChart, Database, Settings, Sun, Pin, PinOff, Battery, Power, MoreHorizontal } from 'lucide-react';
import './Layout.css';

const MAIN_NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/battery', label: 'Battery', icon: Battery },
  { path: '/grid', label: 'Grid', icon: Power },
  { path: '/graphs', label: 'Graphs', icon: LineChart },
  { path: '/data', label: 'Data', icon: Database },
];

const SETTINGS_ITEM = { path: '/settings', label: 'Settings', icon: Settings };

// Mobile Nav Structure
const MOBILE_MAIN_ITEMS = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/battery', label: 'Battery', icon: Battery },
  { path: '/grid', label: 'Grid', icon: Power },
  { path: '/graphs', label: 'Graphs', icon: LineChart },
];

const MOBILE_MORE_ITEMS = [
  { path: '/data', label: 'Data', icon: Database },
  { path: '/settings', label: 'Settings', icon: Settings },
];

function Sidebar({ isPinned, togglePin }) {
  return (
    <div className={`sidebar-wrapper desktop-only ${isPinned ? 'pinned' : 'unpinned'}`}>
      <aside className={`sidebar glass-panel ${isPinned ? 'pinned' : 'unpinned'}`}>
        <div className="sidebar-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Sun size={28} style={{ color: 'var(--accent-color)' }} />
            <h1 className="title">Solar<span style={{ color: 'var(--accent-color)' }}>Dash</span></h1>
          </div>
          <button className="pin-btn" onClick={togglePin} title={isPinned ? "Unpin Sidebar" : "Pin Sidebar"}>
            {isPinned ? <PinOff size={16} /> : <Pin size={16} />}
          </button>
        </div>

        <nav className="sidebar-nav">
          {MAIN_NAV_ITEMS.map((item) => (
            <NavLink 
              key={item.path} 
              to={item.path} 
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <item.icon size={20} />
              <span className="nav-label">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <NavLink 
            to={SETTINGS_ITEM.path} 
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <SETTINGS_ITEM.icon size={20} />
            <span className="nav-label">{SETTINGS_ITEM.label}</span>
          </NavLink>
        </div>
      </aside>
    </div>
  );
}

function BottomNav() {
  const [showMore, setShowMore] = useState(false);
  const location = useLocation();

  // Close more menu when navigating
  useEffect(() => {
    setShowMore(false);
  }, [location]);

  return (
    <>
      <nav className="bottom-nav mobile-only">
        {MOBILE_MAIN_ITEMS.map((item) => (
          <NavLink 
            key={item.path} 
            to={item.path} 
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            title={item.label}
          >
            <item.icon size={22} />
          </NavLink>
        ))}
        <button 
          className={`nav-item ${showMore ? 'active' : ''}`} 
          onClick={() => setShowMore(!showMore)}
        >
          <MoreHorizontal size={22} />
        </button>
      </nav>

      {/* More Menu Popup */}
      {showMore && (
        <div className="mobile-more-overlay mobile-only" onClick={() => setShowMore(false)}>
          <div className="mobile-more-menu glass-panel" onClick={e => e.stopPropagation()}>
            <div className="more-menu-header">More</div>
            {MOBILE_MORE_ITEMS.map(item => (
              <NavLink 
                key={item.path}
                to={item.path}
                className={({ isActive }) => `more-menu-item ${isActive ? 'active' : ''}`}
                onClick={() => setShowMore(false)}
              >
                <item.icon size={20} />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

export default function Layout() {
  const [isSidebarPinned, setIsSidebarPinned] = useState(true);
  const location = useLocation();
  const isDashboard = location.pathname === '/';

  return (
    <div className="app-container">
      <Sidebar isPinned={isSidebarPinned} togglePin={() => setIsSidebarPinned(!isSidebarPinned)} />
      <div className="main-wrapper">
        <header className="mobile-only glass-panel mobile-top-bar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Sun size={24} style={{ color: 'var(--accent-color)' }} />
            <h1 style={{ fontSize: '1.1rem', fontWeight: '700' }}>Solar<span style={{ color: 'var(--accent-color)' }}>Dash</span></h1>
          </div>
          {/* Portal target: Dashboard injects inverter selector + dot here */}
          <div id="mobile-header-slot" style={{ display: 'flex', alignItems: 'center', gap: '10px' }} />
        </header>

        <main className={`main-content ${isDashboard ? 'dashboard-active' : ''}`}>
          <div className="page-transition-wrapper">
            <Outlet />
            {!isDashboard && <div className="mobile-scroll-spacer mobile-only" />}
          </div>
        </main>

        <BottomNav />
      </div>
    </div>
  );
}
