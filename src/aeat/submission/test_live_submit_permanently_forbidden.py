"""Regression guards for permanent AEAT remote-write deletion."""

from __future__ import annotations

import inspect
import sys
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ..auth import AeatAccessGate
from ..cli import app as root_app
from ..cli.submission import app as submission_app
from ..config import Settings
from . import (
    AuthProviderDescription,
    AuthProviderKind,
    LiveSubmitForbiddenError,
    SubmissionEngine,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


class _AuthProvider:
    kind = AuthProviderKind.CERTIFICATE

    def describe(self) -> AuthProviderDescription:
        return AuthProviderDescription(
            kind=self.kind,
            label="Regression certificate",
            configured=True,
            available=True,
            identity_nif="X1234567L",
            subject="CN=Regression",
            expires_on=date(2099, 12, 31),
            health_summary="OK:26800",
        )


class _Deadlines:
    def is_window_open(self, modelo: str, period: str, today: date) -> bool:
        return True


def _engine(tmp_path: Path) -> SubmissionEngine:
    return SubmissionEngine(
        auth_provider=_AuthProvider(),
        deadline_checker=_Deadlines(),
        settings=Settings(aeat_submissions_dir=tmp_path / "submissions"),
    )


def test_access_gate_live_write_is_permanent_refusal() -> None:
    with pytest.raises(LiveSubmitForbiddenError, match="permanently forbidden"):
        AeatAccessGate(Settings()).require_live_write()


def test_settings_expose_no_live_submit_env_vars() -> None:
    live_submit_names = {name for name in Settings.env_var_names() if "LIVE_SUBMIT" in name}
    assert live_submit_names == set()


def test_submission_cli_has_no_submit_or_dry_run_command() -> None:
    runner = CliRunner()
    for command in ("submit", "dry-run"):
        result = runner.invoke(root_app, ["submission", command])
        assert result.exit_code == 2, result.output
        assert "no such command" in result.output.lower()
    registered = {command.name for command in submission_app.registered_commands}
    assert "submit" not in registered
    assert "dry-run" not in registered


def test_engine_transport_methods_are_absent(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    assert not hasattr(engine, "submit_draft")
    assert not hasattr(engine, "submit_amendment")
    assert not (tmp_path / "submissions").exists()


def test_submission_package_exports_no_submitter_or_browser_contract() -> None:
    package_name = __package__
    assert package_name is not None
    submission = sys.modules[package_name]
    assert not hasattr(submission, "Submitter")
    assert not hasattr(submission, "Modelo130Submitter")
    assert not hasattr(submission, "BrowserSessionLike")


def test_engine_source_contains_no_remote_write_dispatch_fragments() -> None:
    banned_fragments = (
        "navigate(",
        ".fill(",
        ".click(",
        "button#firmar-y-enviar",
        ".post(",
        "request(",
    )
    source = inspect.getsource(SubmissionEngine)
    for fragment in banned_fragments:
        assert fragment not in source


def test_submitter_modules_are_absent() -> None:
    assert not (Path(__file__).resolve().parent / "_submitters" / "modelo130.py").exists()
    assert not (Path(__file__).resolve().parent / "_submitters" / "_contract.py").exists()
