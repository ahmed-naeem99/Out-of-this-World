import sqlite3
import pandas as pd
from geopy.distance import geodesic
from datetime import datetime, timedelta

# Define time and distance thresholds for validation
TIME_WINDOW_MINUTES = 60
DISTANCE_THRESHOLD_KM = 1.0

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

# Check if any matching detection exists in another dataset
def validate_detection(fire, other_df):
    for _, row in other_df.iterrows():
        time_diff = abs((fire['datetime'] - row['datetime']).total_seconds()) / 60
        if time_diff <= TIME_WINDOW_MINUTES:
            dist = geodesic((fire['latitude'], fire['longitude']), (row['latitude'], row['longitude'])).km
            if dist <= DISTANCE_THRESHOLD_KM:
                return True
    return False


# Run validation for all detections from the primary sensor
def validate_fires(primary_db, primary_table, secondary_sources):
    primary_df = load_detections(primary_db, primary_table)
    validated_alerts = []

    # Load secondary detections
    secondary_dfs = [(src, load_detections(*src)) for src in secondary_sources]

    for _, fire in primary_df.iterrows():
        for source, df in secondary_dfs:
            if validate_detection(fire, df):
                validated_alerts.append(fire)
                break  # Only need one match to confirm

    validated_df = pd.DataFrame(validated_alerts)
    print(f"Validated {len(validated_df)} out of {len(primary_df)} detections.")
    validated_df.to_csv("validated_fires.csv", index=False)


    # Usage
if __name__ == "__main__":
    primary = ("viirs.db", "viirs_noaa20")
    secondary = [
        ("modis.db", "modis_data"),
        ("viirs.db", "viirs_snpp"),
        ("viirs.db", "viirs_noaa21")
    ]

    validate_fires(primary[0], primary[1], secondary)
