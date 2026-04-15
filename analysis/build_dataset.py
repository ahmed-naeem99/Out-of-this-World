"""
build_dataset.py
================
Builds a labeled training dataset for FireWatch weight optimization.

Pipeline:
  1. Ingest all FIRMS archive zips from ../analysis_data/
  2. Normalize confidence, tag sensor family
  3. Cluster detections (0.02° spatial grid, daily)
  4. Score each cluster using current algorithm weights
  5. Label clusters against NFDB fire perimeter polygons (spatial + temporal join)
  6. Fall back to NFDB point radius for any remaining unknowns
  7. Export labeled_dataset.csv

Run from project root:
  python3 analysis/build_dataset.py
"""

import os
import zipfile
import re
import math
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, box
from pyproj import Transformer
from datetime import timedelta
from scipy.spatial import cKDTree

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR  = os.path.join(ROOT, "analysis_data")
NFDB_POLY_ZIP = os.path.join(DATA_DIR, "NFDB_poly.zip")
NFDB_POINT_PATH = os.path.join(ROOT, "backend", "NFDB_point_20240613.txt")
OUT_CSV   = os.path.join(ROOT, "analysis", "labeled_dataset.csv")

# ── Algorithm constants (mirrors fire_alert_validator.py) ──────────────────
W_VIIRS   = 0.60
W_MODIS   = 0.20
W_LANDSAT = 0.05
MULTI_SENSOR_BONUS = 0.15
TRIPLE_PASS_BONUS  = 0.15
DUPLICATE_SCALE    = 0.20

# ── Bounding box (matches FIRMS download bbox) ─────────────────────────────
LAT_MIN, LAT_MAX = 49.0, 61.0
LON_MIN, LON_MAX = -120.0, -101.0
BBOX_GEOM = box(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)

# ── Fallback point-radius matching (for clusters not inside any polygon) ───
MATCH_RADIUS_KM   = 15.0
MATCH_DAYS_BEFORE = 1
MATCH_DAYS_AFTER  = 60

# ── CSV filename → sensor family ───────────────────────────────────────────
FILENAME_PATTERNS = [
    (r"fire_archive_M-C61",  "modis"),
    (r"fire_archive_SV-C2",  "viirs"),
    (r"fire_archive_J1V-C2", "viirs"),
    (r"fire_nrt_LS",         "landsat"),
]
ZIP_RE = re.compile(r"(modis|viirs_snpp|viirs_j1|landsat)_(\d{4})\.zip", re.IGNORECASE)


# ══════════════════════════════════════════════════════════════════════════
# STEP 1 — Ingest FIRMS archive zips
# ══════════════════════════════════════════════════════════════════════════

def get_input_score(conf_series):
    s = conf_series.astype(str).str.strip().str.lower()
    score = pd.Series(0.7, index=conf_series.index)
    numeric = pd.to_numeric(conf_series, errors="coerce")
    high_mask = s.isin(["h", "high"]) | (numeric >= 85)
    low_mask  = s.isin(["l", "low"])  | (numeric < 60)
    score[high_mask] = 1.0
    score[low_mask & ~high_mask] = 0.2
    return score


def detect_family(csv_name):
    for pattern, family in FILENAME_PATTERNS:
        if re.search(pattern, csv_name):
            return family
    return "unknown"


def load_firms_zips(data_dir):
    frames = []
    for zip_name in sorted(os.listdir(data_dir)):
        if not zip_name.endswith(".zip") or zip_name == "NFDB_poly.zip":
            continue
        m = ZIP_RE.match(zip_name)
        zip_year = int(m.group(2)) if m else 0

        zip_path = os.path.join(data_dir, zip_name)
        with zipfile.ZipFile(zip_path) as zf:
            csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
            if not csv_names:
                continue
            family = detect_family(csv_names[0])
            with zf.open(csv_names[0]) as f:
                df = pd.read_csv(f, low_memory=False)

        df.columns = [c.lower().strip() for c in df.columns]
        df = df[
            df["latitude"].between(LAT_MIN, LAT_MAX) &
            df["longitude"].between(LON_MIN, LON_MAX)
        ].copy()

        if df.empty:
            print(f"  [SKIP] {zip_name} — no rows in bbox")
            continue

        df["family"]      = family
        df["zip_year"]    = zip_year
        df["acq_date"]    = pd.to_datetime(df["acq_date"]).dt.strftime("%Y-%m-%d")
        df["input_score"] = get_input_score(df["confidence"])
        if "type" not in df.columns:
            df["type"] = 0

        frames.append(df[["latitude", "longitude", "acq_date", "input_score",
                           "family", "zip_year", "type"]])
        print(f"  {len(df):>8,} rows  ←  {zip_name}")

    combined = pd.concat(frames, ignore_index=True)
    print(f"\n  Total rows: {len(combined):,}\n")
    return combined


# ══════════════════════════════════════════════════════════════════════════
# STEP 2 — Cluster + Score
# ══════════════════════════════════════════════════════════════════════════

def build_clusters(df):
    df = df.copy()
    df["lat_rnd"] = df["latitude"].round(2)
    df["lon_rnd"]  = df["longitude"].round(2)
    grp_key = ["lat_rnd", "lon_rnd", "acq_date"]

    family_counts = (
        df.groupby(grp_key + ["family"]).size()
        .unstack(fill_value=0)
        .reindex(columns=["viirs", "modis", "landsat"], fill_value=0)
    )
    family_counts.columns = ["n_viirs", "n_modis", "n_landsat"]

    family_max = (
        df.groupby(grp_key + ["family"])["input_score"].max()
        .unstack(fill_value=0.0)
        .reindex(columns=["viirs", "modis", "landsat"], fill_value=0.0)
    )
    family_max.columns = ["viirs_max_score", "modis_max_score", "landsat_max_score"]

    n_type2 = df[df["type"] == 2].groupby(grp_key).size().rename("n_type2")

    clusters = family_counts.join(family_max).join(n_type2).fillna(0).reset_index()
    for col in ["n_type2", "n_viirs", "n_modis", "n_landsat"]:
        clusters[col] = clusters[col].astype(int)
    clusters["year"] = clusters["acq_date"].str[:4].astype(int)

    def score_row(r):
        total = 0.0
        seen  = set()
        for fam, w, n_col, s_col in [
            ("viirs",   W_VIIRS,   "n_viirs",   "viirs_max_score"),
            ("modis",   W_MODIS,   "n_modis",   "modis_max_score"),
            ("landsat", W_LANDSAT, "n_landsat", "landsat_max_score"),
        ]:
            n = r[n_col]
            if n == 0:
                continue
            s = r[s_col]
            total += w * s
            if n > 1:
                total += w * s * DUPLICATE_SCALE * (n - 1)
            seen.add(fam)
        if len(seen) >= 2:
            total += MULTI_SENSOR_BONUS
        if r["n_viirs"] > 2:
            total += TRIPLE_PASS_BONUS
        return min(total * 100, 100.0)

    print("  Scoring clusters...")
    clusters["score"] = clusters.apply(score_row, axis=1).round(2)
    clusters["n_families"] = (
        (clusters["n_viirs"] > 0).astype(int) +
        (clusters["n_modis"] > 0).astype(int) +
        (clusters["n_landsat"] > 0).astype(int)
    )

    print(f"  Built {len(clusters):,} clusters\n")
    return clusters


# ══════════════════════════════════════════════════════════════════════════
# STEP 3 — Load NFDB perimeter polygons
# ══════════════════════════════════════════════════════════════════════════

def load_nfdb_polygons(zip_path):
    """
    Load both shapefiles from NFDB_poly.zip, clip to bbox, return combined GeoDataFrame.
    Columns we keep: geometry, YEAR, REP_DATE, OUT_DATE, SIZE_HA, FIRE_ID
    """
    shp_files = [
        "NFDB_poly_1972to2020_20250630.shp",
        "NFDB_poly_2021to2024_20250630.shp",
    ]

    frames = []
    for shp_name in shp_files:
        print(f"  Reading {shp_name}...")
        path = f"zip://{zip_path}!{shp_name}"

        # Peek at CRS without loading data
        gdf_peek = gpd.read_file(path, rows=1)
        src_crs = gdf_peek.crs

        # Convert WGS84 bbox corners into the shapefile's native CRS
        transformer = Transformer.from_crs("EPSG:4326", src_crs, always_xy=True)
        x_min, y_min = transformer.transform(LON_MIN, LAT_MIN)
        x_max, y_max = transformer.transform(LON_MAX, LAT_MAX)
        native_bbox = (x_min, y_min, x_max, y_max)

        gdf = gpd.read_file(path, bbox=native_bbox)
        if gdf.empty:
            print(f"    → 0 polygons in bbox")
            continue

        # Reproject to WGS84
        gdf = gdf.to_crs(epsg=4326)

        # Normalise date columns
        for col in ["REP_DATE", "OUT_DATE"]:
            if col in gdf.columns:
                gdf[col] = pd.to_datetime(gdf[col], errors="coerce")

        # Use FIRE_ID as the fire identifier
        keep = [c for c in ["geometry", "YEAR", "REP_DATE", "OUT_DATE",
                             "SIZE_HA", "FIRE_ID"] if c in gdf.columns]
        frames.append(gdf[keep])
        print(f"    → {len(gdf):,} polygons in bbox")

    combined = pd.concat(frames, ignore_index=True)
    combined = gpd.GeoDataFrame(combined, geometry="geometry", crs="EPSG:4326")

    # Fill missing OUT_DATE with REP_DATE + 60 days
    if "OUT_DATE" in combined.columns:
        combined["OUT_DATE"] = combined["OUT_DATE"].fillna(
            combined["REP_DATE"] + timedelta(days=60)
        )
    else:
        combined["OUT_DATE"] = combined["REP_DATE"] + timedelta(days=60)

    print(f"\n  Total NFDB polygons in bbox: {len(combined):,}\n")
    return combined


# ══════════════════════════════════════════════════════════════════════════
# STEP 4a — Label via polygon containment (primary)
# ══════════════════════════════════════════════════════════════════════════

def label_by_polygons(clusters, nfdb_poly):
    """
    Spatial join: cluster point → NFDB polygon.
    A cluster is TP if its point falls inside a polygon whose active period
    overlaps the detection date.
    """
    cluster_gdf = gpd.GeoDataFrame(
        clusters.copy(),
        geometry=[Point(lon, lat) for lon, lat in zip(clusters["lon_rnd"], clusters["lat_rnd"])],
        crs="EPSG:4326"
    )

    print("  Running spatial join (point-in-polygon)...")
    joined = gpd.sjoin(cluster_gdf, nfdb_poly[["geometry", "REP_DATE", "OUT_DATE",
                                                "SIZE_HA", "FIRE_ID"]],
                       how="left", predicate="within")

    # Temporal filter: detection date must be within the fire's active period
    det_dates = pd.to_datetime(joined["acq_date"])
    fire_start = joined["REP_DATE"] - timedelta(days=MATCH_DAYS_BEFORE)
    fire_end   = joined["OUT_DATE"] + timedelta(days=1)
    in_period  = (det_dates >= fire_start) & (det_dates <= fire_end)

    # Keep only rows where temporal condition holds; if multiple matches, take first
    valid = joined[in_period & joined["FIRE_ID"].notna()].copy()
    valid = valid[~valid.index.duplicated(keep="first")]

    # Build result — start from original clusters index
    clusters = clusters.copy()
    clusters["label"]        = -1
    clusters["nfdb_id"]      = None
    clusters["nfdb_size_ha"] = np.nan
    clusters["match_method"] = "none"

    tp_idx = valid.index
    clusters.loc[tp_idx, "label"]        = 1
    clusters.loc[tp_idx, "nfdb_id"]      = valid["FIRE_ID"].values
    clusters.loc[tp_idx, "nfdb_size_ha"] = valid["SIZE_HA"].values
    clusters.loc[tp_idx, "match_method"] = "polygon"

    tp = (clusters["label"] == 1).sum()
    print(f"  Polygon TP matches: {tp:,}")
    return clusters


# ══════════════════════════════════════════════════════════════════════════
# STEP 4b — Fallback: point radius for remaining unknowns
# ══════════════════════════════════════════════════════════════════════════

def load_nfdb_points(path):
    df = pd.read_csv(path, low_memory=False)
    df.columns = [c.lower().strip() for c in df.columns]
    df = df[
        df["latitude"].between(LAT_MIN, LAT_MAX) &
        df["longitude"].between(LON_MIN, LON_MAX)
    ].copy()
    df["rep_date"]     = pd.to_datetime(df["rep_date"], errors="coerce")
    df["out_date"]     = pd.to_datetime(df["out_date"], errors="coerce")
    df["out_date_eff"] = df["out_date"].fillna(df["rep_date"] + timedelta(days=60))
    return df.dropna(subset=["rep_date"]).reset_index(drop=True)


def label_fallback_radius(clusters, nfdb_pts):
    """Apply point-radius matching only to clusters still labeled -1."""
    unknown_mask = clusters["label"] == -1
    unknown = clusters[unknown_mask].copy()
    if unknown.empty:
        return clusters

    nfdb_rad = np.radians(nfdb_pts[["latitude", "longitude"]].values)
    tree = cKDTree(nfdb_rad)
    radius_rad = MATCH_RADIUS_KM / 6371.0

    cluster_rad   = np.radians(unknown[["lat_rnd", "lon_rnd"]].values)
    cluster_dates = pd.to_datetime(unknown["acq_date"]).values

    nfdb_start = (nfdb_pts["rep_date"] - timedelta(days=MATCH_DAYS_BEFORE)).values
    nfdb_end   = (nfdb_pts["out_date_eff"] + timedelta(days=1)).values
    nfdb_ids   = nfdb_pts["nfdbfireid"].values
    nfdb_sizes = nfdb_pts["size_ha"].values
    nfdb_lat   = nfdb_pts["latitude"].values
    nfdb_lon   = nfdb_pts["longitude"].values

    candidates = tree.query_ball_point(cluster_rad, r=radius_rad)

    for i, (orig_idx, row) in enumerate(unknown.iterrows()):
        idxs = candidates[i]
        if not idxs:
            continue
        det_ts = cluster_dates[i]
        clat, clon = row["lat_rnd"], row["lon_rnd"]

        best_dist = np.inf
        best_j = -1
        for j in idxs:
            if not (nfdb_start[j] <= det_ts <= nfdb_end[j]):
                continue
            phi1, phi2 = math.radians(clat), math.radians(nfdb_lat[j])
            dphi = phi2 - phi1
            dlam = math.radians(nfdb_lon[j] - clon)
            a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
            d = 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            if d < best_dist:
                best_dist = d
                best_j = j

        if best_j >= 0:
            clusters.loc[orig_idx, "label"]        = 1
            clusters.loc[orig_idx, "nfdb_id"]      = nfdb_ids[best_j]
            clusters.loc[orig_idx, "nfdb_size_ha"] = nfdb_sizes[best_j]
            clusters.loc[orig_idx, "match_method"] = "point_radius"

    added = ((clusters["label"] == 1) & (clusters["match_method"] == "point_radius")).sum()
    print(f"  Point-radius TP matches: {added:,}")
    return clusters


def label_confirmed_fp(clusters):
    """Mark all-type2 clusters with no NFDB match as confirmed FP."""
    n_total = clusters["n_viirs"] + clusters["n_modis"] + clusters["n_landsat"]
    fp_mask = (
        (clusters["label"] == -1) &
        (clusters["n_type2"] > 0) &
        (clusters["n_type2"] == n_total)
    )
    clusters.loc[fp_mask, "label"] = 0
    clusters.loc[fp_mask, "match_method"] = "type2"
    print(f"  Confirmed FP (type=2): {fp_mask.sum():,}")
    return clusters


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("FireWatch — Training Dataset Builder")
    print("=" * 60)

    print("\n[1/5] Loading FIRMS archive data...")
    firms = load_firms_zips(DATA_DIR)

    print("[2/5] Clustering + scoring detections...")
    clusters = build_clusters(firms)

    print("[3/5] Loading NFDB fire perimeter polygons...")
    nfdb_poly = load_nfdb_polygons(NFDB_POLY_ZIP)

    print("[4/5] Labeling clusters...")
    clusters = label_by_polygons(clusters, nfdb_poly)

    print("  Loading NFDB point data for fallback radius matching...")
    nfdb_pts = load_nfdb_points(NFDB_POINT_PATH)
    clusters = label_fallback_radius(clusters, nfdb_pts)
    clusters = label_confirmed_fp(clusters)

    tp  = (clusters["label"] == 1).sum()
    fp  = (clusters["label"] == 0).sum()
    unk = (clusters["label"] == -1).sum()
    print(f"\n  Final — TP: {tp:,}  |  FP: {fp:,}  |  Unknown: {unk:,}")

    print("\n[5/5] Saving...")
    clusters.to_csv(OUT_CSV, index=False)
    print(f"  Saved → {OUT_CSV}")
    print(f"\nDone. {len(clusters):,} clusters total.")


if __name__ == "__main__":
    main()
