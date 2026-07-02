"""PLATEAU zip から 指定メッシュコードの bldg gml だけ抽出する。

Usage:
    python scripts/extract_mesh.py <zip_path> <lat> <lng> <radius_steps> <out_dir>
    例: python scripts/extract_mesh.py data/plateau/27100_osaka-shi_city_2025_citygml_1_op.zip 34.7235 135.4925 5 data/plateau/extracted
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

from mesh_utils import latlng_to_mesh3, mesh3_neighbors


def main():
    if len(sys.argv) < 6:
        print("Usage: python extract_mesh.py <zip> <lat> <lng> <radius_steps> <out_dir>")
        sys.exit(1)
    zip_path = Path(sys.argv[1])
    lat = float(sys.argv[2])
    lng = float(sys.argv[3])
    radius = int(sys.argv[4])
    out_dir = Path(sys.argv[5])
    out_dir.mkdir(parents=True, exist_ok=True)

    center = latlng_to_mesh3(lat, lng)
    target_codes = set(mesh3_neighbors(center, radius_steps=radius))
    print(f"center mesh: {center}")
    print(f"target meshes: {len(target_codes)}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        bldg_entries = [
            e for e in zf.namelist()
            if "bldg" in e and e.endswith(".gml")
        ]
        extracted = 0
        total_size = 0
        for ent in bldg_entries:
            fname = Path(ent).name
            code = fname.split("_")[0]
            if code in target_codes:
                # フラットに展開
                out_path = out_dir / fname
                with zf.open(ent) as src, open(out_path, "wb") as dst:
                    data = src.read()
                    dst.write(data)
                    total_size += len(data)
                extracted += 1
        print(f"extracted: {extracted} files / {total_size/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
