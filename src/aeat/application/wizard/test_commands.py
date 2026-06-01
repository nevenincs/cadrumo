"""Real-behavior tests for wizard status verb localization.

Pins that the status tab-key and verb in ``build_wizard_command`` both route
through ``tr()`` — the tab-key from ``application.wizard.output_labels.status``
and the verb from ``wizard.commands.status.created`` /
``wizard.commands.status.updated`` — rather than hardcoded English literals.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import typer
from pydantic import SecretStr
from typer.testing import CliRunner

from ...adapters.persistence.storage.sql.engine import dispose_engine
from ._catalogue import SETUP_FLOW
from ._commands import build_wizard_command
from ._persistence import WizardPersistMode
from ...core.config import SecretStoreBackend, override_settings
from ...core.i18n import tr
from ...tests.secure_sql import dev_test_database_password

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


# Derive expected tab-key label and verbs from the locale authority.
_EXPECTED_STATUS_LABEL = tr("application.wizard.output_labels.status")
_EXPECTED_CREATED = tr("wizard.commands.status.created")
_EXPECTED_UPDATED = tr("wizard.commands.status.updated")


def test_wizard_create_status_verb_is_localized(
    runner: CliRunner, _isolated_backend: Path
) -> None:
    """Wizard create emits the locale-resolved tab-key and verb, not raw English."""
    app = _wizard_app("create")
    result = runner.invoke(
        app,
        ["operator", "--quiet", "--tax-id", "00000000T", "--activity", "Servicios"],
    )

    assert result.exit_code == 0, result.output
    assert f"{_EXPECTED_STATUS_LABEL}\t{_EXPECTED_CREATED}" in result.output
    # Confirm the raw English literals are absent when locale resolves differently.
    if _EXPECTED_CREATED != "created" or _EXPECTED_STATUS_LABEL != "status":
        assert "status\tcreated" not in result.output


def test_wizard_edit_status_verb_is_localized(
    runner: CliRunner, _isolated_backend: Path
) -> None:
    """Wizard edit emits the locale-resolved tab-key and updated verb."""
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
    assert f"{_EXPECTED_STATUS_LABEL}\t{_EXPECTED_UPDATED}" in result.output
    if _EXPECTED_UPDATED != "updated" or _EXPECTED_STATUS_LABEL != "status":
        assert "status\tupdated" not in result.output
