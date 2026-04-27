import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import './MapComponent.css';
import { MapContainer, TileLayer, Marker, Popup, CircleMarker, AttributionControl, useMap } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import L from 'leaflet';
import SidebarPanel from './SidebarPanel';
import { parseBboxFromEnv, safeToFixed, formatFireDateTimeUTC, getSinceParam, applyFilters } from './utils';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

// Builds a ping-style icon: solid core dot + pulsing outer ring
const makePingIcon = (color, totalSize, className = '') => {
  const core = Math.round(totalSize * 0.42);
  const anchor = totalSize / 2;
  return L.divIcon({
    html: `<div class="ping-wrap" style="width:${totalSize}px;height:${totalSize}px;">
      <div class="ping-core" style="width:${core}px;height:${core}px;background:${color};box-shadow:0 0 6px ${color}99;"></div>
      <div class="ping-ring" style="width:${totalSize}px;height:${totalSize}px;border-color:${color};"></div>
    </div>`,
    className: `ping-icon ${className}`,
    iconSize: [totalSize, totalSize],
    iconAnchor: [anchor, anchor],
  });
};

// Individual fire markers — 3 sizes by confidence level
const FIRE_ICONS = {
  1: makePingIcon('#FFA500', 18),
  2: makePingIcon('#FF5500', 24),
  3: makePingIcon('#FF1100', 30),
};

// Cluster icon — same ping style, scales with count, color shifts with density
const createClusterIcon = (cluster) => {
  const count = cluster.getChildCount();
  const size  = count < 10 ? 32 : count < 50 ? 42 : count < 200 ? 52 : 62;
  const color = count < 10 ? '#FFA500' : count < 50 ? '#FF5500' : '#FF1100';
  return makePingIcon(color, size, 'ping-cluster');
};

// Canvas renderer for raw layer — renders all circle markers in a single draw call
const CANVAS_RENDERER = L.canvas({ padding: 0.5 });

// Raw layer dot colors by confidence level
const LEVEL_COLORS = { 1: '#FFA500', 2: '#FF4500', 3: '#FF0000' };

// REACT_APP_DEMO_ANCHOR in .env pins time queries to demo data.
// Leave unset in production for live dates.
const DEMO_ANCHOR = process.env.REACT_APP_DEMO_ANCHOR
  ? new Date(process.env.REACT_APP_DEMO_ANCHOR)
  : undefined;

const DEFAULT_MAP_BBOX = parseBboxFromEnv();

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

function ZoomControls({ onZoomIn, onZoomOut }) {
  return (
    <div className="floating-zoom-controls">
      <button className="zoom-btn zoom-in" onClick={onZoomIn} aria-label="Zoom in">+</button>
      <button className="zoom-btn zoom-out" onClick={onZoomOut} aria-label="Zoom out">−</button>
    </div>
  );
}

function MapZoomHandler({ onMapReady }) {
  const map = useMap();

  useEffect(() => {
    if (map && onMapReady) onMapReady(map);
  }, [map, onMapReady]);

  useEffect(() => {
    if (!map) return;
    const id = setTimeout(() => map.invalidateSize(), 100);
    return () => clearTimeout(id);
  }, [map]);

  useEffect(() => {
    if (!map) return;
    const handler = () => setTimeout(() => map.invalidateSize(), 100);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, [map]);

  return null;
}

function MapComponent({ viewMode: initialViewMode = 'validated' }) {
  const [allFires, setAllFires]         = useState([]);
  const [isAoiSet, setIsAoiSet]         = useState(true);
  const [isLoading, setIsLoading]       = useState(false);
  const [error, setError]               = useState(null);
  const [updateStatus, setUpdateStatus] = useState('idle');
  const [aoiInputs, setAoiInputs]       = useState(DEFAULT_MAP_BBOX);
  const [confidenceFilters, setConfidenceFilters] = useState({ 1: true, 2: true, 3: true });
  const [daysSlider, setDaysSlider]     = useState(7);
  const [basemap, setBasemap]           = useState('streets');
  const [mapInstance, setMapInstance]   = useState(null);
  const [basemapMenuOpen, setBasemapMenuOpen] = useState(false);
  const mapRef = useRef();

  const filteredFires = useMemo(
    () => applyFilters(allFires, confidenceFilters),
    [allFires, confidenceFilters]
  );

  const fetchFireData = useCallback(() => {
    if (!isAoiSet) return;
    const endpoint = initialViewMode === 'raw' ? '/api/raw_fires' : '/api/fires';
    setIsLoading(true);
    setError(null);

    const since = getSinceParam(daysSlider, DEMO_ANCHOR);
    fetch(`${process.env.REACT_APP_API_URL}${endpoint}?since=${since}`)
      .then(res => {
        if (!res.ok) throw new Error('Network response was not ok');
        return res.json();
      })
      .then(data => {
        const cleaned = (Array.isArray(data) ? data : []).map(fire => {
          const lat = parseFloat(fire.latitude);
          const lng = parseFloat(fire.longitude);
          if (isNaN(lat) || isNaN(lng)) return null;
          const parsedScore = parseFloat(fire.confidence_score);
          return {
            ...fire,
            lat, lng,
            latitude: lat,
            longitude: lng,
            timestamp: new Date(fire.datetime).getTime(),
            confidence_score: isNaN(parsedScore) ? null : parsedScore,
          };
        }).filter(Boolean);
        setAllFires(cleaned);
        setIsLoading(false);
      })
      .catch(err => {
        console.error('Failed to load fire data:', err);
        setError(err.message.includes('Failed to fetch')
          ? 'Server is offline. Please start server.py'
          : 'Failed to load fire data.');
        setIsLoading(false);
      });
  }, [isAoiSet, initialViewMode, daysSlider]);

  useEffect(() => {
    fetchFireData();
  }, [fetchFireData]);

  useEffect(() => {
    if (!basemapMenuOpen) return;
    const handler = (e) => {
      if (!e.target.closest('.floating-basemap-menu')) setBasemapMenuOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [basemapMenuOpen]);

  const toggleConfidenceFilter = useCallback((level) => {
    setConfidenceFilters(prev => ({ ...prev, [level]: !prev[level] }));
  }, []);

  const handleDaysCommit = useCallback((days) => {
    setDaysSlider(days);
  }, []);

  const handleAoiInputChange = (e) => {
    const { name, value } = e.target;
    setAoiInputs(prev => ({ ...prev, [name]: value }));
  };

  const triggerPipelineRun = async (bbox_str, isReset = false) => {
    if (updateStatus !== 'idle') return;
    setUpdateStatus(isReset ? 'resetting' : 'applying');
    setError(null);

    if (bbox_str) {
      setIsAoiSet(true);
    } else {
      setAllFires([]);
      setIsAoiSet(false);
    }

    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/run-pipeline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bbox: bbox_str }),
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
      setError(err.message.includes('Failed to fetch')
        ? 'Server is offline. Please start server.py'
        : 'Failed to update Area of Interest.');
    } finally {
      setUpdateStatus('idle');
    }
  };

  const handleUpdateAOI = () => {
    const { latMin, latMax, lonMin, lonMax } = aoiInputs;
    if (latMin && latMax && lonMin && lonMax) {
      triggerPipelineRun([lonMin, latMin, lonMax, latMax].join(','), false);
    } else {
      setError('Please fill all four coordinates.');
    }
  };

  const handleClearAndResetAOI = () => {
    if (updateStatus !== 'idle') return;
    setAoiInputs({ latMin: '', latMax: '', lonMin: '', lonMax: '' });
    triggerPipelineRun('', true);
  };

  if (isLoading && allFires.length === 0 && isAoiSet) {
    return (
      <div className="map-container">
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <p>Loading...</p>
        </div>
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
        <div className="error-banner">
          <p>{error}</p>
          <button onClick={() => setError(null)}>X</button>
        </div>
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

        {/* Basemap tiles */}
        {basemap === 'satellite' ? (
          <>
            <TileLayer
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              attribution="&copy; Esri"
              maxZoom={19}
            />
            {/* Label overlay — city names, roads, boundaries on top of imagery */}
            <TileLayer
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
              attribution=""
              maxZoom={19}
              opacity={0.85}
            />
          </>
        ) : (
          <TileLayer
            url={`https://{s}.basemaps.cartocdn.com/${
              initialViewMode === 'validated' ? 'light' : 'dark'
            }_all/{z}/{x}/{y}{r}.png`}
            attribution="&copy; CARTO"
          />
        )}

        {/* Validated layer — clustered fire icons */}
        {initialViewMode !== 'raw' && (
          <MarkerClusterGroup
            iconCreateFunction={createClusterIcon}
            chunkedLoading
            maxClusterRadius={60}
          >
            {filteredFires.map((fire, index) => (
              <Marker
                key={`${fire.lat}-${fire.lng}-${index}`}
                position={[fire.lat, fire.lng]}
                icon={FIRE_ICONS[fire.confidence_level] || FIRE_ICONS[1]}
              >
                <Popup className="custom-popup">
                  <div className="popup-content">
                    <h3>
                      {fire.confidence_level === 1 ? 'Moderate (40–60%)' :
                       fire.confidence_level === 2 ? 'High (60–85%)' :
                       'Severe (85%+)'}
                    </h3>
                    <p style={{ textAlign: 'right' }}>
                      <strong>Location:</strong> {safeToFixed(fire.lat, 4)}, {safeToFixed(fire.lng, 4)}
                    </p>
                    {typeof fire.confidence_score === 'number' && (
                      <p><strong>Score:</strong> {safeToFixed(fire.confidence_score, 1)}%</p>
                    )}
                    <p><strong>Date & Time:</strong> {formatFireDateTimeUTC(fire)}</p>
                  </div>
                </Popup>
              </Marker>
            ))}
          </MarkerClusterGroup>
        )}

        {/* Raw layer — canvas-rendered circles, all visible at any zoom, no clustering */}
        {initialViewMode === 'raw' && filteredFires.map((fire, index) => (
          <CircleMarker
            key={`${fire.lat}-${fire.lng}-${index}`}
            center={[fire.lat, fire.lng]}
            radius={5}
            renderer={CANVAS_RENDERER}
            pathOptions={{
              color: LEVEL_COLORS[fire.confidence_level] || LEVEL_COLORS[1],
              fillColor: LEVEL_COLORS[fire.confidence_level] || LEVEL_COLORS[1],
              fillOpacity: 0.75,
              weight: 1,
            }}
          >
            <Popup className="custom-popup">
              <div className="popup-content">
                <h3>Raw Satellite Detection</h3>
                <p style={{ textAlign: 'right' }}>
                  <strong>Location:</strong> {safeToFixed(fire.lat, 4)}, {safeToFixed(fire.lng, 4)}
                </p>
                <p><strong>Sensor:</strong> {fire.primary_sensor || 'N/A'}</p>
                <p><strong>Date & Time:</strong> {formatFireDateTimeUTC(fire)}</p>
              </div>
            </Popup>
          </CircleMarker>
        ))}

        <MapZoomHandler onMapReady={setMapInstance} />
      </MapContainer>

      <ZoomControls
        onZoomIn={() => mapInstance?.zoomIn()}
        onZoomOut={() => mapInstance?.zoomOut()}
      />

      <div className="floating-basemap-menu">
        <button
          className="basemap-menu-button"
          onClick={() => setBasemapMenuOpen(prev => !prev)}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2L2 7L12 12L22 7L12 2Z"/>
            <path d="M2 17L12 22L22 17"/>
            <path d="M2 12L12 17L22 12"/>
          </svg>
        </button>
        {basemapMenuOpen && (
          <div className="basemap-menu-options">
            <div
              className={`basemap-option ${basemap === 'streets' ? 'active' : ''}`}
              onClick={() => { setBasemap('streets'); setBasemapMenuOpen(false); }}
            >
              <div className="basemap-thumbnail"><div className="thumbnail-preview streets"></div></div>
              <div className="basemap-label">Map</div>
            </div>
            <div
              className={`basemap-option ${basemap === 'satellite' ? 'active' : ''}`}
              onClick={() => { setBasemap('satellite'); setBasemapMenuOpen(false); }}
            >
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
        daysSlider={daysSlider}
        onDaysCommit={handleDaysCommit}
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
