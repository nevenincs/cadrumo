"""The single canonical operator-facing state read-projection.

Every operator-facing state or readiness surface that reports "the
truth" about the active profile - ``overview status``, ``auth status``,
``auth test``, and ``modelo readiness`` - consumes this one projection.
None of them re-derives state from a private subset of the stores.

The :class:`OperatorStateProjection` is a typed, frozen pydantic model
built by exactly one producer, :func:`build_operator_state_projection`.
The producer consumes the application-owned profile and workspace read ports,
the auth state, the active-profile health, and the deadline obligations
computed from :class:`Schedule`, and computes each readiness value exactly
once.
Modelo readiness resolves a :class:`RegistrySnapshot` only to evaluate
registry-declared profile, binding, and ledger preflight requirements for the
requested :class:`ModeloReadinessRequest`.

The projection is pure read: building it mutates no store.

Background: ``overview status`` once reconstructed workspace
counters from a different store subset than ``modelo work`` writes:
it read the :class:`~cadrumo.domain.filing.schema.ModeloDraft` store but never the
:class:`~WorkUnitCatalogue` or
:class:`~CalculationRevisionCatalogue` stores, so an
operator who used
``modelo work create`` / ``calculate`` saw ``drafts: 0``. This
projection carries ``drafts`` (the declaration-draft
:class:`~cadrumo.domain.filing.schema.ModeloDraft` store) and ``work_units`` (the
:class:`~WorkUnitCatalogue` store) as distinct counters, so
neither is silently zero.

See Also:
    :class:`~cadrumo.application.overview.calendar_models.OverviewStatusReport`
        Overview emit shape derived from this projection, rather than from a
        second store assembly path.
    :func:`~cadrumo.application.overview.status_report.build_overview_status_report`
        Overview producer that consumes this projection instead of rebuilding
        workspace, auth, and deadline readiness.
    :class:`~cadrumo.application.auth.operator_results.AuthStatusResult`
        Auth emit shape that reads the same canonical configured/authenticated
        readiness values carried here.
    :func:`~cadrumo.application.auth.operator.inspect_operator_auth`
        Auth status producer that reads
        :class:`ProjectionAuthReadiness` and
        :class:`ProjectionActiveProfile` from this projection.
    :class:`~cadrumo.application.state_projection_ports.StateProjectionReadPorts`
        Required application-owned reads supplied by an outer composition root.
    :class:`ProjectionWorkspaceSummary`
        Per-store counter record that keeps declaration drafts, work units, and
        calculation revisions distinct.
    :class:`ProjectionModeloReadiness`
        Per-target readiness record built from profile facts, registry
        snapshots, binding availability, and ledger preflight.
    :func:`~cadrumo.application.workflow._deadline_stage.resolve_deadline_stage_obligation`
        Filing workflow selector that filters a schedule for the workflow gate;
        it does not consume ``pending_obligations`` directly.
    :func:`~cadrumo.domain.deadlines.engine.compute_obligation_schedule`
        Single deadline schedule producer used for projection obligations and
        workflow deadline-stage checks.
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
        Registry authority snapshot used to resolve modelo-readiness preflight
        requirements.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`,
:class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from ..core.aggregation import LEDGER_BINDING_SOURCE_KINDS as _LEDGER_PREFLIGHT_BINDING_SOURCES
from ..core.aggregation import BindingSourceKind
from ..core.auth_provider import AuthProviderKind
from ..core.bucket_pointer import resolve_active_bucket_id
from ..core.errors.hierarchy import CadrumoError
from ..core.hashing import content_hash_hex
from ..core.logging import get_logger
from ..core.period import Period
from ..core.time.clock import today_madrid
from ..domain.calculations.registry.ids import RevisionId
from ..domain.deadlines.engine import DeadlineEngine, compute_obligation_schedule
from ..domain.deadlines.models import Schedule, TaxpayerProfile
from ._state_projection_readiness import (
    one_line_error_message,
    readiness_binding_input_channel,
)
from .auth.credentials import ActiveAuthProjectionSnapshot, active_auth_projection_span
from .auth.operator_probe_ports import OperatorProbePorts
from .auth.operator_scope_ports import OperatorScopePorts
from .auth_credentials import ActiveCertificateCredentials
from .ledger.preflight import (
    LedgerPreflightIssue,
    LedgerPreflightReport,
    preflight_ledger_tax_readiness,
)
from .ledger.usage_ratio_repository import UsageRatioProfileLoader
from .operator_actions.models import PreconditionVerdict
from .producer_capture import ProducerCapture, ProducerCaptureCoordinate, ProducerCaptureScope
from .state_projection_auth import ProjectionAuthReadiness, build_auth_readiness
from .state_projection_models import (
    ModeloProfileRefusalCause,
    ModeloReadinessRequest,
    ModeloRegistryRefusalCause,
    OperatorStateProjection,
    ProjectionActiveProfile,
    ProjectionModeloBindingRequirement,
    ProjectionModeloReadiness,
    ProjectionObligation,
    ProjectionWorkspaceSummary,
)
from .state_projection_ports import StateProjectionReadPorts
from .user_profile.commands import ProfilePreflightReport
from .workflow.profile_health import ActiveProfileHealth, assess_active_profile_health
from .workflow.state_models import WorkflowState

if TYPE_CHECKING:
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
    from ..domain.user_profile.values import UserProfileRecord
    from .auth.certificate_secret_backend import CertificateSecretBackendFactory

_log = get_logger(__name__)


def build_active_profile(health: ActiveProfileHealth) -> ProjectionActiveProfile:
    """Project one coherent profile-health snapshot into the public record."""
    return ProjectionActiveProfile(
        profile_id=health.active_profile,
        label=health.active_profile_label,
        health_status=health.status,
        registered_bucket=health.registered_bucket,
        record_present=health.profile_record_present,
        precondition_verdict=health.precondition_verdict,
    )


def _build_workspace_summary(
    *,
    bucket_id: str | None,
    read_ports: StateProjectionReadPorts,
) -> ProjectionWorkspaceSummary:
    """Project the workspace facts supplied by the application read port.

    With no active profile bucket there is no bucket database to open,
    so the counters are all zero without touching the encrypted stores.
    """
    if bucket_id is None:
        return ProjectionWorkspaceSummary()

    workspace = read_ports.workspace.read_workspace(bucket_id=bucket_id)
    return ProjectionWorkspaceSummary(
        transactions=workspace.transactions,
        invoices=workspace.invoices,
        drafts=workspace.drafts,
        work_units=workspace.work_units,
        discarded_work_units=workspace.discarded_work_units,
        calculation_revisions=workspace.calculation_revisions,
        unreadable_rows=workspace.unreadable_rows,
    )


def _taxpayer_profile_from_state(
    state: WorkflowState,
    *,
    operation: PinnedAuthorityOperation,
) -> TaxpayerProfile:
    """Project the active profile record into an :class:`TaxpayerProfile`.

    Delegates to :func:`~cadrumo.application.user_profile.projections.projection_for_taxpayer`,
    the single fact-to-taxpayer projection authority, so the deadline engine
    receives exactly the profile shape every other surface computes. A live
    record projects against the schema pinned by ``operation``; an absent one
    projects an empty mapping, which carries no facts to decode.
    """
    from .user_profile.projections import projection_for_taxpayer

    record = state.active_profile_record()
    if record is None:
        return projection_for_taxpayer({})
    return projection_for_taxpayer(record, schema=operation.profile_schema())


def build_pending_obligations(
    profile: TaxpayerProfile,
    *,
    today: date,
) -> tuple[ProjectionObligation, ...]:
    """Compute the deadline obligations for the active profile.

    Routes through :func:`~cadrumo.domain.deadlines.engine.compute_obligation_schedule`,
    the single producer of the pending-obligation datum also used by the
    workflow deadline stage. This function projects the full
    :class:`~cadrumo.domain.deadlines.models.Schedule`; the workflow gate separately
    filters its target :class:`~cadrumo.domain.deadlines.models.ModeloDeadline` through
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


@dataclass(frozen=True, slots=True)
class _ModeloReadinessRegistryResolution:
    snapshot: RegistrySnapshot | None
    refusal: str = ""
    cause: ModeloRegistryRefusalCause | None = None

    @property
    def ready(self) -> bool:
        return self.snapshot is not None and not self.refusal


@dataclass(frozen=True, slots=True)
class _ModeloReadinessContext:
    """Profile facts loaded once for a set of readiness requests."""

    bucket_id: str
    record: UserProfileRecord


@dataclass(frozen=True, slots=True)
class _ModeloReadinessLedgerStage:
    """Ledger-preflight values projected into one readiness report."""

    required: bool = False
    ready: bool | None = None
    period: Period | None = None
    checked_transaction_count: int = 0
    issues: tuple[LedgerPreflightIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class _ModeloReadinessEvaluation:
    """All axes evaluated for one readiness request before final projection."""

    profile_report: ProfilePreflightReport
    profile_refusal: str
    profile_refusal_cause: ModeloProfileRefusalCause | None
    profile_precondition_verdict: PreconditionVerdict | None
    registry: _ModeloReadinessRegistryResolution
    period: Period
    missing_bindings: tuple[ProjectionModeloBindingRequirement, ...]
    ledger: _ModeloReadinessLedgerStage


def _load_modelo_readiness_context(
    active_profile_id: str,
    *,
    read_ports: StateProjectionReadPorts,
) -> _ModeloReadinessContext | None:
    """Load profile facts for readiness through the application read port."""
    profile = read_ports.profile.read_profile(profile_id=active_profile_id)
    if profile is None:
        return None
    return _ModeloReadinessContext(
        bucket_id=profile.bucket_id,
        record=profile.record,
    )


def _modelo_profile_refusal(
    *,
    record: UserProfileRecord,
    bucket_id: str,
    request: ModeloReadinessRequest,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> tuple[str, PreconditionVerdict | None, ModeloProfileRefusalCause | None]:
    """Return the first profile refusal while evaluating every refusal limb.

    Only the setup-incomplete limb carries a typed recovery verdict: the
    applicability and pre-activity limbs state facts the operator cannot fix
    through a catalogued action, so they travel as text alone.
    """
    from ..core.i18n.render import tr
    from ..domain.user_profile.values import ProfileSetupState
    from .modelo.profile_readiness_gate import (
        modelo_applicability_refusal,
        pre_activity_period_refusal,
    )
    from .operator_actions.preconditions import profile_setup_incomplete_verdict
    from .user_profile.completeness import missing_required_field_paths
    from .user_profile.projections import record_to_path_values

    setup_verdict = (
        profile_setup_incomplete_verdict(
            modelo=request.modelo,
            missing_required_field_count=len(
                missing_required_field_paths(operation.profile_schema(), record_to_path_values(record)),
            ),
        )
        if record.setup_state is ProfileSetupState.INCOMPLETE
        else None
    )
    applicability_refusal = modelo_applicability_refusal(
        record=record,
        bucket_id=bucket_id,
        modelo=request.modelo,
        operation=operation,
    )
    pre_activity_refusal = pre_activity_period_refusal(
        record=record,
        bucket_id=bucket_id,
        modelo=request.modelo,
        filing_year=request.filing_year,
        period=period,
    )
    if setup_verdict is not None:
        return (
            tr("application.modelo.errors.profile_readiness_setup_incomplete"),
            setup_verdict,
            ModeloProfileRefusalCause.SETUP_INCOMPLETE,
        )
    if applicability_refusal is not None:
        return applicability_refusal[0], None, ModeloProfileRefusalCause.NOT_APPLICABLE
    if pre_activity_refusal is not None:
        return pre_activity_refusal[0], None, ModeloProfileRefusalCause.PRE_ACTIVITY_PERIOD
    return "", None, None


def _build_modelo_profile_stage(
    request: ModeloReadinessRequest,
    *,
    context: _ModeloReadinessContext,
    period: Period,
    registry: _ModeloReadinessRegistryResolution,
    operation: PinnedAuthorityOperation,
) -> tuple[ProfilePreflightReport, str, PreconditionVerdict | None, ModeloProfileRefusalCause | None]:
    """Evaluate profile completeness and target-specific refusal limbs."""
    from .modelo.profile_readiness_gate import modelo_work_profile_preflight_report

    snapshot = registry.snapshot
    revision = snapshot.revision if snapshot is not None else None
    profile_report = modelo_work_profile_preflight_report(
        record=context.record,
        modelo=request.modelo,
        revision_id=revision.id if revision is not None else request.revision_id,
        filing_year=period.filing_year,
        period=period,
        revision=revision,
        resolve_revision_when_missing=snapshot is not None,
        profile_decode_context=operation.profile_decode_context(),
        operation=operation,
    )
    profile_refusal, profile_verdict, refusal_cause = _modelo_profile_refusal(
        record=context.record,
        bucket_id=context.bucket_id,
        request=request,
        period=period,
        operation=operation,
    )
    return profile_report, profile_refusal, profile_verdict, refusal_cause


def _build_modelo_ledger_stage(
    snapshot: RegistrySnapshot | None,
    *,
    bucket_id: str,
    period: Period,
    usage_ratio_profile_loader: UsageRatioProfileLoader,
    operation: PinnedAuthorityOperation,
) -> _ModeloReadinessLedgerStage:
    """Evaluate ledger preflight only when the registry declares it."""
    if snapshot is None or not _snapshot_requires_ledger_preflight(snapshot):
        return _ModeloReadinessLedgerStage()
    report: LedgerPreflightReport = preflight_ledger_tax_readiness(
        bucket_id=bucket_id,
        period=period,
        usage_ratio_profile_loader=usage_ratio_profile_loader,
        operation=operation,
    )
    return _ModeloReadinessLedgerStage(
        required=True,
        ready=report.ready,
        period=report.period,
        checked_transaction_count=report.checked_transaction_count,
        issues=tuple(report.issues),
    )


def _evaluate_modelo_readiness(
    request: ModeloReadinessRequest,
    *,
    context: _ModeloReadinessContext,
    usage_ratio_profile_loader: UsageRatioProfileLoader,
    operation: PinnedAuthorityOperation,
) -> _ModeloReadinessEvaluation:
    """Evaluate profile, registry, binding, and ledger axes for one request."""
    period = _ledger_period_for_modelo_readiness(request)
    registry = _resolve_modelo_readiness_registry(request, period=period, operation=operation)
    profile_report, profile_refusal, profile_precondition_verdict, profile_refusal_cause = _build_modelo_profile_stage(
        request,
        context=context,
        period=period,
        registry=registry,
        operation=operation,
    )
    ledger = _build_modelo_ledger_stage(
        registry.snapshot,
        bucket_id=context.bucket_id,
        period=period,
        usage_ratio_profile_loader=usage_ratio_profile_loader,
        operation=operation,
    )
    missing_bindings = (
        _missing_calculation_bindings_for_readiness(
            registry.snapshot,
            bucket_id=context.bucket_id,
            profile_record=context.record,
            ledger_sources_ready=ledger.ready is True,
            modelo=request.modelo,
            period=period,
            operation=operation,
        )
        if registry.snapshot is not None
        else ()
    )
    return _ModeloReadinessEvaluation(
        profile_report=profile_report,
        profile_refusal=profile_refusal,
        profile_refusal_cause=profile_refusal_cause,
        profile_precondition_verdict=profile_precondition_verdict,
        registry=registry,
        period=period,
        missing_bindings=missing_bindings,
        ledger=ledger,
    )


def _project_modelo_readiness(evaluation: _ModeloReadinessEvaluation) -> ProjectionModeloReadiness:
    """Project one completed readiness evaluation without recomputing axes."""
    profile_report = evaluation.profile_report
    profile_ready = profile_report.ready and not evaluation.profile_refusal
    ledger = evaluation.ledger
    return ProjectionModeloReadiness(
        profile_id=profile_report.profile_id,
        modelo=profile_report.modelo,
        revision_id=profile_report.revision_id,
        filing_year=profile_report.filing_year,
        period=profile_report.period,
        missing=profile_report.missing,
        profile_ready=profile_ready,
        per_operation_requirements_assessed=profile_report.per_operation_requirements_assessed,
        profile_refusal=evaluation.profile_refusal,
        profile_refusal_cause=evaluation.profile_refusal_cause,
        profile_precondition_verdict=evaluation.profile_precondition_verdict,
        registry_ready=evaluation.registry.ready,
        registry_refusal=evaluation.registry.refusal,
        registry_refusal_cause=evaluation.registry.cause,
        binding_ready=not evaluation.missing_bindings,
        missing_bindings=evaluation.missing_bindings,
        ledger_preflight_required=ledger.required,
        ledger_ready=ledger.ready,
        ledger_period=ledger.period,
        ledger_checked_transaction_count=ledger.checked_transaction_count,
        ledger_issues=ledger.issues,
        ready=(
            evaluation.registry.ready
            and profile_ready
            and not evaluation.missing_bindings
            and (not ledger.required or ledger.ready is True)
        ),
    )


def build_modelo_readiness_reports(
    requests: tuple[ModeloReadinessRequest, ...],
    *,
    active_profile_id: str | None,
    read_ports: StateProjectionReadPorts,
    operation: PinnedAuthorityOperation,
) -> tuple[ProjectionModeloReadiness, ...]:
    """Compute one preflight report per readiness request.

    Returns an empty tuple when no request is supplied or no profile is
    active; a profile-load failure for a target is surfaced by the
    caller, not swallowed here.
    """
    if not requests or active_profile_id is None:
        return ()

    context = _load_modelo_readiness_context(active_profile_id, read_ports=read_ports)
    if context is None:
        return ()
    return tuple(
        _project_modelo_readiness(
            _evaluate_modelo_readiness(
                request,
                context=context,
                usage_ratio_profile_loader=read_ports.usage_ratio_profile_loader,
                operation=operation,
            )
        )
        for request in requests
    )


# The ledger-preflight binding source set is single-sourced in
# cadrumo.domain.calculations.registry.LEDGER_BINDING_SOURCE_KINDS; the
# import is at the top of the module (no frozenset literal here).


def _snapshot_requires_ledger_preflight(snapshot: RegistrySnapshot) -> bool:
    """Return whether the registry snapshot declares ledger-backed bindings."""
    return any(binding.source in _LEDGER_PREFLIGHT_BINDING_SOURCES for binding in snapshot.revision.bindings)


def _resolve_modelo_readiness_registry(
    request: ModeloReadinessRequest,
    *,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> _ModeloReadinessRegistryResolution:
    """Resolve the registry snapshot used by modelo readiness.

    Registry lookup failures are converted into a typed refusal string so
    callers can render ``registry_ready: false`` instead of losing the
    rest of the projection.
    """
    from ..domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError

    period_token = period.registry_token
    try:
        snapshot = operation.snapshot(
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
        return _ModeloReadinessRegistryResolution(
            snapshot=None, refusal=refusal, cause=ModeloRegistryRefusalCause.SNAPSHOT_UNAVAILABLE
        )
    if request.revision_id and snapshot.revision.id != request.revision_id:
        refusal = _registry_readiness_revision_mismatch_refusal(
            request,
            period_token=period_token,
            resolved_revision_id=snapshot.revision.id,
        )
        return _ModeloReadinessRegistryResolution(
            snapshot=None, refusal=refusal, cause=ModeloRegistryRefusalCause.REVISION_MISMATCH
        )
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
    operation: PinnedAuthorityOperation,
) -> tuple[ProjectionModeloBindingRequirement, ...]:
    """Return registry bindings not available to calculation readiness.

    Ledger aggregation bindings are the source kinds declared by
    :data:`~cadrumo.core.aggregation.LEDGER_BINDING_SOURCE_KINDS`;
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
    from cadrumo.application.modelo.profile_derived_facts import ProfileBindingResolutionError

    from ..domain.calculations.registry.runtime_graph import enum_consumed_binding_ids, revision_date_binding_ids
    from .calculations.relation_prefill_m202 import relation_prefill_period_zero_default_binding_ids
    from .modelo.profile_binding import profile_resolved_binding_ids, resolve_profile_sourced_bindings

    revision = snapshot.revision
    enum_consumed = set(enum_consumed_binding_ids(revision))
    date_consumed = set(revision_date_binding_ids(revision))
    if not revision.bindings:
        return ()
    period_zero_defaulted = set(
        relation_prefill_period_zero_default_binding_ids(
            revision,
            modelo=modelo,
            filing_year=snapshot.filing_year,
            period=period.registry_token,
            operation=operation,
        )
    )
    try:
        profile_resolution = resolve_profile_sourced_bindings(
            snapshot,
            bucket_id=bucket_id,
            profile_record=profile_record,
            operation=operation,
        )
    except ProfileBindingResolutionError:
        _log.debug(
            "state projection: profile binding resolution failed for modelo readiness",
            extra={"modelo": revision.id, "bucket_id": bucket_id},
            exc_info=True,
        )
        profile_resolved: set[str] = set()
    else:
        profile_resolved = set(profile_resolved_binding_ids(profile_resolution))

    return _build_missing_binding_requirements(
        revision,
        enum_consumed=enum_consumed,
        date_consumed=date_consumed,
        period_zero_defaulted=period_zero_defaulted,
        profile_resolved=profile_resolved,
        ledger_sources_ready=ledger_sources_ready,
    )


def _build_missing_binding_requirements(
    revision: ModeloRevision,
    *,
    enum_consumed: set[str],
    date_consumed: set[str],
    period_zero_defaulted: set[str],
    profile_resolved: set[str],
    ledger_sources_ready: bool,
) -> tuple[ProjectionModeloBindingRequirement, ...]:
    """Project unresolved registry bindings in their canonical ID order."""
    missing: list[ProjectionModeloBindingRequirement] = []
    for binding in sorted(revision.bindings, key=lambda item: item.id):
        binding_id = binding.id
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

    Returns the typed :class:`~cadrumo.core.period.Period` on the request directly.
    When the request carries no period the annual ``0A`` fallback is returned.
    """
    if request.period is None:
        return Period.from_year_and_code(request.filing_year, "0A")
    return request.period


def build_operator_state_projection(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_probe_ports: OperatorProbePorts,
    operator_scope_ports: OperatorScopePorts,
    read_ports: StateProjectionReadPorts,
    operation: PinnedAuthorityOperation,
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
        certificate_secret_backend_factory: Application-owned certificate-secret
            backend factory used by auth readiness.
        operator_probe_ports: Required inward operator-auth probe capabilities.
        operator_scope_ports: Operator-scoped auth and profile capabilities.
        read_ports: Required application-owned profile and workspace reads
            composed by the outer entrypoint for this profile scope.
        operation: Caller-owned generation-pinned authority operation used by
            profile health and any requested modelo readiness projection.
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
    reference_today = today or today_madrid()
    if state is not None and auth_snapshot is not None:
        raise ValueError("state and auth_snapshot are mutually exclusive")
    if auth_snapshot is not None:
        return _assemble_operator_state_projection(
            auth_snapshot.state or WorkflowState(),
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=operator_probe_ports,
            operator_scope_ports=operator_scope_ports,
            read_ports=read_ports,
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
            operation=operation,
            reference_today=reference_today,
        )
    if state is not None:
        return _assemble_operator_state_projection(
            state,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=operator_probe_ports,
            operator_scope_ports=operator_scope_ports,
            read_ports=read_ports,
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
            operation=operation,
            reference_today=reference_today,
        )
    with active_auth_projection_span(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        requested_provider=requested_provider,
        operator_scope_ports=operator_scope_ports,
    ) as snapshot:
        return _assemble_operator_state_projection(
            snapshot.state or WorkflowState(),
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=operator_probe_ports,
            operator_scope_ports=operator_scope_ports,
            read_ports=read_ports,
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
            operation=operation,
            reference_today=reference_today,
        )


def _assemble_operator_state_projection(
    resolved_state: WorkflowState,
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_probe_ports: OperatorProbePorts,
    operator_scope_ports: OperatorScopePorts,
    read_ports: StateProjectionReadPorts,
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
    operation: PinnedAuthorityOperation,
    reference_today: date,
) -> OperatorStateProjection:
    has_active_profile = active_bucket_id is not None

    profile_health = assess_active_profile_health(resolved_state, operation=operation)

    workspace = (
        _build_workspace_summary(
            bucket_id=resolved_state.active_profile_bucket_id(),
            read_ports=read_ports,
        )
        if include_workspace_summary
        else ProjectionWorkspaceSummary()
    )
    auth = build_auth_readiness(
        resolved_state,
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_probe_ports=operator_probe_ports,
        operator_scope_ports=operator_scope_ports,
        provider_kind=provider_kind,
        provider_kind_is_authoritative=provider_kind_is_authoritative,
        requested_provider=requested_provider,
        probe_live_backend=probe_live_backend,
        credential_bucket_id=credential_bucket_id,
        certificate_credentials=certificate_credentials,
    )
    active_profile = build_active_profile(profile_health)

    if has_active_profile and include_pending_obligations:
        pending_obligations = build_pending_obligations(
            _taxpayer_profile_from_state(resolved_state, operation=operation),
            today=reference_today,
        )
    else:
        pending_obligations = ()

    if modelo_readiness_requests:
        modelo_readiness = build_modelo_readiness_reports(
            modelo_readiness_requests,
            active_profile_id=profile_health.active_profile,
            read_ports=read_ports,
            operation=operation,
        )
    else:
        modelo_readiness = ()

    return OperatorStateProjection(
        active_profile=active_profile,
        auth=auth,
        workspace=workspace,
        modelo_readiness=modelo_readiness,
        pending_obligations=pending_obligations,
    )


def _readiness_owner_observation(
    active_profile_id: str,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[str, ...]:
    """Read the profile pointer, the profile record and the registry generation.

    These are the three limbs a readiness report is a function of: which
    profile is active, what that profile declares, and which registry
    generation answered the modelo's requirements. A write to any of them
    between two reads makes the report a stitch across two states, which is
    exactly what the capture window refuses to publish.
    """
    from .user_profile.profile_record_repository import ProfileRecordRepository
    from .workflow.profile_bucket_scan import read_profile_bucket_by_id

    pointer = read_profile_bucket_by_id(active_profile_id)
    if pointer is None:
        return ("absent-pointer",)
    record = ProfileRecordRepository.for_current_session(
        pointer.bucket_id,
        profile_decode_context=operation.profile_decode_context(),
    ).load(pointer.bucket_id)
    return (
        pointer.bucket_id,
        content_hash_hex(record.model_dump(mode="json")),
        str(operation.read_current_coordinate().generation),
    )


_READINESS_CAPTURE_SCOPE = ProducerCaptureScope(
    owner="application.state_projection",
    namespace="modelo.readiness",
)


def capture_modelo_readiness(
    requests: tuple[ModeloReadinessRequest, ...],
    *,
    active_profile_id: str,
    read_ports: StateProjectionReadPorts,
    operation: PinnedAuthorityOperation,
) -> ProducerCapture[tuple[ProjectionModeloReadiness, ...]]:
    """Compute readiness over a window in which none of its owner limbs moved.

    The reports are exactly what :func:`build_modelo_readiness_reports`
    produced; this adds the currentness coordinate a pinned multi-producer
    read needs and nothing else. There is no second readiness computation
    here and none may be added: a consumer that needs readiness without a
    coordinate calls the builder directly.
    """
    return _READINESS_CAPTURE_SCOPE.capture(
        coordinate={"active_profile_id": active_profile_id, "requests": _readiness_request_coordinate(requests)},
        observe=lambda: _readiness_owner_observation(active_profile_id, operation=operation),
        build=lambda: build_modelo_readiness_reports(
            requests,
            active_profile_id=active_profile_id,
            read_ports=read_ports,
            operation=operation,
        ),
    )


def read_modelo_readiness_current_coordinate(
    requests: tuple[ModeloReadinessRequest, ...],
    *,
    active_profile_id: str,
    operation: PinnedAuthorityOperation,
) -> ProducerCaptureCoordinate:
    """Read the coordinate a later pass compares a readiness capture against."""
    return _READINESS_CAPTURE_SCOPE.read_current_coordinate(
        coordinate={"active_profile_id": active_profile_id, "requests": _readiness_request_coordinate(requests)},
        observe=lambda: _readiness_owner_observation(active_profile_id, operation=operation),
    )


def _readiness_request_coordinate(requests: tuple[ModeloReadinessRequest, ...]) -> str:
    """Name the exact request set one readiness capture answers."""
    return content_hash_hex([request.model_dump(mode="json") for request in requests])


__all__ = [
    "ProjectionAuthReadiness",
    "build_active_profile",
    "build_auth_readiness",
    "build_modelo_readiness_reports",
    "build_operator_state_projection",
    "build_pending_obligations",
    "capture_modelo_readiness",
    "read_modelo_readiness_current_coordinate",
]
