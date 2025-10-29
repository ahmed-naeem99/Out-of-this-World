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
  const [error, setError] = useState(null);
  const mapRef = useRef();

  // --- MODIFIED: Renamed state for clarity ---
  const [updateStatus, setUpdateStatus] = useState('idle'); // 'idle', 'applying', 'resetting'
  
  const [aoiInputs, setAoiInputs] = useState({
    latMin: '',
    latMax: '',
    lonMin: '',
    lonMax: ''
  });

  // Filter states
  const [confidenceFilters, setConfidenceFilters] = useState({
    1: true,
    2: true,
    3: true,
    4: true
  });
  const [timeRange, setTimeRange] = useState('all');

  // --- Data Fetching (Using 'datetime' from your JSON) ---
  const fetchFireData = () => {
    console.log("Fetching fire data from /api/fires...");
    setIsLoading(true);
    setError(null);
    
    fetch('http://127.0.0.1:5000/api/fires')
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
          // Using the correct 'datetime' field from your validated data
          timestamp: new Date(fire.datetime).getTime() 
        })).filter(fire => !isNaN(fire.lat) && !isNaN(fire.lng));
        
        setAllFires(cleanedFires);
        setFilteredFires(cleanedFires);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load fire data:', err);
        setError('Failed to load fire data.');
        setIsLoading(false);
      });
  };

  // Initial data load
  useEffect(() => {
    fetchFireData();
  }, []);

  // Filtering logic (no changes)
  useEffect(() => {
    if (allFires.length === 0 && !isLoading) return; 
    let filtered = [...allFires];
    const activeConfidenceLevels = Object.keys(confidenceFilters)
      .filter(level => confidenceFilters[level])
      .map(level => parseInt(level));
    
    if (activeConfidenceLevels.length < 4) {
        if (activeConfidenceLevels.length === 0) {
            filtered = [];
        } else {
            filtered = filtered.filter(fire => 
                activeConfidenceLevels.includes(fire.confidence_level)
            );
        }
    }
    
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
  }, [allFires, confidenceFilters, timeRange, isLoading]);

  // --- Filter Handlers (no changes) ---
  const toggleConfidenceFilter = (level) => {
    setConfidenceFilters(prev => ({ ...prev, [level]: !prev[level] }));
  };

  const handleTimeRangeChange = (range) => {
    setTimeRange(range);
  };

  // --- AOI Form Handlers ---
  const handleAoiInputChange = (e) => {
    const { name, value } = e.target;
    setAoiInputs(prev => ({ ...prev, [name]: value }));
  };

  const clearAoiInputs = () => {
    setAoiInputs({ latMin: '', latMax: '', lonMin: '', lonMax: '' });
  };

  // --- NEW: Refactored Core Pipeline Function ---
  const triggerPipelineRun = async (bbox_str, isReset = false) => {
    if (updateStatus !== 'idle') return; // Prevent multiple clicks
    setUpdateStatus(isReset ? 'resetting' : 'applying');
    setError(null);

    console.log("Triggering pipeline run with BBOX:", bbox_str);

    try {
      const response = await fetch('http://127.0.0.1:5000/api/run-pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bbox: bbox_str }) // Send the bbox (or null for default)
      });

      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Failed to trigger pipeline');

      console.log("Pipeline trigger response:", result.message);
      console.log("Waiting 15 seconds for pipeline...");
      await sleep(15000); 

      console.log("Fetching new fire data...");
      fetchFireData(); // This will set isLoading(false) when done

    } catch (err) {
      console.error('Failed to update AOI:', err);
      setError('Failed to update Area of Interest.');
    } finally {
      setUpdateStatus('idle'); // Set status back to idle
    }
  };

  // --- MODIFIED: "Apply" button handler ---
  const handleUpdateAOI = () => {
    const { latMin, latMax, lonMin, lonMax } = aoiInputs;
    const allFilled = latMin && latMax && lonMin && lonMax;
    const allEmpty = !latMin && !latMax && !lonMin && !lonMax;

    if (allFilled) {
      // Case 1: All fields filled. Send the custom BBOX.
      const bbox_str = [lonMin, latMin, lonMax, latMax].join(',');
      triggerPipelineRun(bbox_str, false);
    } else if (allEmpty) {
      // Case 2: All fields empty. Trigger a default reset.
      console.log("Empty fields, resetting to default AOI.");
      triggerPipelineRun(null, true); // `null` tells the backend to use default
    } else {
      // Case 3: Partially filled. Show an error.
      setError("Please fill all fields, or clear all fields to reset to default.");
    }
  };

  // --- NEW: "Clear & Reset" button handler ---
  const handleClearAndResetAOI = () => {
    if (updateStatus !== 'idle') return;
    clearAoiInputs();
    triggerPipelineRun(null, true); // `null` tells the backend to use default
  };


  // --- Main loading spinner (no changes) ---
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
      {/* --- Secondary Loader (Uses new state) --- */}
      {updateStatus !== 'idle' && (
        <div className="loading-overlay transparent">
            <div className="loading-spinner"></div>
            <p>
              {updateStatus === 'applying' ? 'Applying new AOI...' : 'Resetting to default...'}
            </p>
        </div>
      )}

      {/* Error Display (no changes) */}
      {error && (
          <div className="error-banner">
              <p>{error}</p>
              <button onClick={() => setError(null)}>X</button>
          </div>
      )}

      {/* MapContainer (no changes) */}
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
                <p><strong>Sensors:</strong> {fire.validating_sensors}</p>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {/* --- MODIFIED: Pass all the new props --- */}
      <SidebarPanel 
        fireCount={filteredFires.length} 
        totalFireCount={allFires.length}
        confidenceFilters={confidenceFilters}
        toggleConfidenceFilter={toggleConfidenceFilter}
        timeRange={timeRange}
        handleTimeRangeChange={handleTimeRangeChange}
        // --- Pass all new/modified AOI props ---
        handleUpdateAOI={handleUpdateAOI}
        updateStatus={updateStatus} // Replaces isUpdatingAOI
        aoiInputs={aoiInputs}
        handleAoiInputChange={handleAoiInputChange}
        handleClearAndResetAOI={handleClearAndResetAOI} // New prop
      />
    </div>
  );
}

export default MapComponent;