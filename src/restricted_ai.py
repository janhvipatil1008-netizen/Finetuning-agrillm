"""restricted_ai.py — banned / refused / restricted active ingredients.

CIB&RC's "Major Uses of Pesticides" is a REGISTRATION register. Prohibitions
are issued separately, under s.27A of the Insecticides Act, 1968, and the MUP
tables are not pruned in lockstep. So:

    absence from label_db is not evidence of a ban
    presence in  label_db is not evidence of current legality

label_db contains Monocrotophos, Carbofuran, Carbosulfan, Benfuracarb and
others whose status this project cannot settle from the CIB&RC PDFs alone. A
verifier checking only label_db scores a Monocrotophos recommendation on
cotton as CORRECT — right crop, right pest, right dose, right PHI. That is the
failure this module exists to make impossible.

THE FILE DOES NOT EXIST YET, AND THAT IS FATAL BY DESIGN
=========================================================

`data/final/restricted_ai.csv` has to be sourced from the s.27A notifications
and logged in SOURCES.md with the same hash/date discipline as the CIB&RC
drops. Until it does, `load_restricted_ai()` raises `MissingBanListError`.

It must never degrade to an empty list. An empty ban list is
indistinguishable, at every call site, from "nothing is banned" — and that
reading is both wrong and dangerous. A verifier that cannot check for bans
must refuse to run, not quietly bless everything.

THREE TIERS, NOT ONE BOOLEAN
=============================

    banned                 use prohibited outright
    refused_registration   never granted registration; a claim for it is
                           fabricated regardless of what any table prints
    restricted_use         lawful, but not everywhere -- conditional on crop,
                           because carve-outs exist

The first two are properties of the active ingredient and fail at a.i. level.
The third is a property of the (a.i., crop) pair, so `check()` needs the crop
and returns nothing when the restriction does not reach it.

CSV CONTRACT
============

    active_ingredient   base a.i. name, no strength or formulation code
                        ("Monocrotophos", not "Monocrotophos 36% SL")
    tier                one of the three above
    restricted_crops    ';'-separated scope slugs the restriction BITES on.
                        EMPTY MEANS EVERY CROP -- the safe default, so a row
                        added without thinking about scope restricts widely
                        rather than narrowly.
    instrument          the notification/order imposing it
    date                ISO date of that instrument
    notes               free text, including any carve-out wording
"""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Optional

__all__ = [
    "DEFAULT_RESTRICTED_AI_PATH",
    "MissingBanListError",
    "Restriction",
    "RestrictedAI",
    "TIERS",
    "HARD_FAIL_TIERS",
    "load_restricted_ai",
    "normalise_ai_name",
]

DEFAULT_RESTRICTED_AI_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "final" / "restricted_ai.csv"
)

# Overridable for tests and for a caller pointing at a newer notification set.
PATH_ENV_VAR = "AGRI_RESTRICTED_AI"

Tier = Literal["banned", "refused_registration", "restricted_use"]

TIERS: frozenset[str] = frozenset(
    {"banned", "refused_registration", "restricted_use"})

# Properties of the a.i. itself: no crop can make them acceptable.
HARD_FAIL_TIERS: frozenset[str] = frozenset({"banned", "refused_registration"})

REQUIRED_COLUMNS = ("active_ingredient", "tier", "restricted_crops",
                    "instrument", "date", "notes")


class MissingBanListError(RuntimeError):
    """Raised when the restricted-AI list is absent or unreadable.

    Deliberately not caught anywhere. A missing ban list is a missing safety
    check, and the only correct response is to stop.
    """


def normalise_ai_name(name: str) -> str:
    """'Monocrotophos 36% SL' -> 'monocrotophos'. Strength and code dropped.

    Matches the component normalisation the verifier uses on label_db's
    `active_ingredient`, so a ban row and a label row for the same chemical
    land on the same key.
    """
    head = re.split(r"\s*\d", str(name), maxsplit=1)[0]
    head = re.sub(r"[^A-Za-z\- ]", " ", head)
    return re.sub(r"\s+", " ", head).strip().lower()


@dataclass(frozen=True)
class Restriction:
    active_ingredient: str
    tier: str
    crops: frozenset[str]      # empty == every crop
    instrument: str
    date: str
    notes: str

    def applies_to(self, crop_slug: Optional[str]) -> bool:
        if self.tier in HARD_FAIL_TIERS:
            return True
        if not self.crops:
            return True
        return (crop_slug or "").strip().lower() in self.crops

    def describe(self) -> str:
        where = "all crops" if not self.crops else "/".join(sorted(self.crops))
        return (f"{self.active_ingredient} [{self.tier}, {where}] "
                f"— {self.instrument} {self.date}").strip()


class RestrictedAI:
    """Lookup over the restriction rows. Constructed only via load_restricted_ai."""

    def __init__(self, rows: Iterable[Restriction], source: Path):
        self.source = source
        self._by_name: dict[str, list[Restriction]] = {}
        for r in rows:
            self._by_name.setdefault(normalise_ai_name(r.active_ingredient),
                                     []).append(r)

    def __len__(self) -> int:
        return sum(len(v) for v in self._by_name.values())

    def check(self, ai_components: Iterable[str],
              crop_slug: Optional[str] = None) -> list[Restriction]:
        """Return every restriction hitting these a.i. components on this crop.

        `ai_components` is the normalised component set of one product — a
        co-formulation is checked component by component, because a mixture
        containing a banned partner is banned.
        """
        hits: list[Restriction] = []
        for comp in ai_components:
            for r in self._by_name.get(normalise_ai_name(comp), ()):
                if r.applies_to(crop_slug):
                    hits.append(r)
        return hits


def load_restricted_ai(path: Path | str | None = None) -> RestrictedAI:
    """Load the list, or raise. Never returns an empty-because-missing list.

    Raises:
        MissingBanListError: the file is absent, empty, or missing a required
            column. Every one of those states would otherwise read as "no
            restrictions apply".
    """
    if path is None:
        path = os.environ.get(PATH_ENV_VAR) or DEFAULT_RESTRICTED_AI_PATH
    path = Path(path)

    if not path.exists():
        raise MissingBanListError(
            f"restricted-AI list not found: {path}\n"
            f"  This file is REQUIRED. It is not optional, and its absence is\n"
            f"  not equivalent to 'no active ingredients are restricted'.\n"
            f"  label_db carries Monocrotophos, Carbofuran, Carbosulfan and\n"
            f"  Benfuracarb; without this list the verifier would score a\n"
            f"  recommendation of any of them as CORRECT.\n"
            f"  Source it from the Insecticides Act s.27A notifications, log\n"
            f"  it in SOURCES.md, and write it with columns: "
            f"{', '.join(REQUIRED_COLUMNS)}.\n"
            f"  Set {PATH_ENV_VAR} to point elsewhere."
        )

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise MissingBanListError(
                f"{path} is missing required column(s): {missing}. "
                f"Expected {list(REQUIRED_COLUMNS)}."
            )
        rows: list[Restriction] = []
        for i, raw in enumerate(reader, start=2):
            tier = (raw["tier"] or "").strip().lower()
            if tier not in TIERS:
                raise MissingBanListError(
                    f"{path} line {i}: tier {tier!r} is not one of "
                    f"{sorted(TIERS)}. An unrecognised tier cannot be graded "
                    f"safely, so the whole list is rejected."
                )
            crops = frozenset(
                c.strip().lower()
                for c in (raw["restricted_crops"] or "").split(";")
                if c.strip()
            )
            rows.append(Restriction(
                active_ingredient=(raw["active_ingredient"] or "").strip(),
                tier=tier,
                crops=crops,
                instrument=(raw["instrument"] or "").strip(),
                date=(raw["date"] or "").strip(),
                notes=(raw["notes"] or "").strip(),
            ))

    if not rows:
        raise MissingBanListError(
            f"{path} has a header but no rows. An empty ban list reads as "
            f"'nothing is restricted', which this module exists to prevent. "
            f"If the intent really is an empty list, that is a decision to "
            f"record explicitly, not to express by omission."
        )
    return RestrictedAI(rows, path)
