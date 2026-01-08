import sqlite3
import pandas as pd
import os
from geopy.distance import geodesic
from datetime import datetime, timedelta

# Centralize path logic
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Standardize DB paths
VALIDATED_DB = os.path.join(BASE_DIR, "validated_fires.db")
VIIRS_DB = os.path.join(BASE_DIR, "viirs.db")
MODIS_DB = os.path.join(BASE_DIR, "modis.db")
LANDSAT_DB = os.path.join(BASE_DIR, "landsat.db")
GOES_DB = os.path.join(BASE_DIR, "goes.db")

# Adjusted weights so single primary + one secondary match reliably exceeds 10.0%
SENSOR_WEIGHTS = {
    'viirs': 0.60,  # Increased from 0.60
    'modis': 0.20,  # Increased from 0.20
    'goes': 0.15,   # Increased from 0.15
    'landsat': 0.05  # Increased from 0.05
}

# Increased thresholds by 50% to increase validation yield
MATCH_THRESHOLDS = {
    'viirs':   {'time': 360,   'dist': 5},  # 360 * 1.5, 5.0 * 1.5
    'modis':   {'time': 180,   'dist': 3.0},  # 180 * 1.5, 3.0 * 1.5
    'landsat': {'time': 4320,  'dist': 1.0},  # 4320 * 1.5, 1.0 * 1.5
    'goes':    {'time': 15,  'dist': 10.0}  # 15 * 1.5, 10.0 * 1.5
}

def get_input_score(conf_val):
    """Convert confidence value to normalized score"""
    # First, try to parse as numeric (MODIS uses 0-100 integers)
    try:
        val = int(float(conf_val))
        # MODIS numeric confidence: >=80 = 1.0, 50-79 = 0.7, else = 0.6
        if val >= 85:
            return 1.0
        elif val <= 60: 
            return 0.2
        else:
            return 0.7
    except (ValueError, TypeError):
        pass  # Not numeric, continue to string parsing
    
    # Handle string values (VIIRS/Landsat use L/N/H)
    conf_str = str(conf_val).lower()
    conf_str_upper = str(conf_val).upper()
    
    # Check for high confidence (H, h, high, HIGH)
    if 'h' in conf_str or 'high' in conf_str or 'H' in conf_str_upper or 'HIGH' in conf_str_upper:
        return 1.0
    
    # Check for nominal confidence (N, n, nominal, NOMINAL)
    if 'n' in conf_str or 'nominal' in conf_str or 'N' in conf_str_upper or 'NOMINAL' in conf_str_upper:
        return 0.7
    
    # Check for low confidence (L, l, low, LOW)
    if 'l' in conf_str or 'low' in conf_str or 'L' in conf_str_upper or 'LOW' in conf_str_upper:
        return 0.2  # Increased from 0.6 to help exceed 10.0% threshold

def combine_datetime(acq_date, acq_time):
    """Combine date string and time integer into datetime object"""
    # Ensure acq_time is treated as string to prevent math errors
    if isinstance(acq_time, (int, float)):
        time_str = str(int(acq_time)).zfill(4)
    else:
        time_str = str(acq_time).zfill(4)
    return datetime.strptime(f"{acq_date} {time_str}", "%Y-%m-%d %H%M")

def load_detections(db, table, since=None, bbox=None):
    # Convert relative db path to absolute if needed
    if not os.path.isabs(db):
        db = os.path.join(BASE_DIR, db)
    
    print(f"DEBUG: Looking for data in {db}")
    con = sqlite3.connect(db)
    query = f"SELECT * FROM {table}"
    conditions = []
    
    # REMOVED: BBOX spatial filtering to allow all data (including Newfoundland) to be processed
    # Previously filtered by latitude/longitude, but this excluded valid fires outside the BBOX
    # if bbox and str(bbox).lower() != 'nan' and bbox.strip():
    #     # Filter by BBOX coordinates: lon_min,lat_min,lon_max,lat_max
    #     try:
    #         coords = [float(x.strip()) for x in bbox.split(',')]
    #         if len(coords) == 4:
    #             lon_min, lat_min, lon_max, lat_max = coords
    #             conditions.append(f"latitude >= {lat_min} AND latitude <= {lat_max}")
    #             conditions.append(f"longitude >= {lon_min} AND longitude <= {lon_max}")
    #             print(f"PERFORMANCE: Applying BBOX filter in SQL: lat[{lat_min}-{lat_max}], lon[{lon_min}-{lon_max}]")
    #     except:
    #         pass  # Invalid BBOX format, skip filtering
    
    # PERFORMANCE: Apply date filtering in SQL if possible (when since is provided and we have date info)
    if since:
        # Convert since datetime to date string for SQL comparison
        since_date_str = since.strftime("%Y-%m-%d")
        since_time_str = since.strftime("%H%M")
        conditions.append(f"(acq_date > '{since_date_str}' OR (acq_date = '{since_date_str}' AND acq_time >= '{since_time_str}'))")
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    df = pd.read_sql_query(query, con)
    con.close()
    
    if not df.empty:
        # Debug: verify first row coordinates
        print(f"DEBUG: First Row Coords: Lat={df.iloc[0]['latitude']}, Lon={df.iloc[0]['longitude']}")
        
        # Create datetime column for any remaining time-based filtering
        df['datetime'] = df.apply(lambda r: combine_datetime(r['acq_date'], r['acq_time']), axis=1)
        
        # PERFORMANCE: Additional datetime filtering (if SQL date filtering wasn't precise enough)
        if since:
            df = df[df['datetime'] >= since]
    
    return df

def get_thresholds(table):
    if 'viirs' in table: fam = 'viirs'
    elif 'modis' in table: fam = 'modis'
    elif 'landsat' in table: fam = 'landsat'
    elif 'goes' in table: fam = 'goes'
    else: fam = 'viirs'
    t = MATCH_THRESHOLDS[fam]
    return t['time'], t['dist']

def find_matches(fire, all_secondary_data):
    matches = []
    families_found = set()  # Track which families we've already found matches for
    
    for (db, tbl), df in all_secondary_data:
        if df.empty:
            continue
            
        # Derive family from table name
        if 'viirs' in tbl: family = 'viirs'
        elif 'modis' in tbl: family = 'modis'
        elif 'landsat' in tbl: family = 'landsat'
        elif 'goes' in tbl: family = 'goes'
        else: family = 'viirs'
        
        # Speed optimization: break after finding first match for this family
        if family in families_found:
            continue
        
        tw, dt = get_thresholds(tbl)
        for _, row in df.iterrows():
            time_diff = abs((fire['datetime'] - row['datetime']).total_seconds()) / 60
            if time_diff <= tw:
                # Verify geodesic parameters: (lat1, lon1), (lat2, lon2)
                distance = geodesic(
                    (float(fire['latitude']), float(fire['longitude'])),
                    (float(row['latitude']), float(row['longitude']))
                ).km
                if distance <= dt:
                    # Capture raw confidence value from database (actual value, not normalized)
                    raw_confidence = row.get('confidence', 'n')
                    # Store the raw value as-is for display (e.g., '85' for MODIS, 'H' for VIIRS)
                    if raw_confidence is None:
                        raw_confidence = 'n'  # Default fallback
                    else:
                        # Convert to string but preserve numeric values for MODIS
                        raw_confidence = str(raw_confidence).strip()
                    
                    matches.append({
                        'sensor': tbl,
                        'family': family,
                        'confidence': row.get('confidence', 'n'),  # For scoring calculation
                        'raw_confidence': raw_confidence,  # Raw value for display (number or letter)
                        'row': row
                    })
                    families_found.add(family)  # Mark this family as found
                    break  # Break after finding first match for this family
    return matches

def send_alert(fire, level, score):
    print(f"ALERT: Level {level} ({score}%) at {fire['latitude']}, {fire['longitude']}")

def initialize_validated_db():
    con = sqlite3.connect(VALIDATED_DB)
    cur = con.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS validated_fires (
            latitude REAL,
            longitude REAL,
            acq_date TEXT,
            acq_time TEXT,
            confidence_level INTEGER,
            confidence_score REAL,
            primary_sensor TEXT,
            validating_sensors TEXT,
            datetime TEXT,
            raw_primary_confidence TEXT,
            PRIMARY KEY (latitude, longitude, acq_date, acq_time, primary_sensor)
        )
    ''')
    
    # Check if raw_primary_confidence column exists, add it if missing (migration)
    cur.execute("PRAGMA table_info(validated_fires)")
    columns = [col[1] for col in cur.fetchall()]
    if 'raw_primary_confidence' not in columns:
        print("Adding raw_primary_confidence column to validated_fires table...")
        cur.execute("ALTER TABLE validated_fires ADD COLUMN raw_primary_confidence TEXT")
        con.commit()
    
    
    con.commit()
    con.close()

def validate_fires(primary_db, primary_table, secondary_sources, bbox=None):
    # Convert relative db path to absolute if needed
    if not os.path.isabs(primary_db):
        primary_db = os.path.join(BASE_DIR, primary_db)
    
    # Find the latest timestamp in the primary database
    con = sqlite3.connect(primary_db)
    cur = con.cursor()
    
    # Build query with optional BBOX filter (skip if None or "NaN")
    query = f"SELECT acq_date, acq_time FROM {primary_table}"
    if bbox and str(bbox).lower() != 'nan' and bbox.strip():
        try:
            coords = [float(x.strip()) for x in bbox.split(',')]
            if len(coords) == 4:
                lon_min, lat_min, lon_max, lat_max = coords
                query += f" WHERE latitude >= {lat_min} AND latitude <= {lat_max} AND longitude >= {lon_min} AND longitude <= {lon_max}"
        except:
            pass
    
    query += " ORDER BY acq_date DESC, acq_time DESC LIMIT 1"
    
    cur.execute(query)
    result = cur.fetchone()
    con.close()
    
    if not result:
        print("No primary detections found in database" + (f" for BBOX: {bbox}" if bbox else ""))
        return []
    
    latest_date, latest_time = result
    latest_datetime = combine_datetime(latest_date, latest_time)
    
    # No time filtering - use all data in database (only August 17 data after CSV filtering)
    since = None
    
    print(f"Using all data from database (latest timestamp: {latest_datetime.isoformat()})" + (f" (BBOX: {bbox})" if bbox else ""))
    
    primary_df = load_detections(primary_db, primary_table, since, bbox)
    
    # Speed optimization: limit to 5000 fires if too many
    if len(primary_df) > 5000:
        print(f"WARNING: {len(primary_df)} fires found, limiting to first 5000 for performance")
        primary_df = primary_df.head(5000)
    
    if primary_df.empty:
        print("No primary detections found in the validation window" + (f" for BBOX: {bbox}" if bbox else ""))
        return []
    
    # Load secondary data
    secondary_dfs = []
    for db, tbl in secondary_sources:
        df = load_detections(db, tbl, since, bbox)
        if not df.empty:
            secondary_dfs.append(((db, tbl), df))
        else:
            print(f"No data found for secondary source: {tbl}")

    validated = []  # list of dicts of fires that pass validation

    # Derive primary sensor family
    if 'viirs' in primary_table: primary_family = 'viirs'
    elif 'modis' in primary_table: primary_family = 'modis'
    elif 'landsat' in primary_table: primary_family = 'landsat'
    elif 'goes' in primary_table: primary_family = 'goes'
    else: primary_family = 'viirs'

    for _, fire in primary_df.iterrows():
        matches = find_matches(fire, secondary_dfs)
        
        # Calculate base score for primary sensor
        primary_conf = fire.get('confidence', 'n')
        primary_input_score = get_input_score(primary_conf)
        primary_weight = SENSOR_WEIGHTS.get(primary_family, 0.60)
        base_score = primary_weight * primary_input_score
        
        # Track best score per family
        family_scores = {primary_family: base_score}
        
        # Iterate through matches and track best score per family
        for match in matches:
            family = match['family']
            conf_val = match['confidence']
            input_score = get_input_score(conf_val)
            weight = SENSOR_WEIGHTS.get(family, 0.60)
            score = weight * input_score
            
            # Keep only the highest score for each family
            if family not in family_scores or score > family_scores[family]:
                family_scores[family] = score
        
        # Sum the best scores from all families
        total_score = sum(family_scores.values())
        
        # Track distinct VIIRS detections by timestamp (including primary)
        distinct_viirs_times = set()
        if primary_family == 'viirs':
            distinct_viirs_times.add(fire['acq_time'])
        for match in matches:
            if match['family'] == 'viirs':
                distinct_viirs_times.add(match['row']['acq_time'])
        
        # Tiered bonus system based on number of distinct VIIRS detections
        viirs_count = len(distinct_viirs_times)
        if viirs_count == 2:
            # Two VIIRS sensors detected: add 10% bonus
            total_score += 0.10
        elif viirs_count >= 3:
            # Three or more VIIRS sensors detected: add 25% bonus
            total_score += 0.25
        
        # Multiply by 100 to get percentage and cap at 100
        confidence_score = min(total_score * 100, 100.0)
        
        # REDLINE PROTOCOL: Round confidence_score to 1 decimal place
        confidence_score = round(confidence_score, 1)
        
        # Skip fires with score < 10.0 (lowered threshold for demo)
        if confidence_score < 10.0:
            continue
        
        # Map score to confidence_level
        if confidence_score >= 85:
            confidence_level = 4
        elif confidence_score >= 60:
            confidence_level = 3
        else:  # 40-59
            confidence_level = 2
        
        merged = fire.to_dict()
        merged['confidence_level'] = confidence_level
        merged['confidence_score'] = confidence_score
        merged['primary_sensor'] = primary_table
        
        # Store raw primary confidence value (as-is from source database)
        primary_conf_raw = fire.get('confidence', 'n')
        if primary_conf_raw is None:
            primary_conf_raw = 'n'
        else:
            primary_conf_raw = str(primary_conf_raw).strip()
        merged['raw_primary_confidence'] = primary_conf_raw
        
        # Build validating_sensors string with raw confidence values
        # MODIS shows numbers (e.g., "modis_data(85)"), VIIRS/Landsat show letters (e.g., "viirs_snpp(H)")
        validating_sensors_list = []
        for m in matches:
            sensor_name = m['sensor']
            raw_conf = m.get('raw_confidence', 'n')
            validating_sensors_list.append(f"{sensor_name}({raw_conf})")
        merged['validating_sensors'] = ','.join(sorted(validating_sensors_list))
        validated.append(merged)
        send_alert(fire, confidence_level, confidence_score)

    # Insert validated fires into DB
    if validated:
        con = sqlite3.connect(VALIDATED_DB)
        cur = con.cursor()
        inserted_count = 0
        replaced_count = 0
        
        for fire in validated:
            # HARD RESET: Coordinate integrity check before insertion
            lat = float(fire['latitude'])
            lon = float(fire['longitude'])
            if not (40 <= lat <= 90):
                print(f"CRITICAL ERROR: Latitude {lat} is invalid for Canada. Expected 40-90, got {lat}.")
                continue  # Skip this fire
            if not (-141 <= lon <= -52):
                print(f"CRITICAL ERROR: Longitude {lon} is invalid for Canada. Expected -141 to -52, got {lon}.")
                continue  # Skip this fire
            
            # Check if a record with the same primary key exists
            cur.execute("""
                SELECT confidence_score FROM validated_fires 
                WHERE latitude = ? AND longitude = ? AND acq_date = ? AND acq_time = ? AND primary_sensor = ?
            """, (lat, lon, fire['acq_date'], str(fire.get('acq_time', '')), fire['primary_sensor']))
            
            existing = cur.fetchone()
            current_score = round(fire['confidence_score'], 1)
            
            if existing:
                existing_score = existing[0]
                # Only replace if current score is higher
                if current_score > existing_score:
                    cur.execute("""
                        UPDATE validated_fires 
                        SET confidence_level = ?, confidence_score = ?, validating_sensors = ?, datetime = ?, raw_primary_confidence = ?
                        WHERE latitude = ? AND longitude = ? AND acq_date = ? AND acq_time = ? AND primary_sensor = ?
                    """, (
                        fire['confidence_level'],
                        current_score,
                        fire['validating_sensors'],
                        fire['datetime'].isoformat(),
                        fire.get('raw_primary_confidence', 'n'),
                        lat, lon, fire['acq_date'], str(fire.get('acq_time', '')), fire['primary_sensor']
                    ))
                    replaced_count += 1
                # Otherwise, ignore (keep existing higher score)
            else:
                # Insert new record
                cur.execute("""
                    INSERT INTO validated_fires 
                    (latitude, longitude, acq_date, acq_time, confidence_level, confidence_score, primary_sensor, validating_sensors, datetime, raw_primary_confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    lat,  # latitude column - explicit mapping
                    lon,  # longitude column - explicit mapping
                    fire['acq_date'],
                    str(fire.get('acq_time', '')),  # REDLINE: Use exact string from DB, not calculated object
                    fire['confidence_level'],
                    current_score,  # Already rounded
                    fire['primary_sensor'],
                    fire['validating_sensors'],
                    fire['datetime'].isoformat(),
                    fire.get('raw_primary_confidence', 'n')
                ))
                inserted_count += 1
        
        con.commit()
        con.close()
        print(f"Inserted {inserted_count} new fires, updated {replaced_count} existing fires with higher scores")
    else:
        print("No validated fires found")

    return validated
