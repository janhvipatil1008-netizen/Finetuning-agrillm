"""PHASE 1 triage: does each CIB&RC PDF have a real text layer, or is it a scan?

Pure-Python equivalent of `pdffonts` + `pdftotext`, so the answer does not depend
on poppler being installed. Reports, per file and for a middle page:

  * embedded font count and names           (pdffonts equivalent, via PyMuPDF)
  * extractable character count             (pdftotext equivalent, via pdfplumber)
  * raster image count and coverage         (scan detector)
  * vector line/rect count                  (ruling lines -> camelot lattice viability)

Decision rule (per page): a page is TEXT if it has >=1 embedded font AND
>=200 extractable chars. A page is SCAN if it has ~0 chars and >=1 large image
covering most of the page. Anything else is AMBIGUOUS and gets flagged.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber

RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "cibrc"

FILES = [
    "insecticides_20260331.pdf",
    "fungicides_20260331.pdf",
    "bio_insecticides_20260331.pdf",
    "bio_fungicides_20260331.pdf",
    "herbicides_20260331.pdf",
    "pgr_20260331.pdf",
]

CHAR_TEXT_THRESHOLD = 200


def classify(n_fonts: int, n_chars: int, img_cover: float) -> str:
    if n_fonts >= 1 and n_chars >= CHAR_TEXT_THRESHOLD:
        return "TEXT"
    if n_chars < 20 and img_cover > 0.5:
        return "SCAN"
    return "AMBIGUOUS"


def probe(path: Path) -> dict:
    out: dict = {"file": path.name, "bytes": path.stat().st_size}

    doc = fitz.open(path)
    out["pages"] = doc.page_count

    # sample: middle page, plus first/last content pages for corroboration
    mid = doc.page_count // 2
    samples = sorted({1, mid, doc.page_count - 2})
    samples = [p for p in samples if 0 <= p < doc.page_count]
    out["sampled_pages_0based"] = samples

    doc_fonts: set[str] = set()
    per_page = []

    with pdfplumber.open(path) as plumb:
        for pno in samples:
            page = doc[pno]
            fonts = page.get_fonts(full=False)
            fnames = sorted({f[3] for f in fonts})
            doc_fonts.update(fnames)

            pp = plumb.pages[pno]
            text = pp.extract_text() or ""
            n_chars = len(text.strip())

            page_area = float(page.rect.width * page.rect.height) or 1.0
            img_area = 0.0
            n_imgs = 0
            for blk in page.get_text("dict").get("blocks", []):
                if blk.get("type") == 1:  # image block
                    n_imgs += 1
                    x0, y0, x1, y1 = blk["bbox"]
                    img_area += abs((x1 - x0) * (y1 - y0))
            img_cover = round(img_area / page_area, 3)

            drawings = page.get_drawings()
            n_lines = sum(
                1 for d in drawings for it in d.get("items", []) if it[0] == "l"
            )
            n_rects = sum(
                1 for d in drawings for it in d.get("items", []) if it[0] == "re"
            )

            per_page.append(
                {
                    "page_0based": pno,
                    "page_label": pno + 1,
                    "n_fonts": len(fnames),
                    "fonts": fnames,
                    "n_chars": n_chars,
                    "n_images": n_imgs,
                    "img_coverage": img_cover,
                    "n_vector_lines": n_lines,
                    "n_vector_rects": n_rects,
                    "verdict": classify(len(fnames), n_chars, img_cover),
                    "text_head": text.strip()[:400],
                }
            )

    doc.close()
    out["doc_fonts"] = sorted(doc_fonts)
    out["per_page"] = per_page
    verdicts = {p["verdict"] for p in per_page}
    out["file_verdict"] = (
        "TEXT" if verdicts == {"TEXT"} else "SCAN" if verdicts == {"SCAN"} else "MIXED/CHECK"
    )
    return out


def main() -> None:
    results = []
    for name in FILES:
        p = RAW / name
        if not p.exists():
            print(f"!! MISSING: {name}")
            continue
        results.append(probe(p))

    for r in results:
        print("=" * 78)
        print(f"{r['file']}   pages={r['pages']}  bytes={r['bytes']:,}")
        print(f"  FILE VERDICT: {r['file_verdict']}")
        print(f"  fonts across sampled pages ({len(r['doc_fonts'])}): {r['doc_fonts']}")
        for pg in r["per_page"]:
            print(
                f"  p{pg['page_label']:<4} verdict={pg['verdict']:<10} "
                f"fonts={pg['n_fonts']} chars={pg['n_chars']:<6} "
                f"imgs={pg['n_images']} imgcov={pg['img_coverage']:<6} "
                f"vlines={pg['n_vector_lines']} vrects={pg['n_vector_rects']}"
            )
    print("=" * 78)
    scans = [r["file"] for r in results if r["file_verdict"] != "TEXT"]
    print("FILES NEEDING OCR / REVIEW:", scans if scans else "none")

    outp = Path(__file__).resolve().parents[1] / "data" / "interim" / "phase1_triage.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("wrote", outp)


if __name__ == "__main__":
    sys.exit(main())
