import os
import sys
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
from threading import Thread
import traceback

# --- Key Imports ---
# Import the functions from your data_pipeline.py
try:
    from data_pipeline import run_pipeline, DEFAULT_BBOX
except ImportError:
    print("FATAL ERROR: Could not import from data_pipeline.py")
    print("Make sure that file exists and has `run_pipeline` and `DEFAULT_BBOX`.")
    sys.exit(1)


app = Flask(__name__)
CORS(app)

# Path to the database created by the pipeline
VALIDATED_DB = "validated_fires.db"
# This variable will track if the pipeline is already running
is_pipeline_running = False


# ===================================================================
#  YOUR EXISTING ENDPOINTS (Unchanged)
# ===================================================================

@app.route('/')
def home():
    return jsonify({
        "message": "Fire Detection API Server",
        "endpoints": {
            "/api/fires": "Get validated fire data",
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
    # Default: last 24 hours
    since = datetime.now(timezone.utc) - timedelta(days=7)

    if since_str:
        try:
            since = datetime.fromisoformat(since_str.replace('Z', '+00:00'))
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
        except ValueError:
            return jsonify({
                "error": "Invalid 'since' datetime format. Use ISO format like 2025-07-15T00:00:00Z"
            }), 400

    # Connect to validated_fires.db
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
#  NEW ENDPOINT TO TRIGGER THE PIPELINE
# ===================================================================

def run_pipeline_in_thread(bbox_str):
    """
    Wrapper function to run the pipeline in a separate thread
    so the API request can return immediately.
    """
    global is_pipeline_running
    is_pipeline_running = True
    print(f"THREAD: Pipeline starting for BBOX: {bbox_str}...")
    try:
        # This calls the run_pipeline function from data_pipeline.py
        run_pipeline(bbox_str=bbox_str)
        print(f"THREAD: Pipeline finished successfully.")
    except Exception as e:
        print(f"THREAD: Pipeline FAILED.")
        print(traceback.format_exc())
    finally:
        is_pipeline_running = False

@app.route('/api/run-pipeline', methods=['POST'])
def handle_run_pipeline():
    """
    This is the main API endpoint your frontend will call.
    It accepts a new BBOX and triggers the pipeline.
    """
    global is_pipeline_running
    
    if is_pipeline_running:
        # If it's already running, tell the user to wait.
        return jsonify({"message": "Pipeline is already running. Please wait."}), 429 # 429: Too Many Requests

    try:
        data = request.get_json()
        
        # Get the BBOX from the request, or use the default if none is provided
        bbox_str = data.get('bbox', DEFAULT_BBOX)
        
        # Run the pipeline in a background thread
        pipeline_thread = Thread(target=run_pipeline_in_thread, args=(bbox_str,))
        pipeline_thread.start()
        
        # Return an "Accepted" response
        return jsonify({
            "message": "Pipeline execution started.",
            "bbox": bbox_str
        }), 202 # 202: Accepted

    except Exception as e:
        print(f"Error in /api/run-pipeline: {e}")
        return jsonify({"error": str(e)}), 500

# ===================================================================

if __name__ == '__main__':
    # Use 0.0.0.0 to make it accessible on your network (and Lightsail)
    # Your Procfile will override this, but it's good for local testing
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Main API Server on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
