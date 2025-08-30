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
          aria-label={isCollapsed ? 'Expand panel' : 'Collapse panel'}
        >
          <span className={`toggle-icon ${isCollapsed ? 'collapsed' : ''}`}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M7 10L12 15L17 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </span>
        </button>

        <div className="panel-header">
          <div className="title-section">
            <div className="logo">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M17.5 15.5C17.5 19.5 14.5 22 12 22C9.5 22 6.5 19.5 6.5 15.5C6.5 12.5 9.5 8.5 12 6.5C14.5 8.5 17.5 12.5 17.5 15.5Z" stroke="#FF5E5B" strokeWidth="2"/>
                <path d="M12 2C12 2 15 4.5 15 8C15 11.5 12 11.5 12 11.5C12 11.5 9 11.5 9 8C9 4.5 12 2 12 2Z" fill="#FF5E5B"/>
              </svg>
            </div>
            <h2>FireWatch Analytics</h2>
          </div>
          {!isCollapsed && (
            <div className="fire-count">
              <span className="count">{fireCount}</span> of <span className="total">{totalFireCount}</span> fires visible
            </div>
          )}
        </div>

        {!isCollapsed && (
          <>
            <div className="panel-section">
              <h3>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 8V12L15 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2"/>
                </svg>
                Time Range
              </h3>
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

            <div className="panel-section">
              <h3>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" stroke="currentColor" strokeWidth="2"/>
                  <path d="M7 12H17" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  <path d="M12 7V17" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
                Confidence Level
              </h3>
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

            <div className="panel-section">
              <h3>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" stroke="currentColor" strokeWidth="2"/>
                  <path d="M12 6V12L16 14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                Area of Interest
              </h3>
              <div className="aoi-form">
                <div className="form-row">
                  <div className="form-group">
                    <label>Latitude Min</label>
                    <input type="number" placeholder="e.g., 48.0" />
                  </div>
                  <div className="form-group">
                    <label>Latitude Max</label>
                    <input type="number" placeholder="e.g., 60.0" />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Longitude Min</label>
                    <input type="number" placeholder="e.g., -140.0" />
                  </div>
                  <div className="form-group">
                    <label>Longitude Max</label>
                    <input type="number" placeholder="e.g., -110.0" />
                  </div>
                </div>
                <div className="form-actions">
                  <button className="apply-btn">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M5 13L9 17L19 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    Apply AOI
                  </button>
                  <button className="clear-btn">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M6 6L18 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    Clear
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default SidebarPanel;