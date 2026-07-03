"""視線計算 核ロジック。

入力:
    打上地点 (lng, lat, max_burst_height_m)
    観測地点 (lng, lat)
    地面標高取得関数 get_ground_z(lng, lat) -> float
    建物上面標高取得関数 get_building_top_z(lng, lat) -> float
        建物が無い点は get_ground_z と同値を返す

出力:
    (min_visible_height_m, obstacle_ratio, block_lng, block_lat)
    min_visible_height_m: 最低視認高度（観測点から見える最低の花火高度）。None なら全範囲遮蔽
    obstacle_ratio: 打上高度範囲のうち遮蔽されてる割合 (0.0-1.0)
    block_lng/lat: 「見えない高さ」の視線が最初に遮られる地点。全部見える場合は None

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
) -> tuple[float | None, float, float | None, float | None]:
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

    def first_block_point(h: float) -> tuple[float, float] | None:
        """高さ h の視線が最初に遮られるサンプル点の (lng, lat)"""
        burst_z = launch_ground + h
        line_z = obs_eye_z + (burst_z - obs_eye_z) * ts
        blocked_idx = np.where(line_z[1:-1] < obstacle_z[1:-1])[0]
        if len(blocked_idx) == 0:
            return None
        i = int(blocked_idx[0]) + 1
        return float(lngs[i]), float(lats[i])

    if not visible_flags.any():
        bp = first_block_point(float(heights[-1]))
        return None, 1.0, (bp[0] if bp else None), (bp[1] if bp else None)
    min_visible_height = float(heights[visible_flags.argmax()])
    obstacle_ratio = float(1.0 - visible_flags.mean())
    if min_visible_height <= 0.0:
        return min_visible_height, obstacle_ratio, None, None
    # 「見えない最高の高さ」（min_h の1段下）の遮蔽点 = 何に遮られてるかの代表点
    bp = first_block_point(min_visible_height - HEIGHT_STEP_M)
    return min_visible_height, obstacle_ratio, (bp[0] if bp else None), (bp[1] if bp else None)
