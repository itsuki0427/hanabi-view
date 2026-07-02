# hanabi-view

関西の花火大会が「どこから・どれだけ見えるか」を地図で確認できるサイト。

3D都市モデル（PLATEAU）の建物データと国土地理院の標高データを使い、打上地点から各地点への視線が建物・地形に遮られるかを計算しています。

## 対象大会（2026年）

なにわ淀川花火大会 / 天神祭奉納花火 / 水都くらわんか花火大会 / 岸和田港まつり花火大会 / 姫路みなと祭海上花火大会 / みなと舞鶴ちゃった花火大会 / 長浜・北びわ湖大花火大会

※3D建物データ（PLATEAU）が整備済みの自治体で開催される大会のみ対象

## 見え方の読み方

- **緑**: 低い花火までほぼ全部見える
- **黄〜橙**: 高く上がる花火だけ見える
- **赤**: 建物・地形に遮られてほぼ見えない

地図をクリックすると「その場所から何m以上の高さの花火が見えるか」を表示します。

## 精度について（必読）

このマップは**目安**です。以下は考慮していません:

- 街路樹・電線・仮設物・新築建物（データ更新後のもの）
- 群衆・観覧環境
- 花火の開花サイズ（号数から推定した高さのみ使用）
- 一部大会は打上地点・最大号数が公式未発表のため推定値（地図上に注記あり）

「見える」表示でも現地で見えない場合があります。逆も然り。

## データソース

| データ | 提供元 | ライセンス |
|---|---|---|
| 3D都市モデル（建物） | [Project PLATEAU](https://www.mlit.go.jp/plateau/)（国土交通省） | [PLATEAUサイトポリシー](https://www.mlit.go.jp/plateau/site-policy/)（商用利用可） |
| 標高タイル・地図タイル | [国土地理院](https://maps.gsi.go.jp/development/ichiran.html) | [国土地理院コンテンツ利用規約](https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html)（出典明記） |
| 大会情報 | 各大会公式サイト等（`data/festivals.csv` の source_url 参照） | — |

地図ライブラリ: [MapLibre GL JS](https://maplibre.org/)（BSD-3-Clause）

## 仕組み

1. `data/festivals.csv` — 大会マスタ（打上地点・最大号数・出典）
2. `scripts/prepare_buildings.py` — PLATEAU CityGML から打上地点周辺の建物（footprint + 高さ）を抽出
3. `scripts/batch_calc.py` — 各250mメッシュから打上地点への視線を高度10m刻みでサンプリングし、最低視認高度と遮蔽率を計算
4. `web/` — 計算結果（GeoJSON）を MapLibre で表示する静的サイト

## ローカル実行

```bash
# 表示のみ（計算済みデータ同梱）
cd web && python -m http.server 8000

# 再計算する場合
pip install numpy shapely pyproj lxml requests pillow
# PLATEAU CityGML zip を data/plateau/ に配置（data/plateau/DOWNLOAD_LIST.md 参照）
python scripts/prepare_buildings.py <festival_id>
python scripts/batch_calc.py <festival_id>
```

## License

コード: MIT License（[LICENSE](LICENSE)）
計算結果データ（`web/data/`）: 元データのライセンス（PLATEAU・国土地理院）に従います
