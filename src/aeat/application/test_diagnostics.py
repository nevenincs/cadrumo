"""Tests for application-owned CLI diagnostics."""

from __future__ import annotations

import pytest

from .diagnostics import build_config_doctor_report, render_config_doctor_text

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_config_doctor_report_contains_registry_and_setup_checks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")

    report = build_config_doctor_report()

    assert report.package_name == "aeat"
    assert report.registry.available is True
    assert report.registry.modelo_count > 0
    assert {check.name for check in report.checks} >= {
        "environment.python",
        "registry.load",
        "secure_state.load",
        "profile.active",
        "auth.provider",
    }
    assert report.overall in {"ok", "warn"}


def test_render_config_doctor_text_is_operator_readable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")

    rendered = render_config_doctor_text(build_config_doctor_report())

    assert "Overall\t" in rendered
    assert "registry.load" in rendered
    assert "Logs\t" in rendered
