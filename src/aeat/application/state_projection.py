"""The single canonical operator-facing state read-projection.

Every operator-facing surface that reports "the truth" about the
active profile — ``overview status``, ``auth status``, ``auth test``,
and ``modelo readiness`` — consumes this one projection. None of them
re-derives state from a private subset of the stores.

The :class:`OperatorStateProjection` is a typed, frozen pydantic model
built by exactly one producer, :func:`build_operator_state_projection`.
The producer loads the profile aggregate, the workspace catalogues
(transactions, invoices, modelo drafts, modelo work units, calculation
revisions), the auth state, the active-profile health, and the
deadline obligations, and computes each readiness value exactly once.

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

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from ..core.config import Settings
from ..domain.deadlines import (
    AutonomoProfile,
    DeadlineEngine,
    ObligationStatus,
    Schedule,
)
from ..domain.filing import ModeloDraftRepository
from ..domain.invoices import InvoiceCatalogueRepository
from ..domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ..domain.modelos._repository import WorkUnitCatalogueRepository
from ..domain.transactions import TransactionCatalogueRepository
from .auth import AuthProviderKind, select_provider
from .user_profile import ProfilePreflightReport
from .workflow._models import WorkflowState, resolve_active_bucket_id
from .workflow._persistence import workflow_state_repository
from .workflow._profile_health import ActiveProfileHealth, assess_active_profile_health

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


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
        health_severity: The backend-reported health severity token.
        certificate_path: Recorded certificate filesystem reference, or
            ``""``.
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
        work_units: Count of ``WorkUnitCatalogue`` entries written by
            ``modelo work create``.
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
    calculation_revisions: int = Field(default=0, ge=0)
    unreadable_rows: int = Field(default=0, ge=0)


class ProjectionObligation(BaseModel):
    """One pending filing obligation carried in the projection.

    Attributes:
        modelo: Modelo identifier.
        period: Canonical period string.
        opens_on: First day the filing window accepts submissions.
        closes_on: Last day the filing window accepts submissions.
        status: The engine :class:`ObligationStatus`.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
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
        pending_obligations: The deadline obligations for the active
            profile's current year. The ``verify`` /
            ``NO_PENDING_OBLIGATION`` gate reads the same datum.
    """

    model_config = _STRICT_FROZEN

    active_profile: ProjectionActiveProfile
    auth: ProjectionAuthReadiness
    workspace: ProjectionWorkspaceSummary
    modelo_readiness: tuple[ProfilePreflightReport, ...] = ()
    pending_obligations: tuple[ProjectionObligation, ...] = ()


def _resolve_active_profile_label(bucket_id: str | None) -> str | None:
    """Resolve a bucket UUID to its operator-chosen display name.

    Reads the plaintext profile-bucket manifest (no secret access, no
    active session required); returns ``None`` when no profile is
    active or the manifest cannot be located.
    """

    if bucket_id is None:
        return None
    from .workflow._profile_bucket_scan import read_profile_bucket_by_id

    try:
        pointer = read_profile_bucket_by_id(bucket_id)
    except (OSError, ValueError):
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


def _certificate_configured(state: WorkflowState) -> bool:
    """Return the one canonical ``configured`` flag for the workflow state.

    A provider must be selected in workflow state. For the certificate
    provider, ``configured`` additionally requires a certificate path
    on disk: selecting the provider without supplying a file leaves the
    slot empty, and the field must stay consistent with
    ``health_summary: certificate path not configured``.
    """

    auth = state.auth
    if not auth.provider:
        return False
    if auth.provider == AuthProviderKind.CERTIFICATE.value:
        return bool(auth.certificate_path)
    return True


def _build_auth_readiness(
    state: WorkflowState,
    *,
    requested_provider: str | None,
    probe_live_backend: bool,
) -> ProjectionAuthReadiness:
    """Compute the auth-readiness sub-record once.

    ``configured`` is computed exactly here. When ``probe_live_backend``
    is set, the live backend is queried for the ``available`` /
    ``health_*`` fields — but ``configured`` is never sourced from the
    backend probe, so ``auth status`` and ``auth test`` agree.
    """

    auth = state.auth
    normalized_request = requested_provider.strip().lower() if requested_provider is not None else None
    provider = normalized_request or auth.provider or ""
    configured = bool(auth.provider) and (
        normalized_request is None or auth.provider == normalized_request
    )
    if configured and auth.provider == AuthProviderKind.CERTIFICATE.value:
        configured = bool(auth.certificate_path)

    available = configured and bool(auth.authenticated_at)
    health_summary = ""
    health_severity = ""
    if probe_live_backend and provider:
        try:
            backend = select_provider(AuthProviderKind(provider), settings=Settings())
            description = backend.describe()
            available = description.available
            health_summary = description.health_summary or ""
            health_severity = description.health_severity or ""
        except Exception:
            available = False

    return ProjectionAuthReadiness(
        provider=provider,
        configured=configured,
        authenticated=configured and bool(auth.authenticated_at),
        available=available,
        health_summary=health_summary,
        health_severity=health_severity,
        certificate_path=auth.certificate_path or "",
    )


def _build_workspace_summary(*, bucket_id: str | None) -> ProjectionWorkspaceSummary:
    """Load every workspace store and project its counters.

    With no active profile bucket there is no bucket database to open,
    so the counters are all zero without touching the encrypted stores.
    """

    if bucket_id is None:
        return ProjectionWorkspaceSummary()

    from .diagnostics import secure_object_unreadable_total

    transactions = TransactionCatalogueRepository(bucket_id=bucket_id).load()
    invoices = InvoiceCatalogueRepository().load()
    drafts = tuple(ModeloDraftRepository().iter_drafts())
    work_units = WorkUnitCatalogueRepository().load()
    revisions = CalculationRevisionCatalogueRepository().load()
    return ProjectionWorkspaceSummary(
        transactions=len(transactions.transactions),
        invoices=len(invoices),
        drafts=len(drafts),
        work_units=len(work_units),
        calculation_revisions=len(revisions),
        unreadable_rows=secure_object_unreadable_total(),
    )


def _autonomo_profile_from_state(state: WorkflowState) -> AutonomoProfile:
    """Project the active profile record into an :class:`AutonomoProfile`.

    Mirrors the CLI ``_profile_to_autonomo`` helper so the deadline
    engine receives the same profile shape every surface would compute.
    """

    from ..domain.deadlines import autonomo_profile_from_mapping
    from .user_profile._projections import record_to_values

    record = state.active_profile_record()
    raw = record_to_values(record) if record is not None else {}
    return autonomo_profile_from_mapping(raw, tax_id_default="00000000T")


def _build_pending_obligations(
    profile: AutonomoProfile,
    *,
    today: date,
) -> tuple[ProjectionObligation, ...]:
    """Compute the deadline obligations for the active profile.

    Carried in the projection so the ``NO_PENDING_OBLIGATION`` gate and
    ``modelo readiness`` read the same obligation datum. A failure to
    compute the schedule degrades to an empty tuple rather than failing
    the whole projection.
    """

    try:
        schedule: Schedule = DeadlineEngine().compute(profile, today.year, today=today)
    except Exception:
        return ()
    return tuple(
        ProjectionObligation(
            modelo=obligation.modelo,
            period=obligation.period,
            opens_on=obligation.opens_on,
            closes_on=obligation.closes_on,
            status=obligation.status,
        )
        for obligation in schedule.obligations
    )


class ModeloReadinessRequest(BaseModel):
    """One ``(modelo, revision, year, period)`` readiness target.

    The projection producer accepts a tuple of these and computes one
    :class:`ProfilePreflightReport` per request, so ``modelo readiness``
    never builds its own preflight pass.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    revision_id: str = Field(min_length=1, max_length=64)
    filing_year: int = Field(ge=2000, le=2100)
    period: str = ""


def _build_modelo_readiness(
    requests: tuple[ModeloReadinessRequest, ...],
    *,
    active_profile_id: str | None,
) -> tuple[ProfilePreflightReport, ...]:
    """Compute one preflight report per readiness request.

    Returns an empty tuple when no request is supplied or no profile is
    active; a profile-load failure for a target is surfaced by the
    caller, not swallowed here.
    """

    if not requests or active_profile_id is None:
        return ()

    from .user_profile._orchestration import _shared_schema, build_lifecycle_service
    from .user_profile._preflight import ProfilePreflightService
    from .workflow._profile_bucket_scan import read_profile_bucket_by_id

    pointer = read_profile_bucket_by_id(active_profile_id)
    if pointer is None:
        return ()
    record = build_lifecycle_service(bucket_id=pointer.bucket_id).read(active_profile_id)
    service = ProfilePreflightService(schema=_shared_schema())
    return tuple(
        service.report(
            record=record,
            modelo=request.modelo,
            revision_id=request.revision_id,
            filing_year=request.filing_year,
            period=request.period,
        )
        for request in requests
    )


def build_operator_state_projection(
    *,
    state: WorkflowState | None = None,
    requested_provider: str | None = None,
    probe_live_backend: bool = False,
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
        modelo_readiness_requests: Optional readiness targets; one
            :class:`ProfilePreflightReport` is computed per request.
        today: Reference date for the deadline computation. Defaults to
            :meth:`date.today`.

    Returns:
        The fully-populated :class:`OperatorStateProjection`. Building
        it mutates no store.
    """

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

    workspace = _build_workspace_summary(bucket_id=resolved_state.active_profile_bucket_id())
    auth = _build_auth_readiness(
        resolved_state,
        requested_provider=requested_provider,
        probe_live_backend=probe_live_backend,
    )
    active_profile = _build_active_profile(profile_health)

    if has_active_profile:
        pending_obligations = _build_pending_obligations(
            _autonomo_profile_from_state(resolved_state),
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


__all__ = [
    "ModeloReadinessRequest",
    "OperatorStateProjection",
    "ProjectionActiveProfile",
    "ProjectionAuthReadiness",
    "ProjectionObligation",
    "ProjectionWorkspaceSummary",
    "build_operator_state_projection",
]
