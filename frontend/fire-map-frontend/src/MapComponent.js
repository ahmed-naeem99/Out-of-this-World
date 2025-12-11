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

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

const DEFAULT_MAP_BBOX = {
  latMin: '50.0',
  latMax: '60.0',
  lonMin: '-105.0',
  lonMax: '-85.0'
};

function MapComponent({ viewMode }) {
  const [allFires, setAllFires] = useState([]);
  const [filteredFires, setFilteredFires] = useState([]);
  const [isAoiSet, setIsAoiSet] = useState(true); 
  const [isLoading, setIsLoading] = useState(false); 
  const [error, setError] = useState(null);
  const mapRef = useRef();
  const [updateStatus, setUpdateStatus] = useState('idle'); 
  const [aoiInputs, setAoiInputs] = useState(DEFAULT_MAP_BBOX);
  
  const [confidenceFilters, setConfidenceFilters] = useState({
    1: true, 2: true, 3: true, 4: true
  });
  
  const [timeRange, setTimeRange] = useState('7d'); 
  const [daysSlider, setDaysSlider] = useState(7); 

  const getSinceParam = () => {
    const now = new Date();
    let daysToSubtract = 7; 

    if (timeRange === 'today') {
      daysToSubtract = 1; 
    } else if (timeRange === 'daysSlider') {
      daysToSubtract = daysSlider;
    } else {
      daysToSubtract = 7; 
    }

    const sinceDate = new Date(now.getTime() - daysToSubtract * 24 * 60 * 60 * 1000);
    return sinceDate.toISOString().replace(/\.000Z$/, 'Z'); 
  };

  // --- Data Fetching ---
  const fetchFireData = (isInitialLoad = false) => {
    if (isInitialLoad && !isAoiSet) return;
    
    // Choose endpoint based on viewMode
    const endpoint = viewMode === 'raw' ? '/api/raw_fires' : '/api/fires';

    console.log(`Fetching ${viewMode} data from ${endpoint}...`);
    setIsLoading(true);
    setError(null);
    
    const since = getSinceParam();
    
    fetch(`${process.env.REACT_APP_API_URL}${endpoint}?since=${since}`)
      .then((res) => {
        if (!res.ok) throw new Error('Network response was not ok');
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
        
        applyFilters(cleanedFires, confidenceFilters, timeRange, daysSlider);
      })
      .catch((err) => {
        console.error('Failed to load fire data:', err);
        // Clean error message for connection refused
        if (err.message.includes("Failed to fetch")) {
            setError("Server is offline. Please start server.py");
        } else {
            setError('Failed to load fire data.');
        }
        setIsLoading(false);
      });
  };

  const applyFilters = (fires, confFilters) => {
    let filtered = [...fires];
    const activeConfidenceLevels = Object.keys(confFilters)
      .filter(level => confFilters[level])
      .map(level => parseInt(level));
    
    if (activeConfidenceLevels.length < 4) {
        filtered = filtered.filter(fire => 
            activeConfidenceLevels.includes(fire.confidence_level)
        );
    }
    
    setFilteredFires(filtered);
  };

  // Trigger fetch when viewMode changes
  useEffect(() => {
    fetchFireData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode]); 

  // Initial Pipeline Trigger on Mount
  useEffect(() => {
    if (isAoiSet) {
      const { latMin, latMax, lonMin, lonMax } = DEFAULT_MAP_BBOX;
      const bbox_str = [lonMin, latMin, lonMax, latMax].join(',');
      triggerPipelineRun(bbox_str, false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); 

  useEffect(() => {
    applyFilters(allFires, confidenceFilters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allFires, confidenceFilters]);


  const toggleConfidenceFilter = (level) => {
    setConfidenceFilters(prev => ({ ...prev, [level]: !prev[level] }));
  };

  const handleTimeRangeChange = (range, days) => {
    setTimeRange(range);
    if (range === 'daysSlider') {
      setDaysSlider(days);
    }
    setTimeout(fetchFireData, 0); 
  };
  
  const handleDaysSliderChange = (e) => {
    const days = parseInt(e.target.value);
    setDaysSlider(days);
    if (timeRange === 'daysSlider') {
      setTimeout(fetchFireData, 0); 
    }
  };

  const handleAoiInputChange = (e) => {
    const { name, value } = e.target;
    setAoiInputs(prev => ({ ...prev, [name]: value }));
  };
  
  const clearAoiInputs = () => {
    setAoiInputs({ latMin: '', latMax: '', lonMin: '', lonMax: '' });
  };

  // --- FIXED PIPELINE TRIGGER: Handles 429 Errors Gracefully ---
  const triggerPipelineRun = async (bbox_str, isReset = false) => {
    if (updateStatus !== 'idle') return;
    setUpdateStatus(isReset ? 'resetting' : 'applying');
    setError(null);

    if (bbox_str) {
      setIsAoiSet(true);
    } else {
      setAllFires([]);
      setFilteredFires([]);
      setIsAoiSet(false);
    }

    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/run-pipeline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bbox: bbox_str })
      });

      // --- CRITICAL FIX: Handle 429 (Busy) specifically ---
      if (response.status === 429) {
        console.warn("Pipeline is already running. Continuing to wait for data...");
        // Do NOT throw error. Just let it proceed to wait/fetch steps.
      } else if (!response.ok) {
        // Only throw for real errors
        const result = await response.json();
        throw new Error(result.error || 'Failed to trigger pipeline');
      } else {
        // Success case (202 Accepted)
        const result = await response.json();
        console.log("Pipeline started:", result.message);
      }

      // If a BBOX exists, we wait and fetch regardless of whether we started it or it was already running.
      if (bbox_str) {
        console.log("Waiting 15 seconds for pipeline completion...");
        await sleep(15000); 
        console.log("Fetching latest fire data...");
        fetchFireData(); 
      }

    } catch (err) {
      console.error('Failed to update AOI:', err);
      // Clean handling for server offline
      if (err.message.includes("Failed to fetch")) {
          setError("Server is offline. Please start server.py");
      } else {
          setError('Failed to update Area of Interest. Please try again.');
      }
    } finally {
      setUpdateStatus('idle');
    }
  };
  
  const handleApplyBbox = (inputs) => {
    const { latMin, latMax, lonMin, lonMax } = inputs;
    const allFilled = latMin && latMax && lonMin && lonMax;
    
    if (allFilled) {
      const bbox_str = [lonMin, latMin, lonMax, latMax].join(',');
      setAoiInputs(inputs);
      triggerPipelineRun(bbox_str, false);
    } else {
      setError("Please fill all four coordinates to set the Area of Interest.");
    }
  }

  const handleUpdateAOI = () => {
    handleApplyBbox(aoiInputs);
  };

  const handleClearAndResetAOI = () => {
    if (updateStatus !== 'idle') return;
    clearAoiInputs();
    triggerPipelineRun("", true); 
  };

  const formatFireTimeUTC = (fire) => {
  if (!fire.acq_time || !fire.acq_date) return 'N/A';
  const acqTimeStr = fire.acq_time.toString().padStart(4, '0');
  const hours = parseInt(acqTimeStr.slice(0, 2));
  const minutes = parseInt(acqTimeStr.slice(2, 4));
  const [year, month, day] = fire.acq_date.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day, hours, minutes));
  if (isNaN(date)) return 'Invalid time';

  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: 'UTC'
  }) + ' UTC';
};

  if (isLoading && allFires.length === 0 && isAoiSet) {
    return (
      <div className="map-container">
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <p>Loading {viewMode === 'raw' ? 'Raw Sensor' : 'Validated'} data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="map-container">
      {updateStatus !== 'idle' && (
        <div className="loading-overlay transparent">
            <div className="loading-spinner"></div>
            <p>
              {updateStatus === 'applying' ? 'Applying new AOI and fetching data...' : 'Resetting AOI and clearing data...'}
            </p>
        </div>
      )}

      {error && (
          <div className="error-banner">
              <p>{error}</p>
              <button onClick={() => setError(null)}>X</button>
          </div>
      )}

      <MapContainer
        center={[55.0, -95.0]}
        zoom={5}
        style={{ height: '100%', width: '100%' }}
        ref={mapRef}
        zoomControl={false}
      >
        {viewMode === 'validated' ? (
             <TileLayer
             url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
             attribution='&copy; OpenStreetMap &copy; CARTO'
           />
        ) : (
            <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; OpenStreetMap &copy; CARTO'
          />
        )}


        {filteredFires.map((fire, index) => (
          <Marker
            key={`${fire.lat}-${fire.lng}-${index}`}
            position={[fire.lat, fire.lng]}
            icon={createFireIcon(fire.confidence_level)}
          >
            <Popup className="custom-popup">
              <div className="popup-content">
                <h3>{viewMode === 'raw' ? '📡 Raw Sensor Detection' : '🔥 Validated Fire'}</h3>
                <p style={{ textAlign: "right" }}><strong>Location:</strong> {fire.lat.toFixed(4)}, {fire.lng.toFixed(4)}</p>
                <p><strong>Confidence:</strong> {fire.confidence_level}/4</p>
                <p><strong>Source:</strong> {fire.primary_sensor}</p>
                <p><strong>Date:</strong> {fire.acq_date}</p>
                <p><strong>Time:</strong> {formatFireTimeUTC(fire)}</p>
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
        daysSlider={daysSlider}
        handleDaysSliderChange={handleDaysSliderChange}
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