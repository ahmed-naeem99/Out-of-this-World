import sqlite3
import pandas as pd
from geopy.distance import geodesic
from datetime import datetime, timedelta

# Thresholds for each sensor family
THRESHOLDS = {
    'viirs':   {'time': 360,    'dist': 5.0},
    'modis':   {'time': 180,    'dist': 3.0},
    'landsat': {'time': 4320,  'dist': 1.0},
    'goes':    {'time': 15,    'dist': 10.0}
}

# Convert acquisition date and time to datetime object
def combine_datetime(acq_date, acq_time):
    return datetime.strptime(f"{acq_date} {acq_time.zfill(4)}", "%Y-%m-%d %H%M")

# Load fire detections from a table
def load_detections(db_path, table):
    con = sqlite3.connect(db_path)
    df = pd.read_sql_query(f"SELECT * FROM {table}", con)
    con.close()
    df['datetime'] = df.apply(lambda row: combine_datetime(row['acq_date'], row['acq_time']), axis=1)
    return df

# Pick thresholds by table name
def get_thresholds(table):
    if table.startswith('viirs'):
        fam = 'viirs'
    elif table.startswith('modis'):
        fam = 'modis'
    elif table.startswith('landsat'):
        fam = 'landsat'
    elif table.startswith('goes'):
        fam = 'goes'
    else:
        fam = 'viirs'
    t = THRESHOLDS[fam]
    return t['time'], t['dist']

# Check match in another dataset
def validate_detection(fire, other_df, time_window, dist_thresh):
    for _, row in other_df.iterrows():
        if abs((fire['datetime'] - row['datetime']).total_seconds()) / 60 <= time_window:
            if geodesic((fire['latitude'], fire['longitude']),
                        (row['latitude'], row['longitude'])).km <= dist_thresh:
                return True
    return False


# Validate detections from primary sensor
def validate_fires(primary_db, primary_table, secondary_sources):
    primary_df = load_detections(primary_db, primary_table)
    validated = []

    secondary_dfs = [((db, tbl), load_detections(db, tbl)) for db, tbl in secondary_sources]

    for _, fire in primary_df.iterrows():
        for (db, tbl), df in secondary_dfs:
            tw, dt = get_thresholds(tbl)
            if validate_detection(fire, df, tw, dt):
                validated.append(fire)
                break

    pd.DataFrame(validated).to_csv("validated_fires.csv", index=False)
    print(f"Validated {len(validated)} of {len(primary_df)} detections.")

# Usage
if __name__ == "__main__":
    primary = ("viirs.db", "viirs_noaa20")
    secondary = [
        ("modis.db",   "modis_data"),
        ("viirs.db",   "viirs_snpp"),
        ("viirs.db",   "viirs_noaa21"),
        #("landsat.db", "landsat_data"),   # added
        ("goes.db",    "goes_data")       # added
    ]

    validate_fires(primary[0], primary[1], secondary)