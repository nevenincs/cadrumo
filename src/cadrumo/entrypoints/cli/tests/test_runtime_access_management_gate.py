"""Parsed CLI lifecycle commands use their declared runtime admission posture."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from uuid import uuid4

import pytest
import typer

from cadrumo.application.operator_surface.command_ports import ProfileAuthenticationPosture
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr

from .. import _profile_authentication_gate as gate
from .. import _profile_session_gate as session_gate
from .. import runtime_profile_admission
from .._profile_authentication_contract import ProfileSecretSourceOptions, profile_authentication_posture
from ..command_specs import COMMAND_GRAPH
from ..errors import CliRefusedBoundaryError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MANAGEMENT_KEYS = (
    "cli.config.profile.automation.help",
    "cli.config.profile.automation.deny.help",
    "cli.config.profile.automation.deny.kind_help",
    "cli.config.profile.automation.deny.target_help",
    "cli.config.profile.automation.deny.target_mismatch",
    "cli.config.profile.automation.list.help",
    "cli.config.profile.automation.inspect.help",
    "cli.config.profile.automation.inspect.request_help",
    "cli.config.profile.automation.approve.help",
    "cli.config.profile.automation.approve.request_help",
    "cli.config.profile.automation.approve.digest_help",
    "cli.config.profile.automation.decline.help",
    "cli.config.profile.automation.decline.request_help",
    "cli.config.profile.automation.decline.digest_help",
    "cli.config.profile.automation.review_not_found",
    "cli.config.profile.automation.review_digest_mismatch",
    "cli.config.profile.sessions.help",
    "cli.config.profile.lock.help",
    "cli.config.profile.lock.all_help",
    "cli.config.profile.resume.help",
    "cli.config.profile.resume.grant_help",
)


def _context() -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None:
        return

    return typer.Context(typer.main.get_command(app))


def test_management_graph_declares_separate_recovery_and_authenticated_routes() -> None:
    for key in (
        "config_profile_sessions",
        "config_profile_automation_list",
        "config_profile_automation_inspect",
        "config_profile_automation_approve",
        "config_profile_automation_decline",
        "config_profile_automation_deny",
        "config_profile_lock",
    ):
        node = COMMAND_GRAPH.node(key)
        assert profile_authentication_posture(node) is ProfileAuthenticationPosture.RESUME_FALLBACK
    resume = COMMAND_GRAPH.node("config_profile_resume")
    assert profile_authentication_posture(resume) is ProfileAuthenticationPosture.SELF_AUTHENTICATING
    assert resume.spec.machine_secret is not None
    assert tuple(field.name for field in resume.spec.machine_secret.variants[0].fields) == ("passphrase",)


@pytest.mark.parametrize("locale", tuple(OutputLanguage))
def test_management_help_and_refusals_have_real_locale_values(locale: OutputLanguage) -> None:
    for key in _MANAGEMENT_KEYS:
        value = tr(key, locale=locale)
        assert value and value != key


def test_resume_stages_one_leaf_payload_before_unadmitted_runtime_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = str(uuid4())
    events: list[str] = []
    monkeypatch.setattr(
        "cadrumo.application.cli_provisioning.provision_cli_storage",
        lambda *, writes_state: events.append("provision"),
    )
    monkeypatch.setattr(session_gate, "normalize_ambient_profile", lambda _ctx: None)
    monkeypatch.setattr("cadrumo.core.bucket_pointer.resolve_active_bucket_id", lambda: profile_id)
    monkeypatch.setattr(gate, "_read_and_stage_leaf", lambda **_kwargs: events.append("stage"))

    def bind(_ctx: typer.Context, *, target_bucket_id: str | None, root_selection: object) -> None:
        assert target_bucket_id is None
        assert root_selection is None
        events.append("bind_unadmitted")

    monkeypatch.setattr(runtime_profile_admission, "activate_runtime_recovery", bind)
    spec = COMMAND_GRAPH.node("config_profile_resume").spec
    gate.preflight_parsed_leaf(
        _context(),
        graph=COMMAND_GRAPH,
        spec=spec,
        arguments={"secrets_stdin": True, "secrets_fd": None, "grant": ()},
    )
    assert events == ["provision", "stage", "bind_unadmitted"]


@pytest.mark.parametrize(
    ("source", "arguments", "suffix"),
    (
        (
            ProfileSecretSourceOptions(stdin=True),
            {"secrets_stdin": True, "secrets_fd": None},
            "profile_secrets_stdin_collision",
        ),
        (
            ProfileSecretSourceOptions(descriptor=7),
            {"secrets_stdin": False, "secrets_fd": 8},
            "profile_secrets_inapplicable",
        ),
    ),
)
def test_resume_rejects_root_password_source_before_leaf_read(
    monkeypatch: pytest.MonkeyPatch,
    source: ProfileSecretSourceOptions,
    arguments: Mapping[str, object],
    suffix: str,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(gate, "_read_and_stage_leaf", lambda **_kwargs: events.append("stage"))
    ctx = _context()
    cast("dict[str, object]", ctx.ensure_object(dict))["profile_secret_source"] = source
    with pytest.raises(CliRefusedBoundaryError) as refused:
        gate.preflight_parsed_leaf(
            ctx, graph=COMMAND_GRAPH, spec=COMMAND_GRAPH.node("config_profile_resume").spec, arguments=arguments
        )
    assert refused.value.translated_message is not None
    assert refused.value.translated_message.endswith(suffix)
    assert events == []


def test_approval_rejects_root_and_leaf_stdin_collision_before_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(gate, "_read_and_stage_leaf", lambda **_kwargs: events.append("leaf"))
    monkeypatch.setattr(
        runtime_profile_admission,
        "activate_runtime_profile",
        lambda *_args, **_kwargs: events.append("admit"),
    )
    ctx = _context()
    cast("dict[str, object]", ctx.ensure_object(dict))["profile_secret_source"] = ProfileSecretSourceOptions(stdin=True)
    with pytest.raises(CliRefusedBoundaryError) as refused:
        gate.preflight_parsed_leaf(
            ctx,
            graph=COMMAND_GRAPH,
            spec=COMMAND_GRAPH.node("config_profile_automation_approve").spec,
            arguments={"secrets_stdin": True, "secrets_fd": None},
        )
    assert refused.value.translated_message is not None
    assert refused.value.translated_message.endswith("profile_secrets_stdin_collision")
    assert events == []
