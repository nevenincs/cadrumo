"""Read one declaration's editor workbench inside the profile worker.

These are the reads behind the workbench's registered operations: the form with
its lazily admitted edit baseline and the facts every action is judged against,
one casilla's help, and the source boxes a refused Apply's prerequisite names.
They run under the worker's pinned authority against the profile's repositories;
the frontend receives only their typed results.

Opening a declaration's workbench is the start of its edit session, so the form
read admits the edit baseline that every parse and apply is judged against. An
admission refusal is part of the result, never hidden as "no edit surface".
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.identity.documents import SpanishTaxIdFormat
from ...domain.calculations.registry.bindings_previous_filing import PreviousFilingProvider
from ...domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ...domain.modelos.work_unit import WorkUnit
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .casilla_help import ModeloCasillaHelpCardV1, build_casilla_help_card
from .edit_admission import admit_modelo_edit_baseline
from .edit_models import ModeloEditAdmissionResultV1
from .edit_refusal_projection import ModeloEditCalculationPrerequisiteV1
from .m303_exonerado_390_applicability_attestation import modelo_390_question_asked
from .verification_report_facts import granting_verification_report
from .work_form_service import ModeloWorkFormLoadV1, load_modelo_work_form, modelo_form_snapshot

if TYPE_CHECKING:
    from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.deadlines.festivos import CalendarCCAA
    from ...domain.modelos.protocols import (
        CalculationRevisionCatalogueRepositoryProtocol,
        VerificationReportCatalogueRepositoryProtocol,
    )
    from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
    from ..live.borrador_100 import Borrador100SnapshotRepository
    from ..operations.registry import OperationPublicContractSetV1

_M303: Final[str] = "303"


@dataclass(frozen=True, slots=True)
class ModeloWorkbenchReadPorts:
    """The profile repositories one declaration's workbench is read from.

    ``borrador_snapshots`` is the profile's AEAT draft store, read to say when
    replayed AEAT data was imported; ``holiday_territory`` reads the profile's
    holiday territory afresh on each read, so a deadline shifts for the filer's
    own regional holidays and not the national ones only; ``bucket_events`` is
    the profile's event history, read to say when the latest file for the AEAT
    was created and whether it still matches.
    """

    work_units: WorkUnitCatalogueRepositoryProtocol
    calculations: CalculationRevisionCatalogueRepositoryProtocol
    verifications: VerificationReportCatalogueRepositoryProtocol
    borrador_snapshots: Borrador100SnapshotRepository | None = None
    holiday_territory: Callable[[], CalendarCCAA | None] | None = None
    bucket_events: BucketEventHistoryRepositoryProtocol | None = None


type ModeloWorkbenchReadPortsFactory = Callable[[str, PinnedAuthorityOperation], ModeloWorkbenchReadPorts]
"""Bind the workbench repositories to one profile under the worker's pinned authority."""


@dataclass(frozen=True, slots=True)
class ModeloWorkbenchFormReadV1:
    """One declaration's form and what every workbench action is judged against.

    ``admission`` is the edit baseline admitted with this read, or the typed
    refusal saying why the declaration cannot be edited. The calculation head
    and the verification report granting it are the ones the form shows, so
    Verify and File act on the revision the filer is looking at.
    """

    load: ModeloWorkFormLoadV1
    admission: ModeloEditAdmissionResultV1
    calculation_revision_id: str | None
    verification_report_id: str | None
    #: Whether the next calculation must first ask the ordinary Modelo 303 filing answers.
    asks_m303_evidence: bool
    #: Whether this Modelo 303 period asks the Modelo 390 exemption.
    asks_modelo_390: bool
    registry_revision_id: str
    #: The governed Spanish tax-identifier format the frontend parses NIF entries against.
    tax_id_format: SpanishTaxIdFormat


def _work_unit(work_unit_id: str, *, bucket_id: str, ports: ModeloWorkbenchReadPorts) -> WorkUnit:
    unit = ports.work_units.load().get(work_unit_id)
    if unit is None or unit.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return unit


def read_modelo_workbench_form(
    work_unit_id: str,
    *,
    bucket_id: str,
    ports: ModeloWorkbenchReadPorts,
    operation: PinnedAuthorityOperation,
    operation_contracts: OperationPublicContractSetV1,
    language: OutputLanguage,
) -> ModeloWorkbenchFormReadV1:
    """Admit an edit baseline, read the declaration's form and the facts its actions need."""
    unit = _work_unit(work_unit_id, bucket_id=bucket_id, ports=ports)
    work_catalogue = ports.work_units.load()
    calculation_catalogue = ports.calculations.load(operation=operation)
    admission = admit_modelo_edit_baseline(
        work_unit_id=work_unit_id,
        work_catalogue=work_catalogue,
        calculation_catalogue=calculation_catalogue,
        operation=operation,
        operation_contracts=operation_contracts,
    )
    territory = ports.holiday_territory
    loaded = load_modelo_work_form(
        bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=operation,
        work_unit_repository=ports.work_units,
        calculation_repository=ports.calculations,
        verification_repository=ports.verifications,
        calculation_catalogue=calculation_catalogue,
        admission=admission,
        language=language,
        borrador_snapshots=ports.borrador_snapshots,
        holiday_territory=None if territory is None else territory(),
        bucket_events=ports.bucket_events,
    )
    form = loaded.form
    head_id = form.calculation_revision_id
    head = None if head_id is None else ports.calculations.load(operation=operation).get(head_id)
    report = (
        None
        if head_id is None
        else granting_verification_report(ports.verifications.load(operation=operation), head_id)
    )
    is_m303 = str(unit.modelo) == _M303
    return ModeloWorkbenchFormReadV1(
        load=loaded,
        admission=admission,
        calculation_revision_id=head_id,
        verification_report_id=None if report is None else str(report.verification_report_id),
        asks_m303_evidence=is_m303 and (head is None or head.filing_instance_evidence is None),
        asks_modelo_390=is_m303 and modelo_390_question_asked(unit.period, operation=operation),
        registry_revision_id=str(form.registry_revision_id),
        tax_id_format=runtime_tax_id_format(authority=operation),
    )


def read_modelo_casilla_help(
    work_unit_id: str,
    casilla_id: CasillaId,
    *,
    bucket_id: str,
    registry_revision_id: str,
    calculation_revision_id: str | None,
    ports: ModeloWorkbenchReadPorts,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> ModeloCasillaHelpCardV1:
    """Assemble one casilla's help from the revision and the calculation the form showed."""
    unit = _work_unit(work_unit_id, bucket_id=bucket_id, ports=ports)
    snapshot = modelo_form_snapshot(operation, unit.modelo, unit.filing_year, unit.period, registry_revision_id)
    head = (
        None
        if calculation_revision_id is None
        else ports.calculations.load(operation=operation).get(calculation_revision_id)
    )
    if head is not None and head.work_unit_id != unit.work_unit_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    observation = (
        None if head is None else next((item for item in head.observations if item.casilla_id == casilla_id), None)
    )
    return build_casilla_help_card(
        casilla_id,
        snapshot=snapshot,
        operation=operation,
        language=language,
        on=unit.period.end_date,
        observation=observation,
    )


def modelo_edit_prerequisite_source_boxes(
    prerequisite: ModeloEditCalculationPrerequisiteV1,
    *,
    bucket_id: str,
    registry_revision_id: str,
    ports: ModeloWorkbenchReadPorts,
    operation: PinnedAuthorityOperation,
) -> tuple[CasillaId, ...]:
    """Name the earlier-filing boxes the prerequisite's bindings read, in declaration order."""
    unit = _work_unit(prerequisite.work_unit_id, bucket_id=bucket_id, ports=ports)
    snapshot = modelo_form_snapshot(operation, unit.modelo, unit.filing_year, unit.period, registry_revision_id)
    providers = (binding.provider for binding in snapshot.revision.bindings if binding.id in prerequisite.binding_ids)
    return tuple(
        dict.fromkeys(
            box
            for provider in providers
            if isinstance(provider, PreviousFilingProvider)
            for box in (
                *provider.source_casilla_ids,
                *((provider.source_casilla_id,) if provider.source_casilla_id else ()),
            )
        )
    )


__all__ = [
    "ModeloWorkbenchFormReadV1",
    "ModeloWorkbenchReadPorts",
    "ModeloWorkbenchReadPortsFactory",
    "modelo_edit_prerequisite_source_boxes",
    "read_modelo_casilla_help",
    "read_modelo_workbench_form",
]
