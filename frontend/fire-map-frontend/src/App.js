import React, { useState } from 'react';
import './App.css';
import { MapContainer, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

function App() {
  const [activeDrawer, setActiveDrawer] = useState(null);

  const toggleDrawer = (drawer) => {
    setActiveDrawer(activeDrawer === drawer ? null : drawer);
  };

  return (
    <div className="App">
      <nav className="navbar">
        <h1 className="logo">🔥 FireMap</h1>
        <button className="login-btn" onClick={() => alert("Login popup coming soon!")}>Login</button>
      </nav>

      <main className="main-map">
        <MapContainer
          center={[54.0, -102.0]}
          zoom={4}
          scrollWheelZoom={true}
          style={{ height: '100%', width: '100%' }}
          maxBounds={[[5, -170], [85, -30]]}
          maxBoundsViscosity={1.0}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; OpenStreetMap'
          />
        </MapContainer>

        {/* Floating buttons */}
        <div className="bottom-buttons">
          {['Legend', 'Layers', 'Filters'].map((label) => (
            <div key={label} className="drawer-wrapper">
              <button className="floating-btn" onClick={() => toggleDrawer(label)}>{label}</button>
              {activeDrawer === label && (
                <div className="drawer">
                  <h4>{label}</h4>
                  {label === 'Legend' && (
                    <ul>
                      <li>🟡 Low Confidence</li>
                      <li>🟠 Medium Confidence</li>
                      <li>🔴 High Confidence</li>
                    </ul>
                  )}
                  {label === 'Layers' && (
                    <div>
                      <label><input type="checkbox" /> MODIS</label><br />
                      <label><input type="checkbox" /> VIIRS</label><br />
                      <label><input type="checkbox" /> LANDSAT</label><br />
                      <label><input type="checkbox" /> GOES</label>
                    </div>
                  )}
                  {label === 'Filters' && (
                    <div>
                      <label>Confidence Threshold</label><br />
                      <input type="range" min="0" max="100" />
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

export default App;
