"""国土地理院 標高API ラッパ。試作段階のDEM代替用。

URL: https://cyberjapandata2.gsi.go.jp/general/dem/scripts/getelevation.php
レスポンス: {"elevation": <float>, "hsrc": "DEM5A"|"DEM10B"|...}
レート制限: 公式明記なし。安全側で 0.1秒間隔で叩く
"""
from __future__ import annotations

import time
from functools import lru_cache

import requests

_ENDPOINT = "https://cyberjapandata2.gsi.go.jp/general/dem/scripts/getelevation.php"
_MIN_INTERVAL_S = 0.1
_last_call_t = 0.0


@lru_cache(maxsize=100_000)
def get_elevation(lng: float, lat: float) -> float:
    """指定座標の標高(m)。海上等取得不可なら 0.0 を返す。"""
    global _last_call_t
    wait = _MIN_INTERVAL_S - (time.time() - _last_call_t)
    if wait > 0:
        time.sleep(wait)
    _last_call_t = time.time()

    r = requests.get(
        _ENDPOINT,
        params={"lon": lng, "lat": lat, "outtype": "JSON"},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    elev = data.get("elevation")
    if elev is None or elev == "-----":
        return 0.0
    return float(elev)


if __name__ == "__main__":
    # 動作確認: 淀川河川敷あたり
    print("淀川河川敷:", get_elevation(135.49, 34.72), "m")
    print("生駒山頂:", get_elevation(135.678, 34.679), "m")
