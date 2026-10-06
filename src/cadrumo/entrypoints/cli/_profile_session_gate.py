"""Neutral profile-session route and resume authority for parsed dispatch."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib import import_module
from typing import TYPE_CHECKING, Any, Never, Protocol

import typer

from ...application.operator_surface.command_ports import ProfileAuthenticationPosture
from ...core.errors.hierarchy import InternalInvariantError
from ...core.profile_session import ProfileSessionRefusalReason
from .command_spec import CommandSpec
from .state_projection_support import authority_operation

if TYPE_CHECKING:
    from ...application.user_profile.login_session import ProfileLoginOutcome
    from ...application.user_profile.session_admission import ProfileCredentialRequestV1
    from .common import RequestedCliLeaf
    from .config.secure_input import MachineSecretSelection, ProfileSecretSelection


class RootAuthenticator(Protocol):
    """Exact callback seam from the neutral session gate to root authentication.

    Returns the login outcome it achieved so the shared admission door can
    prove the session it reports, rather than each caller re-deriving that
    proof from the substrate.
    """

    def __call__(
        self,
        bucket_id: str,
        root_selection: ProfileSecretSelection,
        leaf_selection: MachineSecretSelection | None,
        spec: CommandSpec,
        arguments: Mapping[str, object],
    ) -> ProfileLoginOutcome: ...


CliRefusedBoundaryError = import_module(".errors", __package__).CliRefusedBoundaryError

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
    return import_module(".common", __package__)


def bind_profile_target(ctx: typer.Context, *, bucket_id: str) -> None:
    """Bind one proven profile target as this invocation's storage route."""
    from ...core.config import override_settings

    ctx.with_resource(override_settings(cadrumo_active_profile=bucket_id))


def normalize_ambient_profile(ctx: typer.Context) -> None:
    """Normalize an ambient label pointer to the canonical live bucket UUID."""
    from ...application.workflow.errors import ProfileLabelAmbiguousError
    from ...application.workflow.profile_bucket_scan import resolve_profile_bucket
    from ...core.bucket_pointer import resolve_active_bucket_id
    from ...core.config import override_settings
    from ...core.errors.hierarchy import CadrumoError

    active = resolve_active_bucket_id()
    if active is None:
        return
    try:
        pointer = resolve_profile_bucket(active)
    except ProfileLabelAmbiguousError as exc:
        from ...application.profile_preconditions import ProfileSelectionFailure, profile_selection_failure_verdict

        common = _common()
        raise common.attach_cli_policy_verdict(
            CliRefusedBoundaryError(translated_message="errors.refused.refused_profile_label_ambiguous"),
            verdict=profile_selection_failure_verdict(
                ProfileSelectionFailure.AMBIGUOUS,
                requested_profile=active,
            ),
            requested_leaf=common.requested_cli_leaf(ctx),
        ) from exc
    except CadrumoError:
        return
    if pointer is not None:
        ctx.with_resource(override_settings(cadrumo_active_profile=pointer.bucket_id))


def _inspect_write_policy(
    *,
    spec: CommandSpec,
    target_bucket_id: str | None,
    inspect_storage_write_policy: Callable[..., Any],
) -> Any:
    """Return the write-policy decision for a profile-bound leaf, or ``None``."""
    policy = spec.policy
    if policy.write_route != "profile-bound":
        return None
    from ...core.config import load_settings, settings_for_active_profile_bucket

    settings = load_settings()
    if target_bucket_id is not None and "cadrumo_database_url" not in settings.model_fields_set:
        settings = settings_for_active_profile_bucket(target_bucket_id, settings)
    return inspect_storage_write_policy(policy.write_route, settings=settings)


def _write_policy_refusal(*, common: Any, leaf: RequestedCliLeaf, write_policy: Any) -> Exception:
    """Build the boundary error carrying one refusing write-policy verdict."""
    if write_policy.verdict is None:
        raise InternalInvariantError("root write-policy refusal is missing its verdict")
    projection = common.project_cli_policy_refusal(requested_leaf=leaf, verdict=write_policy.verdict)
    context = {
        key: value
        for evidence in projection.precondition_action.evidence
        for key, value in evidence.values.items()
        if key.endswith("_setting")
    }
    refusal = common.attach_cli_policy_refusal_projection(
        CliRefusedBoundaryError(
            write_policy.render_refusal_message(),
            context=context or None,
        ),
        projection=projection,
    )
    if not isinstance(refusal, Exception):
        raise InternalInvariantError("write-policy refusal projection did not return a raisable error")
    return refusal


def _enforce_write_policy(
    *,
    common: Any,
    leaf: RequestedCliLeaf,
    spec: CommandSpec,
    target_bucket_id: str | None,
    inspect_storage_write_policy: Callable[..., Any],
) -> None:
    """Refuse a disallowed profile-bound write before session activation."""
    write_policy = _inspect_write_policy(
        spec=spec,
        target_bucket_id=target_bucket_id,
        inspect_storage_write_policy=inspect_storage_write_policy,
    )
    if write_policy is None or write_policy.allowed:
        return
    raise _write_policy_refusal(common=common, leaf=leaf, write_policy=write_policy)


def enforce_explicit_database_route(
    *,
    spec: CommandSpec,
    command_path: tuple[str, ...],
    target_bucket_id: str | None,
) -> None:
    """Refuse an operator-pinned database URL before a runtime leaf admits a profile.

    The runtime admission path owns its own no-active-profile refusal, and that
    one is the better answer for a cold start: it separates an operator who has
    registered nothing from one who is merely logged out. It has no equivalent
    for an explicitly pinned ``cadrumo_database_url``. Creating or selecting a
    profile does not move that route, so answering a pinned route with "create
    a profile" sends the operator down a recovery that cannot succeed. The
    write policy's closed outcome is the honest one, and it is reached here so
    the runtime and local routes refuse the same pinned route the same way.

    Only that one decision is applied. The write policy's root-fallback branch
    is deliberately left to the runtime path's richer refusal.
    """
    from ...application.storage_write_policy import StorageWritePolicyCode, inspect_storage_write_policy

    write_policy = _inspect_write_policy(
        spec=spec,
        target_bucket_id=target_bucket_id,
        inspect_storage_write_policy=inspect_storage_write_policy,
    )
    if write_policy is None or write_policy.code is not StorageWritePolicyCode.REFUSED_EXPLICIT_DATABASE_URL:
        return
    common = _common()
    leaf = common.RequestedCliLeaf(
        subject_leaf_key=spec.result_schema.identity or spec.key,
        canonical_cli_path=command_path,
    )
    raise _write_policy_refusal(common=common, leaf=leaf, write_policy=write_policy)


def _posture_skips_session(posture: ProfileAuthenticationPosture) -> bool:
    """Return whether the command posture deliberately needs no profile session."""
    return (
        posture is ProfileAuthenticationPosture.NOT_APPLICABLE
        or posture is ProfileAuthenticationPosture.SELF_AUTHENTICATING
    )


def _activate_existing_profile_session(
    ctx: typer.Context,
    *,
    bucket_id: str,
    root_selection: ProfileSecretSelection | None,
    target_bucket_id: str | None,
    active_bucket_session_serves: Callable[[str], bool],
) -> bool:
    """Bind a serving session or refuse an unused root secret source."""
    if not active_bucket_session_serves(bucket_id):
        return False
    if root_selection is not None:
        raise CliRefusedBoundaryError(translated_message="cli.config.custody.errors.profile_secrets_unused")
    if target_bucket_id is not None:
        bind_profile_target(ctx, bucket_id=bucket_id)
    return True


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
    # is refused regardless of it. Dispatch has already opened the invocation's
    # governed-fact scope, so an argument-only parse reads the generation the
    # command itself will.
    refuse_on_arguments_alone(spec, arguments)

    from ...adapters.persistence.storage.master_key.active_session import active_bucket_session_serves
    from ...application.storage_write_policy import inspect_storage_write_policy
    from ...core.bucket_pointer import resolve_active_bucket_id

    common = _common()
    leaf = common.RequestedCliLeaf(
        subject_leaf_key=spec.result_schema.identity or spec.key,
        canonical_cli_path=command_path,
    )
    _enforce_write_policy(
        common=common,
        leaf=leaf,
        spec=spec,
        target_bucket_id=target_bucket_id,
        inspect_storage_write_policy=inspect_storage_write_policy,
    )
    bucket_id = target_bucket_id or resolve_active_bucket_id()
    if bucket_id is None:
        return
    if _posture_skips_session(posture):
        return
    if _activate_existing_profile_session(
        ctx,
        bucket_id=bucket_id,
        root_selection=root_selection,
        target_bucket_id=target_bucket_id,
        active_bucket_session_serves=active_bucket_session_serves,
    ):
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
    from ...core.i18n.render import clear_output_language_cache

    clear_output_language_cache()


def _root_secret_journey(
    *,
    root_selection: ProfileSecretSelection,
    leaf_selection: MachineSecretSelection | None,
    spec: CommandSpec,
    arguments: Mapping[str, object],
    authenticate_root: RootAuthenticator,
) -> Callable[[ProfileCredentialRequestV1], ProfileLoginOutcome | None]:
    """Adapt the declared root secret channel to the shared credential journey.

    A parsed invocation cannot decline: the channel either yields a payload or
    refuses, so this journey never returns ``None``. The optional return in
    the protocol exists for an interactive surface whose operator may abandon
    a credential screen.
    """

    def journey(request: ProfileCredentialRequestV1) -> ProfileLoginOutcome | None:
        if request.bucket_id is None:
            # A parsed invocation always resolves its target before the gate
            # runs; an unnamed one belongs to an interactive chooser, which
            # this surface does not have.
            raise InternalInvariantError("parsed dispatch reached root authentication with no resolved target")
        return authenticate_root(request.bucket_id, root_selection, leaf_selection, spec, arguments)

    return journey


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
    from ...application.user_profile.session_admission import (
        ProfileSessionAdmissionState,
        admit_profile_session,
    )

    admission = admit_profile_session(
        bucket_id=bucket_id,
        profile_decode_context=authority_operation(ctx).profile_decode_context(),
        credentials=None
        if root_selection is None
        else _root_secret_journey(
            root_selection=root_selection,
            leaf_selection=leaf_selection,
            spec=spec,
            arguments=arguments,
            authenticate_root=authenticate_root,
        ),
    )
    if admission.state is ProfileSessionAdmissionState.AUTHENTICATED:
        # The root fallback binds this invocation's storage route and stages
        # its not-persisted notice itself, because both are consequences of
        # having authenticated rather than of having a session.
        return
    if admission.admitted:
        if root_selection is not None:
            raise CliRefusedBoundaryError(translated_message="cli.config.custody.errors.profile_secrets_unused")
        if bind_exact_target:
            bind_profile_target(ctx, bucket_id=bucket_id)
        return
    refusal = admission.resume_refusal
    if refusal is None:
        if _interactive_authentication(ctx, bucket_id=bucket_id, refusal=None):
            return
        from ...application.user_profile.custody_ports import refuse_profile_login_without_password_channel

        refuse_profile_login_without_password_channel()
    if _interactive_authentication(ctx, bucket_id=bucket_id, refusal=refusal):
        return
    _raise_profile_resume_refusal(refusal, target_profile_label, bucket_id, requested_leaf)


def _interactive_authentication(
    ctx: typer.Context,
    *,
    bucket_id: str,
    refusal: ProfileSessionRefusalReason | None,
) -> bool:
    """Offer explicit local credentials only at an interactive terminal.

    No receipt observation is inferred from missing local custody. Runtime
    clients perform automatic proof presentation through their own admission.
    """
    if refusal not in {None, ProfileSessionRefusalReason.KEYRING_UNAVAILABLE}:
        return False
    from .config.secure_input import terminal_can_prompt_for_secrets

    if not terminal_can_prompt_for_secrets():
        return False
    from ._profile_authentication_gate import prompt_root_authentication

    prompt_root_authentication(ctx, bucket_id=bucket_id)
    return True


__all__ = [
    "activate_profile_session",
    "bind_profile_target",
    "normalize_ambient_profile",
    "session_refusal_translation_key",
]


def _raise_profile_resume_refusal(
    refusal: ProfileSessionRefusalReason,
    target_profile_label: str | None,
    bucket_id: str,
    requested_leaf: RequestedCliLeaf,
) -> Never:
    """Attach the existing typed policy verdict after interactive authentication is exhausted."""
    from ...adapters.persistence.storage.errors import KeyringUnavailableError
    from ...application.profile_preconditions import profile_session_failure_verdict

    if refusal is ProfileSessionRefusalReason.KEYRING_UNAVAILABLE:
        raise KeyringUnavailableError("OS keychain is unavailable for profile-session acceleration")
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
