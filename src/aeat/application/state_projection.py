"""The single canonical operator-facing state read-projection.

Every operator-facing surface that reports "the truth" about the
active profile — ``overview status``, ``auth status``, ``auth test``,
and ``modelo readiness`` — consumes this one projection. None of them
re-derives state from a private subset of the stores.

The :class:`OperatorStateProjection` is a typed, frozen pydantic model
built by exactly one producer, :func:`build_operator_state_projection`.
The producer loads the profile aggregate, the workspace catalogues
(transactions via :class:`TransactionCatalogueRepository`, invoices via
:class:`InvoiceCatalogueRepository`, modelo drafts, modelo work units,
calculation revisions), the auth state, the active-profile health, and the
deadline obligations computed from :class:`Schedule`, and computes each
readiness value exactly once.
Modelo readiness resolves a :class:`RegistrySnapshot` only to evaluate
registry-declared preflight requirements for the requested work surface.

The projection is pure read: building it mutates no store.

Background: ``overview status`` historically reconstructed workspace
counters from a different store subset than ``modelo work`` writes —
it read the ``ModeloDraft`` store but never the ``WorkUnitCatalogue``
or ``CalculationRevisionCatalogue`` stores — so an operator who used
``modelo work create`` / ``calculate`` saw ``drafts: 0``. This
projection carries ``drafts`` (the legacy ``ModeloDraft`` store) and
``work_units`` (the ``WorkUnitCatalogue`` store) as distinct counters,
so neither is silently zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ..adapters.persistence.storage import inspect_bucket_storage_runtime
from ..core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..core import Period, resolve_active_bucket_id
from ..core.errors import AeatError
from ..core.identity import ProfileId
from ..core.logging import get_logger
from ..domain.calculations.registry import LEDGER_BINDING_SOURCE_KINDS as _LEDGER_PREFLIGHT_BINDING_SOURCES
from ..domain.deadlines import (
    DeadlineEngine,
    ObligationStatus,
    Schedule,
    TaxpayerProfile,
    compute_obligation_schedule,
)
from ..domain.filing import ModeloDraftRepository
from ..domain.invoices import InvoiceCatalogueRepository
from ..domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ..domain.modelos._repository import WorkUnitCatalogueRepository
from ..domain.modelos._work_unit import WorkUnitState
from ..domain.transactions import TransactionCatalogueRepository
from ..domain.user_profile import load_user_profile_schema
from .auth import AuthProviderKind, select_provider
from .ledger import LedgerPreflightIssue, preflight_ledger_tax_readiness
from .user_profile import ProfilePreflightRequirement
from .workflow._models import WorkflowState
from .workflow._persistence import workflow_state_repository
from .workflow._profile_health import ActiveProfileHealth, assess_active_profile_health

if TYPE_CHECKING:
    from ..domain.calculations.registry import RegistrySnapshot

_log = get_logger(__name__)
_AUTH_PROVIDER_VALUES = frozenset(kind.value for kind in AuthProviderKind)


class ProjectionActiveProfile(BaseModel):
    """Active-profile identity and health, computed once for every surface.

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
        next_action: The operator-facing next-step command carried from
            the profile-health assessment.
    """

    model_config = _STRICT_FROZEN

    profile_id: str | None = None
    label: str | None = None
    health_status: str = ""
    registered_bucket: bool = False
    record_present: bool = False
    next_action: str = ""


class ProjectionAuthReadiness(BaseModel):
    """Auth operational readiness, computed once for every surface.

    ``configured`` is the single canonical definition of "auth is
    operationally ready": a provider is selected in workflow state and,
    for the certificate provider, a certificate path is recorded. Both
    ``auth status`` and ``auth test`` read this same field — they
    cannot disagree because the value is computed once here.

    Attributes:
        provider: The configured (or requested) provider id, or ``""``.
        configured: The single canonical operational-readiness flag.
        authenticated: Whether a live session has been recorded.
        available: Whether the live backend reports itself reachable.
            ``auth test`` may probe the live backend for a fresher
            ``available`` reading, but it never recomputes
            ``configured``.
        health_summary: The backend-reported health summary text.
        health_severity: A non-empty health severity token coherent
            with ``health_summary``. The certificate backend's own
            tokens (``OK`` / ``EXPIRED`` / ...) pass through; for a
            provider whose backend reports no severity the projection
            derives ``ok`` / ``warning`` / ``error`` from the readiness
            signals. Empty only when no provider is selected.
        certificate_path: Recorded certificate filesystem reference for
            the certificate provider, or ``""``. A non-certificate
            provider always reports ``""`` — it never carries a stale
            path from an earlier certificate configuration.
    """

    model_config = _STRICT_FROZEN

    provider: str = ""
    configured: bool = False
    authenticated: bool = False
    available: bool = False
    health_summary: str = ""
    health_severity: str = ""
    certificate_path: str = ""


class ProjectionWorkspaceSummary(BaseModel):
    """Counters for every workspace store, so none is silently zero.

    ``drafts`` and ``work_units`` are deliberately distinct counters:
    ``modelo file`` writes the legacy :class:`ModeloDraft` store while
    ``modelo work create`` / ``calculate`` write the
    :class:`WorkUnitCatalogue` store. A single ``drafts`` counter that
    read only the first store reported ``0`` for an operator who used
    the ``modelo work`` flow.

    Attributes:
        transactions: Count of imported transactions.
        invoices: Count of imported invoices.
        drafts: Count of legacy ``ModeloDraft`` entries.
        work_units: Count of *active* (``BORRADOR``) ``WorkUnitCatalogue``
            entries written by ``modelo work create``. Discarded units
            are excluded so the counter is never inflated by units the
            operator has abandoned.
        discarded_work_units: Count of ``DESCARTADO`` ``WorkUnitCatalogue``
            entries — carried distinctly so a surface can state the
            active / discarded split rather than a misleading total.
        calculation_revisions: Count of ``CalculationRevisionCatalogue``
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

    Attributes:
        modelo: Modelo identifier.
        period: Typed :class:`~aeat.core.Period` for the obligation window.
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
            :class:`ProjectionObligation` records. Computed through
            :func:`compute_obligation_schedule`, the single producer
            shared with the ``WorkflowEngine``
            ``NO_PENDING_OBLIGATION`` gate. The gate filters the same
            schedule down to its narrow ``next_deadline`` /
            ``(modelo, period)`` target; this field carries every
            obligation so a surface can render the whole upcoming set.
    """

    model_config = _STRICT_FROZEN

    active_profile: ProjectionActiveProfile
    auth: ProjectionAuthReadiness
    workspace: ProjectionWorkspaceSummary
    modelo_readiness: tuple[ProjectionModeloReadiness, ...] = ()
    pending_obligations: tuple[ProjectionObligation, ...] = ()


def _resolve_active_profile_label(bucket_id: str | None) -> str | None:
    """Resolve a bucket UUID to its operator-chosen display name.

    Reads the plaintext profile-bucket manifest (no secret access, no
    active session required); returns ``None`` when no profile is
    active or the manifest cannot be located.
    """
    if bucket_id is None:
        return None
    from .workflow import read_profile_bucket_by_id

    try:
        pointer = read_profile_bucket_by_id(bucket_id)
    except (OSError, ValueError) as exc:
        _log.debug(
            "state projection: unable to resolve active-profile label",
            exc_info=exc,
        )
        return None
    return pointer.label if pointer is not None else None


def _build_active_profile(health: ActiveProfileHealth) -> ProjectionActiveProfile:
    """Project the profile-health assessment into the projection sub-record."""
    return ProjectionActiveProfile(
        profile_id=health.active_profile,
        label=_resolve_active_profile_label(health.active_profile),
        health_status=health.status,
        registered_bucket=health.registered_bucket,
        record_present=health.profile_record_present,
        next_action=health.next_action,
    )


def _certificate_path_resolves(certificate_path: str) -> bool:
    """Return whether a recorded certificate path resolves to an existing file.

    ``configured`` for the certificate provider means genuine
    operational readiness, not merely that a path string was recorded.
    A path that is blank, or that does not resolve to an existing
    file, is not usable — and the backend health probe agrees,
    reporting ``certificate path not configured``. Resolving the path
    here keeps ``configured`` coherent with that health summary.
    """
    if not certificate_path:
        return False
    try:
        return Path(certificate_path).is_file()
    except OSError:
        return False


def _provider_configured(state: WorkflowState) -> bool:
    """Return the one canonical ``configured`` flag for the workflow state.

    A provider must be selected in workflow state. For the certificate
    provider, ``configured`` additionally requires a certificate path
    that resolves to an existing file: selecting the provider without
    a usable file leaves the slot operationally incomplete, and the
    flag must stay consistent with
    ``health_summary: certificate path not configured``.
    """
    auth = state.auth
    if not auth.provider:
        return False
    if auth.provider == AuthProviderKind.CERTIFICATE.value:
        return _certificate_path_resolves(auth.certificate_path or "")
    return True


def _build_auth_readiness(
    state: WorkflowState,
    *,
    requested_provider: str | None,
    probe_live_backend: bool,
) -> ProjectionAuthReadiness:
    """Compute the auth-readiness sub-record once.

    ``configured`` is computed exactly here, so ``auth status`` and
    ``auth test`` read one value and cannot disagree. When
    ``probe_live_backend`` is set, the live backend is queried for the
    ``available`` / ``health_*`` fields — and the backend's own
    ``configured`` reading is folded into the canonical ``configured``
    too. The backend's ``configured`` and ``health_summary`` come from
    one ``describe()`` evaluation; folding them together keeps the
    canonical ``configured`` coherent with the health summary, so
    ``configured: True`` can never co-exist with
    ``health_summary: certificate path not configured``.
    """
    auth = state.auth
    normalized_request = requested_provider.strip().lower() if requested_provider is not None else None
    provider = normalized_request or auth.provider or ""
    configured = _provider_configured(state) and (normalized_request is None or auth.provider == normalized_request)

    available = configured and bool(auth.authenticated_at)
    health_summary = ""
    health_severity = ""
    if probe_live_backend and provider:
        if provider not in _AUTH_PROVIDER_VALUES:
            _log.warning(
                "auth backend probe skipped for unknown provider; reporting unavailable",
            )
            available = False
        else:
            try:
                # The certificate path persisted by ``auth configure`` lives in
                # workflow state; the backend reads from ``Settings``. Carry the
                # workflow-state path into the Settings instance the backend
                # sees so ``configure`` and ``status`` cannot disagree on
                # whether the certificate is configured.
                # `load_settings()` honours `override_settings`; bare `Settings()`
                # bypasses the context-var and shows the project default cert
                # path even when a test overrides it.
                from ..core.config import load_settings as _load_settings

                backend_settings = _load_settings()
                if (
                    provider == AuthProviderKind.CERTIFICATE.value
                    and auth.certificate_path
                    and backend_settings.aeat_certificate_path is None
                ):
                    backend_settings = backend_settings.model_copy(
                        update={"aeat_certificate_path": Path(auth.certificate_path)},
                    )
                backend = select_provider(AuthProviderKind(provider), settings=backend_settings)
                description = backend.describe()
                available = description.available
                health_summary = description.health_summary or ""
                health_severity = description.health_severity or ""
                configured = configured and description.configured
            except (AeatError, OSError, ValueError, AttributeError):
                _log.warning(
                    "auth backend probe failed; reporting unavailable",
                    exc_info=True,
                )
                available = False

    authenticated = configured and bool(auth.authenticated_at)
    health_severity = _resolve_health_severity(
        health_severity,
        health_summary=health_summary,
        provider=provider,
        configured=configured,
        available=available,
        authenticated=authenticated,
    )

    return ProjectionAuthReadiness(
        provider=provider,
        configured=configured,
        authenticated=authenticated,
        available=available,
        health_summary=health_summary,
        health_severity=health_severity,
        # G1: the certificate path is a certificate-provider field; a
        # non-certificate provider must never carry a stale path left
        # over from an earlier certificate configuration.
        certificate_path=(auth.certificate_path or "" if provider == AuthProviderKind.CERTIFICATE.value else ""),
    )


def _resolve_health_severity(
    backend_severity: str,
    *,
    health_summary: str,
    provider: str,
    configured: bool,
    available: bool,
    authenticated: bool,
) -> str:
    """Return a non-empty, coherent ``health_severity`` token.

    The certificate backend already emits its own severity tokens
    (``OK`` / ``EXPIRED`` / ``EXPIRING`` ...); those are authoritative
    and pass through unchanged. The Cl@ve Móvil backend reports a
    ``health_summary`` but no severity, so the field would otherwise
    always be empty (persona-fleet finding G4). When a provider is
    selected and the backend left the severity blank, derive a token
    that agrees with the readiness signals: ``ok`` for a configured,
    available, authenticated provider; ``warning`` for one that is
    configured but not yet usable end-to-end; ``info`` when a provider
    is selected but the configuration is still incomplete (an undeclared
    state, not a genuine fault — round-5 M5). With no provider selected
    and no summary the field stays empty — there is nothing to classify.

    ``error`` is reserved for backend-reported genuine faults (a
    certificate corrupt, expired, or unreadable) so a benign pending
    or undeclared state can never be paired with the loudest severity.
    """
    if backend_severity:
        return backend_severity
    if not provider:
        return ""
    if not configured:
        return "info"
    if available and authenticated:
        return "ok"
    return "warning"


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

    Mirrors the CLI ``_profile_to_taxpayer`` helper so the deadline
    engine receives the same profile shape every surface would compute.
    """
    from ..domain.deadlines import taxpayer_profile_from_mapping
    from .user_profile._projections import record_to_values

    record = state.active_profile_record()
    raw = record_to_values(record) if record is not None else {}
    return taxpayer_profile_from_mapping(raw, tax_id_default="00000000T")


def build_pending_obligations(
    profile: TaxpayerProfile,
    *,
    today: date,
) -> tuple[ProjectionObligation, ...]:
    """Compute the deadline obligations for the active profile.

    Routes through :func:`compute_obligation_schedule`, the single
    producer of the pending-obligation datum shared with the
    ``WorkflowEngine`` ``NO_PENDING_OBLIGATION`` gate, so the gate and
    the projection cannot draw a divergent obligation set. A failure to
    compute the schedule is logged and degrades to an empty tuple
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
    except (AeatError, ValueError, LookupError, AttributeError):
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
    :class:`ProfilePreflightReport` per request, so ``modelo readiness``
    never builds its own preflight pass.

    Attributes:
        periodo: Typed :class:`~aeat.core.Period` scoping the readiness
            check, or ``None`` when the caller omits the period (the
            authority then uses the modelo's sole revision for the year).
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    revision_id: str = Field(min_length=1, max_length=64)
    filing_year: int = Field(ge=2000, le=2100)
    period: Period | None = None


class ProjectionModeloBindingRequirement(BaseModel):
    """One calculation binding that readiness cannot currently satisfy."""

    model_config = _STRICT_FROZEN

    binding_id: str = Field(min_length=1, max_length=128)
    source: str = Field(min_length=1, max_length=64)
    input_channel: str = Field(min_length=1, max_length=16)


class ProjectionModeloReadiness(BaseModel):
    """Readiness for one modelo target across profile and ledger facts.

    Attributes:
        period: Typed :class:`~aeat.core.Period` the readiness check was
            scoped to.
        ledger_period: The :class:`~aeat.core.Period` the ledger preflight
            was scoped to, or ``None`` when no ledger preflight was run.
    """

    model_config = _STRICT_FROZEN

    profile_id: ProfileId
    modelo: str = Field(min_length=1, max_length=16)
    revision_id: str = Field(min_length=1, max_length=64)
    filing_year: int = Field(ge=2000, le=2100)
    period: Period
    missing: tuple[ProfilePreflightRequirement, ...] = ()
    profile_ready: bool
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

    from .user_profile._orchestration import build_lifecycle_service
    from .user_profile._preflight import ProfilePreflightService
    from .workflow import read_profile_bucket_by_id

    pointer = read_profile_bucket_by_id(active_profile_id)
    if pointer is None:
        return ()
    record = build_lifecycle_service(bucket_id=pointer.bucket_id).read(active_profile_id)
    service = ProfilePreflightService(schema=load_user_profile_schema())
    reports: list[ProjectionModeloReadiness] = []
    for request in requests:
        readiness_period = _ledger_period_for_modelo_readiness(request)
        registry_resolution = _resolve_modelo_readiness_registry(request, period=readiness_period)
        revision = registry_resolution.snapshot.revision if registry_resolution.snapshot is not None else None
        profile_report = service.report(
            record=record,
            modelo=request.modelo,
            revision_id=request.revision_id,
            period=readiness_period,
            revision=revision,
        )
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
                profile_ready=profile_report.ready,
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
                    and profile_report.ready
                    and not missing_bindings
                    and (ledger_report is None or ledger_report.ready)
                ),
            ),
        )
    return tuple(reports)


# W09.P44.S167: the ledger-preflight binding source set is single-sourced
# in aeat.domain.calculations.registry.LEDGER_BINDING_SOURCE_KINDS; the
# import is at the top of the module (no more frozenset literal here).


def modelo_requires_ledger_preflight(request: ModeloReadinessRequest) -> bool:
    """Return whether a modelo readiness target requires ledger preflight."""
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
    return any(binding.source in _LEDGER_PREFLIGHT_BINDING_SOURCES for binding in snapshot.revision.bindings)


def _resolve_modelo_readiness_registry(
    request: ModeloReadinessRequest,
    *,
    period: Period,
) -> _ModeloReadinessRegistryResolution:
    from ..core.resources import resources
    from ..domain.calculations.registry import RegistrySnapshotError, RegistryValidationError

    period_token = period.registry_token
    try:
        snapshot = resources().modelos.authority.snapshot(
            request.modelo,
            filing_year=request.filing_year,
            period=period_token,
            revision_id=request.revision_id,
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
    if snapshot.revision.id != request.revision_id:
        refusal = (
            "registry revision mismatch for modelo "
            f"{request.modelo!r}: requested {request.revision_id!r}, resolved {snapshot.revision.id!r}. "
            f"Run 'aeat app modelo describe {request.modelo}' to inspect declared revision_ids and periods."
        )
        return _ModeloReadinessRegistryResolution(snapshot=None, refusal=refusal)
    return _ModeloReadinessRegistryResolution(snapshot=snapshot)


def _registry_readiness_refusal(
    request: ModeloReadinessRequest,
    *,
    period_token: str,
    exc: Exception,
) -> str:
    detail = _one_line_error_message(exc)
    return (
        "registry snapshot unresolved for modelo "
        f"{request.modelo!r}, year {request.filing_year}, period {period_token!r}, "
        f"revision {request.revision_id!r}: {detail}. "
        f"Run 'aeat app modelo describe {request.modelo}' to inspect declared revision_ids and periods."
    )


def _one_line_error_message(exc: Exception) -> str:
    for line in str(exc).splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return exc.__class__.__name__


def _missing_calculation_bindings_for_readiness(
    snapshot: RegistrySnapshot,
    *,
    bucket_id: str,
    profile_record: object,
    ledger_sources_ready: bool,
) -> tuple[ProjectionModeloBindingRequirement, ...]:
    """Return non-constant registry bindings not available to calculation readiness.

    Ledger aggregation bindings are available only through the ledger preflight
    path. Once that preflight passes, the calculation mesh can resolve them from
    the bucket ledger and readiness must not report them as missing operator
    inputs.
    """
    from ..domain.calculations.registry import (
        enum_consumed_binding_ids,
        revision_date_binding_ids,
    )
    from .modelo import ProfileBindingResolutionError, resolve_profile_sourced_bindings

    revision = snapshot.revision
    enum_consumed = {str(binding_id) for binding_id in enum_consumed_binding_ids(revision)}
    date_consumed = {str(binding_id) for binding_id in revision_date_binding_ids(revision)}
    if not revision.bindings:
        return ()
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
        profile_resolved = {
            *(str(binding_id) for binding_id in profile_resolution.binding_values),
            *(str(binding_id) for binding_id in profile_resolution.enum_binding_values),
            *(str(binding_id) for binding_id in profile_resolution.date_binding_values),
        }

    missing: list[ProjectionModeloBindingRequirement] = []
    for binding in sorted(revision.bindings, key=lambda item: str(item.id)):
        binding_id = str(binding.id)
        source = _binding_source_value(binding.source)
        if source == "constant_value":
            continue
        if binding.source in _LEDGER_PREFLIGHT_BINDING_SOURCES and ledger_sources_ready:
            continue
        if source == "profile" and binding_id in profile_resolved:
            continue
        missing.append(
            ProjectionModeloBindingRequirement(
                binding_id=binding_id,
                source=source,
                input_channel=_readiness_binding_input_channel(
                    binding_id,
                    enum_consumed=enum_consumed,
                    date_consumed=date_consumed,
                ),
            ),
        )
    return tuple(missing)


def _binding_source_value(source: object) -> str:
    value = getattr(source, "value", source)
    return str(value)


def _readiness_binding_input_channel(
    binding_id: str,
    *,
    enum_consumed: set[str],
    date_consumed: set[str],
) -> str:
    if binding_id in date_consumed:
        return "date"
    if binding_id in enum_consumed:
        return "enum"
    return "decimal"


def _ledger_period_for_modelo_readiness(request: ModeloReadinessRequest) -> Period:
    """Return the typed ledger period for the ledger preflight.

    Returns the typed :class:`~aeat.core.Period` on the request directly.
    When the request carries no period the annual ``0A`` fallback is returned.
    """
    if request.period is None:
        return Period.from_year_and_code(request.filing_year, "0A")
    return request.period


def build_operator_state_projection(
    *,
    state: WorkflowState | None = None,
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
            :func:`workflow_state_repository`; when ``None`` and no
            profile is active, an empty :class:`WorkflowState` is used
            (opening the bucket database would require a session that
            does not exist yet).
        requested_provider: Optional provider id the caller scoped the
            auth readiness to. ``None`` reports the configured provider.
        probe_live_backend: When set, the live auth backend is queried
            for the ``available`` / ``health_*`` fields. ``configured``
            is never sourced from the probe.
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
            :class:`ProfilePreflightReport` is computed per request.
        today: Reference date for the deadline computation. Defaults to
            :meth:`date.today`.

    Returns:
        The fully-populated :class:`OperatorStateProjection`. Building
        it mutates no store.
    """
    _ensure_profile_key_registry_registered()
    reference_today = today or date.today()
    active_bucket_id = resolve_active_bucket_id()
    has_active_profile = active_bucket_id is not None

    if state is not None:
        resolved_state = state
    elif not has_active_profile:
        resolved_state = WorkflowState()
    else:
        resolved_state = workflow_state_repository().load()

    profile_health = assess_active_profile_health(resolved_state)

    workspace = (
        _build_workspace_summary(bucket_id=resolved_state.active_profile_bucket_id())
        if include_workspace_summary
        else ProjectionWorkspaceSummary()
    )
    auth = _build_auth_readiness(
        resolved_state,
        requested_provider=requested_provider,
        probe_live_backend=probe_live_backend,
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
    from . import wizard as _wizard

    _ = _wizard


__all__ = [
    "ModeloReadinessRequest",
    "OperatorStateProjection",
    "ProjectionActiveProfile",
    "ProjectionAuthReadiness",
    "ProjectionModeloBindingRequirement",
    "ProjectionModeloReadiness",
    "ProjectionObligation",
    "ProjectionWorkspaceSummary",
    "build_operator_state_projection",
    "build_pending_obligations",
    "modelo_requires_ledger_preflight",
]
