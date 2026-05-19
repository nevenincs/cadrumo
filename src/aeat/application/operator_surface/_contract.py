"""Application-owned operator surface contract for the CLI workflow redesign."""

from __future__ import annotations

from functools import lru_cache

from ...core.i18n import tr
from ...core.logging import get_logger
from ._errors import OperatorSurfaceContractError
from ._models import (
    LifecycleContract,
    ModeloLifecycleStep,
    MountedCommandDomain,
    MountedCommandFamily,
    OperatorMutability,
    OperatorSurfaceContract,
    OperatorSurfaceLogFields,
    RetiredOperatorSurface,
    RootSurface,
    RootSurfaceName,
    ServiceOwner,
    SourceKind,
    SourceKindAlias,
)

LOGGER = get_logger(__name__)

ACCEPTED_ROOTS: tuple[RootSurface, ...] = (
    RootSurface(
        name=RootSurfaceName.CONFIG,
        purpose="profile lifecycle, bucket lifecycle, first-run state, auth, diagnostics, and durable configuration",
        owns_storage_maintenance=True,
        owns_operational_workflow=False,
        required_children=("init", "profile", "auth", "repair"),
    ),
    RootSurface(
        name=RootSurfaceName.APP,
        purpose="operational tax workflow over the active profile bucket",
        owns_storage_maintenance=False,
        owns_operational_workflow=True,
        required_children=("overview", "ledger", "live", "modelo", "registry", "review"),
    ),
)

RETIRED_OPERATOR_SURFACES: tuple[RetiredOperatorSurface, ...] = (
    RetiredOperatorSurface(
        name="setup",
        replacement="config",
        suggestion="aeat config profile create NAME",
        reason=tr("cli.operator_surface.retired.setup_reason"),
    ),
    RetiredOperatorSurface(
        name="archive",
        replacement="config bucket",
        suggestion="aeat config bucket",
        reason=tr("cli.operator_surface.retired.archive_reason"),
    ),
    RetiredOperatorSurface(
        name="data",
        replacement="app ledger",
        suggestion="aeat app ledger",
        reason=tr("cli.operator_surface.retired.data_reason"),
    ),
    RetiredOperatorSurface(
        name="filing",
        replacement="app modelo",
        suggestion="aeat app modelo",
        reason=tr("cli.operator_surface.retired.filing_reason"),
    ),
    RetiredOperatorSurface(
        name="financial",
        replacement="app ledger",
        suggestion="aeat app ledger",
        reason=tr("cli.operator_surface.retired.financial_reason"),
    ),
    RetiredOperatorSurface(
        name="invoice",
        replacement="app ledger",
        suggestion="aeat app ledger",
        reason=tr("cli.operator_surface.retired.invoice_reason"),
    ),
    RetiredOperatorSurface(
        name="declaration",
        replacement="app modelo",
        suggestion="aeat app modelo",
        reason=tr("cli.operator_surface.retired.declaration_reason"),
    ),
    RetiredOperatorSurface(
        name="sanitize",
        replacement="app ledger",
        suggestion="aeat app ledger check",
        reason=tr("cli.operator_surface.retired.sanitize_reason"),
    ),
    RetiredOperatorSurface(
        name="llm",
        replacement=None,
        suggestion="aeat app ledger classify",
        reason=tr("cli.operator_surface.retired.llm_reason"),
    ),
    RetiredOperatorSurface(
        name="topic",
        replacement="app registry",
        suggestion="aeat app registry citations",
        reason=tr("cli.operator_surface.retired.topic_reason"),
    ),
    RetiredOperatorSurface(
        name="submit",
        replacement=None,
        suggestion=None,
        reason=tr("cli.operator_surface.retired.submit_reason"),
    ),
    RetiredOperatorSurface(
        name="presentation",
        replacement="app modelo export",
        suggestion="aeat app modelo export",
        reason=tr("cli.operator_surface.retired.presentation_reason"),
    ),
    RetiredOperatorSurface(
        name="preflight",
        replacement="app modelo verify",
        suggestion="aeat app modelo verify",
        reason=tr("cli.operator_surface.retired.preflight_reason"),
    ),
    RetiredOperatorSurface(
        name="workflow",
        replacement="app modelo",
        suggestion="aeat app modelo",
        reason=tr("cli.operator_surface.retired.workflow_reason"),
    ),
)

SOURCE_KINDS: tuple[SourceKind, ...] = (
    SourceKind.LEDGER_TRANSACTION,
    SourceKind.PURCHASE_INVOICE_EVIDENCE,
    SourceKind.PAYABLE_INVOICE,
    SourceKind.COLLECTIBLE_INVOICE,
)

SOURCE_KIND_ALIASES: tuple[SourceKindAlias, ...] = (
    SourceKindAlias(alias="lt", canonical=SourceKind.LEDGER_TRANSACTION),
    SourceKindAlias(alias="pie", canonical=SourceKind.PURCHASE_INVOICE_EVIDENCE),
    SourceKindAlias(alias="pi", canonical=SourceKind.PAYABLE_INVOICE),
    SourceKindAlias(alias="ci", canonical=SourceKind.COLLECTIBLE_INVOICE),
)

MOUNTED_COMMAND_FAMILIES: tuple[MountedCommandFamily, ...] = (
    MountedCommandFamily(
        domain=MountedCommandDomain.FIRST_RUN,
        root=RootSurfaceName.CONFIG,
        child="init",
        operator_question="create or refresh the local profile bucket and first-run configuration",
        service_owner="aeat.application.wizard",
        commands=("init",),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.PROFILE,
        root=RootSurfaceName.CONFIG,
        child="profile",
        operator_question="inspect and edit the active profile values used by backend workflows",
        service_owner="aeat.application.user_profile",
        commands=("list", "get", "set", "unset", "status"),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.AUTH,
        root=RootSurfaceName.CONFIG,
        child="auth",
        operator_question="configure and inspect local authentication state for read-only AEAT access",
        service_owner="aeat.application.auth",
        commands=("providers", "configure", "status", "test", "clear"),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.DIAGNOSTICS,
        root=RootSurfaceName.CONFIG,
        child="repair",
        operator_question="diagnose local configuration, logs, connectivity, and secure-object integrity",
        service_owner="aeat.application.diagnostics",
        commands=("connectivity", "integrity", "list", "quarantine", "reset-state", "logs"),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.OVERVIEW,
        root=RootSurfaceName.APP,
        child="overview",
        operator_question="summarize active profile work state and period calendar readiness",
        service_owner="aeat.application.overview",
        commands=("status",),
        mutability=OperatorMutability.READ_ONLY,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.LEDGER,
        root=RootSurfaceName.APP,
        child="ledger",
        operator_question="ingest and review ledger transactions in the active bucket",
        service_owner="aeat.application.transactions",
        commands=("import", "review", "edit"),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.LIVE,
        root=RootSurfaceName.APP,
        child="live",
        operator_question="perform explicit read-only AEAT live observations",
        service_owner="aeat.application.live",
        commands=("filed",),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.MODELO,
        root=RootSurfaceName.APP,
        child="modelo",
        operator_question="inspect modelo registry data and manage modelo work units",
        service_owner="aeat.application.modelo",
        commands=("list", "describe", "casillas", "bindings", "formulas", "work"),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.REGISTRY,
        root=RootSurfaceName.APP,
        child="registry",
        operator_question="inspect and verify local registry authority data",
        service_owner="aeat.application.registry",
        commands=("inspect", "verify", "audit-oracles", "verify-filed-state", "workbooks", "parity"),
        mutability=OperatorMutability.READ_ONLY,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.REVIEW,
        root=RootSurfaceName.APP,
        child="review",
        operator_question="inspect read-only cross-domain items that need operator attention",
        service_owner="aeat.application.review",
        commands=("queue", "show"),
        mutability=OperatorMutability.READ_ONLY,
    ),
)

SERVICE_OWNERS: tuple[ServiceOwner, ...] = (
    ServiceOwner(
        capability="root_contract",
        owner="aeat.application.operator_surface",
        notes="owns accepted root, retired surface, lifecycle, and source-kind contract records",
    ),
    ServiceOwner(
        capability="profile_and_bucket_state",
        owner="aeat.application.user_profile",
        notes="owns active profile state consumed by app commands",
    ),
    ServiceOwner(
        capability="workflow_state",
        owner="aeat.application.workflow",
        notes="owns profile read path and workflow state repository access",
    ),
    ServiceOwner(
        capability="modelo_lifecycle",
        owner="aeat.application.filing",
        notes=(
            "owns calculate, verify, file, amend, reconcile, history, and export behavior "
            "until modelo services split out"
        ),
    ),
    ServiceOwner(
        capability="ledger_transactions",
        owner="aeat.application.transactions",
        notes="owns ledger import and transaction diagnostics until ledger services split out",
    ),
    ServiceOwner(
        capability="review_queue",
        owner="aeat.application.review",
        notes="owns operator review items and edits across source domains",
    ),
)

ERROR_CODES: tuple[str, ...] = ("REFUSED_OPERATOR_SURFACE_CONTRACT",)


def build_operator_surface_contract() -> OperatorSurfaceContract:
    """Build the immutable operator surface contract.

    Returns the canonical declaration of the modelo lifecycle steps,
    operator-facing CLI surfaces, and orthogonal verb axes the rest
    of the codebase reads from. The contract is constructed once at
    import time so every consumer sees the same shape.
    """

    lifecycle = LifecycleContract(
        steps=(
            ModeloLifecycleStep.CALCULATE,
            ModeloLifecycleStep.VERIFY,
            ModeloLifecycleStep.FILE,
        )
    )
    log_fields = OperatorSurfaceLogFields(
        root_count=len(ACCEPTED_ROOTS),
        retired_surface_count=len(RETIRED_OPERATOR_SURFACES),
        lifecycle=" -> ".join(step.value for step in lifecycle.steps),
        source_kind_count=len(SOURCE_KINDS),
    )
    contract = OperatorSurfaceContract(
        roots=ACCEPTED_ROOTS,
        retired_surfaces=RETIRED_OPERATOR_SURFACES,
        lifecycle=lifecycle,
        source_kinds=SOURCE_KINDS,
        source_kind_aliases=SOURCE_KIND_ALIASES,
        command_families=MOUNTED_COMMAND_FAMILIES,
        service_owners=SERVICE_OWNERS,
        log_fields=log_fields,
        error_codes=ERROR_CODES,
    )
    LOGGER.debug("built operator surface contract", extra=log_fields.as_extra())
    return contract


@lru_cache(maxsize=1)
def get_operator_surface_contract() -> OperatorSurfaceContract:
    """Return the cached backend-owned operator surface contract."""

    return build_operator_surface_contract()


def require_accepted_root(name: str) -> RootSurface:
    """Return an accepted root or raise a registered application error."""

    normalized = name.strip().lower()
    for root in get_operator_surface_contract().roots:
        if root.name.value == normalized:
            return root
    retired = retired_surface_suggestion(normalized)
    suggestion = retired.suggestion if retired is not None else "aeat --help"
    reason = retired.reason if retired is not None else tr("cli.operator_surface.errors.accepted_roots_only")
    raise OperatorSurfaceContractError(normalized or name, reason=reason, suggestion=suggestion)


def retired_surface_suggestion(name: str) -> RetiredOperatorSurface | None:
    """Return the retired-surface contract for ``name`` when one exists."""

    normalized = name.strip().lower()
    for surface in get_operator_surface_contract().retired_surfaces:
        if surface.name == normalized:
            return surface
    return None


def resolve_source_kind_alias(value: str) -> SourceKind:
    """Resolve canonical source kinds and parser-only aliases."""

    normalized = value.strip().lower()
    for source_kind in SOURCE_KINDS:
        if source_kind.value == normalized:
            return source_kind
    for alias in SOURCE_KIND_ALIASES:
        if alias.alias == normalized:
            return alias.canonical
    raise OperatorSurfaceContractError(
        value,
        reason=tr("cli.operator_surface.errors.unknown_source_kind"),
        suggestion=tr("cli.operator_surface.errors.source_kind_options"),
    )
