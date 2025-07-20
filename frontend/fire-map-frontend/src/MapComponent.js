import React, { useEffect, useState } from 'react';
import './MapComponent.css';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';

const getFireIcon = (confidence_level) => {
  const colors = {
    1: '#FFD700', // Yellow
    2: '#FFA500', // Orange
    3: '#FF4500', // Bright Red
    4: '#8B0000', // Dark Red
  };

  const level = parseInt(confidence_level);
  const color = colors[level] || 'gray';

  return new L.DivIcon({
    html: `<div style="
      background-color: ${color};
      width: 24px;
      height: 24px;
      border-radius: 50%;
      border: 2px solid white;
    "></div>`,
    className: '', // Remove default Leaflet class interference
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
};

function MapComponent() {
  const [fires, setFires] = useState([]);
  const [showLegend, setShowLegend] = useState(false);
  const [showLayers, setShowLayers] = useState(false);

  useEffect(() => {
    fetch('http://localhost:5000/api/fires')
      .then((res) => res.json())
      .then((data) => setFires(data))
      .catch((err) => console.error('Failed to load fire data:', err));
  }, []);

  return (
    <div className="map-wrapper">
      <MapContainer
        center={[40, -100]}
        zoom={4}
        minZoom={3}
        maxBounds={[
          [5, -170],
          [80, -30],
        ]}
        className="leaflet-container"
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {fires.map((fire, index) => (
          <Marker
            key={index}
            position={[fire.latitude, fire.longitude]}
            icon={getFireIcon(fire.confidence_level)}
          >
            <>
              <Popup
                className="custom-popup"
                closeButton={true}
                autoPan={false}
                offset={[0, -20]} // push popup up a bit
              >
                <div className="popup-content">
                  <h3>🔥 Validated Fire</h3>
                  <p><strong>Latitude:</strong> {fire.latitude}</p>
                  <p><strong>Longitude:</strong> {fire.longitude}</p>
                  <p><strong>Confidence Level:</strong> {fire.confidence_level}</p>
                </div>
              </Popup>
            </>
          </Marker>
        ))}
      </MapContainer>

      <div className="bottom-buttons">
        <button onClick={() => setShowLegend(!showLegend)}>Legend</button>
        <button onClick={() => setShowLayers(!showLayers)}>Layers</button>
      </div>

      {showLegend && (
        <div className="drawer legend-drawer">
          <h3>🟠 Legend</h3>
          <p>Colored circles = validated fire locations</p>
          <p><span style={{ color: '#FFD700' }}>●</span> Confidence 1 (Low)</p>
          <p><span style={{ color: '#FFA500' }}>●</span> Confidence 2</p>
          <p><span style={{ color: '#FF4500' }}>●</span> Confidence 3</p>
          <p><span style={{ color: '#8B0000' }}>●</span> Confidence 4 (High)</p>
        </div>
      )}

      {showLayers && (
        <div className="drawer layers-drawer">
          <h3>🧭 Map Layers</h3>
          <label><input type="checkbox" /> Satellite Imagery</label><br />
          <label><input type="checkbox" /> Active Fire Perimeters</label><br />
          <label><input type="checkbox" /> Air Quality Overlay</label>
        </div>
      )}

    </div>
  );
}

export default MapComponent;
