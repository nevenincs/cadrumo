"""Real-behavior tests for wizard success-output localization.

Pins that success tab labels and verbs in ``build_wizard_command`` route through
``tr()`` rather than hardcoded English literals.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
import typer

from ....core.i18n import tr
from ....tests.secure_sql import isolated_profile_storage_root
from .._catalogue import SETUP_FLOW
from .._commands import build_wizard_command
from .._persistence import WizardPersistMode

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_QUIET_PROFILE_ARGS = [
    "operator",
    "--quiet",
    "--tax-id",
    "00000000T",
    "--entity-type",
    "natural_person",
    "--name",
    "Operator",
    "--surnames",
    "Tester",
    "--activity",
    "Servicios",
]


@pytest.fixture
def _isolated_backend(tmp_path: Path) -> Iterator[Path]:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


def _wizard_app(mode: WizardPersistMode) -> typer.Typer:
    """Build a minimal Typer app wrapping the wizard command for the given mode."""
    app = typer.Typer()
    cmd = build_wizard_command(SETUP_FLOW, mode=mode)
    app.command()(cmd)
    return app


def _invoke_wizard(mode: WizardPersistMode, args: Sequence[str], capsys: pytest.CaptureFixture[str]) -> str:
    command = typer.main.get_command(_wizard_app(mode))
    command.main(args=list(args), standalone_mode=False)
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out


# Derive expected tab-key labels and verbs from the locale authority.
_EXPECTED_PROFILE_LABEL = tr("application.wizard.output_labels.profile")
_EXPECTED_ACTIVE_PROFILE_LABEL = tr("application.wizard.output_labels.active_profile")
_EXPECTED_STATUS_LABEL = tr("application.wizard.output_labels.status")
_EXPECTED_NEXT_LABEL = tr("application.wizard.output_labels.next")
_EXPECTED_CREATED = tr("wizard.commands.status.created")
_EXPECTED_UPDATED = tr("wizard.commands.status.updated")


def test_wizard_create_status_verb_is_localized(
    _isolated_backend: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Wizard create emits the locale-resolved tab-key and verb, not raw English."""
    output = _invoke_wizard(
        "create",
        _QUIET_PROFILE_ARGS,
        capsys,
    )

    lines = set(output.splitlines())
    assert f"{_EXPECTED_PROFILE_LABEL}\toperator" in output
    assert f"{_EXPECTED_STATUS_LABEL}\t{_EXPECTED_CREATED}" in output
    assert f"{_EXPECTED_ACTIVE_PROFILE_LABEL}\toperator" in output
    assert f"{_EXPECTED_NEXT_LABEL}\t" in output
    # Confirm the raw English literals are absent when locale resolves differently.
    if _EXPECTED_PROFILE_LABEL != "profile":
        assert "profile\toperator" not in lines
    if _EXPECTED_CREATED != "created" or _EXPECTED_STATUS_LABEL != "status":
        assert "status\tcreated" not in lines
    if _EXPECTED_ACTIVE_PROFILE_LABEL != "active_profile":
        assert "active_profile\toperator" not in lines
    if _EXPECTED_NEXT_LABEL != "next":
        assert not any(line.startswith("next\t") for line in lines)


def test_wizard_edit_status_verb_is_localized(
    _isolated_backend: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Wizard edit emits the locale-resolved tab-key and updated verb."""
    # Seed a profile first via create so edit has a target.
    _invoke_wizard(
        "create",
        _QUIET_PROFILE_ARGS,
        capsys,
    )

    output = _invoke_wizard(
        "edit",
        _QUIET_PROFILE_ARGS,
        capsys,
    )

    lines = set(output.splitlines())
    assert f"{_EXPECTED_PROFILE_LABEL}\toperator" in output
    assert f"{_EXPECTED_STATUS_LABEL}\t{_EXPECTED_UPDATED}" in output
    assert f"{_EXPECTED_NEXT_LABEL}\t" in output
    if _EXPECTED_PROFILE_LABEL != "profile":
        assert "profile\toperator" not in lines
    if _EXPECTED_UPDATED != "updated" or _EXPECTED_STATUS_LABEL != "status":
        assert "status\tupdated" not in lines
    if _EXPECTED_NEXT_LABEL != "next":
        assert not any(line.startswith("next\t") for line in lines)
