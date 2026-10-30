"""Frozen operator state/readiness records and their total recovery-action projections."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, Field, field_validator

from ..core.aggregation import BindingSourceKind
from ..core.errors.hierarchy import InternalInvariantError, pydantic_validation_boundary
from ..core.filing_year import FilingYear
from ..core.identity.profile import ProfileId
from ..core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..core.operator_action_enums import OperatorActionAxis
from ..core.period import Period
from ..domain.calculations.registry.ids import RevisionId
from ..domain.deadlines.models import ObligationStatus
from .ledger.preflight import LedgerPreflightIssue, LedgerPreflightIssueReason
from .operator_actions.models import PreconditionVerdict
from .state_projection_auth import ProjectionAuthReadiness
from .user_profile.commands import ProfilePreflightRequirement


class ProjectionActiveProfile(BaseModel):
    """Active-profile identity and health, computed once for every surface.

    This record is the projection-side form of
    :class:`~cadrumo.application.workflow.profile_health.ActiveProfileHealth`. Auth and overview
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
            from :func:`~cadrumo.application.workflow.profile_health.assess_active_profile_health`.
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
    :class:`~cadrumo.domain.filing.schema.ModeloDraft` store while
    ``modelo work create`` / ``calculate`` write the
    :class:`~WorkUnitCatalogue` store. Calculation output is
    counted separately through
    :class:`~CalculationRevisionCatalogue`. A single
    ``drafts`` counter that read only the first store reported ``0`` for an
    operator who used the ``modelo work`` flow.

    Attributes:
        transactions: Count of imported transactions.
        invoices: Count of imported invoices.
        drafts: Count of declaration-draft :class:`~cadrumo.domain.filing.schema.ModeloDraft`
            entries.
        work_units: Count of *active* (``BORRADOR``)
            :class:`~WorkUnitCatalogue` entries written by
            ``modelo work create``. Discarded units are excluded so the counter
            is never inflated by units the operator has abandoned.
        discarded_work_units: Count of ``DESCARTADO``
            :class:`~WorkUnitCatalogue` entries, carried
            distinctly so a surface can state the active / discarded split
            rather than a misleading total.
        calculation_revisions: Count of
            :class:`~CalculationRevisionCatalogue`
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

    Rows are copied from the :class:`~cadrumo.domain.deadlines.models.Schedule`
    obligations produced for the active :class:`TaxpayerProfile`. Workflow
    filing gates later select a narrower
    :class:`~cadrumo.domain.deadlines.models.ModeloDeadline` from the same schedule
    producer.

    Attributes:
        modelo: Modelo identifier.
        period: Typed :class:`~cadrumo.core.period.Period` for the obligation window.
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
    :func:`~cadrumo.application.state_projection.build_operator_state_projection`, and consumed by every
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
            :func:`~cadrumo.domain.deadlines.engine.compute_obligation_schedule`, the
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


class ModeloReadinessRequest(BaseModel):
    """One ``(modelo, revision, year, period)`` readiness target.

    The projection producer accepts a tuple of these and computes one
    :class:`ProjectionModeloReadiness` per request, so ``modelo readiness``
    never builds its own profile, registry, binding, or ledger preflight
    pass.

    Attributes:
        period: Typed :class:`~cadrumo.core.period.Period` scoping the readiness
            check, or ``None`` when the caller omits the period (the
            projection uses the annual ``0A`` period for registry and
            ledger preflight resolution).
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    revision_id: RevisionId = Field(min_length=1, max_length=64)
    filing_year: FilingYear
    period: Period | None = None


class ProjectionModeloBindingRequirement(BaseModel):
    """One registry calculation binding readiness cannot currently satisfy.

    These are non-constant binding declarations from the resolved
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot` that are not
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
    @pydantic_validation_boundary
    def _hydrate_source(cls, value: object) -> object:
        """Hydrate the persisted source token without admitting unknown strings."""
        if isinstance(value, str) and not isinstance(value, BindingSourceKind):
            return BindingSourceKind(value)
        return value


CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS: Mapping[
    BindingSourceKind,
    str,
] = MappingProxyType(
    {
        BindingSourceKind.PROFILE: "cli.app.modelo.bindings.readiness.dato_perfil",
        BindingSourceKind.PREVIOUS_FILING: "cli.app.modelo.bindings.readiness.declaracion_previa",
        BindingSourceKind.RELATION_PREFILL: "cli.app.modelo.bindings.readiness.entrada_relacion",
        BindingSourceKind.MANUAL_INPUT: "cli.app.modelo.bindings.readiness.entrada_manual",
        BindingSourceKind.DESIGN_CONSTANT: "cli.app.modelo.bindings.readiness.constante_diseno",
        BindingSourceKind.LEDGER_OSS_AGGREGATION: "cli.app.modelo.bindings.readiness.datos_libro",
        BindingSourceKind.LEDGER_IVA_AGGREGATION: "cli.app.modelo.bindings.readiness.datos_libro",
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION: (
            "cli.app.modelo.bindings.readiness.datos_libro"
        ),
        BindingSourceKind.ACTIVITY_ASSET_DISPOSAL: "cli.app.modelo.bindings.readiness.datos_libro",
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
        BindingSourceKind.M347_THIRD_PARTY_OPERATION: "cli.app.modelo.bindings.readiness.operacion_tercero",
        BindingSourceKind.M349_INTRACOMMUNITY_OPERATION: "cli.app.modelo.bindings.readiness.operacion_intracomunitaria",
        BindingSourceKind.LEDGER_TRANSACTION: "cli.app.modelo.bindings.readiness.datos_libro",
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE: "cli.app.modelo.bindings.readiness.evidencia_factura_compra",
        BindingSourceKind.WITHHOLDING: "cli.app.modelo.bindings.readiness.retencion",
        BindingSourceKind.FOREIGN_ASSET: "cli.app.modelo.bindings.readiness.activo_extranjero",
        BindingSourceKind.ATRIBUCION_MEMBER: "cli.app.modelo.bindings.readiness.miembro_atribucion",
        BindingSourceKind.GASTO193_CONTRIBUTOR: "cli.app.modelo.bindings.readiness.gasto193_contribuyente",
        BindingSourceKind.WITHHOLDING296: "cli.app.modelo.bindings.readiness.withholding296_perceptor",
        BindingSourceKind.AFILIADO_COTIZACION: "cli.app.modelo.bindings.readiness.afiliado_cotizacion",
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
        BindingSourceKind.DESIGN_CONSTANT: OperatorActionAxis.REVIEW_ADVISORY,
        BindingSourceKind.LEDGER_OSS_AGGREGATION: OperatorActionAxis.IMPORT_LEDGER_DATA,
        BindingSourceKind.LEDGER_IVA_AGGREGATION: OperatorActionAxis.IMPORT_LEDGER_DATA,
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION: (OperatorActionAxis.IMPORT_LEDGER_DATA),
        BindingSourceKind.ACTIVITY_ASSET_DISPOSAL: OperatorActionAxis.COMPLETE_DOCUMENT_EVIDENCE,
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
        BindingSourceKind.M347_THIRD_PARTY_OPERATION: OperatorActionAxis.IMPORT_LEDGER_DATA,
        BindingSourceKind.M349_INTRACOMMUNITY_OPERATION: OperatorActionAxis.IMPORT_LEDGER_DATA,
        BindingSourceKind.LEDGER_TRANSACTION: OperatorActionAxis.IMPORT_LEDGER_DATA,
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE: OperatorActionAxis.COMPLETE_DOCUMENT_EVIDENCE,
        BindingSourceKind.WITHHOLDING: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
        BindingSourceKind.FOREIGN_ASSET: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
        BindingSourceKind.ATRIBUCION_MEMBER: OperatorActionAxis.SET_PROFILE_FACT,
        BindingSourceKind.GASTO193_CONTRIBUTOR: OperatorActionAxis.COMPLETE_DOCUMENT_EVIDENCE,
        BindingSourceKind.WITHHOLDING296: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
        BindingSourceKind.AFILIADO_COTIZACION: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
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
        LedgerPreflightIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION: (OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE),
        LedgerPreflightIssueReason.MISSING_PROPORTIONALITY_REFERENCE: (OperatorActionAxis.COMPLETE_DOCUMENT_EVIDENCE),
        LedgerPreflightIssueReason.UNSUPPORTED_CURRENCY: OperatorActionAxis.IMPORT_LEDGER_DATA,
        LedgerPreflightIssueReason.UNSUPPORTED_PERIOD: OperatorActionAxis.IMPORT_LEDGER_DATA,
        LedgerPreflightIssueReason.CENSO_RATIO_MISMATCH: OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE,
        LedgerPreflightIssueReason.MISSING_HOME_OFFICE_AFECTACION: (OperatorActionAxis.COMPLETE_DOCUMENT_EVIDENCE),
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
        raise InternalInvariantError(
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
        raise InternalInvariantError(
            "every BindingSourceKind must declare exactly one binding-readiness locale key; "
            f"missing={missing}; unexpected={unexpected}",
        )


_assert_total_binding_source_readiness_projection()
_assert_total_action_projection(
    LedgerPreflightIssueReason.__name__,
    tuple(LedgerPreflightIssueReason),
    OPERATOR_ACTION_BY_MODELO_READINESS_LEDGER_ISSUE,
)


class ModeloProfileRefusalCause(StrEnum):
    """Closed cause of a profile readiness refusal, independent of display prose."""

    SETUP_INCOMPLETE = "setup_incomplete"
    NOT_APPLICABLE = "not_applicable"
    PRE_ACTIVITY_PERIOD = "pre_activity_period"


class ModeloRegistryRefusalCause(StrEnum):
    """Closed cause of an unavailable modelo registry snapshot."""

    SNAPSHOT_UNAVAILABLE = "snapshot_unavailable"
    REVISION_MISMATCH = "revision_mismatch"


class ProjectionModeloReadiness(BaseModel):
    """Readiness for one modelo target across all preflight axes.

    The projection combines profile requirements, registry-snapshot
    availability, calculation binding resolution, and ledger preflight
    into one emit shape. ``ready`` is true only when every axis is ready; a
    :class:`~cadrumo.application.ledger.preflight.LedgerPreflightIssue` blocks readiness
    only when the resolved :class:`RegistrySnapshot` declares ledger-backed
    bindings.

    Attributes:
        profile_id: Active :data:`~cadrumo.core.identity.profile.ProfileId` used for the
            readiness report.
        modelo: Modelo identifier from the :class:`ModeloReadinessRequest`.
        revision_id: Registry revision requested or resolved for this target.
        filing_year: Filing year used to resolve registry and profile
            requirements.
        missing: Profile fields still required by the
            :class:`~cadrumo.application.user_profile.commands.ProfilePreflightReport`.
        profile_refusal: Operator-facing refusal when profile facts are
            present but disqualify the target period.
        profile_precondition_verdict: Typed recovery verdict for
            ``profile_refusal`` when a catalogued operator action resolves it
            (an unfinished profile setup), or ``None`` when the refusal is
            absent or states facts no action repairs.
        registry_ready: Whether the requested modelo/year/period/revision
            resolved to a usable registry snapshot.
        registry_refusal: Operator-facing explanation when registry
            resolution failed.
        binding_ready: Whether every non-constant registry binding can be
            supplied by the current profile or ledger state.
        missing_bindings: Missing :class:`ProjectionModeloBindingRequirement`
            records for unresolved calculation inputs.
        period: Typed :class:`~cadrumo.core.period.Period` the readiness check was
            scoped to.
        ledger_preflight_required: Whether the registry declares any
            ledger aggregation binding requiring ledger preflight.
        ledger_ready: Ledger-preflight verdict, or ``None`` when no
            ledger preflight was required.
        ledger_period: The :class:`~cadrumo.core.period.Period` the ledger preflight
            was scoped to, or ``None`` when no ledger preflight was run.
        ledger_issues: Blocking :class:`LedgerPreflightIssue` rows.
        per_operation_requirements_assessed: Whether the per-modelo
            schema-required axis (see
            :attr:`~cadrumo.application.user_profile.commands.ProfilePreflightReport.per_operation_requirements_assessed`)
            actually examined any field for this modelo. ``False`` means no
            schema-required field was checked and ``profile_ready`` reflects
            only the export-identity and conditional checks; it MUST NOT be
            rendered as a clean bill of health.
    """

    model_config = _STRICT_FROZEN

    profile_id: ProfileId
    modelo: str = Field(min_length=1, max_length=16)
    revision_id: RevisionId = Field(min_length=1, max_length=64)
    filing_year: FilingYear
    period: Period
    missing: tuple[ProfilePreflightRequirement, ...] = ()
    profile_ready: bool
    per_operation_requirements_assessed: bool
    profile_refusal: str = ""
    profile_refusal_cause: ModeloProfileRefusalCause | None = None
    profile_precondition_verdict: PreconditionVerdict | None = None
    registry_ready: bool = True
    registry_refusal: str = ""
    registry_refusal_cause: ModeloRegistryRefusalCause | None = None
    binding_ready: bool = True
    missing_bindings: tuple[ProjectionModeloBindingRequirement, ...] = ()
    ledger_preflight_required: bool = False
    ledger_ready: bool | None = None
    ledger_period: Period | None = None
    ledger_checked_transaction_count: int = 0
    ledger_issues: tuple[LedgerPreflightIssue, ...] = ()
    ready: bool
