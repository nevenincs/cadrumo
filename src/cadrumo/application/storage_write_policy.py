"""Runtime write-policy decisions for operator command dispatch.

The CLI root asks :func:`inspect_storage_write_policy` before opening
profile-bound storage. The returned :class:`StorageWritePolicyDecision`
combines the matched :class:`StorageWritePolicyCode` with the
:class:`~cadrumo.core.config.StorageRouteKind` derived from
:class:`~cadrumo.core.config.Settings`.

This module is the application-side route query, not the session opener.
The CLI callback's attached execution policy supplies the write-route scope;
this query refuses profile-bound mutations when storage is routed to the
root fallback database or to an explicit ``CADRUMO_DATABASE_URL``. A stale
settings object with a valid active-profile pointer is reclassified through
:func:`~cadrumo.core.config.settings_for_active_profile_bucket` so the root
callback sees the same active-bucket route the storage runtime would use.

See Also:
    :mod:`cadrumo.entrypoints.cli`
        Root command callback that resolves callback policy, consults this
        policy, and opens active bucket sessions only after the policy allows
        dispatch.
    :func:`cadrumo.core.config.classify_storage_route`
        Produces the :class:`~cadrumo.core.config.StorageRouteClassification`
        inspected for guarded mutation paths.
    :mod:`cadrumo.application.operator_actions`
        Canonical failed-condition, evidence, action, and no-recovery records
        returned for write-policy refusals.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, model_validator

from ..core import (
    STORAGE_ROOT_SETTINGS_FIELD,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ..core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..core.config import (
    Settings,
    StorageRouteClassification,
    StorageRouteKind,
    classify_storage_route,
    load_settings,
    settings_for_active_profile_bucket,
)
from ..core.i18n import tr
from .operator_actions import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
    PreconditionVerdict,
    no_action_precondition_verdict,
)


class StorageWritePolicyCode(StrEnum):
    """Machine-readable outcomes from the root write-policy query.

    The values distinguish allowed active-bucket writes, state-free or
    bootstrap-root paths, and the two route-level
    denials the CLI root must stop before opening profile storage. Each value
    is carried in the ``code`` field of :class:`StorageWritePolicyDecision`,
    returned from :func:`inspect_storage_write_policy`.
    """

    ALLOWED_ACTIVE_BUCKET = "allowed_active_bucket"
    BOOTSTRAP_EXEMPT = "bootstrap_exempt"
    NON_PROFILE_BOUND_VERB = "non_profile_bound_verb"
    REFUSED_ROOT_FALLBACK = "refused_root_fallback"
    REFUSED_EXPLICIT_DATABASE_URL = "refused_explicit_database_url"


class StorageWritePolicyCondition(StrEnum):
    """Stable failed-condition identities owned by the write policy."""

    PROFILE_ACTIVE = "profile.active"
    ACTIVE_BUCKET_ROUTE = "storage.route.active_bucket"


class StorageWritePolicyEvidence(StrEnum):
    """Stable evidence identities emitted for write-policy failures."""

    PROFILE_STORAGE_ROUTE = "profile.active.storage_route"
    ACTIVE_BUCKET_ROUTE_CLASSIFICATION = "storage.route.active_bucket.classification"


class StorageWritePolicyDecision(BaseModel):
    """Decision returned by the backend storage write-policy query.

    The CLI root converts refusing decisions into
    :class:`~cadrumo.entrypoints.cli._errors.CliRefusedBoundaryError` instances;
    allowed decisions let dispatch continue toward the active-bucket session
    opener.

    Attributes:
        allowed: Whether root dispatch may continue.
        code: The :class:`StorageWritePolicyCode` that determined the result.
        profile_bound_write: Whether callback policy declares a profile-bound
            storage write route.
        bootstrap_exempt: Whether callback policy declares a bootstrap-root
            write route that is permitted before an active bucket exists.
        route_kind: Effective :class:`~cadrumo.core.config.StorageRouteKind` for
            guarded writes, or ``None`` when no route was inspected.
        message_key: Locale key for a refusal message rendered at the CLI
            boundary.
        detail_message_key: Optional nested detail key for the refusal message.
        verdict: Typed failed-condition outcome for a refusal. Allowed decisions
            never carry a failed verdict.
    """

    model_config = _STRICT_FROZEN

    allowed: bool
    code: StorageWritePolicyCode
    profile_bound_write: bool
    bootstrap_exempt: bool
    route_kind: StorageRouteKind | None = None
    message_key: str = ""
    detail_message_key: str = ""
    verdict: PreconditionVerdict | None = None

    @model_validator(mode="after")
    def _verdict_matches_decision(self) -> StorageWritePolicyDecision:
        """Require a verdict exactly when the write policy refuses dispatch."""
        if self.allowed and self.verdict is not None:
            raise ValueError("allowed storage write-policy decisions cannot carry a failed verdict")
        if not self.allowed and self.verdict is None:
            raise ValueError("refusing storage write-policy decisions require a failed verdict")
        return self

    def render_refusal_message(self, *, locale: str | None = None) -> str:
        """Render the translated user-facing refusal message through :func:`~cadrumo.core.i18n.tr`."""
        if self.allowed or not self.message_key:
            return ""
        if self.detail_message_key:
            return tr(self.message_key, details=tr(self.detail_message_key, locale=locale), locale=locale)
        return tr(self.message_key, locale=locale)


def inspect_storage_write_policy(
    write_route: str,
    *,
    settings: Settings | None = None,
) -> StorageWritePolicyDecision:
    """Return whether a callback's declared route may perform storage writes.

    Bootstrap-root and non-profile-bound policies are allowed without route
    inspection. Guarded mutation paths are allowed only when the effective
    storage route is an active bucket; root fallback and explicit database
    routes return refusing :class:`StorageWritePolicyDecision` values before
    the CLI opens a bucket session. The effective route comes from
    :class:`~cadrumo.core.config.StorageRouteClassification` so root dispatch does
    not duplicate storage-routing logic.

    Unknown values fail closed. The caller obtains the value from validated,
    CommandSpec-owned policy rather than reconstructing a command path.
    """
    if write_route == "bootstrap-root":
        return StorageWritePolicyDecision(
            allowed=True,
            code=StorageWritePolicyCode.BOOTSTRAP_EXEMPT,
            profile_bound_write=False,
            bootstrap_exempt=True,
        )
    if write_route == "none":
        return StorageWritePolicyDecision(
            allowed=True,
            code=StorageWritePolicyCode.NON_PROFILE_BOUND_VERB,
            profile_bound_write=False,
            bootstrap_exempt=False,
        )
    if write_route != "profile-bound":
        raise ValueError(f"unknown command write-route scope: {write_route}")

    route = _classify_effective_write_route(settings)
    if route.kind is StorageRouteKind.ROOT_FALLBACK_DATABASE:
        return StorageWritePolicyDecision(
            allowed=False,
            code=StorageWritePolicyCode.REFUSED_ROOT_FALLBACK,
            profile_bound_write=True,
            bootstrap_exempt=False,
            route_kind=route.kind,
            message_key="cli.config.errors.no_active_profile",
            verdict=_missing_active_profile_verdict(route),
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
            verdict=_explicit_database_route_verdict(route),
        )
    return StorageWritePolicyDecision(
        allowed=True,
        code=StorageWritePolicyCode.ALLOWED_ACTIVE_BUCKET,
        profile_bound_write=True,
        bootstrap_exempt=False,
        route_kind=route.kind,
    )


def _missing_active_profile_verdict(route: StorageRouteClassification) -> PreconditionVerdict:
    """Return the conditional profile-creation action for a cold-root write."""
    condition_id = StorageWritePolicyCondition.PROFILE_ACTIVE.value
    evidence_id = StorageWritePolicyEvidence.PROFILE_STORAGE_ROUTE.value
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            ConditionEvidence(
                condition_id=condition_id,
                evidence_id=evidence_id,
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                values={
                    "active_bucket_attached": False,
                    "active_profile_present": False,
                    "route_kind": route.kind.value,
                },
            ),
        ),
        action=ActionReference(action_id="operator.profile.create"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name="profile_name",
                status=ActionArgumentStatus.MISSING,
            ),
        ),
        missing_argument_names=("profile_name",),
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )


def _explicit_database_route_verdict(route: StorageRouteClassification) -> PreconditionVerdict:
    """Return the closed outcome for an operator-owned database URL override."""
    condition_id = StorageWritePolicyCondition.ACTIVE_BUCKET_ROUTE.value
    return no_action_precondition_verdict(
        condition_id=condition_id,
        evidence_id=StorageWritePolicyEvidence.ACTIVE_BUCKET_ROUTE_CLASSIFICATION.value,
        facts={
            "active_bucket_attached": False,
            "database_url_explicit": True,
            "explicit_route_setting": _settings_environment_name("cadrumo_database_url"),
            "route_kind": route.kind.value,
            "storage_root_setting": _settings_environment_name(STORAGE_ROOT_SETTINGS_FIELD),
        },
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def _settings_environment_name(field_name: str) -> str:
    """Resolve a settings field to the real environment identity or fail."""
    environment_name = field_name.upper()
    if field_name not in Settings.model_fields or environment_name not in Settings.env_var_names():
        raise RuntimeError(f"settings field has no environment authority: {field_name}")
    return environment_name


def _classify_effective_write_route(settings: Settings | None) -> StorageRouteClassification:
    """Return the effective storage route for a guarded write decision.

    A non-explicit root fallback route can still represent stale settings
    captured before the active-profile pointer was read. When a pointer exists,
    reclassify with
    :func:`~cadrumo.core.config.settings_for_active_profile_bucket` so guarded
    writes follow the active bucket route instead of being refused as cold-root
    writes.
    """
    resolved = settings or load_settings()
    route = classify_storage_route(resolved)
    if (
        route.kind is StorageRouteKind.ROOT_FALLBACK_DATABASE
        and "cadrumo_database_url" not in resolved.model_fields_set
    ):
        from .user_profile.profile_pointer import observe_active_profile_pointer

        pointer = observe_active_profile_pointer(resolved.cadrumo_local_storage_root)
        if pointer.bucket_id is not None:
            return classify_storage_route(settings_for_active_profile_bucket(pointer.bucket_id, resolved))
    return route


__all__ = [
    "StorageWritePolicyCode",
    "StorageWritePolicyCondition",
    "StorageWritePolicyDecision",
    "StorageWritePolicyEvidence",
    "inspect_storage_write_policy",
]
