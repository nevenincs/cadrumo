"""Application-owned operator-surface contract for the workflow redesign.

This module declares the accepted :class:`RootSurface` records, canonical
:class:`~aeat.core.BindingSourceKind` subset, parser-only
:class:`SourceKindAlias` records, mounted :class:`MountedCommandFamily`
records, backend :class:`ServiceOwner` inventory, log metadata, and registered
error-code tuple that build the immutable :class:`OperatorSurfaceContract`.

It owns contract data only: command adapters render and enforce this shape
without redefining it. The module does not inspect storage, read environment
variables, construct repositories, or traverse the live command tree.
"""

from __future__ import annotations

from functools import lru_cache

from ...core import BindingSourceKind
from ...core.i18n import tr
from ...core.logging import get_logger
from ._errors import OperatorSurfaceContractError
from ._models import (
    FilingStatus,
    LifecycleContract,
    ModeloLifecycleStep,
    MountedCommandDomain,
    MountedCommandFamily,
    OperatorMutability,
    OperatorSurfaceContract,
    OperatorSurfaceLogFields,
    RootSurface,
    RootSurfaceName,
    ServiceOwner,
    SourceKindAlias,
)

LOGGER = get_logger(__name__)

ACCEPTED_ROOTS: tuple[RootSurface, ...] = (
    RootSurface(
        name=RootSurfaceName.CONFIG,
        purpose="profile lifecycle, bucket lifecycle, first-run state, auth, diagnostics, and durable configuration",
        owns_storage_maintenance=True,
        owns_operational_workflow=False,
        required_children=(
            "profile",
            "lock",
            "switch",
            "rekey",
            "recover",
            "show-recovery",
            "verify-recovery",
            "auth",
            "repair",
            "check",
            "google",
            "reset",
        ),
    ),
    RootSurface(
        name=RootSurfaceName.APP,
        purpose="operational tax workflow over the active profile bucket",
        owns_storage_maintenance=False,
        owns_operational_workflow=True,
        required_children=("overview", "ledger", "live", "modelo", "registry", "review", "contract"),
    ),
)

SOURCE_KINDS: tuple[BindingSourceKind, ...] = (
    BindingSourceKind.LEDGER_TRANSACTION,
    BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
    BindingSourceKind.PAYABLE_INVOICE,
    BindingSourceKind.COLLECTIBLE_INVOICE,
)

SOURCE_KIND_ALIASES: tuple[SourceKindAlias, ...] = (
    SourceKindAlias(alias="lt", canonical=BindingSourceKind.LEDGER_TRANSACTION),
    SourceKindAlias(alias="pie", canonical=BindingSourceKind.PURCHASE_INVOICE_EVIDENCE),
    SourceKindAlias(alias="pi", canonical=BindingSourceKind.PAYABLE_INVOICE),
    SourceKindAlias(alias="ci", canonical=BindingSourceKind.COLLECTIBLE_INVOICE),
)

MOUNTED_COMMAND_FAMILIES: tuple[MountedCommandFamily, ...] = (
    MountedCommandFamily(
        domain=MountedCommandDomain.PROFILE,
        root=RootSurfaceName.CONFIG,
        child="profile",
        operator_question="create, inspect, edit, and export profile buckets used by backend workflows",
        service_owner="aeat.application.user_profile",
        commands=(
            "create",
            "edit",
            "list",
            "show",
            "delete",
            "duplicate",
            "rename",
            "export",
            "import",
            "logout",
            "status",
            "censo",
            "history",
            "capabilities",
            "preflight",
            "validate",
        ),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.CUSTODY,
        root=RootSurfaceName.CONFIG,
        child="lock",
        operator_question="seal active profile custody for profile-bound backend workflows",
        service_owner="aeat.application.user_profile",
        commands=("lock",),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.CUSTODY,
        root=RootSurfaceName.CONFIG,
        child="switch",
        operator_question="switch the active taxpayer profile for profile-bound backend workflows",
        service_owner="aeat.application.user_profile",
        commands=("switch",),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.CUSTODY,
        root=RootSurfaceName.CONFIG,
        child="rekey",
        operator_question="rotate profile custody passphrase and recovery wrapping",
        service_owner="aeat.application.user_profile",
        commands=("rekey",),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.CUSTODY,
        root=RootSurfaceName.CONFIG,
        child="recover",
        operator_question="recover profile custody using the printed recovery key",
        service_owner="aeat.application.user_profile",
        commands=("recover",),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.CUSTODY,
        root=RootSurfaceName.CONFIG,
        child="show-recovery",
        operator_question="display custody recovery material through the redacted CLI surface",
        service_owner="aeat.application.user_profile",
        commands=("show-recovery",),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.CUSTODY,
        root=RootSurfaceName.CONFIG,
        child="verify-recovery",
        operator_question="verify printed recovery custody material without rotating secrets",
        service_owner="aeat.application.user_profile",
        commands=("verify-recovery",),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.AUTH,
        root=RootSurfaceName.CONFIG,
        child="auth",
        operator_question="configure and inspect local authentication state for read-only AEAT access",
        service_owner="aeat.application.auth",
        commands=("providers", "configure", "status", "test", "clear", "apoderado", "diagnostics", "login"),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.DIAGNOSTICS,
        root=RootSurfaceName.CONFIG,
        child="repair",
        operator_question="diagnose local configuration, logs, connectivity, and secure-object integrity",
        service_owner="aeat.application.diagnostics",
        commands=("connectivity", "integrity", "quarantine", "reset-progress", "logs", "profile"),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.DIAGNOSTICS,
        root=RootSurfaceName.CONFIG,
        child="check",
        operator_question="check local provisioning readiness and active-profile capability state",
        service_owner="aeat.application.provisioning",
        commands=("check",),
        mutability=OperatorMutability.READ_ONLY,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.GOOGLE,
        root=RootSurfaceName.CONFIG,
        child="google",
        operator_question="configure Google account auth, Drive folder, and worksheet export mirror",
        service_owner="aeat.application.storage",
        commands=("folder", "login", "logout", "register", "status", "sync"),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.DIAGNOSTICS,
        root=RootSurfaceName.CONFIG,
        child="reset",
        operator_question="reset operator-entered local configuration scopes",
        service_owner="aeat.application.config_reset",
        commands=("reset",),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.OVERVIEW,
        root=RootSurfaceName.APP,
        child="overview",
        operator_question="summarize active profile work state and period calendar readiness",
        service_owner="aeat.application.overview",
        commands=("status", "agenda", "backlog", "calendar", "explain"),
        mutability=OperatorMutability.READ_ONLY,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.LEDGER,
        root=RootSurfaceName.APP,
        child="ledger",
        operator_question="ingest and review ledger transactions in the active bucket",
        service_owner="aeat.application.transactions",
        commands=(
            "add",
            "update",
            "classify",
            "allocate",
            "attach",
            "archive",
            "stash",
            "remove",
            "reset",
            "split",
            "merge",
            "link",
            "check",
            "preflight",
            "history",
            "export",
            "list",
            "view",
            "status",
            "track",
            "import",
            "review",
            "ratios",
            "categories",
            "doclink",
            "evidence",
            "inventory",
            "invoice",
            "participation",
            "providers",
            "restore",
            "rule",
        ),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.LIVE,
        root=RootSurfaceName.APP,
        child="live",
        operator_question="perform explicit read-only AEAT live observations",
        service_owner="aeat.application.live",
        commands=(
            "borrador",
            "expedientes",
            FilingStatus.FILED,
            "iva-wallet",
            "justificante",
            "notifications",
            "portals",
            "verify",
        ),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.MODELO,
        root=RootSurfaceName.APP,
        child="modelo",
        operator_question="inspect modelo registry data and manage modelo work units",
        service_owner="aeat.application.modelo",
        commands=(
            "list",
            "describe",
            "casillas",
            "bindings",
            "formulas",
            "work",
            "aggregate",
            "audit",
            "compare",
            "export",
            "filing-record",
            "history",
            "iva-wallet",
            "m036",
            "project",
            "readiness",
            "reconcile",
            "verification-report",
        ),
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.REGISTRY,
        root=RootSurfaceName.APP,
        child="registry",
        operator_question="inspect and verify local registry authority data",
        service_owner="aeat.application.registry",
        commands=(
            "inspect",
            "verify",
            "audit-oracles",
            "verify-filed-state",
            "workbooks",
            "parity",
            "citations",
            "manuals",
        ),
        mutability=OperatorMutability.READ_ONLY,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.REVIEW,
        root=RootSurfaceName.APP,
        child="review",
        operator_question="inspect read-only cross-domain items that need operator attention",
        service_owner="aeat.application.review",
        commands=("queue", "view"),
        mutability=OperatorMutability.READ_ONLY,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.CONTRACT,
        root=RootSurfaceName.APP,
        child="contract",
        operator_question="emit the operator-surface capability manifest the agent harness reads",
        service_owner="aeat.application.operator_surface",
        commands=("contract",),
        mutability=OperatorMutability.READ_ONLY,
    ),
)

SERVICE_OWNERS: tuple[ServiceOwner, ...] = (
    ServiceOwner(
        capability="root_contract",
        owner="aeat.application.operator_surface",
        notes="owns accepted root, lifecycle, and source-kind contract records",
    ),
    ServiceOwner(
        capability="profile_and_bucket_state",
        owner="aeat.application.user_profile",
        notes="owns active profile state consumed by app commands",
    ),
    ServiceOwner(
        capability="bucket_event_history",
        owner="aeat.domain.buckets",
        notes="owns append-only bucket-event history records exposed by config profile history",
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
    ServiceOwner(
        capability="provisioning_readiness",
        owner="aeat.application.provisioning",
        notes="owns local provisioning readiness checked by config check",
    ),
    ServiceOwner(
        capability="google_export_mirror",
        owner="aeat.application.storage",
        notes="owns Google auth, Drive folder, and worksheet export-mirror state for config google",
    ),
    ServiceOwner(
        capability="config_reset",
        owner="aeat.application.config_reset",
        notes="owns the operator-entered configuration scope reset behind config reset",
    ),
)

OperatorSurfaceErrorCodes: tuple[str, ...] = ("REFUSED_OPERATOR_SURFACE_CONTRACT",)


def build_operator_surface_contract() -> OperatorSurfaceContract:
    """Build the immutable :class:`OperatorSurfaceContract`.

    Returns the canonical declaration of modelo lifecycle steps, accepted
    :class:`RootSurface` values, parser-only :class:`SourceKindAlias` records,
    mounted :class:`MountedCommandFamily` values, and backend
    :class:`ServiceOwner` mappings. The resulting
    :class:`OperatorSurfaceLogFields` are emitted through the shared logger as
    stable, non-secret metadata. Consumers that need the singleton view should
    call :func:`get_operator_surface_contract`, which caches this builder.
    """
    lifecycle = LifecycleContract(
        steps=(
            ModeloLifecycleStep.CALCULATE,
            ModeloLifecycleStep.VERIFY,
            ModeloLifecycleStep.FILE,
        ),
    )
    log_fields = OperatorSurfaceLogFields(
        root_count=len(ACCEPTED_ROOTS),
        lifecycle=" -> ".join(step.value for step in lifecycle.steps),
        source_kind_count=len(SOURCE_KINDS),
    )
    contract = OperatorSurfaceContract(
        roots=ACCEPTED_ROOTS,
        lifecycle=lifecycle,
        source_kinds=SOURCE_KINDS,
        source_kind_aliases=SOURCE_KIND_ALIASES,
        command_families=MOUNTED_COMMAND_FAMILIES,
        service_owners=SERVICE_OWNERS,
        log_fields=log_fields,
        error_codes=OperatorSurfaceErrorCodes,
    )
    LOGGER.debug("built operator surface contract", extra=log_fields.as_extra())
    return contract


@lru_cache(maxsize=1)
def get_operator_surface_contract() -> OperatorSurfaceContract:
    """Return the cached backend-owned operator surface contract.

    Returns the :class:`OperatorSurfaceContract` describing the accepted
    root surfaces, source-kind aliases, command families, service owners, log
    fields, and registered error-code contract. The cache guarantees every
    application and adapter consumer observes the same immutable contract object
    for the current process.
    """
    return build_operator_surface_contract()


def require_accepted_root(name: str) -> RootSurface:
    """Return the :class:`RootSurface` for an accepted root.

    Raises :class:`OperatorSurfaceContractError` when ``name`` is outside the
    backend-owned root contract. The refusal carries localized reason and
    suggestion text, while the accepted path returns the exact
    :class:`RootSurface` record from :func:`get_operator_surface_contract`.
    """
    normalized = name.strip().lower()
    for root in get_operator_surface_contract().roots:
        if root.name.value == normalized:
            return root
    raise OperatorSurfaceContractError(
        normalized or name,
        reason=tr(
            "cli.operator_surface.errors.accepted_roots_only",
            default="accepted operator roots are config and app",
        ),
        suggestion="aeat --help",
    )


def resolve_source_kind_alias(value: str) -> BindingSourceKind:
    """Resolve canonical source kinds and parser-only aliases.

    Returns a canonical :class:`BindingSourceKind` from either the enum token
    itself or an input-only :class:`SourceKindAlias`. The accepted set is the
    :data:`SOURCE_KINDS` subset, and aliases in :data:`SOURCE_KIND_ALIASES`
    never introduce an operator-only source-kind taxonomy.
    """
    normalized = value.strip().lower()
    for source_kind in SOURCE_KINDS:
        if source_kind.value == normalized:
            return source_kind
    for alias in SOURCE_KIND_ALIASES:
        if alias.alias == normalized:
            return alias.canonical
    raise OperatorSurfaceContractError(
        value,
        reason=tr("cli.operator_surface.errors.unknown_source_kind", kind=value),
        suggestion=tr(
            "cli.operator_surface.errors.source_kind_options",
            options=", ".join(source_kind.value for source_kind in SOURCE_KINDS),
        ),
    )
