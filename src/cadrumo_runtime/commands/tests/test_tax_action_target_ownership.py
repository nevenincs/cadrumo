"""Runtime authority commands retain their own action and secret-admission contracts."""

from __future__ import annotations

from uuid import uuid4

import pytest
import typer

from cadrumo.application.cli_exception_preconditions import nested_terminal_precondition_verdict
from cadrumo.application.operator_surface.action_targets import ACTION_TARGETS
from cadrumo.core.operator_action_enums import ActionConditionality
from cadrumo.core.output_rendering import OutputFormat
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.secret_contracts import MachineSecretChannelKind
from cadrumo_client.commands.shared_contracts import DefaultKind
from cadrumo_client.contracts.command_ports import ProfileAuthenticationPosture
from cadrumo_client.contracts.command_program import CommandProgram

from .. import profile_admission
from ..command_specs import RUNTIME_COMMAND_GRAPH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_external_operator_actions_resolve_to_the_runtime_graph_definitions() -> None:
    targets = tuple(target for target in ACTION_TARGETS if target.program is CommandProgram.AUTHENTICATION)
    assert {target.command_key for target in targets} == {
        "config.auth.configure",
        "config.auth.diagnostics.view",
        "config.auth.login",
    }
    for target in targets:
        node = RUNTIME_COMMAND_GRAPH.find_schema_identity(target.command_key)
        assert node is not None, target.command_key
        assert node.path == (CommandProgram.AUTHENTICATION.executable_name, *target.cli_path)
        assert node.spec.result_schema.target is not None
        assert node.spec.result_schema.target.qualname == target.result_schema
        assert (
            tuple(p.name for p in node.spec.parameters if p.default.kind is DefaultKind.REQUIRED)
            == target.required_inputs
        )


def test_graph_postures_keep_rotation_self_authenticating() -> None:
    rotation = RUNTIME_COMMAND_GRAPH.by_schema_identity()["config.passphrase.change"]
    assert rotation.profile_authentication is ProfileAuthenticationPosture.SELF_AUTHENTICATING


def test_runtime_machine_secret_inventory_remains_leaf_only_and_scope_disjoint() -> None:
    adopters = tuple(node for node in RUNTIME_COMMAND_GRAPH.nodes() if node.spec.machine_secret is not None)
    required_owners = {
        "config.passphrase.change",
        "config.passphrase.reset",
        "config.profile.recovery.enable",
        "config.profile.recovery.disable",
        "config.profile.resume",
        "config.profile.automation.approve",
        "config.profile.automation.create",
        "config.profile.automation.change",
        "config.auth.certificate.secret.set",
    }
    assert required_owners == {node.spec.result_schema.identity for node in adopters}
    for node in adopters:
        assert node.spec.kind.value == "leaf"
        channels = {
            p.machine_secret_channel
            for p in node.spec.parameters
            if isinstance(p, OptionSpec) and p.machine_secret_channel is not None
        }
        assert channels == {MachineSecretChannelKind.STDIN, MachineSecretChannelKind.FILE_DESCRIPTOR}
        assert all(getattr(p, "profile_secret_channel", None) is None for p in node.spec.parameters)


@pytest.mark.parametrize(
    ("identity", "method", "credential_reference", "root_stdin"),
    (
        ("config.profile.resume", "api-key", True, False),
        ("config.passphrase.change", "password", False, True),
    ),
)
def test_self_authenticating_leaves_reject_root_sources_before_profile_or_secret_reads(
    monkeypatch: pytest.MonkeyPatch,
    identity: str,
    method: str,
    credential_reference: bool,
    root_stdin: bool,
) -> None:
    app = typer.Typer()

    @app.command()
    def noop() -> None:
        return

    ctx = typer.Context(typer.main.get_command(app))
    profile_admission.bind_runtime_root_context(
        ctx,
        language=None,
        profile=None,
        profile_secrets_stdin=root_stdin,
        profile_secrets_fd=None,
        profile_auth_method=method,
        profile_credential_ref=uuid4() if credential_reference else None,
        format_=OutputFormat.TEXT,
        quiet=False,
        verbose=False,
        debug=False,
    )
    monkeypatch.setattr(
        profile_admission, "resolve_login_target", lambda *_args: pytest.fail("refusal resolved a profile")
    )
    monkeypatch.setattr(
        profile_admission, "_open_recovery_profile", lambda *_args: pytest.fail("refusal opened a recovery connection")
    )
    monkeypatch.setattr(
        profile_admission,
        "read_profile_secret_payload",
        lambda *_args, **_kwargs: pytest.fail("refusal read an inapplicable root secret"),
    )
    node = RUNTIME_COMMAND_GRAPH.find_schema_identity(identity)
    assert node is not None
    try:
        with pytest.raises(CliRefusedBoundaryError) as caught:
            profile_admission.preflight_runtime_command(ctx, node.spec, {})
        message = caught.value.translated_message
        assert isinstance(message, str)
        assert message.endswith("profile_secrets_inapplicable")
        verdict = nested_terminal_precondition_verdict(caught.value)
        assert verdict is not None
        assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
        assert verdict.evidence[0].values == {"profile_authentication_input": "not_applicable", "input_read": False}
    finally:
        ctx.close()
