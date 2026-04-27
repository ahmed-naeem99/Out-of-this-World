import os
import sys
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
from threading import Thread
import traceback

try:
    from data_pipeline import run_pipeline
    from firms_data_collector_v2 import SENSORS
    # Import strict bounds as a default fallback only
    from fire_alert_validator import AB_SK_BBOX
except ImportError:
    sys.exit(1)

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
VALIDATED_DB = os.path.join(BASE_DIR, "validated_fires.db")

def normalize_confidence(conf_val):
    s = str(conf_val).lower()
    if s in ['l', 'low']: return 1
    if s in ['n', 'nominal']: return 2
    if s in ['h', 'high']: return 3
    try:
        val = int(float(conf_val))
        if val >= 85: return 3
        if val >= 60: return 2
        return 1
    except: return 1

@app.route('/api/raw_fires')
def get_raw_fires():
    bbox_param  = request.args.get('bbox')
    since_param = request.args.get('since')

    if bbox_param:
        try:
            lon_min, lat_min, lon_max, lat_max = [float(x) for x in bbox_param.split(',')]
        except:
            lat_min, lat_max = AB_SK_BBOX['lat_min'], AB_SK_BBOX['lat_max']
            lon_min, lon_max = AB_SK_BBOX['lon_min'], AB_SK_BBOX['lon_max']
    else:
        lat_min, lat_max = AB_SK_BBOX['lat_min'], AB_SK_BBOX['lat_max']
        lon_min, lon_max = AB_SK_BBOX['lon_min'], AB_SK_BBOX['lon_max']

    all_raw = []

    for sensor_name, db_file, table_name in SENSORS:
        if not os.path.isabs(db_file): db_file = os.path.join(BASE_DIR, db_file)
        if not os.path.exists(db_file): continue

        try:
            con = sqlite3.connect(db_file)
            cur = con.cursor()

            params = [lat_min, lat_max, lon_min, lon_max]
            since_clause = ""
            if since_param:
                since_clause = "AND acq_date >= ?"
                params.append(since_param[:10])  # compare date portion only

            cur.execute(f"""
                SELECT latitude, longitude, acq_date, acq_time, confidence
                FROM {table_name}
                WHERE latitude BETWEEN ? AND ?
                AND longitude BETWEEN ? AND ?
                {since_clause}
                ORDER BY acq_date DESC, acq_time DESC
                LIMIT 500
            """, params)

            for row in cur.fetchall():
                all_raw.append({
                    "latitude":         row[0],
                    "longitude":        row[1],
                    "acq_date":         row[2],
                    "acq_time":         row[3],
                    "confidence_level": normalize_confidence(row[4] or 'l'),
                    "datetime":         row[2],
                })
            con.close()
        except:
            continue

    return jsonify(all_raw)

@app.route('/api/fires')
def get_validated_fires():
    # 1. Capture the 'since' parameter
    since_param = request.args.get('since')
    
    try:
        con = sqlite3.connect(VALIDATED_DB)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        
        # 2. Build Query based on 'since'
        base_query = "SELECT * FROM validated_fires WHERE confidence_score >= 40"
        params = []
        
        if since_param:
            # Assumes 'datetime' column in DB is ISO format or comparable string
            base_query += " AND datetime >= ?"
            params.append(since_param)
            
        base_query += " ORDER BY confidence_score DESC"
        
        cur.execute(base_query, params)
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        return jsonify(rows)
    except Exception as e:
        print(f"Error fetching fires: {e}")
        return jsonify([])

@app.route('/api/run-pipeline', methods=['POST'])
def handle_run_pipeline():
    # 1. Extract bbox from request body
    data = request.json or {}
    bbox_str = data.get('bbox', None)
    
    # 2. Pass the bbox string to the pipeline
    Thread(target=run_pipeline, args=(bbox_str,)).start()
    
    msg = f"Pipeline started with BBOX: {bbox_str}" if bbox_str else "Pipeline started (Default Mode)"
    return jsonify({"message": msg}), 202

@app.route('/api/status')
def status():
    return jsonify({"status": "online"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"Starting Main API Server on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
