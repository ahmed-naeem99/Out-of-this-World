import sqlite3
from firms_data_collector_v2 import init_all_dbs, fetch_firms, SENSORS
from fire_alert_validator import validate_fires, initialize_validated_db
from datetime import datetime, timezone

# Define which sensor is primary (used for alert validation) and secondary
PRIMARY = ("viirs.db", "viirs_noaa20")
SECONDARY = [
    ("modis.db", "modis_data"),
    ("viirs.db", "viirs_snpp"),
    ("viirs.db", "viirs_noaa21"),
    ("landsat.db", "landsat_data"),
    ("goes.db", "goes_data")
]

# Get the list of all tables and the validated table
ALL_TABLES = [(db, table) for _, db, table in SENSORS]
VALIDATED_DB = "validated_fires.db"
VALIDATED_TABLE = "validated_fires"

# --- MODIFIED: Default BBOX is now an empty string for an empty map start ---
DEFAULT_BBOX = "-122.0,53.0,-110.0,60.0"

# We keep track of the last BBOX used
try:
    with open("last_bbox.txt", "r") as f:
        CURRENT_BBOX_IN_DB = f.read()
except FileNotFoundError:
    CURRENT_BBOX_IN_DB = DEFAULT_BBOX


def clear_all_data():
    """
    Connects to every database and deletes all data from every table.
    This is critical when the Area of Interest changes, OR when the AOI is reset to empty.
    """
    print("--- New BBOX or AOI reset detected. Clearing all old data... ---")
    
    # Get a unique list of all databases
    all_dbs = set([db for db, _ in ALL_TABLES])
    
    for db_name in all_dbs:
        try:
            con = sqlite3.connect(db_name)
            cur = con.cursor()
            # Find all tables in this DB that we manage
            tables_to_clear = [table for db, table in ALL_TABLES if db == db_name]
            for table in tables_to_clear:
                print(f"Clearing table: {table} in {db_name}")
                cur.execute(f"DELETE FROM {table}")
            con.commit()
            con.close()
        except Exception as e:
            print(f"Error clearing {db_name}: {e}")

    # Also clear the validated fires database
    try:
        con = sqlite3.connect(VALIDATED_DB)
        cur = con.cursor()
        print(f"Clearing table: {VALIDATED_TABLE} in {VALIDATED_DB}")
        cur.execute(f"DELETE FROM {VALIDATED_TABLE}")
        con.commit()
        con.close()
    except Exception as e:
        print(f"Error clearing {VALIDATED_DB}: {e}")
    
    print("--- All databases cleared. ---")


def run_pipeline(bbox_str=None):
    """
    Runs the full data pipeline.
    If 'bbox_str' is provided and is different from the last run,
    it will wipe all databases before fetching new data.
    """
    global CURRENT_BBOX_IN_DB
    
    # Use the provided BBOX or fall back to the empty default
    new_bbox = bbox_str or DEFAULT_BBOX
    
    print(f"--- Pipeline started at {datetime.now(timezone.utc).isoformat()} ---")
    print(f"Target BBOX: {'(EMPTY - NO FETCH)' if not new_bbox else new_bbox}")
    
    # --- BBOX CHANGE DETECTION & CLEARING LOGIC ---
    if new_bbox != CURRENT_BBOX_IN_DB:
        clear_all_data()
        # Save the new BBOX as the "current" one
        try:
            with open("last_bbox.txt", "w") as f:
                f.write(new_bbox)
            CURRENT_BBOX_IN_DB = new_bbox
            print(f"Updated last_bbox.txt to: {'(EMPTY)' if not new_bbox else new_bbox}")
        except Exception as e:
            print(f"Error writing to last_bbox.txt: {e}")
    else:
        print("BBOX is unchanged. Performing standard sync.")
    
    
    # Ensure all tables exist (harmless to run)
    init_all_dbs()
    initialize_validated_db()
    
    # --- CONDITIONAL FETCH: Only fetch if a BBOX is provided/set ---
    if new_bbox:
        # Step 1: Fetch new data using the *new_bbox*
        for sensor, db, table in SENSORS:
            # fetch_firms will now skip if new_bbox is empty
            fetch_firms(sensor, db, table, new_bbox) 

        # Step 2: Validate fires
        validate_fires(PRIMARY[0], PRIMARY[1], SECONDARY)
    else:
        print("BBOX is empty. Skipping data fetch and validation.")

    print(f"--- Pipeline finished at {datetime.now(timezone.utc).isoformat()} ---\n")

if __name__ == "__main__":
    # When run manually, it uses the empty default BBOX
    run_pipeline()
