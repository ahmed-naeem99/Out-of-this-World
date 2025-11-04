import React, { useState } from 'react';
import './SidebarPanel.css';

const SidebarPanel = ({ 
  fireCount, 
  totalFireCount, 
  confidenceFilters, 
  toggleConfidenceFilter,
  // --- MODIFIED: New Time Props ---
  timeRange,
  handleTimeRangeChange,
  daysSlider,
  handleDaysSliderChange,
  // --- AOI Props ---
  handleUpdateAOI,
  updateStatus,
  aoiInputs,
  handleAoiInputChange,
  handleClearAndResetAOI
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const isBusy = updateStatus !== 'idle';
  
  // Helper function to wrap the time range change for the buttons
  const handleTimeButtonChange = (value) => {
    // For the buttons, we pass the range and a default day count
    if (value === 'today') {
      handleTimeRangeChange(value, 1);
    } else if (value === '7d') {
      handleTimeRangeChange(value, 7);
    }
  }

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
            {/* Time Range - MODIFIED */}
            <div className="panel-section">
              <h3>Time Range</h3>
              <div className="time-filter">
                {[
                  { value: 'today', label: 'Today', icon: '☀️' },
                  { value: '7d', label: 'Last 7 Days', icon: '📅' },
                ].map(option => (
                  <div 
                    key={option.value}
                    // Check if the range is 'daysSlider' and the days match
                    className={`time-option ${timeRange === option.value ? 'active' : ''}`}
                    onClick={() => handleTimeButtonChange(option.value)}
                  >
                    <span className="time-icon">{option.icon}</span>
                    <span className="time-label">{option.label}</span>
                  </div>
                ))}
              </div>
              
              {/* New Days Slider */}
              <div className="days-slider-container">
                <label>Past {daysSlider} Days</label>
                <input 
                  type="range" 
                  min="1" 
                  max="7" 
                  value={daysSlider}
                  // Set the range to 'daysSlider' when the user starts dragging/clicking the slider
                  onMouseDown={() => timeRange !== 'daysSlider' && handleTimeRangeChange('daysSlider', daysSlider)}
                  onMouseUp={handleDaysSliderChange} // Trigger API call on release
                  onChange={handleDaysSliderChange} // Update value instantly
                  className={`days-slider ${timeRange === 'daysSlider' ? 'active' : ''}`}
                />
              </div>
            </div>

            {/* Confidence Levels (Unchanged) */}
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

            {/* AOI (Unchanged functionality, new placeholders for context) */}
            <div className="panel-section">
              <h3>Area of Interest</h3>
              <div className="aoi-form">
                <div className="form-row">
                  <div className="form-group">
                    <label>Latitude Min</label>
                    <input 
                      type="number" 
                      placeholder="e.g., 53.2" 
                      name="latMin"
                      value={aoiInputs.latMin}
                      onChange={handleAoiInputChange}
                    />
                  </div>
                  <div className="form-group">
                    <label>Latitude Max</label>
                    <input 
                      type="number" 
                      placeholder="e.g., 60.9" 
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
                      placeholder="e.g., -110.1" 
                      name="lonMin"
                      value={aoiInputs.lonMin}
                      onChange={handleAoiInputChange}
                    />
                  </div>
                  <div className="form-group">
                    <label>Longitude Max</label>
                    <input 
                      type="number" 
                      placeholder="e.g., -100.5"
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