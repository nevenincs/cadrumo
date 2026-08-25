"""Reviewed DP30302 semantic field-population matrix across the five M303 design epochs.

The official record-design binaries own field text, ordinal position and count.
This module owns only the reviewed partition scheme applied to that text and
the sub-index axis a repeating module description requires, plus the resulting
per-epoch measurement persisted as a checked artefact.  It neither infers
registry meaning, resolves a projection endpoint, nor claims declaration
coverage: it is a development-time census, not a production authority.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

import rtoml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.domain.calculations.registry.ids import (
    ModeloId,
    SourceRefId,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority

from ..pipeline._record_design_ir import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    load_record_design_intermediate,
)
from ..pipeline._semantic_map_validation import validate_inspection_source_authority

__all__ = [
    "DP30302_EPOCHS",
    "DP30302_EPOCH_COORDINATES",
    "DP30302EpochCoordinate",
    "DP30302EpochFieldMatrix",
    "DP30302FieldMatrix",
    "DP30302FieldPartition",
    "DP30302RepeatingModuleFamily",
    "DP30302RepeatingModuleFamilyEpoch",
    "classify_dp30302_field_description",
    "dp30302_activity_slot",
    "generalize_dp30302_field_description",
    "load_dp30302_epoch_intermediates",
    "load_dp30302_field_matrix",
    "measure_dp30302_field_matrix",
    "resolve_dp30302_module_sub_indices",
]


@dataclass(frozen=True, slots=True)
class DP30302EpochCoordinate:
    """One M303 filing coordinate whose selected snapshot admits one DP30302 design."""

    source_ref: SourceRefId
    filing_year: int
    period: str
    epoch: str


DP30302_EPOCH_COORDINATES: Final[tuple[DP30302EpochCoordinate, ...]] = (
    DP30302EpochCoordinate("aeat-dr-303-2023", 2023, "4T", "2023"),
    DP30302EpochCoordinate("aeat-dr-303-2024-early", 2024, "2T", "2024-early"),
    DP30302EpochCoordinate("aeat-dr-303-2024-late", 2024, "3T", "2024-late"),
    DP30302EpochCoordinate("aeat-dr-303-2025", 2025, "4T", "2025"),
    DP30302EpochCoordinate("aeat-dr-303-2026", 2026, "4T", "2026"),
)
DP30302_EPOCHS: Final[tuple[str, ...]] = tuple(coordinate.epoch for coordinate in DP30302_EPOCH_COORDINATES)

_RESERVE_DESCRIPTION: Final[str] = "Reservado para la AEAT"
_CONSTANT_DESCRIPTIONS: Final[frozenset[str]] = frozenset(
    {
        "Inicio del identificador de modelo y página.",
        "Modelo.",
        "Página.",
        "Fin de identificador de modelo.",
        "Indicador de fin de registro",
    },
)
_PRODUCER_PREFIX: Final[str] = "Indicador de página complementaria"
_NUMBERED_TRAILING_BOX: Final[re.Pattern[str]] = re.compile(r"\[(\d{2,3})\]\s*$")
_AGRICOLA_MARKER: Final[str] = "(A) Actividades agrícolas, ganaderas y forestales - Actividad"
_NO_AGRICOLA_MARKER: Final[str] = "(B) Actividades en RS (exc. a, g y f) - Actividad"
_ACTIVIDAD_SLOT: Final[re.Pattern[str]] = re.compile(r"Actividad (\d+)")


class _StrictModel(BaseModel):
    """Frozen development-tool boundary model with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class DP30302FieldPartition(StrEnum):
    """The six mutually exclusive, exhaustive DP30302 field roles.

    ``simplified`` is deliberately absent: it is the derived union of
    ``AGRICOLA`` and ``NO_AGRICOLA``, never a field's own classification.
    """

    AGRICOLA = "agricola"
    NO_AGRICOLA = "no_agricola"
    NUMBERED = "numbered"
    CONSTANT = "constant"
    RESERVE = "reserve"
    PRODUCER = "producer"


def classify_dp30302_field_description(normalized_description: str) -> DP30302FieldPartition:
    """Classify one exact DP30302 field description into its one reviewed partition.

    Fail-closed: raises :class:`RegistryValidationError` on any description
    outside the six reviewed shapes, so an anchor can never fall silently into
    an unaccounted bucket.  A numbered official box is distinguished from a
    per-activity letter-referenced operand (``[A]``, ``[Z]`` ...) by requiring
    the trailing bracket to hold two or three digits.
    """
    if normalized_description == _RESERVE_DESCRIPTION:
        return DP30302FieldPartition.RESERVE
    if normalized_description in _CONSTANT_DESCRIPTIONS:
        return DP30302FieldPartition.CONSTANT
    if normalized_description.startswith(_PRODUCER_PREFIX):
        return DP30302FieldPartition.PRODUCER
    if _NUMBERED_TRAILING_BOX.search(normalized_description):
        return DP30302FieldPartition.NUMBERED
    if _AGRICOLA_MARKER in normalized_description:
        return DP30302FieldPartition.AGRICOLA
    if _NO_AGRICOLA_MARKER in normalized_description:
        return DP30302FieldPartition.NO_AGRICOLA
    raise RegistryValidationError(
        f"DP30302 field description does not resolve to a reviewed partition: {normalized_description!r}",
    )


def dp30302_activity_slot(normalized_description: str) -> int | None:
    """Return the one-based activity slot named in a per-activity description, else ``None``."""
    match = _ACTIVIDAD_SLOT.search(normalized_description)
    return int(match.group(1)) if match else None


def generalize_dp30302_field_description(normalized_description: str) -> str:
    """Replace the activity-slot digit with a stable placeholder for family grouping."""
    return _ACTIVIDAD_SLOT.sub("Actividad N", normalized_description)


def _numeric_module_ordinal(ordinal: str | None) -> int:
    """Parse a repeating-module field's printed ordinal as its numeric sort position.

    A string sort would put ``"2"`` after ``"10"`` and silently invert the
    sub-index run this resolves, so ordering needs the real numeric value.
    Every DP30302 repeating-module row is a plain AEAT-numbered box -- never
    blank, dotted, or ``bis``-suffixed in this range -- so parsing here reads
    the source's own printed number rather than fabricating one; anything else
    is a genuine corpus surprise this refuses loudly rather than mis-order.
    """
    if ordinal is None or not ordinal.isdigit():
        raise RegistryValidationError(f"DP30302 module field ordinal is not a plain numbered label: {ordinal!r}")
    return int(ordinal)


def resolve_dp30302_module_sub_indices(fields: Sequence[RecordDesignIntermediateField]) -> dict[str | None, int]:
    """Assign a deterministic, gap-free sub-index to every repeating module field.

    Fields are grouped by their exact activity slot and generalized
    description; within each group, source ordinal order fixes the sub-index
    AEAT's own description text does not name (the tariff-tier or
    module-repeat position).  Refuses ambiguous input — a group carrying a
    duplicate ordinal — rather than guessing an order.  Returns the mapping
    keyed by source ordinal so callers can join it back onto the exact anchor.
    """
    groups: dict[tuple[int, str], list[RecordDesignIntermediateField]] = defaultdict(list)
    for field in fields:
        slot = dp30302_activity_slot(field.normalized_description)
        if slot is None:
            continue
        key = (slot, generalize_dp30302_field_description(field.normalized_description))
        groups[key].append(field)

    sub_index_by_ordinal: dict[str | None, int] = {}
    for (slot, generalized), members in groups.items():
        ordinals = tuple(member.ordinal for member in members)
        if len(set(ordinals)) != len(ordinals):
            raise RegistryValidationError(
                f"DP30302 module family {generalized!r} activity {slot} carries duplicate ordinals: {ordinals!r}",
            )
        ordered_members = sorted(members, key=lambda field: _numeric_module_ordinal(field.ordinal))
        for sub_index, member in enumerate(ordered_members, start=1):
            sub_index_by_ordinal[member.ordinal] = sub_index
    return sub_index_by_ordinal


class DP30302EpochFieldMatrix(_StrictModel):
    """One reviewed epoch's exact DP30302 field-population census."""

    epoch: str = Field(min_length=1)
    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    total: int = Field(gt=0)
    agricola: int = Field(ge=0)
    no_agricola: int = Field(ge=0)
    simplified: int = Field(gt=0)
    numbered: int = Field(ge=0)
    constant: int = Field(ge=0)
    reserve: int = Field(ge=0)
    producer: int = Field(ge=0)

    @model_validator(mode="after")
    def _require_exhaustive_disjoint_partition(self) -> DP30302EpochFieldMatrix:
        if self.simplified != self.agricola + self.no_agricola:
            raise ValueError(
                f"DP30302 {self.epoch} simplified count {self.simplified} must equal agrícola plus no agrícola "
                f"({self.agricola + self.no_agricola})",
            )
        partition_sum = self.agricola + self.no_agricola + self.numbered + self.constant + self.reserve + self.producer
        if partition_sum != self.total:
            raise ValueError(
                f"DP30302 {self.epoch} partition counts sum to {partition_sum}, expected total {self.total}",
            )
        return self


class DP30302RepeatingModuleFamilyEpoch(_StrictModel):
    """One epoch's measured per-activity-slot sub-index cardinality for a family."""

    epoch: str = Field(min_length=1)
    sub_index_cardinality: int = Field(ge=1)


class DP30302RepeatingModuleFamily(_StrictModel):
    """One generalized module description whose sub-index cardinality exceeds one.

    A family exists in this list only where at least one epoch repeats the
    description more than once per activity slot — the shape a declaration
    schema must address with a sub-index axis rather than an ad-hoc endpoint
    per occurrence.
    """

    generalized_description: str = Field(min_length=1)
    epochs: tuple[DP30302RepeatingModuleFamilyEpoch, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_unique_epochs_and_genuine_repetition(self) -> DP30302RepeatingModuleFamily:
        epoch_names = tuple(entry.epoch for entry in self.epochs)
        if len(set(epoch_names)) != len(epoch_names):
            raise ValueError(f"DP30302 module family {self.generalized_description!r} repeats an epoch entry")
        if any(epoch not in DP30302_EPOCHS for epoch in epoch_names):
            raise ValueError(f"DP30302 module family {self.generalized_description!r} names an unknown epoch")
        if max(entry.sub_index_cardinality for entry in self.epochs) <= 1:
            raise ValueError(
                f"DP30302 module family {self.generalized_description!r} never exceeds one occurrence per slot",
            )
        return self


class DP30302FieldMatrix(_StrictModel):
    """The complete reviewed five-epoch DP30302 semantic field matrix."""

    schema_version: Literal[1]
    modelo: ModeloId
    epochs: tuple[DP30302EpochFieldMatrix, ...] = Field(min_length=1)
    distinct_field_semantics: int = Field(gt=0)
    repeating_module_families: tuple[DP30302RepeatingModuleFamily, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_exact_epoch_set(self) -> DP30302FieldMatrix:
        epoch_names = tuple(entry.epoch for entry in self.epochs)
        if epoch_names != DP30302_EPOCHS:
            raise ValueError(f"DP30302 field matrix must cover exactly the five epochs in order: {DP30302_EPOCHS!r}")
        return self


def load_dp30302_epoch_intermediates(
    authority: ValidatedRegistryAuthority,
) -> tuple[RecordDesignIntermediate, ...]:
    """Load the five DP30302 designs through selected static inspections."""
    intermediates: list[RecordDesignIntermediate] = []
    for coordinate in DP30302_EPOCH_COORDINATES:
        inspection = authority.inspect_revision(
            "303",
            filing_year=coordinate.filing_year,
            period=coordinate.period,
        )
        intermediate = load_record_design_intermediate(
            authority.source_root,
            inspection.sources,
            source_ref=coordinate.source_ref,
            filing_year=coordinate.filing_year,
            design_epoch=coordinate.epoch,
        )
        validate_inspection_source_authority(intermediate, inspection)
        intermediates.append(intermediate)
    return tuple(intermediates)


def _measure_dp30302_epoch(
    intermediate: RecordDesignIntermediate,
    *,
    epoch: str,
) -> tuple[DP30302EpochFieldMatrix, set[str], dict[str, set[int]]]:
    sheet = next((sheet for sheet in intermediate.sheets if sheet.record_identity == "DP30302"), None)
    if sheet is None:
        raise RegistryValidationError(f"official design {intermediate.source.source_ref!r} carries no DP30302 sheet")

    counts: Counter[DP30302FieldPartition] = Counter()
    distinct_semantics: set[str] = set()
    family_cardinality: dict[str, set[int]] = defaultdict(set)
    slot_groups: dict[tuple[int, str], int] = defaultdict(int)
    for field in sheet.fields:
        counts[classify_dp30302_field_description(field.normalized_description)] += 1
        generalized = generalize_dp30302_field_description(field.normalized_description)
        distinct_semantics.add(generalized)
        slot = dp30302_activity_slot(field.normalized_description)
        if slot is not None:
            slot_groups[(slot, generalized)] += 1

    for (_slot, generalized), count in slot_groups.items():
        family_cardinality[generalized].add(count)
    agricola = counts[DP30302FieldPartition.AGRICOLA]
    no_agricola = counts[DP30302FieldPartition.NO_AGRICOLA]
    return (
        DP30302EpochFieldMatrix(
            epoch=epoch,
            source_ref=intermediate.source.source_ref,
            source_sha256=intermediate.source.source_sha256,
            total=len(sheet.fields),
            agricola=agricola,
            no_agricola=no_agricola,
            simplified=agricola + no_agricola,
            numbered=counts[DP30302FieldPartition.NUMBERED],
            constant=counts[DP30302FieldPartition.CONSTANT],
            reserve=counts[DP30302FieldPartition.RESERVE],
            producer=counts[DP30302FieldPartition.PRODUCER],
        ),
        distinct_semantics,
        family_cardinality,
    )


def measure_dp30302_field_matrix(authority: ValidatedRegistryAuthority) -> DP30302FieldMatrix:
    """Recompute the complete DP30302 matrix from five validated source inspections.

    Each parsed binary is admitted by its filing-context-selected
    :class:`ValidatedRegistryAuthority` inspection before measurement.  This
    neither reads a directory listing nor admits catalogue rows outside the
    selected revision authority.
    """
    epoch_matrices: list[DP30302EpochFieldMatrix] = []
    distinct_semantics: set[str] = set()
    family_cardinality: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))

    for coordinate, intermediate in zip(
        DP30302_EPOCH_COORDINATES,
        load_dp30302_epoch_intermediates(authority),
        strict=True,
    ):
        epoch_matrix, epoch_semantics, epoch_family_cardinality = _measure_dp30302_epoch(
            intermediate,
            epoch=coordinate.epoch,
        )
        epoch_matrices.append(epoch_matrix)
        distinct_semantics.update(epoch_semantics)
        for generalized, cardinalities in epoch_family_cardinality.items():
            family_cardinality[generalized][coordinate.epoch].update(cardinalities)

    families: list[DP30302RepeatingModuleFamily] = []
    for generalized in sorted(family_cardinality):
        per_epoch = family_cardinality[generalized]
        if max(max(cards) for cards in per_epoch.values()) <= 1:
            continue
        epoch_entries: list[DP30302RepeatingModuleFamilyEpoch] = []
        for epoch in DP30302_EPOCHS:
            cards = per_epoch.get(epoch)
            if not cards:
                continue
            if len(cards) != 1:
                raise RegistryValidationError(
                    f"DP30302 module family {generalized!r} has inconsistent per-slot cardinality "
                    f"in {epoch}: {sorted(cards)!r}",
                )
            epoch_entries.append(
                DP30302RepeatingModuleFamilyEpoch(epoch=epoch, sub_index_cardinality=next(iter(cards))),
            )
        families.append(
            DP30302RepeatingModuleFamily(generalized_description=generalized, epochs=tuple(epoch_entries)),
        )

    return DP30302FieldMatrix(
        schema_version=1,
        modelo="303",
        epochs=tuple(epoch_matrices),
        distinct_field_semantics=len(distinct_semantics),
        repeating_module_families=tuple(families),
    )


def load_dp30302_field_matrix(path: Path) -> DP30302FieldMatrix:
    """Load the persisted reviewed DP30302 matrix without weakening its strict schema."""
    if not path.is_file() or path.is_symlink() or path.is_junction():
        raise RegistryValidationError(f"DP30302 field matrix path must be a real file: {path}")
    try:
        payload = rtoml.load(path)
    except rtoml.TomlParsingError as exc:
        raise RegistryValidationError(f"DP30302 field matrix is not valid TOML: {path}") from exc
    # JSON has no native tuple type, so round-tripping through model_validate_json
    # admits TOML's arrays into the model's strict tuple fields without loosening
    # the model's own strict boundary for any other caller.
    return DP30302FieldMatrix.model_validate_json(json.dumps(payload))
