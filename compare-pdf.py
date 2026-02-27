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
