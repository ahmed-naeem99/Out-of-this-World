# server.py
from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd

app = Flask(__name__)
CORS(app)

@app.route('/api/fires')
def get_validated_fires():
    df = pd.read_csv('validated_fires.csv')  
    fires = df[['latitude', 'longitude', 'confidence_level']].dropna().to_dict(orient='records')
    return jsonify(fires)

if __name__ == '__main__':
    app.run(debug=True)
