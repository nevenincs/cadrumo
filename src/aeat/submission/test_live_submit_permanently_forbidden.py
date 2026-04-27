"""Regression guards for the permanent live-submit prohibition (#432)."""

from __future__ import annotations

import inspect
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ..auth import AeatAccessGate
from ..cli import app as root_app
from ..cli.submission import app as submission_app
from ..config import Settings
from . import (
    AuthProviderDescription,
    AuthProviderKind,
    CasillaCatalogue,
    CasillaInputKind,
    CasillaRecord,
    DeadlineWindowChecker,
    DraftLoader,
    Justificante,
    LiveSubmitForbiddenError,
    Modelo130Submitter,
    Portal,
    PortalCatalogue,
    SubmissionEngine,
    Submitter,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


class _Session:
    async def navigate(self, url: str) -> None: ...

    async def fill(self, selector: str, value: str) -> None: ...

    async def click(self, selector: str) -> None: ...

    async def screenshot(self, path: Path) -> None: ...

    async def trace_start(self, name: str) -> None: ...

    async def trace_stop(self, path: Path) -> None: ...

    async def snapshot_form_state(self, path: Path) -> None: ...


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


class _Portals(PortalCatalogue):
    def portal_for(self, modelo: str) -> Portal:
        return Portal(modelo=modelo, presentation_url="https://sede.example.test/130")


class _Deadlines(DeadlineWindowChecker):
    def is_window_open(self, modelo: str, period: str, today: date) -> bool:
        return True


class _Casillas(CasillaCatalogue):
    def casillas_for_modelo(self, modelo: str) -> tuple[CasillaRecord, ...]:
        return (
            CasillaRecord(
                id="01",
                label={"en": "one", "es": "uno", "hu": "egy"},
                input_kind=CasillaInputKind.NUMBER,
            ),
        )

    def get(self, casilla_id: str) -> CasillaRecord:
        return self.casillas_for_modelo("130")[0]


class _Drafts(DraftLoader):
    def load(self, draft_path: Path) -> Any:
        raise NotImplementedError


class _Parser:
    def parse(self, raw_bytes: bytes) -> Justificante:
        return Justificante(csv="CSV-1", pdf_path=Path("var/j.pdf"))


def _base_kwargs(tmp_path: Path) -> dict[str, Any]:
    return {
        "browser_session_factory": _Session,
        "auth_provider": _AuthProvider(),
        "portal_catalogue": _Portals(),
        "draft_loader": _Drafts(),
        "deadline_checker": _Deadlines(),
        "casilla_catalogue": _Casillas(),
        "justificante_parser": _Parser(),
        "submitters": {},
        "settings": Settings(
            aeat_submissions_dir=tmp_path / "submissions",
            aeat_submission_browser_trace_dir=tmp_path / "traces",
        ),
    }


def test_engine_rejects_historical_live_transport_keyword(tmp_path: Path) -> None:
    with pytest.raises(LiveSubmitForbiddenError, match="permanently forbidden"):
        SubmissionEngine(**_base_kwargs(tmp_path), live_transport_supported=True)


def test_engine_rejects_legacy_live_transport_keyword_even_when_false(tmp_path: Path) -> None:
    with pytest.raises(LiveSubmitForbiddenError, match="permanently forbidden"):
        SubmissionEngine(**_base_kwargs(tmp_path), live_transport_supported=False)


def test_engine_methods_do_not_reference_live_submit_dispatch() -> None:
    banned_fragments = (
        "button#firmar-y-enviar",
        ".submit(",
        "POST ",
        "POST\\n",
    )
    for _, member in vars(SubmissionEngine).items():
        if not inspect.isfunction(member):
            continue
        source = inspect.getsource(member)
        for fragment in banned_fragments:
            assert fragment not in source, (
                f"{member.__qualname__} unexpectedly references live-submit fragment {fragment!r}"
            )


def test_concrete_submitters_do_not_reintroduce_live_submit_dispatch() -> None:
    banned_fragments = (
        "button#firmar-y-enviar",
        ".submit(",
        "POST ",
        "POST\\n",
    )
    concrete_submitters = tuple(
        submitter_cls
        for submitter_cls in Submitter.__subclasses__()
        if submitter_cls is Modelo130Submitter or submitter_cls.__module__.startswith("aeat.submission")
    )
    assert concrete_submitters
    for submitter_cls in concrete_submitters:
        assert "submit" not in submitter_cls.__dict__, (
            f"{submitter_cls.__qualname__} reintroduced a live submit() surface"
        )
        for _, member in vars(submitter_cls).items():
            if not inspect.isfunction(member):
                continue
            source = inspect.getsource(member)
            for fragment in banned_fragments:
                assert fragment not in source, (
                    f"{member.__qualname__} unexpectedly references live-submit fragment {fragment!r}"
                )


def test_access_gate_live_write_is_permanent_refusal() -> None:
    with pytest.raises(LiveSubmitForbiddenError, match="permanently forbidden"):
        AeatAccessGate(Settings()).require_live_write()


def test_settings_expose_no_live_submit_env_vars() -> None:
    live_submit_names = {name for name in Settings.env_var_names() if "LIVE_SUBMIT" in name}
    assert live_submit_names == set()


def test_submission_cli_has_no_submit_command() -> None:
    runner = CliRunner()
    result = runner.invoke(root_app, ["submission", "submit"])
    assert result.exit_code == 2, result.output
    assert "no such command" in result.output.lower()
    registered = {command.name for command in submission_app.registered_commands}
    assert "submit" not in registered
