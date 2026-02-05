import pandas as pd
import os
import sys

# --- CONFIGURATION ---
INPUT_FILENAME = "backend/NFDB_point_20240613.txt"  # Matches your file exactly
OUTPUT_FILENAME = "validation_layer_aug2025.csv"
TARGET_START = '2025-08-10'
TARGET_END = '2025-08-17'

print(f"--- PROCESSING {INPUT_FILENAME} ---")

if not os.path.exists(INPUT_FILENAME):
    print(f"ERROR: File not found in {os.getcwd()}")
    sys.exit(1)

# 1. READ DATA
print("Reading file... (This may take a moment)")
try:
    df = pd.read_csv(INPUT_FILENAME, sep=',', encoding='ISO-8859-1', low_memory=False)
except:
    print("Comma read failed. Trying tab-separated...")
    df = pd.read_csv(INPUT_FILENAME, sep='\t', encoding='ISO-8859-1', low_memory=False)

# Normalize Columns
df.columns = [c.upper().strip() for c in df.columns]

# 2. LOCATE DATE COLUMN
possible_cols = ['REP_DATE', 'STARTDATE', 'SRC_AGENCY_DATE', 'DATE']
date_col = next((col for col in possible_cols if col in df.columns), None)

if not date_col:
    print(f"CRITICAL ERROR: No date column found. Columns: {list(df.columns)}")
    sys.exit(1)

print(f"Using date column: {date_col}")
df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

# 3. ANALYZE FILE AGE
max_date = df[date_col].max()
print(f"\n--- DATA ANALYSIS ---")
print(f"Oldest Fire in file: {df[date_col].min().date()}")
print(f"Newest Fire in file: {max_date.date()}")
print(f"Target Window:       {TARGET_START} to {TARGET_END}")

if max_date < pd.to_datetime(TARGET_START):
    print("\n⚠️  WARNING: FILE IS TOO OLD ⚠️")
    print(f"This file only contains data up to {max_date.date()}.")
    print(f"It does NOT contain the August 2025 data you are looking for.")
    print("Government databases often lag by 1-2 years.")
else:
    # 4. FILTER (Only runs if data actually exists)
    mask = (df[date_col] >= TARGET_START) & (df[date_col] <= TARGET_END)
    df_subset = df.loc[mask]

    if df_subset.empty:
        print(f"\nResult: 0 fires found for the target week.")
    else:
        df_subset.to_csv(OUTPUT_FILENAME, index=False)
        print(f"\nSUCCESS: Extracted {len(df_subset)} fires.")
        print(f"Saved to {OUTPUT_FILENAME}")