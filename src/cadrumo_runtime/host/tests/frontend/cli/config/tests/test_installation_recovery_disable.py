"""Recovery removal is a runtime act: the passphrase is proved there, and nothing is removed without it."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import pytest
from click.testing import Result
from pydantic import SecretBytes

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.authentication import ProfileAuthenticationRefusedError
from cadrumo.application.user_profile.recovery_custody import ProfileRecoveryError, profile_recovery_status
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo_client.contracts.installation_requests import (
    InstallationAct,
    InstallationRefused,
    RecoveryDisableReply,
    RecoveryDisableRequest,
    RecoveryEnrollReply,
    RecoveryEnrollRequest,
)
from cadrumo_client.transport.installation_client import InstallationClient, installation_passphrase_document

from .installation_profile_support import PROFILE_INPUT, installation_client, served_installation

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_WRONG_INPUT = "not-the-passphrase-of-this-profile"


def _disable(client: InstallationClient, passphrase: str, *, tui: bool = False) -> object:
    secret = installation_passphrase_document(bytearray(passphrase, "utf-8"))
    frontend = OperationFrontendProjection.TUI if tui else OperationFrontendProjection.CLI
    reply = client.perform(
        # No profile is named: the act disables the selected one, as the command does.
        RecoveryDisableRequest(request_id=uuid4(), frontend=frontend),
        RecoveryDisableReply,
        secret=secret,
    )
    assert not any(secret)
    return reply


def test_removal_proves_the_passphrase_removes_the_code_once_and_then_answers_unchanged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, invoke_cli: Callable[..., Result]
) -> None:
    caplog.set_level(logging.DEBUG)
    with (
        served_installation(tmp_path, run_cli=invoke_cli) as installation,
        installation_client(installation.endpoint) as client,
    ):
        profile, root = installation.profile_id, installation.root
        enrolled = client.perform(
            RecoveryEnrollRequest(request_id=uuid4(), frontend=OperationFrontendProjection.CLI, profile_id=profile),
            RecoveryEnrollReply,
            secret=installation_passphrase_document(bytearray(PROFILE_INPUT, "utf-8")),
            hold_secret=lambda delivered: SecretBytes(bytes(delivered)),
        )
        refused = _disable(client, _WRONG_INPUT)
        kept = profile_recovery_status(profile_id=profile, root=root).enrolled
        removed = _disable(client, PROFILE_INPUT, tui=True)
        gone = profile_recovery_status(profile_id=profile, root=root).enrolled
        unchanged = _disable(client, PROFILE_INPUT)
        unproven = _disable(client, _WRONG_INPUT)

    assert isinstance(enrolled, RecoveryEnrollReply) and enrolled.enrolled
    assert isinstance(refused, InstallationRefused) and isinstance(unproven, InstallationRefused)
    assert refused.act is InstallationAct.RECOVERY_DISABLE
    # A wrong passphrase is refused as a wrong passphrase whether or not a code is enrolled.
    accepted = {
        get_registered_error_code(error).code for error in (ProfileRecoveryError, ProfileAuthenticationRefusedError)
    }
    assert refused.detail.error_code in accepted
    assert unproven.detail.error_code == refused.detail.error_code
    assert kept
    assert isinstance(removed, RecoveryDisableReply) and isinstance(unchanged, RecoveryDisableReply)
    assert (removed.profile_id, removed.enrolled, removed.changed) == (str(profile), False, True)
    assert (unchanged.enrolled, unchanged.changed) == (False, False)
    assert not gone
    for private in (PROFILE_INPUT, _WRONG_INPUT):
        assert private not in refused.model_dump_json()
        assert private not in caplog.text
