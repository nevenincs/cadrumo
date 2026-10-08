"""Canonical exact-profile filing record import request and result contracts."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import FilingRecordId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period
from ...domain.modelos.filing_record import (
    ExternalEvidenceKind,
    FilingDeclarationKind,
)
from ...domain.modelos.filing_text import EvidenceReference
from .filing_chain_reconciliation import (
    FilingReconciliationNotice,
    FilingReconciliationNoticeCode,
    FilingReconciliationOutcome,
    FilingReconciliationResult,
)
from .filing_record_list_contracts import ModeloFilingRecordListEntryProjection

MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID = "modelo.filing_record.import"


MAX_MODELO_FILING_RECORD_IMPORT_CASILLAS = 4_096


MAX_MODELO_FILING_RECORD_IMPORT_NOTICES = 32


MAX_MODELO_FILING_RECORD_IMPORT_CONTEXT_ITEMS = 32


MAX_MODELO_FILING_RECORD_IMPORT_SOURCE_PATH_LENGTH = 4_096


_SourcePath = Annotated[
    str,
    Field(
        min_length=1,
        max_length=MAX_MODELO_FILING_RECORD_IMPORT_SOURCE_PATH_LENGTH,
        pattern=r"\S",
    ),
]


_CasillaDecimalLexical = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?$",
    ),
]


_CasillaValues = Annotated[
    tuple[tuple[CasillaId, _CasillaDecimalLexical], ...],
    Field(max_length=MAX_MODELO_FILING_RECORD_IMPORT_CASILLAS),
]


_ContextItems = Annotated[
    tuple[tuple[Annotated[str, Field(min_length=1, max_length=128)], Annotated[str, Field(max_length=256)]], ...],
    Field(max_length=MAX_MODELO_FILING_RECORD_IMPORT_CONTEXT_ITEMS),
]


_AffectedFilingRecordIds = Annotated[
    tuple[FilingRecordId, ...], Field(max_length=MAX_MODELO_FILING_RECORD_IMPORT_CASILLAS)
]


_DifferingCasillaIds = Annotated[tuple[CasillaId, ...], Field(max_length=MAX_MODELO_FILING_RECORD_IMPORT_CASILLAS)]


def _validate_filing_import_casilla_value(key: CasillaId, lexical: str) -> None:
    """Admit a declared casilla and its finite two-place decimal without coercion."""
    validated_casilla_id(key, surface="filing record import")
    try:
        value = Decimal(lexical)
    except Exception as exc:  # pragma: no cover - the schema regex closes this input
        raise ValueError("filing import values must be canonical decimals") from exc
    exponent = value.as_tuple().exponent
    if not value.is_finite() or not isinstance(exponent, int) or -exponent > 2:
        raise ValueError("filing import values must be finite decimals with at most two fraction digits")


class ModeloFilingRecordImportRequest(BaseModel):
    """Immutable filing import intent, retained only through secure custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    work_unit_id: WorkUnitId
    evidence_kind: ExternalEvidenceKind
    evidence_reference_id: EvidenceReference
    declared_kind: FilingDeclarationKind | None = None
    actor: Annotated[str, Field(min_length=1, max_length=128, pattern=r"\S")] = "aeat-import"
    casilla_values: _CasillaValues = ()
    source_path: _SourcePath | None = None

    @model_validator(mode="after")
    def _one_casilla_source(self) -> Self:
        """Admit precisely one input source and canonical, finite direct values."""
        has_direct_values = bool(self.casilla_values)
        if (self.source_path is not None) == has_direct_values:
            raise ValueError("filing import requires exactly one of casilla values or source_path")
        keys = tuple(key for key, _value in self.casilla_values)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("filing import casilla values must have unique, sorted keys")
        for key, lexical in self.casilla_values:
            _validate_filing_import_casilla_value(key, lexical)
        if self.source_path is not None and ("\x00" in self.source_path or not self.source_path.strip()):
            raise ValueError("source_path must identify a local spreadsheet")
        return self


class ModeloFilingRecordImportNoticeProjection(BaseModel):
    """One stable reconciliation notice with bounded, sorted context."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: FilingReconciliationNoticeCode
    context: _ContextItems = ()

    @model_validator(mode="after")
    def _canonical_context(self) -> Self:
        keys = tuple(key for key, _value in self.context)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("filing import notice context keys must be unique and sorted")
        return self

    @classmethod
    def from_notice(cls, notice: FilingReconciliationNotice) -> ModeloFilingRecordImportNoticeProjection:
        """Copy stable notice fields without mutable mapping aliases."""
        return cls(code=notice.code, context=tuple(sorted(notice.context.items())))


class ModeloFilingRecordImportReconciliationProjection(BaseModel):
    """Allowlisted reconciliation fields matching the current CLI payload."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: FilingReconciliationOutcome
    bucket_id: BucketId
    modelo: Annotated[str, Field(min_length=3, max_length=3, pattern=r"^[0-9]{3}$")]
    filing_year: FilingYear
    period: Annotated[str, Field(min_length=1, max_length=16, pattern=r"\S")]
    member_nif: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    filing_record_id: FilingRecordId | None = None
    affected_filing_record_ids: _AffectedFilingRecordIds = ()
    differing_casilla_ids: _DifferingCasillaIds = ()
    evidence_basis: Literal["casillas", "receipt_totals"] | None = None
    notices: Annotated[
        tuple[ModeloFilingRecordImportNoticeProjection, ...], Field(max_length=MAX_MODELO_FILING_RECORD_IMPORT_NOTICES)
    ] = ()

    @model_validator(mode="after")
    def _validate_scope_and_order(self) -> Self:
        """Keep the result in its exact period and preserve canonical sequences."""
        Period.from_year_and_code(self.filing_year, self.period)
        if len(set(self.affected_filing_record_ids)) != len(self.affected_filing_record_ids):
            raise ValueError("filing import reconciliation repeats an affected record")
        if len(set(self.differing_casilla_ids)) != len(self.differing_casilla_ids):
            raise ValueError("filing import reconciliation repeats a differing casilla")
        return self

    @classmethod
    def from_result(
        cls,
        result: FilingReconciliationResult,
    ) -> ModeloFilingRecordImportReconciliationProjection:
        """Copy the complete public reconciliation result in bounded form."""
        return cls(
            outcome=result.outcome,
            bucket_id=result.bucket_id,
            modelo=result.modelo,
            filing_year=result.filing_year,
            period=result.period.registry_token,
            member_nif=result.member_nif,
            filing_record_id=result.filing_record_id,
            affected_filing_record_ids=result.affected_filing_record_ids,
            differing_casilla_ids=result.differing_casilla_ids,
            evidence_basis=result.evidence_basis,
            notices=tuple(ModeloFilingRecordImportNoticeProjection.from_notice(notice) for notice in result.notices),
        )

    def to_result(self) -> FilingReconciliationResult:
        """Rebuild the canonical application result for the established renderer."""
        return FilingReconciliationResult(
            outcome=self.outcome,
            bucket_id=self.bucket_id,
            modelo=self.modelo,
            filing_year=self.filing_year,
            period=Period.from_year_and_code(self.filing_year, self.period),
            member_nif=self.member_nif,
            filing_record_id=self.filing_record_id,
            affected_filing_record_ids=self.affected_filing_record_ids,
            differing_casilla_ids=self.differing_casilla_ids,
            evidence_basis=self.evidence_basis,
            notices=tuple(
                FilingReconciliationNotice(code=notice.code, context=dict(notice.context)) for notice in self.notices
            ),
        )


def _filing_import_receipt_outside_scope(
    profile_id: UUID,
    record: ModeloFilingRecordListEntryProjection,
    reconciliation: ModeloFilingRecordImportReconciliationProjection,
) -> bool:
    """Correlate the complete imported receipt in its original refusal order."""
    return (
        record.bucket_id != str(profile_id)
        or reconciliation.bucket_id != str(profile_id)
        or reconciliation.filing_record_id != record.filing_record_id
        or reconciliation.modelo != str(record.modelo)
        or reconciliation.filing_year != record.filing_year
        or reconciliation.period != record.period
        or reconciliation.member_nif != record.member_nif
        or record.external_evidence is None
    )


class ModeloFilingRecordImportProjection(BaseModel):
    """Safe filing receipt and complete reconciliation result for CLI parity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    record: ModeloFilingRecordListEntryProjection
    reconciliation: ModeloFilingRecordImportReconciliationProjection

    @model_validator(mode="after")
    def _correlate_receipt_and_reconciliation(self) -> Self:
        """Refuse a result that crosses a profile, receipt, or filing coordinate."""
        record = self.record
        reconciliation = self.reconciliation
        if _filing_import_receipt_outside_scope(self.profile_id, record, reconciliation):
            raise ValueError("filing import receipt exceeds its profile or reconciliation scope")
        if reconciliation.outcome is FilingReconciliationOutcome.UNVERIFIABLE:
            raise ValueError("unverifiable filing imports do not produce a filing receipt")
        return self


class ModeloFilingRecordImportOperationReport(BaseModel):
    """Private encrypted result retaining the writer-effect witness."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: ModeloFilingRecordImportProjection
    local_write_performed: bool
