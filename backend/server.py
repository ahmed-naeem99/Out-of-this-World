from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
import sqlite3

app = Flask(__name__)
CORS(app)

# Path to the database created by the pipeline
VALIDATED_DB = "validated_fires.db"

@app.route('/api/fires')
def get_validated_fires():
    since_str = request.args.get('since')
    # Default: last 24 hours
    since = datetime.now(timezone.utc) - timedelta(days=1)

    if since_str:
        try:
            since = datetime.fromisoformat(since_str)
        except ValueError:
            return jsonify({
                "error": "Invalid 'since' datetime format. Use ISO format like 2025-07-15T00:00"
            }), 400

    # Connect to validated_fires.db
    con = sqlite3.connect(VALIDATED_DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT latitude, longitude, acq_date, acq_time, confidence_level,
               primary_sensor, validating_sensors, datetime
        FROM validated_fires
        WHERE datetime >= ?
    """, (since.isoformat(),))

    rows = [dict(row) for row in cur.fetchall()]
    con.close()

    return jsonify(rows)

if __name__ == '__main__':
    print("Starting server...")
    app.run(debug=True, use_reloader=False)
