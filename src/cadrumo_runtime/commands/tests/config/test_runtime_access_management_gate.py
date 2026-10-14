"""Runtime profile-access commands enforce their declared admission posture."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import typer

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.core.output_rendering import OutputFormat
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.contracts.command_ports import ProfileAuthenticationPosture
from cadrumo_runtime.commands import profile_admission as admission
from cadrumo_runtime.commands.access_management_specs import RUNTIME_ACCESS_MANAGEMENT_COMMAND_SPECS
from cadrumo_runtime.commands.command_specs import RUNTIME_COMMAND_GRAPH

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


def _context(
    *,
    profile: str | None = None,
    profile_secrets_stdin: bool = False,
    profile_secrets_fd: int | None = None,
) -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None:
        return

    ctx = typer.Context(typer.main.get_command(app))
    admission.bind_runtime_root_context(
        ctx,
        language=None,
        profile=profile,
        profile_secrets_stdin=profile_secrets_stdin,
        profile_secrets_fd=profile_secrets_fd,
        profile_auth_method="password",
        profile_credential_ref=None,
        format_=OutputFormat.TEXT,
        quiet=False,
        verbose=False,
        debug=False,
    )
    return ctx


def test_management_graph_declares_separate_recovery_and_authenticated_routes() -> None:
    specs = {spec.key: spec for spec in RUNTIME_ACCESS_MANAGEMENT_COMMAND_SPECS}
    for key in (
        "config_profile_sessions",
        "config_profile_automation_list",
        "config_profile_automation_inspect",
        "config_profile_automation_approve",
        "config_profile_automation_decline",
        "config_profile_automation_deny",
        "config_profile_lock",
    ):
        assert RUNTIME_COMMAND_GRAPH.node(key).spec is specs[key]
        assert specs[key].profile_authentication is ProfileAuthenticationPosture.RESUME_FALLBACK

    resume = RUNTIME_COMMAND_GRAPH.node("config_profile_resume").spec
    assert resume.profile_authentication is ProfileAuthenticationPosture.SELF_AUTHENTICATING
    assert resume.machine_secret is not None
    assert tuple(field.name for field in resume.machine_secret.variants[0].fields) == ("passphrase",)


@pytest.mark.parametrize("locale", tuple(OutputLanguage))
def test_management_help_and_refusals_have_real_locale_values(locale: OutputLanguage) -> None:
    for key in _MANAGEMENT_KEYS:
        value = tr(key, locale=locale)
        assert value and value != key


def test_resume_binds_the_explicit_profile_through_runtime_admission(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = uuid4()
    events: list[tuple[str, UUID]] = []
    monkeypatch.setattr(
        admission,
        "resolve_login_target",
        lambda label: SimpleNamespace(bucket_id=profile_id, label=label),
    )
    monkeypatch.setattr(
        admission,
        "_open_recovery_profile",
        lambda _ctx, target: events.append(("bind_recovery_profile", target)),
    )
    ctx = _context(profile="Selected profile")
    try:
        spec = RUNTIME_COMMAND_GRAPH.node("config_profile_resume").spec
        admission.preflight_runtime_command(ctx, spec, {"secrets_stdin": False, "secrets_fd": None, "grant": ()})
        assert events == [("bind_recovery_profile", profile_id)]
    finally:
        ctx.close()


def test_resume_rejects_root_password_source_before_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    monkeypatch.setattr(admission, "_open_recovery_profile", lambda *_args: events.append("bind"))
    ctx = _context(profile_secrets_stdin=True)
    try:
        with pytest.raises(CliRefusedBoundaryError) as refused:
            admission.preflight_runtime_command(
                ctx,
                RUNTIME_COMMAND_GRAPH.node("config_profile_resume").spec,
                {"secrets_stdin": True, "secrets_fd": None, "grant": ()},
            )
        assert refused.value.translated_message is not None
        assert refused.value.translated_message.endswith("profile_secrets_inapplicable")
        assert events == []
    finally:
        ctx.close()


def test_approval_rejects_root_and_leaf_stdin_collision_before_profile_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    from cadrumo_client.transport import installed_client

    monkeypatch.setattr(installed_client, "open_installed_client", lambda **_kwargs: events.append("open"))
    ctx = _context(profile_secrets_stdin=True)
    try:
        spec = RUNTIME_COMMAND_GRAPH.node("config_profile_automation_approve").spec
        with pytest.raises(CliRefusedBoundaryError) as refused:
            admission.preflight_runtime_command(
                ctx,
                spec,
                {"secrets_stdin": True, "secrets_fd": None},
            )
        assert refused.value.translated_message is not None
        assert refused.value.translated_message.endswith("profile_secrets_stdin_collision")
        assert events == []
    finally:
        ctx.close()


def test_resume_uses_the_canonical_runtime_command_path() -> None:
    assert RUNTIME_COMMAND_GRAPH.node("config_profile_resume").path == (
        "cadrumo-runtime",
        "config",
        "profile",
        "resume",
    )
