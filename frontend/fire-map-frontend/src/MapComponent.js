import React, { useEffect, useState, useRef } from 'react';
import './MapComponent.css';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import SidebarPanel from './SidebarPanel';

// Fix for default markers in react-leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

// Create a simple fire icon
const createFireIcon = (confidence) => {
  const colors = ['#FFD700', '#FFA500', '#FF4500', '#8B0000'];
  const color = colors[confidence - 1] || 'gray';
  
  return L.divIcon({
    html: `<div style="
      background-color: ${color};
      width: 12px;
      height: 12px;
      border-radius: 50%;
      border: 2px solid white;
      box-shadow: 0 0 8px ${color};
    "></div>`,
    className: 'fire-marker',
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  });
};

function MapComponent() {
  const [fires, setFires] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const mapRef = useRef();

  useEffect(() => {
    fetch('http://localhost:5000/api/fires')
      .then((res) => res.json())
      .then((data) => {
        const fireData = Array.isArray(data) ? data : [];
        
        // Ensure coordinates are numbers
        const cleanedFires = fireData.map(fire => ({
          ...fire,
          lat: Number(fire.latitude),
          lng: Number(fire.longitude)
        })).filter(fire => !isNaN(fire.lat) && !isNaN(fire.lng));
        
        setFires(cleanedFires);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load fire data:', err);
        setIsLoading(false);
      });
  }, []);

  if (isLoading) {
    return (
      <div className="map-container">
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <p>Loading fire data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="map-container">
      <MapContainer
        center={[58.5, -104.0]}
        zoom={5}
        style={{ height: '100%', width: '100%' }}
        ref={mapRef}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />

        {fires.map((fire, index) => (
          <Marker
            key={`${fire.lat}-${fire.lng}-${index}`}
            position={[fire.lat, fire.lng]}
            icon={createFireIcon(fire.confidence_level)}
          >
            <Popup>
              <div>
                <h3>🔥 Fire Detection</h3>
                <p><strong>Location:</strong> {fire.lat.toFixed(4)}, {fire.lng.toFixed(4)}</p>
                <p><strong>Confidence:</strong> {fire.confidence_level}/4</p>
                <p><strong>Date:</strong> {fire.acq_date}</p>
                <p><strong>Time:</strong> {fire.acq_time}</p>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      <SidebarPanel fireCount={fires.length} />

      <div className="map-info-panel">
        <strong>Fires: {fires.length}</strong>
      </div>
    </div>
  );
}

export default MapComponent;