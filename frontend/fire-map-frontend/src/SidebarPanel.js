import React, { useState } from 'react';
import './SidebarPanel.css';

const SidebarPanel = ({ 
  fireCount, 
  totalFireCount, 
  confidenceFilters, 
  toggleConfidenceFilter,
  timeRange,
  handleTimeRangeChange,
  handleUpdateAOI,
  updateStatus,
  aoiInputs,
  handleAoiInputChange,
  handleClearAndResetAOI
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const isBusy = updateStatus !== 'idle';

  return (
    <div className="sidebar-wrapper">
      <div className={`sidebar-panel ${isCollapsed ? 'collapsed' : ''}`}>
        
        {/* Toggle Button */}
        <button 
          className="toggle-button"
          onClick={() => setIsCollapsed(!isCollapsed)}
          aria-label={isCollapsed ? 'Expand panel' : 'Collapse panel'}
        >
          <span className={`toggle-icon ${isCollapsed ? 'collapsed' : ''}`}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M7 10L12 15L17 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </span>
        </button>

        {/* Header */}
        <div className="panel-header">
          <h2>FireWatch Analytics</h2>
          {!isCollapsed && (
            <div className="fire-count">
              <span className="count">{fireCount}</span> of <span className="total">{totalFireCount}</span> fires visible
            </div>
          )}
        </div>

        {!isCollapsed && (
          <div className="panel-content">
            {/* Time Range */}
            <div className="panel-section">
              <h3>Time Range</h3>
              <div className="time-filter">
                {[
                  { value: 'all', label: 'All Time', icon: '∞' },
                  { value: '24h', label: 'Last 24h', icon: '⏱' },
                  { value: '7d', label: 'Last 7 Days', icon: '📅' },
                  { value: '30d', label: 'Last 30 Days', icon: '📆' }
                ].map(option => (
                  <div 
                    key={option.value}
                    className={`time-option ${timeRange === option.value ? 'active' : ''}`}
                    onClick={() => handleTimeRangeChange(option.value)}
                  >
                    <span className="time-icon">{option.icon}</span>
                    <span className="time-label">{option.label}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Confidence Levels */}
            <div className="panel-section">
              <h3>Confidence Level</h3>
              <div className="confidence-filter">
                {[1, 2, 3, 4].map(level => (
                  <div 
                    key={level}
                    className={`confidence-toggle ${confidenceFilters[level] ? 'active' : ''}`}
                    onClick={() => toggleConfidenceFilter(level)}
                  >
                    <div className="toggle-track">
                      <div className="toggle-thumb"></div>
                    </div>
                    <div className="confidence-info">
                      <div className={`confidence-dot level-${level}`}></div>
                      <span className="confidence-label">Level {level}</span>
                    </div>
                    <div className="confidence-desc">
                      {level === 1 && 'Low'}
                      {level === 2 && 'Medium'}
                      {level === 3 && 'High'}
                      {level === 4 && 'Very High'}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* AOI */}
            <div className="panel-section">
              <h3>Area of Interest</h3>
              <div className="aoi-form">
                <div className="form-row">
                  <div className="form-group">
                    <label>Latitude Min</label>
                    <input 
                      type="number" 
                      placeholder="e.g., 53.4" 
                      name="latMin"
                      value={aoiInputs.latMin}
                      onChange={handleAoiInputChange}
                    />
                  </div>
                  <div className="form-group">
                    <label>Latitude Max</label>
                    <input 
                      type="number" 
                      placeholder="e.g., 53.5" 
                      name="latMax"
                      value={aoiInputs.latMax}
                      onChange={handleAoiInputChange}
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Longitude Min</label>
                    <input 
                      type="number" 
                      placeholder="e.g., -104.2" 
                      name="lonMin"
                      value={aoiInputs.lonMin}
                      onChange={handleAoiInputChange}
                    />
                  </div>
                  <div className="form-group">
                    <label>Longitude Max</label>
                    <input 
                      type="number" 
                      placeholder="e.g., -104.1"
                      name="lonMax"
                      value={aoiInputs.lonMax}
                      onChange={handleAoiInputChange}
                    />
                  </div>
                </div>
                <div className="form-actions">
                  <button 
                    className="apply-btn"
                    onClick={handleUpdateAOI}
                    disabled={isBusy}
                  >
                    {updateStatus === 'applying' ? 'Applying...' : 'Apply AOI'}
                  </button>
                  <button 
                    className="clear-btn"
                    onClick={handleClearAndResetAOI}
                    disabled={isBusy}
                  >
                    {updateStatus === 'resetting' ? 'Resetting...' : 'Clear & Reset'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SidebarPanel;
