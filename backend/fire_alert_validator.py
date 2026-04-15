import sqlite3
import pandas as pd
from geopy.distance import geodesic
from datetime import datetime, timedelta

# Empirically optimized against NFDB ground truth (2015-2023, AB/SK)
# Previous: viirs=0.60, modis=0.20, landsat=0.05
# Optimization improved Alert tier recall from 55% → 88% at P≥95%
SENSOR_WEIGHTS = {
    'viirs': 0.90,
    'modis': 0.10,
    'goes': 0.15,
    'landsat': 0.10
}

MATCH_THRESHOLDS = {
    'viirs':   {'time': 360,   'dist': 5.0},
    'modis':   {'time': 180,   'dist': 3.0},
    'landsat': {'time': 4320,  'dist': 1.0},
    'goes':    {'time': 15,    'dist': 10.0}
}

def get_input_score(conf_val):
    """Convert confidence value to normalized score"""
    conf_str = str(conf_val).lower()
    
    # Check for high confidence
    if 'h' in conf_str or 'high' in conf_str:
        return 1.0
    try:
        val = int(conf_val)
        if val >= 85:
            return 1.0
    except (ValueError, TypeError):
        pass
    
    # Check for nominal confidence
    if 'n' in conf_str or 'nominal' in conf_str:
        return 0.7
    try:
        val = int(conf_val)
        if 60 <= val <= 84:
            return 0.7
    except (ValueError, TypeError):
        pass
    
    # Check for low confidence
    if 'l' in conf_str or 'low' in conf_str:
        return 0.2
    try:
        val = int(conf_val)
        if val < 60:
            return 0.2
    except (ValueError, TypeError):
        pass
    
    # Default to low if no match
    return 0.2

def combine_datetime(acq_date, acq_time):
    """Combine date string and time integer into datetime object"""
    try:
        # Convert time integer to zero-padded string (e.g., 130 -> '0130')
        time_str = str(int(acq_time)).zfill(4)
        return datetime.strptime(f"{acq_date} {time_str}", "%Y-%m-%d %H%M")
    except ValueError:
        # Handle edge cases where time might be malformed
        return None

def load_detections(db, table, since=None):
    """Loads detection data, optionally filtering by date."""
    con = sqlite3.connect(db)
    query = f"SELECT * FROM {table}"
    
    # Optional: SQL level filtering
    if since:
        since_date = since.strftime('%Y-%m-%d')
        query += f" WHERE acq_date >= '{since_date}'"
    
    try:
        df = pd.read_sql_query(query, con)
    except pd.errors.DatabaseError:
        print(f"Warning: Could not read table {table} from {db}")
        con.close()
        return pd.DataFrame() # Return empty if table doesn't exist
        
    con.close()
    
    if not df.empty:
        # Create datetime column
        df['datetime'] = df.apply(lambda r: combine_datetime(r['acq_date'], r['acq_time']), axis=1)
        
        # Drop rows where datetime failed
        df = df.dropna(subset=['datetime'])

        # Additional filtering by precise datetime object
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
    for (db, tbl), df in all_secondary_data:
        if df.empty:
            continue
            
        # Derive family from table name
        if 'viirs' in tbl: family = 'viirs'
        elif 'modis' in tbl: family = 'modis'
        elif 'landsat' in tbl: family = 'landsat'
        elif 'goes' in tbl: family = 'goes'
        else: family = 'viirs'
        
        tw, dt = get_thresholds(tbl)
        for _, row in df.iterrows():
            # Calculate time difference in minutes
            time_diff = abs((fire['datetime'] - row['datetime']).total_seconds()) / 60
            
            if time_diff <= tw:
                # Calculate physical distance in KM
                distance = geodesic((fire['latitude'], fire['longitude']),
                                  (row['latitude'], row['longitude'])).km
                if distance <= dt:
                    matches.append({
                        'sensor': tbl,
                        'family': family,
                        'confidence': row.get('confidence', 'n'),
                        'row': row
                    })
    return matches

def send_alert(fire, level):
    print(f"[{fire['datetime']}] CONFIDENCE {level}: Fire at {fire['latitude']}, {fire['longitude']}")

def initialize_validated_db():
    con = sqlite3.connect("validated_fires.db")
    cur = con.cursor()
    # Added 'IF NOT EXISTS' to prevent errors
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
            PRIMARY KEY (latitude, longitude, acq_date, acq_time, primary_sensor)
        )
    ''')
    con.commit()
    con.close()

def validate_fires(primary_db, primary_table, secondary_sources):
    # Get data from last 24 hours
    since = datetime.now() - timedelta(days=7)
    
    print(f"Loading primary data from {primary_table}...")
    primary_df = load_detections(primary_db, primary_table, since)
    
    if primary_df.empty:
        print("No primary detections found in database.")
        return []
    
    print(f"Found {len(primary_df)} primary fires. Checking secondary sources...")

    # Load secondary data
    secondary_dfs = []
    for db, tbl in secondary_sources:
        df = load_detections(db, tbl, since)
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
        
        # Add bonus for 3+ distinct VIIRS detections
        if len(distinct_viirs_times) >= 3:
            total_score += 0.25
        
        # Multiply by 100 to get percentage and cap at 100
        confidence_score = min(total_score * 100, 100.0)
        
        # Skip fires with score < 40.0
        if confidence_score < 40.0:
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
        merged['validating_sensors'] = ','.join(sorted(list(set([m['sensor'] for m in matches]))))
        validated.append(merged)
        send_alert(fire, confidence_level)

    # Insert validated fires into DB
    if validated:
        initialize_validated_db() # Ensure DB exists
        con = sqlite3.connect("validated_fires.db")
        cur = con.cursor()
        
        count = 0
        for fire in validated:
            cur.execute("""
                INSERT OR IGNORE INTO validated_fires 
                (latitude, longitude, acq_date, acq_time, confidence_level, confidence_score, primary_sensor, validating_sensors, datetime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fire['latitude'],
                fire['longitude'],
                fire['acq_date'],
                str(fire['acq_time']),  # Ensure acq_time is string
                fire['confidence_level'],
                fire['confidence_score'],
                fire['primary_sensor'],
                fire['validating_sensors'],
                fire['datetime'].isoformat()
            ))
        con.commit()
        con.close()
        print(f"Validation Complete: Inserted {count} new fires. (Total validated: {len(validated)})")
    else:
        print("No validated fires found to insert.")

    return validated