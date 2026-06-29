"""Runtime write-policy decisions for operator command dispatch.

The CLI root asks :func:`inspect_storage_write_policy` before opening
profile-bound storage. The returned :class:`StorageWritePolicyDecision`
combines the matched :class:`StorageWritePolicyCode` with the
:class:`StorageRouteKind` derived from :class:`Settings`.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel

from ..core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..core import Modelo, read_pointer
from ..core.config import (
    Settings,
    StorageRouteClassification,
    StorageRouteKind,
    classify_storage_route,
    load_settings,
    settings_for_active_profile_bucket,
)
from ..core.i18n import tr


class StorageWritePolicyCode(StrEnum):
    """Machine-readable runtime write-policy outcomes."""

    ALLOWED_ACTIVE_BUCKET = "allowed_active_bucket"
    BOOTSTRAP_EXEMPT = "bootstrap_exempt"
    LEAF_REFUSAL_DELEGATED = "leaf_refusal_delegated"
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
    "config google sync calc compute",
    "config profile censo pull",
    "config profile censo apply",
    "config reset",
)


def inspect_storage_write_policy(
    verb_path: str | None,
    *,
    bootstrap_exempt: bool,
    settings: Settings | None = None,
    argv_tokens: Sequence[str] | None = None,
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
    if _delegates_to_leaf_refusal(verb_path, argv_tokens, settings):
        return StorageWritePolicyDecision(
            allowed=True,
            code=StorageWritePolicyCode.LEAF_REFUSAL_DELEGATED,
            profile_bound_write=True,
            bootstrap_exempt=False,
        )

    route = _classify_effective_write_route(settings)
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


def _classify_effective_write_route(settings: Settings | None) -> StorageRouteClassification:
    resolved = settings or load_settings()
    route = classify_storage_route(resolved)
    if route.kind is StorageRouteKind.ROOT_FALLBACK_DATABASE and "aeat_database_url" not in resolved.model_fields_set:
        pointer = read_pointer(resolved.aeat_local_storage_root)
        if pointer is not None:
            return classify_storage_route(settings_for_active_profile_bucket(pointer.bucket_id, resolved))
    return route


def _delegates_to_leaf_refusal(
    verb_path: str,
    argv_tokens: Sequence[str] | None,
    settings: Settings | None,
) -> bool:
    normalised = verb_path.strip()
    if normalised != "app modelo work create" and not normalised.startswith("app modelo work create "):
        return False
    modelo = _option_value(argv_tokens or (), "--modelo")
    if modelo is None:
        return False
    from .modelo._work_create_policy import STUB_ONLY_MODELOS

    modelo_code = modelo.strip()
    if modelo_code not in STUB_ONLY_MODELOS:
        return False
    resolved = settings or load_settings()
    return modelo_code != Modelo.M210 or not resolved.aeat_m210_engine_live


def _option_value(argv_tokens: Sequence[str], option: str) -> str | None:
    prefix = f"{option}="
    for index, token in enumerate(argv_tokens):
        if token.startswith(prefix):
            value = token[len(prefix) :].strip()
            return value or None
        if token == option and index + 1 < len(argv_tokens):
            value = argv_tokens[index + 1].strip()
            return value or None
    return None


__all__ = [
    "PROFILE_BOUND_WRITE_VERB_PATHS",
    "StorageWritePolicyCode",
    "StorageWritePolicyDecision",
    "inspect_storage_write_policy",
    "is_profile_bound_write_verb_path",
]
