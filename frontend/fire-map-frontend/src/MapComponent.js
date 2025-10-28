import React, { useEffect, useState, useRef } from 'react';
import './MapComponent.css';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import SidebarPanel from './SidebarPanel';

// Fix for default markers... (your code is good)
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

// Create fire icons... (your code is good)
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

// --- Helper function to delay execution ---
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

function MapComponent() {
  const [allFires, setAllFires] = useState([]);
  const [filteredFires, setFilteredFires] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdatingAOI, setIsUpdatingAOI] = useState(false); // <-- NEW STATE
  const [error, setError] = useState(null); // <-- NEW STATE
  const mapRef = useRef();
  
  // Filter states
  const [confidenceFilters, setConfidenceFilters] = useState({
    1: true,
    2: true,
    3: true,
    4: true
  });
  const [timeRange, setTimeRange] = useState('all');

  // --- REFACTORED DATA FETCHING ---
  // We put the data fetching in its own function so we can call it
  // on page load AND after updating the AOI.
  const fetchFireData = () => {
    console.log("Fetching fire data from /api/fires...");
    setIsLoading(true); // Show main loader
    setError(null);
    
    // This is your EXISTING data endpoint
    fetch('http://35.182.187.24:5000/api/fires') 
      .then((res) => {
        if (!res.ok) {
          throw new Error('Network response was not ok');
        }
        return res.json();
      })
      .then((data) => {
        const fireData = Array.isArray(data) ? data : [];
        
        const cleanedFires = fireData.map(fire => ({
          ...fire,
          lat: Number(fire.latitude),
          lng: Number(fire.longitude),
          timestamp: new Date(fire.acq_date).getTime()
        })).filter(fire => !isNaN(fire.lat) && !isNaN(fire.lng));
        
        setAllFires(cleanedFires);
        setFilteredFires(cleanedFires); // This will be re-filtered by the useEffect
        setIsLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load fire data:', err);
        setError('Failed to load fire data. Using mock data.'); // Show error
        setIsLoading(false);
        
        // Fallback to mock data
        const mockFires = [
          { latitude: 58.5, longitude: -104.0, confidence_level: 3, acq_date: '2023-08-30', acq_time: '12:30' },
          { latitude: 57.8, longitude: -103.5, confidence_level: 4, acq_date: '2023-08-30', acq_time: '13:45' },
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
  };

  // Initial data load on component mount
  useEffect(() => {
    fetchFireData();
  }, []); // Empty dependency array means this runs once on mount

  // Apply filters whenever filter states change (your code is good)
  useEffect(() => {
    if (allFires.length === 0 && !isLoading) return; // Don't filter if no fires
    
    let filtered = [...allFires];
    
    // Apply confidence filters
    const activeConfidenceLevels = Object.keys(confidenceFilters)
      .filter(level => confidenceFilters[level])
      .map(level => parseInt(level));
    
    // Handle case where all are unchecked (show nothing)
    if (activeConfidenceLevels.length < 4) {
        if (activeConfidenceLevels.length === 0) {
            filtered = [];
        } else {
            filtered = filtered.filter(fire => 
                activeConfidenceLevels.includes(fire.confidence_level)
            );
        }
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
        // 'all' case, do nothing
        break;
    }
    
    setFilteredFires(filtered);
  }, [allFires, confidenceFilters, timeRange, isLoading]); // Added isLoading

  // Filter handlers (your code is good)
  const toggleConfidenceFilter = (level) => {
    setConfidenceFilters(prev => ({
      ...prev,
      [level]: !prev[level]
    }));
  };

  const handleTimeRangeChange = (range) => {
    setTimeRange(range);
  };

  // --- NEW FUNCTION TO HANDLE AOI UPDATE ---
  const handleUpdateAOI = async () => {
    if (!mapRef.current) {
        console.error("Map is not yet initialized.");
        return;
    }
    if (isUpdatingAOI) {
        console.log("AOI update already in progress.");
        return;
    }

    setIsUpdatingAOI(true); // Show secondary loader
    setError(null);
    console.log("Updating Area of Interest...");

    // 1. Get the current map boundaries
    const bounds = mapRef.current.getBounds();
    const bbox_str = [
        bounds.getWest().toFixed(4),
        bounds.getSouth().toFixed(4),
        bounds.getEast().toFixed(4),
        bounds.getNorth().toFixed(4)
    ].join(',');

    console.log("New BBOX string:", bbox_str);

    try {
      // 2. Call your NEW pipeline server (on port 5001)
      //    NOTE: Update the IP address to your backend's IP.
      //    If running locally, 'http://127.0.0.1:5001' is fine.
      const response = await fetch('http://127.0.0.1:5001/api/run-pipeline', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ bbox: bbox_str }),
      });

      const result = await response.json();

      if (response.status === 429) { // "Too Many Requests"
        console.warn("Pipeline is already running.");
        setError("Pipeline is busy. Please try again in a moment.");
        setIsUpdatingAOI(false);
        return;
      }
      
      if (!response.ok) {
        throw new Error(result.error || 'Failed to trigger pipeline');
      }

      console.log("Pipeline trigger response:", result.message);
      
      // 3. Wait for the pipeline to work.
      // This is a simple solution. A better one involves WebSockets
      // or polling, but this is much simpler to implement.
      // Let's give it 15 seconds to fetch and process.
      console.log("Waiting 15 seconds for pipeline to process...");
      await sleep(15000); 

      // 4. Re-fetch data from the ORIGINAL data server
      console.log("Pipeline wait finished. Fetching new fire data...");
      fetchFireData(); // This will set isLoading(false) when done

    } catch (err) {
      console.error('Failed to update AOI:', err);
      setError('Failed to update Area of Interest.');
    } finally {
      // fetchFireData() will manage the isLoading state,
      // but we must turn off the isUpdatingAOI state.
      setIsUpdatingAOI(false);
    }
  };


  // Main loading spinner
  if (isLoading && allFires.length === 0) {
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
      {/* --- NEW Secondary Loader for AOI updates --- */}
      {isUpdatingAOI && (
        <div className="loading-overlay transparent">
            <div className="loading-spinner"></div>
            <p>Updating Area of Interest... This may take a moment.</p>
        </div>
      )}

      {/* --- NEW Error Message Display --- */}
      {error && (
          <div className="error-banner">
              <p>{error}</p>
              <button onClick={() => setError(null)}>X</button>
          </div>
      )}

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
        // --- PASS NEW PROPS ---
        handleUpdateAOI={handleUpdateAOI}
        isUpdatingAOI={isUpdatingAOI}
      />

      <div className="map-info-panel">
        <div className="info-content">
          <span className="fire-icon">🔥</span>
          <span className="fire-count">
            {isLoading ? 'Loading...' : `${filteredFires.length} Fires Detected`}
          </span>
        </div>
      </div>
    </div>
  );
}

export default MapComponent;