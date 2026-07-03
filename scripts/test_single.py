"""1大会・複数観測点で視線計算 試走。

前提:
    - PLATEAU 大阪市 2025年度 CityGML が data/plateau/ に展開済み
    - parse_citygml.py で建物GeoJSON 生成済み: data/buildings_osaka.geojson

実行:
    python scripts/test_single.py
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from elevation_api import get_elevation
from line_of_sight import calc_visibility

ROOT = Path(__file__).resolve().parent.parent
BUILDINGS_PATH = ROOT / "data" / "buildings_osaka.geojson"

# 仮の打上地点（淀川河川敷 想定、正確な座標は要確認）
LAUNCH = {
    "name": "なにわ淀川花火大会(仮)",
    "lng": 135.4925,
    "lat": 34.7235,
    "max_burst_height_m": 330.0,
}

# 試走観測点（梅田・新大阪・本町・心斎橋）
OBSERVERS = [
    ("梅田駅前", 135.4983, 34.7025),
    ("新大阪駅", 135.5004, 34.7335),
    ("本町駅", 135.4983, 34.6837),
    ("心斎橋駅", 135.5010, 34.6750),
    ("淀川河川敷(対岸)", 135.4910, 34.7180),
]


def load_buildings(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    geoms = []
    heights = []
    for feat in data["features"]:
        geoms.append(shape(feat["geometry"]))
        heights.append(feat["properties"]["height_m"])
    tree = STRtree(geoms)
    return tree, geoms, heights


def main():
    if not BUILDINGS_PATH.exists():
        print(f"[ERROR] {BUILDINGS_PATH} が無い。先に parse_citygml.py を実行")
        print("  python scripts/parse_citygml.py data/plateau/<udx_bldg_dir> data/buildings_osaka.geojson")
        return

    print(f"建物データ読込: {BUILDINGS_PATH}")
    tree, geoms, heights = load_buildings(BUILDINGS_PATH)
    print(f"  -> {len(geoms)} 棟")

    @lru_cache(maxsize=200_000)
    def get_ground_z(lng: float, lat: float) -> float:
        return get_elevation(lng, lat)

    @lru_cache(maxsize=200_000)
    def get_building_top_z(lng: float, lat: float) -> float:
        ground = get_ground_z(lng, lat)
        pt = Point(lng, lat)
        idxs = tree.query(pt)
        max_h = 0.0
        for i in idxs:
            if geoms[i].contains(pt):
                if heights[i] > max_h:
                    max_h = heights[i]
        return ground + max_h

    print(f"\n打上: {LAUNCH['name']} ({LAUNCH['lat']}, {LAUNCH['lng']}) 最大{LAUNCH['max_burst_height_m']}m")
    print(f"{'観測点':<20} {'最低視認高度':>12} {'障害物率':>10}")
    print("-" * 50)
    for name, lng, lat in OBSERVERS:
        min_h, ratio, _bx, _by = calc_visibility(
            LAUNCH["lng"], LAUNCH["lat"], LAUNCH["max_burst_height_m"],
            lng, lat,
            get_ground_z, get_building_top_z,
        )
        min_h_str = "全遮蔽" if min_h is None else f"{min_h:>8.0f} m"
        print(f"{name:<20} {min_h_str:>12} {ratio*100:>9.1f}%")


if __name__ == "__main__":
    main()
