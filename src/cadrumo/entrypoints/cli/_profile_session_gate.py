"""Neutral profile-session route and resume authority for parsed dispatch."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib import import_module
from typing import TYPE_CHECKING, Any, Protocol

import typer

from cadrumo.application.operator_surface.command_ports import ProfileAuthenticationPosture

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
        raise CliRefusedBoundaryError(translated_message="errors.refused.refused_profile_label_ambiguous") from exc
    except CadrumoError:
        return
    if pointer is not None:
        ctx.with_resource(override_settings(cadrumo_active_profile=pointer.bucket_id))


def _enforce_write_policy(
    *,
    common: Any,
    leaf: RequestedCliLeaf,
    spec: CommandSpec,
    target_bucket_id: str | None,
    inspect_storage_write_policy: Callable[..., Any],
) -> None:
    """Refuse a disallowed profile-bound write before session activation."""
    policy = spec.policy
    if policy.write_route != "profile-bound":
        return
    from ...core.config import load_settings, settings_for_active_profile_bucket

    settings = load_settings()
    if target_bucket_id is not None and "cadrumo_database_url" not in settings.model_fields_set:
        settings = settings_for_active_profile_bucket(target_bucket_id, settings)
    write_policy = inspect_storage_write_policy(policy.write_route, settings=settings)
    if write_policy.allowed:
        return
    if write_policy.verdict is None:
        raise InternalInvariantError("root write-policy refusal is missing its verdict")
    projection = common.project_cli_policy_refusal(requested_leaf=leaf, verdict=write_policy.verdict)
    context = {
        key: value
        for evidence in projection.precondition_action.evidence
        for key, value in evidence.values.items()
        if key.endswith("_setting")
    }
    raise common.attach_cli_policy_refusal_projection(
        CliRefusedBoundaryError(
            write_policy.render_refusal_message(),
            context=context or None,
        ),
        projection=projection,
    )


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
    # is refused regardless of it.
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
    from ...adapters.persistence.storage.errors import KeyringUnavailableError
    from ...application.profile_preconditions import profile_session_failure_verdict
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
        raise InternalInvariantError("a refused profile admission carries no typed reason")
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


__all__ = [
    "activate_profile_session",
    "bind_profile_target",
    "normalize_ambient_profile",
    "session_refusal_translation_key",
]
