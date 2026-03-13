import sqlite3
import os
from dotenv import load_dotenv
from pathlib import Path
from firms_data_collector_v2 import init_all_dbs, SENSORS, initialize_db_viirs, initialize_db_modis, initialize_db_landsat
from fire_alert_validator import validate_fires_all_sources, initialize_validated_db, AB_SK_BBOX
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
VALIDATED_DB = os.path.join(BASE_DIR, "validated_fires.db")
VIIRS_DB = os.path.join(BASE_DIR, "viirs.db")
MODIS_DB = os.path.join(BASE_DIR, "modis.db")
LANDSAT_DB = os.path.join(BASE_DIR, "landsat.db")
GOES_DB = os.path.join(BASE_DIR, "goes.db")

ALL_SOURCES = [
    (VIIRS_DB, "viirs_noaa20"), (VIIRS_DB, "viirs_noaa21"), (VIIRS_DB, "viirs_snpp"),
    (MODIS_DB, "modis_data"), (LANDSAT_DB, "landsat_data"), (GOES_DB, "goes_data"),
]

def run_pipeline(bbox_str=None):
    print(f"--- Pipeline Started: {datetime.now(timezone.utc).isoformat()} ---")
    
    # 1. Parse BBOX if provided
    target_bbox = None
    if bbox_str and isinstance(bbox_str, str) and len(bbox_str.split(',')) == 4:
        try:
            # Format expected: lon_min, lat_min, lon_max, lat_max
            parts = [float(x.strip()) for x in bbox_str.split(',')]
            target_bbox = {
                'lon_min': parts[0],
                'lat_min': parts[1],
                'lon_max': parts[2],
                'lat_max': parts[3]
            }
            print(f"Target Region: Custom User Input ({bbox_str})")
        except ValueError:
            print("Invalid BBOX format. Using defaults.")
            target_bbox = AB_SK_BBOX
    else:
        print(f"Target Region: Alberta & Saskatchewan (Default)")
        target_bbox = AB_SK_BBOX
    
    print("Initializing tables...")
    initialize_validated_db()
    initialize_db_viirs()
    initialize_db_modis()
    initialize_db_landsat()
    
    # 2. Pass the parsed bbox to the validator
    validate_fires_all_sources(ALL_SOURCES, bbox=target_bbox)
    
    print(f"--- Pipeline Finished ---")

if __name__ == "__main__":
    run_pipeline()