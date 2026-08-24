"""Application-owned operator-surface contract for the workflow redesign.

This module declares the accepted :class:`RootSurface` records, canonical
:class:`~cadrumo.core.BindingSourceKind` subset, parser-only
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
from ._errors import OperatorSurfaceContractError, operator_surface_contract_verdict
from ._models import (
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
            "login",
            "logout",
            "passphrase",
            "auth",
            "repair",
            "check",
            "provision",
            "storage",
            "google",
            "reset",
            "collab",
        ),
    ),
    RootSurface(
        name=RootSurfaceName.APP,
        purpose="operational tax workflow over the active profile bucket",
        owns_storage_maintenance=False,
        owns_operational_workflow=True,
        required_children=(
            "overview",
            "ledger",
            "live",
            "modelo",
            "registry",
            "review",
            "quickfile",
            "diagnostics",
            "maintenance",
        ),
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
        service_owner="cadrumo.application.user_profile",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.CUSTODY,
        root=RootSurfaceName.CONFIG,
        child="login",
        operator_question="authenticate a taxpayer profile and start a resumable session",
        service_owner="cadrumo.application.user_profile",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.CUSTODY,
        root=RootSurfaceName.CONFIG,
        child="logout",
        operator_question="close the active taxpayer profile session and clear its pointer",
        service_owner="cadrumo.application.user_profile",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.CUSTODY,
        root=RootSurfaceName.CONFIG,
        child="passphrase",
        operator_question="rotate the profile custody passphrase after verifying the current one",
        service_owner="cadrumo.application.user_profile",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.AUTH,
        root=RootSurfaceName.CONFIG,
        child="auth",
        operator_question="configure and inspect local authentication state for read-only AEAT access",
        service_owner="cadrumo.application.auth",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.DIAGNOSTICS,
        root=RootSurfaceName.CONFIG,
        child="repair",
        operator_question="diagnose local configuration, logs, connectivity, and secure-object integrity",
        service_owner="cadrumo.application.diagnostics",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.DIAGNOSTICS,
        root=RootSurfaceName.CONFIG,
        child="check",
        operator_question="check local provisioning readiness and active-profile capability state",
        service_owner="cadrumo.application.provisioning",
        mutability=OperatorMutability.READ_ONLY,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.PROVISIONING,
        root=RootSurfaceName.CONFIG,
        child="provision",
        operator_question=(
            "report local model provisioning readiness and explicitly pull or verify a local inference model"
        ),
        service_owner="cadrumo.application.provisioning",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.STORAGE,
        root=RootSurfaceName.CONFIG,
        child="storage",
        operator_question="report where local data lives and reclaim what a category's lifecycle says is regenerable",
        service_owner="cadrumo.application.storage_management",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.GOOGLE,
        root=RootSurfaceName.CONFIG,
        child="google",
        operator_question="configure Google account auth, Drive folder, and worksheet export mirror",
        service_owner="cadrumo.application.storage",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.DIAGNOSTICS,
        root=RootSurfaceName.CONFIG,
        child="reset",
        operator_question="start, inspect, or resume the durable all-profile configuration reset",
        service_owner="cadrumo.application.config_reset",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.COLLAB,
        root=RootSurfaceName.CONFIG,
        child="collab",
        operator_question="register trusted review-package recipients by verified public-key fingerprint",
        service_owner="cadrumo.application.modelo",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.OVERVIEW,
        root=RootSurfaceName.APP,
        child="overview",
        operator_question="summarize active profile work state and period calendar readiness",
        service_owner="cadrumo.application.overview",
        mutability=OperatorMutability.READ_ONLY,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.LEDGER,
        root=RootSurfaceName.APP,
        child="ledger",
        operator_question="ingest and review ledger transactions in the active bucket",
        service_owner="cadrumo.application.transactions",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.LIVE,
        root=RootSurfaceName.APP,
        child="live",
        operator_question="perform explicit read-only AEAT live observations",
        service_owner="cadrumo.application.live",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.MODELO,
        root=RootSurfaceName.APP,
        child="modelo",
        operator_question="inspect modelo registry data and manage modelo work units",
        service_owner="cadrumo.application.modelo",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.REGISTRY,
        root=RootSurfaceName.APP,
        child="registry",
        operator_question="inspect and verify local registry authority data",
        service_owner="cadrumo.application.registry",
        mutability=OperatorMutability.READ_ONLY,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.REVIEW,
        root=RootSurfaceName.APP,
        child="review",
        operator_question="inspect read-only cross-domain items that need operator attention",
        service_owner="cadrumo.application.review",
        mutability=OperatorMutability.READ_ONLY,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.QUICKFILE,
        root=RootSurfaceName.APP,
        child="quickfile",
        operator_question=(
            "run the full local modelo filing chain (readiness, calculate, verify, export) in one command"
        ),
        service_owner="cadrumo.application.modelo",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.DIAGNOSTICS,
        root=RootSurfaceName.APP,
        child="diagnostics",
        operator_question=(
            "report recent local LLM run health, latency, errors, and usage over the active "
            "bucket; inspect and control the opt-in remote telemetry consent level"
        ),
        service_owner="cadrumo.application.diagnostics_run_health",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    MountedCommandFamily(
        domain=MountedCommandDomain.MAINTENANCE,
        root=RootSurfaceName.APP,
        child="maintenance",
        operator_question=(
            "recover local state an interrupted operation left behind, including a "
            "profile-bundle export whose crash left an unencrypted staged file on disk"
        ),
        service_owner="cadrumo.application.user_profile",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
)

SERVICE_OWNERS: tuple[ServiceOwner, ...] = (
    ServiceOwner(
        capability="root_contract",
        owner="cadrumo.application.operator_surface",
        notes="owns accepted root, lifecycle, and source-kind contract records",
    ),
    ServiceOwner(
        capability="profile_and_bucket_state",
        owner="cadrumo.application.user_profile",
        notes="owns active profile state consumed by app commands",
    ),
    ServiceOwner(
        capability="bucket_event_history",
        owner="cadrumo.domain.buckets",
        notes="owns append-only bucket-event history records exposed by config profile history",
    ),
    ServiceOwner(
        capability="workflow_state",
        owner="cadrumo.application.workflow",
        notes="owns profile read path and workflow state repository access",
    ),
    ServiceOwner(
        capability="modelo_lifecycle",
        owner="cadrumo.application.filing",
        notes=(
            "owns calculate, verify, file, amend, reconcile, history, and export behavior "
            "until modelo services split out"
        ),
    ),
    ServiceOwner(
        capability="ledger_transactions",
        owner="cadrumo.application.transactions",
        notes="owns ledger import and transaction diagnostics until ledger services split out",
    ),
    ServiceOwner(
        capability="review_queue",
        owner="cadrumo.application.review",
        notes="owns operator review items and edits across source domains",
    ),
    ServiceOwner(
        capability="provisioning_readiness",
        owner="cadrumo.application.provisioning",
        notes="owns local provisioning readiness checked by config check",
    ),
    ServiceOwner(
        capability="google_export_mirror",
        owner="cadrumo.application.storage",
        notes="owns Google auth, Drive folder, and worksheet export-mirror state for config google",
    ),
    ServiceOwner(
        capability="config_reset",
        owner="cadrumo.application.config_reset",
        notes="owns the durable all-profile reset lifecycle (start, status, resume) behind config reset",
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
    LOGGER.debug("built operator surface contract", extra=log_fields.as_extra().for_logging())
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
    backend-owned root contract. The refusal carries localized reason text,
    while the accepted path returns the exact
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
        precondition_verdict=operator_surface_contract_verdict(
            "operator_surface.accepted_root",
            facts={"requested_root": normalized or name},
        ),
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
        reason=tr(
            "cli.operator_surface.errors.unknown_source_kind",
            kind=value,
            options=", ".join(source_kind.value for source_kind in SOURCE_KINDS),
        ),
        precondition_verdict=operator_surface_contract_verdict(
            "operator_surface.source_kind_alias",
            facts={"requested_source_kind": value},
        ),
    )
