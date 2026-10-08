"""Immutable finding and report facts with exact registry coordinates."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.identifier_grammar import NAMESPACED_ID_PATTERN
from ...core.identity.hex_ids import CalculationRevisionId, VerificationReportId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period, PeriodError
from ...core.time.utc import validate_utc_aware
from ...domain.calculations.registry.ids import (
    LegalRefId,
    ModeloId,
    RevisionId,
    SourceRefId,
    VerificationExpectationId,
)
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
)
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .verification_report_read_contracts import (
    MAX_MODELO_VERIFICATION_REPORT_CASILLAS,
    MAX_MODELO_VERIFICATION_REPORT_FACTS,
    MAX_MODELO_VERIFICATION_REPORT_FINDING_REFS,
    MAX_MODELO_VERIFICATION_REPORT_FINDINGS,
)
from .verification_report_scalar_facts import ModeloVerificationFactProjection, verification_fact_value_is_bounded

_FindingLocaleKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=200, pattern=NAMESPACED_ID_PATTERN),
]


_ReportCasillas = Annotated[tuple[CasillaId, ...], Field(max_length=MAX_MODELO_VERIFICATION_REPORT_CASILLAS)]


class ModeloVerificationRegistrySnapshotProjection(BaseModel):
    """Closed scalar coordinates for a verification report's registry ref."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: ModeloId
    revision_id: RevisionId
    modelo_year: FilingYear
    period: Annotated[str, Field(min_length=1, max_length=16)]

    @model_validator(mode="after")
    def _period_is_canonical(self) -> Self:
        try:
            parsed = Period.from_year_and_code(self.modelo_year, self.period)
        except PeriodError:
            raise ValueError("verification report registry period is invalid") from None
        if parsed.registry_token != self.period:
            raise ValueError("verification report registry period must be canonical")
        return self

    @classmethod
    def from_snapshot(cls, reference: RegistrySnapshotRef) -> ModeloVerificationRegistrySnapshotProjection:
        """Copy the domain reference into schema-safe scalar fields."""
        return cls(
            modelo=str(reference.modelo),
            revision_id=str(reference.revision_id),
            modelo_year=reference.modelo_year,
            period=str(reference.period),
        )


_FindingFacts = Annotated[
    tuple[ModeloVerificationFactProjection, ...], Field(max_length=MAX_MODELO_VERIFICATION_REPORT_FACTS)
]


class ModeloVerificationFindingProjection(BaseModel):
    """Bounded locale-neutral finding facts, retaining legal and source refs."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: ModeloVerificationFindingKind
    severity: ModeloVerificationFindingSeverity
    casilla_id: CasillaId | None = None
    expectation_id: VerificationExpectationId | None = None
    message_locale_key: _FindingLocaleKey
    message_facts: _FindingFacts = ()
    legal_refs: Annotated[
        tuple[LegalRefId, ...], Field(min_length=1, max_length=MAX_MODELO_VERIFICATION_REPORT_FINDING_REFS)
    ]
    source_refs: Annotated[tuple[SourceRefId, ...], Field(max_length=MAX_MODELO_VERIFICATION_REPORT_FINDING_REFS)] = ()

    @model_validator(mode="after")
    def _unique_refs(self) -> Self:
        if len(set(self.legal_refs)) != len(self.legal_refs) or len(set(self.source_refs)) != len(self.source_refs):
            raise ValueError("verification finding references must not repeat")
        fact_keys = tuple(fact.key for fact in self.message_facts)
        if fact_keys != tuple(sorted(set(fact_keys))):
            raise ValueError("verification finding facts must be unique and ordered")
        return self

    @classmethod
    def from_finding(cls, finding: ModeloVerificationFinding) -> ModeloVerificationFindingProjection:
        """Copy every locale-neutral finding fact without rendering or truncating it."""
        if (
            len(finding.message_facts) > MAX_MODELO_VERIFICATION_REPORT_FACTS
            or any(len(key) > 128 for key in finding.message_facts)
            or len(finding.legal_refs) > MAX_MODELO_VERIFICATION_REPORT_FINDING_REFS
            or len(finding.source_refs) > MAX_MODELO_VERIFICATION_REPORT_FINDING_REFS
            or any(not verification_fact_value_is_bounded(item) for item in finding.message_facts.values())
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return cls(
            kind=finding.kind,
            severity=finding.severity,
            casilla_id=finding.casilla_id,
            expectation_id=finding.expectation_id,
            message_locale_key=finding.message_locale_key,
            message_facts=tuple(
                ModeloVerificationFactProjection.from_fact(key, value)
                for key, value in sorted(finding.message_facts.items())
            ),
            legal_refs=finding.legal_refs,
            source_refs=finding.source_refs,
        )

    def to_finding(self) -> ModeloVerificationFinding:
        """Restore the persisted domain finding this projection copied, without authoring a new one."""
        return ModeloVerificationFinding.model_validate(
            {
                "kind": self.kind,
                "severity": self.severity,
                "casilla_id": self.casilla_id,
                "expectation_id": self.expectation_id,
                "message_locale_key": self.message_locale_key,
                "message_facts": {fact.key: fact.typed_value() for fact in self.message_facts},
                "legal_refs": self.legal_refs,
                "source_refs": self.source_refs,
            }
        )


class ModeloVerificationReportProjection(BaseModel):
    """Complete bounded public facts from one persisted verification report."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    verification_report_id: VerificationReportId
    calculation_revision_id: CalculationRevisionId
    registry_snapshot_ref: ModeloVerificationRegistrySnapshotProjection
    completeness_status: VerificationCompletenessStatus
    granted_verificado_completo: bool
    resolved_casilla_ids: _ReportCasillas
    missing_required_casilla_ids: _ReportCasillas
    run_at: datetime
    verified_by: Annotated[str, Field(min_length=1, max_length=64)]
    findings: Annotated[
        tuple[ModeloVerificationFindingProjection, ...], Field(max_length=MAX_MODELO_VERIFICATION_REPORT_FINDINGS)
    ]

    @field_validator("run_at")
    @classmethod
    @pydantic_validation_boundary
    def _run_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _report_invariants(self) -> Self:
        if set(self.resolved_casilla_ids) & set(self.missing_required_casilla_ids):
            raise ValueError("verification report casillas cannot be both resolved and missing")
        if len(set(self.resolved_casilla_ids)) != len(self.resolved_casilla_ids):
            raise ValueError("resolved verification report casillas must not repeat")
        if len(set(self.missing_required_casilla_ids)) != len(self.missing_required_casilla_ids):
            raise ValueError("missing verification report casillas must not repeat")
        has_blocking = any(finding.severity is ModeloVerificationFindingSeverity.BLOCKING for finding in self.findings)
        if self.granted_verificado_completo != (
            self.completeness_status is VerificationCompletenessStatus.COMPLETE and not has_blocking
        ):
            raise ValueError("verification report grant must match its completeness and findings")
        if self.run_at.tzinfo is None:
            raise ValueError("verification report timestamp must be timezone-aware")
        return self

    @classmethod
    def from_report(cls, report: VerificationReport) -> ModeloVerificationReportProjection:
        """Copy the full report projection, refusing instead of clipping large records."""
        if (
            len(report.findings) > MAX_MODELO_VERIFICATION_REPORT_FINDINGS
            or len(report.resolved_casilla_ids) > MAX_MODELO_VERIFICATION_REPORT_CASILLAS
            or len(report.missing_required_casilla_ids) > MAX_MODELO_VERIFICATION_REPORT_CASILLAS
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return cls(
            verification_report_id=report.verification_report_id,
            calculation_revision_id=report.calculation_revision_id,
            registry_snapshot_ref=ModeloVerificationRegistrySnapshotProjection.from_snapshot(
                report.registry_snapshot_ref
            ),
            completeness_status=report.completeness_status,
            granted_verificado_completo=report.granted_verificado_completo,
            resolved_casilla_ids=report.resolved_casilla_ids,
            missing_required_casilla_ids=report.missing_required_casilla_ids,
            run_at=report.run_at,
            verified_by=report.verified_by,
            findings=tuple(ModeloVerificationFindingProjection.from_finding(finding) for finding in report.findings),
        )

    def to_report(self) -> VerificationReport:
        """Restore the persisted domain report, so the existing renderer owns localization."""
        snapshot = self.registry_snapshot_ref
        return VerificationReport(
            verification_report_id=self.verification_report_id,
            calculation_revision_id=self.calculation_revision_id,
            registry_snapshot_ref=RegistrySnapshotRef(
                modelo=snapshot.modelo,
                revision_id=snapshot.revision_id,
                modelo_year=snapshot.modelo_year,
                period=snapshot.period,
            ),
            completeness_status=self.completeness_status,
            findings=tuple(finding.to_finding() for finding in self.findings),
            resolved_casilla_ids=self.resolved_casilla_ids,
            missing_required_casilla_ids=self.missing_required_casilla_ids,
            run_at=self.run_at,
            verified_by=self.verified_by,
            granted_verificado_completo=self.granted_verificado_completo,
        )
