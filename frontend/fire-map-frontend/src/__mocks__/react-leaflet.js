const React = require('react');

const MapContainer = ({ children }) =>
  React.createElement('div', { 'data-testid': 'map-container' }, children);

const TileLayer = () => null;

const Marker = ({ children, position }) =>
  React.createElement('div', { 'data-testid': 'marker', 'data-position': position?.join(',') }, children);

const Popup = ({ children }) =>
  React.createElement('div', { 'data-testid': 'popup' }, children);

const AttributionControl = () => null;

const useMap = () => ({
  invalidateSize: jest.fn(),
  zoomIn: jest.fn(),
  zoomOut: jest.fn(),
  fitBounds: jest.fn(),
  on: jest.fn(),
  off: jest.fn(),
});

const CircleMarker = ({ children, center }) =>
  React.createElement('div', { 'data-testid': 'circle-marker', 'data-center': center?.join(',') }, children);

module.exports = { MapContainer, TileLayer, Marker, Popup, AttributionControl, useMap, CircleMarker };
