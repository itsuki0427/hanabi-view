"""国土地理院 標高タイル（PNG）ローカルキャッシュ付きストア。

標高API の代替。タイルを一括DLしてローカル参照 → ループ内ネットワークゼロ。

タイル仕様（公式: https://maps.gsi.go.jp/development/ichiran.html#dem）:
    dem_png  : 10mメッシュ相当, zoom<=14, 全国カバー
    標高値 x = (R*256^2 + G*256 + B) * 0.01 [m]
    x >= 2^23 は負値: x - 2^24
    (R,G,B) = (128,0,0) は無効値（海など）→ 0.0 扱い
"""
from __future__ import annotations

import math
import time
from pathlib import Path

import numpy as np
import requests
from PIL import Image

TILE_URL = "https://cyberjapandata.gsi.go.jp/xyz/dem_png/{z}/{x}/{y}.png"
ZOOM = 14
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "dem_tiles"
_DL_INTERVAL_S = 0.02


def _latlng_to_tile_pixel(lat: float, lng: float, z: int) -> tuple[int, int, int, int]:
    """(tile_x, tile_y, px, py)"""
    n = 2 ** z
    xf = (lng + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    yf = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    tx, ty = int(xf), int(yf)
    px = int((xf - tx) * 256)
    py = int((yf - ty) * 256)
    return tx, ty, px, py


class DemTileStore:
    def __init__(self, zoom: int = ZOOM):
        self.zoom = zoom
        self._tiles: dict[tuple[int, int], np.ndarray | None] = {}
        self._invalid_masks: dict[tuple[int, int], np.ndarray] = {}
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._last_dl = 0.0

    def _tile_path(self, tx: int, ty: int) -> Path:
        return CACHE_DIR / f"{self.zoom}_{tx}_{ty}.png"

    def _decode(self, img: Image.Image) -> tuple[np.ndarray, np.ndarray]:
        arr = np.asarray(img.convert("RGB"), dtype=np.int64)
        x = arr[:, :, 0] * 65536 + arr[:, :, 1] * 256 + arr[:, :, 2]
        elev = x.astype(np.float64) * 0.01
        elev = np.where(x >= 2 ** 23, (x - 2 ** 24) * 0.01, elev)
        invalid = (arr[:, :, 0] == 128) & (arr[:, :, 1] == 0) & (arr[:, :, 2] == 0)
        elev[invalid] = 0.0
        return elev, invalid

    def _load_tile(self, tx: int, ty: int) -> np.ndarray | None:
        key = (tx, ty)
        if key in self._tiles:
            return self._tiles[key]
        p = self._tile_path(tx, ty)
        if not p.exists():
            wait = _DL_INTERVAL_S - (time.time() - self._last_dl)
            if wait > 0:
                time.sleep(wait)
            self._last_dl = time.time()
            r = None
            for attempt in range(4):
                try:
                    r = requests.get(TILE_URL.format(z=self.zoom, x=tx, y=ty), timeout=15)
                    break
                except (requests.Timeout, requests.ConnectionError):
                    if attempt == 3:
                        raise
                    time.sleep(2 ** attempt)  # 1,2,4秒 バックオフ
            if r.status_code == 404:
                # 海のみのタイル等は提供なし
                self._tiles[key] = None
                p.with_suffix(".404").touch()
                return None
            r.raise_for_status()
            p.write_bytes(r.content)
        elif p.with_suffix(".404").exists():
            self._tiles[key] = None
            return None
        elev, invalid = self._decode(Image.open(p))
        self._tiles[key] = elev
        self._invalid_masks[key] = invalid
        return elev

    def get_elevation(self, lng: float, lat: float) -> float:
        tx, ty, px, py = _latlng_to_tile_pixel(lat, lng, self.zoom)
        if self._tile_path(tx, ty).with_suffix(".404").exists() and (tx, ty) not in self._tiles:
            self._tiles[(tx, ty)] = None
        tile = self._load_tile(tx, ty)
        if tile is None:
            return 0.0
        return float(tile[py, px])

    def is_sea(self, lng: float, lat: float) -> bool:
        """標高タイルの無効値ピクセル（海域）判定。
        _decode で無効値は 0.0 に置換済みのため、無効マスクを別持ちする代わりに
        タイル欠損 (404) = 海域のみタイル も海扱いにする。"""
        tx, ty, px, py = _latlng_to_tile_pixel(lat, lng, self.zoom)
        tile = self._load_tile(tx, ty)
        if tile is None:
            return True
        mask = self._invalid_masks.get((tx, ty))
        if mask is None:
            return False
        return bool(mask[py, px])

    def prefetch_bbox(self, lat_min: float, lat_max: float, lng_min: float, lng_max: float):
        tx0, ty1, _, _ = _latlng_to_tile_pixel(lat_min, lng_min, self.zoom)
        tx1, ty0, _, _ = _latlng_to_tile_pixel(lat_max, lng_max, self.zoom)
        total = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
        print(f"DEMタイル prefetch: {total} 枚 (zoom={self.zoom})")
        done = 0
        for tx in range(tx0, tx1 + 1):
            for ty in range(ty0, ty1 + 1):
                self._load_tile(tx, ty)
                done += 1
                if done % 50 == 0 or done == total:
                    print(f"  [{done}/{total}]")


if __name__ == "__main__":
    store = DemTileStore()
    # 標高API実測値と突合: 淀川河川敷 8.1m / 生駒山頂 629.0m
    print("淀川河川敷:", store.get_elevation(135.49, 34.72), "m (API実測 8.1)")
    print("生駒山頂:", store.get_elevation(135.678, 34.679), "m (API実測 629.0)")
