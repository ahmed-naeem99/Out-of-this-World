import sqlite3
import pandas as pd
import os
from geopy.distance import geodesic
from datetime import datetime, timedelta

# Centralize path logic
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Standardize DB paths
VALIDATED_DB = os.path.join(BASE_DIR, "validated_fires.db")
VIIRS_DB = os.path.join(BASE_DIR, "viirs.db")
MODIS_DB = os.path.join(BASE_DIR, "modis.db")
LANDSAT_DB = os.path.join(BASE_DIR, "landsat.db")
GOES_DB = os.path.join(BASE_DIR, "goes.db")

# === ALBERTA & SASKATCHEWAN BOUNDING BOX ===
# Alberta: ~49°N to 60°N, ~110°W to 120°W
# Saskatchewan: ~49°N to 60°N, ~101.5°W to 110°W
AB_SK_BBOX = {
    'lat_min': 49.0,
    'lat_max': 60.0,
    'lon_min': -120.0,  # Western edge of Alberta
    'lon_max': -101.5   # Eastern edge of Saskatchewan
}

# --- FIREWATCH SCORING LOGIC (ADJUSTED FOR MODIS-ONLY REGIONS) ---
SENSOR_WEIGHTS = {
    'viirs':   0.60,
    'modis':   0.20,
    'goes':    0.15,
    'landsat': 0.05
}

# NEW: Adjusted weights when VIIRS data is unavailable
SENSOR_WEIGHTS_MODIS_PRIMARY = {
    'modis':   0.70,  # Boost MODIS when it's the only primary sensor
    'goes':    0.20,
    'landsat': 0.10,
    'viirs':   0.00   # Not available in this region
}

MATCH_THRESHOLDS = {
    'viirs':   {'time': 360,   'dist': 5.0},
    'modis':   {'time': 180,   'dist': 3.0},
    'landsat': {'time': 4320,  'dist': 1.0},
    'goes':    {'time': 30,    'dist': 10.0} 
}

STATIC_HOTSPOTS = [
    # --- OIL & GAS (High Profile) ---
    (57.0, -111.4, "Athabasca Oil Sands - Fort McMurray"),
    (56.7, -111.3, "Suncor Base Plant"),
    (57.1, -111.5, "Syncrude Mildred Lake"),
    
    # --- INDUSTRIAL (Dramatic Vetoes) ---
    (53.5, -113.5, "Edmonton Refinery District"),
    (51.0, -114.0, "Calgary Industrial Zone"),
    
    # --- POWER GENERATION ---
    (53.6, -110.2, "Coal-Fired Power Plant - Wabamun"),
    (49.7, -112.8, "Natural Gas Plant - Lethbridge"),
    
    # --- AGRICULTURAL (Proves Sophistication) ---
    (52.1, -106.6, "Controlled Burn Area - Saskatoon Region"),
    (50.4, -104.6, "Agricultural Waste Burn - Regina"),
]

# Add to fire_alert_validator.py
KNOWN_WATER_BODIES = [
    # Lake Athabasca
    {'lat_min': 58.5, 'lat_max': 59.5, 'lon_min': -110.5, 'lon_max': -108.5},
    # Lake Claire
    {'lat_min': 58.5, 'lat_max': 59.0, 'lon_min': -112.5, 'lon_max': -111.5},
]

def check_sun_glint_veto(lat, lon, confidence):
    """Veto low-confidence fires over water (sun glint)"""
    if confidence.lower() != 'l':  # Only veto LOW confidence
        return False
    
    for water in KNOWN_WATER_BODIES:
        if (water['lat_min'] <= lat <= water['lat_max'] and
            water['lon_min'] <= lon <= water['lon_max']):
            return True
    return False

# In validation loop (after line 275):
is_vetoed = check_sun_glint_veto()

def check_static_veto(lat, lon):
    for hotspot in STATIC_HOTSPOTS:
        h_lat, h_lon, _ = hotspot
        try:
            distance = geodesic((lat, lon), (h_lat, h_lon)).km
            if distance <= 1.0: return True
        except:
            continue
    return False

def is_in_ab_sk(lat, lon):
    """Check if coordinates are within Alberta/Saskatchewan"""
    return (AB_SK_BBOX['lat_min'] <= lat <= AB_SK_BBOX['lat_max'] and
            AB_SK_BBOX['lon_min'] <= lon <= AB_SK_BBOX['lon_max'])

def get_input_score(conf_val):
    try:
        val = int(float(conf_val))
        if val >= 85: return 1.0
        elif val < 60: return 0.2
        else: return 0.7
    except (ValueError, TypeError):
        pass
    
    conf_str = str(conf_val).lower()
    if 'h' in conf_str or 'high' in conf_str: return 1.0
    if 'l' in conf_str or 'low' in conf_str: return 0.2
    return 0.7

def combine_datetime(acq_date, acq_time):
    if isinstance(acq_time, (int, float)):
        time_str = str(int(acq_time)).zfill(4)
    else:
        time_str = str(acq_time).zfill(4)
    try:
        return datetime.strptime(f"{acq_date} {time_str}", "%Y-%m-%d %H%M")
    except ValueError:
        return datetime.strptime(f"{acq_date} 0000", "%Y-%m-%d %H%M")

def load_detections(db, table, bbox=None):
    """Load fire detections with AB/SK filtering"""
    if not os.path.isabs(db): 
        db = os.path.join(BASE_DIR, db)
    
    con = sqlite3.connect(db)
    
    # ALWAYS apply AB/SK filter
    query = f"""SELECT * FROM {table} 
                WHERE latitude >= {AB_SK_BBOX['lat_min']} 
                AND latitude <= {AB_SK_BBOX['lat_max']}
                AND longitude >= {AB_SK_BBOX['lon_min']}
                AND longitude <= {AB_SK_BBOX['lon_max']}"""
    
    # Add user-provided BBOX if exists (further restriction)
    if bbox and str(bbox).lower() != 'nan' and bbox.strip():
        try:
            coords = [float(x.strip()) for x in bbox.split(',')]
            if len(coords) == 4:
                lon_min, lat_min, lon_max, lat_max = coords
                query += f" AND latitude >= {lat_min} AND latitude <= {lat_max}"
                query += f" AND longitude >= {lon_min} AND longitude <= {lon_max}"
        except:
            pass
    
    query += " LIMIT 1000"  # Increased limit for AB/SK region

    try:
        df = pd.read_sql_query(query, con)
    except Exception as e:
        print(f"  Error reading {table}: {e}")
        con.close()
        return pd.DataFrame()
        
    con.close()
    
    if not df.empty:
        df['datetime'] = df.apply(lambda r: combine_datetime(r['acq_date'], r['acq_time']), axis=1)
    
    return df

def initialize_validated_db():
    con = sqlite3.connect(VALIDATED_DB)
    cur = con.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS validated_fires (
            latitude REAL,
            longitude REAL,
            acq_date TEXT,
            acq_time TEXT,
            confidence_level INTEGER,
            confidence_score REAL,
            primary_sensor TEXT,
            validating_sensors TEXT,
            datetime TEXT,
            raw_primary_confidence TEXT,
            PRIMARY KEY (latitude, longitude, acq_date, acq_time, primary_sensor)
        )
    ''')
    cur.execute("PRAGMA table_info(validated_fires)")
    cols = [c[1] for c in cur.fetchall()]
    if 'raw_primary_confidence' not in cols:
        cur.execute("ALTER TABLE validated_fires ADD COLUMN raw_primary_confidence TEXT")
    con.commit()
    con.close()

def validate_fires_all_sources(all_sources, bbox=None):
    """
    Unified validation with AB/SK filtering and MODIS-only scoring adjustment
    """
    
    print(f"\n--- UNIFIED VALIDATION (AB/SK ONLY) ---")
    print(f"   Target Area: Alberta & Saskatchewan")
    print(f"   Lat: {AB_SK_BBOX['lat_min']} to {AB_SK_BBOX['lat_max']}")
    print(f"   Lon: {AB_SK_BBOX['lon_min']} to {AB_SK_BBOX['lon_max']}")
    
    # Step 1: Load all data from all sources
    all_fires = []
    has_viirs = False
    
    for db, table in all_sources:
        df = load_detections(db, table, bbox=bbox)
        if not df.empty:
            df['source_db'] = db
            df['source_table'] = table
            
            # Determine family
            if 'viirs' in table: 
                df['family'] = 'viirs'
                has_viirs = True
            elif 'modis' in table: df['family'] = 'modis'
            elif 'landsat' in table: df['family'] = 'landsat'
            elif 'goes' in table: df['family'] = 'goes'
            else: df['family'] = 'viirs'
            
            all_fires.append(df)
            print(f"  ✓ Loaded {len(df)} fires from {table}")
    
    if not all_fires:
        print("  ⚠ No fire data found in AB/SK region")
        return []
    
    # Detect if we're in a MODIS-only scenario
    if not has_viirs:
        print("  ⚠ WARNING: No VIIRS data available - using MODIS-adjusted scoring")
        weights_to_use = SENSOR_WEIGHTS_MODIS_PRIMARY
    else:
        print("  ✓ VIIRS data available - using standard scoring")
        weights_to_use = SENSOR_WEIGHTS
    
    # Step 2: Combine all fires
    combined_df = pd.concat(all_fires, ignore_index=True)
    print(f"  Total raw detections in AB/SK: {len(combined_df)}")
    
    # Step 3: DEDUPLICATE (OPTIMIZED)
    print(f"  Deduplicating {len(combined_df)} fires...")

    # Sort by date/time first to reduce comparisons
    combined_df = combined_df.sort_values('datetime').reset_index(drop=True)

    deduplicated_fires = []
    used_indices = set()

    for idx, fire in combined_df.iterrows():
        if idx in used_indices:
            continue
        
        # OPTIMIZATION: Only check nearby fires (within 24 hours)
        time_window = timedelta(hours=24)
        nearby_mask = (
            (combined_df['datetime'] >= fire['datetime'] - time_window) &
            (combined_df['datetime'] <= fire['datetime'] + time_window)
        )
        nearby_df = combined_df[nearby_mask]
        
        cluster = [fire]
        used_indices.add(idx)

        for idx2, fire2 in nearby_df.iterrows():
            if idx2 in used_indices or idx == idx2:
                continue
            
            try:
                dist = geodesic(
                    (float(fire['latitude']), float(fire['longitude'])),
                    (float(fire2['latitude']), float(fire2['longitude']))
                ).km
                
                time_diff = abs((fire['datetime'] - fire2['datetime']).total_seconds() / 60)
                
                if dist <= 1.0 and time_diff <= 30:
                    cluster.append(fire2)
                    used_indices.add(idx2)
            except:
                continue
        
        # Select best fire from cluster
        cluster_df = pd.DataFrame(cluster)
        cluster_df['input_score'] = cluster_df['confidence'].apply(get_input_score)
        best_fire = cluster_df.sort_values('input_score', ascending=False).iloc[0]
        
        best_fire = best_fire.copy()
        best_fire['cluster_sources'] = [f"{f['source_table']}({f['confidence']})" for f in cluster]
        best_fire['cluster_size'] = len(cluster)
        
        deduplicated_fires.append(best_fire)

    print(f"  After deduplication: {len(deduplicated_fires)} unique fires")
    
    # Step 4: Validate each unique fire
    validated = []
    
    for idx, fire in enumerate(deduplicated_fires):
        if idx > 0 and idx % 50 == 0:
            print(f"     Validated {idx}/{len(deduplicated_fires)} fires...")
        
        # Check AB/SK boundary (should always pass due to query filter)
        if not is_in_ab_sk(fire['latitude'], fire['longitude']):
            continue
        
        # Check static hotspot veto
        is_vetoed = check_static_veto(fire['latitude'], fire['longitude'])
        
        # Calculate score from cluster
        primary_family = fire['family']
        primary_table = fire['source_table']
        
        prim_input = get_input_score(fire['confidence'])
        prim_weight = weights_to_use.get(primary_family, 0.6)
        base_score = prim_weight * prim_input
        
        family_scores = {primary_family: base_score}
        viirs_times = set()
        if primary_family == 'viirs':
            viirs_times.add(fire['acq_time'])
        
        # Add cluster contributions
        for source_str in fire.get('cluster_sources', []):
            if '(' not in source_str:
                continue
            table_name, conf = source_str.split('(')
            conf = conf.rstrip(')')
            
            if 'viirs' in table_name: fam = 'viirs'
            elif 'modis' in table_name: fam = 'modis'
            elif 'landsat' in table_name: fam = 'landsat'
            elif 'goes' in table_name: fam = 'goes'
            else: continue
            
            sc = weights_to_use.get(fam, 0) * get_input_score(conf)
            
            if fam not in family_scores or sc > family_scores[fam]:
                family_scores[fam] = sc
            
            if fam == 'viirs':
                viirs_times.add(fire['acq_time'])
        
        total_score = sum(family_scores.values())
        
        # Bonus Logic (only if VIIRS available)
        if has_viirs:
            viirs_count = len(viirs_times)
            if viirs_count >= 3:
                total_score += 0.25
            elif viirs_count == 2:
                total_score += 0.10
        else:
            # MODIS-only bonus: Multiple MODIS detections
            modis_count = len([s for s in fire.get('cluster_sources', []) if 'modis' in s])
            if modis_count >= 2:
                total_score += 0.15  # Smaller bonus for MODIS clustering
        
        confidence_score = min(total_score * 100, 100.0)
        
        # Apply veto
        if is_vetoed:
            confidence_score = 10.0
        
        confidence_score = round(confidence_score, 1)
        
        # Tier Assignment
        if confidence_score >= 85:
            confidence_level = 4
        elif confidence_score >= 60:
            confidence_level = 3
        elif confidence_score >= 40:
            confidence_level = 2
        else:
            confidence_level = 1
        
        validating_sensors_str = ", ".join(fire.get('cluster_sources', []))
        
        validated.append({
            'latitude': fire['latitude'],
            'longitude': fire['longitude'],
            'acq_date': fire['acq_date'],
            'acq_time': str(fire['acq_time']),
            'confidence_level': confidence_level,
            'confidence_score': confidence_score,
            'primary_sensor': primary_table,
            'validating_sensors': validating_sensors_str,
            'datetime': fire['datetime'].isoformat(),
            'raw_primary_confidence': str(fire['confidence']).strip()
        })
    
    # Step 5: Save to database
    if validated:
        con = sqlite3.connect(VALIDATED_DB)
        cur = con.cursor()
        
        for v in validated:
            cur.execute("""
                INSERT OR REPLACE INTO validated_fires 
                (latitude, longitude, acq_date, acq_time, confidence_level, confidence_score, 
                 primary_sensor, validating_sensors, datetime, raw_primary_confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                v['latitude'], v['longitude'], v['acq_date'], v['acq_time'],
                v['confidence_level'], v['confidence_score'], v['primary_sensor'],
                v['validating_sensors'], v['datetime'], v['raw_primary_confidence']
            ))
        
        con.commit()
        con.close()
        print(f"  ✓ Saved {len(validated)} validated fires in AB/SK")
    
    return validated