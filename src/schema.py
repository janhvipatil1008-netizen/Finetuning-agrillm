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

* Spray volume is a range, unlike PHI. PHI is a legal label value where one
  safe number is correct. Spray volume varies with crop stage and equipment,
  so the range is the answer. It stays numeric so the reward function can
  check it; free text would make it unverifiable.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

Basis = Literal[
    "per_acre",           # already converted from per_ha by label_db
    "per_ha",             # as printed in CIB&RC
    "per_tree",
    "per_plant",
    "per_kg_seed",
    "per_sq_m",
    "concentration_pct",  # e.g. 0.025% — NEVER area-converted
    "per_litre_water",    # e.g. 2.5 ml/l — NEVER area-converted
    "free_text",          # prose method, common in bio-pesticides
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
        if self.basis == "free_text":
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
    caution: str

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

        # An unknown pre-harvest interval is not a minor gap. If we cannot say
        # when the crop is safe to harvest, a human must be involved.
        if any(c.phi_days is None for c in self.chemical_options):
            if not self.escalate_to_expert:
                raise ValueError("unknown PHI requires escalate_to_expert=True")

        # If we didn't understand the question, we don't get to prescribe.
        if not self.query_understood and self.chemical_options:
            raise ValueError("cannot recommend chemicals on an ununderstood query")

        return self
