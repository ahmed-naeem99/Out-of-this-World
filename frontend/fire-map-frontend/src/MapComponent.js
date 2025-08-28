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
  const [allFires, setAllFires] = useState([]); // All fires from API
  const [filteredFires, setFilteredFires] = useState([]); // Fires after filtering
  const [isLoading, setIsLoading] = useState(true);
  const mapRef = useRef();
  
  // Filter states
  const [confidenceFilters, setConfidenceFilters] = useState({
    1: true,
    2: true,
    3: true,
    4: true
  });
  const [timeRange, setTimeRange] = useState('all'); // 'all', '24h', '7d', '30d'

  useEffect(() => {
    fetch('http://localhost:5000/api/fires')
      .then((res) => res.json())
      .then((data) => {
        const fireData = Array.isArray(data) ? data : [];
        
        // Ensure coordinates are numbers
        const cleanedFires = fireData.map(fire => ({
          ...fire,
          lat: Number(fire.latitude),
          lng: Number(fire.longitude),
          // Convert date to timestamp for filtering
          timestamp: new Date(fire.acq_date).getTime()
        })).filter(fire => !isNaN(fire.lat) && !isNaN(fire.lng));
        
        setAllFires(cleanedFires);
        setFilteredFires(cleanedFires);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load fire data:', err);
        setIsLoading(false);
      });
  }, []);

  // Apply filters whenever filter states change
  useEffect(() => {
    if (allFires.length === 0) return;
    
    let filtered = [...allFires];
    
    // Apply confidence filters
    const activeConfidenceLevels = Object.keys(confidenceFilters)
      .filter(level => confidenceFilters[level])
      .map(level => parseInt(level));
    
    if (activeConfidenceLevels.length > 0) {
      filtered = filtered.filter(fire => 
        activeConfidenceLevels.includes(fire.confidence_level)
      );
    }
    
    // Apply time filters
    const now = new Date().getTime();
    switch(timeRange) {
      case '24h':
        filtered = filtered.filter(fire => now - fire.timestamp <= 24 * 60 * 60 * 1000);
        break;
      case '7d':
        filtered = filtered.filter(fire => now - fire.timestamp <= 7 * 24 * 60 * 60 * 1000);
        break;
      case '30d':
        filtered = filtered.filter(fire => now - fire.timestamp <= 30 * 24 * 60 * 60 * 1000);
        break;
      default:
        // 'all' - no time filter
        break;
    }
    
    setFilteredFires(filtered);
  }, [allFires, confidenceFilters, timeRange]);

  const toggleConfidenceFilter = (level) => {
    setConfidenceFilters(prev => ({
      ...prev,
      [level]: !prev[level]
    }));
  };

  const handleTimeRangeChange = (range) => {
    setTimeRange(range);
  };

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

        {filteredFires.map((fire, index) => (
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

      <SidebarPanel 
        fireCount={filteredFires.length} 
        totalFireCount={allFires.length}
        confidenceFilters={confidenceFilters}
        toggleConfidenceFilter={toggleConfidenceFilter}
        timeRange={timeRange}
        handleTimeRangeChange={handleTimeRangeChange}
      />

      <div className="map-info-panel">
        <strong>Fires: {filteredFires.length}</strong>
      </div>
    </div>
  );
}

export default MapComponent;