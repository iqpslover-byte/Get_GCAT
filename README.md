# Get_GCAT

衛星トラッカー「OP's LAB Maps」の機体諸元表示用に、
GCAT の衛星カタログから**軌道上の PAYLOAD の諸元だけ**を抜き出した JSON を毎日生成します。

## 出力

`data/gcat_slim.json` … 約 18,700 件 / 3.5MB（gzip 0.23MB）

NORAD 番号（ゼロ埋めなし）をキーにした辞書です。

```json
"25544": {
  "m": 20281.0, "dm": 19000.0, "len": 12.6, "dia": 4.2, "span": 23.9,
  "sh": "Cyl + 2 Pan", "mfr": "KHRR", "bus": "77KS", "own": "JSC", "st": "US",
  "pl": "77KM  No. 175-01", "orb": "LLEO/I", "ld": "1998-11-20", "alt": "ISS FGB"
}
```

| キー | 内容 | | キー | 内容 |
|---|---|---|---|---|
| `m` | 質量 (kg) | | `own` | 運用者 |
| `dm` | 乾燥質量 (kg) | | `st` | 国 |
| `len` / `dia` | 長さ / 直径 (m) | | `pl` | 計画名（打上げグループ名） |
| `span` | 全幅 (m) | | `orb` | 運用軌道の分類 |
| `mq` | `1` なら質量は推定値 | | `ld` | 打上げ日 (YYYY-MM-DD) |
| `sh` | 形状 | | `alt` | 別名（` / ` 区切り） |
| `mfr` / `bus` | 製造 / バス | | | |

値が無い項目はキーごと省かれます。

## 更新

`.github/workflows/build-gcat.yml` が毎日 06:00 UTC（JST 15:00）に実行され、
変化があった時だけコミットします。手動実行は Actions タブの "Run workflow" から。

ローカルで動かす場合：

```
python tools/build_gcat.py --refresh
```

## 出典・ライセンス

データ元は **[GCAT: General Catalog of Artificial Space Objects](https://planet4589.org/space/gcat/)**
（Jonathan C. McDowell 氏）の `tsv/cat/satcat.tsv` です。

GCAT は **[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)** で提供されており、
帰属を示せば複製・改変・再配布ができます。本リポジトリの `data/gcat_slim.json` は
GCAT から項目を抜粋・整形した派生物であり、同じく CC BY 4.0 で提供します。

> McDowell, Jonathan C., *General Catalog of Artificial Space Objects*,
> https://planet4589.org/space/gcat

スクリプト（`tools/`）は OP's LAB Maps の一部です。
