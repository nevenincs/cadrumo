"""The workflow actionlint check must not provision its executable."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev import actionlint

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_check_path_reports_remediation_without_calling_installer(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing check executable is a read-only failure, not an implicit install."""
    installer_called = False

    def fail_if_called() -> Path:
        nonlocal installer_called
        installer_called = True
        raise AssertionError("workflow checks must not provision actionlint")

    monkeypatch.setattr(actionlint, "find", lambda: None)
    monkeypatch.setattr(actionlint, "ensure", fail_if_called)

    assert actionlint.main([]) == actionlint.TOOL_MISSING
    assert installer_called is False
    assert "just setup-repository-tools" in capsys.readouterr().err
