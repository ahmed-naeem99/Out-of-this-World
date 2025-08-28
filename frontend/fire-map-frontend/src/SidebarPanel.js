import React from 'react';
import './SidebarPanel.css';

const SidebarPanel = ({ 
  fireCount, 
  totalFireCount, 
  confidenceFilters, 
  toggleConfidenceFilter,
  timeRange,
  handleTimeRangeChange
}) => {
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
        <h3>Time Range</h3>
        <div className="time-filter">
          {[
            { value: 'all', label: 'All Time' },
            { value: '24h', label: 'Last 24h' },
            { value: '7d', label: 'Last 7 Days' },
            { value: '30d', label: 'Last 30 Days' }
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

      <div className="panel-section">
        <h3>Area of Interest</h3>
        <p className="placeholder">AOI controls coming soon…</p>
      </div>
    </div>
  );
};

export default SidebarPanel;