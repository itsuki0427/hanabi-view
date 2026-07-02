"""バッチ視線計算: festivals.csv 駆動。座標入り全大会 × メッシュ → 結果GeoJSON。

- 標高 = 国土地理院 標高タイル（ローカルキャッシュ）
- 出力 = メッシュ正方形ポリゴン（フロントで塗りつぶし表示）
- 海域メッシュ（標高タイル無効値）はスキップ
- 200点ごと途中保存（中断→再開可能）
- web/data/festivals.json も CSV から自動生成（二重管理防止）

実行:
    python scripts/batch_calc.py [festival_id ...]
    引数なし = CSV内 座標入り全大会
出力:
    web/data/result_<festival_id>.geojson
    web/data/festivals.json
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path
from time import time

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from dem_tiles import DemTileStore
from line_of_sight import calc_visibility

ROOT = Path(__file__).resolve().parent.parent
FESTIVALS_CSV = ROOT / "data" / "festivals.csv"
OUT_DIR = ROOT / "web" / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RADIUS_KM = 10.0
GRID_STEP_M = 250.0
CHECKPOINT_EVERY = 200

def buildings_path(festival_id: int) -> Path:
    """prepare_buildings.py が生成する大会別建物ファイル"""
    return ROOT / "data" / f"buildings_f{festival_id}.geojson"


def load_festivals() -> list[dict]:
    rows = []
    with FESTIVALS_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["lat"] and row["lng"] and row["max_height_m"]:
                rows.append({
                    "id": int(row["id"]),
                    "name": row["name"],
                    "date": row["date"],
                    "time": row["time"],
                    "city": row["city"],
                    "lat": float(row["lat"]),
                    "lng": float(row["lng"]),
                    "max_shaku": row["max_shaku"],
                    "max_burst_height_m": float(row["max_height_m"]),
                    "location_confidence": row["location_confidence"],
                    "source_url": row["source_url"],
                    "ui_note": row.get("ui_note") or "",
                    "height_provisional": "暫定" in (row.get("notes") or ""),
                })
    return rows


def gen_grid(center_lat, center_lng, radius_km, step_m):
    deg_lat = (radius_km * 1000) / 111_000
    deg_lng = (radius_km * 1000) / (111_000 * math.cos(math.radians(center_lat)))
    step_lat = step_m / 111_000
    step_lng = step_m / (111_000 * math.cos(math.radians(center_lat)))
    lat = center_lat - deg_lat
    while lat <= center_lat + deg_lat:
        lng = center_lng - deg_lng
        while lng <= center_lng + deg_lng:
            yield lat, lng, step_lat, step_lng
            lng += step_lng
        lat += step_lat


def load_buildings(path: Path):
    print(f"建物読込: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    geoms, heights = [], []
    for feat in data["features"]:
        geoms.append(shape(feat["geometry"]))
        heights.append(feat["properties"]["height_m"])
    tree = STRtree(geoms)
    print(f"  -> {len(geoms)} 棟")
    return tree, geoms, heights


def calc_festival(fest: dict, store: DemTileStore):
    bpath = buildings_path(fest["id"])
    if not bpath.exists():
        print(f"[SKIP] id={fest['id']} {fest['name']}: {bpath.name} 未生成 (prepare_buildings.py 先に実行)")
        return

    tree, geoms, heights = load_buildings(bpath)

    deg_lat = (RADIUS_KM * 1000) / 111_000 * 1.1
    deg_lng = (RADIUS_KM * 1000) / (111_000 * math.cos(math.radians(fest["lat"]))) * 1.1
    store.prefetch_bbox(
        fest["lat"] - deg_lat, fest["lat"] + deg_lat,
        fest["lng"] - deg_lng, fest["lng"] + deg_lng,
    )

    def get_ground_z(lng, lat):
        return store.get_elevation(lng, lat)

    def get_building_top_z(lng, lat):
        ground = get_ground_z(lng, lat)
        pt = Point(lng, lat)
        max_h = 0.0
        for i in tree.query(pt):
            if geoms[i].contains(pt) and heights[i] > max_h:
                max_h = heights[i]
        return ground + max_h

    cells = list(gen_grid(fest["lat"], fest["lng"], RADIUS_KM, GRID_STEP_M))
    print(f"[{fest['name']}] メッシュ: {len(cells)}")

    out_path = OUT_DIR / f"result_{fest['id']}.geojson"
    part_path = out_path.with_suffix(".part.json")

    features = []
    start_idx = 0
    if part_path.exists():
        prev = json.loads(part_path.read_text(encoding="utf-8"))
        features = prev["features"]
        start_idx = prev.get("next_idx", 0)
        print(f"  途中保存から再開: idx={start_idx}")

    def dump(path: Path, next_idx: int | None = None):
        obj = {
            "type": "FeatureCollection",
            "grid_step_m": GRID_STEP_M,
            "features": features,
        }
        if next_idx is not None:
            obj["next_idx"] = next_idx
        path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")

    t0 = time()
    skipped_sea = 0
    for i in range(start_idx, len(cells)):
        lat, lng, step_lat, step_lng = cells[i]
        if store.is_sea(lng, lat):
            skipped_sea += 1
        else:
            min_h, ratio = calc_visibility(
                fest["lng"], fest["lat"], fest["max_burst_height_m"],
                lng, lat,
                get_ground_z, get_building_top_z,
            )
            half_lat, half_lng = step_lat / 2, step_lng / 2
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[
                    [round(lng - half_lng, 6), round(lat - half_lat, 6)],
                    [round(lng + half_lng, 6), round(lat - half_lat, 6)],
                    [round(lng + half_lng, 6), round(lat + half_lat, 6)],
                    [round(lng - half_lng, 6), round(lat + half_lat, 6)],
                    [round(lng - half_lng, 6), round(lat - half_lat, 6)],
                ]]},
                "properties": {
                    "min_h": -1 if min_h is None else int(round(min_h)),
                    "ratio": round(ratio, 3),
                },
            })
        done = i + 1
        if done % CHECKPOINT_EVERY == 0 or done == len(cells):
            dump(part_path, next_idx=done)
            elapsed = time() - t0
            rate = (done - start_idx) / elapsed if elapsed > 0 else 0
            eta = (len(cells) - done) / rate if rate > 0 else 0
            print(f"  [{done}/{len(cells)}] {rate:.1f} pt/s ETA {eta/60:.1f}min (海スキップ {skipped_sea})")

    dump(out_path)
    part_path.unlink(missing_ok=True)
    print(f"  DONE: {out_path} ({len(features)} セル)")


def export_festivals_json(fests: list[dict]):
    computed = [f for f in fests if (OUT_DIR / f"result_{f['id']}.geojson").exists()]
    (OUT_DIR / "festivals.json").write_text(
        json.dumps(computed, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"festivals.json: {len(computed)} 大会")


def main():
    fests = load_festivals()
    if len(sys.argv) > 1:
        ids = {int(a) for a in sys.argv[1:]}
        fests = [f for f in fests if f["id"] in ids]
    print(f"対象大会: {[f['name'] for f in fests]}")
    store = DemTileStore()
    for fest in fests:
        calc_festival(fest, store)
    export_festivals_json(load_festivals())


if __name__ == "__main__":
    main()
