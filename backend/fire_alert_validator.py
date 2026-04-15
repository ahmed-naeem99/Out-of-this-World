import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta

# Centralize path logic
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Standardize DB paths
VALIDATED_DB = os.path.join(BASE_DIR, "validated_fires.db")

# === DEFAULT FALLBACK BOUNDS (AB/SK) ===
AB_SK_BBOX = {
    'lat_min': 49.0,
    'lat_max': 60.0,
    'lon_min': -120.0, 
    'lon_max': -110.0   
}

# --- SCORING WEIGHTS ---
# Empirically optimized against NFDB ground truth (2015-2023, AB/SK)
# Previous: viirs=0.60, modis=0.20, landsat=0.05
# Optimization improved Alert tier recall from 55% → 88% at P≥95%
SENSOR_WEIGHTS = { 'viirs': 0.90, 'modis': 0.10, 'goes': 0.15, 'landsat': 0.10 }
SENSOR_WEIGHTS_MODIS_PRIMARY = { 'modis': 0.70, 'goes': 0.20, 'landsat': 0.10, 'viirs': 0.00 }

# --- STATIC HOTSPOTS ---
STATIC_HOTSPOTS = [
    (57.0, -111.4, "Athabasca Oil Sands - Fort McMurray"),
    (56.970647, -111.473869, "Suncor Base Plant"),
    (57.048918, -111.583240, "Syncrude Mildred Lake"),
    (53.5, -113.5, "Edmonton Refinery District"),
    (51.0, -114.0, "Calgary Industrial Zone"),
    (53.6, -110.2, "Coal-Fired Power Plant - Wabamun"),
    (49.7, -112.8, "Natural Gas Plant - Lethbridge"),
    (50.7911, -116.5852, "Mountanious Region"),
]

def check_static_veto(lat, lon):
    for h_lat, h_lon, name in STATIC_HOTSPOTS:
        if abs(lat - h_lat) < 0.1 and abs(lon - h_lon) < 0.1:
            return True
    return False

def get_input_score(conf_val):
    s = str(conf_val).lower()
    if 'h' in s or 'high' in s: return 1.0
    if 'l' in s or 'low' in s: return 0.2
    try:
        val = int(float(conf_val))
        if val >= 85: return 1.0
        elif val < 60: return 0.2
    except: pass
    return 0.7

def combine_datetime(acq_date, acq_time):
    time_str = str(int(float(acq_time))).zfill(4)
    return datetime.strptime(f"{acq_date} {time_str}", "%Y-%m-%d %H%M")

def load_detections(db, table, bbox):
    if not os.path.isabs(db): db = os.path.join(BASE_DIR, db)
    con = sqlite3.connect(db)
    
    # USE THE PASSED BBOX, NOT THE HARDCODED ONE
    query = f"""SELECT * FROM {table} 
                WHERE latitude BETWEEN {bbox['lat_min']} AND {bbox['lat_max']}
                AND longitude BETWEEN {bbox['lon_min']} AND {bbox['lon_max']}
                ORDER BY acq_date DESC LIMIT 50000"""
    try:
        df = pd.read_sql_query(query, con)
    except:
        return pd.DataFrame()
    finally:
        con.close()
    
    if not df.empty:
        df['datetime'] = df.apply(lambda r: combine_datetime(r['acq_date'], r['acq_time']), axis=1)
    return df

def initialize_validated_db():
    con = sqlite3.connect(VALIDATED_DB)
    con.execute('''CREATE TABLE IF NOT EXISTS validated_fires (
            latitude REAL, longitude REAL, acq_date TEXT, acq_time TEXT,
            confidence_level INTEGER, confidence_score REAL,
            primary_sensor TEXT, validating_sensors TEXT,
            datetime TEXT, raw_primary_confidence TEXT,
            PRIMARY KEY (latitude, longitude, acq_date, acq_time))''')
    
    cur = con.cursor()
    cur.execute("PRAGMA table_info(validated_fires)")
    cols = [c[1] for c in cur.fetchall()]
    if 'raw_primary_confidence' not in cols:
        cur.execute("ALTER TABLE validated_fires ADD COLUMN raw_primary_confidence TEXT")
    con.commit()
    con.close()

def validate_fires_all_sources(all_sources, bbox=None):
    if bbox is None:
        bbox = AB_SK_BBOX # Safety fallback
        
    print(f"--- UNIFIED VALIDATION ---")
    print(f"  Region: {bbox['lat_min']} to {bbox['lat_max']} Lat, {bbox['lon_min']} to {bbox['lon_max']} Lon")
    
    all_dfs = []
    has_viirs = False
    
    for db, table in all_sources:
        # Pass the dynamic BBOX to the loader
        df = load_detections(db, table, bbox)
        if not df.empty:
            df['source_table'] = table
            if 'viirs' in table: 
                df['family'] = 'viirs'; has_viirs = True
            elif 'modis' in table: df['family'] = 'modis'
            elif 'landsat' in table: df['family'] = 'landsat'
            else: df['family'] = 'goes'
            all_dfs.append(df)
            print(f"  -> Loaded {len(df)} from {table}")

    if not all_dfs:
        print("  ! No data found in this region.")
        # We must clear the DB if no fires found, otherwise old fires persist
        con = sqlite3.connect(VALIDATED_DB)
        con.execute("DELETE FROM validated_fires")
        con.commit()
        con.close()
        return []

    combined = pd.concat(all_dfs, ignore_index=True)
    weights = SENSOR_WEIGHTS if has_viirs else SENSOR_WEIGHTS_MODIS_PRIMARY

    print(f"  Processing {len(combined)} fires...")
    
    combined['lat_rnd'] = combined['latitude'].round(2)
    combined['lon_rnd'] = combined['longitude'].round(2)
    combined['date_str'] = combined['datetime'].dt.date.astype(str)

    combined['sort_score'] = combined['confidence'].apply(get_input_score)
    combined = combined.sort_values('sort_score', ascending=False)

    validated_rows = []
    grouped = combined.groupby(['lat_rnd', 'lon_rnd', 'date_str'])

    for _, group in grouped:
        primary = group.iloc[0]
        
        total_score = 0
        seen_families = set()
        cluster_sources = []

        for _, row in group.iterrows():
            fam = row['family']
            conf = str(row['confidence'])
            score = weights.get(fam, 0.1) * get_input_score(conf)
            cluster_sources.append(f"{row['source_table']}({conf})")
            if fam not in seen_families:
                total_score += score
                seen_families.add(fam)
            else:
                total_score += (score * 0.2)

        if len(seen_families) >= 2: total_score += 0.15
        if 'viirs' in seen_families and len(group) > 2: total_score += 0.15

        final_score = min(total_score * 100, 100.0)
        
        if check_static_veto(primary['latitude'], primary['longitude']):
            final_score = 10.0

        if final_score >= 85: level = 3
        elif final_score >= 60: level = 2
        elif final_score >= 40: level = 1
        else: continue 

        validated_rows.append((
            primary['latitude'], primary['longitude'], 
            primary['acq_date'], primary['acq_time'],
            level, round(final_score, 1),
            primary['source_table'], ", ".join(cluster_sources[:5]),
            primary['datetime'].isoformat(), str(primary['confidence'])
        ))

    con = sqlite3.connect(VALIDATED_DB)
    con.execute("DELETE FROM validated_fires") 
    if validated_rows:
        con.executemany("""
            INSERT OR REPLACE INTO validated_fires 
            (latitude, longitude, acq_date, acq_time, confidence_level, confidence_score, 
             primary_sensor, validating_sensors, datetime, raw_primary_confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, validated_rows)
        print(f"  ✓ DONE. Saved {len(validated_rows)} validated fires.")
    else:
        print("  ✓ DONE. No validated fires in this region.")
        
    con.commit()
    con.close()
    
    return validated_rows