"""視線計算 核ロジック。

入力:
    打上地点 (lng, lat, max_burst_height_m)
    観測地点 (lng, lat)
    地面標高取得関数 get_ground_z(lng, lat) -> float
    建物上面標高取得関数 get_building_top_z(lng, lat) -> float
        建物が無い点は get_ground_z と同値を返す

出力:
    (min_visible_height_m, obstacle_ratio)
    min_visible_height_m: 最低視認高度（観測点から見える最低の花火高度）。None なら全範囲遮蔽
    obstacle_ratio: 打上高度範囲のうち遮蔽されてる割合 (0.0-1.0)

座標系:
    入力は WGS84 (lng, lat)
    視線サンプリングは メートル系で実施（pyproj で 平面直角6系 EPSG:6674 = JGD2011 第6系/近畿）
"""
from __future__ import annotations

from typing import Callable

import numpy as np
from pyproj import Transformer

_TO_M = Transformer.from_crs("EPSG:4326", "EPSG:6674", always_xy=True)
_TO_LL = Transformer.from_crs("EPSG:6674", "EPSG:4326", always_xy=True)

EYE_HEIGHT_M = 1.6
SAMPLING_STEP_M = 50.0
HEIGHT_STEP_M = 10.0


def calc_visibility(
    launch_lng: float,
    launch_lat: float,
    max_burst_height_m: float,
    obs_lng: float,
    obs_lat: float,
    get_ground_z: Callable[[float, float], float],
    get_building_top_z: Callable[[float, float], float],
) -> tuple[float | None, float]:
    lx, ly = _TO_M.transform(launch_lng, launch_lat)
    ox, oy = _TO_M.transform(obs_lng, obs_lat)

    horiz = float(np.hypot(lx - ox, ly - oy))
    n_steps = max(int(horiz / SAMPLING_STEP_M), 2)
    ts = np.linspace(0.0, 1.0, n_steps + 1)
    xs = ox + (lx - ox) * ts
    ys = oy + (ly - oy) * ts

    lngs, lats = _TO_LL.transform(xs, ys)

    obstacle_z = np.array([
        get_building_top_z(float(lng), float(lat))
        for lng, lat in zip(lngs, lats)
    ])

    obs_ground = get_ground_z(obs_lng, obs_lat)
    obs_eye_z = obs_ground + EYE_HEIGHT_M
    launch_ground = get_ground_z(launch_lng, launch_lat)

    heights = np.arange(0.0, max_burst_height_m + HEIGHT_STEP_M, HEIGHT_STEP_M)
    visible_flags = np.zeros(len(heights), dtype=bool)

    for i, h in enumerate(heights):
        burst_z = launch_ground + h
        line_z = obs_eye_z + (burst_z - obs_eye_z) * ts
        # 端点（観測点・打上点）は判定から除外
        blocked = bool(np.any(line_z[1:-1] < obstacle_z[1:-1]))
        visible_flags[i] = not blocked

    if not visible_flags.any():
        return None, 1.0
    min_visible_height = float(heights[visible_flags.argmax()])
    obstacle_ratio = float(1.0 - visible_flags.mean())
    return min_visible_height, obstacle_ratio
