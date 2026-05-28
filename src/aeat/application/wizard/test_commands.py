"""Real-behavior tests for wizard status verb localization.

Pins that ``typer.echo("status\t...")`` in ``build_wizard_command`` emits
the localized verb from ``wizard.commands.status.created`` /
``wizard.commands.status.updated`` rather than a hardcoded English literal.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import typer
from pydantic import SecretStr
from typer.testing import CliRunner

from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.wizard._catalogue import SETUP_FLOW
from aeat.application.wizard._commands import build_wizard_command
from aeat.application.wizard._persistence import WizardPersistMode
from aeat.core.config import SecretStoreBackend, override_settings
from aeat.core.i18n import tr
from aeat.tests.secure_sql import dev_test_database_password

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def _isolated_backend(tmp_path: Path) -> Iterator[Path]:
    with override_settings(
        aeat_local_storage_root=tmp_path,
        aeat_active_profile=None,
        aeat_secret_store_backend=SecretStoreBackend.FILE,
        aeat_secret_passphrase=SecretStr(dev_test_database_password()),
    ) as settings:
        dispose_engine(settings)
        try:
            yield tmp_path
        finally:
            dispose_engine(settings)


def _wizard_app(mode: WizardPersistMode) -> typer.Typer:
    """Build a minimal Typer app wrapping the wizard command for the given mode."""
    app = typer.Typer()
    cmd = build_wizard_command(SETUP_FLOW, mode=mode)
    app.command()(cmd)
    return app


# Derive expected verbs from the locale authority rather than hardcoding English.
_EXPECTED_CREATED = tr("wizard.commands.status.created")
_EXPECTED_UPDATED = tr("wizard.commands.status.updated")


def test_wizard_create_status_verb_is_localized(
    runner: CliRunner, _isolated_backend: Path
) -> None:
    """Wizard create emits the locale-resolved verb, not the raw English literal."""
    app = _wizard_app("create")
    result = runner.invoke(
        app,
        ["operator", "--quiet", "--tax-id", "00000000T", "--activity", "Servicios"],
    )

    assert result.exit_code == 0, result.output
    assert f"status\t{_EXPECTED_CREATED}" in result.output
    # Confirm the raw English literal is absent when locale resolves differently.
    if _EXPECTED_CREATED != "created":
        assert "status\tcreated" not in result.output


def test_wizard_edit_status_verb_is_localized(
    runner: CliRunner, _isolated_backend: Path
) -> None:
    """Wizard edit emits the locale-resolved updated verb."""
    # Seed a profile first via create so edit has a target.
    create_app = _wizard_app("create")
    seed = runner.invoke(
        create_app,
        ["operator", "--quiet", "--tax-id", "00000000T", "--activity", "Servicios"],
    )
    assert seed.exit_code == 0, seed.output

    edit_app = _wizard_app("edit")
    result = runner.invoke(
        edit_app,
        ["operator", "--quiet", "--tax-id", "00000000T", "--activity", "Servicios"],
    )

    assert result.exit_code == 0, result.output
    assert f"status\t{_EXPECTED_UPDATED}" in result.output
    if _EXPECTED_UPDATED != "updated":
        assert "status\tupdated" not in result.output
