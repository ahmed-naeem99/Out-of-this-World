import pandas as pd
import sqlite3
import time
from datetime import datetime, timedelta, timezone

# Define all variables

MAP_KEY = "d44b3f3aef34095690bdb6bb00c539e6"
DAYS = str(2)  # Last n day of data from 1-10

# Choose a study area i.e. Manitoba (-98.9,53.9,-96.3,55.1)
BBOX = "-110.1,53.2,-100.5,60.9"  # Test area (lon_min,lat_min,lon_max,lat_max)

# Database setup functions

def initialize_db_modis():
    con = sqlite3.connect("modis.db")
    cur = con.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS modis_data (
            latitude REAL,
            longitude REAL,
            brightness REAL,
            scan REAL,
            track REAL,
            acq_date TEXT,
            acq_time TEXT,
            satellite TEXT,
            instrument TEXT,
            confidence TEXT,
            version TEXT,
            bright_t31 REAL,
            frp REAL,
            daynight TEXT,
            sensor TEXT,
            acquired_at TEXT,
            PRIMARY KEY (latitude, longitude, acq_date, acq_time)
        )
    ''')
    con.commit()
    con.close()

def initialize_db_viirs():
    con = sqlite3.connect("viirs.db")
    cur = con.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS viirs_snpp (
            latitude REAL,
            longitude REAL,
            bright_ti4 REAL,
            scan REAL,
            track REAL,
            acq_date TEXT,
            acq_time TEXT,
            satellite TEXT,
            instrument TEXT,
            confidence TEXT,
            version TEXT,
            bright_ti5,
            frp REAL,
            daynight TEXT,
            sensor TEXT,
            acquired_at TEXT,
            PRIMARY KEY (latitude, longitude, acq_date, acq_time)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS viirs_noaa20 (
            latitude REAL,
            longitude REAL,
            bright_ti4 REAL,
            scan REAL,
            track REAL,
            acq_date TEXT,
            acq_time TEXT,
            satellite TEXT,
            instrument TEXT,
            confidence TEXT,
            version TEXT,
            bright_ti5,
            frp REAL,
            daynight TEXT,
            sensor TEXT,
            acquired_at TEXT,
            PRIMARY KEY (latitude, longitude, acq_date, acq_time)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS viirs_noaa21 (
            latitude REAL,
            longitude REAL,
            bright_ti4 REAL,
            scan REAL,
            track REAL,
            acq_date TEXT,
            acq_time TEXT,
            satellite TEXT,
            instrument TEXT,
            confidence TEXT,
            version TEXT,
            bright_ti5,
            frp REAL,
            daynight TEXT,
            sensor TEXT,
            acquired_at TEXT,
            PRIMARY KEY (latitude, longitude, acq_date, acq_time)
        )
    ''')

    con.commit()
    con.close()

def initialize_db_landsat():
    con = sqlite3.connect("landsat.db")
    cur = con.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS landsat_data (
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
            PRIMARY KEY (latitude, longitude, acq_date, acq_time)
        )
    ''')
    con.commit()
    con.close()

def initialize_db_goes():
    con = sqlite3.connect("goes.db")
    cur = con.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS goes_data (
            latitude REAL,
            longitude REAL,
            bright_ti4 REAL,
            scan REAL,
            track REAL,
            acq_date TEXT,
            acq_time TEXT,
            satellite TEXT,
            instrument TEXT,
            confidence TEXT,
            version TEXT,
            bright_ti5,
            frp REAL,
            daynight TEXT,
            sensor TEXT,
            acquired_at TEXT,
            PRIMARY KEY (latitude, longitude, acq_date, acq_time)
        )
    ''')
    con.commit()
    con.close()


# =================================================================
# vvvv THIS IS THE UPDATED FUNCTION vvvv
# =================================================================

def fetch_firms(sensor, db_name, table_name, bbox):
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    
    # --- THIS IS THE KEY CHANGE ---
    # The URL is now built using the 'bbox' argument passed to the function
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{sensor}/{bbox}/{DAYS}"
    # --- END OF KEY CHANGE ---
    
    print(f"[{timestamp}] Fetching {sensor} data for BBOX: {bbox}")
    
    con = None  # Initialize con outside try block for finally clause
    df = pd.DataFrame() # Initialize empty DataFrame for robust error handling

    try:
        # --- 1. FETCH DATA ---
        # We force 'acq_time' to be a string (dtype)
        try:
            df = pd.read_csv(url, dtype={'acq_time': str})
        except pd.errors.EmptyDataError:
            print(f"[{timestamp}] No active fire data returned from API for {sensor}.")
            # We continue with an empty df to allow the DELETE step to run
        
        print(f"DEBUG: Downloaded {len(df)} records from API for {sensor}")
        
        # Add our custom columns
        df['sensor'] = sensor
        df['acquired_at'] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Clean duplicates *within the downloaded file* just in case.
        if not df.empty:
            df = df.drop_duplicates(subset=['latitude', 'longitude', 'acq_date', 'acq_time'])
            print(f"DEBUG: After local dedupe, {len(df)} records remain for staging")

        # --- 2. SAVE TO DATABASE (The "Sync" Pattern) ---
        con = sqlite3.connect(db_name)
        cur = con.cursor()
        
        # Get count before
        count_before = pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table_name}", con)['count'][0]
        print(f"DEBUG: Database has {count_before} records before sync")
        
        staging_table = f"staging_{table_name}" # A unique temp table name

        # Step A: Dump all new data (even if empty) into a temporary staging table.
        df.to_sql(staging_table, con, if_exists="replace", index=False)

        
        # === "INSERT OR REPLACE" LOGIC (Compatible with old SQLite) ===
        if not df.empty:
            all_columns = [f'"{col}"' for col in df.columns]
            all_columns_str = ", ".join(all_columns)
        replace_query = f'''
            INSERT OR REPLACE INTO {table_name} ({all_columns_str})
            SELECT {all_columns_str} FROM {staging_table}
        '''
        cur.execute(replace_query)


        # === NEW "DELETE" LOGIC ===
        utc_now = datetime.now(timezone.utc)
        date_window = [
            (utc_now - timedelta(days=i)).strftime('%Y-%m-%d') 
            for i in range(int(DAYS) + 1)
        ]
        date_window_tuple = tuple(date_window) # e.g., ('2025-10-27', '2025-10-26', '2025-10-25')

        # Step C: Delete
        # This logic is correct. It deletes records from the DB that are in the
        # time window but NOT in the new data we just downloaded.
        # ***BUT*** this only works if the BBOX is the same!
        # If the BBOX changes, we must delete *all* old data first.
        # We will handle that in `run_pipeline.py`.
        
        delete_query = f'''
            DELETE FROM {table_name}
            WHERE
                acq_date IN {date_window_tuple}
                AND NOT EXISTS (
                    SELECT 1 FROM {staging_table}
                    WHERE
                        {staging_table}.latitude = {table_name}.latitude AND
                        {staging_table}.longitude = {table_name}.longitude AND
                        {staging_table}.acq_date = {table_name}.acq_date AND
                        {staging_table}.acq_time = {table_name}.acq_time
                )
        '''
        cur.execute(delete_query)
        deleted_rows = cur.rowcount # Get how many rows were deleted
        
        # Step D: Clean up the staging table
        cur.execute(f"DROP TABLE IF EXISTS {staging_table}")

        con.commit()

        # === NEW "REPORTING" LOGIC ===
        count_after = pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table_name}", con)['count'][0]
        net_change = count_after - count_before
        
        print(f"DEBUG: Database now has {count_after} records total")
        print(f"[{timestamp}] SUCCESS: Synced {sensor}. Net change: {net_change:+} records. (Deleted {deleted_rows} stale records)")

    except Exception as e:
        print(f"[{timestamp}] ERROR processing {sensor}: {e}")
        if con:
            con.rollback()
    finally:
        if con:
            con.close()
# db_init.py section
def init_all_dbs():
    initialize_db_modis()
    initialize_db_viirs()
    initialize_db_landsat()
    initialize_db_goes()

# sensor_config.py section
SENSORS = [
    ("MODIS_NRT", "modis.db", "modis_data"),
    ("VIIRS_SNPP_NRT", "viirs.db", "viirs_snpp"),
    ("VIIRS_NOAA20_NRT", "viirs.db", "viirs_noaa20"),
    ("VIIRS_NOAA21_NRT", "viirs.db", "viirs_noaa21"),
    ("LANDSAT_NRT", "landsat.db", "landsat_data"),
    ("GOES_NRT", "goes.db", "goes_data"),
]

# NAIN LOOP
if __name__ == "__main__":
    init_all_dbs()