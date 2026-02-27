# pdf-visual-diff

2つのPDFファイルをピクセルレベルで比較し、視覚的な差分を自動検出するツールです。  
デザインの崩れ・テキストの抜け・レイアウトのズレをリグレッションテストとして継続的に検知することを目的としています。

## 特徴

- PDFを画像に変換し、ページ単位でピクセル比較
- 差分箇所を赤くハイライトした画像を出力
- 差分検出時は終了コード `1` を返し、CIと連携しやすい設計
- `uv` のインラインスクリプトメタデータにより、単一ファイルで依存関係を完結
- GitHub Actions（Ubuntu）およびローカル（Windows）の両環境で動作

## 動作イメージ

差分が検出されると、該当ページの差分画像が出力ディレクトリに保存されます。

```
diff_results/
└── diff_page_1.png   # 差分箇所が赤くハイライトされた画像
```

## セットアップ

### 前提条件

| ツール | バージョン | 用途 |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | 最新版 | Python依存関係の管理・実行 |
| `poppler-utils` | 要別途インストール | PDFを画像に変換（`pdftocairo`） |

### インストール

**Windows**

```powershell
# uv のインストール（winget）
winget install -e --id astral-sh.uv
# poppler のインストール（winget）
winget install -e --id oschwartz10612.Poppler
```

> `poppler` をインストール後、`pdftocairo.exe` があるディレクトリ（例: `C:\Program Files\poppler-xx\bin`）を環境変数 `PATH` に追加してください。

**Ubuntu / Debian**

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils
# uv のインストール
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Pythonパッケージ（`pdf2image`、`pixelmatch`、`pillow`）は `uv run` 実行時に自動インストールされます。

## 使い方

### 基本コマンド

```bash
uv run compare-pdf.py <比較元PDF> <比較先PDF>
```

### 出力ディレクトリを指定する場合

```bash
uv run compare-pdf.py expected.pdf output.pdf --output visual_diff_results
```

### 例
```ps1
# 同じ内容のPDFファイルを比較
uv run compare-pdf.py testfiles/expected.pdf testfiles/actual1.pdf

# 文字列が異なるPDFファイルを比較
uv run compare-pdf.py testfiles/expected.pdf testfiles/actual2.pdf

# ページ数が異なるPDFファイルを比較
uv run compare-pdf.py testfiles/expected.pdf testfiles/actual3.pdf
```

### 実行結果

| 終了コード | 意味 |
|---|---|
| `0` | 差分なし（全ページ一致） |
| `1` | 差分あり（差分画像を出力ディレクトリに保存） |

- ページ内容が一致する場合：
  ```
  ✅ No significant differences.
  ```
- ページ内容が視覚的に異なる場合：差分として検出
  ```
  Page 1: Found 904 pixels of difference.
  ❌ Differences found.
  ```
- ページ数が異なる場合：差分として検出
  ```
  Warning: Page count mismatch! (1 vs 2)
  Page 2: Missing in one of the PDFs.
  ❌ Differences found.
  ```

## スクリプト（`compare-pdf.py`）

スクリプトの新規作成は以下のコマンドで行います。  
依存パッケージはインラインメタデータとして自動的に記述されます。

```ps1
uv init --script compare-pdf.py
uv add --script compare-pdf.py 'pdf2image' 'pixelmatch' 'pillow'

```

```python
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "pdf2image>=1.17.0",
#     "pillow>=12.1.1",
#     "pixelmatch>=0.3.0",
# ]
# ///

import sys
import argparse
from itertools import zip_longest
from pathlib import Path
from pdf2image import convert_from_path
from pixelmatch.contrib.PIL import pixelmatch
from PIL import Image


def compare_pdf_pages(file1: str, file2: str, output_dir: str = "diff_results") -> bool:
    """
    2つのPDFファイルをページ単位でピクセル比較し、差分画像を出力する。

    Args:
        file1: 比較元PDFファイルのパス。
        file2: 比較先PDFファイルのパス。
        output_dir: 差分画像の出力先ディレクトリ。存在しない場合は自動生成される。

    Returns:
        差分が1件以上検出された場合は True、全ページ一致の場合は False。
    """
    images1 = convert_from_path(file1, dpi=100, use_pdftocairo=True)
    images2 = convert_from_path(file2, dpi=100, use_pdftocairo=True)
    Path(output_dir).mkdir(exist_ok=True, parents=True)
    diff_detected = False

    if len(images1) != len(images2):
        print(f"Warning: Page count mismatch! ({len(images1)} vs {len(images2)})")
        diff_detected = True

    # zip_longest を使用し、ページ数が異なる場合も全ページを比較対象にする
    for i, (img1, img2) in enumerate(zip_longest(images1, images2)):
        if img1 is None or img2 is None:
            # 一方にしか存在しないページは差分として記録し、あるほうを保存する
            existing = img1 or img2
            existing.save(Path(output_dir) / f"diff_page_{i+1}.png")
            print(f"Page {i+1}: Missing in one of the PDFs.")
            continue

        # pixelmatch は RGBA 形式を要求するため、比較前に両画像を変換する
        img1 = img1.convert("RGBA")
        img2 = img2.convert("RGBA")

        # サイズが異なる場合は img1 の寸法に合わせてリサイズする
        if img1.size != img2.size:
            print(f"Page {i+1}: Size mismatch {img1.size} vs {img2.size}. Resizing img2.")
            img2 = img2.resize(img1.size, Image.LANCZOS)

        diff_img = Image.new("RGBA", img1.size)
        mismatch = pixelmatch(img1, img2, diff_img, threshold=0.1)

        if mismatch > 0:
            diff_detected = True
            highlighted = Image.alpha_composite(img1, diff_img)
            highlighted.save(Path(output_dir) / f"diff_page_{i+1}.png")
            print(f"Page {i+1}: Found {mismatch} pixels of difference.")

    return diff_detected


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="2つのPDFファイルをピクセルレベルで比較し、差分を画像として出力します。"
    )
    parser.add_argument("pdf_a", help="比較元PDFファイルのパス")
    parser.add_argument("pdf_b", help="比較先PDFファイルのパス")
    parser.add_argument("--output", "-o", default="diff_results", help="差分画像の出力ディレクトリ（デフォルト: diff_results）")
    args = parser.parse_args()

    if compare_pdf_pages(args.pdf_a, args.pdf_b, args.output):
        print("❌ Differences found.")
        sys.exit(1)
    else:
        print("✅ No significant differences.")
        sys.exit(0)
```

## GitHub Actions への組み込み

以下のようにワークフローへ組み込みます。

```yaml
- name: Install poppler
  run: |
    sudo apt-get update
    sudo apt-get install -y poppler-utils

- name: Setup uv
  uses: astral-sh/setup-uv@v7

- name: Visual Diff Check
  run: |
    uv run compare-pdf.py testfiles/expected_pattern1.pdf testfiles/actual_pattern1.pdf \
      --output visual_diff_results

- name: Upload Visual Diff Results
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: pdf-visual-diff-reports
    path: visual_diff_results/
```

差分が検出されたとき（ステップ失敗時）のみアーティファクトとしてアップロードされるため、不要なストレージ消費を抑えられます。

## 設定パラメータ

スクリプト内の以下の値を変更することで、検出感度を調整できます。

| パラメータ | デフォルト値 | 説明 |
|---|---|---|
| `dpi` | `100` | PDF → 画像変換の解像度。高くするほど精細だが処理が遅くなる |
| `threshold` | `0.1` | ピクセル差分の許容閾値（0〜1）。大きくするほど差分を検出しにくくなる |

