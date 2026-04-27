import { parseBboxFromEnv, safeToFixed, getSinceParam, applyFilters, formatFireDateTimeUTC } from './utils';

// ─── safeToFixed ────────────────────────────────────────────────────────────

describe('safeToFixed', () => {
  test('formats a valid positive number', () => {
    expect(safeToFixed(12.3456, 2)).toBe('12.35');
  });
  test('formats zero', () => {
    expect(safeToFixed(0, 1)).toBe('0.0');
  });
  test('returns N/A for NaN', () => {
    expect(safeToFixed(NaN)).toBe('N/A');
  });
  test('returns N/A for undefined', () => {
    expect(safeToFixed(undefined)).toBe('N/A');
  });
  test('returns N/A for null', () => {
    expect(safeToFixed(null)).toBe('N/A');
  });
  test('returns N/A for a numeric string (not a number type)', () => {
    expect(safeToFixed('12.3')).toBe('N/A');
  });
});

// ─── getSinceParam ──────────────────────────────────────────────────────────

describe('getSinceParam', () => {
  const anchor = new Date('2025-08-17T00:00:00.000Z');

  test('subtracts 7 days from anchor', () => {
    expect(getSinceParam(7, anchor)).toBe('2025-08-10T00:00:00Z');
  });
  test('subtracts 1 day from anchor', () => {
    expect(getSinceParam(1, anchor)).toBe('2025-08-16T00:00:00Z');
  });
  test('subtracts 0 days (returns anchor)', () => {
    expect(getSinceParam(0, anchor)).toBe('2025-08-17T00:00:00Z');
  });
  test('result has no .000Z suffix', () => {
    expect(getSinceParam(7, anchor)).not.toContain('.000');
  });
  test('result matches ISO format', () => {
    expect(getSinceParam(7, anchor)).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
  });
  test('defaults to current time when no anchor provided', () => {
    const before = Date.now();
    const result = getSinceParam(1);
    const after = Date.now();
    const resultMs = new Date(result).getTime();
    expect(resultMs).toBeGreaterThanOrEqual(before - 24 * 3600 * 1000 - 1000);
    expect(resultMs).toBeLessThanOrEqual(after - 24 * 3600 * 1000 + 1000);
  });
});

// ─── applyFilters ────────────────────────────────────────────────────────────

describe('applyFilters', () => {
  const fires = [
    { confidence_level: 1 },
    { confidence_level: 2 },
    { confidence_level: 3 },
    { confidence_level: 2 },
  ];

  test('returns all fires when all levels active', () => {
    expect(applyFilters(fires, { 1: true, 2: true, 3: true })).toHaveLength(4);
  });
  test('filters to level 3 only', () => {
    const result = applyFilters(fires, { 1: false, 2: false, 3: true });
    expect(result).toHaveLength(1);
    expect(result[0].confidence_level).toBe(3);
  });
  test('returns empty when all levels disabled', () => {
    expect(applyFilters(fires, { 1: false, 2: false, 3: false })).toHaveLength(0);
  });
  test('filters levels 2 and 3', () => {
    const result = applyFilters(fires, { 1: false, 2: true, 3: true });
    expect(result).toHaveLength(3);
    expect(result.every(f => f.confidence_level >= 2)).toBe(true);
  });
  test('handles empty fires array', () => {
    expect(applyFilters([], { 1: true, 2: true, 3: true })).toHaveLength(0);
  });
  test('does not mutate the input array', () => {
    const original = [...fires];
    applyFilters(fires, { 1: false, 2: false, 3: true });
    expect(fires).toEqual(original);
  });
});

// ─── formatFireDateTimeUTC ───────────────────────────────────────────────────

describe('formatFireDateTimeUTC', () => {
  test('formats fire with acq_date and acq_time', () => {
    const result = formatFireDateTimeUTC({ acq_date: '2025-08-15', acq_time: 1430 });
    expect(result).toContain('Aug 15, 2025');
    expect(result).toContain('UTC');
  });
  test('pads single-digit hour acq_time', () => {
    const result = formatFireDateTimeUTC({ acq_date: '2025-08-15', acq_time: 900 });
    expect(result).not.toBe('N/A');
    expect(result).toContain('Aug 15, 2025');
  });
  test('falls back to datetime field', () => {
    const result = formatFireDateTimeUTC({ datetime: '2025-08-15T14:30:00Z' });
    expect(result).toContain('Aug 15, 2025');
    expect(result).toContain('UTC');
  });
  test('falls back to timestamp field', () => {
    const result = formatFireDateTimeUTC({ timestamp: new Date('2025-08-15T14:30:00Z').getTime() });
    expect(result).toContain('Aug 15, 2025');
  });
  test('returns N/A for empty fire object', () => {
    expect(formatFireDateTimeUTC({})).toBe('N/A');
  });
  test('returns N/A for invalid datetime string', () => {
    expect(formatFireDateTimeUTC({ datetime: 'not-a-date' })).toBe('N/A');
  });
  test('acq_date+acq_time takes priority over datetime', () => {
    const result = formatFireDateTimeUTC({
      acq_date: '2025-08-10',
      acq_time: 1200,
      datetime: '2025-08-15T14:30:00Z',
    });
    expect(result).toContain('Aug 10, 2025');
  });
});

// ─── parseBboxFromEnv ────────────────────────────────────────────────────────

describe('parseBboxFromEnv', () => {
  const original = process.env.REACT_APP_DEFAULT_BBOX;

  afterEach(() => {
    if (original === undefined) delete process.env.REACT_APP_DEFAULT_BBOX;
    else process.env.REACT_APP_DEFAULT_BBOX = original;
  });

  test('returns hardcoded defaults when env not set', () => {
    delete process.env.REACT_APP_DEFAULT_BBOX;
    expect(parseBboxFromEnv()).toEqual({ latMin: '40', latMax: '90', lonMin: '-141', lonMax: '-52' });
  });
  test('parses lon_min,lat_min,lon_max,lat_max order correctly', () => {
    process.env.REACT_APP_DEFAULT_BBOX = '-110.0,53.0,-100.0,60.0';
    expect(parseBboxFromEnv()).toEqual({
      latMin: '53.0', latMax: '60.0', lonMin: '-110.0', lonMax: '-100.0',
    });
  });
  test('trims whitespace from values', () => {
    process.env.REACT_APP_DEFAULT_BBOX = ' -110.0 , 53.0 , -100.0 , 60.0 ';
    const result = parseBboxFromEnv();
    expect(result.lonMin).toBe('-110.0');
    expect(result.latMin).toBe('53.0');
  });
});
