import React, { useEffect, useState, useRef } from 'react';
import './MapComponent.css';
import { MapContainer, TileLayer, Marker, Popup, AttributionControl, useMap } from 'react-leaflet';
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

// Parse DEFAULT_BBOX from .env file (format: "lon_min,lat_min,lon_max,lat_max")
const parseBboxFromEnv = () => {
  const bboxStr = process.env.REACT_APP_DEFAULT_BBOX;
  if (!bboxStr) {
    throw new Error('REACT_APP_DEFAULT_BBOX must be set in .env file');
  }
  const [lonMin, latMin, lonMax, latMax] = bboxStr.split(',').map(v => v.trim());
  return {
    latMin: latMin,
    latMax: latMax,
    lonMin: lonMin,
    lonMax: lonMax
  };
};

const DEFAULT_MAP_BBOX = parseBboxFromEnv();

// Component to access map instance for zoom controls
function ZoomControls({ onZoomIn, onZoomOut }) {
  return (
    <div className="floating-zoom-controls">
      <button className="zoom-btn zoom-in" onClick={onZoomIn} aria-label="Zoom in">
        +
      </button>
      <button className="zoom-btn zoom-out" onClick={onZoomOut} aria-label="Zoom out">
        −
      </button>
    </div>
  );
}

// Component to get map instance and expose zoom functions
function MapZoomHandler({ onMapReady }) {
  const map = useMap();
  
  useEffect(() => {
    if (map && onMapReady) {
      onMapReady(map);
    }
  }, [map, onMapReady]);
  
  return null;
}

function MapComponent({ viewMode: initialViewMode = 'validated' }) {
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
  const [basemap, setBasemap] = useState('streets'); // 'streets' or 'satellite'
  const [mapInstance, setMapInstance] = useState(null);
  const [basemapMenuOpen, setBasemapMenuOpen] = useState(false); 

  // Use the viewMode prop directly
  const currentViewMode = initialViewMode;

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
    
    // Choose endpoint based on currentViewMode
    const endpoint = currentViewMode === 'raw' ? '/api/raw_fires' : '/api/fires';

    console.log(`Fetching ${currentViewMode} data from ${endpoint}...`);
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
          timestamp: new Date(fire.datetime).getTime(),
          confidence_score: fire.confidence_score !== undefined ? fire.confidence_score : null
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

  // Trigger fetch when viewMode prop changes
  useEffect(() => {
    fetchFireData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialViewMode]);

  // Close basemap menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (basemapMenuOpen && !event.target.closest('.floating-basemap-menu')) {
        setBasemapMenuOpen(false);
      }
    };

    if (basemapMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [basemapMenuOpen]); 

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

  const handleBasemapSelect = (selectedBasemap) => {
    setBasemap(selectedBasemap);
    setBasemapMenuOpen(false);
  };

  const handleZoomIn = () => {
    if (mapInstance) {
      mapInstance.zoomIn();
    }
  };

  const handleZoomOut = () => {
    if (mapInstance) {
      mapInstance.zoomOut();
    }
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
          <p>Loading {currentViewMode === 'raw' ? 'Raw Sensor' : 'Validated'} data...</p>
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
        attributionControl={false}
      >
        <AttributionControl position="bottomleft" />
        {basemap === 'satellite' ? (
          <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            attribution='&copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
            noWrap={false}
            tileSize={512}
            keepBuffer={10}
          />
        ) : basemap === 'streets' && currentViewMode === 'validated' ? (
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; OpenStreetMap &copy; CARTO'
            noWrap={false}
            tileSize={512}
            keepBuffer={10}
          />
        ) : (
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; OpenStreetMap &copy; CARTO'
            noWrap={false}
            tileSize={512}
            keepBuffer={10}
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
                <h3>{currentViewMode === 'raw' ? '📡 Raw Sensor Detection' : '🔥 Validated Fire'}</h3>
                <p style={{ textAlign: "right" }}><strong>Location:</strong> {fire.lat.toFixed(4)}, {fire.lng.toFixed(4)}</p>
                {fire.confidence_score !== null && fire.confidence_score !== undefined && (
                  <p><strong>Confidence Score:</strong> {fire.confidence_score.toFixed(1)}%</p>
                )}
                <p><strong>Source:</strong> {fire.primary_sensor}</p>
                <p><strong>Date:</strong> {fire.acq_date}</p>
                <p><strong>Time:</strong> {formatFireTimeUTC(fire)}</p>
              </div>
            </Popup>
          </Marker>
        ))}
        <MapZoomHandler onMapReady={setMapInstance} />
      </MapContainer>

      {/* Floating Zoom Controls */}
      <ZoomControls onZoomIn={handleZoomIn} onZoomOut={handleZoomOut} />

      {/* Floating Basemap Toggle Menu */}
      <div className="floating-basemap-menu">
        <button 
          className="basemap-menu-button" 
          onClick={() => setBasemapMenuOpen(!basemapMenuOpen)}
          aria-label="Basemap menu"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
        
        {basemapMenuOpen && (
          <div className="basemap-menu-options">
            <div 
              className={`basemap-option ${basemap === 'streets' ? 'active' : ''}`}
              onClick={() => handleBasemapSelect('streets')}
            >
              <div className="basemap-thumbnail">
                <div className={`thumbnail-preview streets ${currentViewMode === 'validated' ? 'light' : 'dark'}`}></div>
              </div>
              <div className="basemap-info">
                <div className="basemap-label">Map</div>
              </div>
            </div>
            <div 
              className={`basemap-option ${basemap === 'satellite' ? 'active' : ''}`}
              onClick={() => handleBasemapSelect('satellite')}
            >
              <div className="basemap-thumbnail">
                <div className="thumbnail-preview satellite"></div>
              </div>
              <div className="basemap-info">
                <div className="basemap-label">Satellite</div>
              </div>
            </div>
          </div>
        )}
      </div>

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