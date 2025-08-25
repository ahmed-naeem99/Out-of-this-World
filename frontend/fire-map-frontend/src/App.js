import React from 'react';
import './App.css';
import MapComponent from './MapComponent';

function App() {
  return (
    <div className="App">
      <nav className="navbar">
        <div className="navbar-brand">
          <h1 className="logo">🔥 FireWatch</h1>
          <span className="tagline">Real-time Wildfire Monitoring</span>
        </div>
        <button className="login-btn" onClick={() => alert("Login feature coming soon!")}>
          Sign In
        </button>
      </nav>

      <div className="main-content">
        <MapComponent />
      </div>
    </div>
  );
}

export default App;