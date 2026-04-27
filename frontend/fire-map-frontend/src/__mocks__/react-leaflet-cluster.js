const React = require('react');

const MarkerClusterGroup = ({ children }) =>
  React.createElement('div', { 'data-testid': 'cluster-group' }, children);

module.exports = MarkerClusterGroup;
