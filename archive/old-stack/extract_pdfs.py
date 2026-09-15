"""
extract_pdfs.py

Extract text from PDF files in the workspace root and save each as a .txt file in data/.
"""
import os
from pathlib import Path

try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    import PyPDF2
except Exception:
    PyPDF2 = None

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

pdf_files = sorted([p for p in ROOT.glob("*.pdf") if p.is_file()])
if not pdf_files:
    print("No PDF files found in the workspace root.")
    raise SystemExit(0)

print(f"Found {len(pdf_files)} PDF(s).")


def extract_with_pdfplumber(path: Path) -> str:
    parts = []
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            parts.append(text)
    return "\n\n".join(parts)


def extract_with_pypdf2(path: Path) -> str:
    reader = PyPDF2.PdfReader(str(path))
    parts = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        parts.append(text)
    return "\n\n".join(parts)


for pdf in pdf_files:
    out_path = DATA_DIR / f"{pdf.stem}.txt"
    if out_path.exists():
        print(f"SKIP {pdf.name} -> {out_path.name} already exists")
        continue

    print(f"EXTRACT {pdf.name} ...")
    try:
        if pdfplumber is not None:
            text = extract_with_pdfplumber(pdf)
        elif PyPDF2 is not None:
            text = extract_with_pypdf2(pdf)
        else:
            raise RuntimeError("No PDF extraction library available")
    except Exception as e:
        print(f"FAILED {pdf.name}: {e}")
        continue

    out_path.write_text(text, encoding="utf-8")
    print(f"SAVED  {pdf.name} -> {out_path} ({len(text)} chars)")

print("Done.")
