import React, { useEffect, useState } from 'react';
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
      width: 20px;
      height: 20px;
      border-radius: 50%;
      border: 2px solid white;
      box-shadow: 0 0 10px rgba(0, 0, 0, 0.5);
    "></div>`,
    className: 'fire-marker',
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });
};

function MapComponent() {
  const [fires, setFires] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [mapReady, setMapReady] = useState(false);
  const [filteredFires, setFilteredFires] = useState([]);
  const [filters, setFilters] = useState({
    confidenceLevels: [1, 2, 3, 4],
    timeRange: 'all',
    areaOfInterest: null
  });

  useEffect(() => {
    // Small delay to ensure DOM is fully rendered
    const timer = setTimeout(() => {
      setMapReady(true);
    }, 100);
    
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    setIsLoading(true);
    fetch('http://localhost:5000/api/fires')
      .then((res) => res.json())
      .then((data) => {
        setFires(data);
        setFilteredFires(data);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load fire data:', err);
        setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    // Apply filters whenever they change
    let filtered = fires;
    
    // Filter by confidence level
    if (filters.confidenceLevels.length > 0) {
      filtered = filtered.filter(fire => 
        filters.confidenceLevels.includes(parseInt(fire.confidence_level))
      );
    }
    
    // Filter by time range
    if (filters.timeRange !== 'all') {
      const now = new Date();
      let cutoffDate = new Date();
      
      switch(filters.timeRange) {
        case '24h':
          cutoffDate.setHours(now.getHours() - 24);
          break;
        case '7d':
          cutoffDate.setDate(now.getDate() - 7);
          break;
        case '30d':
          cutoffDate.setDate(now.getDate() - 30);
          break;
        default:
          break;
      }
      
      filtered = filtered.filter(fire => {
        if (!fire.datetime) return false;
        const fireDate = new Date(fire.datetime);
        return fireDate >= cutoffDate;
      });
    }
    
    // Filter by area of interest (if provided)
    if (filters.areaOfInterest) {
      const { lat, lng, radius } = filters.areaOfInterest;
      filtered = filtered.filter(fire => {
        const distance = getDistanceFromLatLonInKm(
          lat, lng, fire.latitude, fire.longitude
        );
        return distance <= radius;
      });
    }
    
    setFilteredFires(filtered);
  }, [filters, fires]);

  // Helper function to calculate distance between coordinates
  const getDistanceFromLatLonInKm = React.useCallback((lat1, lon1, lat2, lon2) => {
    const R = 6371; // Radius of the earth in km
    const dLat = deg2rad(lat2 - lat1);
    const dLon = deg2rad(lon2 - lon1);
    const a = 
      Math.sin(dLat/2) * Math.sin(dLat/2) +
      Math.cos(deg2rad(lat1)) * Math.cos(deg2rad(lat2)) * 
      Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)); 
    return R * c; // Distance in km
  });

  const deg2rad = (deg) => {
    return deg * (Math.PI/180);
  };

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
  };

  if (!mapReady) {
    return (
      <div className="map-container">
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <p>Initializing map...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="map-container">
      <MapContainer
        center={[51.0447, -114.0719]}
        zoom={6}
        minZoom={2}
        maxZoom={18}
        style={{ height: '100%', width: '100%' }}
        preferCanvas={true}      // use canvas renderer for speed
        zoomAnimation={true}
        zoomAnimationThreshold={8}
        markerZoomAnimation={true}
        wheelPxPerZoomLevel={60} // smoother mousewheel zoom
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />

        {filteredFires.map((fire, index) => (
          <Marker
            key={index}
            position={[fire.latitude, fire.longitude]}
            icon={getFireIcon(fire.confidence_level)}
          >
            <Popup className="custom-popup">
              <div className="popup-content">
                <h3>🔥 Fire Detection</h3>
                <p><strong>Latitude:</strong> {fire.latitude.toFixed(4)}</p>
                <p><strong>Longitude:</strong> {fire.longitude.toFixed(4)}</p>
                <p><strong>Confidence Level:</strong> {fire.confidence_level}/4</p>
                <p><strong>Date Detected:</strong> {fire.datetime || 'Unknown'}</p>
              </div>t
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      <SidebarPanel 
        filters={filters}
        onFilterChange={handleFilterChange}
        fireCount={filteredFires.length}
        totalFireCount={fires.length}
      />

      {isLoading && (
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <p>Loading fire data...</p>
        </div>
      )}
    </div>
  );
}

export default MapComponent;