"""PHASE 2b — full-file character-conservation audit, lattice flavour only.

Inspection only. **No extracted table data is written to disk.** The cache
(`data/interim/phase2b_audit.json`, gitignored) holds only loss metadata:
per-page character counts, the text-layer lines lattice FAILED to return, the
geometry of the ruled table box, and section-heading anchors. The extracted
cells themselves are used in memory and discarded.

Method
------
Three measurements per page, lattice only (word attribution is budgeted
against the character multiset rather than being a separate free-standing
measurement — see point 2):

1. **Character multiset** (the Phase 2 measure, reproduced verbatim so the
   sampled-page numbers in `reports/phase2_inspect.md` can be checked against
   this run):
       missing = Counter(page text layer) - Counter(all lattice cells)
       extra   = Counter(all lattice cells) - Counter(page text layer)
   Phase 2 discounted the bare page-number footer by subtracting its digits
   from the reference. That is kept as `*_disc` for comparability, but it is
   **not** the authoritative number here: on pages where the ruled box extends
   over the footer, camelot *does* return the page number, and the blind
   subtraction then manufactures a phantom `extra`. The authoritative numbers
   are `missing_raw` / `extra_raw`, measured against the untouched text layer,
   with the footer classified by geometry instead.

2. **Word attribution, budgeted against the multiset** — which text is
   missing, not just how many chars. Every text-layer word is consumed
   greedily against the multiset of cell tokens. A word not found as a token
   is not automatically a loss: it is only kept as a loss candidate if its own
   characters can be debited from the page's `missing_raw` character budget
   (built once from measurement 1, then spent word by word in reading order).
   If the word's characters are not actually missing, it is an attribution
   artifact, not a loss, and is dropped before geometry is even considered.
   This forgives two distinct false positives without a special case for
   either: camelot splitting a word with a cell-internal newline
   (`C\\nucumber` -> tokens `c` + `ucumber`, both present elsewhere in the
   multiset) and pdfplumber fusing horizontally overlapping glyph runs into a
   pseudo-word (fungicides p76: cell text "Leaf Blast" and the neighbouring
   dose "100" interleave into `1l0as0t`, matching no cell but also debiting
   nothing real). Whatever survives the budget is genuinely unaccounted for.

3. **Geometry** — each surviving word's bbox against the union of the camelot
   lattice table bboxes on that page (`Table._bbox`, pdfminer y-from-bottom,
   converted to pdfplumber top-down). This is what separates a benign loss
   from a real one, and it is not optional: a heading sitting above the ruled
   box is content lattice is *right* to drop, while the same characters missing
   from inside the box would be a dropped label claim. Each surviving line is
   placed in a zone relative to the box union: inside / above / below / beside.
   Inside-box words are attributed before out-of-box words (in case a heading
   word happens to also appear inside a cell nearby), so a loss is always
   charged to the region it geometrically belongs to.

Loss classes
------------
  benign-footer          bare page-number line, outside the ruled box
  benign-outside-table   heading line ABOVE the ruled box, few words, <=1
                         numeric token
  benign-no-table-page   page carries no ruled lines at all (the title +
                         contents page of each file); there is no table to
                         extract, so nothing is lost
  REAL                   inside the ruled box; or BELOW / BESIDE it; or above
                         it but shaped like table data. "Below the box" is
                         deliberately NOT benign — on fungicides p83 the
                         asterisk footnotes that qualify the seed-treatment
                         dose sit below the box, and calling them benign
                         because they are outside it would silently drop a
                         dose condition.

Section detection (requirement 4)
---------------------------------
Section headings in these files are the SAME 11pt Times as the body text, and
bold is not a discriminator (every chemical-name row is bold too). Nor is
geometry: "Approved Uses of Registered Insecticides" sits above the ruled box
on insecticides p2, but "Combination Product" (p56) and "PUBLIC HEALTH USE"
(p89) are INSIDE it and come back as ordinary cells. Section detection
therefore runs on the raw text layer, independent of camelot, using headings
anchored with `^...$` on the whitespace-stripped line.

The anchoring is the point. Phase 2 used a loose substring `search`, which
matched the phrase "Ready to use household insecticides" inside data cells and
invented HOUSEHOLD boundaries on insecticides p92/p95/p96/p97. It also can not
be replaced by trusting the file's own contents page: insecticides p1 lists
Public Health at printed page 85 and Locust at 105, but the actual headings are
on pages 89 and 109 — the contents page is stale by 3-4 pages.

Anchors are forward-filled from p2 (p1 is the title + contents page, and its
contents list names every section, so it must not set the fill state). A
heading found part-way down a page makes that page a BOUNDARY page carrying two
sections, recorded with the split y — a page-level section filter would either
leak public-health rows into crop advice or discard the crop rows above the
heading.

Usage
-----
  python tools/phase2b_audit.py audit    # parse + cache
  python tools/phase2b_audit.py report   # build reports/phase2b_full_audit.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, OrderedDict
from pathlib import Path

import camelot
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "cibrc"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

AUDIT_JSON = INTERIM / "phase2b_audit.json"

IN_SCOPE = [
    "insecticides_20260331.pdf",
    "fungicides_20260331.pdf",
    "bio_insecticides_20260331.pdf",
    "bio_fungicides_20260331.pdf",
]

# Pages the Phase 2 report sampled, used as a cross-check that this run
# reproduces the earlier numbers rather than quietly measuring something else.
PHASE2_SAMPLES = {
    "insecticides_20260331.pdf": {2: 36, 55: 0, 84: 0},
    "fungicides_20260331.pdf": {2: 0, 42: 0, 82: 0},
    "bio_insecticides_20260331.pdf": {2: 0, 10: 0, 18: 0},
    "bio_fungicides_20260331.pdf": {2: 0, 10: 0, 19: 0},
}

WS = re.compile(r"\s+")
FOOTER_RE = re.compile(r"^\(?\d{1,4}\)?$")

# Section heading vocabulary -> one of the four requested categories.
# Anchored with `fullmatch`-style tightness on the normalised heading line so a
# data cell reading "Ready to use household insecticides" cannot masquerade as
# the HOUSEHOLD INSECTICIDES section heading. Phase 2 used a loose `search`
# and picked up exactly that false boundary on insecticides p92/p95/p96/p97.
SECTION_HEADINGS = [
    # (category, subsection label, regex on the normalised heading line)
    ("crop-advisory", "agricultural-use",
     re.compile(r"^approvedusesofregisteredinsecticides$")),
    ("crop-advisory", "agricultural-use",
     re.compile(r"^agriculturaluse$")),
    ("crop-advisory", "combination-product",
     re.compile(r"^combinationproduct$")),
    ("crop-advisory", "fungicides-single",
     re.compile(r"^\d*\.?fungicidessingleproductformulationsuse$")),
    ("crop-advisory", "fungicides-combination",
     re.compile(r"^\d*\.?fungicidescombinationuses$")),
    ("crop-advisory", "bio-insecticides",
     re.compile(r"^\d*\.?majorusesofbio-?insecticides$")),
    ("crop-advisory", "bio-fungicides",
     re.compile(r"^\d*\.?majorusesofbio-?fungicides$")),
    ("public-health", "public-health-use",
     re.compile(r"^\d*\.?(insecticidesregisteredfor)?publichealthuses?$")),
    ("public-health", "public-health-use",
     re.compile(r"^\d*\.?majorusesofbio-?pesticidesforpublichealth$")),
    ("household", "household-insecticides",
     re.compile(r"^\d*\.?householdinsecticides$")),
    ("locust", "locust-control",
     re.compile(r"^\d*\.?recommendedchemicalsbyfaoforlocustcontrol$")),
]

CATEGORIES = ("crop-advisory", "public-health", "household", "locust")


def norm(s: object) -> str:
    return WS.sub("", str(s or "")).casefold()


def tokens(s: object) -> list[str]:
    """Cell -> normalised whitespace-separated tokens."""
    return [t for t in (WS.split(str(s or "").strip())) if t and norm(t)]


# --------------------------------------------------------------------------- #
# geometry
# --------------------------------------------------------------------------- #

def boxes_top_down(tables, height: float) -> list[tuple]:
    """camelot Table._bbox (y from bottom) -> (x0, top, x1, bottom)."""
    out = []
    for t in tables:
        x0, y0, x1, y1 = t._bbox
        out.append((float(x0), height - float(y1), float(x1), height - float(y0)))
    return out


def in_any_box(w: dict, boxes: list[tuple], pad: float = 2.0) -> bool:
    """Word centre inside any ruled-table box (padded for glyph overhang)."""
    cx = (w["x0"] + w["x1"]) / 2.0
    cy = (w["top"] + w["bottom"]) / 2.0
    for x0, top, x1, bottom in boxes:
        if x0 - pad <= cx <= x1 + pad and top - pad <= cy <= bottom + pad:
            return True
    return False


def group_lines(words: list[dict], tol: float = 3.0) -> list[dict]:
    """Cluster words into visual lines by `top`, left-to-right within a line."""
    if not words:
        return []
    ws = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines: list[list[dict]] = [[ws[0]]]
    for w in ws[1:]:
        if abs(w["top"] - lines[-1][0]["top"]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    out = []
    for grp in lines:
        grp.sort(key=lambda w: w["x0"])
        out.append({
            "text": " ".join(w["text"] for w in grp),
            "top": round(min(w["top"] for w in grp), 1),
            "bottom": round(max(w["bottom"] for w in grp), 1),
            "x0": round(min(w["x0"] for w in grp), 1),
            "x1": round(max(w["x1"] for w in grp), 1),
            "words": grp,
        })
    return out


# --------------------------------------------------------------------------- #
# per-page audit
# --------------------------------------------------------------------------- #

NUMERICISH = re.compile(r"^[\d.,%/+–—-]+$")


def page_has_table_rules(page) -> bool:
    """Does this page carry a ruled grid, i.e. is there a table to extract?

    A count of thin rects is not enough on its own: the title page's heading
    underlines are thin rects too (insecticides p1 has two, 157x1.1 and
    89x1.1). A grid needs rules in both directions, so require >=2 horizontal
    and >=2 vertical. Real table pages clear this by two orders of magnitude
    (283-388 thin rects); the title pages have zero vertical rules.
    """
    h = v = 0
    for r in list(page.rects) + list(page.lines):
        w, ht = float(r["width"]), float(r["height"])
        if ht < 2 and w > 50:
            h += 1
        elif w < 2 and ht > 20:
            v += 1
    return h >= 2 and v >= 2


def zone_of(line: dict, inside: bool, boxes: list[tuple]) -> str:
    """inside | above | below | beside — position relative to the box union."""
    if inside:
        return "inside"
    if not boxes:
        return "no-box"
    cy = (line["top"] + line["bottom"]) / 2.0
    if cy < min(b[1] for b in boxes):
        return "above"
    if cy > max(b[3] for b in boxes):
        return "below"
    return "beside"


def classify_line(line: dict, zone: str, has_rules: bool) -> str:
    """benign-* | REAL. Corroboration is applied later, by the caller."""
    txt = line["text"].strip()
    if zone == "no-box":
        # No ruled lines anywhere on the page => no table to extract.
        return "benign-no-table-page" if not has_rules else "REAL"
    if FOOTER_RE.match(txt):
        return "benign-footer"
    if zone == "inside":
        return "REAL"
    if zone == "above":
        n_num = sum(1 for w in line["words"] if NUMERICISH.match(w["text"]))
        if len(line["words"]) <= 12 and n_num <= 1:
            return "benign-outside-table"
        return "REAL"          # data-shaped above the box = missed table region
    return "REAL"              # below / beside: footnotes and stray columns


def audit_page(page, tables, page_no: int) -> dict:
    height = float(page.height)
    text = page.extract_text() or ""
    words = page.extract_words()
    boxes = boxes_top_down(tables, height)

    # --- 1. character multiset -------------------------------------------- #
    ref_raw = Counter(norm(text))
    cell_chars = Counter()
    cell_texts: list[str] = []
    for t in tables:
        for row in t.df.values.tolist():
            for cell in row:
                cell_texts.append(str(cell or ""))
                cell_chars.update(norm(cell))

    missing_raw = ref_raw - cell_chars
    extra_raw = cell_chars - ref_raw

    # Phase 2's footer-discounted variant, for comparability only.
    ref_disc = ref_raw.copy()
    for ch in norm(str(page_no)):
        if ref_disc[ch]:
            ref_disc[ch] -= 1
    missing_disc = ref_disc - cell_chars
    extra_disc = cell_chars - ref_disc

    # --- 2. word attribution ---------------------------------------------- #
    avail = Counter()
    for ct in cell_texts:
        avail.update(norm(t) for t in tokens(ct))

    # --- 3. geometry ------------------------------------------------------- #
    inside_flags = {id(w): in_any_box(w, boxes) for w in words}
    n_inside = sum(1 for w in words if inside_flags[id(w)])
    has_rules = page_has_table_rules(page)

    # Consumption order determines who gets to claim shared characters from
    # the page-level budget, so it must run most-certain-loss-first:
    #   1. the bare page-number footer — a near-certain loss, and one that
    #      must claim its OWN digits before anything else can. Getting this
    #      wrong is not hypothetical: on insecticides p90 the digits of a
    #      footer "90" were claimed by the unrelated inside-box word
    #      "(200mg/m" (which merely happens to contain a '0'), because that
    #      word was reached first and the budget has no memory of WHICH line
    #      a character came from.
    #   2. inside-box words — on insecticides p109 the heading word
    #      "Recommended" (above the box) would otherwise be matched against
    #      the cell reading "Fenitrothion is also recommended for ...",
    #      pushing the loss onto a table row instead of the heading.
    #   3. everything else outside the box.
    # See module docstring point 2 for why the budget check (not a plain
    # avail-token miss) is what decides real loss vs. attribution artifact.
    def is_footerish(w: dict) -> bool:
        return bool(FOOTER_RE.match(w["text"])) and w["top"] > height * 0.85

    footerish = [w for w in words if is_footerish(w)]
    footerish_ids = {id(w) for w in footerish}
    budget = missing_raw.copy()
    unmatched: list[dict] = []
    artifact_words: list[dict] = []
    corr: dict[int, int] = {}
    ordered = (footerish
               + [w for w in words if inside_flags[id(w)]
                  and id(w) not in footerish_ids]
               + [w for w in words if not inside_flags[id(w)]
                  and id(w) not in footerish_ids])
    for w in ordered:
        nw = norm(w["text"])
        if not nw:
            continue
        if avail[nw] > 0:
            avail[nw] -= 1
            continue
        overlap = Counter(nw) & budget
        n_corr = sum(overlap.values())
        if n_corr == 0:
            artifact_words.append(w)
            continue
        budget -= overlap
        corr[id(w)] = n_corr
        unmatched.append(w)

    # --- 4. render each surviving line as it is actually printed ----------- #
    # Verbatim text-layer lines, so the report can quote what is missing as it
    # is printed rather than as the leftovers of multiset consumption: on
    # insecticides p2 the heading loses "of" to another cell and would read
    # "Approved Uses Registered Insecticides" without this.
    text_lines = [{"text": tl["text"].strip(),
                   "top": float(tl["top"]), "bottom": float(tl["bottom"])}
                  for tl in page.extract_text_lines()]

    def source_line(line: dict) -> str:
        cy = (line["top"] + line["bottom"]) / 2.0
        for tl in text_lines:
            if tl["top"] - 2 <= cy <= tl["bottom"] + 2:
                return tl["text"]
        return line["text"]

    losses = []
    for line in group_lines(unmatched):
        inside = any(inside_flags[id(w)] for w in line["words"])
        zone = zone_of(line, inside, boxes)
        cls = classify_line(line, zone, has_rules)
        n_chars = sum(len(norm(w["text"])) for w in line["words"])
        n_corr = sum(corr.get(id(w), 0) for w in line["words"])
        losses.append({
            "text": line["text"],
            "source_line": source_line(line),
            "top": line["top"], "bottom": line["bottom"],
            "x0": line["x0"], "x1": line["x1"],
            "inside_box": inside,
            "zone": zone,
            "chars": n_chars,
            "chars_corroborated": n_corr,
            "class": cls,
        })

    out_words = [w for w in words if not inside_flags[id(w)]]
    out_lines = [{"text": l["text"], "top": l["top"], "bottom": l["bottom"]}
                 for l in group_lines(out_words)]

    # Section anchors come from the RAW TEXT LAYER, not from out-of-box lines:
    # several real headings sit inside the ruled box (see module docstring).
    anchors = []
    for tl in page.extract_text_lines():
        nl = norm(tl["text"])
        for cat, sub, pat in SECTION_HEADINGS:
            if pat.match(nl):
                top = round(float(tl["top"]), 1)
                # Is there table content ABOVE this heading? That, not an
                # arbitrary y threshold, is what makes the page a boundary
                # page carrying two sections. fungicides p2's heading sits at
                # y=107 with nothing above it — first page of a section, not a
                # split.
                above = sum(1 for w in words
                            if inside_flags[id(w)] and w["bottom"] < top - 2)
                anchors.append({"category": cat, "subsection": sub,
                                "heading": tl["text"].strip(), "top": top,
                                "table_words_above": above})
                break
    anchors.sort(key=lambda a: a["top"])

    # missing chars decomposed by zone, so the benign/REAL split is quantified.
    # (Attribution artifacts never reach `losses` — they are filtered out of
    # `unmatched` above, before grouping — so no class filter is needed here.)
    by_zone: dict[str, int] = {}
    for l in losses:
        by_zone[l["zone"]] = by_zone.get(l["zone"], 0) + l["chars_corroborated"]

    return {
        "has_rules": has_rules,
        "missing_by_zone": by_zone,
        "missing_unattributed": sum(budget.values()),
        "page": page_no,
        "height": round(height, 1),
        "ntables": len(tables),
        "shapes": [list(t.df.shape) for t in tables],
        "boxes": [[round(v, 1) for v in b] for b in boxes],
        "textchars_raw": sum(ref_raw.values()),
        "cellchars": sum(cell_chars.values()),
        "missing_raw": sum(missing_raw.values()),
        "extra_raw": sum(extra_raw.values()),
        "missing_disc": sum(missing_disc.values()),
        "extra_disc": sum(extra_disc.values()),
        "missing_chars_detail": "".join(sorted(missing_raw.elements()))[:400],
        "extra_chars_detail": "".join(sorted(extra_raw.elements()))[:400],
        "nwords": len(words),
        "nwords_inside_box": n_inside,
        "artifact_word_count": len(artifact_words),
        "artifact_words": sorted({w["text"] for w in artifact_words})[:20],
        "losses": losses,
        "out_of_box_lines": out_lines,
        "anchors": anchors,
    }


def audit_file(name: str) -> dict:
    path = RAW / name
    t0 = time.time()
    with pdfplumber.open(path) as pdf:
        npages = len(pdf.pages)
        tl = camelot.read_pdf(str(path), pages=f"1-{npages}", flavor="lattice")
        by: dict[int, list] = {}
        for t in tl:
            by.setdefault(int(t.page), []).append(t)
        print(f"  {name}: {len(tl)} lattice tables over "
              f"{len(by)}/{npages} pages, {time.time()-t0:.1f}s", flush=True)
        pages = [audit_page(pdf.pages[p - 1], by.get(p, []), p)
                 for p in range(1, npages + 1)]
    print(f"  {name}: audited {npages} pages, {time.time()-t0:.1f}s", flush=True)
    return {"file": name, "pages": npages, "page_audits": pages}


# --------------------------------------------------------------------------- #
# section ranges
# --------------------------------------------------------------------------- #

def section_map(rec: dict) -> dict:
    """Forward-fill anchors into a per-page section, then compress to ranges."""
    per_page = []
    cur_cat, cur_sub = "unclassified", "unclassified"
    for pa in rec["page_audits"]:
        p = pa["page"]
        anchors = pa["anchors"]
        if p == 1:
            # Title + contents page. Its contents list names every section, so
            # it must not be allowed to set the forward-fill state.
            per_page.append({"page": p, "section": "front-matter",
                             "subsection": "front-matter",
                             "boundary": False, "anchors": []})
            continue
        entering = cur_cat
        if anchors:
            # the LAST heading on the page is the one that continues onto p+1
            last = anchors[-1]
            cur_cat, cur_sub = last["category"], last["subsection"]
            # A boundary page is one with table rows ABOVE the heading that
            # belong to the OUTGOING section.
            boundary = (last.get("table_words_above", 0) > 0
                        and entering not in (None, "unclassified", cur_cat))
            per_page.append({
                "page": p,
                "section": cur_cat,
                "subsection": cur_sub,
                "boundary": bool(boundary),
                "section_above_split": entering if boundary else None,
                "split_top": last["top"] if boundary else None,
                "anchors": [{"heading": a["heading"], "top": a["top"],
                             "category": a["category"]} for a in anchors],
            })
        else:
            per_page.append({"page": p, "section": cur_cat,
                             "subsection": cur_sub,
                             "boundary": False, "anchors": []})

    ranges = []
    for row in per_page:
        if ranges and ranges[-1]["section"] == row["section"] \
                and ranges[-1]["subsection"] == row["subsection"]:
            ranges[-1]["last_page"] = row["page"]
        else:
            ranges.append({"section": row["section"],
                           "subsection": row["subsection"],
                           "first_page": row["page"], "last_page": row["page"]})

    by_cat: dict[str, list[list[int]]] = {}
    for r in ranges:
        by_cat.setdefault(r["section"], []).append([r["first_page"], r["last_page"]])

    return {"per_page": per_page, "ranges": ranges, "by_category": by_cat}


# --------------------------------------------------------------------------- #
# stages
# --------------------------------------------------------------------------- #

def stage_audit() -> None:
    INTERIM.mkdir(parents=True, exist_ok=True)
    out = []
    for name in IN_SCOPE:
        print(f"== {name}", flush=True)
        rec = audit_file(name)
        rec["sections"] = section_map(rec)
        out.append(rec)
    AUDIT_JSON.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {AUDIT_JSON}")

    # --- console summary, so a bad run is obvious before the report ------- #
    print("\n=== per-file totals (lattice) ===")
    for rec in out:
        pas = rec["page_audits"]
        real = [pa for pa in pas
                if any(l["class"] == "REAL" for l in pa["losses"])]
        print(f"{rec['file']:<34} pages={rec['pages']:>4} "
              f"missing_raw_tot={sum(pa['missing_raw'] for pa in pas):>6} "
              f"extra_raw_tot={sum(pa['extra_raw'] for pa in pas):>5} "
              f"pages_with_REAL={len(real):>3}")

    print("\n=== Phase 2 cross-check (missing, footer-discounted) ===")
    for rec in out:
        exp = PHASE2_SAMPLES.get(rec["file"], {})
        for pa in rec["page_audits"]:
            if pa["page"] in exp:
                got, want = pa["missing_disc"], exp[pa["page"]]
                print(f"  {rec['file']:<34} p{pa['page']:<4} phase2={want:<5} "
                      f"phase2b={got:<5} {'OK' if got == want else 'MISMATCH'}")

    print("\n=== REAL losses ===")
    for rec in out:
        for pa in rec["page_audits"]:
            reals = [l for l in pa["losses"] if l["class"] == "REAL"]
            if reals:
                print(f"--- {rec['file']} p{pa['page']} "
                      f"(ntables={pa['ntables']}, missing_raw={pa['missing_raw']}, "
                      f"by_zone={pa['missing_by_zone']}, "
                      f"unattributed={pa['missing_unattributed']})")
                for l in reals:
                    print(f"      zone={l['zone']:<7} corr={l['chars_corroborated']:>4}"
                          f"/{l['chars']:<4} :: {l['text']!r}")

    print("\n=== class histogram ===")
    hist: Counter = Counter()
    for rec in out:
        for pa in rec["page_audits"]:
            for l in pa["losses"]:
                hist[l["class"]] += 1
    for k, v in hist.most_common():
        print(f"  {k:<24} {v}")

    print("\n=== unattributed missing chars (should be ~0) ===")
    for rec in out:
        tot = sum(pa["missing_unattributed"] for pa in rec["page_audits"])
        worst = sorted(rec["page_audits"],
                       key=lambda pa: -pa["missing_unattributed"])[:3]
        print(f"  {rec['file']:<34} total={tot:<6} worst="
              + ", ".join(f"p{pa['page']}:{pa['missing_unattributed']}" for pa in worst))

    print("\n=== section ranges ===")
    for rec in out:
        print(f"--- {rec['file']}")
        for r in rec["sections"]["ranges"]:
            print(f"      {r['section']:<14} {r['subsection']:<24} "
                  f"p{r['first_page']}-p{r['last_page']}")


def load() -> list[dict]:
    if not AUDIT_JSON.exists():
        sys.exit(f"missing {AUDIT_JSON}; run: python tools/phase2b_audit.py audit")
    return json.loads(AUDIT_JSON.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["audit", "report"])
    args = ap.parse_args()
    if args.stage == "audit":
        stage_audit()
    else:
        from phase2b_report import build_report  # noqa: PLC0415
        build_report(load())


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
