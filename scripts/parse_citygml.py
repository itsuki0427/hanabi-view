"""PLATEAU CityGML から建物 footprint + 高さを抽出。

入力: PLATEAU 大阪市 2025年度 CityGML（解凍後の udx/bldg/*.gml）
出力: GeoJSON FeatureCollection（geometry=Polygon、properties.height_m=建物高さ）

LOD1 想定。bldg:measuredHeight + bldg:lod0FootPrint or bldg:lod1Solid bottom face
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from lxml import etree
from shapely.geometry import Polygon, mapping

# CityGML namespaces (v2/v3/v4 共通使い分け、必要時拡張)
NS = {
    "gml": "http://www.opengis.net/gml",
    "bldg": "http://www.opengis.net/citygml/building/2.0",
    "core": "http://www.opengis.net/citygml/2.0",
}


def parse_pos_list(text: str) -> list[tuple[float, float]]:
    """gml:posList の "lat lng h lat lng h ..." を [(lng, lat), ...] に。
    PLATEAU CityGML の座標は (緯度, 経度, 高さ) 順（srsName 平面直角 or WGS84）"""
    vals = text.split()
    coords: list[tuple[float, float]] = []
    for i in range(0, len(vals), 3):
        lat = float(vals[i])
        lng = float(vals[i + 1])
        coords.append((lng, lat))
    return coords


def parse_building(bldg_el) -> dict | None:
    height_el = bldg_el.find(".//bldg:measuredHeight", NS)
    if height_el is None or height_el.text is None:
        return None
    height = float(height_el.text)

    # LOD0 footprint 優先、なければ LOD1 底面（簡易: 最初の Polygon を採用）
    poly_el = bldg_el.find(".//bldg:lod0FootPrint//gml:Polygon", NS)
    if poly_el is None:
        poly_el = bldg_el.find(".//bldg:lod1Solid//gml:Polygon", NS)
    if poly_el is None:
        return None

    pos_list = poly_el.find(".//gml:posList", NS)
    if pos_list is None or pos_list.text is None:
        return None

    coords = parse_pos_list(pos_list.text)
    if len(coords) < 4:
        return None
    poly = Polygon(coords)
    if not poly.is_valid:
        poly = poly.buffer(0)
        if not poly.is_valid or poly.is_empty:
            return None
    return {
        "type": "Feature",
        "geometry": mapping(poly),
        "properties": {"height_m": height},
    }


def parse_gml_file(path: Path) -> list[dict]:
    tree = etree.parse(str(path))
    root = tree.getroot()
    features = []
    for bldg in root.iterfind(".//bldg:Building", NS):
        f = parse_building(bldg)
        if f is not None:
            features.append(f)
    return features


def main():
    if len(sys.argv) < 3:
        print("Usage: python parse_citygml.py <input_dir_or_file> <output.geojson>")
        sys.exit(1)
    inp = Path(sys.argv[1])
    out = Path(sys.argv[2])

    if inp.is_dir():
        gml_files = sorted(inp.glob("**/*.gml"))
    else:
        gml_files = [inp]

    all_features = []
    for i, gf in enumerate(gml_files, 1):
        feats = parse_gml_file(gf)
        all_features.extend(feats)
        print(f"[{i}/{len(gml_files)}] {gf.name}: {len(feats)} buildings")

    fc = {"type": "FeatureCollection", "features": all_features}
    out.write_text(json.dumps(fc), encoding="utf-8")
    print(f"DONE: {len(all_features)} buildings -> {out}")


if __name__ == "__main__":
    main()
