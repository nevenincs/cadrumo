"""Application-owned operator surface contract for the CLI workflow redesign."""

from __future__ import annotations

from functools import lru_cache

from ...core.logging import get_logger
from ._errors import OperatorSurfaceContractError
from ._models import (
    LifecycleContract,
    ModeloLifecycleStep,
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
        required_children=("init", "profile", "auth", "doctor", "bucket"),
    ),
    RootSurface(
        name=RootSurfaceName.APP,
        purpose="operational tax workflow over the active profile bucket",
        owns_storage_maintenance=False,
        owns_operational_workflow=True,
        required_children=("overview", "ledger", "modelo", "live", "registry", "review"),
    ),
)

RETIRED_OPERATOR_SURFACES: tuple[RetiredOperatorSurface, ...] = (
    RetiredOperatorSurface(
        name="setup",
        replacement="config",
        suggestion="aeat config init",
        reason="setup and config are consolidated under the config root",
    ),
    RetiredOperatorSurface(
        name="archive",
        replacement="config bucket",
        suggestion="aeat config bucket",
        reason="bucket storage operations belong under config",
    ),
    RetiredOperatorSurface(
        name="data",
        replacement="app ledger",
        suggestion="aeat app ledger",
        reason="ledger data operations belong under the app ledger workflow",
    ),
    RetiredOperatorSurface(
        name="deadlines",
        replacement="app overview",
        suggestion="aeat app overview",
        reason="deadline and calendar signals are absorbed by app overview",
    ),
    RetiredOperatorSurface(
        name="browser",
        replacement="config doctor connectivity",
        suggestion="aeat config doctor connectivity",
        reason="browser/site-health diagnostics belong under config doctor",
    ),
    RetiredOperatorSurface(
        name="filing",
        replacement="app modelo",
        suggestion="aeat app modelo",
        reason="modelo lifecycle is calculate -> verify -> file under app modelo",
    ),
    RetiredOperatorSurface(
        name="financial",
        replacement="app ledger",
        suggestion="aeat app ledger",
        reason="financial transaction work is ledger work",
    ),
    RetiredOperatorSurface(
        name="invoice",
        replacement="app ledger",
        suggestion="aeat app ledger",
        reason="bare invoice terminology is replaced by the source-kind taxonomy",
    ),
    RetiredOperatorSurface(
        name="declaration",
        replacement="app modelo",
        suggestion="aeat app modelo",
        reason="declaration behavior folds into modelo work units and revisions",
    ),
    RetiredOperatorSurface(
        name="sanitize",
        replacement="app ledger",
        suggestion="aeat app ledger check",
        reason="sanitization is internal to ledger ingestion",
    ),
    RetiredOperatorSurface(
        name="llm",
        replacement=None,
        suggestion="aeat app ledger classify",
        reason="classification is exposed only through ledger services",
    ),
    RetiredOperatorSurface(
        name="topic",
        replacement="app registry",
        suggestion="aeat app registry citations",
        reason="topic content folds into registry citations and inline help",
    ),
    RetiredOperatorSurface(
        name="submit",
        replacement=None,
        suggestion=None,
        reason="live submission is permanently disabled",
    ),
    RetiredOperatorSurface(
        name="presentation",
        replacement="app modelo export",
        suggestion="aeat app modelo export",
        reason="presentation artifacts are modelo exports",
    ),
    RetiredOperatorSurface(
        name="preflight",
        replacement="app modelo verify",
        suggestion="aeat app modelo verify",
        reason="preflight is internal to verify and file",
    ),
    RetiredOperatorSurface(
        name="workflow",
        replacement="app modelo",
        suggestion="aeat app modelo",
        reason="workflow execution is exposed through domain mini-apps",
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

SERVICE_OWNERS: tuple[ServiceOwner, ...] = (
    ServiceOwner(
        capability="root_contract",
        owner="aeat.application.operator_surface",
        notes="owns accepted root, retired surface, lifecycle, and source-kind contract records",
    ),
    ServiceOwner(
        capability="profile_and_bucket_state",
        owner="aeat.application.profile",
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
    """Build the immutable operator surface contract from accepted ADR decisions."""

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
    reason = retired.reason if retired is not None else "accepted roots are config and app"
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
        reason="unknown source kind",
        suggestion="use ledger_transaction, purchase_invoice_evidence, payable_invoice, or collectible_invoice",
    )
