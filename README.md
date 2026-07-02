# hanabi-view

関西圏 花火大会 視認可能エリア マップ。

## 何ができる

- 関西圏（2026年）主要花火大会を地図上で選択
- 任意地点から「最低何mから見えるか」「打上高度範囲のうち何%遮蔽されてないか」を可視化
- PLATEAU 3D都市モデル + 国土地理院DEM で 建物・地形の遮蔽を計算

## スコープ

- 対象: 2026年 関西 7大会（淀川・天神祭・くらわんか・岸和田・姫路・舞鶴・長浜）
  - PLATEAU（3D建物データ）対応自治体の大会のみ。神戸・芦屋・大津等は未対応のため対象外
- 精度: 建物・地形のみ考慮。木・電線・架線は無視（目安）
- 配信: 完全静的（GeoJSON + MapLibre）

## データソース

- PLATEAU 3D都市モデル: G空間情報センター（無料）
- 標高DEM: 国土地理院 基盤地図情報5mメッシュ（無料）
- 地図タイル: 国土地理院 地理院タイル（無料・要出典明記）
- 花火大会データ: 手動収集（`data/festivals.csv`）

## ディレクトリ構成

- `data/` 入力データ（CSV）・中間生成物
- `scripts/` 計算スクリプト（Python）
- `web/` フロントエンド（MapLibre + Vanilla TS）
- `docs/` 仕様書・設計メモ

## 使い方（ローカル）

```
cd web
..\.venv\Scripts\python.exe -m http.server 8000
# → http://localhost:8000
```

## データ更新手順

1. `data/festivals.csv` を編集（大会情報の一次ソース。festivals.json は自動生成）
2. PLATEAU zip を `data/plateau/` に配置（[DOWNLOAD_LIST.md](data/plateau/DOWNLOAD_LIST.md)）
3. `python scripts/prepare_buildings.py <大会id>` — 建物データ生成
4. `python scripts/batch_calc.py <大会id>` — 視認計算 + festivals.json 再生成

## 進捗

- [x] 試作: 淀川花火で視線計算 動作確認（河川敷=見える/ビル街=遮蔽 の妥当性確認済み）
- [x] 大会データ収集（7大会・出典付き）
- [x] フロント実装（大会切替・メッシュ塗り・クリック詳細）
- [ ] 全7大会 バッチ計算（済: 淀川・天神祭 / 残: PLATEAU zip DL待ち）
- [ ] 仕様書ドラフト
- [ ] GitHubリポ・Cloudflare Pages デプロイ（我妻さん指示待ち）
