from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
from fire_alert_validator import validate_fires

app = Flask(__name__)
CORS(app)

PRIMARY = ("viirs.db", "viirs_noaa20")
SECONDARY = [
    ("modis.db",   "modis_data"),
    ("viirs.db",   "viirs_snpp"),
    ("viirs.db",   "viirs_noaa21"),
    ("goes.db",    "goes_data")
]

@app.route('/api/fires')
def get_validated_fires():
    since_str = request.args.get('since')
    since = None

    if since_str:
        try:
            since = datetime.fromisoformat(since_str)
        except ValueError:
            return jsonify({"error": "Invalid 'since' datetime format. Use ISO format like 2025-07-15T00:00"}), 400

    fires = validate_fires(PRIMARY[0], PRIMARY[1], SECONDARY, since)
    clean = [
        {
            'latitude': fire['latitude'],
            'longitude': fire['longitude'],
            'confidence_level': fire['confidence_level'],
            'datetime': fire['datetime'].isoformat()
        } for fire in fires
    ]
    return jsonify(clean)

if __name__ == '__main__':
    validate_fires(PRIMARY[0], PRIMARY[1], SECONDARY)
    app.run(debug=True)
