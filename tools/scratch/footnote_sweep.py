"""PRE-WORK (a): sweep all 231 pages for asterisk/dagger/superscript footnote
markers, independent of the phase-2b loss classification, and cross-reference
against what phase 2b called each page.
"""
import json
import re
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "cibrc"
AUDIT = ROOT / "data" / "interim" / "phase2b_audit.json"

FILES = [
    "insecticides_20260331.pdf",
    "fungicides_20260331.pdf",
    "bio_insecticides_20260331.pdf",
    "bio_fungicides_20260331.pdf",
]

MARKER_RE = re.compile(r"\*{1,4}|[†‡]")
FOOTER_RE = re.compile(r"^\(?\d{1,4}\)?$")

audit = json.loads(AUDIT.read_text(encoding="utf-8"))
classes_by = {}
for rec in audit:
    for pa in rec["page_audits"]:
        classes_by[(rec["file"], pa["page"])] = sorted({l["class"] for l in pa["losses"]})

rows = []
for fn in FILES:
    path = RAW / fn
    with pdfplumber.open(path) as pdf:
        for i, pg in enumerate(pdf.pages, start=1):
            text = pg.extract_text() or ""
            lines = [l for l in text.splitlines() if l.strip()]
            hits = []
            for ln in lines:
                if FOOTER_RE.match(ln.strip()):
                    continue
                for m in MARKER_RE.finditer(ln):
                    # context: the word/token the marker is attached to
                    start = max(0, m.start() - 25)
                    end = min(len(ln), m.end() + 40)
                    hits.append((m.group(), ln[start:end].strip()))
            if hits:
                cls = classes_by.get((fn, i), [])
                rows.append({"file": fn, "page": i, "hits": hits, "phase2b_classes": cls})

    # superscript char scan: small, vertically-shifted glyphs glued to a word
    with pdfplumber.open(path) as pdf:
        for i, pg in enumerate(pdf.pages, start=1):
            chars = pg.chars
            if not chars:
                continue
            sizes = [c["size"] for c in chars]
            mode_size = max(set(round(s, 1) for s in sizes),
                            key=lambda s: sum(1 for x in sizes if round(x, 1) == s))
            supers = [c for c in chars
                      if round(c["size"], 1) < mode_size - 1.5 and c["text"].strip()]
            if supers:
                cls = classes_by.get((fn, i), [])
                for c in supers:
                    # neighbouring chars for context
                    nearby = [ch for ch in chars
                              if abs(ch["top"] - c["top"]) < 15 and abs(ch["x0"] - c["x0"]) < 60]
                    nearby.sort(key=lambda ch: ch["x0"])
                    ctx = "".join(ch["text"] for ch in nearby)
                    rows.append({"file": fn, "page": i, "superscript": c["text"],
                                 "size": round(c["size"], 1), "mode_size": mode_size,
                                 "context": ctx, "phase2b_classes": cls})

print(f"total pages swept: {sum(len(json.loads(AUDIT.read_text(encoding='utf-8'))[j]['page_audits']) for j in range(len(FILES)))}")
print(f"rows with marker/superscript hits: {len(rows)}\n")

for r in rows:
    print(json.dumps(r, ensure_ascii=False))
