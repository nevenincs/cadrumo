"""Persisted amendment authority resolution for modelo export."""

from __future__ import annotations

from typing import NoReturn, Protocol

from ...application.filing import AmendmentEvidence
from ...core import Modelo
from ...domain.calculations.registry import bundled_authority
from ...domain.deadlines import TaxpayerProfile
from ...domain.justificante import Justificante, JustificanteRepositoryProtocol
from ...domain.modelos import (
    CalculationRevision,
    CalculationRevisionAggregateContext,
    CalculationRevisionAmendmentIdentity,
    CalculationRevisionAmendmentKind,
    M303RectificativaMotive,
    ModeloExportError,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordCatalogueRepositoryProtocol,
    WorkUnit,
    is_justificante_backed_external_evidence,
    validate_calculation_revision_aggregate,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol


class AmendmentExportCommand(Protocol):
    calculation_revision_id: str
    amendment_evidence: AmendmentEvidence | None


def resolve_persisted_amendment_export_evidence(
    command: AmendmentExportCommand,
    revision: CalculationRevision,
    *,
    work_unit: WorkUnit,
    workflow_profile: TaxpayerProfile,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    justificante_repository: JustificanteRepositoryProtocol | None,
) -> AmendmentEvidence | None:
    """Resolve immutable amendment evidence exclusively from persisted authority."""
    identity = revision.amendment_identity
    if identity is None:
        if command.amendment_evidence is not None:
            _raise(command, "typed amendment evidence was supplied for a non-amendment revision")
        return None
    records = filing_repository.load()
    target = _target(command, identity=identity, work_unit=work_unit, records=records)
    justificantes, receipt = _receipt(
        command,
        target=target,
        work_unit=work_unit,
        workflow_profile=workflow_profile,
        repository=justificante_repository,
    )
    motive, receipt_number = _evidence(
        command,
        revision=revision,
        identity=identity,
        work_unit=work_unit,
        workflow_profile=workflow_profile,
        work_unit_repository=work_unit_repository,
        records=records,
        justificantes=justificantes,
        receipt=receipt,
    )
    persisted = AmendmentEvidence(
        kind=identity.kind,
        m303_rectificativa_motive=motive,
        original_aeat_receipt=receipt_number,
    )
    if command.amendment_evidence is not None and command.amendment_evidence != persisted:
        _raise(command, "supplied amendment evidence diverges from persisted authority")
    return persisted


def _raise(command: AmendmentExportCommand, cause: str) -> NoReturn:
    raise ModeloExportError(
        translated_message="application.modelo.errors.export_draft_write_failed",
        context={"calculation_revision_id": command.calculation_revision_id, "cause": cause},
    )


def _target(
    command: AmendmentExportCommand,
    *,
    identity: CalculationRevisionAmendmentIdentity,
    work_unit: WorkUnit,
    records: ModeloRecordCatalogue,
) -> ModeloRecord:
    target = records.get(identity.amends_filing_record_id)
    if target is None or not target.aeat_accepted or target.external_evidence is None:
        _raise(command, "amended filing target lacks persisted AEAT evidence")
    if (
        target.work_unit_id,
        target.bucket_id,
        target.modelo,
        target.filing_year,
        target.period,
    ) != (
        work_unit.work_unit_id,
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
    ) or not is_justificante_backed_external_evidence(target.external_evidence.kind):
        _raise(command, "amended filing target crosses the export coordinate")
    return target


def _receipt(
    command: AmendmentExportCommand,
    *,
    target: ModeloRecord,
    work_unit: WorkUnit,
    workflow_profile: TaxpayerProfile,
    repository: JustificanteRepositoryProtocol | None,
) -> tuple[tuple[Justificante, ...], Justificante]:
    if repository is None:
        _raise(command, "amendment export requires injected justificante repository authority")
    evidence = target.external_evidence
    if evidence is None:
        _raise(command, "amended filing target lacks persisted AEAT evidence")
    justificantes = tuple(repository.iter_justificantes())
    matches = tuple(item for item in justificantes if item.csv == evidence.reference_id)
    if len(matches) != 1:
        _raise(command, "amended filing target does not resolve to one persisted justificante")
    receipt = matches[0]
    if (
        not receipt.matches_filing_target(
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            tax_id=workflow_profile.tax_id,
        )
        or receipt.presentation_id is None
    ):
        _raise(command, "persisted justificante disagrees with the export authority")
    return justificantes, receipt


def _evidence(
    command: AmendmentExportCommand,
    *,
    revision: CalculationRevision,
    identity: CalculationRevisionAmendmentIdentity,
    work_unit: WorkUnit,
    workflow_profile: TaxpayerProfile,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    records: ModeloRecordCatalogue,
    justificantes: tuple[Justificante, ...],
    receipt: Justificante,
) -> tuple[M303RectificativaMotive | None, str]:
    receipt_number = receipt.presentation_id
    if receipt_number is None:
        _raise(command, "persisted justificante has no AEAT presentation receipt")
    if identity.kind is not CalculationRevisionAmendmentKind.RECTIFICATIVA or work_unit.modelo != Modelo.M303.value:
        return identity.m303_rectificativa_motive, receipt_number
    validated = validate_calculation_revision_aggregate(
        revision,
        context=CalculationRevisionAggregateContext(
            work_units=work_unit_repository.load(),
            filing_records=records,
            justificantes=justificantes,
            registry_snapshots={
                work_unit.work_unit_id: bundled_authority().snapshot(
                    Modelo.M303.value,
                    filing_year=work_unit.filing_year,
                    period=work_unit.period.registry_token,
                )
            },
            expected_taxpayer_tax_id=workflow_profile.tax_id,
        ),
    )
    if validated is None:
        _raise(command, "M303 rectificativa aggregate did not resolve persisted evidence")
    return validated.motive, validated.original_aeat_receipt


__all__ = ["resolve_persisted_amendment_export_evidence"]
