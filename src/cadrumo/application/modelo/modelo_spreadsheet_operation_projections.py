"""Strict renderer-neutral spreadsheet operation projections and read facts."""

from __future__ import annotations

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.ids import (
    BindingId,
    FormulaId,
    LegalRefId,
    ModeloId,
    RelationId,
    RevisionId,
    SourceRefId,
)
from ..operations.public_period import PublicPeriod
from ..storage.calc_sheets.records import SheetRelationProvenanceValue
from .modelo_spreadsheet_observations import SpreadsheetAssembledObservation

_PathText = Annotated[str, Field(min_length=1, max_length=4096, pattern=r"\S")]
_Text = Annotated[str, Field(max_length=4096)]
_Handle = Annotated[str, Field(min_length=1, max_length=4096)]
_Count = Annotated[int, Field(ge=0)]
MAX_MODELO_SPREADSHEET_ROWS = 65_536


class ModeloSpreadsheetProjection(BaseModel):
    """Encrypted renderer-neutral result with its owning profile coordinate."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    modelo: ModeloId
    revision: RevisionId
    period: PublicPeriod


class ModeloSpreadsheetExportProjection(ModeloSpreadsheetProjection):
    """The same existing workbook publication receipt and coverage facts."""

    output_path: _PathText
    byte_size: _Count
    sha256: Hex64Str
    tab_names: Annotated[tuple[_Text, ...], Field(min_length=1, max_length=128)]
    casilla_count: _Count
    prefill_relations: bool


class SpreadsheetPullMetadata(BaseModel):
    """Every identity stamp already exposed by the canonical pull surface."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    modelo_id: _Text
    revision_id: RevisionId
    filing_year: int
    period: _Text
    engine_version: _Text
    registry_sha: _Text
    exported_at: _Text | None = None


class SpreadsheetOperatorEdit(BaseModel):
    """Populated casilla row, preserving the existing textual scalar projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    casilla_id: CasillaId
    label: _Text
    value: _Text | None = None


class SpreadsheetBindingEdit(BaseModel):
    """One numeric or enum binding cell."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    binding: BindingId
    value: _Text | None = None


class SpreadsheetRelationEdit(BaseModel):
    """Preserve all existing relation provenance beside its textual value."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    relation: RelationId
    value: _Text | None = None
    provenance: SheetRelationProvenanceValue | None = None
    source_modelo: ModeloId | None = None
    source_filing_year: int | None = None
    source_periods: tuple[str, ...] = ()
    source_casilla_ids: tuple[CasillaId, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()
    resolved_at: _Text | None = None


class SpreadsheetRowSetCell(SpreadsheetBindingEdit):
    """A populated row cell retaining its exact declared row coordinate."""

    row_index: Annotated[int, Field(ge=1)]


class SpreadsheetRowSet(BaseModel):
    """One populated canonical worksheet grouping."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    grouping: _Handle
    cells: Annotated[tuple[SpreadsheetRowSetCell, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]


class SpreadsheetAssembledGrouping(BaseModel):
    """The canonical assembler's existing JSON observations, without persistence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    grouping: _Handle
    source_kind: _Handle
    observation_count: _Count
    observations: Annotated[tuple[SpreadsheetAssembledObservation, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]

    @model_validator(mode="after")
    def _complete_observations(self) -> Self:
        if self.observation_count != len(self.observations):
            raise ValueError("assembled observation count disagrees with its rows")
        return self


class SpreadsheetReadFacts(BaseModel):
    """Read facts common to the existing pull and calculate projections."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    spreadsheet_id: _Handle
    cells_read: _Count
    operator_edits_populated: _Count
    binding_edits_populated: _Count
    relation_edits_populated: _Count


class SpreadsheetPullFacts(SpreadsheetReadFacts):
    """Normalized inbound facts, not an adapter object or a new ingress algorithm."""

    metadata_match: Literal["matches", "stale", "missing"]
    metadata: SpreadsheetPullMetadata
    operator_edits_total: _Count
    operator_edits: Annotated[tuple[SpreadsheetOperatorEdit, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]
    binding_edits: Annotated[tuple[SpreadsheetBindingEdit, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]
    relation_edits: Annotated[tuple[SpreadsheetRelationEdit, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]
    row_set_edits_populated: _Count
    row_set_cells_populated: _Count
    row_set_edits: Annotated[tuple[SpreadsheetRowSet, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]
    assembled_groupings: Annotated[
        tuple[SpreadsheetAssembledGrouping, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)
    ]
    assembled_observation_count: _Count

    @model_validator(mode="after")
    def _complete_counts(self) -> Self:
        if not _edit_counts_match(self) or not _row_set_counts_match(self) or not _assembled_count_matches(self):
            raise ValueError("spreadsheet pull counts disagree with their complete rows")
        return self


def _edit_counts_match(facts: SpreadsheetPullFacts) -> bool:
    return (
        facts.operator_edits_populated == len(facts.operator_edits)
        and facts.operator_edits_total >= facts.operator_edits_populated
        and facts.binding_edits_populated == len(facts.binding_edits)
        and facts.relation_edits_populated == len(facts.relation_edits)
    )


def _row_set_counts_match(facts: SpreadsheetPullFacts) -> bool:
    return facts.row_set_edits_populated == len(facts.row_set_edits) and facts.row_set_cells_populated == sum(
        len(row.cells) for row in facts.row_set_edits
    )


def _assembled_count_matches(facts: SpreadsheetPullFacts) -> bool:
    return facts.assembled_observation_count == sum(row.observation_count for row in facts.assembled_groupings)


class SpreadsheetComputedCasilla(BaseModel):
    """Exactly the calculated value and grounding fields already disclosed."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    casilla_id: CasillaId
    value: _Text
    formula_id: FormulaId | None = None
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]


class SpreadsheetCalculateFacts(SpreadsheetReadFacts):
    """Canonical computation facts from a matching remote workbook."""

    metadata_match: Literal["matches"]
    computed: Annotated[tuple[SpreadsheetComputedCasilla, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]


class ModeloSpreadsheetPullProjection(ModeloSpreadsheetProjection, SpreadsheetPullFacts):
    """Complete current pull disclosure, bound to its registered profile."""


class ModeloSpreadsheetCalculateProjection(ModeloSpreadsheetProjection, SpreadsheetCalculateFacts):
    """Complete current calculation disclosure, with no local filing write."""


class SpreadsheetVerifyDivergence(BaseModel):
    """Existing three-way divergence row; absent oracle values stay absent."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    casilla_id: CasillaId
    label: _Text
    local: _Text | None = None
    sheets: _Text | None = None
    aeat: _Text | None = None


class SpreadsheetVerifyFacts(BaseModel):
    """Canonical report projection plus private transport write acknowledgement."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    spreadsheet_id: _Handle
    spreadsheet_url: _Handle
    verdict: Literal["all_match", "divergence", "inconclusive"]
    aeat_oracle_present: bool
    computed_count: _Count
    divergence_count: _Count
    divergences: Annotated[tuple[SpreadsheetVerifyDivergence, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]

    @model_validator(mode="after")
    def _complete_divergences(self) -> Self:
        if self.divergence_count != len(self.divergences):
            raise ValueError("parity divergence count disagrees with its complete rows")
        return self


class ModeloSpreadsheetVerifyProjection(ModeloSpreadsheetProjection, SpreadsheetVerifyFacts):
    """Current parity result, without disclosing provider write counters."""


__all__ = [
    "MAX_MODELO_SPREADSHEET_ROWS",
    "ModeloSpreadsheetCalculateProjection",
    "ModeloSpreadsheetExportProjection",
    "ModeloSpreadsheetProjection",
    "ModeloSpreadsheetPullProjection",
    "ModeloSpreadsheetVerifyProjection",
    "SpreadsheetAssembledGrouping",
    "SpreadsheetBindingEdit",
    "SpreadsheetCalculateFacts",
    "SpreadsheetComputedCasilla",
    "SpreadsheetOperatorEdit",
    "SpreadsheetPullFacts",
    "SpreadsheetPullMetadata",
    "SpreadsheetReadFacts",
    "SpreadsheetRelationEdit",
    "SpreadsheetRowSet",
    "SpreadsheetRowSetCell",
    "SpreadsheetVerifyDivergence",
    "SpreadsheetVerifyFacts",
]
