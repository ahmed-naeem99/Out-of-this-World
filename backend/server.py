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

VALIDATED_DB = "validated_fires.db"
is_pipeline_running = False

# --- Helper to normalize confidence to 1-4 scale for frontend ---
def normalize_confidence(conf_val):
    # VIIRS uses 'l', 'n', 'h'
    if str(conf_val).lower() in ['l', 'low']: return 2
    if str(conf_val).lower() in ['n', 'nominal']: return 3
    if str(conf_val).lower() in ['h', 'high']: return 4
    
    # MODIS uses 0-100
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
            "/api/run-pipeline": "POST to trigger a new data pull for an AOI"
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
    since_str = request.args.get('since')
    since = datetime.now(timezone.utc) - timedelta(days=7)

    if since_str:
        try:
            since = datetime.fromisoformat(since_str.replace('Z', '+00:00'))
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
        except ValueError:
            return jsonify({
                "error": "Invalid 'since' datetime format."
            }), 400

    try:
        con = sqlite3.connect(VALIDATED_DB)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        cur.execute("""
            SELECT latitude, longitude, acq_date, acq_time, confidence_level,
                   primary_sensor, validating_sensors, datetime
            FROM validated_fires
            WHERE datetime >= ?
            ORDER BY datetime DESC
        """, (since.isoformat(),))

        rows = [dict(row) for row in cur.fetchall()]
        con.close()
        return jsonify(rows)
        
    except sqlite3.Error as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

# ===================================================================
#  NEW ENDPOINT: RAW DATA
# ===================================================================

@app.route('/api/raw_fires')
def get_raw_fires():
    since_str = request.args.get('since')
    # Default to 24h for raw data if not specified
    since = datetime.now(timezone.utc) - timedelta(days=1)
    if since_str:
        try:
            since = datetime.fromisoformat(since_str.replace('Z', '+00:00'))
            if since.tzinfo is None: since = since.replace(tzinfo=timezone.utc)
        except ValueError:
            pass 

    since_date_str = since.strftime('%Y-%m-%d')
    all_raw_fires = []

    # Iterate over all sensors defined in firms_data_collector_v2
    for sensor_name, db_file, table_name in SENSORS:
        try:
            if not os.path.exists(db_file):
                continue

            con = sqlite3.connect(db_file)
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            
            # Simple date filtering 
            query = f"SELECT * FROM {table_name} WHERE acq_date >= ?"
            cur.execute(query, (since_date_str,))
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
    if is_pipeline_running:
        # 429 indicates specific "Too Many Requests" state
        return jsonify({"message": "Pipeline is already running. Please wait."}), 429 

    try:
        data = request.get_json()
        bbox_str = data.get('bbox', DEFAULT_BBOX)
        pipeline_thread = Thread(target=run_pipeline_in_thread, args=(bbox_str,))
        pipeline_thread.start()
        
        return jsonify({
            "message": "Pipeline execution started.",
            "bbox": bbox_str
        }), 202 

    except Exception as e:
        print(f"Error in /api/run-pipeline: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Main API Server on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)