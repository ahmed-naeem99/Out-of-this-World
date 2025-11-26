import React, { useEffect, useState, useRef } from 'react';
import './MapComponent.css';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import SidebarPanel from './SidebarPanel';

// Fix for default markers...
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

// Create fire icons...
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
  // --- MODIFIED: Initial loading is now handled by the BBOX prompt state
  const [isAoiSet, setIsAoiSet] = useState(false); // New state to track if a BBOX has been set
  const [isLoading, setIsLoading] = useState(false); // Reset to false, only trigger for fetch
  const [error, setError] = useState(null);
  const mapRef = useRef();

  // State for tracking BBOX pipeline status
  const [updateStatus, setUpdateStatus] = useState('idle'); // 'idle', 'applying', 'resetting'
  
  // Default BBOX coordinates for display/input hints
  const DEFAULT_AOI_HINTS = {
    latMin: '53.2',
    latMax: '60.9',
    lonMin: '-110.1',
    lonMax: '-100.5'
  };

  // State for AOI inputs (starts with empty strings)
  const [aoiInputs, setAoiInputs] = useState({
    latMin: '',
    latMax: '',
    lonMin: '',
    lonMax: ''
  });
  
  // State for the initial BBOX entry screen
  const [initialBbox, setInitialBbox] = useState({
    latMin: '', latMax: '', lonMin: '', lonMax: ''
  });

  // Filter states
  const [confidenceFilters, setConfidenceFilters] = useState({
    1: true, 2: true, 3: true, 4: true
  });
  
  // --- MODIFIED: New time range state and slider state ---
  const [timeRange, setTimeRange] = useState('7d'); // Default to last 7 days
  const [daysSlider, setDaysSlider] = useState(7); // Slider value between 1 and 7

  // --- Calculate 'since' parameter for API based on current timeRange/daysSlider ---
  const getSinceParam = () => {
    const now = new Date();
    let daysToSubtract = 7; // Default for '7d' or slider on '7d'

    if (timeRange === 'today') {
      daysToSubtract = 1; // Last 24 hours is close enough for 'Today'/'1d'
    } else if (timeRange === 'daysSlider') {
      daysToSubtract = daysSlider;
    } else {
      daysToSubtract = 7; // '7d' default
    }

    // Calculate the start date and format as ISO 8601 for the API
    const sinceDate = new Date(now.getTime() - daysToSubtract * 24 * 60 * 60 * 1000);
    return sinceDate.toISOString().replace(/\.000Z$/, 'Z'); // Format for SQLite/backend
  };

  // --- Data Fetching (Now uses the 'since' parameter) ---
  const fetchFireData = (isInitialLoad = false) => {
    if (isInitialLoad && !isAoiSet) {
      console.log("Initial load skipped: AOI not set.");
      return;
    }
    
    console.log("Fetching fire data from /api/fires...");
    setIsLoading(true);
    setError(null);
    
    // Get the time parameter for the API call
    const since = getSinceParam();
    
    fetch(`${process.env.REACT_APP_API_URL}/api/fires?since=${since}`)
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
          timestamp: new Date(fire.datetime).getTime() 
        })).filter(fire => !isNaN(fire.lat) && !isNaN(fire.lng));
        
        setAllFires(cleanedFires);
        setIsLoading(false);
        
        // Apply filters immediately after fetch
        applyFilters(cleanedFires, confidenceFilters, timeRange, daysSlider);
      })
      .catch((err) => {
        console.error('Failed to load fire data:', err);
        setError('Failed to load fire data.');
        setIsLoading(false);
      });
  };

  // --- Dedicated Filtering Logic (no longer needed in a useEffect) ---
  const applyFilters = (fires, confFilters) => {
    let filtered = [...fires];
    const activeConfidenceLevels = Object.keys(confFilters)
      .filter(level => confFilters[level])
      .map(level => parseInt(level));
    
    // Apply Confidence Filter
    if (activeConfidenceLevels.length < 4) {
        filtered = filtered.filter(fire => 
            activeConfidenceLevels.includes(fire.confidence_level)
        );
    }
    
    // NOTE: We don't need a time filter here because the API query already filtered the data based on 'since'.
    
    setFilteredFires(filtered);
  };

  // Initial data load check (Wait for AOI to be set)
  useEffect(() => {
    if (isAoiSet) {
      fetchFireData(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAoiSet]);

  // Run filter only on confidence/time range change (time range now triggers a fetch)
  useEffect(() => {
    applyFilters(allFires, confidenceFilters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allFires, confidenceFilters]);


  // --- Time Range Handlers ---
  const toggleConfidenceFilter = (level) => {
    setConfidenceFilters(prev => ({ ...prev, [level]: !prev[level] }));
  };

  const handleTimeRangeChange = (range, days) => {
    setTimeRange(range);
    if (range === 'daysSlider') {
      setDaysSlider(days);
    }
    // Trigger a new fetch when the time range changes
    // This will use the new state values in getSinceParam()
    setTimeout(fetchFireData, 0); 
  };
  
  const handleDaysSliderChange = (e) => {
    const days = parseInt(e.target.value);
    setDaysSlider(days);
    // If the timeRange is already 'daysSlider', trigger a new fetch
    if (timeRange === 'daysSlider') {
      setTimeout(fetchFireData, 0); 
    }
  };

  // --- AOI Form Handlers ---
  const handleAoiInputChange = (e) => {
    const { name, value } = e.target;
    setAoiInputs(prev => ({ ...prev, [name]: value }));
  };
  
  const handleInitialBboxChange = (e) => {
    const { name, value } = e.target;
    setInitialBbox(prev => ({ ...prev, [name]: value }));
  }

  const clearAoiInputs = () => {
    setAoiInputs({ latMin: '', latMax: '', lonMin: '', lonMax: '' });
  };

  // --- Core Pipeline Function ---
  const triggerPipelineRun = async (bbox_str, isReset = false) => {
    if (updateStatus !== 'idle') return;
    setUpdateStatus(isReset ? 'resetting' : 'applying');
    setError(null);

    // If a BBOX is provided (not empty string), set the AOI as active
    if (bbox_str) {
      setIsAoiSet(true);
    } else {
      // If BBOX is empty (reset/initial empty)
      setAllFires([]);
      setFilteredFires([]);
      setIsAoiSet(false);
    }

    console.log("Triggering pipeline run with BBOX:", bbox_str);

    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/run-pipeline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bbox: bbox_str })
      });

      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Failed to trigger pipeline');

      console.log("Pipeline trigger response:", result.message);
      // Only wait and fetch if a BBOX was provided, otherwise, we're done (cleared data)
      if (bbox_str) {
        console.log("Waiting 15 seconds for pipeline...");
        await sleep(15000); 

        console.log("Fetching new fire data...");
        // Re-fetch with the current time filter settings
        fetchFireData(); 
      }

    } catch (err) {
      console.error('Failed to update AOI:', err);
      setError('Failed to update Area of Interest.');
    } finally {
      setUpdateStatus('idle');
    }
  };
  
  // --- MODIFIED: "Apply" button handler logic (shared with initial prompt) ---
  const handleApplyBbox = (inputs) => {
    const { latMin, latMax, lonMin, lonMax } = inputs;
    const allFilled = latMin && latMax && lonMin && lonMax;
    
    if (allFilled) {
      const bbox_str = [lonMin, latMin, lonMax, latMax].join(',');
      // Update the sidebar inputs to reflect the newly set AOI
      setAoiInputs(inputs);
      triggerPipelineRun(bbox_str, false);
    } else {
      setError("Please fill all four coordinates to set the Area of Interest.");
    }
  }

  // --- "Apply AOI" in Sidebar handler ---
  const handleUpdateAOI = () => {
    // Use the same logic, passing the current sidebar inputs
    handleApplyBbox(aoiInputs);
  };

  // --- "Clear & Reset" button handler ---
  const handleClearAndResetAOI = () => {
    if (updateStatus !== 'idle') return;
    clearAoiInputs();
    // Pass an empty string, which the pipeline will use as DEFAULT_BBOX
    triggerPipelineRun("", true); 
  };


  // --- Initial BBOX Prompt Render ---
  if (!isAoiSet && allFires.length === 0 && updateStatus === 'idle') {
    return (
      <div className="map-container">
        <div className="initial-prompt-overlay">
          <div className="initial-prompt-box">
            <h2>🌎 Define Area of Interest</h2>
            <p>Enter the bounding box coordinates (min/max longitude and latitude) to load fire data.</p>
            <div className="aoi-form">
              <div className="form-row">
                <div className="form-group">
                  <label>Latitude Min</label>
                  <input 
                    type="number" 
                    placeholder={`e.g., ${DEFAULT_AOI_HINTS.latMin}`} 
                    name="latMin"
                    value={initialBbox.latMin}
                    onChange={handleInitialBboxChange}
                  />
                </div>
                <div className="form-group">
                  <label>Latitude Max</label>
                  <input 
                    type="number" 
                    placeholder={`e.g., ${DEFAULT_AOI_HINTS.latMax}`} 
                    name="latMax"
                    value={initialBbox.latMax}
                    onChange={handleInitialBboxChange}
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Longitude Min</label>
                  <input 
                    type="number" 
                    placeholder={`e.g., ${DEFAULT_AOI_HINTS.lonMin}`} 
                    name="lonMin"
                    value={initialBbox.lonMin}
                    onChange={handleInitialBboxChange}
                  />
                </div>
                <div className="form-group">
                  <label>Longitude Max</label>
                  <input 
                    type="number" 
                    placeholder={`e.g., ${DEFAULT_AOI_HINTS.lonMax}`}
                    name="lonMax"
                    value={initialBbox.lonMax}
                    onChange={handleInitialBboxChange}
                  />
                </div>
              </div>
            </div>
            <button 
              className="apply-btn"
              onClick={() => handleApplyBbox(initialBbox)}
              disabled={updateStatus !== 'idle'}
            >
              Apply AOI & Load Data
            </button>
            {error && <p className="error-text">❌ {error}</p>}
          </div>
        </div>
      </div>
    );
  }
  
  // --- Main Loading Spinner and Overlay are unchanged/adjusted for new states ---
  if (isLoading && allFires.length === 0 && isAoiSet) {
    return (
      <div className="map-container">
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <p>Loading initial fire data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="map-container">
      {/* Secondary Loader */}
      {updateStatus !== 'idle' && (
        <div className="loading-overlay transparent">
            <div className="loading-spinner"></div>
            <p>
              {updateStatus === 'applying' ? 'Applying new AOI and fetching data...' : 'Resetting AOI and clearing data...'}
            </p>
        </div>
      )}

      {/* Error Display */}
      {error && (
          <div className="error-banner">
              <p>{error}</p>
              <button onClick={() => setError(null)}>X</button>
          </div>
      )}

      <MapContainer
        // Initial center (using the old default BBOX center as a fallback visual)
        center={[57.05, -105.3]} 
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
        // --- Pass new time props ---
        timeRange={timeRange}
        handleTimeRangeChange={handleTimeRangeChange}
        daysSlider={daysSlider}
        handleDaysSliderChange={handleDaysSliderChange}
        // --- AOI props ---
        handleUpdateAOI={handleUpdateAOI}
        updateStatus={updateStatus}
        aoiInputs={aoiInputs}
        handleAoiInputChange={handleAoiInputChange}
        handleClearAndResetAOI={handleClearAndResetAOI}
      />
    </div>
  );
}

export default MapComponent;
