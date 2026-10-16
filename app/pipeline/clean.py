"""Text cleaning: keep raw + clean for audit.

Also strips PDF-extraction noise: form feeds, page numbers, and headers/footers
that repeat on many pages (they pollute embeddings and full-text search).
"""
import re
import unicodedata

# "IIT MADRAS - Institute Rules" / "Page 3 of 42" style lines
_PAGE_NUM = re.compile(r"^\s*(page\s+)?\d{1,4}\s*(of\s+\d{1,4})?\s*$", re.I)
_HEADER_FOOTER_MIN = 3      # a line repeated on >= 3 pages is boilerplate
_HEADER_FOOTER_MAX_LEN = 90  # only short lines qualify


def _dedupe_headers_footers(lines: list) -> list:
    counts = {}
    for ln in lines:
        s = ln.strip()
        if not s or len(s) > _HEADER_FOOTER_MAX_LEN:
            continue
        counts[s] = counts.get(s, 0) + 1
    boiler = {s for s, n in counts.items() if n >= _HEADER_FOOTER_MIN}
    if not boiler:
        return lines
    return [ln for ln in lines if ln.strip() not in boiler]


def clean_text(raw: str) -> str:
    if not raw:
        return ""
    t = unicodedata.normalize("NFKC", raw)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\f", "\n")            # form feeds before collapsing blank runs
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)   # de-hyphenate across line breaks
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    lines = [ln.strip() for ln in t.split("\n")]
    lines = [ln for ln in lines if len(ln) == 0 or len(ln) >= 2]
    lines = [ln for ln in lines if not _PAGE_NUM.match(ln)]
    lines = _dedupe_headers_footers(lines)
    # collapse blank runs LAST: removing boilerplate can create new adjacencies
    collapsed: list = []
    prev_blank = False
    for ln in lines:
        if not ln:
            if prev_blank:
                continue
            prev_blank = True
        else:
            prev_blank = False
        collapsed.append(ln)
    return "\n".join(collapsed).strip()
