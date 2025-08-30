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

// Create cooler animated fire icons with SVG
const createFireIcon = (confidence) => {
  const colors = ['#FFD700', '#FFA500', '#FF4500', '#FF0000'];
  const sizes = [20, 24, 28, 32];
  const color = colors[confidence - 1] || 'gray';
  const size = sizes[confidence - 1] || 24;
  
  return L.divIcon({
    html: `
      <div class="fire-marker-container" style="width: ${size}px; height: ${size}px;">
        <svg width="${size}" height="${size}" viewBox="0 0 24 24" class="fire-icon">
          <path fill="${color}" d="M17.5,15.5c0,4-3,6.5-5.5,6.5s-5.5-2.5-5.5-6.5c0-3,3-7,5.5-9s5.5,6,5.5,9Z"/>
          <path fill="#FFF" opacity="0.3" d="M12,2c0,0,3,2.5,3,6s-3,3.5-3,3.5s-3-0.5-3-4S12,2,12,2Z"/>
        </svg>
        <div class="fire-pulse" style="background-color: ${color};"></div>
      </div>
    `,
    className: 'fire-marker',
    iconSize: [size, size],
    iconAnchor: [size/2, size/2],
  });
};

function MapComponent() {
  const [allFires, setAllFires] = useState([]);
  const [filteredFires, setFilteredFires] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const mapRef = useRef();
  
  // Filter states
  const [confidenceFilters, setConfidenceFilters] = useState({
    1: true,
    2: true,
    3: true,
    4: true
  });
  const [timeRange, setTimeRange] = useState('all');

  useEffect(() => {
    fetch('http://localhost:5000/api/fires')
      .then((res) => {
        if (!res.ok) {
          throw new Error('Network response was not ok');
        }
        return res.json();
      })
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
        
        // Fallback to mock data if API fails
        const mockFires = [
          { latitude: 58.5, longitude: -104.0, confidence_level: 3, acq_date: '2023-08-30', acq_time: '12:30' },
          { latitude: 57.8, longitude: -103.5, confidence_level: 4, acq_date: '2023-08-30', acq_time: '13:45' },
          { latitude: 59.2, longitude: -105.1, confidence_level: 2, acq_date: '2023-08-29', acq_time: '10:15' },
          { latitude: 58.0, longitude: -102.8, confidence_level: 1, acq_date: '2023-08-29', acq_time: '09:20' },
          { latitude: 59.5, longitude: -103.2, confidence_level: 3, acq_date: '2023-08-28', acq_time: '14:30' },
        ];
        
        const fireData = Array.isArray(mockFires) ? mockFires : [];
        const cleanedFires = fireData.map(fire => ({
          ...fire,
          lat: Number(fire.latitude),
          lng: Number(fire.longitude),
          timestamp: new Date(fire.acq_date).getTime()
        })).filter(fire => !isNaN(fire.lat) && !isNaN(fire.lng));
        
        setAllFires(cleanedFires);
        setFilteredFires(cleanedFires);
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
        zoomControl={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        />

        {filteredFires.map((fire, index) => (
          <Marker
            key={`${fire.lat}-${fire.lng}-${index}`}
            position={[fire.lat, fire.lng]}
            icon={createFireIcon(fire.confidence_level)}
          >
            <Popup className="custom-popup">
              <div className="popup-content">
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
        <div className="info-content">
          <span className="fire-icon">🔥</span>
          <span className="fire-count">{filteredFires.length} Fires Detected</span>
        </div>
      </div>
    </div>
  );
}

export default MapComponent;