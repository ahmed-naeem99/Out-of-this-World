import React, { useState } from 'react';
import './SidebarPanel.css';

const SidebarPanel = ({ 
  fireCount, 
  totalFireCount, 
  confidenceFilters, 
  toggleConfidenceFilter,
  timeRange,
  handleTimeRangeChange
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <div className="sidebar-wrapper">
      <div className={`sidebar-panel ${isCollapsed ? 'collapsed' : ''}`}>
        <button 
          className="toggle-button"
          onClick={() => setIsCollapsed(!isCollapsed)}
        >
          {isCollapsed ? '▼' : '▲'}
        </button>

        <div className="panel-header">
          <h2>FireWatch Controls</h2>
          {!isCollapsed && (
            <div className="fire-count">
              Showing {fireCount} of {totalFireCount} fires
            </div>
          )}
        </div>

        {!isCollapsed && (
          <>
            <div className="panel-section">
              <h3>Confidence Level</h3>
              <div className="confidence-filter">
                {[1, 2, 3, 4].map(level => (
                  <div 
                    key={level}
                    className={`confidence-toggle ${confidenceFilters[level] ? 'active' : ''}`}
                    onClick={() => toggleConfidenceFilter(level)}
                  >
                    <div className={`confidence-dot level-${level}`}></div>
                    <span className="confidence-label">Level {level}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="panel-section">
              <h3>Area of Interest</h3>
              <div className="aoi-form">
                <div className="form-group">
                  <label>Latitude Min</label>
                  <input type="number" placeholder="Enter min latitude" />
                </div>
                <div className="form-group">
                  <label>Latitude Max</label>
                  <input type="number" placeholder="Enter max latitude" />
                </div>
                <div className="form-group">
                  <label>Longitude Min</label>
                  <input type="number" placeholder="Enter min longitude" />
                </div>
                <div className="form-group">
                  <label>Longitude Max</label>
                  <input type="number" placeholder="Enter max longitude" />
                </div>
                <div className="form-actions">
                  <button className="apply-btn">Apply AOI</button>
                  <button className="clear-btn">Clear</button>
                </div>
              </div>
            </div>

            <div className="panel-section">
              <h3>Time Range</h3>
              <div className="time-filter">
                {[
                  { value: 'all', label: 'All Time' },
                  { value: '24h', label: 'Last 24h' }
                ].map(option => (
                  <div 
                    key={option.value}
                    className={`time-option ${timeRange === option.value ? 'active' : ''}`}
                    onClick={() => handleTimeRangeChange(option.value)}
                  >
                    {option.label}
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default SidebarPanel;