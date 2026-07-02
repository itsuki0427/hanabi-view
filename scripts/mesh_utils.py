"""日本標準地域メッシュ（3次=1kmメッシュ）変換ユーティリティ。

3次メッシュコード = 8桁
  1次: 緯度*1.5 (2桁) + 経度-100 (2桁) = 4桁、80km四方
  2次: 1次内の8x8分割 = 2桁、10km四方
  3次: 2次内の10x10分割 = 2桁、1km四方
"""
from __future__ import annotations


def latlng_to_mesh3(lat: float, lng: float) -> str:
    p = int(lat * 1.5)
    a = lat * 1.5 - p
    u = int(lng - 100)
    f = lng - 100 - u
    q = int(a * 8)
    g = a * 8 - q
    v = int(f * 8)
    h = f * 8 - v
    r = int(g * 10)
    w = int(h * 10)
    return f"{p:02d}{u:02d}{q}{v}{r}{w}"


def mesh3_to_latlng_sw(code: str) -> tuple[float, float]:
    """3次メッシュコードの 南西角 (lat, lng) を返す"""
    p = int(code[0:2])
    u = int(code[2:4])
    q = int(code[4])
    v = int(code[5])
    r = int(code[6])
    w = int(code[7])
    lat = (p + (q + r / 10) / 8) / 1.5
    lng = 100 + u + (v + w / 10) / 8
    return lat, lng


def mesh3_neighbors(center_code: str, radius_steps: int = 5) -> list[str]:
    """中心メッシュから ±radius_steps の範囲のメッシュコード一覧。
    radius_steps=5 -> 11x11=121メッシュ（約11km四方）
    """
    cx_lat, cx_lng = mesh3_to_latlng_sw(center_code)
    # 3次メッシュ 1単位 = 緯度 1/120度, 経度 1/80度
    step_lat = 1.0 / 120
    step_lng = 1.0 / 80
    codes = set()
    for dy in range(-radius_steps, radius_steps + 1):
        for dx in range(-radius_steps, radius_steps + 1):
            lat = cx_lat + (dy + 0.5) * step_lat
            lng = cx_lng + (dx + 0.5) * step_lng
            codes.add(latlng_to_mesh3(lat, lng))
    return sorted(codes)


if __name__ == "__main__":
    # 淀川花火 想定地点
    lat, lng = 34.7235, 135.4925
    code = latlng_to_mesh3(lat, lng)
    print(f"({lat}, {lng}) -> mesh3 = {code}")
    sw = mesh3_to_latlng_sw(code)
    print(f"SW corner: {sw}")
    neigh = mesh3_neighbors(code, radius_steps=5)
    print(f"周辺メッシュ ({len(neigh)} 個):")
    for c in neigh:
        print(f"  {c}")
