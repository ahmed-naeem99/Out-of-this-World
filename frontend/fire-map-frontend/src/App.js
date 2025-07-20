import React from 'react';
import './App.css';
import 'leaflet/dist/leaflet.css';
import MapComponent from './MapComponent';

function App() {
  return (
    <div className="App">
      <nav className="navbar">
        <div className="navbar-title">🔥 FireMap</div>
        <button className="login-btn" onClick={() => alert('Login popup coming soon!')}>
          Sign In
        </button>
      </nav>
      <div className="map-container">
        <MapComponent />
      </div>
    </div>
  );
}

export default App;
