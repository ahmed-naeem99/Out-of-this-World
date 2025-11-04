import pandas as pd
import sqlite3
import time
from datetime import datetime, timedelta, timezone

# Define all variables

MAP_KEY = "d44b3f3aef34095690bdb6bb00c539e6"
DAYS = str(7)  # Last n day of data from 1-10

# Choose a study area i.e. Manitoba (-98.9,53.9,-96.3,55.1)
BBOX = ""  # Test area (lon_min,lat_min,lon_max,lat_max)

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

def fetch_firms(sensor, db_name, table_name, bbox):
    # Use timezone-aware datetime
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    
    # --- Check for empty BBOX ---
    if not bbox:
        print(f"[{timestamp}] Skipping {sensor} data fetch: BBOX is empty.")
        return # Skip the fetch if no bounding box is provided

    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{sensor}/{bbox}/{DAYS}"
    print(f"[{timestamp}] Fetching {sensor} data for BBOX: {bbox}")
    
    con = None 
    df = pd.DataFrame() 

    try:
        # --- 1. FETCH DATA ---
        try:
            df = pd.read_csv(url, dtype={'acq_time': str})
        except pd.errors.EmptyDataError:
            print(f"[{timestamp}] No active fire data returned from API for {sensor}.")
        
        print(f"DEBUG: Downloaded {len(df)} records from API for {sensor}")
        
        # Use timezone-aware datetime
        df['sensor'] = sensor
        df['acquired_at'] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        if not df.empty:
            df = df.drop_duplicates(subset=['latitude', 'longitude', 'acq_date', 'acq_time'])
            print(f"DEBUG: After local dedupe, {len(df)} records remain for staging")

        # --- 2. SAVE TO DATABASE (The "Sync" Pattern) ---
        con = sqlite3.connect(db_name)
        cur = con.cursor()
        
        count_before = pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table_name}", con)['count'][0]
        print(f"DEBUG: Database has {count_before} records before sync")
        
        staging_table = f"staging_{table_name}"
        df.to_sql(staging_table, con, if_exists="replace", index=False)

        
        # === "INSERT OR REPLACE" LOGIC ===
        if not df.empty:
            all_columns = [f'"{col}"' for col in df.columns]
            all_columns_str = ", ".join(all_columns)
            
            # This query now only runs if df is not empty
            replace_query = f'''
                INSERT OR REPLACE INTO {table_name} ({all_columns_str})
                SELECT {all_columns_str} FROM {staging_table}
            '''
            cur.execute(replace_query)


        # === "DELETE" LOGIC ===
        # Use the fixed DAYS from the module
        utc_now = datetime.now(timezone.utc)
        date_window = [
            (utc_now - timedelta(days=i)).strftime('%Y-%m-%d') 
            for i in range(int(DAYS) + 1)
        ]
        date_window_tuple = tuple(date_window)

        # Handle the case of an empty tuple to avoid SQL syntax error
        if len(date_window_tuple) < 1:
              # If DAYS=0, the tuple is empty, just skip deletion
              print("DEBUG: Date window is too small, skipping delete step.")
              deleted_rows = 0
        else:
            # Format tuple for SQL (e.g., ('2025-11-03', '2025-11-02'))
            date_tuple_str = str(date_window_tuple)
            if len(date_window_tuple) == 1:
                # SQLite requires a comma for a single-item tuple in IN clause
                 date_tuple_str = f"('{date_window_tuple[0]}')" 

            delete_query = f'''
                DELETE FROM {table_name}
                WHERE
                    acq_date IN {date_tuple_str}
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
            deleted_rows = cur.rowcount
        
        # === CLEANUP AND REPORTING ===
        cur.execute(f"DROP TABLE IF EXISTS {staging_table}")
        con.commit()

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

def init_all_dbs():
    initialize_db_modis()
    initialize_db_viirs()
    initialize_db_landsat()
    initialize_db_goes()

SENSORS = [
    ("MODIS_NRT", "modis.db", "modis_data"),
    ("VIIRS_SNPP_NRT", "viirs.db", "viirs_snpp"),
    ("VIIRS_NOAA20_NRT", "viirs.db", "viirs_noaa20"),
    ("VIIRS_NOAA21_NRT", "viirs.db", "viirs_noaa21"),
    ("LANDSAT_NRT", "landsat.db", "landsat_data"),
    ("GOES_NRT", "goes.db", "goes_data"),
]

# MAIN LOOP
if __name__ == "__main__":
    init_all_dbs()