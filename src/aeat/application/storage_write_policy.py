"""Runtime write-policy decisions for operator command dispatch.

The CLI root asks :func:`inspect_storage_write_policy` before opening
profile-bound storage. The returned :class:`StorageWritePolicyDecision`
combines the matched :class:`StorageWritePolicyCode` with the
:class:`~aeat.core.config.StorageRouteKind` derived from
:class:`~aeat.core.config.Settings`.

This module is the application-side policy query, not the session opener.
It classifies the dispatched verb path, honours bootstrap-exempt CLI
surfaces, delegates stub-only Modelo work-create refusals to the leaf
handler, and refuses profile-bound mutations when storage is routed to the
root fallback database or to an explicit ``AEAT_DATABASE_URL``. A stale
settings object with a valid active-profile pointer is reclassified through
:func:`~aeat.core.config.settings_for_active_profile_bucket` so the root
callback sees the same active-bucket route the storage runtime would use.

See Also:
    :mod:`aeat.entrypoints.cli`
        Root command callback that reconstructs verb paths, consults this
        policy, and opens active bucket sessions only after the policy allows
        dispatch.
    :func:`aeat.entrypoints.cli._bootstrap_exempt.is_bootstrap_exempt`
        Supplies the sessionless bootstrap flag passed into
        :func:`inspect_storage_write_policy`.
    :func:`aeat.core.config.classify_storage_route`
        Produces the :class:`~aeat.core.config.StorageRouteClassification`
        inspected for guarded mutation paths.
    :data:`aeat.core.storage_route_guidance.EXPLICIT_DATABASE_URL_PROFILE_RECOVERY`
        Operator recovery text attached to explicit database URL refusals.
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
from ..core.storage_route_guidance import EXPLICIT_DATABASE_URL_PROFILE_RECOVERY


class StorageWritePolicyCode(StrEnum):
    """Machine-readable outcomes from the root write-policy query.

    The values distinguish allowed active-bucket writes, read-only or
    bootstrap-exempt paths, leaf-owned refusals, and the two route-level
    denials the CLI root must stop before opening profile storage. Each value
    is carried in the ``code`` field of :class:`StorageWritePolicyDecision`,
    returned from :func:`inspect_storage_write_policy`.
    """

    ALLOWED_ACTIVE_BUCKET = "allowed_active_bucket"
    BOOTSTRAP_EXEMPT = "bootstrap_exempt"
    LEAF_REFUSAL_DELEGATED = "leaf_refusal_delegated"
    NON_PROFILE_BOUND_VERB = "non_profile_bound_verb"
    NO_VERB_PATH = "no_verb_path"
    REFUSED_ROOT_FALLBACK = "refused_root_fallback"
    REFUSED_EXPLICIT_DATABASE_URL = "refused_explicit_database_url"


class StorageWritePolicyDecision(BaseModel):
    """Decision returned by the backend storage write-policy query.

    The CLI root converts refusing decisions into
    :class:`~aeat.entrypoints.cli._errors.CliRefusedBoundaryError` instances;
    allowed decisions let dispatch continue toward the active-bucket session
    opener.

    Attributes:
        allowed: Whether root dispatch may continue.
        code: The :class:`StorageWritePolicyCode` that determined the result.
        profile_bound_write: Whether the verb path matched the guarded
            profile-bound mutation catalogue.
        bootstrap_exempt: Whether the CLI root classified the invocation as
            bootstrap-exempt before policy inspection.
        route_kind: Effective :class:`~aeat.core.config.StorageRouteKind` for
            guarded writes, or ``None`` when no route was inspected.
        message_key: Locale key for a refusal message rendered at the CLI
            boundary.
        detail_message_key: Optional nested detail key for the refusal message.
        recovery_hint: Structured operator recovery hint for the error envelope.
    """

    model_config = _STRICT_FROZEN

    allowed: bool
    code: StorageWritePolicyCode
    profile_bound_write: bool
    bootstrap_exempt: bool
    route_kind: StorageRouteKind | None = None
    message_key: str = ""
    detail_message_key: str = ""
    recovery_hint: str = ""

    def render_refusal_message(self, *, locale: str | None = None) -> str:
        """Render the translated user-facing refusal message through :func:`~aeat.core.i18n.tr`."""
        if self.allowed or not self.message_key:
            return ""
        if self.detail_message_key:
            return tr(self.message_key, details=tr(self.detail_message_key, locale=locale), locale=locale)
        return tr(self.message_key, locale=locale)

    def refusal_context(self) -> dict[str, str] | None:
        """Return structured context for :class:`~aeat.entrypoints.cli._errors.CliRefusedBoundaryError`."""
        if not self.recovery_hint:
            return None
        return {"recovery": self.recovery_hint}


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
"""Profile-bound mutation verb prefixes guarded by the root write policy.

:func:`is_profile_bound_write_verb_path` matches this catalog by prefix after
the CLI root reconstructs the Typer verb path. The catalog is separate from
:data:`~aeat.entrypoints.cli._bootstrap_exempt.BOOTSTRAP_EXEMPT_VERB_PATHS`:
bootstrap-exempt verbs skip the active-session gate, while these prefixes
identify commands that must be routed through an active profile bucket before
they can mutate profile-bound storage.
"""


def inspect_storage_write_policy(
    verb_path: str | None,
    *,
    bootstrap_exempt: bool,
    settings: Settings | None = None,
    argv_tokens: Sequence[str] | None = None,
) -> StorageWritePolicyDecision:
    """Return whether ``verb_path`` may perform profile-bound writes.

    Bootstrap-exempt and non-profile-bound paths are allowed without route
    inspection. Guarded mutation paths are allowed only when the effective
    storage route is an active bucket; root fallback and explicit database
    routes return refusing :class:`StorageWritePolicyDecision` values before
    the CLI opens a bucket session. The effective route comes from
    :class:`~aeat.core.config.StorageRouteClassification` so root dispatch does
    not duplicate storage-routing logic.

    See Also:
        :data:`PROFILE_BOUND_WRITE_VERB_PATHS`
            Guarded mutation catalog consulted by this policy query.
        :func:`~aeat.entrypoints.cli._bootstrap_exempt.is_bootstrap_exempt`
            Source of the ``bootstrap_exempt`` input from the CLI root.
        :func:`is_profile_bound_write_verb_path`
            Prefix matcher used before route classification.
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
            recovery_hint=EXPLICIT_DATABASE_URL_PROFILE_RECOVERY,
        )
    return StorageWritePolicyDecision(
        allowed=True,
        code=StorageWritePolicyCode.ALLOWED_ACTIVE_BUCKET,
        profile_bound_write=True,
        bootstrap_exempt=False,
        route_kind=route.kind,
    )


def is_profile_bound_write_verb_path(verb_path: str) -> bool:
    """Return whether ``verb_path`` names a profile-bound mutation surface.

    Matching is prefix-based against :data:`PROFILE_BOUND_WRITE_VERB_PATHS`
    so positional arguments appended by Click/Typer reconstruction do not
    hide a guarded operator command.
    """
    normalised = verb_path.strip()
    return any(
        normalised == guarded or normalised.startswith(f"{guarded} ") for guarded in PROFILE_BOUND_WRITE_VERB_PATHS
    )


def _classify_effective_write_route(settings: Settings | None) -> StorageRouteClassification:
    """Return the effective storage route for a guarded write decision.

    A non-explicit root fallback route can still represent stale settings
    captured before the active-profile pointer was read. When a pointer exists,
    reclassify with
    :func:`~aeat.core.config.settings_for_active_profile_bucket` so guarded
    writes follow the active bucket route instead of being refused as cold-root
    writes.
    """
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
    """Return whether a work-create refusal belongs to the modelo leaf handler.

    Stub-only modelos are intentionally allowed past the root route guard so the
    leaf command can emit its specific unsupported-work-create refusal. Modelo
    210 stays root-guarded when the live engine is enabled because that path can
    become a real profile-bound write. The check uses :class:`Modelo` for the
    canonical M210 identifier.
    """
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
    """Return an option value from reconstructed Click/Typer argv tokens."""
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
