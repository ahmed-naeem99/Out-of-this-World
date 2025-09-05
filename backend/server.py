from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
import sqlite3

app = Flask(__name__)
CORS(app)

# Path to the database created by the pipeline
VALIDATED_DB = "validated_fires.db"

@app.route('/')
def home():
    return jsonify({
        "message": "Fire Detection API Server",
        "endpoints": {
            "/api/fires": "Get validated fire data",
            "/api/status": "Check server status"
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
    since = datetime.now(timezone.utc) - timedelta(days=1)

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

""" if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='127.0.0.1', port=5000) """