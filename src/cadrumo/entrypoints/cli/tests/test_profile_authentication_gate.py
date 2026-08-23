"""Focused parsed-dispatch proof for the root profile-authentication gate."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

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
from .._profile_authentication_gate import _preflight_sources, consume_root_fallback

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


def test_root_fallback_asserts_exact_authenticated_target(monkeypatch: pytest.MonkeyPatch) -> None:
    import cadrumo.adapters.persistence.storage as storage
    import cadrumo.application.user_profile as profiles
    import cadrumo.entrypoints.cli._profile_authentication_gate as gate

    class _Payload:
        profile_passphrase = SimpleNamespace(get_secret_value=lambda: "secret")

    monkeypatch.setattr(gate, "_read_and_stage_leaf", lambda **_kwargs: None)
    monkeypatch.setattr(gate, "ProfileAuthenticationSecrets", _Payload)
    monkeypatch.setattr(gate, "read_profile_secret_payload", lambda *_args, **_kwargs: _Payload())
    monkeypatch.setattr(profiles, "login_profile", lambda **_kwargs: SimpleNamespace(bucket_id="other", session_persisted=True))
    monkeypatch.setattr(storage, "active_bucket_session_serves", lambda _bucket_id: True)
    context = SimpleNamespace(find_root=lambda: SimpleNamespace(ensure_object=lambda _type: {}))

    with pytest.raises(RuntimeError, match="exact requested session"):
        consume_root_fallback(
            cast("object", context),
            bucket_id="target",
            root=ProfileSecretSelection(ProfileSecretChannel.STDIN),
            leaf=None,
            spec=_leaf("config.profile.show"),
            arguments={},
        )


def test_root_fallback_stages_non_persistence_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    import cadrumo.adapters.persistence.storage as storage
    import cadrumo.application.user_profile as profiles
    import cadrumo.entrypoints.cli._profile_authentication_gate as gate

    class _Payload:
        profile_passphrase = SimpleNamespace(get_secret_value=lambda: "secret")

    state: dict[str, object] = {}
    context = SimpleNamespace(find_root=lambda: SimpleNamespace(ensure_object=lambda _type: state))
    monkeypatch.setattr(gate, "_read_and_stage_leaf", lambda **_kwargs: None)
    monkeypatch.setattr(gate, "ProfileAuthenticationSecrets", _Payload)
    monkeypatch.setattr(gate, "read_profile_secret_payload", lambda *_args, **_kwargs: _Payload())
    monkeypatch.setattr(
        profiles,
        "login_profile",
        lambda **_kwargs: SimpleNamespace(bucket_id="target", session_persisted=False),
    )
    monkeypatch.setattr(storage, "active_bucket_session_serves", lambda bucket_id: bucket_id == "target")

    consume_root_fallback(
        cast("object", context),
        bucket_id="target",
        root=ProfileSecretSelection(ProfileSecretChannel.STDIN),
        leaf=None,
        spec=_leaf("config.profile.show"),
        arguments={},
    )

    assert state == {"profile_session_not_persisted": True}
