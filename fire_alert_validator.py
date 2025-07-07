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
    if table.startswith('viirs'):   fam = 'viirs'
    elif table.startswith('modis'): fam = 'modis'
    elif table.startswith('landsat'): fam = 'landsat'
    elif table.startswith('goes'):  fam = 'goes'
    else: fam = 'viirs'
    t = THRESHOLDS[fam]
    return t['time'], t['dist']

# Find a matching record and return it
def find_match(fire, other_df, time_window, dist_thresh):
    for _, row in other_df.iterrows():
        if abs((fire['datetime'] - row['datetime']).total_seconds()) / 60 <= time_window:
            if geodesic((fire['latitude'], fire['longitude']),
                        (row['latitude'], row['longitude'])).km <= dist_thresh:
                return row
    return None

# Validate detections and save comparison columns
def validate_fires(primary_db, primary_table, secondary_sources):
    primary_df = load_detections(primary_db, primary_table)
    out_rows = []

    secondary_dfs = [((db, tbl), load_detections(db, tbl)) for db, tbl in secondary_sources]

    for _, fire in primary_df.iterrows():
        for (db, tbl), df in secondary_dfs:
            tw, dt = get_thresholds(tbl)
            match = find_match(fire, df, tw, dt)
            if match is not None:
                merged = fire.to_dict()
                merged['matched_sensor'] = tbl
                for col in match.index:
                    merged[f"{col}_match"] = match[col]
                out_rows.append(merged)
                break

    pd.DataFrame(out_rows).to_csv("validated_fires.csv", index=False)
    print(f"Validated {len(out_rows)} of {len(primary_df)} detections.")

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
