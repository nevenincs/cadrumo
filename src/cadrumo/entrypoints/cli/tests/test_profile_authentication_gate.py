"""Focused parsed-dispatch proof for the root profile-authentication gate."""

from __future__ import annotations

import pytest

from .._command_spec import ProfileAuthenticationPosture
from .._command_specs import COMMAND_GRAPH
from .._config._secure_input import (
    MachineSecretChannel,
    MachineSecretSelection,
    ProfileSecretChannel,
    ProfileSecretSelection,
)
from .._errors import CliRefusedBoundaryError
from .._profile_authentication_gate import _preflight_sources

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _leaf(identity: str):
    return COMMAND_GRAPH.by_schema_identity()[identity]


def test_cross_scope_stdin_collision_refuses_before_any_read() -> None:
    root = ProfileSecretSelection(ProfileSecretChannel.STDIN)
    leaf = MachineSecretSelection(MachineSecretChannel.STDIN)

    with pytest.raises(CliRefusedBoundaryError) as caught:
        _preflight_sources(root=root, leaf=leaf)

    assert caught.value.translated_message.endswith("profile_secrets_stdin_collision")


def test_cross_scope_same_descriptor_refuses_but_distinct_descriptors_pass() -> None:
    root = ProfileSecretSelection(ProfileSecretChannel.FILE_DESCRIPTOR, descriptor=7)

    with pytest.raises(CliRefusedBoundaryError) as caught:
        _preflight_sources(
            root=root,
            leaf=MachineSecretSelection(MachineSecretChannel.FILE_DESCRIPTOR, descriptor=7),
        )
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

