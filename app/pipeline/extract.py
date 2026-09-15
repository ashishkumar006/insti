"""Extract raw text from uploads: pdf/txt/md/html/csv/xlsx/xls/docx/pptx.

Strategy per type (offline-first, deterministic):
- Digital PDFs: pdfplumber -> PyPDF2. Scanned PDFs (no text layer):
  render pages with PyMuPDF -> DeepSeek-OCR via Ollama (optional).
- Excel: openpyxl, one section per sheet (Sheet: name + pipe-joined rows).
- Word/PowerPoint: manual OOXML parse (no extra deps).
- CSV: rows joined; HTML/MD: tags stripped, text kept.
"""
import csv
import io
import pathlib
import re
import zipfile
import xml.etree.ElementTree as ET

SUPPORTED = (".pdf", ".txt", ".md", ".markdown", ".html", ".htm",
             ".csv", ".xlsx", ".xls", ".docx", ".pptx")


def extract_text(path: str, filename: str) -> str:
    suf = pathlib.Path(filename).suffix.lower()
    if suf in (".txt", ".md", ".markdown"):
        return pathlib.Path(path).read_text(encoding="utf-8", errors="ignore")
    if suf in (".html", ".htm"):
        return _html(path)
    if suf == ".csv":
        return _csv(path)
    if suf in (".xlsx", ".xls"):
        return _excel(path)
    if suf == ".docx":
        return _ooxml_text(path, "word/document.xml", "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
    if suf == ".pptx":
        return _pptx(path)
    if suf == ".pdf":
        return _pdf(path)
    raise ValueError("Unsupported file. Use: " + ", ".join(SUPPORTED))


# ── PDF: text layer first, vision OCR for scans ─────────────────────────────

def _pdf(path: str) -> str:
    text = ""
    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(path) as pdf:
            text = "\n\n".join([(p.extract_text() or "") for p in pdf.pages]).strip()
    except Exception:
        text = ""
    if len(text) < 100:
        try:
            import PyPDF2  # type: ignore
            reader = PyPDF2.PdfReader(path)
            alt = "\n\n".join([(p.extract_text() or "") for p in reader.pages]).strip()
            if len(alt) > len(text):
                text = alt
        except Exception:
            pass
    if len(text) >= 100:
        return text
    try:
        vlm = _pdf_vlm_ocr(path)
    except Exception:
        vlm = ""
    if vlm.strip():
        return vlm
    if text:
        return text
    raise ValueError("No extractable text (scanned PDF needs `ollama pull deepseek-ocr`)")


def _pdf_vlm_ocr(path: str, max_pages: int = 30, dpi: int = 150) -> str:
    """Scanned pages -> text. Order: Gemini API (cloud-safe) -> local DeepSeek-OCR.

    OCR_MODE env: auto (both) | gemini | ollama | off.
    """
    import fitz  # PyMuPDF
    from app.config import cfg
    mode = (cfg.ocr_mode or "auto").lower()
    if mode == "off":
        return ""
    doc = fitz.open(path)
    pages = min(len(doc), max_pages)
    pngs = [doc[i].get_pixmap(dpi=dpi).tobytes("png") for i in range(pages)]
    if mode in ("auto", "gemini"):
        key = cfg.gemini_api_key or cfg.paygo_api_key
        if key:
            try:
                from app.llm.gemini_adapter import GeminiAdapter
                g = GeminiAdapter(key)
                out = [g.ocr_image(b) for b in pngs]
                if any(o.strip() for o in out):
                    return "\n\n".join([p for p in out if p.strip()])
            except Exception:
                pass
        if mode == "gemini":
            return ""
    if mode in ("auto", "ollama"):
        import base64
        import httpx
        out = []
        try:
            with httpx.Client(timeout=300.0) as c:
                show = c.post(cfg.ollama_url.rstrip("/") + "/api/show", json={"name": "deepseek-ocr"})
                if show.status_code != 200:
                    return ""
                for img in pngs:
                    b64 = base64.b64encode(img).decode()
                    r = c.post(cfg.ollama_url.rstrip("/") + "/api/generate", json={
                        "model": "deepseek-ocr",
                        "prompt": "<image>\n<|grounding|>Convert the document to markdown.",
                        "images": [b64], "stream": False,
                        "options": {"temperature": 0.0, "num_predict": 4096}})
                    r.raise_for_status()
                    t = (r.json().get("response") or "").strip()
                    if t:
                        out.append(t)
        except Exception:
            return "\n\n".join([p for p in out if p.strip()])
        return "\n\n".join([p for p in out if p.strip()])
    return ""


# ── Office / structured ─────────────────────────────────────────────────────

def _excel(path: str) -> str:
    import openpyxl  # handles .xlsx; .xls raises a clear error below
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as e:
        raise ValueError("Could not read spreadsheet (for .xls save as .xlsx first): {}".format(e)[:160])
    sections = []
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True):
            vals = [str(v).strip() for v in row if v is not None and str(v).strip() != ""]
            if vals:
                rows.append(" | ".join(vals))
        if rows:
            sections.append("# Sheet: {}\n{}".format(ws.title, "\n".join(rows)))
    if not sections:
        raise ValueError("Spreadsheet has no readable cells")
    return "\n\n".join(sections)


def _csv(path: str) -> str:
    with open(path, "r", encoding="utf-8-sig", errors="ignore", newline="") as f:
        rows = [[" ".join(cell.split()) for cell in row if cell and cell.strip()]
                for row in csv.reader(f)]
    lines = [" | ".join(r) for r in rows if r]
    if not lines:
        raise ValueError("CSV has no readable rows")
    return "\n".join(lines)


def _ooxml_text(path: str, doc_xml: str, text_tag: str) -> str:
    """Paragraphs + tables from a docx word/document.xml (no deps)."""
    with zipfile.ZipFile(path) as z:
        try:
            root = ET.fromstring(z.read(doc_xml))
        except KeyError:
            raise ValueError("Not a valid .docx file")
    paras = []
    for p in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        t = "".join([(n.text or "") for n in p.iter(text_tag)]).strip()
        if t:
            paras.append(t)
    text = "\n\n".join(paras).strip()
    if not text:
        raise ValueError("Document has no readable text")
    return text


def _pptx(path: str) -> str:
    """Slide texts from pptx (no deps)."""
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    slides = []
    try:
        with zipfile.ZipFile(path) as z:
            names = sorted([n for n in z.namelist()
                            if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)])
            if not names:
                raise ValueError("Not a valid .pptx file")
            for i, n in enumerate(names, 1):
                root = ET.fromstring(z.read(n))
                texts = [t.text.strip() for t in root.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}t")
                         if t.text and t.text.strip()]
                if texts:
                    slides.append("# Slide {}\n{}".format(i, "\n".join(texts)))
    except zipfile.BadZipFile:
        raise ValueError("Not a valid .pptx file")
    if not slides:
        raise ValueError("Presentation has no readable text")
    return "\n\n".join(slides)


def _html(path: str) -> str:
    raw = pathlib.Path(path).read_text(encoding="utf-8", errors="ignore")
    try:
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text(separator="\n")
    except Exception:
        return re.sub(r"<[^>]+>", "\n", raw)
