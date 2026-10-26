"""Working state shared by read-only authored-family assessment stages."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from cadrumo.domain.calculations.registry.keyed_families import KeyedFamilySpec
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision


@dataclass(slots=True)
class AssessmentRun:
    """One modelo's assessment inputs and the totals, findings and rows accumulated across its revisions."""

    modelo_dir: Path
    fingerprint: str
    input_fingerprints: tuple[Mapping[str, str], ...]
    definition: ModeloDefinition
    totals: Counter[str] = field(default_factory=Counter)
    unresolved: list[Mapping[str, object]] = field(default_factory=list)
    blocked: list[Mapping[str, object]] = field(default_factory=list)
    rows: list[Mapping[str, object]] = field(default_factory=list)


@dataclass(slots=True)
class FamilyRun:
    """One family of one revision being measured, with its counters and findings."""

    run: AssessmentRun
    revision: ModeloRevision
    revision_id: str
    raw: Mapping[str, object]
    previous: str | None
    spec: KeyedFamilySpec
    row: Counter[str] = field(default_factory=Counter)
    unresolved: list[Mapping[str, object]] = field(default_factory=list)
    blocked: list[Mapping[str, object]] = field(default_factory=list)
    include_row: bool = True


@dataclass(frozen=True, slots=True)
class FamilyBaseline:
    """The storage baseline a family is compared against and how that baseline was declared."""

    candidate_id: str | None
    baseline_id: str | None
    explicit_root: bool
    stated_root: bool
    net_of_edition_tokens: bool
    storage_support_missing: bool


__all__ = ("AssessmentRun", "FamilyBaseline", "FamilyRun")
