import React from 'react';
import './SidebarPanel.css';

const SidebarPanel = ({ fireCount, totalFireCount }) => {
  return (
    <div className="sidebar-panel">
      <div className="panel-header">
        <h2>FireWatch Controls</h2>
        <div className="fire-count">
          Showing {fireCount} of {totalFireCount} fires
        </div>
      </div>

      {/* Placeholder sections just for UI */}
      <div className="panel-section">
        <h3>Confidence Level</h3>
        <p className="placeholder">Filter controls coming soon…</p>
      </div>

      <div className="panel-section">
        <h3>Time Range</h3>
        <p className="placeholder">Time range filter coming soon…</p>
      </div>

      <div className="panel-section">
        <h3>Area of Interest</h3>
        <p className="placeholder">AOI controls coming soon…</p>
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
