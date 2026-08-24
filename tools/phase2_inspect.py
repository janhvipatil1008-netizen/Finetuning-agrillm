"""PHASE 2 (Inspect & Audit) — camelot flavour comparison on the 4 in-scope PDFs.

Inspection only. Writes NO extracted table data to disk; the only artefacts are
an inspection-metadata cache (shapes + first/last row per page, needed to pick
page-boundary samples) and the human-readable report.

Stages
------
  census   parse every page of every in-scope file in BOTH flavours, recording
           shape / accuracy / whitespace / first row / last row. Cached to JSON.
  report   build reports/phase2_inspect.md from the census plus targeted
           deep-dives (verbatim headers, p55 row-level diff, page-order proof).

Usage
-----
  python tools/phase2_inspect.py census
  python tools/phase2_inspect.py report
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import camelot
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "cibrc"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

IN_SCOPE = [
    "insecticides_20260331.pdf",
    "fungicides_20260331.pdf",
    "bio_insecticides_20260331.pdf",
    "bio_fungicides_20260331.pdf",
]

ARCHIVED = ["herbicides_20260331.pdf", "pgr_20260331.pdf"]

FLAVOURS = ("lattice", "stream")

CENSUS_JSON = INTERIM / "phase2_census.json"

# pages used for the character-conservation audit: first / middle / last table
# page of each in-scope file
LOSS_TARGETS = {
    "insecticides_20260331.pdf": [2, 55, 84],
    "fungicides_20260331.pdf": [2, 42, 82],
    "bio_insecticides_20260331.pdf": [2, 10, 18],
    "bio_fungicides_20260331.pdf": [2, 10, 19],
}

# Section markers, so we can tell crop-advisory tables from public-health /
# household / locust tables that must never be ingested as crop advice.
SECTION_PATTERNS = [
    ("AGRI", re.compile(r"approved uses of registered insecticides|agricultural use", re.I)),
    ("COMBINATION", re.compile(r"combination product|combination uses|insecticides combination", re.I)),
    ("PUBLIC_HEALTH", re.compile(r"public health use", re.I)),
    ("HOUSEHOLD", re.compile(r"household insecticides|household use", re.I)),
    ("LOCUST", re.compile(r"locust control", re.I)),
    ("BIO_FUNGI", re.compile(r"major uses of bio-?fungicides", re.I)),
    ("BIO_INSECT", re.compile(r"major uses of bio-?insecticides", re.I)),
    ("FUNGI_SINGLE", re.compile(r"fungicides single product formulations", re.I)),
    ("FUNGI_COMBO", re.compile(r"fungicides combination uses", re.I)),
]


def vis(s: str) -> str:
    """Make a cell printable in markdown while keeping content verbatim.

    Newlines inside a camelot cell are the single most important signal in this
    audit (they mark wrapped text), so they are shown as a visible glyph rather
    than dropped.
    """
    if s is None:
        return ""
    return str(s).replace("\r", "").replace("\n", "↵").replace("|", "\\|")


def is_blank(s: object) -> bool:
    return not str(s or "").strip()


# --------------------------------------------------------------------------- #
# census
# --------------------------------------------------------------------------- #

def census_file(name: str) -> dict:
    path = RAW / name
    rec: dict = {"file": name, "flavours": {}}

    with pdfplumber.open(path) as pdf:
        rec["pages"] = len(pdf.pages)
        sections = {}
        for i, pg in enumerate(pdf.pages, start=1):
            txt = pg.extract_text() or ""
            hits = [tag for tag, pat in SECTION_PATTERNS if pat.search(txt)]
            if hits:
                sections[str(i)] = hits
        rec["section_markers"] = sections

    for flavour in FLAVOURS:
        t0 = time.time()
        pages_meta: list[dict] = []
        order: list[int] = []
        err = None
        try:
            tables = camelot.read_pdf(
                str(path), pages=f"2-{rec['pages']}", flavor=flavour
            )
            for t in tables:
                df = t.df
                order.append(int(t.page))
                pages_meta.append(
                    {
                        "page": int(t.page),
                        "rows": int(df.shape[0]),
                        "cols": int(df.shape[1]),
                        "accuracy": t.parsing_report.get("accuracy"),
                        "whitespace": t.parsing_report.get("whitespace"),
                        "order_index": t.parsing_report.get("order"),
                        "first_row": [str(x) for x in df.iloc[0].tolist()],
                        "last_row": [str(x) for x in df.iloc[-1].tolist()],
                    }
                )
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"

        rec["flavours"][flavour] = {
            "error": err,
            "elapsed_s": round(time.time() - t0, 1),
            "n_tables": len(pages_meta),
            "page_order_returned": order,
            "page_order_is_sorted": order == sorted(order),
            "tables": pages_meta,
        }
        print(
            f"  [{name}] {flavour}: {len(pages_meta)} tables in "
            f"{rec['flavours'][flavour]['elapsed_s']}s "
            f"sorted={rec['flavours'][flavour]['page_order_is_sorted']} err={err}"
        )
    return rec


def run_census() -> None:
    INTERIM.mkdir(parents=True, exist_ok=True)
    out = []
    for name in IN_SCOPE:
        print(f"== census {name}")
        out.append(census_file(name))
    CENSUS_JSON.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", CENSUS_JSON)


# --------------------------------------------------------------------------- #
# report helpers
# --------------------------------------------------------------------------- #

def md_table(rows: list[list[str]], head: list[str]) -> list[str]:
    out = ["| " + " | ".join(head) + " |",
           "|" + "|".join(["---"] * len(head)) + "|"]
    for r in rows:
        cells = [vis(c) for c in r]
        cells += [""] * (len(head) - len(cells))
        out.append("| " + " | ".join(cells[: len(head)]) + " |")
    return out


def grab(name: str, page: int, flavour: str):
    """Return list of camelot Tables for one page."""
    try:
        return list(
            camelot.read_pdf(str(RAW / name), pages=str(page), flavor=flavour)
        )
    except Exception as e:  # noqa: BLE001
        print(f"   !! grab {name} p{page} {flavour}: {e}")
        return []


def dump_rows(tabs, limit: int | None, label: str) -> list[str]:
    """Render every row of every table on a page as a fenced verbatim block."""
    lines = [f"```text", f"# {label}"]
    if not tabs:
        lines += ["<no table returned>", "```"]
        return lines
    for ti, t in enumerate(tabs):
        df = t.df
        lines.append(f"# table[{ti}] shape={df.shape} page={t.page}")
        n = df.shape[0] if limit is None else min(limit, df.shape[0])
        for ri in range(n):
            cells = [str(x) for x in df.iloc[ri].tolist()]
            rendered = " ‖ ".join(c.replace("\n", "↵") for c in cells)
            lines.append(f"r{ri:<3}| {rendered}")
        if limit is not None and df.shape[0] > n:
            lines.append(f"... ({df.shape[0] - n} more rows)")
    lines.append("```")
    return lines


def classify_stream_rows(df) -> dict:
    """Naive mechanical rule: blank leading cell => continuation.

    Kept because it is the heuristic a Phase 3 parser would reach for first, and
    the point of this audit is to show where it fails. Compare against
    align_rows(), which is the trustworthy analysis.
    """
    buckets = {"continuation": [], "distinct": [], "full_width": [], "empty": []}
    for ri in range(df.shape[0]):
        cells = [str(x) for x in df.iloc[ri].tolist()]
        populated = [i for i, c in enumerate(cells) if not is_blank(c)]
        if not populated:
            buckets["empty"].append((ri, cells))
        elif len(populated) == 1:
            buckets["full_width"].append((ri, cells))
        elif is_blank(cells[0]):
            buckets["continuation"].append((ri, cells))
        elif len(cells) > 1 and not is_blank(cells[0]) and not is_blank(cells[1]):
            buckets["distinct"].append((ri, cells))
        else:
            buckets["continuation"].append((ri, cells))
    return buckets


def norm(s: str) -> str:
    """Whitespace-insensitive normalisation for content-conservation tests."""
    return re.sub(r"\s+", "", str(s or "")).lower()


def row_text(df, ri: int) -> str:
    return norm(" ".join(str(x) for x in df.iloc[ri].tolist()))


def content_conservation(lat_df, strm_df) -> dict:
    """Do both flavours recover the SAME characters, just segmented differently?

    This is the decisive test. If the concatenated normalised text of every
    lattice cell equals that of every stream cell, then lattice cannot have
    'merged away' any entry stream found — the only difference is where row
    boundaries were drawn.
    """
    lat = "".join(row_text(lat_df, i) for i in range(lat_df.shape[0]))
    strm = "".join(row_text(strm_df, i) for i in range(strm_df.shape[0]))
    out = {
        "lattice_chars": len(lat),
        "stream_chars": len(strm),
        "identical": lat == strm,
        "same_multiset": Counter(lat) == Counter(strm),
        "only_in_lattice": "".join(
            sorted((Counter(lat) - Counter(strm)).elements())
        )[:200],
        "only_in_stream": "".join(
            sorted((Counter(strm) - Counter(lat)).elements())
        )[:200],
    }
    if lat != strm:
        i = 0
        while i < min(len(lat), len(strm)) and lat[i] == strm[i]:
            i += 1
        out["first_divergence_at"] = i
        out["lattice_around"] = lat[max(0, i - 60): i + 60]
        out["stream_around"] = strm[max(0, i - 60): i + 60]
    return out


def align_rows(lat_df, strm_df) -> list[dict]:
    """Map each stream physical row to the lattice row that contains its content.

    Per-cell containment, not whole-row substring. The earlier whole-row approach
    was wrong: lattice and stream emit the *same characters in a different order*
    within a wrapped row (lattice keeps 'Thrips,↵Whitefly' together, stream emits
    'Thrips,' then the numbers then 'Whitefly'), so no whole-row substring test
    can align them.

    For each stream row, score every lattice row by how many of the stream row's
    non-empty cells appear inside it; assign to the best scorer, preferring the
    earliest row on ties and never moving backwards past an already-anchored row.
    """
    lat_texts = [row_text(lat_df, i) for i in range(lat_df.shape[0])]
    assign: list[dict] = []
    lo = 0
    for si in range(strm_df.shape[0]):
        cells = [str(x) for x in strm_df.iloc[si].tolist()]
        parts = [norm(c) for c in cells if not is_blank(c)]
        if not parts:
            assign.append({"stream_row": si, "lattice_row": None,
                           "matched": 0, "n_parts": 0, "cells": cells})
            continue
        best, best_score = None, -1
        for li in range(lo, len(lat_texts)):
            score = sum(1 for p in parts if p and p in lat_texts[li])
            if score > best_score:
                best, best_score = li, score
        full = best_score == len(parts)
        if full and best is not None:
            lo = best  # monotonic progression, allow repeats within a row
        assign.append({"stream_row": si, "lattice_row": best,
                       "matched": best_score, "n_parts": len(parts),
                       "fully_accounted": full, "cells": cells})
    return assign


def analyse_extras(lat_df, strm_df, assign) -> dict:
    """Bucket stream rows: anchors, fragments, and genuinely-lost entries."""
    groups: dict[int, list[dict]] = {}
    for a in assign:
        groups.setdefault(a["lattice_row"], []).append(a)

    extras: list[dict] = []
    for li, members in groups.items():
        for a in members[1:]:
            extras.append(a)

    blank_lead = [a for a in extras if is_blank(a["cells"][0])]
    pop_lead = [a for a in extras if not is_blank(a["cells"][0])]

    # A stream row is only evidence of a LOST entry if NO lattice row on the
    # page accounts for all of its cell contents.
    lat_texts = [row_text(lat_df, i) for i in range(lat_df.shape[0])]
    lost = []
    for a in extras:
        parts = [norm(c) for c in a["cells"] if not is_blank(c)]
        if not parts:
            continue
        if not any(all(p in lt for p in parts) for lt in lat_texts):
            lost.append(a)

    return {
        "n_extra": len(extras),
        "blank_leading_cell": blank_lead,
        "populated_leading_cell": pop_lead,
        "unaccounted_rows": lost,
        "groups": groups,
    }


def pick_boundary_pair(rec: dict, flavour: str) -> tuple[int, int] | None:
    """Find (N, N+1) where N+1's first row has a blank leading cell.

    That is exactly the forward-fill hazard: the chemical/crop name lives on
    page N and page N+1 opens mid-block with nothing to inherit from.
    """
    tabs = {t["page"]: t for t in rec["flavours"][flavour]["tables"]}
    for pg in sorted(tabs):
        nxt = tabs.get(pg + 1)
        if not nxt:
            continue
        fr = nxt["first_row"]
        if fr and is_blank(fr[0]):
            return pg, pg + 1
    return None


def stratified_pages(rec: dict, flavour: str) -> dict:
    """page 1 (=2, first table page), middle, boundary pair, final content page."""
    n = rec["pages"]
    tabs = sorted(t["page"] for t in rec["flavours"][flavour]["tables"])
    first = tabs[0] if tabs else 2
    last = tabs[-1] if tabs else n
    mid = tabs[len(tabs) // 2] if tabs else n // 2
    pair = pick_boundary_pair(rec, flavour)
    return {"first": first, "middle": mid, "final": last, "boundary_pair": pair}


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #

def build_report() -> None:
    census = json.loads(CENSUS_JSON.read_text(encoding="utf-8"))
    by_name = {r["file"]: r for r in census}
    L: list[str] = []
    A = L.append

    A("# Phase 2 — Inspect & Audit (CIB&RC registers, edition 2026-03-31)")
    A("")
    A("Inspection only. **No extracted table data was written to disk.** The only")
    A("artefacts are this report and an inspection-metadata cache")
    A("(`data/interim/phase2_census.json`, gitignored) holding per-page shapes and")
    A("first/last rows, which is what the page-boundary sampling needed.")
    A("")
    A("Generated by `tools/phase2_inspect.py`. camelot 2.0.0, opencv 5.0.0, pdfium")
    A("rasterisation (no Ghostscript). In every verbatim dump below, a newline")
    A("*inside* one camelot cell is shown as `↵` and the cell separator is `‖`.")
    A("Cell content is otherwise unmodified.")
    A("")

    # ---------------- scope ----------------
    A("## 0. Scope")
    A("")
    A("| file | pages | status |")
    A("|---|---|---|")
    for n in IN_SCOPE:
        A(f"| `{n}` | {by_name[n]['pages']} | **PARSE** |")
    for n in ARCHIVED:
        A(f"| `{n}` | — | **ARCHIVED — not parsed, not opened in this phase** |")
    A("")

    # ---------------- section map ----------------
    A("### 0.1 Section map — not every page is crop advisory")
    A("")
    A("Detected from page text. This matters more than it looks: the insecticide")
    A("register continues past the crop tables into public-health, household and")
    A("locust tables that share a similar shape. Ingesting those as crop advice")
    A("would put mosquito-coil and rodenticide doses into a farm advisory.")
    A("")
    for n in IN_SCOPE:
        rec = by_name[n]
        A(f"**`{n}`** ({rec['pages']} pages)")
        A("")
        marks = rec["section_markers"]
        if not marks:
            A("- no section markers matched")
        else:
            for pg in sorted(marks, key=lambda x: int(x)):
                A(f"- p{pg}: {', '.join(marks[pg])}")
        A("")

    # ---------------- page order ----------------
    A("## 3. Page-order verification (requirement 3)")
    A("")
    A("Each file was parsed in a **single** multi-page `read_pdf(pages='2-N')`")
    A("call per flavour, then the returned `Table.page` values were compared")
    A("against their sorted order. This is the real question for Phase 3: if")
    A("order were not guaranteed, a forward-fill would carry a chemical name")
    A("backwards across pages.")
    A("")
    A("| file | flavour | tables returned | page sequence sorted? |")
    A("|---|---|---|---|")
    for n in IN_SCOPE:
        for f in FLAVOURS:
            fl = by_name[n]["flavours"][f]
            A(
                f"| `{n}` | {f} | {fl['n_tables']} | "
                f"**{'YES' if fl['page_order_is_sorted'] else 'NO'}** |"
            )
    A("")
    A("Also recorded per table: camelot's own `order` field within a page")
    A("(`parsing_report['order']`), so multiple tables on one page stay ordered.")
    A("")

    # ---------------- shape census ----------------
    A("## 6. Shape census — ALL pages, both flavours (requirement 6)")
    A("")
    for n in IN_SCOPE:
        rec = by_name[n]
        A(f"### `{n}` — {rec['pages']} pages")
        A("")
        for f in FLAVOURS:
            fl = rec["flavours"][f]
            if fl["error"]:
                A(f"- **{f}: ERROR** {fl['error']}")
                continue
            cols = Counter(t["cols"] for t in fl["tables"])
            shapes = Counter((t["rows"], t["cols"]) for t in fl["tables"])
            mode_cols = cols.most_common(1)[0][0] if cols else None
            off = [t["page"] for t in fl["tables"] if t["cols"] != mode_cols]
            A(f"**{f}** — {fl['n_tables']} tables, {fl['elapsed_s']}s")
            A("")
            A(f"- column-count histogram: "
              f"{dict(sorted(cols.items()))}  → **mode = {mode_cols} cols**")
            A(f"- pages whose column count differs from mode "
              f"({len(off)}): {off if off else 'none'}")
            top = ", ".join(f"{s}×{c}" for s, c in shapes.most_common(12))
            A(f"- top (rows,cols) shapes: {top}")
            A("")
        A("")

    # ---------------- headers ----------------
    A("## 4 & 8. Verbatim header rows, column count, and units")
    A("")
    A("Header rows are printed exactly as camelot returns them from the **first**")
    A("table page of each file, both flavours.")
    A("")
    for n in IN_SCOPE:
        rec = by_name[n]
        strat = stratified_pages(rec, "lattice")
        pg = strat["first"]
        A(f"### `{n}` — header from p{pg}")
        A("")
        for f in FLAVOURS:
            tabs = grab(n, pg, f)
            L.extend(dump_rows(tabs, 6, f"{n} p{pg} flavour={f} (first 6 rows)"))
            A("")
        A("")

    # ---------------- stratified samples ----------------
    A("## 1 & 5. Stratified page samples + 6 representative rows per file")
    A("")
    A("Stratification per requirement 1: first table page, a middle page, a page")
    A("pair spanning a chemical-block break, and the final content page. For the")
    A("two bio files (19 and 20 pages) the same four strata are used — they just")
    A("land closer together (requirement 10).")
    A("")
    for n in IN_SCOPE:
        rec = by_name[n]
        strat = stratified_pages(rec, "lattice")
        A(f"### `{n}`")
        A("")
        A(f"- first table page: **p{strat['first']}**")
        A(f"- middle page: **p{strat['middle']}**")
        A(f"- final content page: **p{strat['final']}**")
        A(f"- block-break page pair: **{strat['boundary_pair']}**")
        A("")
        for label, pg in (("middle", strat["middle"]), ("final", strat["final"])):
            for f in FLAVOURS:
                tabs = grab(n, pg, f)
                L.extend(
                    dump_rows(tabs, 6, f"{n} p{pg} ({label}) flavour={f} — 6 rows")
                )
                A("")
        A("")

    # ---------------- page boundary ----------------
    A("## 9. Page-boundary sample — the forward-fill hazard (requirement 9)")
    A("")
    A("For each file: last 3 rows of page N, then first 3 rows of page N+1, so the")
    A("blank leading cell at the top of N+1 is directly visible.")
    A("")
    for n in IN_SCOPE:
        rec = by_name[n]
        pair = pick_boundary_pair(rec, "lattice")
        A(f"### `{n}` — pair {pair}")
        A("")
        if not pair:
            A("_no page pair found whose first row has a blank leading cell_")
            A("")
            continue
        pN, pN1 = pair
        for f in FLAVOURS:
            for pg, which, tail in ((pN, "N", True), (pN1, "N+1", False)):
                tabs = grab(n, pg, f)
                if not tabs:
                    A(f"```text\n# {n} p{pg} {f}: no table\n```")
                    continue
                df = tabs[0].df
                lines = ["```text",
                         f"# {n} p{pg} ({which}) flavour={f} shape={df.shape} "
                         f"— {'LAST 3' if tail else 'FIRST 3'} rows"]
                idxs = (
                    range(max(0, df.shape[0] - 3), df.shape[0])
                    if tail
                    else range(min(3, df.shape[0]))
                )
                for ri in idxs:
                    cells = [str(x) for x in df.iloc[ri].tolist()]
                    lines.append(
                        f"r{ri:<3}| "
                        + " ‖ ".join(c.replace("\n", "↵") for c in cells)
                    )
                    if not tail and ri == 0:
                        lines.append(
                            f"      ^ leading cell blank? "
                            f"{is_blank(cells[0])}"
                        )
                lines.append("```")
                L.extend(lines)
                A("")
        A("")

    # ---------------- p55 deep dive ----------------
    A("## 2 & 7. Insecticides p55 — lattice vs stream, evidence first")
    A("")
    lat = grab("insecticides_20260331.pdf", 55, "lattice")
    strm = grab("insecticides_20260331.pdf", 55, "stream")
    lat_rows = sum(t.df.shape[0] for t in lat)
    strm_rows = sum(t.df.shape[0] for t in strm)
    A("### Physical row counts (requirement 2)")
    A("")
    A("| flavour | tables on page | total physical rows | shapes |")
    A("|---|---|---|---|")
    A(f"| lattice | {len(lat)} | **{lat_rows}** | "
      f"{[tuple(t.df.shape) for t in lat]} |")
    A(f"| stream | {len(strm)} | **{strm_rows}** | "
      f"{[tuple(t.df.shape) for t in strm]} |")
    A("")
    A("Deliberately **not** using camelot's accuracy score, per requirement 2.")
    A("")

    A("### Full verbatim dump — lattice")
    A("")
    L.extend(dump_rows(lat, None, "insecticides p55 LATTICE — every row"))
    A("")
    A("### Full verbatim dump — stream")
    A("")
    L.extend(dump_rows(strm, None, "insecticides p55 STREAM — every row"))
    A("")

    A("### Content-conservation test — did lattice lose anything at all?")
    A("")
    A("Before classifying rows, the decisive check: concatenate the normalised")
    A("(whitespace-stripped, lowercased) text of **every** cell from each flavour")
    A("and compare. If the two strings are identical, lattice cannot have merged")
    A("away an entry that stream found — the flavours differ only in where row")
    A("boundaries were drawn, not in what text was recovered.")
    A("")
    if lat and strm:
        cc = content_conservation(lat[0].df, strm[0].df)
        A("| measure | value |")
        A("|---|---|")
        A(f"| lattice normalised chars | {cc['lattice_chars']} |")
        A(f"| stream normalised chars | {cc['stream_chars']} |")
        A(f"| byte-identical (same order)? | {cc['identical']} |")
        A(f"| **same character multiset (same content)?** | "
          f"**{cc['same_multiset']}** |")
        A(f"| characters present only in lattice | `{cc['only_in_lattice']}` |")
        A(f"| characters present only in stream | `{cc['only_in_stream']}` |")
        A("")
        if not cc["identical"]:
            A("The two strings hold the **same characters in a different order**.")
            A("That is the whole story of this page. Example divergence:")
            A("")
            A("```text")
            A(f"first divergence at char {cc['first_divergence_at']}")
            A(f"lattice: ...{cc['lattice_around']}...")
            A(f"stream : ...{cc['stream_around']}...")
            A("```")
            A("")
            A("Lattice keeps the wrapped pest cell whole (`thrips,whitefly`) and")
            A("then the numbers. Stream emits `thrips,`, then the numbers, then")
            A("`whitefly` on a later physical row — so the wrapped tail is")
            A("separated from its own row by four numeric cells.")
            A("")

    A("### Row alignment — which stream rows are the 'extra' ones (requirement 7)")
    A("")
    A("Each stream row is assigned to the lattice row that contains its cell")
    A("contents, scored **per cell**. (A whole-row substring match cannot work")
    A("here: as shown above the two flavours emit the same characters in a")
    A("different order within a wrapped row.) A stream row counts as *extra*")
    A("when an earlier stream row already anchored the same lattice row.")
    A("")
    if lat and strm:
        assign = align_rows(lat[0].df, strm[0].df)
        ax = analyse_extras(lat[0].df, strm[0].df, assign)
        A("```text")
        A("stream_row -> lattice_row   (matched cells / total non-empty cells)")
        for a in assign:
            lr = "NONE" if a["lattice_row"] is None else f"L{a['lattice_row']}"
            A(
                f"s{a['stream_row']:<3} -> {lr:<5} "
                f"({a['matched']}/{a['n_parts']}) | "
                + " ‖ ".join(c.replace("\n", "↵")[:30] for c in a["cells"])
            )
        A("```")
        A("")
        A(f"Total stream rows: **{strm_rows}**. Total lattice rows: "
          f"**{lat_rows}**. Extra rows attributable to stream: "
          f"**{ax['n_extra']}** (= {strm_rows} − {lat_rows} = "
          f"{strm_rows - lat_rows} expected).")
        A("")
        A("#### The two counts requested")
        A("")
        A("| category | count |")
        A("|---|---|")
        A(f"| extra rows with a **blank leading cell** (wrapped-text artifact, "
          f"unambiguous) | **{len(ax['blank_leading_cell'])}** |")
        A(f"| extra rows with a **populated leading cell** | "
          f"**{len(ax['populated_leading_cell'])}** |")
        A(f"| extra rows whose content **no lattice row on the page accounts "
          f"for** (i.e. a distinct entry lattice genuinely lost) | "
          f"**{len(ax['unaccounted_rows'])}** |")
        A("")
        for key, title in (
            ("blank_leading_cell", "Extra rows — blank leading cell"),
            ("populated_leading_cell", "Extra rows — populated leading cell"),
            ("unaccounted_rows",
             "Extra rows NOT accounted for by any lattice row (= real losses)"),
        ):
            rows = ax[key]
            A(f"#### {title} ({len(rows)})")
            A("")
            if not rows:
                A("_none — every one of these rows' contents is already present "
                  "inside a lattice row on this page_")
                A("")
                continue
            A("```text")
            for rec in rows:
                lr = ("NONE" if rec["lattice_row"] is None
                      else f"L{rec['lattice_row']}")
                A(
                    f"s{rec['stream_row']:<3} ->{lr:<5} "
                    f"({rec['matched']}/{rec['n_parts']} cells found) | "
                    + " ‖ ".join(c.replace("\n", "↵") for c in rec["cells"])
                )
            A("```")
            A("")

    A("### The naive heuristic, and why it is not enough")
    A("")
    A("For contrast, here is the rule a Phase 3 parser would reach for first —")
    A("*blank leading cell means continuation* — applied to all 42 stream rows.")
    A("")
    if strm:
        allb = {"continuation": [], "distinct": [], "full_width": [], "empty": []}
        for t in strm:
            b = classify_stream_rows(t.df)
            for k in allb:
                allb[k].extend(b[k])
        A("| bucket | count |")
        A("|---|---|")
        for k in ("continuation", "distinct", "full_width", "empty"):
            A(f"| {k} | **{len(allb[k])}** |")
        A(f"| **total** | **{sum(len(v) for v in allb.values())}** |")
        A("")
        for k in ("continuation", "distinct", "full_width", "empty"):
            A(f"<details><summary>rows bucketed <code>{k}</code> "
              f"({len(allb[k])})</summary>")
            A("")
            if not allb[k]:
                A("_none_")
            else:
                A("```text")
                for ri, cells in allb[k]:
                    A(f"r{ri:<3}| "
                      + " ‖ ".join(c.replace('\n', '↵') for c in cells))
                A("```")
            A("")
            A("</details>")
            A("")

    # ---------------- character conservation across files ----------------
    A("## Character-conservation audit — does a flavour LOSE label-claim text?")
    A("")
    A("Row counts and accuracy scores cannot tell you whether text was lost. This")
    A("does: for each sampled page, compare the character multiset of every cell a")
    A("flavour returns against the page's raw text layer (the bare page-number")
    A("footer is discounted). `missing` = characters the text layer has and the")
    A("flavour did not return. `extra` = characters returned more than once,")
    A("i.e. duplicated content.")
    A("")
    A("| file | page | flavour | chars | missing | extra | |")
    A("|---|---|---|---|---|---|---|")
    for name, pages in LOSS_TARGETS.items():
        path = RAW / name
        with pdfplumber.open(path) as pdf:
            for pg in pages:
                ref = Counter(norm(pdf.pages[pg - 1].extract_text() or ""))
                for ch in norm(str(pg)):
                    if ref[ch]:
                        ref[ch] -= 1
                for flavour in FLAVOURS:
                    got = Counter()
                    try:
                        for t in camelot.read_pdf(
                            str(path), pages=str(pg), flavor=flavour
                        ):
                            for _, row in t.df.iterrows():
                                for cell in row.tolist():
                                    got.update(norm(cell))
                    except Exception:  # noqa: BLE001
                        pass
                    miss = sum((ref - got).values())
                    ext = sum((got - ref).values())
                    flag = "**LOSS**" if miss else ""
                    A(f"| `{name}` | {pg} | {flavour} | {sum(got.values())} | "
                      f"{miss} | {ext} | {flag} |")
    A("")
    A("The single lattice shortfall is insecticides p2, 36 characters. Those")
    A("characters are exactly the page heading *\"Approved Uses of Registered")
    A("Insecticides\"*, which sits **outside** the ruled table box. Lattice is")
    A("correct to exclude it; it is not a label claim. No dose, dilution or PHI")
    A("character is missing from any lattice page sampled.")
    A("")

    # ---------------- collapse test ----------------
    A("## Column-position stability — the constraint that shapes Phase 3")
    A("")
    A("The census shows the 6-column crop schema is only the *dominant* one. The")
    A("obvious explanation would be that lattice finds spurious extra vertical")
    A("rules and emits mostly-empty filler columns; if so, dropping columns that")
    A("are blank in every row would collapse the count back to 6. **Tested, and")
    A("that is not what is happening:**")
    A("")
    A("| file | cols before collapse | cols after collapse | land on exactly 6 |")
    A("|---|---|---|---|")
    for name in IN_SCOPE:
        try:
            tabs = camelot.read_pdf(str(RAW / name), pages="2-end",
                                    flavor="lattice")
        except Exception as e:  # noqa: BLE001
            A(f"| `{name}` | ERROR | {e} | |")
            continue
        before, after = Counter(), Counter()
        for t in tabs:
            before[t.df.shape[1]] += 1
            keep = [c for c in t.df.columns
                    if any(str(v).strip() for v in t.df[c].tolist())]
            after[len(keep)] += 1
        n6 = after.get(6, 0)
        tot = sum(after.values())
        A(f"| `{name}` | {dict(sorted(before.items()))} | "
          f"{dict(sorted(after.items()))} | "
          f"**{n6}/{tot} ({100 * n6 // max(1, tot)}%)** |")
    A("")
    A("Collapsing blank columns barely moves the needle (insecticides 39→45 of")
    A("109). So the surplus columns are **not** empty — they carry real values,")
    A("just at inconsistent positions. Inspecting an off-schema page shows why:")
    A("")
    A("```text")
    A("insecticides p87, lattice, 22 columns:")
    A("Okra (Bhindi) ‖ Red spider mites ‖ 60 +60 ‖ ‖ ‖ ‖ ‖ 500 ‖ ‖ ‖ ‖ 500 ‖ ‖ ‖ ‖ ‖ ‖ 03 ‖ ‖ ‖ ‖")
    A("           ^crop          ^pest      ^dose             ^form      ^dilution        ^PHI")
    A("```")
    A("")
    A("Six logical values, spread over 22 physical columns, and the column index")
    A("of each value **differs row to row within the same table** because the")
    A("source merges cells vertically. lattice therefore emits the union of every")
    A("vertical rule it finds on the page.")
    A("")
    A("**Consequence for Phase 3: positional column indexing is unsafe.** A")
    A("parser that reads `row[2]` as the a.i. dose will silently read a blank, or")
    A("worse the dilution, on these pages. Phase 3 must detect the header per")
    A("table and map columns by matched header text (or by x-coordinate against")
    A("the ruling lines), and must gate every table on 'did I resolve all six")
    A("logical columns?' — quarantining the ones that fail rather than guessing.")
    A("")

    L.extend(UNITS_SECTION.splitlines())
    L.extend(BIO_SECTION.splitlines())
    L.extend(READING_SECTION.splitlines())

    REPORTS.mkdir(parents=True, exist_ok=True)
    outp = REPORTS / "phase2_inspect.md"
    outp.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote", outp, f"({len(L)} lines)")


UNITS_SECTION = """
## 4. Is it 6 columns or 7? — direct answer

**Six logical columns. Always, in all four files.** The 7s (and the 8s, 10s,
22s) are physical artifacts, and there are two distinct causes:

* **7 = 6 + one spurious empty column.** The dose header is a *merged* cell
  (`Dosage per ha`) spanning three sub-columns. On some pages lattice keeps the
  span boundary *and* the three sub-boundaries, yielding one extra column that is
  empty on most rows. fungicides p2 shows it exactly — header tier 1 is
  `Crop ‖ Common name of the disease ‖ Dosage per ha ‖ ‖ ‖ ‖ Waiting period…`
  and the data row beneath is
  `Potato ‖ Late blight… ‖ 100 ‖ 500 ‖ 375-500 ‖ ‖ 19` — six values, seven
  cells, the sixth empty.
* **8 and above = vertical cell merges.** Where the source merges cells down a
  column, lattice emits the union of every vertical rule on the page. See the
  column-stability section below for the 22-column case.

Physical column counts observed on the header page: insecticides 6,
fungicides 7, bio_insecticides 6, bio_fungicides 7.

## 8. Header units, verbatim as printed — and what is ambiguous

Every in-scope file uses the **same two-tier header**: a spanning dose
super-header over sub-columns. Lattice reconstructs both tiers; the strings
below are exactly as lattice returned them (`↵` = newline inside the cell).

### insecticides — 6 logical columns

```text
tier 1: Crop ‖ Common Name of↵the pest ‖ Dosage/ha ‖ ‖ ‖ Waiting↵Period (days)
tier 2:      ‖                          ‖ a.i (gm) ‖ Formulation↵(gm/ml) ‖ Dilution in↵Water (Liter) ‖
```

| # | column | unit as printed | reading |
|---|---|---|---|
| 1 | `Crop` | — | crop name |
| 2 | `Common Name of the pest` | — | pest common name |
| 3 | `Dosage/ha` → `a.i (gm)` | grams of **active ingredient** per hectare | per-ha quantity |
| 4 | `Dosage/ha` → `Formulation (gm/ml)` | grams **or** millilitres of **formulated product** per hectare | per-ha quantity |
| 5 | `Dosage/ha` → `Dilution in Water (Liter)` | litres of spray water per hectare | per-ha volume |
| 6 | `Waiting Period (days)` | days | pre-harvest interval |

### fungicides — 6 logical columns

```text
tier 1: Crop ‖ Common name↵of the disease ‖ Dosage per ha ‖ ‖ ‖ Waiting↵period from↵last↵application↵to↵harvest↵(in days)
tier 2:      ‖                             ‖ a.  i. (g) ‖ Formulation↵(g/ml)/% ‖ Dilution↵in↵water(L) ‖
```

The fungicide *combination* section (from p43) reprints the header as
`Crop ‖ Common name of the disease ‖ Dosage/ha (a.i.) ‖ Dosage/ha (Formulation) ‖ Dilution ‖ Waiting Period`
— same six meanings, different wording, and `Dilution` there carries **no unit
at all**.

### bio_insecticides / bio_fungicides — 6 logical columns

```text
bio_insecticides
tier 1: Name of↵crop ‖ Name of Insect ‖ Dose/ha ‖ ‖ Dilution in water↵(liter/ha) ‖ Waiting↵period↵(Days)
tier 2:              ‖                 ‖ a.i. (g) ‖ Formulation↵(g/ml)/% ‖ ‖

bio_fungicides
tier 1: Name of Crop ‖ Common name of↵the Disease ‖ Dose/ha ‖ ‖ ‖ Dilution in water↵(liter/ha) ‖ Waiting period↵(Days)
tier 2:              ‖                             ‖ a.i↵.↵(g↵) ‖ Formulatio↵n↵  (g/ml)/% ‖ ‖ ‖
```

### Columns whose unit is ambiguous from the header alone — flag these

1. **`Formulation (g/ml)/%` — the worst offender.** The trailing `/%` means the
   same column mixes three incompatible quantity kinds, and the header does not
   say which applies to a given row:
   - a per-ha mass/volume — `500`, `1500gm`, `2.5kg`
   - a **concentration** — `0.025%`, `0.1%`
   - a **dilution ratio** — `2.5 ml per lit of water`, `100ml/100lit.Water`

   Observed on the same page, fungicides p2: Potato Late blight `500` (per ha)
   sits three rows above Mango Anthracnose `0.1%` (a concentration) and
   Pomegranate `0.1%` with dilution `500 L/ha (or depending on size of tree)`.
   **Multiplying a concentration by the 0.404686 acre factor would produce a
   fabricated number.** This is the unit trap called out for Phase 4; it must be
   detected per row, not per column.

2. **`Dosage/ha` / `Dose/ha` as a super-header is not always true.** Rows exist
   whose value is explicitly per-tree, per-plant, per-kg-seed or per-litre:
   `18.75-22.5/tree`, `10 Lit./tree`, `1gm/ kg seed`, `0.15 gm per lit`,
   `250 ml/plant`, `100 gm/plant`. The header says per hectare; the cell says
   otherwise. **The cell wins, and the header must not be trusted as the unit.**

3. **`a.i (gm)` sometimes holds a percentage, not a mass** — insecticides p2
   Abamectin: a.i. `0.00048-0.00096%`, formulation `0.025-0.050%`. Both tiers are
   concentrations for that entry.

4. **`Dilution in Water (Liter)`** is usually spray volume per ha, but also
   carries free text (`As required depending upon PP equipment used`,
   `10 Lit./tree`, `Soil drench in the nursery`) and, in the insecticide public
   health section, `ml/m2`.

5. **`Waiting Period (days)`** holds non-integers that must map to null, never
   zero: `-`, `--`, `N/A`, `NA`, `Not applicable`, `Seed dresser`,
   `Being seed treatment waiting not required`. It also holds ranges (`7-10`,
   `14-21`, `3-5`), `>90 days`, `Not less than 21 weeks`, and prose
   (`At the end of harvest`). Fungicides p23 Polyoxin D shows a literal `0`,
   which is a real zero-day PHI and must be preserved as 0, distinct from null.
"""

BIO_SECTION = """
## 10. Do the two bio files match the main files structurally?

**Header: yes.** Both use the same six logical columns with the same two-tier
dose super-header (quoted verbatim above). A single column mapping can serve all
four files.

**Body: no — they diverge in two ways that matter.**

1. **Prose replaces numbers in the dose/dilution cells.** In bio_fungicides and
   the nematode part of bio_insecticides, whole rows carry a method paragraph
   instead of quantities, often spanning the dose *and* dilution *and* PHI
   columns as one merged cell:

   ```text
   bio_insecticides p10, lattice, 3 columns:
   Brinjal ‖ Root-knot nematodes↵(Meloidogyne spp.) ‖ Treat the seed with
   Pseudomonas fluorescens 1.0% WP @ 20 gm/kg of seeds & treat the nursery beds
   with the ... @ 50 gm/sq.m and apply ... @ 5 kg/ha enriched FYM @ 5 tons/ha
   to the soil before transplanting.
   ```

   That page collapses to **3 columns**, not 6. The dose is real but embedded in
   a sentence, with three different bases in one cell (per kg seed, per sq.m,
   per ha). These rows cannot be parsed by column and must be routed to a
   free-text branch, flagged, and left out of any numeric dose field.

2. **Column counts are less stable per page than fungicides.** bio_fungicides
   lattice: 12/19 tables at 6 columns, with 9- and 11-column pages. Its p2
   header is also mangled at character level in the source itself —
   lattice returns `a.i↵.↵(g↵)` and `Formulatio↵n↵  (g/ml)/%`, and crop names
   split mid-word (`C↵ucumber`). Character-level, not word-level, wrapping.
   Header matching in Phase 3 must normalise whitespace aggressively.

**Stratification note.** With 19 and 20 pages the four strata land close
together (first p2, middle p10/p10, last p18/p19) and the block-break pair is
adjacent to the middle. They are still four distinct strata, but for these two
files the sample is a large fraction of the file, so the census in §6 — which
covers every page — is the more meaningful evidence.
"""

READING_SECTION = """
## 2 & 7. My reading — labelled as my reading

You asked for evidence first and a clearly-labelled interpretation after. The
evidence is above; this is the interpretation, and it is mine, not a measurement.

**On insecticides p55: stream is over-splitting wrapped text into physical rows.
Lattice is not merging distinct entries across faint lines.** I hold that with
high confidence, on four independent grounds:

1. **Nothing is missing from lattice.** Both flavours return the identical
   1,087-character multiset for the page — zero characters unique to either. The
   strings differ only in *order*. Lattice cannot have merged away an entry it
   still contains every character of.
2. **Zero unaccounted rows.** Of stream's 23 extra rows, every single one has its
   full cell content located inside some lattice row on the page. Not one is an
   entry lattice lost.
3. **Lattice's 19 rows equal the page's logical content**, countable by hand from
   the text layer: 2 trailing rows from the previous block, 4 chemical headers
   (Tolfenpyrad 15% EC, Triflumezopyrim 10% SC, Triflumezopyrim 20% WG,
   ZincPhosphide 80%), 1 sub-header, and 12 crop/pest entries. 2+4+1+12 = 19.
4. **Stream's splits are visibly incoherent.** The clearest case: the dose
   `23.6 ml/100 L water` is torn into stream rows s19 (`23.6 ml/100`) and s21
   (`L water`) — with the Mango row s20 sitting *between the two halves of its
   own dose*. A parser reading stream in row order would attach `23.6 ml/100` to
   the preceding Paddy entry and leave Mango's dilution blank. Likewise the Rice
   entry: stream s25 gives `Rice ‖ (blank) ‖ 25 ‖ 125 ‖ 500 ‖ 21` with the pest
   name scattered across s23, s24, s26, s27.

**The counts, and why the obvious heuristic is not safe.** Of the 23 extra rows,
10 have a blank leading cell and 13 have a populated one — yet 0 are distinct
entries. The 13 populated-leading rows are wrapped text in the *crop* column:
`application` (tail of `Foliar application`), and 11 rows of the ZincPhosphide
rodent entry whose crop cell wraps as `For rodent / control in / field and /
residential / premises(to / be used under / the / supervision / of trained /
personal)`.

So the natural Phase 3 rule — *blank leading cell means continuation* — would
catch only 10 of 23 fragmentation events on this one page. On the other 13 it
would ingest `field and` as a crop name paired with the pest
`Tatera indica, Meriones`. That is a fabricated label claim, and it is exactly
the class of silent error that propagates into training, reward and eval.

**One caveat I want on the record.** All of the above is p55 plus 11 other
sampled pages. It is not proof for all 231 pages, and the character-conservation
audit is the check I would run over the full corpus in Phase 3 as a gate, not a
spot check.

## 9. My reading of the page-boundary evidence

**All four files need cross-page forward-fill. Every one of them has a page
pair whose first row opens with a blank leading cell.** The raw rows are in §9;
this is what I read from them.

| file | pair | first row of page N+1 | continues |
|---|---|---|---|
| insecticides | (10, 11) | ` ‖ hopper, Hispa ‖ …` | `Paddy(Rice) ‖ Brown plant hopper, Gall↵midge, Stem borer, Green leaf` on p10 r27 |
| fungicides | (9, 10) | ` ‖ (Leveilulla↵taurica) ‖ …` | `Chilli ‖ Powdery mildew` on p9 r20 |
| bio_insecticides | (10, 11) | ` ‖ (Tylenchulus↵semipenetrans) ‖ …` | `Acid lime ‖ Citrus nematodes` on p10 r13 |
| bio_fungicides | (2, 3) | ` ‖ ‖ ‖ spray) ‖ ‖` | the Wheat foliar-spray entry on p2 r15 |

Two things follow that I think matter more than the samples themselves.

**Forward-fill must carry the active ingredient, not just the crop.** On
insecticides p11 the blank-crop row inherits `Paddy(Rice)` from p10 — but the
governing chemical, `Carbofuran 03%CG`, is a full-width header row *further back
on p10*. So the fill has two independent carries with different lifetimes: crop
resets on each new crop row, chemical resets only on a new chemical header. Both
must survive a page transition. This is the error the brief called invisible
downstream, and the page-order result (§3, sorted for every file and flavour) is
precisely what makes a sequential fill safe.

**The boundary is also where stream fails hardest.** bio_insecticides p11 under
stream returns:

```text
r1  | Cotton ‖ (Pectinophora↵>140 ‖ 9875↵25↵NA
```

Three separate columns — pheromone dose `>140`, dispensers `9875`, area `25`,
PHI `NA` — collapsed into two cells, with the pest name fragment
`(Pectinophora` welded onto the dose. Lattice returns the same content
correctly separated. A row like that is not recoverable by cleaning; it is
wrong in a way that looks plausible.

## Recommended flavour per file

| file | recommendation | why |
|---|---|---|
| `insecticides_20260331.pdf` | **lattice** | 1 table/page vs stream's 170 for 108 pages; keeps wrapped cells intact; 0 characters lost on 3/3 sampled pages vs stream losing 247 on p84 and duplicating 613 on p2 |
| `fungicides_20260331.pdf` | **lattice** | cleanest file — 59/82 tables natively 6-col; stream lost 270 chars on p2 and 6 on p82 |
| `bio_insecticides_20260331.pdf` | **lattice** | 13/18 tables 6-col; stream lost 29 chars on p2 |
| `bio_fungicides_20260331.pdf` | **lattice** | stream lost 556 chars on p2, 277 on p10, 61 on p19 — over half the page content in one case |

**Lattice for all four.** The deciding factor is not accuracy score or row count,
it is that lattice preserves a wrapped cell as one cell, and loses no
label-claim characters on any page sampled. Ruled borders exist on every page
(112–408 vector rectangles, Phase 1), which is what lattice needs.

### Conditions I would attach to that recommendation

1. **Do not index columns positionally.** Shown above: the same logical column
   sits at different indices on different rows of the same table. Detect the
   header per table, map by normalised header text, and gate on all six logical
   columns resolving.
2. **Quarantine, do not guess.** insecticides has only 45/109 tables at 6
   columns after blank-column collapse. Every table that fails the six-column
   gate must land in a quarantine file with its page number for manual review —
   not be force-fitted.
3. **Restrict insecticides to the crop-advisory page range.** Sections detected
   in §0.1 put public health at p85+, household at p90+, and FAO locust at p105+.
   Those tables have different schemas and describe mosquito coils, bed nets and
   rodenticides. They must never enter a crop advisory. Same for
   bio_insecticides p15+ (public health).
4. **Run the character-conservation audit as a Phase 3 gate**, per page, not as a
   spot check — it is the only check here that actually detects silent loss.
5. **Route prose-dose rows to a separate branch** (bio files especially) rather
   than attempting numeric extraction on them.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["census", "report"])
    a = ap.parse_args()
    if a.stage == "census":
        run_census()
    else:
        build_report()


if __name__ == "__main__":
    sys.exit(main())
