export const parseBboxFromEnv = () => {
  const bboxStr = process.env.REACT_APP_DEFAULT_BBOX;
  if (!bboxStr) return { latMin: '40', latMax: '90', lonMin: '-141', lonMax: '-52' };
  const [lonMin, latMin, lonMax, latMax] = bboxStr.split(',').map(v => v.trim());
  return { latMin, latMax, lonMin, lonMax };
};

export const safeToFixed = (val, digits = 1) => {
  if (typeof val === 'number' && !isNaN(val)) return val.toFixed(digits);
  return 'N/A';
};

// Returns ISO string for (now - daysBack days).
// Pass an explicit `now` for demo mode or deterministic tests.
export const getSinceParam = (daysBack, now = new Date()) => {
  const since = new Date(now.getTime() - daysBack * 24 * 60 * 60 * 1000);
  return since.toISOString().replace(/\.000Z$/, 'Z');
};

export const applyFilters = (fires, confidenceFilters) => {
  const activeLevels = new Set(
    Object.entries(confidenceFilters)
      .filter(([, active]) => active)
      .map(([level]) => parseInt(level))
  );
  return fires.filter(fire => activeLevels.has(fire.confidence_level));
};

export const formatFireDateTimeUTC = (fire) => {
  let dateObj = null;
  if (fire.acq_time != null && fire.acq_date) {
    const timeStr = fire.acq_time.toString().padStart(4, '0');
    const hours = parseInt(timeStr.slice(0, 2));
    const minutes = parseInt(timeStr.slice(2, 4));
    const [year, month, day] = fire.acq_date.split('-').map(Number);
    dateObj = new Date(Date.UTC(year, month - 1, day, hours, minutes));
  } else if (fire.datetime) {
    dateObj = new Date(fire.datetime);
  } else if (fire.timestamp) {
    dateObj = new Date(fire.timestamp);
  }

  if (!dateObj || isNaN(dateObj)) return 'N/A';

  const dateStr = dateObj.toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC',
  });
  const timeStr = dateObj.toLocaleTimeString('en-US', {
    hour: 'numeric', minute: '2-digit', hour12: true, timeZone: 'UTC',
  });
  return `${dateStr} — ${timeStr} UTC`;
};
