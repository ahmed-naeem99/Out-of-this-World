from firms_data_collector_v2 import init_all_dbs, fetch_firms, SENSORS
from fire_alert_validator import validate_fires, initialize_validated_db
from datetime import datetime

# Define which sensor is primary (used for alert validation) and secondary
PRIMARY = ("viirs.db", "viirs_noaa20")
SECONDARY = [
    ("modis.db", "modis_data"),
    ("viirs.db", "viirs_snpp"),
    ("viirs.db", "viirs_noaa21"),
    ("landsat.db", "landsat_data"),
    ("goes.db", "goes_data")
]

def run_pipeline():
    print(f"--- Pipeline started at {datetime.utcnow().isoformat()} ---")
    
    # Ensure validated_fires DB exists
    initialize_validated_db()
    
    # Step 1: Fetch new data
    init_all_dbs()
    for sensor, db, table in SENSORS:
        fetch_firms(sensor, db, table)

    # Step 2: Validate fires
    validate_fires(PRIMARY[0], PRIMARY[1], SECONDARY)

    print(f"--- Pipeline finished at {datetime.utcnow().isoformat()} ---\n")

if __name__ == "__main__":
    run_pipeline()
