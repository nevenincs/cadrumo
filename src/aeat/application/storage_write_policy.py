"""Runtime write-policy decisions for operator command dispatch."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from ..core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..core.config import Settings, StorageRouteKind, classify_storage_route
from ..core.i18n import tr


class StorageWritePolicyCode(StrEnum):
    """Machine-readable runtime write-policy outcomes."""

    ALLOWED_ACTIVE_BUCKET = "allowed_active_bucket"
    BOOTSTRAP_EXEMPT = "bootstrap_exempt"
    NON_PROFILE_BOUND_VERB = "non_profile_bound_verb"
    NO_VERB_PATH = "no_verb_path"
    REFUSED_ROOT_FALLBACK = "refused_root_fallback"
    REFUSED_EXPLICIT_DATABASE_URL = "refused_explicit_database_url"


class StorageWritePolicyDecision(BaseModel):
    """Decision returned by the backend storage write-policy query."""

    model_config = _STRICT_FROZEN

    allowed: bool
    code: StorageWritePolicyCode
    profile_bound_write: bool
    bootstrap_exempt: bool
    route_kind: StorageRouteKind | None = None
    message_key: str = ""
    detail_message_key: str = ""

    def render_refusal_message(self, *, locale: str | None = None) -> str:
        """Render the translated user-facing refusal message."""
        if self.allowed or not self.message_key:
            return ""
        if self.detail_message_key:
            return tr(self.message_key, details=tr(self.detail_message_key, locale=locale), locale=locale)
        return tr(self.message_key, locale=locale)


PROFILE_BOUND_WRITE_VERB_PATHS: tuple[str, ...] = (
    "app ledger add",
    "app ledger update",
    "app ledger classify",
    "app ledger allocate",
    "app ledger attach",
    "app ledger archive",
    "app ledger stash",
    "app ledger remove",
    "app ledger reset",
    "app ledger split",
    "app ledger merge",
    "app ledger link",
    "app ledger track",
    "app ledger export",
    "app ledger import",
    "app ledger rule add",
    "app ledger rule apply",
    "app ledger ratios set",
    "app ledger ratios unset",
    "app ledger payable-invoice add",
    "app ledger payable-invoice update",
    "app ledger payable-invoice remove",
    "app ledger collectible-invoice add",
    "app ledger collectible-invoice update",
    "app ledger collectible-invoice remove",
    "app ledger inventory create",
    "app ledger inventory movement add",
    "app ledger inventory valuation preview",
    "app ledger evidence add",
    "app ledger evidence update",
    "app ledger evidence remove",
    "app live iva-wallet pull",
    "app live iva-wallet pull-history",
    "app live filed pull",
    "app live filed pull-sources",
    "app live notifications pull",
    "app live expedientes pull",
    "app live verify nif-iva",
    "app live verify tgvi",
    "app modelo work create",
    "app modelo work rename",
    "app modelo work discard",
    "app modelo work calculate",
    "app modelo work verify",
    "app modelo work file",
    "app modelo work amend",
    "app modelo filing-record import",
    "app modelo reconcile",
    "app modelo export",
    "config auth configure",
    "config auth login",
    "config auth clear",
    "config auth diagnostics report",
    "config auth apoderado configure",
    "config auth apoderado clear",
    "config google register",
    "config google login",
    "config google logout",
    "config google folder set",
    "config google sync push",
    "config google sync calc pull",
    "config profile edit",
    "config profile censo pull",
    "config profile censo apply",
    "config profile delete",
    "config profile duplicate",
    "config profile rename",
    "config reset",
)


def inspect_storage_write_policy(
    verb_path: str | None,
    *,
    bootstrap_exempt: bool,
    settings: Settings | None = None,
) -> StorageWritePolicyDecision:
    """Return whether ``verb_path`` may perform profile-bound writes.

    Returns a :class:`StorageWritePolicyDecision` with the allow/deny
    verdict and the policy code that determined it.
    """
    if bootstrap_exempt:
        return StorageWritePolicyDecision(
            allowed=True,
            code=StorageWritePolicyCode.BOOTSTRAP_EXEMPT,
            profile_bound_write=False,
            bootstrap_exempt=True,
        )
    if verb_path is None:
        return StorageWritePolicyDecision(
            allowed=True,
            code=StorageWritePolicyCode.NO_VERB_PATH,
            profile_bound_write=False,
            bootstrap_exempt=False,
        )
    if not is_profile_bound_write_verb_path(verb_path):
        return StorageWritePolicyDecision(
            allowed=True,
            code=StorageWritePolicyCode.NON_PROFILE_BOUND_VERB,
            profile_bound_write=False,
            bootstrap_exempt=False,
        )

    route = classify_storage_route(settings)
    if route.kind is StorageRouteKind.ROOT_FALLBACK_DATABASE:
        return StorageWritePolicyDecision(
            allowed=False,
            code=StorageWritePolicyCode.REFUSED_ROOT_FALLBACK,
            profile_bound_write=True,
            bootstrap_exempt=False,
            route_kind=route.kind,
            message_key="cli.config.errors.no_active_profile",
        )
    if route.kind is StorageRouteKind.EXPLICIT_DATABASE_URL:
        return StorageWritePolicyDecision(
            allowed=False,
            code=StorageWritePolicyCode.REFUSED_EXPLICIT_DATABASE_URL,
            profile_bound_write=True,
            bootstrap_exempt=False,
            route_kind=route.kind,
            message_key="errors.storage.runtime.not_ready",
            detail_message_key="errors.storage.runtime.route_not_active_bucket",
        )
    return StorageWritePolicyDecision(
        allowed=True,
        code=StorageWritePolicyCode.ALLOWED_ACTIVE_BUCKET,
        profile_bound_write=True,
        bootstrap_exempt=False,
        route_kind=route.kind,
    )


def is_profile_bound_write_verb_path(verb_path: str) -> bool:
    """Return whether ``verb_path`` names a profile-bound mutation surface."""
    normalised = verb_path.strip()
    return any(
        normalised == guarded or normalised.startswith(f"{guarded} ") for guarded in PROFILE_BOUND_WRITE_VERB_PATHS
    )


__all__ = [
    "PROFILE_BOUND_WRITE_VERB_PATHS",
    "StorageWritePolicyCode",
    "StorageWritePolicyDecision",
    "inspect_storage_write_policy",
    "is_profile_bound_write_verb_path",
]
