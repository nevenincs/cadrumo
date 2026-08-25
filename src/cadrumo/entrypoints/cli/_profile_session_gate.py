"""Neutral profile-session route and resume authority for parsed dispatch."""

from __future__ import annotations

from collections.abc import Mapping
from importlib import import_module
from typing import TYPE_CHECKING, Any, Protocol

import typer

from ...core import ProfileSessionRefusalReason
from ._command_spec import CommandSpec, ProfileAuthenticationPosture

if TYPE_CHECKING:
    from ._common import RequestedCliLeaf
    from ._config._secure_input import MachineSecretSelection, ProfileSecretSelection


class RootAuthenticator(Protocol):
    """Exact callback seam from the neutral session gate to root authentication."""

    def __call__(
        self,
        bucket_id: str,
        root_selection: ProfileSecretSelection,
        leaf_selection: MachineSecretSelection | None,
        spec: CommandSpec,
        arguments: Mapping[str, object],
    ) -> None: ...


CliRefusedBoundaryError = import_module("cadrumo.entrypoints.cli._errors").CliRefusedBoundaryError

_LOGGED_OUT_REFUSALS = frozenset(
    {ProfileSessionRefusalReason.ABSENT, ProfileSessionRefusalReason.KEYCHAIN_ENTRY_MISSING}
)


def session_refusal_translation_key(refusal: ProfileSessionRefusalReason) -> str:
    """Map every typed resume refusal to its stable operator diagnostic."""
    return (
        "cli.config.errors.profile_session_absent"
        if refusal in _LOGGED_OUT_REFUSALS
        else "cli.config.errors.profile_session_expired"
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
    from ...core.bucket_pointer import resolve_active_bucket_id
    from ...core.config import override_settings
    from ...core.errors import CadrumoError

    active = resolve_active_bucket_id()
    if active is None:
        return
    try:
        pointer = resolve_profile_bucket(active)
    except ProfileLabelAmbiguousError as exc:
        raise CliRefusedBoundaryError(translated_message="errors.refused.refused_profile_label_ambiguous") from exc
    except CadrumoError:
        return
    if pointer is not None:
        ctx.with_resource(override_settings(cadrumo_active_profile=pointer.bucket_id))


def activate_profile_session(
    ctx: typer.Context,
    *,
    posture: ProfileAuthenticationPosture,
    root_selection: ProfileSecretSelection | None,
    leaf_selection: MachineSecretSelection | None,
    spec: CommandSpec,
    arguments: Mapping[str, object],
    target_bucket_id: str | None,
    target_profile_label: str | None,
    command_path: tuple[str, ...],
    authenticate_root: RootAuthenticator,
) -> None:
    """Apply write policy and exact-target session proof from parsed authority."""
    from ._argument_only_refusals import refuse_on_arguments_alone

    # A refusal the arguments alone settle must precede the profile-bound write
    # gate below. Otherwise an unsupported modelo is answered with "no active
    # profile", sending the operator to build an environment for a request that
    # is refused regardless of it.
    refuse_on_arguments_alone(spec, arguments)

    from ...adapters.persistence.storage import active_bucket_session_serves
    from ...application.storage_write_policy import inspect_storage_write_policy
    from ...core.bucket_pointer import resolve_active_bucket_id

    common = _common()
    leaf = common.RequestedCliLeaf(
        subject_leaf_key=spec.result_schema.identity or spec.key,
        canonical_cli_path=command_path,
    )
    policy = spec.policy
    if policy.write_route == "profile-bound":
        from ...core.config import load_settings, settings_for_active_profile_bucket

        settings = load_settings()
        if target_bucket_id is not None and "cadrumo_database_url" not in settings.model_fields_set:
            settings = settings_for_active_profile_bucket(target_bucket_id, settings)
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
    # Profile-key readers are registered by wizard module side effects.  The
    # parsed gate now runs before deferred handler imports, so establish that
    # catalogue explicitly before any resumed/root-authenticated dispatch.
    from ...application.wizard import ensure_profile_keys_registered

    ensure_profile_keys_registered()
    if active_bucket_session_serves(bucket_id):
        if root_selection is not None:
            raise CliRefusedBoundaryError(translated_message="cli.config.custody.errors.profile_secrets_unused")
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
        target_profile_label=target_profile_label,
        requested_leaf=leaf,
    )
    from ...core.i18n import clear_output_language_cache

    clear_output_language_cache()


def _resume_or_authenticate(
    ctx: typer.Context,
    *,
    bucket_id: str,
    root_selection: ProfileSecretSelection | None,
    leaf_selection: MachineSecretSelection | None,
    spec: CommandSpec,
    arguments: Mapping[str, object],
    bind_exact_target: bool,
    authenticate_root: RootAuthenticator,
    target_profile_label: str | None,
    requested_leaf: RequestedCliLeaf,
) -> None:
    from ...adapters.persistence.storage import active_bucket_session_serves
    from ...adapters.persistence.storage.errors import KeyringUnavailableError
    from ...application.profile_preconditions import profile_session_failure_verdict
    from ...application.user_profile import bind_resumed_profile_session

    refusal = bind_resumed_profile_session(bucket_id=bucket_id)
    if refusal is None:
        if not active_bucket_session_serves(bucket_id):
            raise RuntimeError("resumed profile session does not serve the requested target")
        if root_selection is not None:
            raise CliRefusedBoundaryError(translated_message="cli.config.custody.errors.profile_secrets_unused")
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
    verdict = profile_session_failure_verdict(
        refusal,
        profile_name=target_profile_label or common.active_profile_label() or bucket_id,
    )
    key = session_refusal_translation_key(refusal)
    raise common.attach_cli_policy_verdict(
        CliRefusedBoundaryError(translated_message=key, context={"reason": refusal.value}),
        verdict=verdict,
        requested_leaf=requested_leaf,
    )


def _interactive_authentication(ctx: typer.Context, *, bucket_id: str) -> bool:
    """Keep a parsed CLI invocation non-interactive after a session refusal."""
    del ctx, bucket_id
    return False


def authenticate_profile_for_manager(ctx: typer.Context, *, bucket_id: str) -> bool:
    """Use the canonical interactive gate for a manager-selected profile."""
    return _interactive_authentication(ctx, bucket_id=bucket_id)


def resume_registered_profile_for_manager(ctx: typer.Context, *, bucket_id: str) -> None:
    """Resume and bind a profile just registered by the manager frontend."""
    from ...adapters.persistence.storage import active_bucket_session_serves
    from ...application.user_profile import bind_resumed_profile_session

    refusal = bind_resumed_profile_session(bucket_id=bucket_id)
    if refusal is not None or not active_bucket_session_serves(bucket_id):
        raise RuntimeError("registered profile session could not be resumed")
    bind_profile_target(ctx, bucket_id=bucket_id)


__all__ = [
    "activate_profile_session",
    "authenticate_profile_for_manager",
    "bind_profile_target",
    "normalize_ambient_profile",
    "resume_registered_profile_for_manager",
    "session_refusal_translation_key",
]
