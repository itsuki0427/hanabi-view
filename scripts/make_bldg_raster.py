"""大会ごとの建物高さラスタPNG生成（断面図のクライアント描画用）。

- buildings_f<id>.geojson を 50mメッシュでサンプリング → 高さ(m)をピクセル値に
- グレースケールPNG（0-255 = 0-255m、超過はcap）
- ジオリファレンスは同名 .json（bbox）に保存

実行:
    python scripts/make_bldg_raster.py [festival_id ...]
出力:
    web/data/bldg_<id>.png / web/data/bldg_<id>.json
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from batch_calc import load_festivals, buildings_path, RADIUS_KM

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "web" / "data"

PIXEL_M = 50.0  # 1ピクセル=50m


def make_raster(fest: dict) -> None:
    bpath = buildings_path(fest["id"])
    if not bpath.exists():
        print(f"[SKIP] id={fest['id']} {fest['name']}: 建物ファイルなし")
        return

    data = json.loads(bpath.read_text(encoding="utf-8"))
    geoms = [shape(f["geometry"]) for f in data["features"]]
    heights = [f["properties"]["height_m"] for f in data["features"]]
    tree = STRtree(geoms)

    lat0, lng0 = fest["lat"], fest["lng"]
    deg_lat = (RADIUS_KM * 1000) / 111_000
    deg_lng = (RADIUS_KM * 1000) / (111_000 * math.cos(math.radians(lat0)))
    lat_min, lat_max = lat0 - deg_lat, lat0 + deg_lat
    lng_min, lng_max = lng0 - deg_lng, lng0 + deg_lng

    px_h = int((lat_max - lat_min) * 111_000 / PIXEL_M)
    px_w = int((lng_max - lng_min) * 111_000 * math.cos(math.radians(lat0)) / PIXEL_M)
    arr = np.zeros((px_h, px_w), dtype=np.uint8)

    print(f"[{fest['name']}] raster {px_w}x{px_h}")
    for row in range(px_h):
        # 行=北から南（画像座標）
        lat = lat_max - (row + 0.5) * (lat_max - lat_min) / px_h
        for col in range(px_w):
            lng = lng_min + (col + 0.5) * (lng_max - lng_min) / px_w
            pt = Point(lng, lat)
            mh = 0.0
            for i in tree.query(pt):
                if geoms[i].contains(pt) and heights[i] > mh:
                    mh = heights[i]
            if mh > 0:
                arr[row, col] = min(int(round(mh)), 255)
        if (row + 1) % 100 == 0 or row + 1 == px_h:
            print(f"  [{row + 1}/{px_h}]")

    png_path = OUT_DIR / f"bldg_{fest['id']}.png"
    Image.fromarray(arr, mode="L").save(png_path, optimize=True)
    meta = {
        "bbox": [round(lng_min, 6), round(lat_min, 6), round(lng_max, 6), round(lat_max, 6)],
        "px_w": px_w,
        "px_h": px_h,
        "pixel_m": PIXEL_M,
    }
    (OUT_DIR / f"bldg_{fest['id']}.json").write_text(json.dumps(meta), encoding="utf-8")
    size_kb = png_path.stat().st_size / 1024
    print(f"  DONE: {png_path.name} ({size_kb:.0f} KB)")


def main():
    fests = load_festivals()
    if len(sys.argv) > 1:
        ids = {int(a) for a in sys.argv[1:]}
        fests = [f for f in fests if f["id"] in ids]
    for fest in fests:
        make_raster(fest)


if __name__ == "__main__":
    main()
