"""大会ごとの建物GeoJSON生成: PLATEAU zip → メッシュ抽出 → パース → 掃除。

- festivals.csv の座標から 周辺±radius_steps メッシュの bldg gml を zip から一時抽出
- parse_citygml でGeoJSON化 → data/buildings_f<id>.geojson
- 一時gmlは削除（ディスク節約）

実行:
    python scripts/prepare_buildings.py <festival_id> [festival_id ...]
"""
from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

from mesh_utils import latlng_to_mesh3, mesh3_neighbors
from parse_citygml import parse_gml_file
from batch_calc import load_festivals

ROOT = Path(__file__).resolve().parent.parent
PLATEAU_DIR = ROOT / "data" / "plateau"
TMP_DIR = PLATEAU_DIR / "_tmp_extract"

# 大会id -> PLATEAU zipファイル名（DOWNLOAD_LIST.md 参照）
ZIP_BY_FESTIVAL = {
    1: "27100_osaka-shi_city_2025_citygml_1_op.zip",
    2: "27100_osaka-shi_city_2025_citygml_1_op.zip",
    3: "27207_takatsuki-shi_city_2020_citygml_7_op.zip",
    4: "27202_kishiwadashi_city_2024_citygml_1_op.zip",
    6: "28201_himeji-shi_city_2023_citygml_2_op.zip",
    7: "26202_maizuru-shi_city_2025_citygml_1_op.zip",
    8: "25203_nagahama-shi_pref_2024_citygml_1_op.zip",
}

# 計算グリッド±10km + 視線マージンをカバー（21x21メッシュ ≒ 21km四方）
RADIUS_STEPS = 10


def prepare(fest: dict) -> None:
    import json

    zip_name = ZIP_BY_FESTIVAL.get(fest["id"])
    if zip_name is None:
        print(f"[SKIP] id={fest['id']} {fest['name']}: zip未定義")
        return
    zip_path = PLATEAU_DIR / zip_name
    if not zip_path.exists():
        print(f"[SKIP] id={fest['id']} {fest['name']}: {zip_name} 未DL")
        return

    out_path = ROOT / "data" / f"buildings_f{fest['id']}.geojson"
    center = latlng_to_mesh3(fest["lat"], fest["lng"])
    targets = set(mesh3_neighbors(center, radius_steps=RADIUS_STEPS))
    print(f"[{fest['name']}] center={center} 対象メッシュ={len(targets)}")

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    extracted = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for ent in zf.namelist():
            if "bldg" not in ent or not ent.endswith(".gml"):
                continue
            fname = Path(ent).name
            if fname.split("_")[0] not in targets:
                continue
            dst = TMP_DIR / fname
            with zf.open(ent) as src, open(dst, "wb") as f:
                f.write(src.read())
            extracted.append(dst)
    print(f"  抽出: {len(extracted)} ファイル")

    all_features = []
    for i, gf in enumerate(extracted, 1):
        feats = parse_gml_file(gf)
        all_features.extend(feats)
        if i % 20 == 0 or i == len(extracted):
            print(f"  パース [{i}/{len(extracted)}] 累計 {len(all_features)} 棟")

    out_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": all_features}),
        encoding="utf-8")
    print(f"  DONE: {out_path} ({len(all_features)} 棟)")

    shutil.rmtree(TMP_DIR)


def main():
    fests = load_festivals()
    if len(sys.argv) > 1:
        ids = {int(a) for a in sys.argv[1:]}
        fests = [f for f in fests if f["id"] in ids]
    for fest in fests:
        prepare(fest)


if __name__ == "__main__":
    main()
