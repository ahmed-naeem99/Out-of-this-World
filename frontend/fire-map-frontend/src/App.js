import React, { useState } from "react";
import "./App.css";
import MapComponent from "./MapComponent";
import { Bell, Layers } from "lucide-react";

function App() {
  const [showNotifs, setShowNotifs] = useState(false);
  // Default to validated mode
  const [viewMode, setViewMode] = useState('validated'); 

  const toggleViewMode = () => {
    setViewMode(prev => prev === 'validated' ? 'raw' : 'validated');
  };

  return (
    // Add a class based on the mode for global styling (theme switching)
    <div className={`App ${viewMode === 'validated' ? 'theme-light' : 'theme-dark'}`}>
      <nav className="navbar">
        <div className="navbar-brand">
          <div className="logo-container">
            <h1 className="logo-text">FireWatch</h1>
          </div>
          <span className="tagline">
            {viewMode === 'validated' ? 'Validated Incident Monitoring' : 'Raw Sensor Data Feed'}
          </span>
        </div>

        <div className="navbar-actions">
          {/* Layer Switcher Button */}
          <button 
            className={`layer-switch-btn ${viewMode}`}
            onClick={toggleViewMode}
            title="Switch Data Layer"
          >
            <Layers size={18} />
            <span>{viewMode === 'validated' ? 'Validated Layer' : 'Raw Data Layer'}</span>
          </button>

          <button
            className="notif-btn"
            onClick={() => setShowNotifs(!showNotifs)}
            aria-label="Notifications"
          >
            <Bell size={22} />
          </button>

          {showNotifs && (
            <div className="notif-panel">
              <p className="notif-header">Notifications</p>
              <p className="notif-empty">No new alerts</p>
            </div>
          )}

          <button
            className="login-btn"
            onClick={() => alert("Login feature coming soon!")}
          >
            Sign In
          </button>
        </div>
      </nav>

      <div className="main-content">
        <MapComponent viewMode={viewMode} />
      </div>
    </div>
  );
}

export default App;