"""An explicit CLI API key uses only the protected runtime login path."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from uuid import uuid4

import pytest
import typer

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.operator_surface.command_ports import ProfileAuthenticationPosture
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr

from .. import _profile_authentication_gate as gate
from .. import _profile_session_gate as session_gate
from .. import runtime_profile_admission
from .._profile_authentication_contract import (
    ProfileAuthenticationMethod,
    ProfileAuthenticationSecrets,
    ProfileSecretSourceOptions,
    profile_authentication_posture,
)
from ..command_specs import COMMAND_GRAPH
from ..config.secure_input import ProfileSecretChannel, ProfileSecretSelection
from ..errors import CliRefusedBoundaryError
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_API_AUTH_KEYS = (
    "cli.config.custody.profile_auth_method_help",
    "cli.config.custody.errors.profile_secrets_api_key_requires_channel",
    "cli.config.custody.errors.profile_secrets_api_key_inapplicable",
    "cli.config.custody.errors.profile_secrets_method_mismatch",
)


@pytest.mark.parametrize("language", tuple(OutputLanguage))
def test_api_auth_help_and_refusals_are_localised(language: OutputLanguage) -> None:
    for key in _API_AUTH_KEYS:
        value = tr(key, locale=language)
        assert value and value != key


def _context(source: ProfileSecretSourceOptions) -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None:
        return

    context = typer.Context(typer.main.get_command(app))
    cast("dict[str, object]", context.ensure_object(dict))["profile_secret_source"] = source
    return context


@pytest.mark.parametrize(
    "command",
    (
        ("config", "profile", "view"),
        ("config", "profile", "resume"),
        ("config", "profile", "archive", "export", "--output", "ignored.bundle"),
    ),
)
def test_api_method_without_protected_root_channel_refuses_before_admission(command: tuple[str, ...]) -> None:
    result = invoke_cached_cli(("--profile-auth-method", "api-key", *command))
    assert result.exit_code == 2
    assert "profile_secrets_api_key_requires_channel" not in result.output


def test_api_method_refuses_local_leaf_before_reading_the_root_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """A verb invoked in a mode that opens no runtime client refuses the key.

    ``app modelo work report verify --document-only`` authenticates against
    the runtime in its ordinary mode, so the posture alone does not settle
    this. The invocation is what decides: a local run has no protected runtime
    login for the key to reach, and the refusal must land before the root
    secret is read or a local session is admitted.
    """
    events: list[str] = []
    monkeypatch.setattr(gate, "_read_and_stage_leaf", lambda **_kwargs: events.append("read_leaf"))
    monkeypatch.setattr(
        session_gate, "activate_profile_session", lambda *_args, **_kwargs: events.append("admit_local")
    )
    source = ProfileSecretSourceOptions(stdin=True, method=ProfileAuthenticationMethod.API_KEY)
    with pytest.raises(CliRefusedBoundaryError) as refused:
        gate.preflight_parsed_leaf(
            _context(source),
            graph=COMMAND_GRAPH,
            spec=COMMAND_GRAPH.node("app_modelo_work_report_verify").spec,
            arguments={"document_only": True},
        )
    assert refused.value.translated_message is not None
    assert refused.value.translated_message.endswith("profile_secrets_api_key_inapplicable")
    assert events == []


def test_runtime_leaf_receives_explicit_api_method_before_local_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[object, ...]] = []
    monkeypatch.setattr("cadrumo.application.cli_provisioning.provision_cli_storage", lambda **_kwargs: None)
    monkeypatch.setattr(session_gate, "normalize_ambient_profile", lambda _ctx: None)
    monkeypatch.setattr("cadrumo.core.bucket_pointer.resolve_active_bucket_id", lambda: str(uuid4()))
    monkeypatch.setattr(gate, "_diagnose_unregistered_profile", lambda **_kwargs: False)
    monkeypatch.setattr(
        runtime_profile_admission,
        "activate_runtime_profile",
        lambda _ctx, **kwargs: events.append((kwargs["root_selection"], kwargs["method"])),
    )
    source = ProfileSecretSourceOptions(stdin=True, method=ProfileAuthenticationMethod.API_KEY)
    # A grant change requires a stored reference for its independent fresh
    # reconciliation, so the raw-key route remains available to other leaves.
    raw_key_leaves = gate._RUNTIME_PROFILE_KEYS - {"config_profile_automation_change"}
    # Two leaves gate their own dispatch before the secret source is read: a
    # discard demands its audited confirmation, and a censo import reaches the
    # runtime only when it applies rather than previews. Supplying both is how
    # the invocation gets as far as runtime admission, which is the subject
    # here; neither value relaxes the authentication route under test.
    confirmations: Mapping[str, object] = {"confirmed": True, "apply": True}
    for key in raw_key_leaves:
        spec = COMMAND_GRAPH.node(key).spec
        assert profile_authentication_posture(COMMAND_GRAPH.node(key)) is ProfileAuthenticationPosture.RESUME_FALLBACK
        gate.preflight_parsed_leaf(
            _context(source), graph=COMMAND_GRAPH, spec=spec, arguments=cast(Mapping[str, object], confirmations)
        )
    assert events == [(ProfileSecretSelection(ProfileSecretChannel.STDIN), ProfileAuthenticationMethod.API_KEY)] * len(
        raw_key_leaves
    )


class _LoginWitness:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.secret: bytearray | None = None

    def resume_receipt(self) -> None:
        self.calls.append("receipt")
        raise AssertionError("API authentication must not attempt a human receipt")

    def login_password(self, _secret: bytearray) -> None:
        self.calls.append("password")
        raise AssertionError("API authentication must not attempt password login")

    def login_api_key(self, secret: bytearray) -> None:
        self.calls.append("api_key")
        self.secret = secret
        assert bytes(secret) == b"synthetic-api-key"


def test_api_login_consumes_once_and_wipes_the_mutable_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    witness = _LoginWitness()
    monkeypatch.setattr(
        runtime_profile_admission,
        "read_profile_secret_payload",
        lambda _model, *, selection: ProfileAuthenticationSecrets.model_validate({"api_key": "synthetic-api-key"}),
    )
    runtime_profile_admission._authenticate(
        _context(ProfileSecretSourceOptions(method=ProfileAuthenticationMethod.API_KEY)),
        cast(RuntimeFrontendClient, witness),
        root_selection=ProfileSecretSelection(ProfileSecretChannel.STDIN),
        profile_label=None,
        method=ProfileAuthenticationMethod.API_KEY,
    )
    assert witness.calls == ["api_key"]
    assert witness.secret == bytearray(len(b"synthetic-api-key"))


@pytest.mark.parametrize(
    ("method", "field"),
    (
        (ProfileAuthenticationMethod.PASSWORD, "api_key"),
        (ProfileAuthenticationMethod.API_KEY, "profile_passphrase"),
    ),
)
def test_selected_method_refuses_the_other_valid_payload(
    monkeypatch: pytest.MonkeyPatch,
    method: ProfileAuthenticationMethod,
    field: str,
) -> None:
    witness = _LoginWitness()
    monkeypatch.setattr(
        runtime_profile_admission,
        "read_profile_secret_payload",
        lambda _model, *, selection: ProfileAuthenticationSecrets.model_validate({field: "synthetic-secret"}),
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        if method is ProfileAuthenticationMethod.API_KEY:
            runtime_profile_admission._authenticate(
                _context(ProfileSecretSourceOptions(method=method)),
                cast(RuntimeFrontendClient, witness),
                root_selection=ProfileSecretSelection(ProfileSecretChannel.STDIN),
                profile_label=None,
                method=method,
            )
        else:
            runtime_profile_admission._password(
                cast(RuntimeFrontendClient, witness), selection=ProfileSecretSelection(ProfileSecretChannel.STDIN)
            )
    assert refused.value.translated_message is not None
    assert refused.value.translated_message.endswith("profile_secrets_method_mismatch")
    assert witness.calls == []
