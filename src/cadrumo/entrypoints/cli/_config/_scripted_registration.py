"""Non-interactive profile creation for ``config profile create``.

``create`` serves two audiences through one verb. An operator at a capable
terminal is diverted to the registration screen; everything else — a script,
an agent, a CI job, any host without a full-screen console — arrives here.

That second arm had no creation path at all. It fell through to the setup
flow, whose ``create`` mode refuses outright because the flow is not a
creation authority: a profile is brought into existence by supplying a label
and a passphrase, and the flow collects neither. The refusal was correct
about the flow and wrong about the operator, who was told to "register with
credentials" by a surface that offered no way to do it.

The credential channel is resolved in one declared order, and every step is a
channel the operator chose:

1. one bounded strict-JSON ``--secrets-stdin`` or ``--secrets-fd`` payload for
   machine callers;
2. the hardened no-echo console prompt when a real console is attached;
3. otherwise an instructive refusal naming the supported channels, because silently creating a
   profile under a passphrase nobody chose is worse than refusing.

The passphrase is never accepted as an ``argv`` value, on this verb or any
other: a command line is visible in the process table and in shell history.
"""

from __future__ import annotations

import json
import os
from contextlib import suppress
from typing import TYPE_CHECKING, cast

import typer
from pydantic import SecretStr

from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import emit_envelope
from ..errors import CliRefusedBoundaryError
from ._secure_input import MachineSecretPayload

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from typer._click.core import Context as _TyperClickContext

    from ....application.user_profile.recovery_custody import ProfileRecoveryEnrollment


class ProfileCreationSecrets(MachineSecretPayload):
    """Strict machine-channel payload for profile creation."""

    passphrase: SecretStr
    passphrase_confirmation: SecretStr


class ProfileRecoveryVerification(MachineSecretPayload):
    """Strict possession proof returned after the one-time handoff."""

    recovery_mnemonic: SecretStr


def resolve_creation_passphrase(*, secrets_stdin: bool = False, secrets_fd: int | None = None) -> str:
    """Return the passphrase for a scripted registration, or refuse.

    Exactly one explicit bounded machine payload wins. Without one, a real
    interactive terminal receives the no-echo prompt; a non-interactive caller
    must choose one of the explicit channels.
    """
    from ._secure_input import (
        prompt_secret_no_echo,
        read_machine_secret_payload,
        select_machine_secret_channel,
        terminal_can_prompt_for_secrets,
    )

    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    if selection is not None:
        secrets = read_machine_secret_payload(ProfileCreationSecrets, selection=selection)
        first = secrets.passphrase.get_secret_value()
        if first != secrets.passphrase_confirmation.get_secret_value():
            raise CliRefusedBoundaryError(
                translated_message="cli.config.profile.create_passphrase_mismatch",
            )
        return first

    if terminal_can_prompt_for_secrets():
        first = prompt_secret_no_echo(tr("cli.config.profile.create_passphrase_prompt"))
        again = prompt_secret_no_echo(tr("cli.config.profile.create_confirm_passphrase_prompt"))
        if first != again:
            raise CliRefusedBoundaryError(
                translated_message="cli.config.profile.create_passphrase_mismatch",
            )
        return first

    raise CliRefusedBoundaryError(
        translated_message="cli.config.profile.create_passphrase_channel_absent",
    )


def _validated_recovery_descriptors(
    *,
    passphrase_fd: int | None,
    handoff_fd: int | None,
    verification_fd: int | None,
) -> tuple[int, int] | None:
    """Preflight the headless handoff pair before any descriptor is consumed."""
    if (handoff_fd is None) != (verification_fd is None):
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.create_recovery_descriptor_pair_required")
    if handoff_fd is None or verification_fd is None:
        return None
    descriptors = (handoff_fd, verification_fd)
    if any(descriptor < 0 or descriptor in {0, 1, 2} for descriptor in descriptors):
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.create_recovery_descriptor_reserved",
        )
    occupied = {descriptor for descriptor in (passphrase_fd,) if descriptor is not None}
    if handoff_fd == verification_fd or any(descriptor in occupied for descriptor in descriptors):
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.create_recovery_descriptor_collision",
        )
    return descriptors


def _write_recovery_handoff(descriptor: int, mnemonic: str) -> None:
    """Write one bounded secret document and close its descriptor on every exit."""
    raw = bytearray(json.dumps({"recovery_mnemonic": mnemonic}, separators=(",", ":")).encode("utf-8") + b"\n")
    try:
        if len(raw) > 8192:
            raise CliRefusedBoundaryError(
                translated_message="cli.config.profile.create_recovery_handoff_too_large",
            )
        view = memoryview(raw)
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                raise OSError("recovery handoff descriptor accepted no bytes")
            written += count
    except OSError as exc:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.create_recovery_handoff_unwritable",
        ) from exc
    finally:
        raw[:] = b"\x00" * len(raw)
        with suppress(OSError):
            os.close(descriptor)


def _read_recovery_verification(descriptor: int) -> ProfileRecoveryVerification:
    """Read one newline-framed strict object without depending on pipe EOF."""
    from ._secure_input import MACHINE_SECRET_MAX_BYTES, _validate_secrets_payload

    raw = bytearray()
    try:
        while len(raw) <= MACHINE_SECRET_MAX_BYTES:
            chunk = os.read(descriptor, min(1024, MACHINE_SECRET_MAX_BYTES + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
            newline = raw.find(b"\n")
            if newline >= 0:
                if newline != len(raw) - 1:
                    raise CliRefusedBoundaryError(
                        translated_message="cli.config.custody.errors.secrets_fd_invalid_json",
                        context={"expected_fields": "recovery_mnemonic"},
                    )
                del raw[newline:]
                break
        if len(raw) > MACHINE_SECRET_MAX_BYTES:
            raise CliRefusedBoundaryError(translated_message="cli.config.custody.errors.secrets_fd_too_large")
        return _validate_secrets_payload(
            raw,
            ProfileRecoveryVerification,
            invalid_json_key="cli.config.custody.errors.secrets_fd_invalid_json",
            missing_fields_key="cli.config.custody.errors.secrets_fd_missing_fields",
        )
    except OSError as exc:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.secrets_fd_unreadable",
            context={"descriptor": str(descriptor)},
        ) from exc
    finally:
        raw[:] = b"\x00" * len(raw)
        with suppress(OSError):
            os.close(descriptor)


def _recovery_handover(
    *,
    descriptors: tuple[int, int] | None,
) -> Callable[[ProfileRecoveryEnrollment], str]:
    """Build an interactive or descriptor handoff with possession proof.

    Creation never falls through to a password-only profile. A terminal caller
    must re-enter the phrase; a headless caller receives it on one bounded
    descriptor and returns the exact phrase on another bounded descriptor.
    Both proofs complete before the registration transaction can publish.
    """
    from ._secure_input import (
        prompt_secret_no_echo,
        terminal_can_prompt_for_secrets,
        write_to_controlling_terminal,
    )

    if descriptors is None and not terminal_can_prompt_for_secrets():
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.create_recovery_channel_absent",
        )

    def handover(enrollment: ProfileRecoveryEnrollment) -> str:
        """Deliver once and return exact proof to the publication owner."""
        expected = enrollment.recovery_key.mnemonic
        if descriptors is None:
            write_to_controlling_terminal(
                f"{tr('cli.config.custody.data_loss_warning')}\n\n{expected}",
            )
            supplied = prompt_secret_no_echo(tr("cli.config.profile.create_recovery_verification_prompt"))
        else:
            handoff_fd, verification_fd = descriptors
            _write_recovery_handoff(handoff_fd, expected)
            proof = _read_recovery_verification(verification_fd)
            supplied = proof.recovery_mnemonic.get_secret_value()
        try:
            if supplied != expected:
                raise CliRefusedBoundaryError(
                    translated_message="cli.config.profile.create_recovery_verification_mismatch",
                )
            return supplied
        finally:
            del expected

    return handover


def register_profile_from_scripted_invocation(
    ctx: _TyperClickContext,
    kwargs: Mapping[str, object],
) -> None:
    """Create a profile from a scripted ``config profile create`` invocation.

    The label is the verb's own positional subject. Facts supplied as field
    flags are applied after the record exists rather than as preconditions
    for it: a profile is born incomplete on purpose, so a rejected fact
    leaves a real profile the operator can correct instead of nothing.
    """
    from ....application.user_profile.registration import register_profile_with_credentials
    from ....application.wizard.commands import scripted_profile_facts
    from ....application.wizard.results import ConfigProfileCreateResult, ProfileWizardStatus
    from ....core.wizard_catalogue import get_setup_flow

    supplied = kwargs.get("profile_name")
    label = supplied.strip() if isinstance(supplied, str) else ""
    if not label:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.create_name_required",
        )

    # Projected BEFORE the passphrase is resolved so a refused flag -- a foral
    # CCAA token, an unparseable value -- costs the operator nothing: no
    # prompt, no profile, nothing to undo. The facts then ride INTO the create
    # transaction, which already holds the record session, rather than being
    # written through a second unlock once registration has closed it.
    facts = scripted_profile_facts(get_setup_flow(), kwargs)
    raw_secrets_fd = kwargs.get("secrets_fd")
    secrets_fd = raw_secrets_fd if isinstance(raw_secrets_fd, int) else None
    raw_handoff_fd = kwargs.get("recovery_handoff_fd")
    raw_verification_fd = kwargs.get("recovery_verification_fd")
    recovery_descriptors = _validated_recovery_descriptors(
        passphrase_fd=secrets_fd,
        handoff_fd=raw_handoff_fd if isinstance(raw_handoff_fd, int) else None,
        verification_fd=raw_verification_fd if isinstance(raw_verification_fd, int) else None,
    )
    passphrase: str | None = None
    try:
        passphrase = resolve_creation_passphrase(
            secrets_stdin=bool(kwargs.get("secrets_stdin")),
            secrets_fd=secrets_fd,
        )
        outcome = register_profile_with_credentials(
            label=label,
            passphrase=passphrase,
            facts=facts,
            recovery_handover=_recovery_handover(descriptors=recovery_descriptors),
        )
    finally:
        if passphrase is not None:
            del passphrase
        if recovery_descriptors is not None:
            for descriptor in recovery_descriptors:
                with suppress(OSError):
                    os.close(descriptor)

    if not outcome.recovery_enrolled:
        raise RuntimeError("profile creation returned without mandatory recovery enrollment")
    notices = (
        Notice(
            code="PROFILE_RECOVERY_ENROLLED",
            severity=NoticeSeverity.INFO,
            message=tr("cli.config.profile.create_recovery_enrolled"),
        ),
    )
    emit_envelope(
        # CAST-RATIONALE-TYPER-CLICK-CONTEXT: ctx is the vendored
        # typer._click.core.Context this package accepts at its boundary;
        # emit_envelope's signature names the public typer.Context alias
        # for the same runtime object.
        cast(typer.Context, ctx),
        command="config.profile.create",
        result=ConfigProfileCreateResult(
            profile_name=outcome.label,
            status=ProfileWizardStatus.CREATED,
            active_profile=outcome.label,
        ),
        lines=[
            tr("cli.config.profile.manager_closed_created", profile=outcome.label),
            *(notice.message for notice in notices),
        ],
        notices=notices,
    )


__all__ = ["register_profile_from_scripted_invocation", "resolve_creation_passphrase"]
