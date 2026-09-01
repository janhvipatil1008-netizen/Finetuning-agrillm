"""
schema.py — the shape of every answer this model will ever produce.

FROZEN once training-data generation starts. A change after that point
invalidates the dataset, the reward function and the benchmark together.

Design notes worth keeping:

* Dose is not a string. CIB&RC states dose on at least eight bases (per ha,
  per tree, per plant, per kg seed, per sq m, as a percentage, as a per-litre
  dilution, and as prose). A single `dose_per_acre: str` cannot represent
  orchard or seed-treatment claims, and a model forced into that field will
  invent an acre figure.

* phi_days: None means unknown, 0 means a genuine zero-day interval. These
  never collapse into each other. Where CIB&RC prints a range, label_db keeps
  phi_min/phi_max/phi_raw and the Advisory emits the LARGER value — the safety
  choice is made here, deliberately, not buried in a regex.

* phi_not_applicable (added 2026-09-01): None was doing two jobs. label_db
  separates them across four columns — 16 rows where the label POSITIVELY
  states no interval applies (seed dressers: 'NR', 'Seed dresser', 'waiting
  not required') from 184 where it prints '-' / blank / 'Nil' and the interval
  is genuinely unknown. The schema collapsed both into phi_days=None, and the
  old invariant then forced escalate_to_expert=True on all 200. On the 16 that
  is not merely lossy, it is an affirmatively WRONG answer: the label says no
  waiting period applies, and the model was compelled to send the farmer to an
  expert anyway. The flag restores the distinction label_db already carries.

  It sits on ChemicalOption, not Advisory, because PHI is a property of the
  product. Six (crop, pest) pairs register both a seed dresser and a foliar
  spray — cotton/Jassid has Imidacloprid 48% FS ('NR') beside Acephate 75% SP
  (15 days) — so one advisory legitimately needs both states at once.

* Basis 'unstated' (added 2026-09-01): refuse-to-guess is a rule this codebase
  enforces everywhere else — dose_parser returns NEEDS_UNIT rather than
  inventing a unit, pest_matcher returns unmatched rather than picking a
  plausible pest. The schema could not say it. `dose` is required and a
  numeric basis demands value_min, so "this chemical is registered for your
  crop and pest but I cannot state the dose" had exactly one shape:
  basis='free_text' with no value — structurally identical to the 10 rows
  whose dose IS genuine prose ('1.0 g/plant & 22.2 to 25.6 Kg/ha', 'Foliar
  spray'). 42 rows have no parseable product dose (25 empty, 17 unparseable,
  of which 13 are the unit-unresolvable NEEDS_UNIT survivors). Without a
  distinct basis the verifier cannot tell a principled refusal from a dropped
  field, and the model's only alternatives were to invent a number or to drop
  a registered chemical entirely.

  'unstated' forces escalate_to_expert=True. A chemical nobody can dose is
  precisely the case a human should see.

* Spray volume is a range, unlike PHI. PHI is a legal label value where one
  safe number is correct. Spray volume varies with crop stage and equipment,
  so the range is the answer. It stays numeric so the reward function can
  check it; free text would make it unverifiable.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

Basis = Literal[
    "per_acre",           # derived from per_ha by label_db, area bases only
    "per_ha",             # as printed in CIB&RC
    "per_tree",
    "per_plant",
    "per_kg_seed",
    "per_sq_m",
    "concentration_pct",  # e.g. 0.025% — NEVER area-converted
    "per_litre_water",    # e.g. 2.5 ml/l — NEVER area-converted
    "free_text",          # prose method, common in bio-pesticides
    "unstated",           # registered, but no dose can be stated — see above
]

Unit = Literal["g", "ml", "kg", "l", "%"]

MASS_VOL = {"g", "ml", "kg", "l"}


class Cause(BaseModel):
    name: str
    type: Literal["pest", "disease", "nutrient", "abiotic", "weed"]
    confidence: float = Field(ge=0, le=1)
    evidence: str


class Dose(BaseModel):
    basis: Basis
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    unit: Optional[Unit] = None
    raw: str                     # verbatim CIB&RC cell — the audit trail

    @model_validator(mode="after")
    def _check(self):
        # Neither basis carries a number: free_text is prose the label
        # printed, unstated is a dose nobody can give. Both legitimately
        # have no value_min and no unit.
        if self.basis in ("free_text", "unstated"):
            return self
        if self.value_min is None or self.unit is None:
            raise ValueError(f"numeric basis {self.basis} needs value_min and unit")
        if self.value_max is not None and self.value_max < self.value_min:
            raise ValueError("value_max < value_min")
        # The real hazard is not a bad unit string, it is 0.025 labelled
        # per_acre with unit '%' — a concentration wearing an area basis.
        if self.basis == "concentration_pct" and self.unit != "%":
            raise ValueError("concentration_pct must use unit '%'")
        if self.basis != "concentration_pct" and self.unit not in MASS_VOL:
            raise ValueError(f"basis {self.basis} cannot use unit {self.unit!r}")
        return self


class ChemicalOption(BaseModel):
    active_ingredient: str
    formulation: str
    dose: Dose
    spray_volume_min_l_per_acre: Optional[int] = Field(default=None, ge=0)
    spray_volume_max_l_per_acre: Optional[int] = Field(default=None, ge=0)
    phi_days: Optional[int] = Field(default=None, ge=0)
    phi_not_applicable: bool = False
    caution: str

    @model_validator(mode="after")
    def _check_phi(self):
        # phi_not_applicable asserts the LABEL states no interval applies. It
        # is meaningless beside a number, and allowing both would recreate the
        # overload this field exists to remove — a third state meaning "there
        # is an interval, and also there isn't".
        if self.phi_not_applicable and self.phi_days is not None:
            raise ValueError(
                "phi_not_applicable=True cannot carry a phi_days value; "
                f"got phi_days={self.phi_days}")
        return self

    @model_validator(mode="after")
    def _check_volume(self):
        lo, hi = self.spray_volume_min_l_per_acre, self.spray_volume_max_l_per_acre
        if (lo is None) != (hi is None):
            raise ValueError("spray volume needs both bounds or neither")
        if lo is not None and hi < lo:
            raise ValueError("spray volume max < min")
        return self


class Advisory(BaseModel):
    in_scope: bool
    query_understood: bool
    clarifying_question: Optional[str] = None
    likely_causes: list[Cause] = []
    non_chemical_first: list[str] = []
    chemical_options: list[ChemicalOption] = []
    safety: list[str] = []
    escalate_to_expert: bool

    @model_validator(mode="after")
    def _invariants(self):
        # Out of scope means no recommendation. No exceptions.
        if not self.in_scope and self.chemical_options:
            raise ValueError("out-of-scope answers cannot carry chemical options")

        # An UNKNOWN pre-harvest interval is not a minor gap. If we cannot say
        # when the crop is safe to harvest, a human must be involved.
        #
        # A NOT-APPLICABLE one is different: the label positively states no
        # interval applies (seed dressers). That is a complete answer and must
        # not force escalation -- the distinction phi_not_applicable exists to
        # carry. ChemicalOption._check_phi guarantees the flag never sits
        # beside a number, so the two branches cannot overlap.
        if any(c.phi_days is None and not c.phi_not_applicable
               for c in self.chemical_options):
            if not self.escalate_to_expert:
                raise ValueError("unknown PHI requires escalate_to_expert=True")

        # A chemical that cannot be dosed is exactly the case a human should
        # see. Registering the claim without the number is honest; letting it
        # reach a farmer unescalated is not.
        if any(c.dose.basis == "unstated" for c in self.chemical_options):
            if not self.escalate_to_expert:
                raise ValueError(
                    "a dose basis of 'unstated' requires escalate_to_expert=True")

        # If we didn't understand the question, we don't get to prescribe.
        if not self.query_understood and self.chemical_options:
            raise ValueError("cannot recommend chemicals on an ununderstood query")

        return self
