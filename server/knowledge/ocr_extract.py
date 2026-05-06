"""
一次性脚本：OCR提取PDF全文
使用 PyMuPDF + Tesseract OCR

用法:
  python ocr_extract.py                        # 提取《积极心理学》（默认）
  python ocr_extract.py cbt                    # 提取《认知行为疗法入门》
  python ocr_extract.py <pdf_path> <out_path>  # 自定义路径
"""
import re
import sys
import io
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"

# 预设书籍
_PRESETS = {
    "positive": (
        _PROJECT_ROOT / "积极心理学 by 克里斯托弗-彼得森.pdf",
        _DATA_DIR / "积极心理学_raw.txt",
    ),
    "cbt": (
        _PROJECT_ROOT / "认知行为疗法入门+(郭召良)+(Z-Library).pdf",
        _DATA_DIR / "认知行为疗法入门_raw.txt",
    ),
}


def clean_ocr_text(text: str) -> str:
    """清理OCR产生的多余空格，保留段落结构"""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            cleaned.append("")
            continue
        # 去除中文字符之间的空格（保留英文/数字间的空格）
        line = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', line)
        line = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[，。、；：！？）》」』])', '', line)
        line = re.sub(r'(?<=[（《「『])\s+(?=[\u4e00-\u9fff])', '', line)
        # 中文和英文/数字之间保留一个空格
        line = re.sub(r'(?<=[\u4e00-\u9fff])\s{2,}(?=[a-zA-Z0-9])', ' ', line)
        line = re.sub(r'(?<=[a-zA-Z0-9])\s{2,}(?=[\u4e00-\u9fff])', ' ', line)
        cleaned.append(line)
    return "\n".join(cleaned)


def extract_pdf(pdf_path: Path, output_path: Path):
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        sys.exit(1)

    doc = fitz.open(str(pdf_path))
    total = len(doc)
    print(f"Total pages: {total}")

    all_text = []
    for i in range(total):
        page = doc[i]
        # 3x zoom for better OCR quality
        mat = fitz.Matrix(3, 3)
        pix = page.get_pixmap(matrix=mat)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img, lang="chi_sim+eng")
        cleaned = clean_ocr_text(text)
        all_text.append(f"=== 第 {i+1} 页 ===\n{cleaned}")

        if (i + 1) % 10 == 0:
            print(f"  Processed {i+1}/{total} pages...")

    doc.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(all_text))

    print(f"\nDone! Output: {output_path}")
    print(f"Total size: {output_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in _PRESETS:
        preset = sys.argv[1] if len(sys.argv) > 1 else "positive"
        pdf_path, output_path = _PRESETS[preset]
    elif len(sys.argv) == 3:
        pdf_path = Path(sys.argv[1])
        output_path = Path(sys.argv[2])
    else:
        print("用法:")
        print("  python ocr_extract.py              # 提取《积极心理学》")
        print("  python ocr_extract.py cbt           # 提取《认知行为疗法入门》")
        print("  python ocr_extract.py <pdf> <out>   # 自定义路径")
        sys.exit(0)

    extract_pdf(pdf_path, output_path)
