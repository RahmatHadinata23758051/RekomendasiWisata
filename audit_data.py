#!/usr/bin/env python3
"""Audit data integrity: coordinates, regency consistency, duplicates, dead images."""
import json
import glob
import pandas as pd
import os

# 1. Audit recommender_ready_features.csv
df = pd.read_csv('Data/consolidated/recommender_ready_features.csv')
print("=== recommender_ready_features.csv ===")
print(f"Total rows: {len(df)}")
print(f"Missing latitude: {df['latitude'].isna().sum()}")
print(f"Missing longitude: {df['longitude'].isna().sum()}")

# Check if all coords are within Lampung bounds
lampung_lat_min, lampung_lat_max = -6.5, -3.5
lampung_lng_min, lampung_lng_max = 103.0, 106.5
out_of_bounds = df[
    (df['latitude'] < lampung_lat_min) | (df['latitude'] > lampung_lat_max) |
    (df['longitude'] < lampung_lng_min) | (df['longitude'] > lampung_lng_max)
]
print(f"Coordinates outside Lampung bounds: {len(out_of_bounds)}")
if len(out_of_bounds) > 0:
    print(out_of_bounds[['canonical_id', 'name', 'city_or_regency', 'latitude', 'longitude']].to_string())

# Duplicate coordinates
dups = df[df.duplicated(subset=['latitude', 'longitude'], keep=False)]
groups = dups.groupby(['latitude', 'longitude']).size().reset_index(name='count')
print(f"Exact duplicate coordinate groups: {len(groups)}")
print(f"Max overlap in single coord: {groups['count'].max()}")

# 2. Audit JSON source files for city vs address consistency
files = glob.glob('Data/*.json')
all_regencies = set()
mismatches = []
for f in files:
    with open(f, 'r', encoding='utf-8') as fp:
        raw = json.load(fp)
    # Handle both list and dict formats
    if isinstance(raw, dict):
        # INPUT.json may have nested structure
        data = []
        for v in raw.values():
            if isinstance(v, list):
                data.extend(v)
            elif isinstance(v, dict):
                data.append(v)
    else:
        data = raw
    for item in data:
        if not isinstance(item, dict):
            continue
        addr = item.get('address', '') or ''
        city = item.get('city', '') or ''
        if city:
            all_regencies.add(city)
        if 'Kabupaten' in city or 'Kota' in city:
            if city not in addr:
                mismatches.append((item.get('title', '?'), city, addr))

print(f"\nUnique regencies in JSON files: {len(all_regencies)}")
print(sorted(all_regencies))
print(f"\nCity/Regency not found in address field: {len(mismatches)}")
for t, c, a in mismatches[:30]:
    print(f"  - {t}: city='{c}', addr='{a[:80]}...'")

# 3. Cross-check city_or_regency in CSV vs JSON city field
csv_regencies = set(df['city_or_regency'].unique())
json_regencies = set(all_regencies)
print(f"\nRegencies in CSV not in JSON: {csv_regencies - json_regencies}")
print(f"Regencies in JSON not in CSV: {json_regencies - csv_regencies}")

# 4. Check image_url availability in master parquet
if os.path.exists('Data/consolidated/attractions_enrichment_master_full.parquet'):
    master = pd.read_parquet('Data/consolidated/attractions_enrichment_master_full.parquet')
    print(f"\n=== attractions_enrichment_master_full.parquet ===")
    print(f"Total rows: {len(master)}")
    if 'image_url' in master.columns:
        missing_img = master['image_url'].isna().sum()
        empty_img = (master['image_url'] == '').sum()
        print(f"Missing image_url: {missing_img}")
        print(f"Empty image_url: {empty_img}")
        valid_img = master[master['image_url'].notna() & (master['image_url'] != '')]
        print(f"Valid image_url: {len(valid_img)}")
    else:
        print("No image_url column")

print("\n=== Audit Complete ===")