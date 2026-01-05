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

// Create fire icons (UPDATED FOR LEVELS 1-3)
const createFireIcon = (confidence) => {
  // Level 1 (40-60): Orange
  // Level 2 (60-85): Dark Orange
  // Level 3 (85+): Red
  const colors = ['#FFA500', '#FF4500', '#FF0000'];
  const sizes = [22, 26, 30];

  // Array index is level - 1 (e.g. Level 1 -> index 0)
  const index = Math.max(0, Math.min(confidence - 1, 2));

  const color = colors[index];
  const size = sizes[index];
  const anchor = size / 2;

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
    iconAnchor: [anchor, anchor],
  });
};

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

const parseBboxFromEnv = () => {
  const bboxStr = process.env.REACT_APP_DEFAULT_BBOX;
  if (!bboxStr) {
    return { latMin: "40", latMax: "90", lonMin: "-141", lonMax: "-52" };
  }
  const [lonMin, latMin, lonMax, latMax] = bboxStr.split(',').map(v => v.trim());
  return { latMin, latMax, lonMin, lonMax };
};

const DEFAULT_MAP_BBOX = parseBboxFromEnv();

const safeToFixed = (val, digits = 1) => {
  if (typeof val === 'number' && !isNaN(val)) {
    return val.toFixed(digits);
  }
  return "N/A";
};

function ZoomControls({ onZoomIn, onZoomOut }) {
  return (
    <div className="floating-zoom-controls">
      <button className="zoom-btn zoom-in" onClick={onZoomIn} aria-label="Zoom in">+</button>
      <button className="zoom-btn zoom-out" onClick={onZoomOut} aria-label="Zoom out">−</button>
    </div>
  );
}

// MapZoomHandler: We keep this to get the instance, but we removed the auto-zoom useEffect
function MapZoomHandler({ onMapReady }) {
  const map = useMap();
  useEffect(() => {
    if (map && onMapReady) onMapReady(map);
  }, [map, onMapReady]);
  
  useEffect(() => {
    if (map) {
      const timeoutId = setTimeout(() => map.invalidateSize(), 100);
      return () => clearTimeout(timeoutId);
    }
  }, [map]);
  
  useEffect(() => {
    if (map) {
      const handleResize = () => setTimeout(() => map.invalidateSize(), 100);
      window.addEventListener('resize', handleResize);
      return () => window.removeEventListener('resize', handleResize);
    }
  }, [map]);
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
  
  // UPDATED: Default filters for Levels 1, 2, 3
  const [confidenceFilters, setConfidenceFilters] = useState({
    1: true, 2: true, 3: true
  });
  
  const [timeRange, setTimeRange] = useState('7d'); 
  const [daysSlider, setDaysSlider] = useState(7);
  const [basemap, setBasemap] = useState('streets'); 
  const [mapInstance, setMapInstance] = useState(null);
  const [basemapMenuOpen, setBasemapMenuOpen] = useState(false); 

  const currentViewMode = initialViewMode;
  const DEMO_NOW = new Date('2025-08-17T23:59:59Z');

  const getSinceParam = () => {
    const DEMO_ANCHOR = new Date('2025-08-10T00:00:00Z');
    let daysToAdd = 0; 
    if (timeRange === 'today') daysToAdd = 7; 
    else if (timeRange === 'daysSlider') daysToAdd = 7 - daysSlider; 
    else daysToAdd = 0; 

    const sinceDate = new Date(DEMO_ANCHOR.getTime() + daysToAdd * 24 * 60 * 60 * 1000);
    const finalDate = sinceDate > DEMO_NOW ? DEMO_NOW : sinceDate;
    return finalDate.toISOString().replace(/\.000Z$/, 'Z'); 
  };

  const fetchFireData = (isInitialLoad = false) => {
    if (isInitialLoad && !isAoiSet) return;
    
    const endpoint = currentViewMode === 'raw' ? '/api/raw_fires' : '/api/fires';
    setIsLoading(true);
    setError(null);
    
    const since = getSinceParam();
    let queryParams = `since=${since}`;
    
    if (currentViewMode === 'raw') {
    }
    
    fetch(`${process.env.REACT_APP_API_URL}${endpoint}?${queryParams}`)
      .then((res) => {
        if (!res.ok) throw new Error('Network response was not ok');
        return res.json();
      })
      .then((data) => {
        const fireData = Array.isArray(data) ? data : [];
        
        const cleanedFires = fireData.map(fire => {
          const lat = parseFloat(fire.latitude);
          const lng = parseFloat(fire.longitude);
          if (isNaN(lat) || isNaN(lng)) return null;
          
          let safeScore = null;
          if (fire.confidence_score !== undefined && fire.confidence_score !== null) {
            const parsedScore = parseFloat(fire.confidence_score);
            if (!isNaN(parsedScore)) safeScore = parsedScore;
          }

          return {
            ...fire,
            lat: lat,
            lng: lng,
            latitude: lat,
            longitude: lng,
            timestamp: new Date(fire.datetime).getTime(),
            confidence_score: safeScore 
          };
        }).filter(fire => fire !== null);
        
        setAllFires(cleanedFires);
        setIsLoading(false);
        applyFilters(cleanedFires, confidenceFilters);
      })
      .catch((err) => {
        console.error('Failed to load fire data:', err);
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
    
    // Filter fires based on whether their level (1, 2, 3) is active
    filtered = filtered.filter(fire => 
        activeConfidenceLevels.includes(fire.confidence_level)
    );
    setFilteredFires(filtered);
  };

  useEffect(() => {
    fetchFireData();
    // eslint-disable-next-line
  }, [initialViewMode]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (basemapMenuOpen && !event.target.closest('.floating-basemap-menu')) {
        setBasemapMenuOpen(false);
      }
    };
    if (basemapMenuOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [basemapMenuOpen]); 

  useEffect(() => {
    fetchFireData(true);
    // eslint-disable-next-line
  }, []); 

  useEffect(() => {
    applyFilters(allFires, confidenceFilters);
    // eslint-disable-next-line
  }, [allFires, confidenceFilters]);

  // --- CHANGED: REMOVED AUTO-ZOOM useEffect ---
  // We deleted the useEffect that called mapInstance.fitBounds on filteredFires change.
  // The map will now stay exactly where you position it.

  const toggleConfidenceFilter = (level) => {
    setConfidenceFilters(prev => ({ ...prev, [level]: !prev[level] }));
  };

  const handleTimeRangeChange = (range, days) => {
    setTimeRange(range);
    if (range === 'daysSlider') setDaysSlider(days);
    setTimeout(fetchFireData, 0); 
  };
  
  const handleDaysSliderChange = (e) => {
    const days = parseInt(e.target.value);
    setDaysSlider(days);
    if (timeRange === 'daysSlider') setTimeout(fetchFireData, 0); 
  };

  const handleAoiInputChange = (e) => {
    const { name, value } = e.target;
    setAoiInputs(prev => ({ ...prev, [name]: value }));
  };
  
  const clearAoiInputs = () => {
    setAoiInputs({ latMin: '', latMax: '', lonMin: '', lonMax: '' });
  };

  const triggerPipelineRun = async (bbox_str, isReset = false) => {
    if (updateStatus !== 'idle') return;
    setUpdateStatus(isReset ? 'resetting' : 'applying');
    setError(null);

    if (bbox_str) setIsAoiSet(true);
    else {
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

      if (response.status !== 429 && !response.ok) {
        const result = await response.json();
        throw new Error(result.error || 'Failed to trigger pipeline');
      }

      if (bbox_str) {
        await sleep(15000); 
        fetchFireData(); 
      }

    } catch (err) {
      console.error('Failed to update AOI:', err);
      if (err.message.includes("Failed to fetch")) {
          setError("Server is offline. Please start server.py");
      } else {
          setError('Failed to update Area of Interest.');
      }
    } finally {
      setUpdateStatus('idle');
    }
  };
  
  const handleApplyBbox = (inputs) => {
    const { latMin, latMax, lonMin, lonMax } = inputs;
    if (latMin && latMax && lonMin && lonMax) {
      const bbox_str = [lonMin, latMin, lonMax, latMax].join(',');
      setAoiInputs(inputs);
      triggerPipelineRun(bbox_str, false);
    } else {
      setError("Please fill all four coordinates.");
    }
  }

  const handleUpdateAOI = () => handleApplyBbox(aoiInputs);

  const handleClearAndResetAOI = () => {
    if (updateStatus !== 'idle') return;
    clearAoiInputs();
    triggerPipelineRun("", true); 
  };

  const handleBasemapSelect = (selectedBasemap) => {
    setBasemap(selectedBasemap);
    setBasemapMenuOpen(false);
  };

  const formatFireDateTimeUTC = (fire) => {
    // Prefer acquisition date/time when available, otherwise fall back to datetime/timestamp
    let dateObj = null;
    if (fire.acq_time && fire.acq_date) {
      const acqTimeStr = fire.acq_time.toString().padStart(4, '0');
      const hours = parseInt(acqTimeStr.slice(0, 2));
      const minutes = parseInt(acqTimeStr.slice(2, 4));
      const [year, month, day] = fire.acq_date.split('-').map(Number);
      dateObj = new Date(Date.UTC(year, month - 1, day, hours, minutes));
    } else if (fire.datetime) {
      dateObj = new Date(fire.datetime);
    } else if (fire.timestamp) {
      dateObj = new Date(fire.timestamp);
    }

    if (!dateObj || isNaN(dateObj)) return 'N/A';

    const dateStr = dateObj.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' });
    const timeStr = dateObj.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true, timeZone: 'UTC' });
    return `${dateStr} — ${timeStr} UTC`;
  };

  if (isLoading && allFires.length === 0 && isAoiSet) {
    return (
      <div className="map-container">
        <div className="loading-overlay"><div className="loading-spinner"></div><p>Loading...</p></div>
      </div>
    );
  }

  return (
    <div className="map-container">
      {updateStatus !== 'idle' && (
        <div className="loading-overlay transparent">
            <div className="loading-spinner"></div>
            <p>{updateStatus === 'applying' ? 'Applying new AOI...' : 'Resetting...'}</p>
        </div>
      )}
      {error && (
          <div className="error-banner"><p>{error}</p><button onClick={() => setError(null)}>X</button></div>
      )}

      <MapContainer
        center={[54.5, -110.0]}
        zoom={6}
        minZoom={3}
        maxZoom={18}
        style={{ height: '100%', width: '100%' }}
        ref={mapRef}
        zoomControl={false}
        attributionControl={false}
      >
        <AttributionControl position="bottomleft" />
        {basemap === 'satellite' ? (
          <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            attribution='&copy; Esri'
          />
        ) : (
          <TileLayer
            url={`https://{s}.basemaps.cartocdn.com/${basemap === 'streets' && currentViewMode === 'validated' ? 'light' : 'dark'}_all/{z}/{x}/{y}{r}.png`}
            attribution='&copy; CARTO'
          />
        )}

        {filteredFires.map((fire, index) => {
          if (isNaN(fire.lat) || isNaN(fire.lng)) return null;

          return (
            <Marker
               key={`${fire.lat}-${fire.lng}-${index}`}
               position={[fire.lat, fire.lng]}
               icon={createFireIcon(fire.confidence_level)}
             >
              <Popup className="custom-popup">
                 <div className="popup-content">
                   {/* UPDATED POPUP LOGIC */}
                   {currentViewMode === 'raw' ? (
                     <h3>Raw Satellite Detection</h3>
                   ) : (
                     <h3>
                       {fire.confidence_level === 1 ? 'Moderate (40-60%)' :
                        fire.confidence_level === 2 ? 'High (60-85%)' : 
                        'Severe (85%+)'}
                     </h3>
                   )}
                   
                   <p style={{ textAlign: "right" }}><strong>Location:</strong> {safeToFixed(fire.lat, 4)}, {safeToFixed(fire.lng, 4)}</p>
                   
                   {typeof fire.confidence_score === 'number' && (
                     <p><strong>Score:</strong> {safeToFixed(fire.confidence_score, 1)}%</p>
                   )}
                   <p><strong>Date & Time:</strong> {formatFireDateTimeUTC(fire)}</p>
                 </div>
               </Popup>
            </Marker>
          )
        })}
        <MapZoomHandler onMapReady={setMapInstance} />
      </MapContainer>

      <ZoomControls onZoomIn={() => mapInstance?.zoomIn()} onZoomOut={() => mapInstance?.zoomOut()} />

      <div className="floating-basemap-menu">
        <button className="basemap-menu-button" onClick={() => setBasemapMenuOpen(!basemapMenuOpen)}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2L2 7L12 12L22 7L12 2Z"/><path d="M2 17L12 22L22 17"/><path d="M2 12L12 17L22 12"/></svg>
        </button>
        {basemapMenuOpen && (
          <div className="basemap-menu-options">
            <div className={`basemap-option ${basemap === 'streets' ? 'active' : ''}`} onClick={() => handleBasemapSelect('streets')}>
              <div className="basemap-thumbnail"><div className="thumbnail-preview streets"></div></div>
              <div className="basemap-label">Map</div>
            </div>
            <div className={`basemap-option ${basemap === 'satellite' ? 'active' : ''}`} onClick={() => handleBasemapSelect('satellite')}>
              <div className="basemap-thumbnail"><div className="thumbnail-preview satellite"></div></div>
              <div className="basemap-label">Satellite</div>
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