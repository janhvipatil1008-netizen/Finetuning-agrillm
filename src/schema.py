"""Strict output schema for agri-llm advisories.

Every model generation — training target and inference output — must validate
against `Advisory`. Validation failure is a hard reject: it means the sample
never enters `data/final/`, or the inference response is retried/escalated.

Pydantic v2.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

CauseType = Literal["pest", "disease", "nutrient", "abiotic", "weed"]


class Cause(BaseModel):
    """A single candidate diagnosis for the farmer's reported symptoms."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=2,
        description="Common name of the pest/disease/disorder, e.g. 'pink bollworm'.",
    )
    type: CauseType = Field(
        ...,
        description="Category of the causal agent.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Calibrated likelihood this is the cause, given the symptoms described.",
    )
    evidence: str = Field(
        ...,
        min_length=3,
        description="Symptoms/context from the query that support this cause.",
    )


class ChemicalOption(BaseModel):
    """One CIB&RC label-claim-backed chemical control option.

    Every field here must trace to the CIB&RC register extract. If a value is
    not in the register, the option must be omitted entirely rather than guessed.
    """

    model_config = ConfigDict(extra="forbid")

    active_ingredient: str = Field(
        ...,
        min_length=2,
        description="Active ingredient with strength, e.g. 'emamectin benzoate 5% SG'.",
    )
    formulation: str = Field(
        ...,
        min_length=1,
        description="Formulation type, e.g. 'SG', 'SC', 'EC', 'WG'.",
    )
    dose_per_acre: str = Field(
        ...,
        min_length=1,
        description="Label dose per acre with units, e.g. '80 g/acre'.",
    )
    spray_volume_l_per_acre: int = Field(
        ...,
        gt=0,
        description="Water volume per acre in litres for the recommended spray.",
    )
    phi_days: int = Field(
        ...,
        ge=0,
        description="Pre-harvest interval (waiting period) in days.",
    )
    caution: str = Field(
        ...,
        min_length=3,
        description="Resistance, phytotoxicity, residue, bee/beneficial or mixing cautions.",
    )


class Advisory(BaseModel):
    """Top-level advisory response. This is the model's entire output."""

    model_config = ConfigDict(extra="forbid")

    in_scope: bool = Field(
        ...,
        description="False if the crop or topic is outside the frozen scope (see scope.py).",
    )
    query_understood: bool = Field(
        ...,
        description="False if the query is too vague/ambiguous to diagnose as written.",
    )
    clarifying_question: Optional[str] = Field(
        default=None,
        description="Single most informative follow-up question when query_understood is False.",
    )
    likely_causes: list[Cause] = Field(
        default=[],
        description="Ranked candidate causes, highest confidence first.",
    )
    non_chemical_first: list[str] = Field(
        default=[],
        description="Cultural/mechanical/biological measures to try before any spray.",
    )
    chemical_options: list[ChemicalOption] = Field(
        default=[],
        description="CIB&RC-approved chemical options; empty if none can be verified.",
    )
    safety: list[str] = Field(
        default=[],
        description="PPE, re-entry, mixing, disposal and residue/PHI safety instructions.",
    )
    escalate_to_expert: bool = Field(
        ...,
        description="True when a KVK/agri-officer must be consulted before acting.",
    )


__all__ = ["Cause", "CauseType", "ChemicalOption", "Advisory"]
