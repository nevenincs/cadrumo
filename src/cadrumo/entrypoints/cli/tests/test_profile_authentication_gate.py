"""Focused parsed-dispatch proof for the root profile-authentication gate."""

from __future__ import annotations

import json
import os
import sys

import pytest

from ....core import OutputLanguage, ProfileSessionRefusalReason
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from .._command_spec import ProfileAuthenticationPosture
from .._command_specs import COMMAND_GRAPH
from .._config._secure_input import (
    MachineSecretChannel,
    MachineSecretSelection,
    ProfileSecretChannel,
    ProfileSecretSelection,
)
from .._errors import CliRefusedBoundaryError, render_error_payload
from .._profile_authentication_gate import _preflight_sources
from .._profile_authentication_notice import (
    drain_profile_authentication_notices,
    stage_profile_session_not_persisted_notice,
)
from .._profile_session_gate import session_refusal_translation_key
from .._windows_profile_secret_bootstrap import descriptor_from_inherited_handle

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _leaf(identity: str):
    return COMMAND_GRAPH.by_schema_identity()[identity]


def test_cross_scope_stdin_collision_refuses_before_any_read() -> None:
    root = ProfileSecretSelection(ProfileSecretChannel.STDIN)
    leaf = MachineSecretSelection(MachineSecretChannel.STDIN)

    with pytest.raises(CliRefusedBoundaryError) as caught:
        _preflight_sources(root=root, leaf=leaf)

    assert caught.value.translated_message is not None
    assert caught.value.translated_message.endswith("profile_secrets_stdin_collision")


def test_cross_scope_same_descriptor_refuses_but_distinct_descriptors_pass() -> None:
    root = ProfileSecretSelection(ProfileSecretChannel.FILE_DESCRIPTOR, descriptor=7)

    with pytest.raises(CliRefusedBoundaryError) as caught:
        _preflight_sources(
            root=root,
            leaf=MachineSecretSelection(MachineSecretChannel.FILE_DESCRIPTOR, descriptor=7),
        )
    assert caught.value.translated_message is not None
    assert caught.value.translated_message.endswith("profile_secrets_fd_collision")

    _preflight_sources(
        root=root,
        leaf=MachineSecretSelection(MachineSecretChannel.FILE_DESCRIPTOR, descriptor=8),
    )


def test_graph_postures_keep_rotation_self_authenticating() -> None:
    rotation = _leaf("config.passphrase.change")
    show = _leaf("config.profile.show")

    assert rotation.profile_authentication is ProfileAuthenticationPosture.SELF_AUTHENTICATING
    assert show.profile_authentication is not ProfileAuthenticationPosture.SELF_AUTHENTICATING


def test_every_resume_refusal_reason_has_an_operator_diagnostic() -> None:
    for reason in ProfileSessionRefusalReason:
        key = session_refusal_translation_key(reason)
        assert key in {
            "cli.config.errors.profile_session_absent",
            "cli.config.errors.profile_session_expired",
        }


@pytest.mark.parametrize("language", tuple(OutputLanguage))
def test_root_profile_authentication_diagnostics_are_localised(language: OutputLanguage) -> None:
    with override_settings(cadrumo_output_language=language):
        with pytest.raises(CliRefusedBoundaryError) as caught:
            _preflight_sources(
                root=ProfileSecretSelection(ProfileSecretChannel.STDIN),
                leaf=MachineSecretSelection(MachineSecretChannel.STDIN),
            )
        rendered = render_error_payload(caught.value, as_json=True)
    payload = json.loads(rendered)
    assert "profile_secrets_stdin_collision" not in payload["error"]["message"]
    assert "profile_passphrase" not in rendered


def test_non_persistence_notice_is_delivered_on_a_post_login_refusal() -> None:
    drain_profile_authentication_notices()
    stage_profile_session_not_persisted_notice()
    rendered = render_error_payload(
        CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.profile_secrets_unused"
        ),
        as_json=True,
        command="config.profile.show",
    )
    payload = json.loads(rendered)
    assert [notice["code"] for notice in payload["notices"]] == [
        "config.login.session_not_persisted"
    ]
    assert payload["error"]["code"] == "REFUSED_CLI_BOUNDARY"
    assert drain_profile_authentication_notices() == ()


def test_non_persistence_notice_uses_the_notice_transport_in_text_refusals() -> None:
    drain_profile_authentication_notices()
    stage_profile_session_not_persisted_notice()
    rendered = render_error_payload(
        CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.profile_secrets_unused"
        ),
        as_json=False,
        command="config.profile.show",
    )
    assert rendered.startswith("notice\tconfig.login.session_not_persisted\t")
    assert drain_profile_authentication_notices() == ()


@pytest.mark.parametrize("as_json", (True, False))
def test_click_terminal_refusal_drains_the_notice_once(as_json: bool) -> None:
    drain_profile_authentication_notices()
    stage_profile_session_not_persisted_notice()
    arguments = ["config", "profile", "show", "--not-a-real-option"]
    if as_json:
        arguments[:0] = ["--format", "json"]
    refused = invoke_cached_cli(arguments)
    assert refused.exit_code == 2
    assert refused.output.count("config.login.session_not_persisted") == 1

    next_refusal = invoke_cached_cli(arguments)
    assert next_refusal.exit_code == 2
    assert "config.login.session_not_persisted" not in next_refusal.output


def test_windows_handle_bootstrap_does_not_claim_numeric_fd_inheritance_on_posix() -> None:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        read_descriptor, write_descriptor = os.pipe()
        os.close(write_descriptor)
        import msvcrt

        source_handle = msvcrt.get_osfhandle(read_descriptor)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]  # reason: Windows-only HANDLE ownership proof
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.DuplicateHandle.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        kernel32.DuplicateHandle.restype = wintypes.BOOL
        process = kernel32.GetCurrentProcess()
        inherited_handle = wintypes.HANDLE()
        duplicated = kernel32.DuplicateHandle(
            process,
            wintypes.HANDLE(source_handle),
            process,
            ctypes.byref(inherited_handle),
            0,
            True,
            2,  # DUPLICATE_SAME_ACCESS
        )
        os.close(read_descriptor)
        assert duplicated
        assert inherited_handle.value is not None
        descriptor = descriptor_from_inherited_handle(inherited_handle.value)
        assert descriptor >= 0
        os.close(descriptor)
    else:
        with pytest.raises(RuntimeError, match="only available on Windows"):
            descriptor_from_inherited_handle(7)
