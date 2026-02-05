import sqlite3
import os
from dotenv import load_dotenv
from pathlib import Path
from firms_data_collector_v2 import init_all_dbs, SENSORS, initialize_db_viirs, initialize_db_modis, initialize_db_landsat
from fire_alert_validator import validate_fires_all_sources, initialize_validated_db
from datetime import datetime, timezone

# Centralize path logic
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Standardize DB paths
VALIDATED_DB = os.path.join(BASE_DIR, "validated_fires.db")
VIIRS_DB = os.path.join(BASE_DIR, "viirs.db")
MODIS_DB = os.path.join(BASE_DIR, "modis.db")
LANDSAT_DB = os.path.join(BASE_DIR, "landsat.db")
GOES_DB = os.path.join(BASE_DIR, "goes.db")

# Load .env file from fire-map-frontend folder
env_path = Path(__file__).parent.parent / 'frontend' / 'fire-map-frontend' / '.env'
load_dotenv(env_path)

# Read bounding box from REACT_APP_DEFAULT_BBOX in .env file
DEFAULT_BBOX = os.getenv('REACT_APP_DEFAULT_BBOX')
if not DEFAULT_BBOX:
    raise ValueError("REACT_APP_DEFAULT_BBOX must be set in .env file")

# ALL SOURCES - Use for unified validation
ALL_SOURCES = [
    (VIIRS_DB, "viirs_noaa20"),
    (VIIRS_DB, "viirs_noaa21"),
    (VIIRS_DB, "viirs_snpp"),
    (MODIS_DB, "modis_data"),
    (LANDSAT_DB, "landsat_data"),
    (GOES_DB, "goes_data"),
]

# Get the list of all tables and the validated table
ALL_TABLES = [(db, table) for _, db, table in SENSORS]
VALIDATED_TABLE = "validated_fires"

# Track the last BBOX used
BBOX_TRACKING_FILE = "current_bbox.txt"

def get_current_bbox_from_file():
    try:
        with open(BBOX_TRACKING_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def save_current_bbox_to_file(bbox_str):
    try:
        with open(BBOX_TRACKING_FILE, "w") as f:
            f.write(bbox_str)
    except Exception as e:
        print(f"Error writing to {BBOX_TRACKING_FILE}: {e}")

CURRENT_BBOX_IN_DB = get_current_bbox_from_file() or DEFAULT_BBOX


def clear_validated_data():
    print("--- New BBOX detected. Clearing validated fires... ---")
    try:
        con = sqlite3.connect(VALIDATED_DB)
        cur = con.cursor()
        print(f"Clearing table: {VALIDATED_TABLE} in {VALIDATED_DB}")
        cur.execute(f"DELETE FROM {VALIDATED_TABLE}")
        con.commit()
        con.close()
        print("--- Validated fires cleared. ---")
    except Exception as e:
        print(f"Error clearing {VALIDATED_DB}: {e}")


def run_pipeline(bbox_str=None):
    """
    Unified pipeline: Load all sources, deduplicate, then validate.
    This prevents the 3x duplication issue.
    """
    global CURRENT_BBOX_IN_DB
    
    # HARD RESET: Initialize and Clear
    print("HARD RESET: Initializing validated_fires table...")
    initialize_validated_db()
    
    print("HARD RESET: Clearing validated_fires table at pipeline start...")
    try:
        conn = sqlite3.connect(VALIDATED_DB)
        conn.execute("DELETE FROM validated_fires")
        conn.commit()
        conn.close()
        print("HARD RESET: Validated fires table cleared.")
    except Exception as e:
        print(f"HARD RESET: Error clearing table (might not exist yet): {e}")
    
    new_bbox = bbox_str or DEFAULT_BBOX
    
    print(f"--- Pipeline started at {datetime.now(timezone.utc).isoformat()} ---")
    print(f"Target BBOX: {'(EMPTY - NO FILTER)' if not new_bbox else new_bbox}")
    
    print("Initializing all database tables...")
    initialize_validated_db()
    initialize_db_viirs()
    initialize_db_modis()
    initialize_db_landsat()
    
    if new_bbox != CURRENT_BBOX_IN_DB:
        clear_validated_data()
        CURRENT_BBOX_IN_DB = new_bbox
        save_current_bbox_to_file(new_bbox)
        print(f"BBOX changed. Updated to: {new_bbox}")
    else:
        print("BBOX is unchanged.")
    
    # --- UNIFIED VALIDATION ---
    # Process all sources together to prevent duplication
    
    if new_bbox:
        validated_fires = validate_fires_all_sources(ALL_SOURCES, bbox=new_bbox)
    else:
        validated_fires = validate_fires_all_sources(ALL_SOURCES)

    # Final DB Count Check
    con_final = sqlite3.connect(VALIDATED_DB)
    cur_final = con_final.cursor()
    cur_final.execute("SELECT COUNT(*) FROM validated_fires")
    db_count = cur_final.fetchone()[0]
    con_final.close()
    
    print(f"\nTotal unique fires in DB: {db_count}")
    print(f"--- Pipeline finished at {datetime.now(timezone.utc).isoformat()} ---\n")

if __name__ == "__main__":
    run_pipeline()