"""Parsed-dispatch safety gate for root profile authentication."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, cast

import typer

from ._command_spec import CommandSpec, MachineSecretVariantSpec, ProfileAuthenticationPosture
from ._config._secure_input import (
    MachineSecretChannel,
    MachineSecretPayload,
    MachineSecretSelection,
    ProfileSecretChannel,
    ProfileSecretSelection,
    read_machine_secret_payload,
    read_profile_secret_payload,
    select_machine_secret_channel,
    select_profile_secret_channel,
    stage_machine_secret_payload,
)
from ._profile_authentication_contract import (
    ProfileAuthenticationSecrets,
    ProfileSecretSourceOptions,
    profile_authentication_posture,
    root_profile_secret_model,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cadrumo.application.workflow.profile_bucket_models import ProfileBucketPointer


_RESOLVED_PROFILE_TARGET_KEY = "cadrumo.resolved_profile_target"


def _refuse(key: str) -> None:
    error = import_module("cadrumo.entrypoints.cli._errors").CliRefusedBoundaryError
    raise error(translated_message=f"cli.config.custody.errors.{key}")


def _root_source(ctx: typer.Context) -> ProfileSecretSourceOptions:
    value = cast("dict[str, object]", ctx.find_root().ensure_object(dict)).get("profile_secret_source")
    if value is None:
        return ProfileSecretSourceOptions()
    if not isinstance(value, ProfileSecretSourceOptions):
        raise TypeError("root profile-secret source has an invalid type")
    return value


def _leaf_selection(spec: CommandSpec, arguments: Mapping[str, object]) -> MachineSecretSelection | None:
    if spec.machine_secret is None:
        return None
    return select_machine_secret_channel(
        secrets_stdin=bool(arguments.get("secrets_stdin", False)),
        secrets_fd=cast("int | None", arguments.get("secrets_fd")),
    )


def _preflight_sources(*, root: ProfileSecretSelection | None, leaf: MachineSecretSelection | None) -> None:
    if root is None or leaf is None:
        return
    root_descriptor = 0 if root.channel is ProfileSecretChannel.STDIN else root.descriptor
    leaf_descriptor = 0 if leaf.channel is MachineSecretChannel.STDIN else leaf.descriptor
    if root_descriptor != leaf_descriptor:
        return
    if root_descriptor == 0:
        _refuse("profile_secrets_stdin_collision")
    _refuse("profile_secrets_fd_collision")


def _selected_variant(spec: CommandSpec, arguments: Mapping[str, object]) -> MachineSecretVariantSpec:
    machine = spec.machine_secret
    if machine is None:
        raise RuntimeError("leaf machine-secret model requested for a non-adopter")
    matches: list[MachineSecretVariantSpec] = []
    for variant in machine.variants:
        condition = variant.condition
        if condition is None:
            matches.append(variant)
            continue
        present = arguments.get(condition.option_name) is not None
        if present is (condition.presence == "present"):
            matches.append(variant)
    if len(matches) != 1:
        raise RuntimeError("parsed command does not select exactly one machine-secret variant")
    return matches[0]


def _read_and_stage_leaf(
    *, spec: CommandSpec, arguments: Mapping[str, object], selection: MachineSecretSelection | None
) -> None:
    if selection is None:
        return
    from ._command_target import resolve_deferred_target

    model = resolve_deferred_target(_selected_variant(spec, arguments).model)
    if not isinstance(model, type) or not issubclass(model, MachineSecretPayload):
        raise TypeError("leaf machine-secret model must inherit MachineSecretPayload")
    stage_machine_secret_payload(read_machine_secret_payload(model, selection=selection))


def _resolve_login_target_or_refuse(raw: str):
    """Resolve a profile target, converting label ambiguity to the CLI refusal.

    `resolve_login_target` surfaces `ProfileLabelAmbiguousError`, a WorkflowError
    from the application layer. Left uncaught here it reaches the terminal
    boundary and renders the WORKFLOW-layer message ("... active buckets carry
    it") instead of the dedicated CLI refusal that tells the operator what to do
    ("Use the profile UUID to disambiguate").

    That exact escape was fixed once before, at the three other CLI sites that
    resolve a label -- `_config/_profile_support.resolve_profile_by_label`,
    `_profile_session_gate.normalize_ambient_profile`, and the root
    `--profile` override. This preflight is a FOURTH resolution site, introduced
    after that fix, and it did not carry the conversion, so the escape returned
    on `config profile show <label>` and `config profile validate <label>`.
    """
    from ...application.profile_preconditions import (
        ProfileSelectionFailure,
        profile_selection_failure_verdict,
    )
    from ...application.user_profile.login_session import resolve_login_target
    from cadrumo.application.workflow.errors import ProfileLabelAmbiguousError
    from ...domain.user_profile import ProfileNotFoundError
    from ._common import attach_cli_policy_verdict
    from ._errors import CliRefusedBoundaryError

    try:
        return resolve_login_target(raw)
    except ProfileLabelAmbiguousError as error:
        raise CliRefusedBoundaryError(
            translated_message="errors.refused.refused_profile_label_ambiguous",
        ) from error
    except ProfileNotFoundError as error:
        # The message already names the next step in prose ("run `aeat config
        # profile list`"), but the TYPED action was null, so the machine-readable
        # half of that guidance was missing -- and this CLI's operator is an
        # non-interactive caller, for which the prose is not actionable. The verdict is
        # attached to the existing error rather than replacing it with a
        # `CliRefusedBoundaryError`, so `REFUSED_PROFILE_NOT_FOUND` and its
        # message stay exactly as they are on the wire; only the absent
        # projection is filled. The root `--profile` override already projects
        # this same UNKNOWN verdict.
        attach_cli_policy_verdict(
            error,
            verdict=profile_selection_failure_verdict(
                ProfileSelectionFailure.UNKNOWN,
                requested_profile=raw,
            ),
        )
        raise


def preflight_parsed_leaf(
    ctx: typer.Context,
    *,
    spec: CommandSpec,
    arguments: Mapping[str, object],
) -> None:
    """Preflight parsed root/leaf sources, then run the ordinary root gate."""
    from ._command_specs import COMMAND_GRAPH
    from ._profile_session_gate import activate_profile_session, bind_profile_target, normalize_ambient_profile

    node = next(node for node in COMMAND_GRAPH.nodes() if node.spec.key == spec.key)
    posture = profile_authentication_posture(node)
    source = _root_source(ctx)
    root = select_profile_secret_channel(
        profile_secrets_stdin=source.stdin,
        profile_secrets_fd=source.descriptor,
    )
    leaf = _leaf_selection(spec, arguments)
    _preflight_sources(root=root, leaf=leaf)
    if posture is not ProfileAuthenticationPosture.RESUME_FALLBACK and root is not None:
        _refuse("profile_secrets_inapplicable")
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    from ...core.logging import resume_logging_configuration
    from ._log_levels import LogLevel, apply_to_root_logger

    log_level = root_state.get("log_level")
    if isinstance(log_level, LogLevel):
        resume_logging_configuration()
        apply_to_root_logger(log_level)
    explicit_target = None
    explicit_label = None
    if spec.profile_target_parameter is not None:
        raw_target = arguments.get(spec.profile_target_parameter)
        if raw_target is not None:
            if not isinstance(raw_target, str):
                raise TypeError("profile target parameter has an invalid type")
            pointer = _resolve_login_target_or_refuse(raw_target)
            explicit_target = pointer.bucket_id
            explicit_label = pointer.label
            root_state[_RESOLVED_PROFILE_TARGET_KEY] = pointer
    if explicit_target is None and posture is not ProfileAuthenticationPosture.NOT_APPLICABLE:
        profile_override = root_state.get("profile_override")
        if isinstance(profile_override, str):
            pointer = _resolve_login_target_or_refuse(profile_override)
            explicit_target = pointer.bucket_id
            explicit_label = pointer.label
            if posture is not ProfileAuthenticationPosture.RESUME_FALLBACK:
                bind_profile_target(ctx, bucket_id=explicit_target)
        else:
            normalize_ambient_profile(ctx)

    def authenticate(
        bucket_id: str,
        root_selection: ProfileSecretSelection,
        leaf_selection: MachineSecretSelection | None,
        spec: CommandSpec,
        arguments: Mapping[str, object],
    ) -> None:
        consume_root_fallback(
            ctx,
            bucket_id=bucket_id,
            root=root_selection,
            leaf=leaf_selection,
            spec=spec,
            arguments=arguments,
        )

    if spec.allow_unregistered_profile_diagnostic:
        from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket_by_id
        from ...core.bucket_pointer import resolve_active_bucket_id

        active = resolve_active_bucket_id()
        if active is not None and read_profile_bucket_by_id(active) is None:
            if root is not None:
                _refuse("profile_secrets_inapplicable")
            from ...core import ensure_storage_tree

            ensure_storage_tree()
            return
    if posture is not ProfileAuthenticationPosture.RESUME_FALLBACK:
        activate_profile_session(
            ctx,
            posture=posture,
            root_selection=None,
            leaf_selection=leaf,
            spec=spec,
            arguments=arguments,
            target_bucket_id=explicit_target,
            target_profile_label=explicit_label,
            command_path=node.path[1:],
            authenticate_root=authenticate,
        )
    else:
        if root is not None and explicit_target is None:
            from ...core.bucket_pointer import resolve_active_bucket_id

            if resolve_active_bucket_id() is None:
                _refuse("profile_secrets_missing_target")
        activate_profile_session(
            ctx,
            posture=posture,
            root_selection=root,
            leaf_selection=leaf,
            spec=spec,
            arguments=arguments,
            target_bucket_id=explicit_target,
            target_profile_label=explicit_label,
            command_path=node.path[1:],
            authenticate_root=authenticate,
        )
    from ...core import ensure_storage_tree

    ensure_storage_tree()


def resolved_command_profile_target(ctx: typer.Context) -> ProfileBucketPointer | None:
    """Return the one graph-declared explicit target resolved by dispatch."""
    value = cast("dict[str, object]", ctx.find_root().ensure_object(dict)).get(_RESOLVED_PROFILE_TARGET_KEY)
    if value is None:
        return None
    from cadrumo.application.workflow.profile_bucket_models import ProfileBucketPointer

    if not isinstance(value, ProfileBucketPointer):
        raise TypeError("resolved command profile target has an invalid type")
    return value


def consume_root_fallback(
    ctx: typer.Context,
    *,
    bucket_id: str,
    root: ProfileSecretSelection,
    leaf: MachineSecretSelection | None,
    spec: CommandSpec,
    arguments: Mapping[str, object],
) -> None:
    """Read all required payloads, authenticate exactly, and assert the session."""
    from ...adapters.persistence.storage import active_bucket_session_serves
    from ...application.user_profile.login_session import login_profile

    _read_and_stage_leaf(spec=spec, arguments=arguments, selection=leaf)
    payload = read_profile_secret_payload(root_profile_secret_model(), selection=root)
    passphrase = ""
    try:
        if not isinstance(payload, ProfileAuthenticationSecrets):
            raise TypeError("root profile-secret model resolved an unexpected payload type")
        passphrase = payload.profile_passphrase.get_secret_value()
        outcome = login_profile(
            name=bucket_id,
            passphrase_callback=lambda: passphrase,
        )
        if outcome.bucket_id != bucket_id or not active_bucket_session_serves(bucket_id):
            raise RuntimeError("profile authentication did not establish the exact requested session")
        from ._profile_session_gate import bind_profile_target

        bind_profile_target(ctx, bucket_id=bucket_id)
        if not outcome.session_persisted:
            from ._profile_authentication_notice import stage_profile_session_not_persisted_notice

            stage_profile_session_not_persisted_notice()
    finally:
        passphrase = ""
        del payload


__all__ = [
    "consume_root_fallback",
    "preflight_parsed_leaf",
    "resolved_command_profile_target",
]
