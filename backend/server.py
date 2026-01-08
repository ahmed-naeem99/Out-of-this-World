import os
import sys
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
from threading import Thread
import traceback

# --- Key Imports ---
try:
    from data_pipeline import run_pipeline, DEFAULT_BBOX
    # We need the sensor list to know which DBs to query for raw data
    from firms_data_collector_v2 import SENSORS 
except ImportError:
    print("FATAL ERROR: Could not import from data_pipeline.py or firms_data_collector_v2.py")
    print("Ensure these files exist in the same directory.")
    sys.exit(1)


app = Flask(__name__)
CORS(app)

# Centralize path logic
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Standardize DB paths
VALIDATED_DB = os.path.join(BASE_DIR, "validated_fires.db")
VIIRS_DB = os.path.join(BASE_DIR, "viirs.db")
MODIS_DB = os.path.join(BASE_DIR, "modis.db")
LANDSAT_DB = os.path.join(BASE_DIR, "landsat.db")
GOES_DB = os.path.join(BASE_DIR, "goes.db")
is_pipeline_running = False

# --- Helper to normalize confidence to 1-4 scale for frontend ---
def normalize_confidence(conf_val):
    # VIIRS uses 'l', 'n', 'h' (lowercase)
    conf_str = str(conf_val).lower()
    if conf_str in ['l', 'low']: return 2
    if conf_str in ['n', 'nominal']: return 3
    if conf_str in ['h', 'high']: return 4
    
    # Landsat/MODIS uses 'L', 'M', 'H' (uppercase) or 0-100
    conf_str_upper = str(conf_val).upper()
    if conf_str_upper in ['L', 'LOW']: return 2
    if conf_str_upper in ['M', 'MEDIUM', 'NOMINAL']: return 3
    if conf_str_upper in ['H', 'HIGH']: return 4
    
    # MODIS/Landsat numeric confidence (0-100)
    try:
        val = int(conf_val)
        if val >= 80: return 4
        if val >= 50: return 3
        if val >= 30: return 2
        return 1
    except:
        return 1

# ===================================================================
#  ENDPOINTS
# ===================================================================

@app.route('/')
def home():
    return jsonify({
        "message": "Fire Detection API Server",
        "endpoints": {
            "/api/fires": "Get validated fire data",
            "/api/raw_fires": "Get raw sensor data",
            "/api/status": "Check server status",
            "/api/run-pipeline": "POST to filter and validate data for an AOI (demo mode)"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/status')
def status():
    """Check server and database status"""
    try:
        con = sqlite3.connect(VALIDATED_DB)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM validated_fires")
        count = cur.fetchone()[0]
        con.close()
        
        return jsonify({
            "status": "online",
            "database": VALIDATED_DB,
            "total_fires": count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except sqlite3.Error as e:
        return jsonify({
            "status": "error",
            "message": f"Database error: {str(e)}"
        }), 500

@app.route('/api/fires')
def get_validated_fires():
    print(f"DEBUG: Querying DB at {VALIDATED_DB}")
    
    try:
        # Check if database file exists
        if not os.path.exists(VALIDATED_DB):
            print(f"WARNING: Database file not found at {VALIDATED_DB}, returning empty list")
            return jsonify([])
        
        con = sqlite3.connect(VALIDATED_DB, timeout=5.0)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='validated_fires'")
        if not cur.fetchone():
            print("WARNING: Table 'validated_fires' does not exist, returning empty list")
            con.close()
            return jsonify([])

        # Remove date filtering - return all validated fires ordered by confidence_score DESC
        # Include raw_primary_confidence field for verification
        cur.execute("""
            SELECT latitude, longitude, acq_date, acq_time, confidence_level, confidence_score,
                   primary_sensor, validating_sensors, datetime, raw_primary_confidence
            FROM validated_fires
            ORDER BY confidence_score DESC
        """)

        rows = []
        for row in cur.fetchall():
            row_dict = dict(row)
            # Fallback: if confidence_score is missing or NULL, calculate from confidence_level
            if row_dict.get('confidence_score') is None:
                row_dict['confidence_score'] = row_dict.get('confidence_level', 2) * 25.0
            
            # Add confidence to primary_sensor field: "viirs_noaa20(n)" or "viirs_noaa20(H)"
            primary_sensor = row_dict.get('primary_sensor', '')
            raw_primary_conf = row_dict.get('raw_primary_confidence', 'n')
            if raw_primary_conf:
                row_dict['primary_sensor'] = f"{primary_sensor}({raw_primary_conf})"
            else:
                row_dict['primary_sensor'] = primary_sensor
            
            rows.append(row_dict)
        
        # HARD RESET: If table is empty, return [] instead of error
        if len(rows) == 0:
            print("HARD RESET: Table is empty, returning empty list")
            con.close()
            return jsonify([])
        
        print(f"DEBUG: Returning {len(rows)} fires from database")
        con.close()
        return jsonify(rows)
        
    except sqlite3.OperationalError as e:
        # Database locked or busy - return empty list instead of error
        if "locked" in str(e).lower() or "busy" in str(e).lower():
            print(f"WARNING: Database locked/busy: {str(e)}, returning empty list")
            return jsonify([])
        else:
            print(f"WARNING: Database operational error: {str(e)}, returning empty list")
            return jsonify([])
    except sqlite3.Error as e:
        print(f"WARNING: Database error: {str(e)}, returning empty list")
        return jsonify([])
    except Exception as e:
        print(f"WARNING: Unexpected error: {str(e)}, returning empty list")
        return jsonify([])

# ===================================================================
#  NEW ENDPOINT: RAW DATA
# ===================================================================

@app.route('/api/raw_fires')
def get_raw_fires():
    # Get BBOX parameter if provided
    bbox_str = request.args.get('bbox')
    
    all_raw_fires = []
    
    # Parse BBOX if provided: "lon_min,lat_min,lon_max,lat_max"
    bbox_coords = None
    if bbox_str:
        try:
            coords = [float(x.strip()) for x in bbox_str.split(',')]
            if len(coords) == 4:
                bbox_coords = {
                    'lon_min': coords[0],
                    'lat_min': coords[1],
                    'lon_max': coords[2],
                    'lat_max': coords[3]
                }
        except:
            pass  # Invalid BBOX format, ignore

    # Iterate over all sensors defined in firms_data_collector_v2
    for sensor_name, db_file, table_name in SENSORS:
        try:
            # Convert relative path to absolute if needed
            if not os.path.isabs(db_file):
                db_file = os.path.join(BASE_DIR, db_file)
            
            if not os.path.exists(db_file):
                continue

            con = sqlite3.connect(db_file)
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            
            # Build query with BBOX filtering if provided
            if bbox_coords:
                # Get latest date for date filtering (last 24 hours)
                cur.execute(f"SELECT MAX(acq_date) FROM {table_name}")
                latest_date_result = cur.fetchone()
                if latest_date_result and latest_date_result[0]:
                    latest_date = latest_date_result[0]
                    query = f"""SELECT * FROM {table_name} 
                                WHERE acq_date >= ? 
                                AND latitude >= ? AND latitude <= ? 
                                AND longitude >= ? AND longitude <= ?"""
                    cur.execute(query, (
                        latest_date,
                        bbox_coords['lat_min'],
                        bbox_coords['lat_max'],
                        bbox_coords['lon_min'],
                        bbox_coords['lon_max']
                    ))
                else:
                    query = f"""SELECT * FROM {table_name} 
                                WHERE latitude >= ? AND latitude <= ? 
                                AND longitude >= ? AND longitude <= ?"""
                    cur.execute(query, (
                        bbox_coords['lat_min'],
                        bbox_coords['lat_max'],
                        bbox_coords['lon_min'],
                        bbox_coords['lon_max']
                    ))
            else:
                # No BBOX: limit to most recent 1000 fires only
                query = f"SELECT * FROM {table_name} ORDER BY acq_date DESC, acq_time DESC LIMIT 1000"
                cur.execute(query)
            
            rows = cur.fetchall()
            
            for row in rows:
                r = dict(row)
                
                # Normalize data structure
                normalized = {
                    "latitude": r['latitude'],
                    "longitude": r['longitude'],
                    "acq_date": r['acq_date'],
                    "acq_time": r['acq_time'],
                    "confidence_level": normalize_confidence(r.get('confidence', 'l')),
                    "primary_sensor": sensor_name, 
                    "datetime": r.get('acquired_at', r['acq_date']) 
                }
                all_raw_fires.append(normalized)
            
            con.close()
        except Exception as e:
            print(f"Error fetching raw data from {table_name}: {e}")
            continue

    return jsonify(all_raw_fires)

# ===================================================================
#  PIPELINE TRIGGER
# ===================================================================

def run_pipeline_in_thread(bbox_str):
    global is_pipeline_running
    is_pipeline_running = True
    print(f"THREAD: Pipeline starting for BBOX: {bbox_str}...")
    try:
        run_pipeline(bbox_str=bbox_str)
        print(f"THREAD: Pipeline finished successfully.")
    except Exception as e:
        print(f"THREAD: Pipeline FAILED.")
        print(traceback.format_exc())
    finally:
        is_pipeline_running = False

@app.route('/api/run-pipeline', methods=['POST'])
def handle_run_pipeline():
    global is_pipeline_running
    
    # Robust lock check: check multiple times to prevent race conditions
    if is_pipeline_running:
        print("WARNING: Pipeline already running, rejecting request")
        return jsonify({"message": "Pipeline is already running. Please wait."}), 429 
    
    # Double-check after a tiny delay to catch race conditions
    import time
    time.sleep(0.01)  # 10ms delay
    if is_pipeline_running:
        print("WARNING: Pipeline started between checks, rejecting request")
        return jsonify({"message": "Pipeline is already running. Please wait."}), 429 

    try:
        data = request.get_json()
        bbox_str = data.get('bbox', DEFAULT_BBOX)
        
        # Final check before spawning thread
        if is_pipeline_running:
            print("WARNING: Pipeline became active just before thread spawn, rejecting request")
            return jsonify({"message": "Pipeline is already running. Please wait."}), 429 
        
        # Set flag BEFORE starting thread to prevent race condition
        is_pipeline_running = True
        pipeline_thread = Thread(target=run_pipeline_in_thread, args=(bbox_str,))
        pipeline_thread.start()
        
        print(f"Pipeline thread spawned successfully for BBOX: {bbox_str}")
        return jsonify({
            "message": "Pipeline execution started.",
            "bbox": bbox_str
        }), 202 

    except Exception as e:
        print(f"Error in /api/run-pipeline: {e}")
        is_pipeline_running = False  # Reset flag on error
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Main API Server on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)