import sqlite3
import pandas as pd
from geopy.distance import geodesic
from datetime import datetime

THRESHOLDS = {
    'viirs':   {'time': 360,   'dist': 5.0},
    'modis':   {'time': 180,   'dist': 3.0},
    'landsat': {'time': 4320,  'dist': 1.0},
    'goes':    {'time': 15,    'dist': 10.0}
}

def combine_datetime(acq_date, acq_time):
    return datetime.strptime(f"{acq_date} {acq_time.zfill(4)}", "%Y-%m-%d %H%M")

def load_detections(db, table, since=None):
    con = sqlite3.connect(db)
    query = f"SELECT * FROM {table}"
    df = pd.read_sql_query(query, con)
    con.close()
    df['datetime'] = df.apply(lambda r: combine_datetime(r['acq_date'], r['acq_time']), axis=1)
    if since:
        df = df[df['datetime'] >= since]
    return df

def get_thresholds(table):
    if table.startswith('viirs'): fam = 'viirs'
    elif table.startswith('modis'): fam = 'modis'
    elif table.startswith('landsat'): fam = 'landsat'
    elif table.startswith('goes'): fam = 'goes'
    else: fam = 'viirs'
    t = THRESHOLDS[fam]
    return t['time'], t['dist']

def find_matches(fire, all_secondary_data):
    matches = []
    for (db, tbl), df in all_secondary_data:
        tw, dt = get_thresholds(tbl)
        for _, row in df.iterrows():
            if abs((fire['datetime'] - row['datetime']).total_seconds()) / 60 <= tw:
                if geodesic((fire['latitude'], fire['longitude']),
                            (row['latitude'], row['longitude'])).km <= dt:
                    matches.append((tbl, row))
                    break
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

def validate_fires(primary_db, primary_table, secondary_sources, since=None):
    primary_df = load_detections(primary_db, primary_table, since)
    secondary_dfs = [((db, tbl), load_detections(db, tbl, since)) for db, tbl in secondary_sources]

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
            fire['acq_time'],
            fire['confidence_level'],
            fire['primary_sensor'],
            fire['validating_sensors'],
            fire['datetime'].isoformat()
        ))
    con.commit()
    con.close()

    return validated
