import React, { useState } from "react";
import "./App.css";
import MapComponent from "./MapComponent";
import { Bell } from "lucide-react";

function App() {
  const [showNotifs, setShowNotifs] = useState(false);

  return (
    <div className="App">
      <nav className="navbar">
        <div className="navbar-brand">
          <div className="logo-container">
            
            <h1 className="logo-text">FireWatchNov17</h1>
          </div>
          <span className="tagline">Real-time Wildfire Monitoring</span>
        </div>

        <div className="navbar-actions">
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
              <p className="notif-empty">No new alerts 🔕</p>
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
        <MapComponent />
      </div>
    </div>
  );
}

export default App;
