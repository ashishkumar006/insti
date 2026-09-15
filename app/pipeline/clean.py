"""Text cleaning: keep raw + clean for audit."""
import re
import unicodedata


def clean_text(raw: str) -> str:
    if not raw:
        return ""
    t = unicodedata.normalize("NFKC", raw)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)  # de-hyphenate
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    # drop tiny noisy lines but keep structure
    lines = [ln.strip() for ln in t.split("\n")]
    lines = [ln for ln in lines if len(ln) == 0 or len(ln) >= 2]
    return "\n".join(lines).strip()
