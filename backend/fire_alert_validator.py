import sqlite3
import pandas as pd
from geopy.distance import geodesic
from datetime import datetime, timedelta

# Thresholds for matching secondary sensors
THRESHOLDS = {
    'viirs':   {'time': 360,   'dist': 5.0},
    'modis':   {'time': 180,   'dist': 3.0},
    'landsat': {'time': 4320,  'dist': 1.0},
    'goes':    {'time': 15,    'dist': 10.0}
}

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
    t = THRESHOLDS[fam]
    return t['time'], t['dist']

def find_matches(fire, all_secondary_data):
    matches = []
    for (db, tbl), df in all_secondary_data:
        if df.empty:
            continue
            
        tw, dt = get_thresholds(tbl)
        for _, row in df.iterrows():
            # Calculate time difference in minutes
            time_diff = abs((fire['datetime'] - row['datetime']).total_seconds()) / 60
            
            if time_diff <= tw:
                # Calculate physical distance in KM
                distance = geodesic((fire['latitude'], fire['longitude']),
                                  (row['latitude'], row['longitude'])).km
                if distance <= dt:
                    matches.append((tbl, row))
                    break  # Only need one match per sensor type
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
            primary_sensor TEXT,
            validating_sensors TEXT,
            datetime TEXT,
            PRIMARY KEY (latitude, longitude, acq_date, acq_time, primary_sensor)
        )
    ''')
    con.commit()
    con.close()

def validate_fires(primary_db, primary_table, secondary_sources):
    # FIX 1: Set since to None. 
    # Since your fetch script handles the 7-day limit, let's validate everything we have.
    since = None 
    
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

    validated = [] 

    for _, fire in primary_df.iterrows():
        matches = find_matches(fire, secondary_dfs)
        confidence_level = len(matches)

        # FIX 2: Changed from (> 0) to (>= 0)
        # We want to save the fire even if only the primary sensor saw it.
        if confidence_level >= 0:
            merged = fire.to_dict()
            merged['confidence_level'] = confidence_level
            merged['primary_sensor'] = primary_table
            
            # Handle empty matches list gracefully
            if matches:
                merged['validating_sensors'] = ','.join([m[0] for m in matches])
            else:
                merged['validating_sensors'] = "None"
            
            # Convert datetime to string for storage
            merged['datetime'] = fire['datetime'].isoformat()
            
            validated.append(merged)
            
            # Optional: Only print alert if it has high confidence
            if confidence_level > 0:
                send_alert(merged, confidence_level)

    # Insert validated fires into DB
    if validated:
        initialize_validated_db() # Ensure DB exists
        con = sqlite3.connect("validated_fires.db")
        cur = con.cursor()
        
        count = 0
        for fire in validated:
            try:
                cur.execute("""
                    INSERT OR IGNORE INTO validated_fires 
                    (latitude, longitude, acq_date, acq_time, confidence_level, primary_sensor, validating_sensors, datetime)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fire['latitude'],
                    fire['longitude'],
                    fire['acq_date'],
                    str(fire['acq_time']),
                    fire['confidence_level'],
                    fire['primary_sensor'],
                    fire['validating_sensors'],
                    fire['datetime']
                ))
                if cur.rowcount > 0:
                    count += 1
            except Exception as e:
                print(f"Error inserting row: {e}")

        con.commit()
        con.close()
        print(f"Validation Complete: Inserted {count} new fires. (Total validated: {len(validated)})")
    else:
        print("No validated fires found to insert.")

    return validated