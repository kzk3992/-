# USDJPY Black Swan Analysis Toolkit

USDJPYの1分足（2015-01-01〜2025-12-31）を取得・整形し、ブラックスワンイベント（5分窓で50pips以上の急変）を抽出して、月別×時間帯別にポワソン推定を行うツールです。

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## ディレクトリ構成

```
project_root/
  README.md
  requirements.txt
  main.py
  src/
  data/
    raw/
    clean/
    events/
  reports/
  tests/
```

## 使い方（推奨フロー）

### 1. データダウンロード（Dukascopy）

```bash
python main.py download --start 2015-01-01 --end 2025-12-31 --pair USDJPY --granularity 1m
```

- `data/raw/` に日次のCSVを保存します。
- 途中までダウンロード済みならスキップします。
- 取得に失敗する場合はリトライし、失敗した時間帯はスキップします（ログで確認）。

### 2. 前処理（JST変換・結合）

```bash
python main.py preprocess
```

- `data/raw/*.csv` を結合し、JSTへ変換します。
- 出力: `data/clean/usdjpy_1m_jst.csv`
- 欠損は補完せず、観測時間Tから除外されます。

### 3. ブラックスワン検出

```bash
python main.py detect --window-minutes 5 --threshold-pips 50 --decluster-minutes 30
```

- Δは `close(t) - close(t-5min)`（5本前の終値との差分）を使用。
- 30分以内の再検出は同一イベントとして統合し、イベント時刻は最初の検出時刻で固定。
- 出力: `data/events/swans.csv`

### 4. ポワソン推定

```bash
python main.py poisson
```

- 出力:
  - `reports/lambda_by_month_timeband.csv`
  - `reports/probability_by_month_timeband.csv`
  - `reports/summary.txt`

### 5. 可視化（任意）

```bash
python main.py plot
```

- `reports/` に月×時間帯のヒートマップ（λ, P）をPNGで保存します。

## ローカルCSV入力モード

Dukascopy取得が難しい場合、`data/raw/` に以下のヘッダを持つCSVを配置してください。`preprocess` 以降は同じパイプラインで処理できます。

```csv
timestamp,open,high,low,close,volume
2024-01-01T00:00:00+00:00,110.00000,110.02000,109.98000,110.01000,100
```

## 時間帯区分（JST）

- A: 09:00–14:59
- B: 15:00–20:59
- C: 21:00–02:59（跨日）
- D: 03:00–08:59

## 出力物

- `data/clean/usdjpy_1m_jst.csv`
- `data/events/swans.csv`
- `reports/lambda_by_month_timeband.csv`
- `reports/probability_by_month_timeband.csv`
- `reports/summary.txt`
- `reports/lambda_heatmap.png`（plot時）
- `reports/probability_heatmap.png`（plot時）

## 注意点

- Dukascopyの1分足データは`.bi5`から復号してCSVに変換します。価格は100000で除算しています（USDJPYに合わせた小数精度）。
- 欠損がある場合は観測時間Tから除外されます。
