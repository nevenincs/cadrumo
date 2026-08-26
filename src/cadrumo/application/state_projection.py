"""The single canonical operator-facing state read-projection.

Every operator-facing state or readiness surface that reports "the
truth" about the active profile - ``overview status``, ``auth status``,
``auth test``, and ``modelo readiness`` - consumes this one projection.
None of them re-derives state from a private subset of the stores.

The :class:`OperatorStateProjection` is a typed, frozen pydantic model
built by exactly one producer, :func:`build_operator_state_projection`.
The producer loads the profile aggregate, the workspace catalogues
(transactions via :class:`TransactionCatalogueRepository`, invoices via
:class:`InvoiceCatalogueRepository`, declaration drafts via
:class:`~cadrumo.adapters.persistence.profile.filing_drafts.ModeloDraftRepository`,
modelo work units via
:class:`~adapters.persistence.profile.modelos_work_units.WorkUnitCatalogueRepository`, and calculation
revisions via
:class:`~adapters.persistence.profile.modelos_calculation.CalculationRevisionCatalogueRepository`), the
auth state, the active-profile health, and the deadline obligations computed
from :class:`Schedule`, and computes each readiness value exactly once.
Modelo readiness resolves a :class:`RegistrySnapshot` only to evaluate
registry-declared profile, binding, and ledger preflight requirements for the
requested :class:`ModeloReadinessRequest`.

The projection is pure read: building it mutates no store.

Background: ``overview status`` once reconstructed workspace
counters from a different store subset than ``modelo work`` writes:
it read the :class:`~cadrumo.domain.filing.ModeloDraft` store but never the
:class:`~cadrumo.domain.modelos.WorkUnitCatalogue` or
:class:`~cadrumo.domain.modelos.CalculationRevisionCatalogue` stores, so an
operator who used
``modelo work create`` / ``calculate`` saw ``drafts: 0``. This
projection carries ``drafts`` (the declaration-draft
:class:`~cadrumo.domain.filing.ModeloDraft` store) and ``work_units`` (the
:class:`~cadrumo.domain.modelos.WorkUnitCatalogue` store) as distinct counters, so
neither is silently zero.

See Also:
    :class:`~cadrumo.application.overview.OverviewStatusReport`
        Overview emit shape derived from this projection, rather than from a
        second store assembly path.
    :func:`~cadrumo.application.overview.build_overview_status_report`
        Overview producer that consumes this projection instead of rebuilding
        workspace, auth, and deadline readiness.
    :class:`~cadrumo.application.auth.AuthStatusResult`
        Auth emit shape that reads the same canonical configured/authenticated
        readiness values carried here.
    :func:`~cadrumo.application.auth.inspect_operator_auth`
        Auth status producer that reads
        :class:`ProjectionAuthReadiness` and
        :class:`ProjectionActiveProfile` from this projection.
    :func:`~cadrumo.adapters.persistence.storage.inspect_bucket_storage_runtime`
        Storage-runtime inspection used by the workspace summary without
        letting presentation surfaces open their own storage-reading paths.
    :class:`ProjectionWorkspaceSummary`
        Per-store counter record that keeps declaration drafts, work units, and
        calculation revisions distinct.
    :class:`ProjectionModeloReadiness`
        Per-target readiness record built from profile facts, registry
        snapshots, binding availability, and ledger preflight.
    :func:`~cadrumo.application.workflow._deadline_stage.resolve_deadline_stage_obligation`
        Filing workflow selector that filters a schedule for the workflow gate;
        it does not consume ``pending_obligations`` directly.
    :func:`~cadrumo.domain.deadlines.compute_obligation_schedule`
        Single deadline schedule producer used for projection obligations and
        workflow deadline-stage checks.
    :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot`
        Registry authority snapshot used to resolve modelo-readiness preflight
        requirements.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from secrets import token_bytes
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

from cadrumo.application.workflow.profile_health import ActiveProfileHealth, assess_active_profile_health
from cadrumo.application.workflow.state_models import WorkflowState
from cadrumo.core.aggregation import LEDGER_BINDING_SOURCE_KINDS as _LEDGER_PREFLIGHT_BINDING_SOURCES
from cadrumo.domain.calculations.registry.ids import RevisionId

from ..adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ..adapters.persistence.storage import inspect_bucket_storage_runtime
from ..core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..core import AuthProviderKind, BindingSourceKind, OperatorActionAxis, Period
from ..core.bucket_pointer import resolve_active_bucket_id
from ..core.errors import CadrumoError
from ..core.hashing import content_hash_hex
from ..core.identity import ProfileId
from ..core.logging import get_logger
from ..core.time import today_madrid
from ..domain.calculations.registry.authority import bundled_authority
from ..domain.deadlines import (
    DeadlineEngine,
    ObligationStatus,
    Schedule,
    TaxpayerProfile,
    compute_obligation_schedule,
)
from ..domain.modelos import WorkUnitState
from ._state_projection_auth import ProjectionAuthReadiness, build_auth_readiness
from ._state_projection_readiness import (
    one_line_error_message,
    readiness_binding_input_channel,
)
from .auth.credentials import ActiveAuthProjectionSnapshot, active_auth_projection_span
from .auth_credentials import ActiveCertificateCredentials
from .ledger.preflight import LedgerPreflightIssue, LedgerPreflightIssueReason, preflight_ledger_tax_readiness
from .operator_actions import PreconditionVerdict
from .user_profile.commands import ProfilePreflightRequirement

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

_log = get_logger(__name__)


class ProjectionActiveProfile(BaseModel):
    """Active-profile identity and health, computed once for every surface.

    This record is the projection-side form of
    :class:`~cadrumo.application.workflow.ActiveProfileHealth`. Auth and overview
    surfaces read these fields instead of re-running profile pointer or bucket
    manifest checks.

    Attributes:
        profile_id: Immutable bucket UUID of the active profile, or
            ``None`` when no profile is active.
        label: Operator-chosen display name of the active profile, or
            ``None`` when no profile is active or the label cannot be
            resolved.
        health_status: The :class:`ActiveProfileHealth` status string
            (``none`` / ``dangling_pointer`` / ``incomplete`` /
            ``ready`` / ...).
        registered_bucket: Whether the active-profile pointer resolves
            to a registered bucket.
        record_present: Whether the encrypted profile record loaded.
        precondition_verdict: The application-owned recovery verdict carried
            from :func:`~cadrumo.application.workflow.assess_active_profile_health`.
    """

    model_config = _STRICT_FROZEN

    profile_id: ProfileId | None = None
    label: str | None = None
    health_status: str = ""
    registered_bucket: bool = False
    record_present: bool = False
    precondition_verdict: PreconditionVerdict | None = None


class ProjectionWorkspaceSummary(BaseModel):
    """Counters for every workspace store, so none is silently zero.

    ``drafts`` and ``work_units`` are deliberately distinct counters:
    ``modelo file`` writes the declaration-draft
    :class:`~cadrumo.domain.filing.ModeloDraft` store while
    ``modelo work create`` / ``calculate`` write the
    :class:`~cadrumo.domain.modelos.WorkUnitCatalogue` store. Calculation output is
    counted separately through
    :class:`~cadrumo.domain.modelos.CalculationRevisionCatalogue`. A single
    ``drafts`` counter that read only the first store reported ``0`` for an
    operator who used the ``modelo work`` flow.

    Attributes:
        transactions: Count of imported transactions.
        invoices: Count of imported invoices.
        drafts: Count of declaration-draft :class:`~cadrumo.domain.filing.ModeloDraft`
            entries.
        work_units: Count of *active* (``BORRADOR``)
            :class:`~cadrumo.domain.modelos.WorkUnitCatalogue` entries written by
            ``modelo work create``. Discarded units are excluded so the counter
            is never inflated by units the operator has abandoned.
        discarded_work_units: Count of ``DESCARTADO``
            :class:`~cadrumo.domain.modelos.WorkUnitCatalogue` entries, carried
            distinctly so a surface can state the active / discarded split
            rather than a misleading total.
        calculation_revisions: Count of
            :class:`~cadrumo.domain.modelos.CalculationRevisionCatalogue`
            entries written by ``modelo work calculate``.
        unreadable_rows: Count of secure-object rows that failed to
            decrypt — an integrity warning.
    """

    model_config = _STRICT_FROZEN

    transactions: int = Field(default=0, ge=0)
    invoices: int = Field(default=0, ge=0)
    drafts: int = Field(default=0, ge=0)
    work_units: int = Field(default=0, ge=0)
    discarded_work_units: int = Field(default=0, ge=0)
    calculation_revisions: int = Field(default=0, ge=0)
    unreadable_rows: int = Field(default=0, ge=0)


class ProjectionObligation(BaseModel):
    """One pending filing obligation carried in the projection.

    Rows are copied from the :class:`~cadrumo.domain.deadlines.Schedule`
    obligations produced for the active :class:`TaxpayerProfile`. Workflow
    filing gates later select a narrower
    :class:`~cadrumo.domain.deadlines.ModeloDeadline` from the same schedule
    producer.

    Attributes:
        modelo: Modelo identifier.
        period: Typed :class:`~cadrumo.core.Period` for the obligation window.
        opens_on: First day the filing window accepts submissions.
        closes_on: Last day the filing window accepts submissions.
        status: The engine :class:`ObligationStatus`.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    period: Period
    opens_on: date
    closes_on: date
    status: ObligationStatus


class OperatorStateProjection(BaseModel):
    """The single canonical operator-facing state view.

    Built by exactly one producer,
    :func:`build_operator_state_projection`, and consumed by every
    operator-facing surface. Each readiness value it carries is
    computed once; surfaces present these values, they never recompute.

    Attributes:
        active_profile: Active-profile identity + health.
        auth: Auth operational readiness (carries the one canonical
            ``configured`` definition).
        workspace: Per-store workspace counters.
        modelo_readiness: Per-modelo preflight readiness reports, keyed
            by the ``(modelo, revision, year, period)`` request the
            caller asked for. Empty when no modelo target was supplied.
        pending_obligations: The full, unfiltered deadline obligations
            for the active profile's current year, as
            :class:`ProjectionObligation` records. They are computed through
            :func:`~cadrumo.domain.deadlines.compute_obligation_schedule`, the
            same schedule producer that the workflow deadline stage filters
            through
            :func:`~cadrumo.application.workflow._deadline_stage.resolve_deadline_stage_obligation`.
            The workflow does not consume this tuple directly; the shared
            invariant is producer-level schedule agreement.
    """

    model_config = _STRICT_FROZEN

    active_profile: ProjectionActiveProfile
    auth: ProjectionAuthReadiness
    workspace: ProjectionWorkspaceSummary
    modelo_readiness: tuple[ProjectionModeloReadiness, ...] = ()
    pending_obligations: tuple[ProjectionObligation, ...] = ()


def _build_active_profile(health: ActiveProfileHealth) -> ProjectionActiveProfile:
    """Project one coherent profile-health snapshot into the public record."""
    return ProjectionActiveProfile(
        profile_id=health.active_profile,
        label=health.active_profile_label,
        health_status=health.status,
        registered_bucket=health.registered_bucket,
        record_present=health.profile_record_present,
        precondition_verdict=health.precondition_verdict,
    )


def _build_workspace_summary(*, bucket_id: str | None) -> ProjectionWorkspaceSummary:
    """Load every workspace store and project its counters.

    With no active profile bucket there is no bucket database to open,
    so the counters are all zero without touching the encrypted stores.
    """
    if bucket_id is None:
        return ProjectionWorkspaceSummary()

    inspect_bucket_storage_runtime(bucket_id).require_ready()

    from .diagnostics import secure_object_unreadable_total

    transactions = TransactionCatalogueRepository(bucket_id=bucket_id).load()
    invoices = InvoiceCatalogueRepository().load()
    drafts = tuple(ModeloDraftRepository().iter_drafts())
    work_units = WorkUnitCatalogueRepository().load()
    revisions = CalculationRevisionCatalogueRepository().load()
    active_work_units = sum(1 for unit in work_units.values() if unit.state is WorkUnitState.BORRADOR)
    discarded_work_units = sum(1 for unit in work_units.values() if unit.state is WorkUnitState.DESCARTADO)
    return ProjectionWorkspaceSummary(
        transactions=len(transactions.transactions),
        invoices=len(invoices),
        drafts=len(drafts),
        work_units=active_work_units,
        discarded_work_units=discarded_work_units,
        calculation_revisions=len(revisions),
        unreadable_rows=secure_object_unreadable_total(),
    )


def _taxpayer_profile_from_state(state: WorkflowState) -> TaxpayerProfile:
    """Project the active profile record into an :class:`TaxpayerProfile`.

    Delegates to :func:`~cadrumo.application.user_profile.projection_for_taxpayer`,
    the single fact-to-taxpayer projection authority, so the deadline engine
    receives exactly the profile shape every other surface computes.
    """
    from .user_profile.projections import projection_for_taxpayer

    record = state.active_profile_record()
    return projection_for_taxpayer(record if record is not None else {})


def build_pending_obligations(
    profile: TaxpayerProfile,
    *,
    today: date,
) -> tuple[ProjectionObligation, ...]:
    """Compute the deadline obligations for the active profile.

    Routes through :func:`~cadrumo.domain.deadlines.compute_obligation_schedule`,
    the single producer of the pending-obligation datum also used by the
    workflow deadline stage. This function projects the full
    :class:`~cadrumo.domain.deadlines.Schedule`; the workflow gate separately
    filters its target :class:`~cadrumo.domain.deadlines.ModeloDeadline` through
    :func:`~cadrumo.application.workflow._deadline_stage.resolve_deadline_stage_obligation`.
    A failure to compute the schedule is logged and degrades to an empty tuple
    rather than failing the whole projection.

    Args:
        profile: The :class:`TaxpayerProfile` whose deadline obligations are
            projected.
        today: Reference date for fiscal-year selection and obligation status.

    Returns:
        The projected :class:`ProjectionObligation` records.
    """
    try:
        schedule: Schedule = compute_obligation_schedule(DeadlineEngine(), profile, today=today)
    except (CadrumoError, ValueError, LookupError, AttributeError):
        _log.warning(
            "deadline schedule computation failed; reporting no pending obligations",
            exc_info=True,
        )
        return ()
    obligations: list[ProjectionObligation] = []
    for obligation in schedule.obligations:
        obligations.append(
            ProjectionObligation(
                modelo=obligation.modelo,
                period=obligation.period,
                opens_on=obligation.opens_on,
                closes_on=obligation.closes_on,
                status=obligation.status,
            ),
        )
    return tuple(obligations)


class ModeloReadinessRequest(BaseModel):
    """One ``(modelo, revision, year, period)`` readiness target.

    The projection producer accepts a tuple of these and computes one
    :class:`ProjectionModeloReadiness` per request, so ``modelo readiness``
    never builds its own profile, registry, binding, or ledger preflight
    pass.

    Attributes:
        period: Typed :class:`~cadrumo.core.Period` scoping the readiness
            check, or ``None`` when the caller omits the period (the
            projection uses the annual ``0A`` period for registry and
            ledger preflight resolution).
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    revision_id: RevisionId = Field(min_length=1, max_length=64)
    filing_year: int = Field(ge=2000, le=2100)
    period: Period | None = None


class ProjectionModeloBindingRequirement(BaseModel):
    """One registry calculation binding readiness cannot currently satisfy.

    These are non-constant binding declarations from the resolved
    :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot` that are not
    supplied by profile binding resolution, enum/date helpers, or a successful
    ledger preflight. The parent :class:`ProjectionModeloReadiness` carries
    these rows as operator-facing missing input requirements.
    """

    model_config = _STRICT_FROZEN

    binding_id: str = Field(min_length=1, max_length=128)
    source: BindingSourceKind
    input_channel: str = Field(min_length=1, max_length=16)

    @field_validator("source", mode="before")
    @classmethod
    def _hydrate_source(cls, value: object) -> object:
        """Hydrate the persisted source token without admitting unknown strings."""
        if isinstance(value, str) and not isinstance(value, BindingSourceKind):
            return BindingSourceKind(value)
        return value


MODELO_READINESS_MISSING_PROFILE_ACTION = OperatorActionAxis.SET_PROFILE_FACT
"""Action spine for every profile requirement in readiness ``missing``."""


CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS: Mapping[
    BindingSourceKind,
    str,
] = MappingProxyType(
    {
        BindingSourceKind.PROFILE: "cli.app.modelo.bindings.readiness.dato_perfil",
        BindingSourceKind.PREVIOUS_FILING: "cli.app.modelo.bindings.readiness.declaracion_previa",
        BindingSourceKind.RELATION_PREFILL: "cli.app.modelo.bindings.readiness.entrada_relacion",
        BindingSourceKind.MANUAL_INPUT: "cli.app.modelo.bindings.readiness.entrada_manual",
        BindingSourceKind.LEDGER_OSS_AGGREGATION: "cli.app.modelo.bindings.readiness.datos_libro",
        BindingSourceKind.LEDGER_IVA_AGGREGATION: "cli.app.modelo.bindings.readiness.datos_libro",
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION: (
            "cli.app.modelo.bindings.readiness.datos_libro"
        ),
        BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION: "cli.app.modelo.bindings.readiness.datos_libro",
        BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION: (
            "cli.app.modelo.bindings.readiness.datos_libro"
        ),
        BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION: "cli.app.modelo.bindings.readiness.datos_libro",
        BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION: "cli.app.modelo.bindings.readiness.datos_libro",
        BindingSourceKind.RETENCIONES_AGGREGATION: "cli.app.modelo.bindings.readiness.registro_retenciones",
        BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION: (
            "cli.app.modelo.bindings.readiness.compensacion_iva_anual"
        ),
        BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY: (
            "cli.app.modelo.bindings.readiness.declaracion_previa"
        ),
        BindingSourceKind.BIENES_INVERSION_REGULARIZACION: (
            "cli.app.modelo.bindings.readiness.regularizacion_bienes_inversion"
        ),
        BindingSourceKind.INVENTORY: "cli.app.modelo.bindings.readiness.inventario",
        BindingSourceKind.PRORRATA_REGULARIZACION: "cli.app.modelo.bindings.readiness.regularizacion_prorrata",
        BindingSourceKind.BORRADOR: "cli.app.modelo.bindings.readiness.borrador_aeat",
        BindingSourceKind.IVA_WALLET_DECISION: "cli.app.modelo.bindings.readiness.decision_compensacion_iva",
        BindingSourceKind.PAYABLE_INVOICE: "cli.app.modelo.bindings.readiness.factura_recibida",
        BindingSourceKind.COLLECTIBLE_INVOICE: "cli.app.modelo.bindings.readiness.factura_emitida",
        BindingSourceKind.LEDGER_TRANSACTION: "cli.app.modelo.bindings.readiness.datos_libro",
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE: "cli.app.modelo.bindings.readiness.evidencia_factura_compra",
        BindingSourceKind.WITHHOLDING: "cli.app.modelo.bindings.readiness.retencion",
        BindingSourceKind.FOREIGN_ASSET: "cli.app.modelo.bindings.readiness.activo_extranjero",
        BindingSourceKind.RELATED_PARTY_OPERATION: "cli.app.modelo.bindings.readiness.operacion_vinculada",
        BindingSourceKind.ATRIBUCION_MEMBER: "cli.app.modelo.bindings.readiness.miembro_atribucion",
        BindingSourceKind.REFUND_OPERATION: "cli.app.modelo.bindings.readiness.operacion_reembolso",
        BindingSourceKind.DONATIVO_DONOR: "cli.app.modelo.bindings.readiness.donante_donativo",
        BindingSourceKind.GASTO193_CONTRIBUTOR: "cli.app.modelo.bindings.readiness.gasto193_contribuyente",
        BindingSourceKind.WITHHOLDING296: "cli.app.modelo.bindings.readiness.withholding296_perceptor",
    },
)
"""Total locale-key projection for the noun describing each binding source."""


OPERATOR_ACTION_BY_MODELO_READINESS_BINDING_SOURCE: Mapping[
    BindingSourceKind,
    OperatorActionAxis,
] = MappingProxyType(
    {
        BindingSourceKind.PROFILE: OperatorActionAxis.SET_PROFILE_FACT,
        BindingSourceKind.PREVIOUS_FILING: OperatorActionAxis.FILE_PRIOR_PERIOD,
        BindingSourceKind.RELATION_PREFILL: OperatorActionAxis.FILE_PRIOR_PERIOD,
        BindingSourceKind.MANUAL_INPUT: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
        BindingSourceKind.LEDGER_OSS_AGGREGATION: OperatorActionAxis.IMPORT_LEDGER_DATA,
        BindingSourceKind.LEDGER_IVA_AGGREGATION: OperatorActionAxis.IMPORT_LEDGER_DATA,
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION: (OperatorActionAxis.IMPORT_LEDGER_DATA),
        BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION: OperatorActionAxis.IMPORT_LEDGER_DATA,
        BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION: (OperatorActionAxis.IMPORT_LEDGER_DATA),
        BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION: OperatorActionAxis.IMPORT_LEDGER_DATA,
        BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION: OperatorActionAxis.IMPORT_LEDGER_DATA,
        BindingSourceKind.RETENCIONES_AGGREGATION: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
        BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION: OperatorActionAxis.CAPTURE_EXTERNAL_EVIDENCE,
        BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY: OperatorActionAxis.FILE_PRIOR_PERIOD,
        BindingSourceKind.BIENES_INVERSION_REGULARIZACION: OperatorActionAxis.COMPLETE_DOCUMENT_EVIDENCE,
        BindingSourceKind.INVENTORY: OperatorActionAxis.COMPLETE_DOCUMENT_EVIDENCE,
        BindingSourceKind.PRORRATA_REGULARIZACION: OperatorActionAxis.COMPLETE_DOCUMENT_EVIDENCE,
        BindingSourceKind.BORRADOR: OperatorActionAxis.CAPTURE_EXTERNAL_EVIDENCE,
        BindingSourceKind.IVA_WALLET_DECISION: OperatorActionAxis.CAPTURE_EXTERNAL_EVIDENCE,
        BindingSourceKind.PAYABLE_INVOICE: OperatorActionAxis.IMPORT_LEDGER_DATA,
        BindingSourceKind.COLLECTIBLE_INVOICE: OperatorActionAxis.IMPORT_LEDGER_DATA,
        BindingSourceKind.LEDGER_TRANSACTION: OperatorActionAxis.IMPORT_LEDGER_DATA,
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE: OperatorActionAxis.COMPLETE_DOCUMENT_EVIDENCE,
        BindingSourceKind.WITHHOLDING: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
        BindingSourceKind.FOREIGN_ASSET: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
        BindingSourceKind.RELATED_PARTY_OPERATION: OperatorActionAxis.CAPTURE_EXTERNAL_EVIDENCE,
        BindingSourceKind.ATRIBUCION_MEMBER: OperatorActionAxis.SET_PROFILE_FACT,
        BindingSourceKind.REFUND_OPERATION: OperatorActionAxis.CAPTURE_EXTERNAL_EVIDENCE,
        BindingSourceKind.DONATIVO_DONOR: OperatorActionAxis.COMPLETE_DOCUMENT_EVIDENCE,
        BindingSourceKind.GASTO193_CONTRIBUTOR: OperatorActionAxis.COMPLETE_DOCUMENT_EVIDENCE,
        BindingSourceKind.WITHHOLDING296: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
    },
)
"""Total action spine for a readiness ``missing_bindings`` source."""


OPERATOR_ACTION_BY_MODELO_READINESS_LEDGER_ISSUE: Mapping[
    LedgerPreflightIssueReason,
    OperatorActionAxis,
] = MappingProxyType(
    {
        LedgerPreflightIssueReason.MISSING_BUSINESS_CLASSIFICATION: OperatorActionAxis.IMPORT_LEDGER_DATA,
        LedgerPreflightIssueReason.MISSING_CATEGORY: OperatorActionAxis.IMPORT_LEDGER_DATA,
        LedgerPreflightIssueReason.MISSING_TAXABLE_BASE: OperatorActionAxis.IMPORT_LEDGER_DATA,
        LedgerPreflightIssueReason.MISSING_IVA_AMOUNT: OperatorActionAxis.IMPORT_LEDGER_DATA,
        LedgerPreflightIssueReason.MISSING_IVA_RATE: OperatorActionAxis.IMPORT_LEDGER_DATA,
        LedgerPreflightIssueReason.MISSING_EUR_TAX_SUBSTRATE: OperatorActionAxis.IMPORT_LEDGER_DATA,
        LedgerPreflightIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE: OperatorActionAxis.RESOLVE_IDENTITY,
        LedgerPreflightIssueReason.DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION: (
            OperatorActionAxis.RESOLVE_IDENTITY
        ),
        LedgerPreflightIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION: OperatorActionAxis.RESOLVE_IDENTITY,
        LedgerPreflightIssueReason.MISSING_COUNTERPARTY_ESTABLISHMENT_ON_EXPORT: (OperatorActionAxis.RESOLVE_IDENTITY),
        LedgerPreflightIssueReason.MISSING_PROPORTIONALITY_REFERENCE: (OperatorActionAxis.COMPLETE_DOCUMENT_EVIDENCE),
        LedgerPreflightIssueReason.UNSUPPORTED_CURRENCY: OperatorActionAxis.IMPORT_LEDGER_DATA,
        LedgerPreflightIssueReason.UNSUPPORTED_PERIOD: OperatorActionAxis.IMPORT_LEDGER_DATA,
        LedgerPreflightIssueReason.CENSO_RATIO_MISMATCH: OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE,
        LedgerPreflightIssueReason.ANOMALY_NON_DECLARABLE_IVA_CATEGORY: OperatorActionAxis.REVIEW_ADVISORY,
        LedgerPreflightIssueReason.ANOMALY_NON_DECLARABLE_RECARGO_EQUIVALENCIA: (OperatorActionAxis.REVIEW_ADVISORY),
    },
)
"""Total action spine for readiness ``ledger_issues`` reasons."""


def _assert_total_action_projection[ActionSourceT: StrEnum](
    source_name: str,
    members: tuple[ActionSourceT, ...],
    projection: Mapping[ActionSourceT, OperatorActionAxis],
) -> None:
    member_set = set(members)
    projection_set = set(projection)
    if member_set != projection_set:
        missing = sorted(member.value for member in member_set - projection_set)
        unexpected = sorted(str(member) for member in projection_set - member_set)
        raise RuntimeError(
            f"every {source_name} must declare exactly one OperatorActionAxis; "
            f"missing={missing}; unexpected={unexpected}",
        )


_assert_total_action_projection(
    BindingSourceKind.__name__,
    tuple(BindingSourceKind),
    OPERATOR_ACTION_BY_MODELO_READINESS_BINDING_SOURCE,
)


def _assert_total_binding_source_readiness_projection() -> None:
    member_set = set(BindingSourceKind)
    projection_set = set(CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS)
    if member_set != projection_set:
        missing = sorted(member.value for member in member_set - projection_set)
        unexpected = sorted(str(member) for member in projection_set - member_set)
        raise RuntimeError(
            "every BindingSourceKind must declare exactly one binding-readiness locale key; "
            f"missing={missing}; unexpected={unexpected}",
        )


_assert_total_binding_source_readiness_projection()
_assert_total_action_projection(
    LedgerPreflightIssueReason.__name__,
    tuple(LedgerPreflightIssueReason),
    OPERATOR_ACTION_BY_MODELO_READINESS_LEDGER_ISSUE,
)


class ProjectionModeloReadiness(BaseModel):
    """Readiness for one modelo target across all preflight axes.

    The projection combines profile requirements, registry-snapshot
    availability, calculation binding resolution, and ledger preflight
    into one emit shape. ``ready`` is true only when every axis is ready; a
    :class:`~cadrumo.application.ledger.preflight.LedgerPreflightIssue` blocks readiness
    only when the resolved :class:`RegistrySnapshot` declares ledger-backed
    bindings.

    Attributes:
        profile_id: Active :data:`~cadrumo.core.identity.ProfileId` used for the
            readiness report.
        modelo: Modelo identifier from the :class:`ModeloReadinessRequest`.
        revision_id: Registry revision requested or resolved for this target.
        filing_year: Filing year used to resolve registry and profile
            requirements.
        missing: Profile fields still required by the
            :class:`~cadrumo.application.user_profile.ProfilePreflightReport`.
        profile_refusal: Operator-facing refusal when profile facts are
            present but disqualify the target period.
        registry_ready: Whether the requested modelo/year/period/revision
            resolved to a usable registry snapshot.
        registry_refusal: Operator-facing explanation when registry
            resolution failed.
        binding_ready: Whether every non-constant registry binding can be
            supplied by the current profile or ledger state.
        missing_bindings: Missing :class:`ProjectionModeloBindingRequirement`
            records for unresolved calculation inputs.
        period: Typed :class:`~cadrumo.core.Period` the readiness check was
            scoped to.
        ledger_preflight_required: Whether the registry declares any
            ledger aggregation binding requiring ledger preflight.
        ledger_ready: Ledger-preflight verdict, or ``None`` when no
            ledger preflight was required.
        ledger_period: The :class:`~cadrumo.core.Period` the ledger preflight
            was scoped to, or ``None`` when no ledger preflight was run.
        ledger_issues: Blocking :class:`LedgerPreflightIssue` rows.
        per_operation_requirements_assessed: Whether the per-modelo
            schema-required axis (see
            :attr:`~cadrumo.application.user_profile.ProfilePreflightReport.per_operation_requirements_assessed`)
            actually examined any field for this modelo. ``False`` means no
            schema-required field was checked and ``profile_ready`` reflects
            only the export-identity and conditional checks; it MUST NOT be
            rendered as a clean bill of health.
    """

    model_config = _STRICT_FROZEN

    profile_id: ProfileId
    modelo: str = Field(min_length=1, max_length=16)
    revision_id: RevisionId = Field(min_length=1, max_length=64)
    filing_year: int = Field(ge=2000, le=2100)
    period: Period
    missing: tuple[ProfilePreflightRequirement, ...] = ()
    profile_ready: bool
    per_operation_requirements_assessed: bool
    profile_refusal: str = ""
    registry_ready: bool = True
    registry_refusal: str = ""
    binding_ready: bool = True
    missing_bindings: tuple[ProjectionModeloBindingRequirement, ...] = ()
    ledger_preflight_required: bool = False
    ledger_ready: bool | None = None
    ledger_period: Period | None = None
    ledger_checked_transaction_count: int = 0
    ledger_issues: tuple[LedgerPreflightIssue, ...] = ()
    ready: bool


@dataclass(frozen=True, slots=True)
class _ModeloReadinessRegistryResolution:
    snapshot: RegistrySnapshot | None
    refusal: str = ""

    @property
    def ready(self) -> bool:
        return self.snapshot is not None and not self.refusal


def _build_modelo_readiness(
    requests: tuple[ModeloReadinessRequest, ...],
    *,
    active_profile_id: str | None,
) -> tuple[ProjectionModeloReadiness, ...]:
    """Compute one preflight report per readiness request.

    Returns an empty tuple when no request is supplied or no profile is
    active; a profile-load failure for a target is surfaced by the
    caller, not swallowed here.
    """
    if not requests or active_profile_id is None:
        return ()

    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket_by_id

    from ..core.i18n import tr
    from ..domain.user_profile.values import ProfileSetupState
    from .modelo._profile_readiness_gate import (
        modelo_applicability_refusal,
        modelo_work_profile_preflight_report,
        pre_activity_period_refusal,
    )
    from .user_profile.profile_record_repository import ProfileRecordRepository

    pointer = read_profile_bucket_by_id(active_profile_id)
    if pointer is None:
        return ()
    record = ProfileRecordRepository.for_current_session(pointer.bucket_id).load(pointer.bucket_id)
    reports: list[ProjectionModeloReadiness] = []
    for request in requests:
        readiness_period = _ledger_period_for_modelo_readiness(request)
        registry_resolution = _resolve_modelo_readiness_registry(request, period=readiness_period)
        revision = registry_resolution.snapshot.revision if registry_resolution.snapshot is not None else None
        profile_report = modelo_work_profile_preflight_report(
            record=record,
            modelo=request.modelo,
            revision_id=revision.id if revision is not None else request.revision_id,
            filing_year=readiness_period.filing_year,
            period=readiness_period,
            revision=revision,
            resolve_revision_when_missing=registry_resolution.snapshot is not None,
            authority=bundled_authority(),
        )
        profile_refusal = (
            tr("application.modelo.errors.profile_readiness_setup_incomplete")
            if record.setup_state is ProfileSetupState.INCOMPLETE
            else ""
        )
        applicability_refusal = modelo_applicability_refusal(
            record=record,
            bucket_id=pointer.bucket_id,
            modelo=request.modelo,
        )
        if not profile_refusal and applicability_refusal is not None:
            profile_refusal = applicability_refusal[0]
        pre_activity_refusal = pre_activity_period_refusal(
            record=record,
            bucket_id=pointer.bucket_id,
            modelo=request.modelo,
            filing_year=request.filing_year,
            period=readiness_period,
        )
        if not profile_refusal and pre_activity_refusal is not None:
            profile_refusal = pre_activity_refusal[0]
        profile_ready = profile_report.ready and not profile_refusal
        ledger_report = None
        if registry_resolution.snapshot is not None and _snapshot_requires_ledger_preflight(
            registry_resolution.snapshot
        ):
            ledger_report = preflight_ledger_tax_readiness(
                bucket_id=pointer.bucket_id,
                period=readiness_period,
            )
        missing_bindings = (
            _missing_calculation_bindings_for_readiness(
                registry_resolution.snapshot,
                bucket_id=pointer.bucket_id,
                profile_record=record,
                ledger_sources_ready=ledger_report is not None and ledger_report.ready,
                modelo=request.modelo,
                period=readiness_period,
            )
            if registry_resolution.snapshot is not None
            else ()
        )
        reports.append(
            ProjectionModeloReadiness(
                profile_id=profile_report.profile_id,
                modelo=profile_report.modelo,
                revision_id=profile_report.revision_id,
                filing_year=profile_report.filing_year,
                period=profile_report.period,
                missing=profile_report.missing,
                profile_ready=profile_ready,
                per_operation_requirements_assessed=profile_report.per_operation_requirements_assessed,
                profile_refusal=profile_refusal,
                registry_ready=registry_resolution.ready,
                registry_refusal=registry_resolution.refusal,
                binding_ready=not missing_bindings,
                missing_bindings=missing_bindings,
                ledger_preflight_required=ledger_report is not None,
                ledger_ready=ledger_report.ready if ledger_report is not None else None,
                ledger_period=(ledger_report.period if ledger_report is not None else None),
                ledger_checked_transaction_count=(
                    ledger_report.checked_transaction_count if ledger_report is not None else 0
                ),
                ledger_issues=tuple(ledger_report.issues) if ledger_report is not None else (),
                ready=(
                    registry_resolution.ready
                    and profile_ready
                    and not missing_bindings
                    and (ledger_report is None or ledger_report.ready)
                ),
            ),
        )
    return tuple(reports)


# The ledger-preflight binding source set is single-sourced in
# cadrumo.domain.calculations.registry.LEDGER_BINDING_SOURCE_KINDS; the
# import is at the top of the module (no frozenset literal here).


def modelo_requires_ledger_preflight(request: ModeloReadinessRequest) -> bool:
    """Return whether a modelo readiness target requires ledger preflight.

    An unresolved registry snapshot is treated as "not required" for this
    predicate and logged at DEBUG; the full readiness projection reports
    the registry refusal through
    :attr:`ProjectionModeloReadiness.registry_refusal` after resolving the same
    :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot`.
    """
    readiness_period = _ledger_period_for_modelo_readiness(request)
    resolution = _resolve_modelo_readiness_registry(request, period=readiness_period)
    if resolution.snapshot is None:
        _log.debug(
            "state projection: registry snapshot unavailable for modelo readiness; ledger preflight skipped",
            extra={
                "modelo": request.modelo,
                "filing_year": request.filing_year,
                "period": readiness_period.registry_token,
                "refusal": resolution.refusal,
            },
        )
        return False
    return _snapshot_requires_ledger_preflight(resolution.snapshot)


def _snapshot_requires_ledger_preflight(snapshot: RegistrySnapshot) -> bool:
    """Return whether the registry snapshot declares ledger-backed bindings."""
    return any(binding.source in _LEDGER_PREFLIGHT_BINDING_SOURCES for binding in snapshot.revision.bindings)


def _resolve_modelo_readiness_registry(
    request: ModeloReadinessRequest,
    *,
    period: Period,
) -> _ModeloReadinessRegistryResolution:
    """Resolve the registry snapshot used by modelo readiness.

    Registry lookup failures are converted into a typed refusal string so
    callers can render ``registry_ready: false`` instead of losing the
    rest of the projection.
    """
    from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError

    period_token = period.registry_token
    try:
        snapshot = bundled_authority().snapshot(
            request.modelo,
            filing_year=request.filing_year,
            period=period_token,
        )
    except (FileNotFoundError, RegistrySnapshotError, RegistryValidationError) as exc:
        refusal = _registry_readiness_refusal(request, period_token=period_token, exc=exc)
        _log.debug(
            "state projection: registry snapshot unavailable for modelo readiness",
            extra={
                "modelo": request.modelo,
                "revision_id": request.revision_id,
                "filing_year": request.filing_year,
                "period": period_token,
                "refusal": refusal,
            },
            exc_info=True,
        )
        return _ModeloReadinessRegistryResolution(snapshot=None, refusal=refusal)
    if request.revision_id and snapshot.revision.id != request.revision_id:
        refusal = _registry_readiness_revision_mismatch_refusal(
            request,
            period_token=period_token,
            resolved_revision_id=snapshot.revision.id,
        )
        return _ModeloReadinessRegistryResolution(snapshot=None, refusal=refusal)
    return _ModeloReadinessRegistryResolution(snapshot=snapshot)


def _registry_readiness_refusal(
    request: ModeloReadinessRequest,
    *,
    period_token: str,
    exc: Exception,
) -> str:
    detail = one_line_error_message(exc)
    return (
        "registry snapshot unresolved for modelo "
        f"{request.modelo!r}, year {request.filing_year}, period {period_token!r}, "
        f"revision {request.revision_id!r}: {detail}."
    )


def _registry_readiness_revision_mismatch_refusal(
    request: ModeloReadinessRequest,
    *,
    period_token: str,
    resolved_revision_id: RevisionId,
) -> str:
    return (
        "registry snapshot unresolved for modelo "
        f"{request.modelo!r}, year {request.filing_year}, period {period_token!r}, "
        f"revision {request.revision_id!r}: requested revision {request.revision_id!r} "
        f"does not match law-determined revision {resolved_revision_id!r}."
    )


def _missing_calculation_bindings_for_readiness(
    snapshot: RegistrySnapshot,
    *,
    bucket_id: str,
    profile_record: object,
    ledger_sources_ready: bool,
    modelo: str,
    period: Period,
) -> tuple[ProjectionModeloBindingRequirement, ...]:
    """Return registry bindings not available to calculation readiness.

    Ledger aggregation bindings are the source kinds declared by
    :data:`~cadrumo.domain.calculations.registry.LEDGER_BINDING_SOURCE_KINDS`;
    they are available only through the ledger preflight path. Once that
    preflight passes, the calculation mesh can resolve them from the bucket
    ledger and readiness must not report them as missing operator inputs.

    A relation-prefill binding the calculate resolver zero-defaults for
    ``period`` (the Modelo 202 first-period same-model previous-payment carry,
    which has no upstream filing before its first target period) is likewise
    not a missing operator input: calculate satisfies it with a zero default,
    so readiness must not report it as missing. Both surfaces read the one
    shared authority (:func:`relation_prefill_period_zero_default_binding_ids`)
    so the readiness missing set and the calculate refusal set agree by
    construction (``aeat-calculation-aggregation``).
    """
    from cadrumo.domain.calculations.registry.runtime_graph import enum_consumed_binding_ids, revision_date_binding_ids

    from .calculations import relation_prefill_period_zero_default_binding_ids
    from .modelo.profile_binding import (
        ProfileBindingResolutionError,
        profile_resolved_binding_ids,
        resolve_profile_sourced_bindings,
    )

    revision = snapshot.revision
    enum_consumed = {str(binding_id) for binding_id in enum_consumed_binding_ids(revision)}
    date_consumed = {str(binding_id) for binding_id in revision_date_binding_ids(revision)}
    if not revision.bindings:
        return ()
    period_zero_defaulted = {
        str(binding_id)
        for binding_id in relation_prefill_period_zero_default_binding_ids(
            revision,
            modelo=modelo,
            period=period.registry_token,
        )
    }
    try:
        profile_resolution = resolve_profile_sourced_bindings(
            snapshot,
            bucket_id=bucket_id,
            profile_record=profile_record,
        )
    except ProfileBindingResolutionError:
        _log.debug(
            "state projection: profile binding resolution failed for modelo readiness",
            extra={"modelo": revision.id, "bucket_id": bucket_id},
            exc_info=True,
        )
        profile_resolved: set[str] = set()
    else:
        profile_resolved = {str(binding_id) for binding_id in profile_resolved_binding_ids(profile_resolution)}

    missing: list[ProjectionModeloBindingRequirement] = []
    for binding in sorted(revision.bindings, key=lambda item: str(item.id)):
        binding_id = str(binding.id)
        if binding.source in _LEDGER_PREFLIGHT_BINDING_SOURCES and ledger_sources_ready:
            continue
        if binding.source == BindingSourceKind.PROFILE and binding_id in profile_resolved:
            continue
        if binding_id in period_zero_defaulted:
            continue
        missing.append(
            ProjectionModeloBindingRequirement(
                binding_id=binding_id,
                source=binding.source,
                input_channel=readiness_binding_input_channel(
                    binding_id,
                    enum_consumed=enum_consumed,
                    date_consumed=date_consumed,
                ),
            ),
        )
    return tuple(missing)


def _ledger_period_for_modelo_readiness(request: ModeloReadinessRequest) -> Period:
    """Return the typed ledger period for the ledger preflight.

    Returns the typed :class:`~cadrumo.core.Period` on the request directly.
    When the request carries no period the annual ``0A`` fallback is returned.
    """
    if request.period is None:
        return Period.from_year_and_code(request.filing_year, "0A")
    return request.period


def build_operator_state_projection(
    *,
    state: WorkflowState | None = None,
    auth_snapshot: ActiveAuthProjectionSnapshot | None = None,
    requested_provider: str | None = None,
    probe_live_backend: bool = False,
    include_workspace_summary: bool = True,
    include_pending_obligations: bool = True,
    modelo_readiness_requests: tuple[ModeloReadinessRequest, ...] = (),
    today: date | None = None,
) -> OperatorStateProjection:
    """Assemble the one canonical operator-facing state projection.

    This is the single producer of :class:`OperatorStateProjection`.
    Every operator-facing surface calls it and reads its typed fields;
    no surface re-derives state.

    Args:
        state: Pre-loaded workflow state. When ``None`` and a profile
            is active, the state is loaded through
            :func:`~cadrumo.application.workflow.persistence.workflow_state_repository`;
            when ``None`` and no
            profile is active, an empty :class:`WorkflowState` is used
            (opening the bucket database would require a session that
            does not exist yet). A caller-supplied state has no storage-route
            provenance, so live backend probing is suppressed rather than
            combining that snapshot with credentials from the current route.
        auth_snapshot: Route-witnessed auth state and credentials obtained from
            :func:`active_auth_projection_span`. The caller keeps that span open
            while this function consumes the snapshot. Mutually exclusive with
            ``state``; unlike an unproven state value, the snapshot permits its
            witnessed credentials to feed the live backend probe.
        requested_provider: Optional provider id the caller scoped the
            auth readiness to. ``None`` reports the configured provider.
        probe_live_backend: When set, the live auth backend is queried
            for the ``available`` / ``health_*`` fields. The probe may
            downgrade derived authentication readiness, but it never
            elevates configuration.
        include_workspace_summary: When false, skip ledger, invoice,
            draft, work-unit, and revision counters. Auth-only surfaces
            use this so unrelated workspace-store corruption cannot
            block local auth readiness inspection; overview-style
            surfaces keep the default full projection.
        include_pending_obligations: When false, skip period deadline
            projection. Auth-only surfaces do not render obligation rows,
            so they should not fail because an unrelated period-readiness
            path changes.
        modelo_readiness_requests: Optional readiness targets; one
            :class:`ProjectionModeloReadiness` is computed per request.
        today: Reference date for the deadline computation. Defaults to
            :meth:`date.today`.

    Returns:
        The fully-populated :class:`OperatorStateProjection`. Building
        it mutates no store.
    """
    _ensure_profile_key_registry_registered()
    reference_today = today or today_madrid()
    if state is not None and auth_snapshot is not None:
        raise ValueError("state and auth_snapshot are mutually exclusive")
    if auth_snapshot is not None:
        return _assemble_operator_state_projection(
            auth_snapshot.state or WorkflowState(),
            active_bucket_id=auth_snapshot.bucket_id,
            credential_bucket_id=(auth_snapshot.bucket_id if auth_snapshot.state is not None else None),
            certificate_credentials=auth_snapshot.certificate_credentials,
            provider_kind=auth_snapshot.provider,
            provider_kind_is_authoritative=True,
            requested_provider=requested_provider,
            probe_live_backend=probe_live_backend,
            include_workspace_summary=include_workspace_summary,
            include_pending_obligations=include_pending_obligations,
            modelo_readiness_requests=modelo_readiness_requests,
            reference_today=reference_today,
        )
    if state is not None:
        return _assemble_operator_state_projection(
            state,
            active_bucket_id=resolve_active_bucket_id(),
            credential_bucket_id=None,
            certificate_credentials=None,
            provider_kind=None,
            provider_kind_is_authoritative=False,
            requested_provider=requested_provider,
            probe_live_backend=probe_live_backend,
            include_workspace_summary=include_workspace_summary,
            include_pending_obligations=include_pending_obligations,
            modelo_readiness_requests=modelo_readiness_requests,
            reference_today=reference_today,
        )
    with active_auth_projection_span(requested_provider=requested_provider) as snapshot:
        return _assemble_operator_state_projection(
            snapshot.state or WorkflowState(),
            active_bucket_id=snapshot.bucket_id,
            credential_bucket_id=(snapshot.bucket_id if snapshot.state is not None else None),
            certificate_credentials=snapshot.certificate_credentials,
            provider_kind=snapshot.provider,
            provider_kind_is_authoritative=True,
            requested_provider=requested_provider,
            probe_live_backend=probe_live_backend,
            include_workspace_summary=include_workspace_summary,
            include_pending_obligations=include_pending_obligations,
            modelo_readiness_requests=modelo_readiness_requests,
            reference_today=reference_today,
        )


def _assemble_operator_state_projection(
    resolved_state: WorkflowState,
    *,
    active_bucket_id: str | None,
    credential_bucket_id: str | None,
    certificate_credentials: ActiveCertificateCredentials | None,
    provider_kind: AuthProviderKind | None,
    provider_kind_is_authoritative: bool,
    requested_provider: str | None,
    probe_live_backend: bool,
    include_workspace_summary: bool,
    include_pending_obligations: bool,
    modelo_readiness_requests: tuple[ModeloReadinessRequest, ...],
    reference_today: date,
) -> OperatorStateProjection:
    has_active_profile = active_bucket_id is not None

    profile_health = assess_active_profile_health(resolved_state)

    workspace = (
        _build_workspace_summary(bucket_id=resolved_state.active_profile_bucket_id())
        if include_workspace_summary
        else ProjectionWorkspaceSummary()
    )
    auth = build_auth_readiness(
        resolved_state,
        provider_kind=provider_kind,
        provider_kind_is_authoritative=provider_kind_is_authoritative,
        requested_provider=requested_provider,
        probe_live_backend=probe_live_backend,
        credential_bucket_id=credential_bucket_id,
        certificate_credentials=certificate_credentials,
    )
    active_profile = _build_active_profile(profile_health)

    if has_active_profile and include_pending_obligations:
        pending_obligations = build_pending_obligations(
            _taxpayer_profile_from_state(resolved_state),
            today=reference_today,
        )
    else:
        pending_obligations = ()

    modelo_readiness = _build_modelo_readiness(
        modelo_readiness_requests,
        active_profile_id=profile_health.active_profile,
    )

    return OperatorStateProjection(
        active_profile=active_profile,
        auth=auth,
        workspace=workspace,
        modelo_readiness=modelo_readiness,
        pending_obligations=pending_obligations,
    )


def _ensure_profile_key_registry_registered() -> None:
    """Import the wizard package before projection code reads profile-key metadata."""
    from .wizard.compiler import ensure_profile_keys_registered

    ensure_profile_keys_registered()




_READINESS_CAPTURE_MAX_ATTEMPTS = 8
_readiness_capture_process_pid = os.getpid()
_readiness_capture_process_nonce = token_bytes(32)
_readiness_capture_domains: set[str] = set()
_readiness_capture_lock = RLock()
_readiness_capture_generations: dict[str, tuple[tuple[str, ...], int]] = {}
_readiness_capture_generation = 0


class ProjectionModeloReadinessCaptureError(CadrumoError, RuntimeError):
    """Raised when readiness cannot be computed over one stable window."""


@dataclass(frozen=True, slots=True)
class ProjectionModeloReadinessCapture:
    """One readiness report set and its currentness coordinate.

    ``reports`` is exactly what the sole readiness producer returned: every
    axis is carried whole, none is collapsed into a summary, and no capability
    is inferred from a ready flag. The active profile pointer, profile record
    and registry authority identity are folded into the opaque comparison
    domain and never exposed.
    """

    reports: tuple[ProjectionModeloReadiness, ...]
    comparison_domain: str
    generation: int

    def require_current(
        self, current: ProjectionModeloReadinessCurrentCoordinate
    ) -> ProjectionModeloReadinessCapture:
        """Refuse a currentness comparison outside this owner process domain."""
        _require_readiness_process_domain(self.comparison_domain)
        current.require_current(self)
        return self


@dataclass(frozen=True, slots=True)
class ProjectionModeloReadinessCurrentCoordinate:
    """Opaque same-process coordinate for one readiness owner scope."""

    comparison_domain: str
    generation: int

    def require_current(
        self, captured: ProjectionModeloReadinessCapture
    ) -> ProjectionModeloReadinessCurrentCoordinate:
        """Require a capture from this exact owner scope and process incarnation."""
        _require_readiness_process_domain(self.comparison_domain)
        _require_readiness_process_domain(captured.comparison_domain)
        if self.comparison_domain != captured.comparison_domain:
            raise ProjectionModeloReadinessCaptureError(
                translated_message="errors.refused.modelo_readiness_capture_not_current",
                context={"reason": "distinct_owner_scope"},
            )
        if self.generation != captured.generation:
            raise ProjectionModeloReadinessCaptureError(
                translated_message="errors.refused.modelo_readiness_capture_not_current",
                context={"reason": "capture_superseded"},
            )
        return self


def _require_readiness_process_domain(domain: str) -> None:
    """Refuse a coordinate domain not minted in this process incarnation."""
    if _readiness_capture_process_pid != os.getpid():
        raise ProjectionModeloReadinessCaptureError(
            translated_message="errors.refused.modelo_readiness_capture_not_current",
            context={"reason": "forked_process"},
        )
    with _readiness_capture_lock:
        known = domain in _readiness_capture_domains
    if not known:
        raise ProjectionModeloReadinessCaptureError(
            translated_message="errors.refused.modelo_readiness_capture_not_current",
            context={"reason": "foreign_process_incarnation"},
        )


def _readiness_comparison_domain(
    *,
    active_profile_id: str,
    requests: tuple[ModeloReadinessRequest, ...],
) -> str:
    """Mint the non-persisted coordinate domain for one readiness owner scope."""
    from ..core.config import load_settings

    domain = content_hash_hex(
        {
            "owner": "application.state_projection.modelo_readiness",
            "storage_root": str(load_settings().cadrumo_local_storage_root),
            "namespace": "application.modelo_readiness",
            "active_profile_id": active_profile_id,
            "requests": tuple(request.model_dump(mode="json") for request in requests),
            "process_incarnation": _readiness_capture_process_nonce.hex(),
        }
    )
    with _readiness_capture_lock:
        _readiness_capture_domains.add(domain)
    return domain


def _readiness_owner_observation(active_profile_id: str) -> tuple[str, ...]:
    """Read the pointer, profile record and registry authority limbs."""
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket_by_id

    from ..domain.calculations.registry.authority import bundled_authority
    from .user_profile.profile_record_repository import ProfileRecordRepository

    pointer = read_profile_bucket_by_id(active_profile_id)
    if pointer is None:
        return ("absent-pointer",)
    record = ProfileRecordRepository.for_current_session(pointer.bucket_id).load(pointer.bucket_id)
    registry_generation = bundled_authority().read_current_coordinate().generation
    return (
        pointer.bucket_id,
        content_hash_hex(record.model_dump(mode="json")),
        str(registry_generation),
    )


def _readiness_generation_for(domain: str, observation: tuple[str, ...]) -> int:
    """Assign one injective, order-preserving generation per distinct observation."""
    global _readiness_capture_generation
    with _readiness_capture_lock:
        recorded = _readiness_capture_generations.get(domain)
        if recorded is not None and recorded[0] == observation:
            return recorded[1]
        _readiness_capture_generation += 1
        _readiness_capture_generations[domain] = (observation, _readiness_capture_generation)
        return _readiness_capture_generation


def read_modelo_readiness_current_coordinate(
    requests: tuple[ModeloReadinessRequest, ...],
    *,
    active_profile_id: str,
) -> ProjectionModeloReadinessCurrentCoordinate:
    """Return the typed current coordinate for same-domain capture validation."""
    observation = _readiness_owner_observation(active_profile_id)
    domain = _readiness_comparison_domain(active_profile_id=active_profile_id, requests=requests)
    return ProjectionModeloReadinessCurrentCoordinate(
        comparison_domain=domain,
        generation=_readiness_generation_for(domain, observation),
    )


def capture_modelo_readiness(
    requests: tuple[ModeloReadinessRequest, ...],
    *,
    active_profile_id: str,
) -> ProjectionModeloReadinessCapture:
    """Compute readiness over a window in which none of its owner limbs moved.

    The owner observation is read either side of the sole
    :func:`_build_modelo_readiness` computation, so a profile or registry write
    landing mid-computation is retried rather than published as a report set
    stitched across two states. The reports are returned exactly as the
    producer built them.
    """
    for _attempt in range(_READINESS_CAPTURE_MAX_ATTEMPTS):
        before = _readiness_owner_observation(active_profile_id)
        reports = _build_modelo_readiness(requests, active_profile_id=active_profile_id)
        after = _readiness_owner_observation(active_profile_id)
        if before != after:
            continue
        domain = _readiness_comparison_domain(active_profile_id=active_profile_id, requests=requests)
        return ProjectionModeloReadinessCapture(
            reports=reports,
            comparison_domain=domain,
            generation=_readiness_generation_for(domain, after),
        )
    raise ProjectionModeloReadinessCaptureError(
        translated_message="errors.refused.modelo_readiness_capture_not_current",
        context={"reason": "contended", "attempts": _READINESS_CAPTURE_MAX_ATTEMPTS},
    )

__all__ = [
    "CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS",
    "MODELO_READINESS_MISSING_PROFILE_ACTION",
    "OPERATOR_ACTION_BY_MODELO_READINESS_BINDING_SOURCE",
    "OPERATOR_ACTION_BY_MODELO_READINESS_LEDGER_ISSUE",
    "ModeloReadinessRequest",
    "OperatorStateProjection",
    "ProjectionActiveProfile",
    "ProjectionAuthReadiness",
    "ProjectionModeloBindingRequirement",
    "ProjectionModeloReadiness",
    "ProjectionModeloReadinessCapture",
    "ProjectionModeloReadinessCaptureError",
    "ProjectionModeloReadinessCurrentCoordinate",
    "ProjectionObligation",
    "ProjectionWorkspaceSummary",
    "build_auth_readiness",
    "build_operator_state_projection",
    "build_pending_obligations",
    "capture_modelo_readiness",
    "modelo_requires_ledger_preflight",
    "read_modelo_readiness_current_coordinate",
]
