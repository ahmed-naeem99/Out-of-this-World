import sqlite3
import pandas as pd
import os
from pathlib import Path
from datetime import datetime, timezone
from firms_data_collector_v2 import init_all_dbs, SENSORS

# Centralize path logic
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Standardize DB paths
VIIRS_DB = os.path.join(BASE_DIR, "viirs.db")
MODIS_DB = os.path.join(BASE_DIR, "modis.db")
LANDSAT_DB = os.path.join(BASE_DIR, "landsat.db")
GOES_DB = os.path.join(BASE_DIR, "goes.db")

# Mapping CSV files
CSV_MAPPING = [
    ("demo_data/viirs_snpp.csv", VIIRS_DB, "viirs_snpp", "VIIRS_SNPP_NRT"),
    ("demo_data/viirs_noaa20.csv", VIIRS_DB, "viirs_noaa20", "VIIRS_NOAA20_NRT"),
    ("demo_data/viirs_noaa21.csv", VIIRS_DB, "viirs_noaa21", "VIIRS_NOAA21_NRT"),
    ("demo_data/modis_data.csv", MODIS_DB, "modis_data", "MODIS_NRT"),
    ("demo_data/landsat_data.csv", LANDSAT_DB, "landsat_data", "LANDSAT_NRT"),
]

# --- SYNTHETIC DEMO DATA (Guarantees the Demo Logic Works) ---
# We inject these specifically to test the Scoring Logic (Veto, Bonus, etc.)
SYNTHETIC_DATA = {
    "viirs_noaa20": [
        # Cluster A: Confirmed Fire (High Confidence + 3 Pass Bonus)
        {"lat": 59.123, "lon": -111.456, "conf": "h", "date": "2025-08-17", "time": "1430"},
        # Cluster B: Static Veto Test (Near Oil Sands - Should be filtered/gray)
        {"lat": 57.001, "lon": -111.401, "conf": "h", "date": "2025-08-17", "time": "1435"},
        # Cluster C: Noise (Low Confidence - Should be filtered/gray)
        {"lat": 61.500, "lon": -120.000, "conf": "l", "date": "2025-08-17", "time": "1440"},
    ],
    "viirs_snpp": [
        # Cluster A: Cross-check (Nominal)
        {"lat": 59.124, "lon": -111.457, "conf": "n", "date": "2025-08-17", "time": "1432"},
    ],
    "viirs_noaa21": [
        # Cluster A: Third pass (Nominal) - TRIGGERS 25% BONUS
        {"lat": 59.122, "lon": -111.455, "conf": "n", "date": "2025-08-17", "time": "1438"},
    ],
    "modis_data": [
        # Cluster A: Cross-check (High Numeric)
        {"lat": 59.120, "lon": -111.460, "conf": "85", "date": "2025-08-17", "time": "1430"},
    ]
}

def get_table_columns(db_path, table_name):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = [info[1] for info in cur.fetchall()]
    con.close()
    return columns

def load_csv_to_table(csv_path, db_name, table_name, sensor_label):
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"WARNING: CSV file not found: {csv_path} (Skipping)")
        return

    print(f"Processing {csv_path}...")
    try:
        df = pd.read_csv(csv_path, dtype={'acq_time': str})
        
        # --- CHANGED: REMOVED STRICT DATE FILTER ---
        # We allow all data so the DB isn't empty. The Validator handles date logic if needed.
        # if 'acq_date' in df.columns:
        #     df = df[df['acq_date'] == '2025-08-17']
        
        df['sensor'] = sensor_label
        df['acquired_at'] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        if 'acq_time' in df.columns:
            df['acq_time'] = df['acq_time'].str.zfill(4)

        db_columns = get_table_columns(db_name, table_name)
        valid_columns = [col for col in df.columns if col in db_columns]
        df_final = df[valid_columns].copy()

        if table_name == 'landsat_data':
            pk_cols = ['latitude', 'longitude', 'acq_date', 'acq_time', 'scan', 'track']
        else:
            pk_cols = ['latitude', 'longitude', 'acq_date', 'acq_time']
        
        if all(col in df_final.columns for col in pk_cols):
            df_final = df_final.drop_duplicates(subset=pk_cols, keep='first')

        con = sqlite3.connect(db_name)
        cur = con.cursor()
        
        # Don't drop tables here, or we lose the init work. Just clear.
        if table_name != 'landsat_data':
            cur.execute(f"DELETE FROM {table_name}")
            
        con.commit()
        df_final.to_sql(table_name, con, if_exists='append', index=False, chunksize=500)
        con.commit()
        
        count = pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table_name}", con)['count'][0]
        print(f"  -> Loaded {count} rows from CSV.")
        con.close()

    except Exception as e:
        print(f"  ERROR processing {csv_path}: {e}")

def inject_synthetic_data():
    print("\n--- INJECTING SYNTHETIC DEMO DATA ---")
    # This guarantees the "Oil Sands" and "Confirmed Fire" logic works even if CSVs are empty
    
    for table, rows in SYNTHETIC_DATA.items():
        if "viirs" in table: db = VIIRS_DB
        elif "modis" in table: db = MODIS_DB
        else: continue
            
        con = sqlite3.connect(db)
        cur = con.cursor()
        print(f"  Injecting {len(rows)} test rows into {table}...")
        
        for row in rows:
            # Upsert logic to ensure we don't duplicate if run multiple times
            # (Using a simplified INSERT OR REPLACE)
            cur.execute(f"""
                INSERT OR REPLACE INTO {table} 
                (latitude, longitude, acq_date, acq_time, confidence, acquired_at) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (row['lat'], row['lon'], row['date'], row['time'], row['conf'], 
                  f"{row['date']}T{row['time'][:2]}:{row['time'][2:]}:00"))
        
        con.commit()
        con.close()
    print("--- SYNTHETIC INJECTION COMPLETE ---\n")

def seed_demo():
    print("=== STARTING HYBRID SEEDING ===")
    
    # 1. Initialize DBs
    init_all_dbs()
    
    # 2. Try to load CSVs (if they exist)
    for csv_path, db_name, table_name, sensor_label in CSV_MAPPING:
        load_csv_to_table(csv_path, db_name, table_name, sensor_label)

    # 3. Inject Synthetic Data (The Backup Plan)
    inject_synthetic_data()

    print("=== SEEDING COMPLETE ===")

if __name__ == "__main__":
    seed_demo()