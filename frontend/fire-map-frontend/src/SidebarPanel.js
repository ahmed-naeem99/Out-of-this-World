import React, { useState, useEffect } from 'react';
import './SidebarPanel.css';

const SidebarPanel = ({
  fireCount,
  totalFireCount,
  confidenceFilters,
  toggleConfidenceFilter,
  daysSlider,
  onDaysCommit,
  handleUpdateAOI,
  updateStatus,
  aoiInputs,
  handleAoiInputChange,
  handleClearAndResetAOI,
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  // localDays tracks the visual slider position during drag without triggering a fetch
  const [localDays, setLocalDays] = useState(daysSlider);

  // Sync visual state when parent commits a new value (e.g. button click)
  useEffect(() => { setLocalDays(daysSlider); }, [daysSlider]);

  const isBusy = updateStatus !== 'idle';
  const sliderPercentage = ((localDays - 1) / 6) * 100;
  const sliderStyle = {
    background: `linear-gradient(to right, var(--primary) 0%, var(--primary) ${sliderPercentage}%, rgba(184, 180, 180, 0.2) ${sliderPercentage}%, rgba(184, 180, 180, 0.2) 100%)`,
  };

  const isToday  = daysSlider === 1;
  const is7Days  = daysSlider === 7;
  const isPreset = isToday || is7Days;

  return (
    <div className="sidebar-wrapper">
      <div className={`sidebar-panel ${isCollapsed ? 'collapsed' : ''}`}>

        <button
          className="toggle-button"
          onClick={() => setIsCollapsed(c => !c)}
          aria-label={isCollapsed ? 'Expand panel' : 'Collapse panel'}
        >
          <span className={`toggle-icon ${isCollapsed ? 'collapsed' : ''}`}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M7 10L12 15L17 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </span>
        </button>

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

            <div className="panel-section">
              <h3>Time Range</h3>
              <div className="time-filter">
                <div
                  className={`time-option ${isToday ? 'active' : ''}`}
                  onClick={() => onDaysCommit(1)}
                >
                  <span className="time-label">Today</span>
                </div>
                <div
                  className={`time-option ${is7Days ? 'active' : ''}`}
                  onClick={() => onDaysCommit(7)}
                >
                  <span className="time-label">Last 7 Days</span>
                </div>
              </div>

              <div className={`days-slider-container ${isPreset ? 'passive-mode' : ''}`}>
                <label>
                  {isToday ? 'Showing Today' :
                   is7Days ? 'Showing Last 7 Days' :
                   `Past ${localDays} Days`}
                </label>
                <input
                  type="range"
                  min="1"
                  max="7"
                  value={localDays}
                  style={sliderStyle}
                  onChange={e => setLocalDays(parseInt(e.target.value))}
                  onMouseUp={() => onDaysCommit(localDays)}
                  className={`days-slider ${!isPreset ? 'active' : ''}`}
                />
                <div className="slider-labels">
                  <span>1d</span>
                  <span>7d</span>
                </div>
              </div>
            </div>

            <div className="panel-section">
              <h3>Confidence Level</h3>
              <div className="confidence-filter">
                {[1, 2, 3].map(level => (
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
                      {level === 1 && 'Level 1 (40-60%)'}
                      {level === 2 && 'Level 2 (60-85%)'}
                      {level === 3 && 'Level 3 (85+%)'}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="panel-section">
              <h3>Area of Interest</h3>
              <div className="aoi-form">
                <div className="form-row">
                  <div className="form-group">
                    <label>Lat Min</label>
                    <input type="number" placeholder="53.2" name="latMin" value={aoiInputs.latMin} onChange={handleAoiInputChange} />
                  </div>
                  <div className="form-group">
                    <label>Lat Max</label>
                    <input type="number" placeholder="60.9" name="latMax" value={aoiInputs.latMax} onChange={handleAoiInputChange} />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Lon Min</label>
                    <input type="number" placeholder="-110.1" name="lonMin" value={aoiInputs.lonMin} onChange={handleAoiInputChange} />
                  </div>
                  <div className="form-group">
                    <label>Lon Max</label>
                    <input type="number" placeholder="-100.5" name="lonMax" value={aoiInputs.lonMax} onChange={handleAoiInputChange} />
                  </div>
                </div>
                <div className="form-actions">
                  <button className="apply-btn" onClick={handleUpdateAOI} disabled={isBusy}>
                    {updateStatus === 'applying' ? 'Applying...' : 'Apply AOI'}
                  </button>
                  <button className="clear-btn" onClick={handleClearAndResetAOI} disabled={isBusy}>
                    {updateStatus === 'resetting' ? 'Resetting...' : 'Reset'}
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
