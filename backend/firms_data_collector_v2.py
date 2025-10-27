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

def fetch_firms(sensor, db_name, table_name):
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{sensor}/{BBOX}/{DAYS}"
    print(f"[{timestamp}] Fetching {sensor} data")
    
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
        df['acquired_at'] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

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

        
        # === NEW "UPSERT" LOGIC ===
        # This handles both INSERTS and UPDATES in one command.
        if not df.empty:
            # Get all columns for the INSERT
            all_columns = [f'"{col}"' for col in df.columns]
            all_columns_str = ", ".join(all_columns)
            
            # Define primary key columns (must match your CREATE TABLE)
            pk_columns = ['latitude', 'longitude', 'acq_date', 'acq_time']
            
            # Get columns to UPDATE (all columns *except* the primary key)
            update_columns = [col for col in df.columns if col not in pk_columns]
            
            # Create the "SET" part of the query
            # e.g., "confidence = excluded.confidence, version = excluded.version"
            update_set_str = ", ".join([f'"{col}" = excluded."{col}"' for col in update_columns])
            
            # Step B: Insert or Update (Upsert)
            # If PK matches, UPDATE the other columns.
            # If no PK match, INSERT a new row.
            upsert_query = f'''
                INSERT INTO {table_name} ({all_columns_str})
                SELECT {all_columns_str} FROM {staging_table}
                ON CONFLICT(latitude, longitude, acq_date, acq_time) DO UPDATE SET
                    {update_set_str}
            '''
            cur.execute(upsert_query)


        # === NEW "DELETE" LOGIC ===
        # This is the critical step you were missing.
        
        # We must define the time window to check for deletions.
        # We can't just use the dates in the staging_table, because if there
        # are NO fires, the staging table is empty, and nothing gets deleted.
        # Instead, we build a date list based on the {DAYS} variable.
        
        utc_now = datetime.now(timezone.utc)
        # We check +1 day to cover the full 48-hour window (e.g., 48h ago might be 2 days ago)
        date_window = [
            (utc_now - timedelta(days=i)).strftime('%Y-%m-%d') 
            for i in range(int(DAYS) + 1)
        ]
        date_window_tuple = tuple(date_window) # e.g., ('2025-10-27', '2025-10-26', '2025-10-25')

        # Step C: Delete
        # Delete rows from our local DB that are in the time window
        # but are *NOT* in the fresh data from NASA (the staging table).
        delete_query = f'''
            DELETE FROM {table_name}
            WHERE
                -- Condition 1: The row is inside the time window we just fetched
                acq_date IN {date_window_tuple}
                
                -- Condition 2: And this row (by PK) does NOT exist in the new data
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
        
        # Get count after
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