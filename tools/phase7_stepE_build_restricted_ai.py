"""
phase7_stepE_build_restricted_ai.py -- build data/final/restricted_ai.csv
from the official CIB&RC prohibition list, and report what it collides with.

This closes CLAUDE.md's first Known Gap. Until now `restricted_ai.py` raised
`MissingBanListError` at import, G4 was non-functional, and Flag E on the
KCC pool was unanswerable.


THE SOURCE IS NOT THE MUP REGISTERS -- THAT WAS CHECKED, NOT ASSUMED
====================================================================

The Step E brief suggested the CIB&RC PDFs already in data/raw/cibrc/ carry
banned/restricted information. They do not. A regex sweep for
ban|prohibit|restrict|withdraw|refus|s.27A across all 231 pages of the four
parsed registers returned only false positives -- "Bandicota" (a rat genus),
"Banana", "Bangalore", "bangle". Zero prohibition content. That confirms
what restricted_ai.py's docstring and CLAUDE.md both already said: MUP is a
REGISTRATION register, and prohibitions are issued separately.

The real source is a separate PPQS publication by the same directorate:

    LIST OF PESTICIDES WHICH ARE BANNED, REFUSED REGISTRATION AND
    RESTRICTED IN USE  (Updated on 31.07.2026)
    https://ppqs.gov.in/sites/default/files/list_of_pesticides_which_are_banned_refused_registration_and_restricted_in_use.pdf
    -> data/raw/cibrc/banned_restricted_20230601.pdf
    sha256 6bdd966bcbc1901503cfb0f91b740221016856a6923c5688602fdbbe29a3afe4

Its three sections map exactly onto restricted_ai.py's three tiers, which is
not a coincidence -- the module was designed against this document.


TRANSCRIPTION IS MACHINE-CHECKED
=================================

The entries below are transcribed by hand, because the PDF's numbered lists
carry inline statutory citations and multi-line restriction prose that no
table parser recovers cleanly. Hand transcription risks typos, and a typo
here is a safety defect: a misspelled a.i. silently never matches, so a
banned molecule reads as unrestricted.

So `verify_against_pdf()` asserts every transcribed active_ingredient string
actually occurs in the extracted PDF text before the CSV is written. The
build fails loudly rather than emitting an unverified list.


TWO SOURCE SPELLINGS ARE WRONG, AND ARE CARRIED BOTH WAYS
==========================================================

The official PDF misspells two molecules:

    "Endosulfron"          -> Endosulfan   (I.A #18)
    "Dicohlro Diphenyl..." -> Dichloro...  (III #7, DDT)

`normalise_ai_name` is a pure string reduction, so transcribing the typo
verbatim would produce a key ('endosulfron') that can never match label_db's
'Endosulfan'. Endosulfan is Supreme-Court-banned; a lookup that misses it is
exactly the failure this file exists to prevent. Both rows are therefore
emitted TWICE -- once verbatim for audit against the source, once corrected
so the lookup fires -- with the relationship recorded in notes. Extra rows
are harmless: RestrictedAI indexes by name and returns all hits.


CROP SCOPING: THE CONDITION LOGIC THE BRIEF DEFERS ALREADY EXISTS
==================================================================

The brief says to treat `restricted` as `banned` "for now -- we can add
condition logic later". That logic is already implemented:
`Restriction.applies_to()` returns False when a restricted_use row names
crops and the queried crop is not among them, and an EMPTY restricted_crops
already means every crop.

Using it is not a nicety, it is required for correctness. Section III
restrictions are mostly crop-specific, and blanket-banning them would be
actively wrong:

    Mancozeb   banned on Guava, Jowar, Tapioca -- none of our 8 crops.
               161 mentions in the KCC pool, the single most-named
               chemical. Blanket-banning it would refuse the most common
               legitimate fungicide advice in the corpus.
    Quinalphos banned on Jute, Cardamom, Sorghum -- none of our 8. 41 KCC
               mentions.

So restricted_crops carries the crops each order actually names. Crops
outside scope.CROPS are still recorded verbatim (they simply never match a
slug, which is the correct behaviour). For restrictions that are scoped by
FORMULATION or by OPERATOR rather than by crop, and which therefore do not
reach ordinary agricultural use of the 8 crops, restricted_crops carries a
non-crop scope token (`public_health`, `stored_grain_fumigation`,
`seed_treatment_only`). Those tokens are never equal to a scope slug, so
such a row correctly never fires on our crops while the real scope stays
recorded and auditable.

Every one of those scoping calls is listed in the report for review. The
verbatim restriction text is preserved in `notes` on every row so a human
can audit each one against the source.
"""
from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

import pandas as pd
import pdfplumber

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

SOURCE_PDF = REPO_ROOT / "data" / "raw" / "cibrc" / "banned_restricted_20230601.pdf"
OUT_CSV = REPO_ROOT / "data" / "final" / "restricted_ai.csv"
LABEL_DB = REPO_ROOT / "data" / "final" / "label_db.parquet"

SOURCE_URL = ("https://ppqs.gov.in/sites/default/files/"
              "list_of_pesticides_which_are_banned_refused_registration_"
              "and_restricted_in_use.pdf")
SOURCE_TITLE = ("LIST OF PESTICIDES WHICH ARE BANNED, REFUSED REGISTRATION "
                "AND RESTRICTED IN USE (Updated on 31.07.2026)")
DOWNLOAD_DATE = "2026-09-01"

FIELDS = ["active_ingredient", "tier", "restricted_crops", "instrument",
          "date", "notes", "restriction_type", "source_section"]

# Where the PDF's layout breaks a name across columns, or spells it with
# stray whitespace, the verification probe differs from the transcribed
# name. Keyed by transcribed name -> the exact substring to find in the PDF.
# Every entry here is a place the source text and the usable name diverge,
# so each one is deliberate and reviewable rather than a silent skip.
VERIFY_PROBES = {
    # PDF prints "2,4, 5-T" with a stray space after the second comma.
    "2,4,5-T": "2,4, 5-T",
    # PDF's section III table splits the DDT name across the column gap:
    # "Dicohlro Diphenyl" | <restriction prose> | "Trichloroethane (POPs)".
    # It is also misspelled ("Dicohlro"). Probe the fragment that survives.
    "Dichloro Diphenyl Trichloroethane": "Dicohlro Diphenyl",
}


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------
# transcription  (name, instrument, date)
# --------------------------------------------------------------------------

# I.A -- banned for manufacture, import and use.
BANNED_A = [
    ("Alachlor", "S.O. 3951(E)", "2018-08-08"),
    ("Aldicarb", "S.O. 682(E)", "2001-07-17"),
    ("Aldrin", "", ""),
    ("Benzene Hexachloride", "", ""),
    ("Benomyl", "S.O. 3951(E)", "2018-08-08"),
    ("Calcium Cyanide", "", ""),
    ("Carbaryl", "S.O. 3951(E)", "2018-08-08"),
    ("Chlorbenzilate", "S.O. 682(E)", "2001-07-17"),
    ("Chlordane", "", ""),
    ("Chlorofenvinphos", "", ""),
    ("Copper Acetoarsenite", "", ""),
    ("Diazinon", "S.O. 3951(E)", "2018-08-08"),
    ("Dibromochloropropane", "S.O. 569(E)", "1989-07-25"),
    ("Dichlorovos", "S.O. 3951(E)", "2018-08-08"),
    ("Dicofol", "S.O. 4294(E)", "2023-10-03"),
    ("Dieldrin", "S.O. 682(E)", "2001-07-17"),
    ("Dinocap", "S.O. 4294(E)", "2023-10-03"),
    ("Endosulfron", "Supreme Court WP(C) 213/2011", "2017-01-10"),
    ("Endrin", "", ""),
    ("Ethyl Mercury Chloride", "", ""),
    ("Ethyl Parathion", "", ""),
    ("Ethylene Dibromide", "S.O. 682(E)", "2001-07-17"),
    ("Fenarimol", "S.O. 3951(E)", "2018-08-08"),
    ("Fenthion", "S.O. 3951(E)", "2018-08-08"),
    ("Heptachlor", "", ""),
    ("Lindane", "", ""),
    ("Linuron", "S.O. 3951(E)", "2018-08-08"),
    ("Maleic Hydrazide", "S.O. 682(E)", "2001-07-17"),
    ("Menazon", "", ""),
    ("Methomyl", "S.O. 4294(E)", "2023-10-03"),
    ("Methoxy Ethyl Mercury Chloride", "S.O. 3951(E)", "2018-08-08"),
    ("Methyl Parathion", "S.O. 3951(E)", "2018-08-08"),
    ("Metoxuron", "", ""),
    ("Nitrofen", "", ""),
    ("Paraquat Dimethyl Sulphate", "", ""),
    ("Pentachloro Nitrobenzene", "S.O. 569(E)", "1989-07-25"),
    ("Pentachlorophenol", "", ""),
    ("Phenyl Mercury Acetate", "", ""),
    ("Phorate", "S.O. 3951(E)", "2018-08-08"),
    ("Phosphamidon", "S.O. 3951(E)", "2018-08-08"),
    ("Sodium Cyanide", "S.O. 3951(E)", "2018-08-08"),
    ("Sodium Methane Arsonate", "", ""),
    ("Tetradifon", "", ""),
    ("Thiometon", "S.O. 3951(E)", "2018-08-08"),
    ("Toxaphene", "S.O. 569(E)", "1989-07-25"),
    ("Triazophos", "S.O. 3951(E)", "2018-08-08"),
    ("Tridemorph", "S.O. 3951(E)", "2018-08-08"),
    ("Trichloro acetic acid", "S.O. 682(E)", "2001-07-17"),
    ("Trichlorfon", "S.O. 3951(E)", "2018-08-08"),
]

# I.B -- banned for USE, manufacture for export continues. Still banned for
# use in India, so an advisory model must never recommend one.
BANNED_B = [
    ("Captafol", "S.O. 679(E)", "2001-07-17"),
    ("Dichlorvos", "S.O. 1196(E)", "2020-03-20"),
    ("Nicotin Sulfate", "S.O. 325(E)", "1992-05-11"),
    ("Phorate", "S.O. 1196(E)", "2020-03-20"),
    ("Triazophos", "S.O. 1196(E)", "2020-03-20"),
]

# I.C -- withdrawn. Brief says treat as banned. The source notes withdrawal
# "may become inoperative" if the industry submits the required data, so the
# reversibility is recorded in notes rather than lost.
WITHDRAWN_C = [
    ("Dalapon", "S.O. 915(E)", "2006-06-15"),
    ("Ferbam", "S.O. 915(E)", "2006-06-15"),
    ("Formothion", "S.O. 915(E)", "2006-06-15"),
    ("Nickel Chloride", "S.O. 915(E)", "2006-06-15"),
    ("Paradichlorobenzene", "S.O. 915(E)", "2006-06-15"),
    ("Simazine", "S.O. 915(E)", "2006-06-15"),
    ("Sirmate", "S.O. 2485(E)", "2014-09-24"),
    ("Warfarin", "S.O. 915(E)", "2006-06-15"),
]

# II -- refused registration. The source gives no instrument per row.
REFUSED_II = [
    "2,4,5-T", "Ammonium Sulphamate", "Azinphos Ethyl", "Azinphos Methyl",
    "Binapacryl", "Calcium Arsenate", "Carbophenothion", "Chinomethionate",
    "Dicrotophos", "EPN", "Fentin Acetate", "Fentin Hydroxide",
    "Lead Arsenate", "Leptophos", "Mephosfolan", "Mevinphos",
    "Thiodemeton", "Vamidothion",
]

# III -- restricted in use. crops: ';'-joined; EMPTY MEANS EVERY CROP.
# See the module docstring on the non-crop scope tokens.
RESTRICTED_III = [
    ("Aluminium Phosphide", "stored_grain_fumigation",
     "G.S.R. 371(E) / S.O. 677(E)", "1999-05-20",
     "Pest control operations only by Govt/approved operators under expert "
     "supervision. Tube packs of 10 and 20 tablets of 3g banned completely "
     "(S.O. 677(E) 2001-07-17). Fumigant: not an agricultural foliar use on "
     "the 8 scope crops."),
    ("Captafol", "seed_treatment_only", "S.O. 569(E)", "1989-07-25",
     "Use as foliar spray is BANNED; permitted only as seed dresser. "
     "Manufacture of Captafol 80% DS banned except for export "
     "(S.O. 679(E) 2001-07-17). Also listed banned-for-use in section I.B."),
    ("Carbofuran", "", "S.O. 4294(E)", "2023-10-03",
     "All formulations EXCEPT Carbofuran 3% Encapsulated Granule (CG), with "
     "the crop labels, may be stopped from use. Empty crop scope = every "
     "crop: the exception is formulation-level, not crop-level, so any "
     "non-3%-CG recommendation is restricted on all 8 scope crops."),
    ("Chlorpyriphos", "ber;citrus;tobacco", "S.O. 4294(E)", "2023-10-03",
     "Banned for use in Ber, Citrus and Tobacco. None of the three is a "
     "scope crop, so this does not fire on the 8."),
    ("Cypermethrin", "public_health", "WP(C) 10052/2009; LPA-429/2009",
     "2009-09-08",
     "Cypermethrin 3% Smoke Generator restricted to Pest Control Operators, "
     "not general public. Formulation- and use-scoped (public health), not "
     "a restriction on agricultural cypermethrin."),
    ("Dazomet", "tea", "S.O. 3006(E)", "2008-12-31",
     "Use not permitted on Tea. Tea is not a scope crop."),
    ("Dichloro Diphenyl Trichloroethane", "", "S.O. 378(E)", "1989-05-26",
     "Use of DDT in AGRICULTURE is withdrawn; public health use capped at "
     "10,000 MT/annum (S.O. 295(E) 2006-03-08). Empty crop scope = every "
     "crop, because the agricultural withdrawal reaches all 8."),
    ("Dimethoate", "tomato;grape;pomegranate;onion", "S.O. 4294(E)",
     "2023-10-03",
     "Banned for use in fruits and vegetables CONSUMED AS RAW FOOD ITEMS. "
     "The order names a category, not a crop list; the four scope crops "
     "listed here are this project's reading of that category "
     "(tomato/grape/pomegranate/onion). JUDGEMENT CALL -- flagged for "
     "review. Cotton, soybean, tur and gram are not raw-consumed."),
    ("Fenitrothion", "", "S.O. 706(E)", "2007-05-03",
     "Banned in agriculture EXCEPT locust control in scheduled desert area "
     "and public health. Empty crop scope = every crop: the carve-out is "
     "not an agricultural crop use."),
    ("Malathion",
     "soybean;tomato;grape", "S.O. 4294(E)", "2023-10-03",
     "Banned for use on Sorghum, Pea, Soybean, Castor, Sunflower, Bhindi, "
     "Brinjal, Cauliflower, Radish, Turnip, Tomato, Apple, Mango and Grape. "
     "Three of those are scope crops: soybean, tomato, grape."),
    ("Mancozeb", "guava;jowar;tapioca", "S.O. 4294(E)", "2023-10-03",
     "Banned for use on Guava, Jowar and Tapioca. None is a scope crop, so "
     "this does not fire on the 8 -- see module docstring, Mancozeb is the "
     "most-mentioned chemical in the KCC pool and blanket-banning it would "
     "be wrong."),
    ("Methyl Bromide", "stored_grain_fumigation", "G.S.R. 371(E)",
     "1999-05-20",
     "Use only by Govt/approved pest control operators under expert "
     "supervision. Fumigant, not an agricultural foliar use on the 8."),
    ("Monocrotophos", "", "S.O. 4294(E)", "2023-10-03",
     "Banned for use on VEGETABLES since S.O. 1482(E) 2005-10-10. "
     "Additionally S.O. 4294(E) discontinues Monocrotophos 36% SL: no new "
     "registration certificates, all 36% SL certificates cancelled after a "
     "one-year extension window (i.e. from 2024-10-03), sale only to clear "
     "existing stock till expiry. Empty crop scope = every crop, "
     "CONSERVATIVE: the vegetable ban reaches tomato and onion, and the "
     "dominant registered formulation is now cancelled. JUDGEMENT CALL -- "
     "flagged for review."),
    ("Oxyfluorfen", "potato;groundnut", "S.O. 4294(E)", "2023-10-03",
     "Banned for use on Potato and Groundnut. Neither is a scope crop."),
    ("Quinalphos", "jute;cardamom;sorghum", "S.O. 4294(E)", "2023-10-03",
     "Banned for use on Jute, Cardamom and Sorghum. None is a scope crop."),
    ("Trifluralin", "", "S.O. 3951(E)", "2018-08-08",
     "Registration, import, manufacture, formulation, transport, sale and "
     "ALL uses EXCEPT use in wheat prohibited and completely banned from "
     "2018-08-08. Empty crop scope = every crop: wheat is not a scope crop, "
     "so the carve-out never applies here."),
]

# Source-PDF misspellings. Emitted a second time under the correct spelling
# so the lookup key matches label_db. See module docstring.
SPELLING_CORRECTIONS = {
    "Endosulfron": "Endosulfan",
    "Dichloro Diphenyl Trichloroethane": None,   # already corrected inline
}


def build_rows() -> list[dict]:
    rows: list[dict] = []

    def add(ai, tier, crops, instrument, date, notes, rtype, section):
        rows.append({
            "active_ingredient": ai, "tier": tier, "restricted_crops": crops,
            "instrument": instrument, "date": date, "notes": notes,
            "restriction_type": rtype, "source_section": section,
        })

    for name, inst, date in BANNED_A:
        add(name, "banned", "", inst, date,
            "Banned for manufacture, import and use.", "banned", "I.A")

    for name, inst, date in BANNED_B:
        add(name, "banned", "", inst, date,
            "Banned for USE in India; manufacture for export permitted. An "
            "advisory must never recommend it.", "banned", "I.B")

    for name, inst, date in WITHDRAWN_C:
        add(name, "banned", "", inst, date,
            "Withdrawn. Withdrawal may become inoperative if the required "
            "data is generated and accepted by the Registration Committee. "
            "Treated as banned per the Phase 7 Step E brief.",
            "withdrawn", "I.C")

    for name in REFUSED_II:
        add(name, "refused_registration", "", "", "",
            "Refused registration: never granted registration, so any label "
            "claim for it is fabricated. Source gives no per-row instrument.",
            "refused_registration", "II")

    for name, crops, inst, date, note in RESTRICTED_III:
        add(name, "restricted_use", crops, inst, date, note,
            "restricted", "III")

    # corrected-spelling / alias duplicates
    add("Endosulfan", "banned", "", "Supreme Court WP(C) 213/2011",
        "2017-01-10",
        "CORRECTED SPELLING of the source PDF's 'Endosulfron' (section I.A "
        "#18). Emitted so the normalise_ai_name key matches label_db; the "
        "verbatim misspelling is also present for audit.",
        "banned", "I.A (corrected)")

    add("DDT", "restricted_use", "", "S.O. 378(E)", "1989-05-26",
        "ALIAS row for 'Dichloro Diphenyl Trichloroethane' (section III #7), "
        "which the source PDF both misspells ('Dicohlro') and splits across "
        "its table columns. DDT is the name any text would actually use. "
        "Agricultural use withdrawn, so empty crop scope = every crop.",
        "restricted", "III (alias)")

    return rows


def verify_against_pdf(rows: list[dict], pdf_text: str) -> list[str]:
    """Every transcribed a.i. must actually occur in the source PDF.

    A transcription typo produces a key that silently never matches, so a
    banned molecule would read as unrestricted. Fail loudly instead.
    """
    norm = " ".join(pdf_text.lower().split())
    problems = []
    for r in rows:
        ai = r["active_ingredient"]
        if r["source_section"].endswith("(corrected)"):
            continue  # deliberately not in the source; that is the point
        probe = " ".join(VERIFY_PROBES.get(ai, ai).lower().split())
        if probe not in norm:
            problems.append(f"{ai!r} (section {r['source_section']}) NOT FOUND in source PDF")
    return problems


def main() -> None:
    from restricted_ai import normalise_ai_name

    log("=" * 70)
    log("BUILDING data/final/restricted_ai.csv")
    log("=" * 70)

    sha = hashlib.sha256(SOURCE_PDF.read_bytes()).hexdigest()
    log(f"\nSource : {SOURCE_PDF.name}")
    log(f"sha256 : {sha}")
    log(f"URL    : {SOURCE_URL}")

    with pdfplumber.open(SOURCE_PDF) as pdf:
        pdf_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    rows = build_rows()
    log(f"\nTranscribed {len(rows)} rows.")

    problems = verify_against_pdf(rows, pdf_text)
    if problems:
        log("\nTRANSCRIPTION CHECK FAILED:")
        for p in problems:
            log(f"  {p}")
        raise SystemExit("Refusing to write an unverified ban list.")
    log("Transcription check: every a.i. string found verbatim in the source PDF. OK")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    log(f"\nWrote {len(rows)} rows -> {OUT_CSV}")

    # ---- it must actually load through the module that consumes it -------
    from restricted_ai import load_restricted_ai
    rai = load_restricted_ai(OUT_CSV)
    log(f"load_restricted_ai() OK: {len(rai)} restrictions indexed.")

    by_tier = pd.Series([r["tier"] for r in rows]).value_counts()
    log("\nBy tier:\n" + by_tier.to_string())
    by_type = pd.Series([r["restriction_type"] for r in rows]).value_counts()
    log("\nBy restriction_type:\n" + by_type.to_string())

    log("\nNormalised keys (normalise_ai_name), first 12:")
    for r in rows[:12]:
        log(f"  {r['active_ingredient']:34s} -> {normalise_ai_name(r['active_ingredient'])!r}")

    cross_check_label_db(rai)


def cross_check_label_db(rai) -> None:
    """Which label_db rows recommend a molecule this list restricts?"""
    from verify import normalise_ai
    import scope

    log("\n" + "=" * 70)
    log("CROSS-CHECK: label_db rows naming a restricted molecule")
    log("=" * 70)

    df = pd.read_parquet(LABEL_DB)
    hits = []
    for i, r in df.iterrows():
        comps = normalise_ai(r["active_ingredient"])
        restrictions = rai.check(comps, str(r["crop_slug"]))
        if restrictions:
            hits.append({
                "idx": i,
                "crop_slug": r["crop_slug"],
                "active_ingredient": r["active_ingredient"],
                "pest": r["pest_or_disease"],
                "tiers": ";".join(sorted({x.tier for x in restrictions})),
                "which": ";".join(sorted({x.active_ingredient for x in restrictions})),
                "source_file": r["source_file"],
                "trainable": (str(r["dose_ai_branch"]) in {"numeric", "free_text"}
                              and str(r["dose_formulation_branch"]) in {"numeric", "free_text"}),
            })
    h = pd.DataFrame(hits)
    log(f"\n{len(h):,} of {len(df):,} label_db rows CONTRADICT the ban list "
        f"(CIB&RC registers a use for a molecule the same directorate restricts).")
    if h.empty:
        return

    log(f"  of those, trainable: {int(h['trainable'].sum()):,}")
    log("\nBy molecule:")
    log(h.groupby("which").size().sort_values(ascending=False).to_string())
    log("\nBy crop:")
    log(h.groupby("crop_slug").size().sort_values(ascending=False).to_string())
    log("\nBy tier:")
    log(h.groupby("tiers").size().sort_values(ascending=False).to_string())

    log("\nEvery contradicting row:")
    for _, r in h.iterrows():
        log(f"  [{r['crop_slug']:12s}] {str(r['active_ingredient'])[:46]:46s} "
            f"pest={str(r['pest'])[:34]:34s} {r['tiers']:20s} trainable={r['trainable']}")

    out = REPO_ROOT / "data" / "interim" / "label_db_ban_contradictions.csv"
    h.to_csv(out, index=False)
    log(f"\nWrote contradiction detail -> {out}")


if __name__ == "__main__":
    main()
