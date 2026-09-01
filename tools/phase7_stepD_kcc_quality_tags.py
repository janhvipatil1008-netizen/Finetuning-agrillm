"""
phase7_stepD_kcc_quality_tags.py -- quality-tag every deduped KCC row.

Input:  data/interim/kcc_deduped.parquet (5,692 rows, Phase 7 Step C)
Output: data/interim/kcc_tagged.parquet  (same columns + flag columns)
        reports/phase7_stepD_kcc_quality_tags.md

Six flags per the Step D brief: A (answer contains advice), C (pest
unmatchable), D (crop mismatch), E (banned chemical), F (label_db
matchable), G (local-language terms).


FLAG E CANNOT BE COMPUTED, AND IS LEFT NULL RATHER THAN FALSE
==============================================================

Flag E asks whether a query or answer names a chemical on "the G4 ban
list". That list does not exist. `data/final/restricted_ai.csv` has never
been sourced -- it is CLAUDE.md's first Known Gap, and `restricted_ai.py`
raises `MissingBanListError` rather than let its absence read as "nothing
is banned". `load_restricted_ai()` explicitly refuses an empty file for
the same reason.

So this script does the HALF of flag E that is real -- extracting the
chemical names each row mentions, which is the join's left side and is
independently useful -- and leaves `banned_chemical_query` as pd.NA on
every row. Not False. False asserts "this row mentions nothing banned",
which is a safety claim no artifact in this repo can currently support,
and writing it would be the same 0-vs-None collapse that `phi_days` and
`Dose.basis='unstated'` exist to prevent. The extracted chemical
vocabulary is reported so the ban list, once sourced, is a one-column
join away.

The import guard is cleared with a SENTINEL placeholder written to a
scratch dir (never data/final/), holding one row whose active_ingredient
cannot match any real chemical. verify.py's ban list is consulted by G4
and nothing else; `normalise_ai`, `LabelDB` and `expected_answerable` --
all this script uses it for -- never read it. So flag F is exactly as
correct as it would be with the real list present, and the placeholder
cannot leak into a flag E answer because flag E is not computed at all.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

IN_PARQUET = REPO_ROOT / "data" / "interim" / "kcc_deduped.parquet"
OUT_PARQUET = REPO_ROOT / "data" / "interim" / "kcc_tagged.parquet"
LABEL_DB = REPO_ROOT / "data" / "final" / "label_db.parquet"

CROPS = ["cotton", "soybean", "tur", "gram", "onion", "tomato", "grape", "pomegranate"]


REAL_BAN_LIST = REPO_ROOT / "data" / "final" / "restricted_ai.csv"


def _install_sentinel_ban_list() -> Path:
    """Clear verify.py's import guard WITHOUT fabricating ban data.

    The one row's active_ingredient is a sentinel that normalise_ai_name
    reduces to a string no pesticide is named -- so even a mistaken later
    call to RESTRICTED_AI.check() returns nothing rather than a plausible
    wrong answer. Written to a temp dir, never to data/final/, so the real
    guard stays armed for every other caller in the repo.
    """
    path = Path(tempfile.gettempdir()) / "agri_sentinel_not_a_ban_list.csv"
    path.write_text(
        "active_ingredient,tier,restricted_crops,instrument,date,notes\n"
        "ZZSENTINELNOTAREALBANLIST,banned,,"
        "PLACEHOLDER-NOT-A-LEGAL-INSTRUMENT,1970-01-01,"
        "Sentinel row only. This is NOT the s.27A ban list. Flag E is not "
        "computed from it. See phase7_stepD_kcc_quality_tags.py docstring.\n",
        encoding="utf-8",
    )
    os.environ["AGRI_RESTRICTED_AI"] = str(path)
    return path


# Phase 7 Step E sourced the real list. When it is present, flag E is
# computed for real; when it is absent this falls back to the sentinel and
# flag E stays NA, so this script keeps working either way and never
# silently reports "nothing is banned".
HAVE_REAL_BAN_LIST = REAL_BAN_LIST.exists()
if HAVE_REAL_BAN_LIST:
    os.environ["AGRI_RESTRICTED_AI"] = str(REAL_BAN_LIST)
    SENTINEL_BAN_LIST = None
else:
    SENTINEL_BAN_LIST = _install_sentinel_ban_list()

import scope  # noqa: E402
from crop_mapper import map_crop  # noqa: E402
from pest_matcher import load_table, match_pest, normalise_pest  # noqa: E402
# Private, imported deliberately: these are the head nouns and modifiers
# pest_matcher itself uses to recognise a pest phrase. Flag C needs to find
# pest-ish phrases the synonym table does NOT contain (that is the whole
# point of the flag), so it needs the same vocabulary. Copying the lists
# here would let them drift from the module they exist to mirror.
from pest_matcher import _HEADS, _MODIFIERS  # noqa: E402
from verify import LabelDB, expected_answerable, load_label_db, normalise_ai  # noqa: E402
from verify import Answerability, RESTRICTED_AI  # noqa: E402

PEST_TABLE = load_table()

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def log(msg: str) -> None:
    print(msg, flush=True)


def normalize(text: object) -> str:
    s = "" if not isinstance(text, str) else text
    s = _PUNCT_RE.sub(" ", s.lower())
    return _SPACE_RE.sub(" ", s).strip()


# --------------------------------------------------------------------------
# FLAG A -- answer_contains_advice
# --------------------------------------------------------------------------

# Number followed by a unit. Latin units plus the Devanagari/regional unit
# words that appear in this corpus -- ~30% of KccAns is in a regional script
# (Phase 7 Step B), and a Latin-only regex would score those as "no dose"
# purely because of the script they are written in.
_DOSE_RE = re.compile(
    r"\d\s*(?:%|g\b|gm\b|gms\b|gram|grm|kg\b|ml\b|mls\b|l\b|lit\b|ltr\b|litre|liter"
    r"|ग्राम|ग्रॅम|ग्रा\b|मिली|मिलि|मिलीलीटर|मिलिलीटर|लीटर|लिटर|किलो"
    r"|ગ્રામ|મિલી|લિટર|గ్రాములు|మిల్లి|లీటర్ల|ಗ್ರಾಂ|ಮಿಲಿ|ಲೀಟರ್)",
    re.IGNORECASE)

_ADVICE_VERB_RE = re.compile(
    r"\b(?:spray|sprey|spraying|apply|application|applied|drench|drenching"
    r"|treat|treatment|dust|dusting|broadcast|soak|soaking|mix|mixing"
    r"|recommend|recommended|suggest|suggested|advised)\b"
    r"|फवारणी|फवार|छिड़काव|छिडकाव|स्प्रे|आळवणी|ड्रेंचिंग|छिड़के|छिडकाव"
    r"|છંટકાવ|પંપ|పిచికారి|చల్లాలి|ಸಿಂಪಡಿಸಿ",
    re.IGNORECASE)


def build_chemical_vocab(label_df: pd.DataFrame) -> set[str]:
    """Every molecule name label_db knows, from its active_ingredient column."""
    vocab: set[str] = set()
    for ai in label_df["active_ingredient"].dropna().unique():
        for comp in normalise_ai(ai):
            # One- and two-character fragments would match inside ordinary
            # words; a real a.i. name is never that short.
            if len(comp) >= 4:
                vocab.add(comp)
    return vocab


def find_chemicals(text: object, vocab: set[str]) -> list[str]:
    norm = normalize(text)
    if not norm:
        return []
    return sorted({c for c in vocab if re.search(rf"\b{re.escape(c)}\b", norm)})


def flag_a_answer_contains_advice(answer: object, vocab: set[str]) -> tuple[bool, str]:
    """True if KccAns carries a chemical name, a dose, or an advisory verb.

    Deliberately over-inclusive: the flag's purpose is to mark answers that
    must never become a training target, so a false positive costs nothing
    and a false negative is the dangerous direction.
    """
    s = answer if isinstance(answer, str) else ""
    reasons = []
    if find_chemicals(s, vocab):
        reasons.append("chemical")
    if _DOSE_RE.search(s):
        reasons.append("dose")
    if _ADVICE_VERB_RE.search(s):
        reasons.append("verb")
    return bool(reasons), "+".join(reasons)


# --------------------------------------------------------------------------
# FLAG C -- pest_unmatchable  /  FLAG G -- local_language_terms
# --------------------------------------------------------------------------

# scope.SYNONYMS keys that are transliterated Marathi/Hindi rather than
# English, plus the local crop names crop_mapper already recognises. Flag G
# asks specifically for local-language coverage, so the plain-English keys
# in SYNONYMS ('thrips', 'leafhopper') are not counted as local terms.
_LOCAL_PEST_TERMS = {
    k: v for k, v in scope.SYNONYMS.items()
    if k in {
        "gulabi bondhali", "pandhri mashi", "safed makkhi", "tudtude", "mava",
        "phulkide", "bhuri", "davnya", "karpa", "telya", "ghatee ali",
        "mar rog", "anar butterfly",
    }
}
_LOCAL_CROP_TERMS = {
    "kapas": "cotton", "chana": "gram", "kanda": "onion", "tamatar": "tomato",
    "draksha": "grape", "anar": "pomegranate", "dalimb": "pomegranate",
    "toor": "tur", "arhar": "tur", "bhat": "soybean",
}


def _surface_forms_for(crop_slug: str, _cache: dict = {}) -> list[str]:
    if crop_slug not in _cache:
        _cache[crop_slug] = sorted(
            PEST_TABLE.surface_forms(crop_slug), key=len, reverse=True)
    return _cache[crop_slug]


def _candidate_pest_phrases(norm_query: str) -> list[str]:
    """Pest-ish phrases in the query, whether or not the table knows them.

    A head noun ('blight', 'borer', 'mite') optionally preceded by a
    modifier ('early', 'pink', 'red'). This is how flag C finds a pest the
    synonym table is MISSING -- searching only known surface forms could
    never surface a gap.
    """
    words = norm_query.split()
    out: list[str] = []
    for i, w in enumerate(words):
        if w in _HEADS:
            if i > 0 and words[i - 1] in _MODIFIERS:
                out.append(f"{words[i - 1]} {w}")
            else:
                out.append(w)
    return out


def flag_c_pest(crop_slug: str, query: object) -> dict:
    """Resolve a pest from QueryText; say precisely why when it fails."""
    norm = normalize(query)
    if not norm:
        return {"canonical": None, "unmatchable": True,
                "pest_string": "", "reason": "empty query"}

    # 1. a curated surface form for this crop, longest first
    for surface in _surface_forms_for(crop_slug):
        ns = normalize(surface)
        if ns and re.search(rf"\b{re.escape(ns)}\b", norm):
            r = match_pest(crop_slug, surface, PEST_TABLE)
            if r.matched:
                return {"canonical": r.canonical_name, "unmatchable": False,
                        "pest_string": surface, "reason": ""}

    # 2. a transliterated local term scope.py knows
    for term, canonical in _LOCAL_PEST_TERMS.items():
        if re.search(rf"\b{re.escape(term)}\b", norm):
            return {"canonical": canonical, "unmatchable": False,
                    "pest_string": term, "reason": ""}

    # 3. a pest-ish phrase the table does NOT carry -> a real gap
    for phrase in _candidate_pest_phrases(norm):
        r = match_pest(crop_slug, phrase, PEST_TABLE)
        if r.matched:
            return {"canonical": r.canonical_name, "unmatchable": False,
                    "pest_string": phrase, "reason": ""}
        key = normalise_pest(phrase)
        reason = ("ambiguous across crops" if key in PEST_TABLE.ambiguous_forms
                  else "no match in synonym table")
        return {"canonical": None, "unmatchable": True,
                "pest_string": phrase, "reason": reason}

    return {"canonical": None, "unmatchable": True,
            "pest_string": "", "reason": "no pest term found in query"}


def flag_g_local_terms(query: object) -> list[str]:
    norm = normalize(query)
    if not norm:
        return []
    found = []
    for term in list(_LOCAL_PEST_TERMS) + list(_LOCAL_CROP_TERMS):
        if re.search(rf"\b{re.escape(term)}\b", norm):
            found.append(term)
    return sorted(found)


# --------------------------------------------------------------------------
# FLAG D -- crop_mismatch
# --------------------------------------------------------------------------

def flag_e_banned(crop_slug: str, chems: list[str]) -> tuple[object, str]:
    """Do any chemicals named in this row hit the restriction list?

    Returns (verdict, detail). Verdict is pd.NA when no real ban list is
    installed -- never False, which would assert "nothing here is banned".
    Checked crop-scoped, so a restricted_use row bites only on the crops
    its instrument actually names.
    """
    if not HAVE_REAL_BAN_LIST:
        return pd.NA, ""
    if not chems:
        return False, ""
    hits = RESTRICTED_AI.check(chems, crop_slug)
    if not hits:
        return False, ""
    detail = ";".join(sorted({f"{h.active_ingredient}[{h.tier}]" for h in hits}))
    return True, detail


def flag_d_crop_mismatch(crop_slug: str, query: object) -> tuple[bool, str]:
    """True when QueryText names an in-scope crop that is NOT this row's.

    Naming no crop is not a mismatch (most queries name none). Naming the
    row's own crop alongside another is not a mismatch either -- an
    intercrop query legitimately mentions both.
    """
    text = query if isinstance(query, str) else ""
    slugs = {r.slug for r in map_crop(text) if r.slug}
    if not slugs or crop_slug in slugs:
        return False, ""
    return True, "/".join(sorted(slugs))


# --------------------------------------------------------------------------
# FLAG F -- label_db_matchable
# --------------------------------------------------------------------------

def flag_f_label_db(crop_slug: str, canonical: str | None, db: LabelDB) -> dict:
    rows = db.for_pair(crop_slug, canonical)
    trainable = [r for r in rows if r.trainable]
    gradeable = [r for r in trainable if not r.defective]
    answerability = expected_answerable(crop_slug, canonical, db)
    return {
        "matchable": bool(trainable),
        "match_count": len(trainable),
        "gradeable_count": len(gradeable),
        "rows_any": len(rows),
        "answerability": answerability.value,
    }


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> None:
    if HAVE_REAL_BAN_LIST:
        log(f"Ban list: {REAL_BAN_LIST} -- flag E computed for real.")
    else:
        log(f"NO real ban list. Sentinel placeholder: {SENTINEL_BAN_LIST}. "
            f"Flag E will be NA on every row.")
    log(f"Loading {IN_PARQUET} ...")
    df = pd.read_parquet(IN_PARQUET)
    log(f"Loaded {len(df):,} rows.")

    label_df = load_label_db(LABEL_DB)
    db = LabelDB(label_df, PEST_TABLE)
    vocab = build_chemical_vocab(label_df)
    log(f"label_db: {len(label_df):,} rows, chemical vocabulary {len(vocab)} molecules.")

    recs = []
    for _, row in df.iterrows():
        crop = str(row["crop_slug"])
        query, answer = row["QueryText"], row["KccAns"]

        a_flag, a_reason = flag_a_answer_contains_advice(answer, vocab)
        c = flag_c_pest(crop, query)
        d_flag, d_detail = flag_d_crop_mismatch(crop, query)
        f = flag_f_label_db(crop, c["canonical"], db)
        g_terms = flag_g_local_terms(query)

        chems_q = find_chemicals(query, vocab)
        chems_a = find_chemicals(answer, vocab)
        e_flag, e_detail = flag_e_banned(crop, sorted(set(chems_q) | set(chems_a)))

        recs.append({
            "answer_contains_advice": a_flag,
            "answer_advice_reason": a_reason,
            "pest_canonical": c["canonical"],
            "pest_unmatchable": c["unmatchable"],
            "pest_string": c["pest_string"],
            "pest_unmatchable_reason": c["reason"],
            "crop_mismatch": d_flag,
            "crop_mismatch_detail": d_detail,
            "banned_chemical_query": e_flag,   # pd.NA if no real list. Never False-by-default.
            "banned_chemical_detail": e_detail,
            "chemicals_in_query": ";".join(chems_q),
            "chemicals_in_answer": ";".join(chems_a),
            "label_db_matchable": f["matchable"],
            "label_db_match_count": f["match_count"],
            "label_db_gradeable_count": f["gradeable_count"],
            "label_db_rows_any": f["rows_any"],
            "answerability": f["answerability"],
            "local_language_terms": ";".join(g_terms),
            "has_local_language_terms": bool(g_terms),
        })

    flags = pd.DataFrame(recs, index=df.index)
    out = pd.concat([df, flags], axis=1)
    out["banned_chemical_query"] = out["banned_chemical_query"].astype("boolean")

    report(out, db)

    out.to_parquet(OUT_PARQUET, index=False)
    log(f"\nSaved {len(out):,} rows x {out.shape[1]} cols -> {OUT_PARQUET}")
    log("\nSTOP -- tagging only. Not committed. Waiting for review.")


def report(out: pd.DataFrame, db: LabelDB) -> None:
    n = len(out)

    def pct(k: int) -> str:
        return f"{k:,} ({k / n:.1%})"

    log("\n" + "=" * 70)
    log("1. PER-FLAG COUNTS")
    log("=" * 70)
    log(f"\nTotal rows: {n:,}\n")
    log(f"A  answer_contains_advice   : {pct(int(out['answer_contains_advice'].sum()))}")
    log(f"C  pest_unmatchable         : {pct(int(out['pest_unmatchable'].sum()))}")
    log(f"D  crop_mismatch            : {pct(int(out['crop_mismatch'].sum()))}")
    if HAVE_REAL_BAN_LIST:
        log(f"E  banned_chemical_query    : "
            f"{pct(int(out['banned_chemical_query'].fillna(False).sum()))}  "
            f"[list: {len(RESTRICTED_AI)} restrictions]")
    else:
        log(f"E  banned_chemical_query    : NOT COMPUTED -- no ban list exists "
            f"(all {n:,} rows NA)")
    log(f"F  label_db_matchable       : {pct(int(out['label_db_matchable'].sum()))}")
    log(f"G  has_local_language_terms : {pct(int(out['has_local_language_terms'].sum()))}")

    log("\nFlag A breakdown by trigger:")
    log(out["answer_advice_reason"].replace("", "(none)").value_counts().to_string())

    log("\nFlag A by answer_script (a Latin-only regex would under-count non-Latin):")
    log(pd.crosstab(out["answer_script"], out["answer_contains_advice"]).to_string())

    log("\nAnswerability (flag F verdict, from verify.expected_answerable):")
    log(out["answerability"].value_counts().to_string())

    log("\n" + "=" * 70)
    log("2. FLAG F PER CROP -- queries that can produce grounded SFT examples")
    log("=" * 70)
    per_crop = out.groupby("crop_slug").agg(
        rows=("crop_slug", "size"),
        matchable=("label_db_matchable", "sum"),
        pest_unmatchable=("pest_unmatchable", "sum"),
    ).reindex(CROPS)
    per_crop["matchable_pct"] = (per_crop["matchable"] / per_crop["rows"] * 100).round(1)
    log("\n" + per_crop.to_string())

    log("\n" + "=" * 70)
    log("3. FLAG C -- pest strings that could not be resolved")
    log("=" * 70)
    unm = out[out["pest_unmatchable"]]
    log(f"\n{len(unm):,} rows. By reason:")
    log(unm["pest_unmatchable_reason"].value_counts().to_string())
    named = unm[unm["pest_string"] != ""]
    log(f"\nOf those, {len(named):,} DID name a pest-ish phrase the table could not "
        f"resolve.\nFull list of distinct phrases (crop, phrase, reason, rows):")
    grp = (named.groupby(["crop_slug", "pest_string", "pest_unmatchable_reason"])
           .size().sort_values(ascending=False))
    for (crop, phrase, reason), cnt in grp.items():
        log(f"  {cnt:5,}  {crop:12s} {phrase!r:28s} {reason}")

    log("\n" + "=" * 70)
    log("4. FLAG E -- restricted-chemical hits, and chemicals extracted")
    log("=" * 70)
    if HAVE_REAL_BAN_LIST:
        hit = out[out["banned_chemical_query"].fillna(False)]
        log(f"\nBan list: {RESTRICTED_AI.source}  ({len(RESTRICTED_AI)} restrictions)")
        log(f"Rows hitting it: {len(hit):,} ({len(hit)/n:.1%})")
        if len(hit):
            log("\nBy restriction hit:")
            log(hit["banned_chemical_detail"].value_counts().to_string())
            log("\nBy crop:")
            log(hit["crop_slug"].value_counts().to_string())
            log("\nExamples:")
            for _, r in hit.head(8).iterrows():
                log(f"  [{r['crop_slug']:12s}] {r['banned_chemical_detail']}")
                log(f"     Q: {str(r['QueryText'])[:95]}")
    counter: Counter = Counter()
    for col in ("chemicals_in_query", "chemicals_in_answer"):
        for cell in out[col]:
            if cell:
                counter.update(cell.split(";"))
    log(f"\n{len(counter)} distinct label_db molecules named across query+answer text.")
    log("Ranked (these are the LEFT side of the ban-list join, not ban verdicts):")
    for name, cnt in counter.most_common():
        log(f"  {cnt:5,}  {name}")

    log("\n" + "=" * 70)
    log("5. FLAG D -- crop mismatches, full list")
    log("=" * 70)
    mm = out[out["crop_mismatch"]]
    log(f"\n{len(mm):,} rows.")
    grp = mm.groupby(["crop_slug", "crop_mismatch_detail"]).size().sort_values(ascending=False)
    log("\nBy (tagged crop -> crop named in text), row count:")
    for (crop, detail), cnt in grp.items():
        log(f"  {cnt:5,}  tagged={crop:12s} text names={detail}")
    log("\nEvery mismatched row:")
    for _, r in mm.iterrows():
        log(f"  [{r['crop_slug']:12s} vs {r['crop_mismatch_detail']:12s}] "
            f"{r['StateName']:14s} {r['QueryText']!r}")

    log("\n" + "=" * 70)
    log("6. 20-ROW SAMPLE, ALL FLAGS")
    log("=" * 70)
    for _, r in out.sample(min(20, n), random_state=0).iterrows():
        log("-" * 70)
        log(f"  {r['StateName']:14s} {r['crop_slug']:12s} {r['CreatedOn']}")
        log(f"  Q: {r['QueryText']}")
        log(f"  A[{'ADVICE:' + r['answer_advice_reason'] if r['answer_contains_advice'] else 'no advice'}]"
            f" {str(r['KccAns'])[:110]}")
        log(f"  C pest={r['pest_canonical']!r} unmatchable={r['pest_unmatchable']} "
            f"({r['pest_string']!r} {r['pest_unmatchable_reason']})")
        log(f"  D mismatch={r['crop_mismatch']} {r['crop_mismatch_detail']!r}   "
            f"E=NA(no ban list)   G={r['local_language_terms']!r}")
        log(f"  F matchable={r['label_db_matchable']} count={r['label_db_match_count']} "
            f"gradeable={r['label_db_gradeable_count']} -> {r['answerability']}")


if __name__ == "__main__":
    main()
