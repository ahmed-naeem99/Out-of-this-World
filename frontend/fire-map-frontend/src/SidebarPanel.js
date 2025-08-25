import React, { useState } from 'react';
import './SidebarPanel.css';

const SidebarPanel = ({ filters, onFilterChange, fireCount, totalFireCount }) => {
  const [aoiForm, setAoiForm] = useState({
    lat: '',
    lng: '',
    radius: '50'
  });

  const handleConfidenceToggle = (level) => {
    const newLevels = filters.confidenceLevels.includes(level)
      ? filters.confidenceLevels.filter(l => l !== level)
      : [...filters.confidenceLevels, level];
    
    onFilterChange({
      ...filters,
      confidenceLevels: newLevels
    });
  };

  const handleTimeRangeChange = (range) => {
    onFilterChange({
      ...fires,
      timeRange: range
    });
  };

  const handleAoiSubmit = (e) => {
    e.preventDefault();
    
    if (aoiForm.lat && aoiForm.lng && aoiForm.radius) {
      onFilterChange({
        ...filters,
        areaOfInterest: {
          lat: parseFloat(aoiForm.lat),
          lng: parseFloat(aoiForm.lng),
          radius: parseFloat(aoiForm.radius)
        }
      });
    }
  };

  const clearAoi = () => {
    setAoiForm({ lat: '', lng: '', radius: '50' });
    onFilterChange({
      ...filters,
      areaOfInterest: null
    });
  };

  return (
    <div className="sidebar-panel">
      <div className="panel-header">
        <h2>FireWatch Controls</h2>
        <div className="fire-count">
          Showing {fireCount} of {totalFireCount} fires
        </div>
      </div>

      <div className="panel-section">
        <h3>Confidence Level</h3>
        <div className="confidence-filter">
          {[1, 2, 3, 4].map(level => (
            <div 
              key={level}
              className={`confidence-toggle ${filters.confidenceLevels.includes(level) ? 'active' : ''}`}
              onClick={() => handleConfidenceToggle(level)}
            >
              <span className={`confidence-dot level-${level}`}></span>
              <span className="confidence-label">
                {level === 1 && 'Low'}
                {level === 2 && 'Medium'}
                {level === 3 && 'High'}
                {level === 4 && 'Very High'}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="panel-section">
        <h3>Time Range</h3>
        <div className="time-filter">
          {[
            { value: 'all', label: 'All Time' },
            { value: '24h', label: 'Last 24 Hours' },
            { value: '7d', label: 'Last 7 Days' },
            { value: '30d', label: 'Last 30 Days' }
          ].map(option => (
            <div 
              key={option.value}
              className={`time-option ${filters.timeRange === option.value ? 'active' : ''}`}
              onClick={() => handleTimeRangeChange(option.value)}
            >
              {option.label}
            </div>
          ))}
        </div>
      </div>

      <div className="panel-section">
        <h3>Area of Interest</h3>
        <form className="aoi-form" onSubmit={handleAoiSubmit}>
          <div className="form-group">
            <label>Latitude</label>
            <input 
              type="number" 
              step="any"
              value={aoiForm.lat}
              onChange={(e) => setAoiForm({...aoiForm, lat: e.target.value})}
              placeholder="e.g., 51.0447"
            />
          </div>
          <div className="form-group">
            <label>Longitude</label>
            <input 
              type="number" 
              step="any"
              value={aoiForm.lng}
              onChange={(e) => setAoiForm({...aoiForm, lng: e.target.value})}
              placeholder="e.g., -114.0719"
            />
          </div>
          <div className="form-group">
            <label>Radius (km)</label>
            <input 
              type="number" 
              value={aoiForm.radius}
              onChange={(e) => setAoiForm({...aoiForm, radius: e.target.value})}
              min="1"
              max="1000"
            />
          </div>
          <div className="form-actions">
            <button type="submit" className="apply-btn">
              Apply Area Filter
            </button>
            {filters.areaOfInterest && (
              <button type="button" className="clear-btn" onClick={clearAoi}>
                Clear
              </button>
            )}
          </div>
        </form>
      </div>

      <div className="panel-section">
        <h3>Export Data</h3>
        <p>Download current view data for analysis</p>
        <button className="export-btn">
          Export CSV
        </button>
      </div>
    </div>
  );
};

export default SidebarPanel;