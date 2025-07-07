from datetime import datetime
import sqlite3
import pandas as pd
from geopy.distance import geodesic

def combine_datetime(acq_date, acq_time):
    return datetime.strptime(f"{acq_date} {acq_time.zfill(4)}", "%Y-%m-%d %H%M")

acq_date = "2025-06-13"
acq_time = "1744"

#print(combine_datetime(acq_date, acq_time))

def load_detections(db_path, table):
    con = sqlite3.connect(db_path)
    df = pd.read_sql_query(f"SELECT * FROM {table}", con)
    con.close()
    df['datetime'] = df.apply(lambda row: combine_datetime(row['acq_date'], row['acq_time']), axis=1)
    return df

db_path = "viirs.db"
table_name = "viirs_noaa20"

df = load_detections(db_path, table_name)
print(df.head())  

TIME_WINDOW_MINUTES = 60
DISTANCE_THRESHOLD_KM = 1.0

def validate_detection(fire, other_df):
    for _, row in other_df.iterrows():
        time_diff = abs((fire['datetime'] - row['datetime']).total_seconds()) / 60
        if time_diff <= TIME_WINDOW_MINUTES:
            dist = geodesic((fire['latitude'], fire['longitude']), (row['latitude'], row['longitude'])).km
            if dist <= DISTANCE_THRESHOLD_KM:
                print(f"Match found! Time diff: {time_diff:.2f} min, Distance: {dist:.2f} km")
                return True
            else:
                print(f"Close in time but too far. Distance: {dist:.2f} km")
        else:
            print(f"Too far in time. Time diff: {time_diff:.2f} min")
    return False

def validate_all(primary_db, primary_table, secondary_db, secondary_table):
    primary_df = load_detections(primary_db, primary_table)
    secondary_df = load_detections(secondary_db, secondary_table)

    validated_fires = []

    print(f"\nValidating {len(primary_df)} detections from {primary_table} against {secondary_table}...\n")

    for _, fire in primary_df.iterrows():
        print(f"\n🔍 Checking fire at ({fire['latitude']}, {fire['longitude']}) on {fire['datetime']}")
        if validate_detection(fire, secondary_df):
            validated_fires.append(fire)
            print("VALIDATED\n")
        else:
            print("NOT VALIDATED\n")

    validated_df = pd.DataFrame(validated_fires)
    print(f"\nResult: {len(validated_df)} out of {len(primary_df)} detections validated.")
    return validated_df

# Run the validation
if __name__ == "__main__":
    primary_db = "viirs.db"
    primary_table = "viirs_noaa20"

    secondary_db = "viirs.db"
    secondary_table = "viirs_noaa21"

    validated_df = validate_all(primary_db, primary_table, secondary_db, secondary_table)
    print("\nValidated Detections:")
    print(validated_df.head())