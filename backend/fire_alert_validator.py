import sqlite3
import pandas as pd
from geopy.distance import geodesic
from datetime import datetime

# Thresholds per sensor
THRESHOLDS = {
    'viirs':   {'time': 360,   'dist': 5.0},
    'modis':   {'time': 180,   'dist': 3.0},
    'landsat': {'time': 4320,  'dist': 1.0},
    'goes':    {'time': 15,    'dist': 10.0}
}

# Combine acq_date + acq_time
def combine_datetime(acq_date, acq_time):
    return datetime.strptime(f"{acq_date} {acq_time.zfill(4)}", "%Y-%m-%d %H%M")

# Load one table
def load_detections(db, table):
    con = sqlite3.connect(db)
    df = pd.read_sql_query(f"SELECT * FROM {table}", con)
    con.close()
    df['datetime'] = df.apply(lambda r: combine_datetime(r['acq_date'], r['acq_time']), axis=1)
    return df

# Map table to family
def get_thresholds(table):
    if table.startswith('viirs'): fam = 'viirs'
    elif table.startswith('modis'): fam = 'modis'
    elif table.startswith('landsat'): fam = 'landsat'
    elif table.startswith('goes'): fam = 'goes'
    else: fam = 'viirs'
    t = THRESHOLDS[fam]
    return t['time'], t['dist']

# Find a matching record and return it
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

# Send alert (for now, just print it)
def send_alert(fire_id, alert_level):
    print(f"ALERT: Fire ID {fire_id} is LEVEL {alert_level}")

# Validate detections and save comparison columns
def validate_fires(primary_db, primary_table, secondary_sources):
    primary_df = load_detections(primary_db, primary_table)
    out_rows = []

    secondary_dfs = [((db, tbl), load_detections(db, tbl)) for db, tbl in secondary_sources]

    for idx, fire in primary_df.iterrows():
        matches = find_matches(fire, secondary_dfs)
        alert_level = len(matches)

        if alert_level > 0:
            merged = fire.to_dict()
            merged['alert_level'] = alert_level
            for sensor_name, match_row in matches:
                merged[f"matched_sensor_{sensor_name}"] = sensor_name
                for col in match_row.index:
                    merged[f"{sensor_name}_{col}"] = match_row[col]
            out_rows.append(merged)
            send_alert(idx, alert_level)

    pd.DataFrame(out_rows).to_csv("validated_fires.csv", index=False)
    print(f"{len(out_rows)} fires validated out of {len(primary_df)} total.")

# Usage
if __name__ == "__main__":
    primary = ("viirs.db", "viirs_noaa20")
    secondary = [
        ("modis.db",   "modis_data"),
        ("viirs.db",   "viirs_snpp"),
        ("viirs.db",   "viirs_noaa21"),
        #("landsat.db", "landsat_data"),
        ("goes.db",    "goes_data")
    ]
    
    validate_fires(primary[0], primary[1], secondary)
