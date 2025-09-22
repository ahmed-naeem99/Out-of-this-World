import pandas as pd
import sqlite3
import time
from datetime import datetime, timezone

# Define all variables

MAP_KEY = "d44b3f3aef34095690bdb6bb00c539e6"
DAYS = str(1)  # Last n day of data from 1-10

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


def fetch_firms(sensor, db_name, table_name):
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{sensor}/{BBOX}/{DAYS}"
    print(f"[{timestamp}] Fetching {sensor} data")

    try:
        df = pd.read_csv(url)

        # Add sensor name
        df['sensor'] = sensor

        # Build acquired_at properly from acq_date + acq_time
        # FIRMS gives acq_time like 924 → make it "09:24"
        df['acquired_at'] = df.apply(
            lambda r: f"{r['acq_date']} "
                      f"{str(r['acq_time']).zfill(4)[:2]}:"
                      f"{str(r['acq_time']).zfill(4)[2:]}",
            axis=1
        )

        con = sqlite3.connect(db_name)
        cur = con.cursor()

        # Explicitly match DB schema column order
        cols = [
            "latitude","longitude","bright_ti4","scan","track",
            "acq_date","acq_time","satellite","instrument",
            "confidence","version","bright_ti5","frp",
            "daynight","sensor","acquired_at"
        ]
        sql = f"""
            INSERT OR IGNORE INTO {table_name} 
            ({','.join(cols)})
            VALUES ({','.join(['?'] * len(cols))})
        """

        skipped = 0
        for _, row in df.iterrows():
            try:
                values = [None if pd.isna(x) else x for x in row[cols]]
                cur.execute(sql, tuple(values))
            except Exception as e:
                print(f"Skipping row due to error: {e}")
                skipped += 1

        con.commit()
        con.close()

        print(f"[{timestamp}] {sensor} data saved successfully (skipped {skipped})")

    except Exception as e:
        print(f"[{timestamp}] Error occurred: {e}")

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
