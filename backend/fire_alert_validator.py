import sqlite3
import pandas as pd
from geopy.distance import geodesic
from datetime import datetime, timedelta

THRESHOLDS = {
    'viirs':   {'time': 360,   'dist': 5.0},
    'modis':   {'time': 180,   'dist': 3.0},
    'landsat': {'time': 4320,  'dist': 1.0},
    'goes':    {'time': 15,    'dist': 10.0}
}

def combine_datetime(acq_date, acq_time):
    """Combine date string and time integer into datetime object"""
    # Convert time integer to zero-padded string
    time_str = str(int(acq_time)).zfill(4)
    return datetime.strptime(f"{acq_date} {time_str}", "%Y-%m-%d %H%M")

def load_detections(db, table, since=None):
    con = sqlite3.connect(db)
    query = f"SELECT * FROM {table}"
    if since:
        # For SQL query filtering by date
        since_date = since.strftime('%Y-%m-%d')
        query += f" WHERE acq_date >= '{since_date}'"
    
    df = pd.read_sql_query(query, con)
    con.close()
    
    if not df.empty:
        # Create datetime column
        df['datetime'] = df.apply(lambda r: combine_datetime(r['acq_date'], r['acq_time']), axis=1)
        
        # Additional filtering by datetime if since parameter provided
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
            time_diff = abs((fire['datetime'] - row['datetime']).total_seconds()) / 60
            if time_diff <= tw:
                distance = geodesic((fire['latitude'], fire['longitude']),
                                  (row['latitude'], row['longitude'])).km
                if distance <= dt:
                    matches.append((tbl, row))
                    break  # Only need one match per sensor type
    return matches

def send_alert(fire, level):
    print(f"CONFIDENCE LEVEL {level}: Fire at ({fire['latitude']}, {fire['longitude']}) on {fire['acq_date']} at {fire['acq_time']}")

def initialize_validated_db():
    con = sqlite3.connect("validated_fires.db")
    cur = con.cursor()
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
    # Get data from last 24 hours
    since = datetime.now() - timedelta(days=7)
    
    primary_df = load_detections(primary_db, primary_table, since)
    
    if primary_df.empty:
        print("No primary detections found in the last 24 hours")
        return []
    
    # Load secondary data
    secondary_dfs = []
    for db, tbl in secondary_sources:
        df = load_detections(db, tbl, since)
        if not df.empty:
            secondary_dfs.append(((db, tbl), df))
        else:
            print(f"No data found for secondary source: {tbl}")

    validated = []  # list of dicts of fires that pass validation

    for _, fire in primary_df.iterrows():
        matches = find_matches(fire, secondary_dfs)
        confidence_level = len(matches)

        if confidence_level > 0:
            merged = fire.to_dict()
            merged['confidence_level'] = confidence_level
            merged['primary_sensor'] = primary_table
            merged['validating_sensors'] = ','.join([m[0] for m in matches])
            validated.append(merged)
            send_alert(fire, confidence_level)

    # Insert validated fires into DB
    if validated:
        con = sqlite3.connect("validated_fires.db")
        cur = con.cursor()
        for fire in validated:
            cur.execute("""
                INSERT OR IGNORE INTO validated_fires 
                (latitude, longitude, acq_date, acq_time, confidence_level, primary_sensor, validating_sensors, datetime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fire['latitude'],
                fire['longitude'],
                fire['acq_date'],
                str(fire['acq_time']),  # Ensure acq_time is string
                fire['confidence_level'],
                fire['primary_sensor'],
                fire['validating_sensors'],
                fire['datetime'].isoformat()
            ))
        con.commit()
        con.close()
        print(f"Inserted {len(validated)} validated fires into database")
    else:
        print("No validated fires found")

    return validated
