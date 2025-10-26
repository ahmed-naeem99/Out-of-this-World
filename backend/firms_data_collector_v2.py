import pandas as pd
import sqlite3
import time
from datetime import datetime, timezone

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

    try:
        # --- 1. FETCH DATA ---
        # We force 'acq_time' to be a string (dtype)
        # This prevents '0030' (00:30) from being read as the integer 30.
        df = pd.read_csv(url, dtype={'acq_time': str})
        
        if df.empty:
            print(f"[{timestamp}] No data downloaded from API for {sensor}.")
            return

        print(f"DEBUG: Downloaded {len(df)} records from API for {sensor}")
        
        # Add our custom columns
        df['sensor'] = sensor
        df['acquired_at'] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # Clean duplicates *within the downloaded file* just in case.
        df = df.drop_duplicates(subset=['latitude', 'longitude', 'acq_date', 'acq_time'])
        print(f"DEBUG: After local dedupe, {len(df)} records remain for staging")

        # --- 2. SAVE TO DATABASE (The "Upsert" Pattern) ---
        con = sqlite3.connect(db_name)
        
        # Get count before
        count_before = pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table_name}", con)['count'][0]
        print(f"DEBUG: Database has {count_before} records before insert")

        # Get the columns from the DataFrame to ensure they match the SQL query
        # This makes the code robust, as each sensor has different columns
        all_columns = [f'"{col}"' for col in df.columns]
        all_columns_str = ", ".join(all_columns)
        
        staging_table = f"staging_{table_name}" # A unique temp table name

        # Step A: Dump all new data into a temporary staging table.
        # 'if_exists="replace"' makes this fast and clean.
        df.to_sql(staging_table, con, if_exists="replace", index=False)

        # Step B: Use "INSERT OR IGNORE" to copy from staging to main.
        # The PRIMARY KEY you created will automatically and *very quickly*
        # "ignore" any rows that are already in {table_name}.
        con.execute(f'''
            INSERT OR IGNORE INTO {table_name} ({all_columns_str})
            SELECT {all_columns_str} FROM {staging_table}
        ''')
        
        # Step C: Clean up the staging table
        con.execute(f"DROP TABLE IF EXISTS {staging_table}")

        con.commit()

        # Get count after
        count_after = pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table_name}", con)['count'][0]
        new_records = count_after - count_before
        
        print(f"DEBUG: Database now has {count_after} records total")
        print(f"[{timestamp}] SUCCESS: Inserted {new_records} new records for {sensor}.")

    except pd.errors.EmptyDataError:
        print(f"[{timestamp}] No data returned from FIRMS API for {sensor}.")
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