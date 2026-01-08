import sqlite3
import pandas as pd
import os
from pathlib import Path
from datetime import datetime, timezone
from firms_data_collector_v2 import (
    init_all_dbs,
    SENSORS
)

# Centralize path logic
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Standardize DB paths
VIIRS_DB = os.path.join(BASE_DIR, "viirs.db")
MODIS_DB = os.path.join(BASE_DIR, "modis.db")
LANDSAT_DB = os.path.join(BASE_DIR, "landsat.db")
GOES_DB = os.path.join(BASE_DIR, "goes.db")

# Mapping CSV files to their intended DB tables
# Make sure the file names match your local files exactly
CSV_MAPPING = [
    ("demo_data/viirs_snpp.csv", VIIRS_DB, "viirs_snpp", "VIIRS_SNPP_NRT"),
    ("demo_data/viirs_noaa20.csv", VIIRS_DB, "viirs_noaa20", "VIIRS_NOAA20_NRT"),
    ("demo_data/viirs_noaa21.csv", VIIRS_DB, "viirs_noaa21", "VIIRS_NOAA21_NRT"),
    ("demo_data/modis_data.csv", MODIS_DB, "modis_data", "MODIS_NRT"),
    ("demo_data/landsat_data.csv", LANDSAT_DB, "landsat_data", "LANDSAT_NRT"),
]

def get_table_columns(db_path, table_name):
    """Retrieve the list of column names from the SQLite table."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = [info[1] for info in cur.fetchall()]
    con.close()
    return columns

def load_csv_to_table(csv_path, db_name, table_name, sensor_label):
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"WARNING: CSV file not found: {csv_path}")
        return

    print(f"Processing {csv_path}...")
    
    try:
        # 1. Read CSV (NASA acq_time is often an int, force to string)
        df = pd.read_csv(csv_path, dtype={'acq_time': str})
        
        # 2. Filter to ONLY August 17, 2025 data (discard Aug 10-16)
        if 'acq_date' in df.columns:
            before_count = len(df)
            df = df[df['acq_date'] == '2025-08-17']
            after_count = len(df)
            print(f"  Filtered to August 17 only: {before_count} -> {after_count} rows")
        
        # 3. Add Required Metadata Columns that aren't in NASA's raw CSV
        df['sensor'] = sensor_label
        df['acquired_at'] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # 4. Clean up acq_time (ensure 4 digits like '0945')
        if 'acq_time' in df.columns:
            df['acq_time'] = df['acq_time'].str.zfill(4)

        # 5. Filter to match DB schema
        # This prevents the "no column named X" error
        db_columns = get_table_columns(db_name, table_name)
        
        # Keep only columns that exist in BOTH the CSV and the Database
        valid_columns = [col for col in df.columns if col in db_columns]
        df_final = df[valid_columns].copy()

        # CRITICAL FIX: Remove duplicates based on Primary Key before SQL insertion
        # Landsat uses 6-column primary key (includes scan and track)
        # Other tables use 4-column primary key
        if table_name == 'landsat_data':
            pk_cols = ['latitude', 'longitude', 'acq_date', 'acq_time', 'scan', 'track']
        else:
            pk_cols = ['latitude', 'longitude', 'acq_date', 'acq_time']
        
        if all(col in df_final.columns for col in pk_cols):
            before_count = len(df_final)
            df_final = df_final.drop_duplicates(subset=pk_cols, keep='first')
            after_count = len(df_final)
            if before_count != after_count:
                print(f"  Removed {before_count - after_count} primary key duplicates from CSV")

        # 6. Connect and Reset Table
        con = sqlite3.connect(db_name)
        cur = con.cursor()
        
        # For Landsat, drop and recreate table to ensure schema matches (6-column primary key)
        # For other tables, just clear data
        if table_name == 'landsat_data':
            cur.execute(f"DROP TABLE IF EXISTS {table_name}")
            # Recreate with correct schema (6-column primary key)
            cur.execute('''
                CREATE TABLE landsat_data (
                    latitude REAL,
                    longitude REAL,
                    path TEXT,
                    row TEXT,
                    scan REAL,
                    track REAL,
                    acq_date TEXT,
                    acq_time TEXT,
                    satellite TEXT,
                    confidence TEXT,
                    daynight TEXT,
                    sensor TEXT,
                    acquired_at TEXT,
                    PRIMARY KEY (latitude, longitude, acq_date, acq_time, scan, track)
                )
            ''')
            print(f"  Recreated {table_name} with 6-column primary key")
        else:
            cur.execute(f"DELETE FROM {table_name}") # Clear existing data
        
        con.commit()

        # 7. Load Data
        df_final.to_sql(table_name, con, if_exists='append', index=False, chunksize=500)
        con.commit()
        
        final_count = pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table_name}", con)['count'][0]
        print(f"  SUCCESS: Loaded {final_count} rows into {table_name}")
        con.close()

    except Exception as e:
        print(f"  ERROR processing {csv_path}: {e}")

def seed_demo():
    print("=== STARTING STATIC DEMO SEEDING ===")
    
    # Step 1: Initialize the DBs to create the tables
    init_all_dbs()
    print("Databases initialized.")

    # Step 2: Load each CSV
    for csv_path, db_name, table_name, sensor_label in CSV_MAPPING:
        load_csv_to_table(csv_path, db_name, table_name, sensor_label)

    print("=== SEEDING COMPLETE ===")

if __name__ == "__main__":
    seed_demo()