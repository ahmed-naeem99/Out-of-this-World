import sqlite3
import os
from dotenv import load_dotenv
from pathlib import Path
from firms_data_collector_v2 import init_all_dbs, SENSORS, initialize_db_viirs, initialize_db_modis, initialize_db_landsat
from fire_alert_validator import validate_fires, initialize_validated_db
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

# Define ONLY ONE VIIRS sensor as primary source
# Use absolute paths for database files
VIIRS_PRIMARY_SENSORS = [
    (VIIRS_DB, "viirs_noaa20")
]

# Secondary sources: MODIS, Landsat, GOES, and the other two VIIRS sensors as cross-checks
SECONDARY = [
    (MODIS_DB, "modis_data"),
    (LANDSAT_DB, "landsat_data"),
    (GOES_DB, "goes_data"),
    (VIIRS_DB, "viirs_noaa21"),  # VIIRS cross-check
    (VIIRS_DB, "viirs_snpp")     # VIIRS cross-check
]

# Get the list of all tables and the validated table
ALL_TABLES = [(db, table) for _, db, table in SENSORS]
VALIDATED_TABLE = "validated_fires"

# Track the last BBOX used - stored in a file to persist across runs
BBOX_TRACKING_FILE = "current_bbox.txt"

def get_current_bbox_from_file():
    """Read the last used BBOX from file, or return None if file doesn't exist"""
    try:
        with open(BBOX_TRACKING_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def save_current_bbox_to_file(bbox_str):
    """Save the current BBOX to file"""
    try:
        with open(BBOX_TRACKING_FILE, "w") as f:
            f.write(bbox_str)
    except Exception as e:
        print(f"Error writing to {BBOX_TRACKING_FILE}: {e}")

CURRENT_BBOX_IN_DB = get_current_bbox_from_file() or DEFAULT_BBOX


def clear_validated_data():
    """
    Clear only the validated fires database when BBOX changes.
    In demo mode, we don't clear raw databases (they contain pre-seeded data).
    """
    print("--- New BBOX detected. Clearing validated fires... ---")
    
    try:
        con = sqlite3.connect(VALIDATED_DB)
        cur = con.cursor()
        print(f"Clearing table: {VALIDATED_TABLE} in {VALIDATED_DB}")
        cur.execute(f"DROP TABLE IF EXISTS {VALIDATED_TABLE}")
        con.commit()
        con.close()
        print("--- Validated fires cleared. ---")
    except Exception as e:
        print(f"Error clearing {VALIDATED_DB}: {e}")


def run_pipeline(bbox_str=None):
    """
    Demo mode pipeline: Query raw databases for points inside BBOX, then validate fires.
    No API fetching - works with pre-seeded demo data.
    
    When bbox_str is provided, queries viirs.db, modis.db, and landsat.db
    for any points that fall inside the bbox_str coordinates (lon_min,lat_min,lon_max,lat_max),
    then runs validate_fires on that filtered subset.
    """
    global CURRENT_BBOX_IN_DB
    
    # HARD RESET: Initialize table first, then clear it safely
    print("HARD RESET: Initializing validated_fires table...")
    initialize_validated_db()
    
    # HARD RESET: Clear validated_fires table ONCE at the very top before any processing
    print("HARD RESET: Clearing validated_fires table at pipeline start...")
    try:
        conn = sqlite3.connect(VALIDATED_DB)
        conn.execute("DELETE FROM validated_fires")
        conn.commit()
        conn.close()
        print("HARD RESET: Validated fires table cleared.")
    except sqlite3.OperationalError as e:
        # If table doesn't exist, ignore error (it will be empty anyway after initialization)
        if "no such table" in str(e).lower():
            print(f"HARD RESET: Table doesn't exist yet (will be created), proceeding...")
        else:
            print(f"HARD RESET: Error clearing table: {e}, proceeding anyway...")
    except Exception as e:
        print(f"HARD RESET: Unexpected error clearing table: {e}, proceeding anyway...")
    
    # Use the provided BBOX or fall back to the empty default
    new_bbox = bbox_str or DEFAULT_BBOX
    
    print(f"--- Pipeline started at {datetime.now(timezone.utc).isoformat()} ---")
    print(f"Target BBOX: {'(EMPTY - NO FILTER)' if not new_bbox else new_bbox}")
    
    # Robust table initialization - ensure tables exist even if files were deleted
    print("Initializing all database tables...")
    initialize_validated_db()
    initialize_db_viirs()
    initialize_db_modis()
    initialize_db_landsat()
    
    # --- BBOX CHANGE DETECTION & CLEARING LOGIC ---
    if new_bbox != CURRENT_BBOX_IN_DB:
        clear_validated_data()
        CURRENT_BBOX_IN_DB = new_bbox
        save_current_bbox_to_file(new_bbox)
        print(f"BBOX changed. Updated to: {'(EMPTY)' if not new_bbox else new_bbox}")
    else:
        print("BBOX is unchanged.")
    
    # --- BBOX FILTERING AND VALIDATION ---
    
    # Use only ONE VIIRS sensor as primary (others act as cross-checks in secondary)
    primary_db, primary_table = VIIRS_PRIMARY_SENSORS[0]
    print(f"\n--- Validating fires using {primary_table} as primary sensor... ---")
    print(f"Secondary sources: {[tbl for _, tbl in SECONDARY]}")
    
    if new_bbox:
        # Validate fires with BBOX filtering (filtering happens during load_detections)
        validate_fires(primary_db, primary_table, SECONDARY, bbox=new_bbox)
    else:
        # No BBOX: validate all data
        validate_fires(primary_db, primary_table, SECONDARY)
    
    # Get final count
    con_final = sqlite3.connect(VALIDATED_DB)
    cur_final = con_final.cursor()
    cur_final.execute("SELECT COUNT(*) FROM validated_fires")
    count_final = cur_final.fetchone()[0]
    con_final.close()
    print(f"Total fires validated: {count_final}")

    print(f"--- Pipeline finished at {datetime.now(timezone.utc).isoformat()} ---\n")

if __name__ == "__main__":
    # When run manually, it uses the empty default BBOX
    run_pipeline()
