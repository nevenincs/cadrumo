"""Neutral profile-session route and resume authority for parsed dispatch."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib import import_module
from typing import Any

import typer

from ...core import ProfileSessionRefusalReason
from ._command_spec import CommandSpec, ProfileAuthenticationPosture

CliRefusedBoundaryError = import_module(
    "cadrumo.entrypoints.cli._errors"
).CliRefusedBoundaryError

_LOGGED_OUT_REFUSALS = frozenset(
    {ProfileSessionRefusalReason.ABSENT, ProfileSessionRefusalReason.KEYCHAIN_ENTRY_MISSING}
)


def _common() -> Any:
    """Resolve the already-initialized facade without a static runtime cycle."""
    return import_module("cadrumo.entrypoints.cli._common")


def bind_profile_target(ctx: typer.Context, *, bucket_id: str) -> None:
    """Bind one proven profile target as this invocation's storage route."""
    from ...core.config import override_settings

    ctx.with_resource(override_settings(cadrumo_active_profile=bucket_id))


def normalize_ambient_profile(ctx: typer.Context) -> None:
    """Normalize an ambient label pointer to the canonical live bucket UUID."""
    from ...application.workflow import ProfileLabelAmbiguousError, resolve_profile_bucket
    from ...core import resolve_active_bucket_id
    from ...core.config import override_settings
    from ...core.errors import CadrumoError

    active = resolve_active_bucket_id()
    if active is None:
        return
    try:
        pointer = resolve_profile_bucket(active)
    except ProfileLabelAmbiguousError as exc:
        raise CliRefusedBoundaryError(
            translated_message="errors.refused.refused_profile_label_ambiguous"
        ) from exc
    except CadrumoError:
        return
    if pointer is not None:
        ctx.with_resource(override_settings(cadrumo_active_profile=pointer.bucket_id))


def activate_profile_session(
    ctx: typer.Context,
    *,
    posture: ProfileAuthenticationPosture,
    root_selection: object | None,
    leaf_selection: object | None,
    spec: CommandSpec,
    arguments: Mapping[str, object],
    target_bucket_id: str | None,
    command_path: tuple[str, ...],
    authenticate_root: Callable[[str, object, object | None, CommandSpec, Mapping[str, object]], None],
) -> None:
    """Apply write policy and exact-target session proof from parsed authority."""
    from ...adapters.persistence.storage import active_bucket_session_serves
    from ...application.storage_write_policy import inspect_storage_write_policy
    from ...core import resolve_active_bucket_id

    common = _common()
    leaf = common.RequestedCliLeaf(
        subject_leaf_key=spec.result_schema.identity or spec.key,
        canonical_cli_path=command_path,
    )
    policy = spec.policy
    if policy.write_route == "profile-bound":
        from ...core.config import load_settings

        settings = load_settings()
        if target_bucket_id is not None:
            settings = settings.model_copy(update={"cadrumo_active_profile": target_bucket_id})
        write_policy = inspect_storage_write_policy(policy.write_route, settings=settings)
        if not write_policy.allowed:
            if write_policy.verdict is None:
                raise RuntimeError("root write-policy refusal is missing its verdict")
            projection = common.project_cli_policy_refusal(requested_leaf=leaf, verdict=write_policy.verdict)
            raise common.attach_cli_policy_refusal_projection(
                CliRefusedBoundaryError(
                    write_policy.render_refusal_message(),
                    context=common.cli_policy_refusal_context(projection),
                ),
                projection=projection,
            )
    bucket_id = target_bucket_id or resolve_active_bucket_id()
    if bucket_id is None:
        return
    if posture is ProfileAuthenticationPosture.NOT_APPLICABLE:
        return
    if posture is ProfileAuthenticationPosture.SELF_AUTHENTICATING:
        return
    if active_bucket_session_serves(bucket_id):
        if root_selection is not None:
            raise CliRefusedBoundaryError(
                translated_message="cli.config.custody.errors.profile_secrets_unused"
            )
        if target_bucket_id is not None:
            bind_profile_target(ctx, bucket_id=bucket_id)
        return
    _resume_or_authenticate(
        ctx,
        bucket_id=bucket_id,
        root_selection=root_selection,
        leaf_selection=leaf_selection,
        spec=spec,
        arguments=arguments,
        bind_exact_target=target_bucket_id is not None,
        authenticate_root=authenticate_root,
    )
    from ...core.i18n import clear_output_language_cache

    clear_output_language_cache()


def _resume_or_authenticate(
    ctx: typer.Context,
    *,
    bucket_id: str,
    root_selection: object | None,
    leaf_selection: object | None,
    spec: CommandSpec,
    arguments: Mapping[str, object],
    bind_exact_target: bool,
    authenticate_root: Callable[[str, object, object | None, CommandSpec, Mapping[str, object]], None],
) -> None:
    from ...adapters.persistence.storage.errors import KeyringUnavailableError
    from ...application.profile_preconditions import profile_session_failure_verdict
    from ...application.user_profile import bind_resumed_profile_session

    refusal = bind_resumed_profile_session(bucket_id=bucket_id)
    if refusal is None:
        if root_selection is not None:
            raise CliRefusedBoundaryError(
                translated_message="cli.config.custody.errors.profile_secrets_unused"
            )
        if bind_exact_target:
            bind_profile_target(ctx, bucket_id=bucket_id)
        return
    if root_selection is not None:
        authenticate_root(bucket_id, root_selection, leaf_selection, spec, arguments)
        return
    if refusal is ProfileSessionRefusalReason.KEYRING_UNAVAILABLE:
        raise KeyringUnavailableError("OS keychain is unavailable for profile-session acceleration")
    if _interactive_authentication(ctx, bucket_id=bucket_id):
        return
    common = _common()
    verdict = profile_session_failure_verdict(refusal, profile_name=common.active_profile_label() or bucket_id)
    key = (
        "cli.config.errors.profile_session_absent"
        if refusal in _LOGGED_OUT_REFUSALS
        else "cli.config.errors.profile_session_expired"
    )
    raise common.attach_cli_policy_verdict(
        CliRefusedBoundaryError(translated_message=key, context={"reason": refusal.value}),
        verdict=verdict,
        requested_leaf=common.requested_cli_leaf(ctx),
    )


def _interactive_authentication(ctx: typer.Context, *, bucket_id: str) -> bool:
    from ...adapters.persistence.storage import active_bucket_session_serves
    from ...application.user_profile import bind_resumed_profile_session
    login_frontend = import_module("cadrumo.entrypoints.cli._config._login_frontend")
    outcome = login_frontend.offer_login_to_a_gated_verb(ctx, bucket_id=bucket_id)
    if outcome is None or outcome.bucket_id != bucket_id:
        return False
    if bind_resumed_profile_session(bucket_id=bucket_id) is not None:
        return False
    if not active_bucket_session_serves(bucket_id):
        return False
    bind_profile_target(ctx, bucket_id=bucket_id)
    return True


__all__ = ["activate_profile_session", "bind_profile_target", "normalize_ambient_profile"]
