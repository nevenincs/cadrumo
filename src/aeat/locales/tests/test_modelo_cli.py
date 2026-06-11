"""CLI integration tests for modelo schema-local locale commands."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.core.resources import bundled_path
from aeat.domain.calculations.registry import load_modelo_directory
from aeat.locales.cli import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

MODELO_ID = "130"
REVISION_ID = "2019-y-siguientes"


@pytest.fixture
def registry_root(tmp_path: Path) -> Path:
    """Return a temp registry root containing the real bundled M130 modelo."""
    root = tmp_path / "registry" / "aeat"
    modelos = root / "modelos"
    modelos.mkdir(parents=True)
    shutil.copytree(bundled_path("registry", "aeat", "modelos", MODELO_ID), modelos / MODELO_ID)
    return root


@pytest.fixture
def runner() -> CliRunner:
    """Return an isolated Typer runner."""
    return CliRunner()


def test_coverage_command_reports_complete_revision(runner: CliRunner, registry_root: Path) -> None:
    """Coverage reports translated and required counts for one revision."""
    result = _invoke_modelo(
        runner,
        registry_root,
        "coverage",
        "en",
        MODELO_ID,
        REVISION_ID,
    )

    assert result.exit_code == 0, result.output
    assert "locale=en modelo=130 revision=2019-y-siguientes" in result.output
    assert "labels=20/20" in result.output
    assert "help=20/20" in result.output


def test_audit_command_fails_and_lists_missing_schema_keys(runner: CliRunner, registry_root: Path) -> None:
    """Audit exits nonzero when a required schema-local translation is absent."""
    _remove_revision_label(registry_root, "02")

    result = _invoke_modelo(
        runner,
        registry_root,
        "audit",
        "en",
        MODELO_ID,
        REVISION_ID,
    )

    assert result.exit_code == 1, result.output
    assert "locale=en modelo=130 revision=2019-y-siguientes labels=19/20 help=20/20" in result.output
    assert "missing locale=en modelo=130 revision=2019-y-siguientes" in result.output
    assert "field=labels key=02" in result.output


def test_scaffold_check_reports_drift_without_writing(runner: CliRunner, registry_root: Path) -> None:
    """Scaffold check mode reports drift and leaves registry TOML unchanged."""
    locale_path = _revision_locale_path(registry_root)
    _remove_revision_label(registry_root, "02")
    before = locale_path.read_text(encoding="utf-8")

    result = _invoke_modelo(
        runner,
        registry_root,
        "scaffold",
        "en",
        MODELO_ID,
        REVISION_ID,
        "--check",
    )

    assert result.exit_code == 1, result.output
    assert "field=labels key=02" in result.output
    assert locale_path.read_text(encoding="utf-8") == before


def test_scaffold_set_and_remove_commands_write_validated_leaf(runner: CliRunner, registry_root: Path) -> None:
    """Scaffold, set, and remove mutate the registry-local file through the CLI."""
    _remove_revision_label(registry_root, "02")

    scaffolded = _invoke_modelo(
        runner,
        registry_root,
        "scaffold",
        "en",
        MODELO_ID,
        REVISION_ID,
    )
    after_scaffold = _revision_locale_path(registry_root).read_text(encoding="utf-8")

    set_result = _invoke_modelo(
        runner,
        registry_root,
        "set",
        "en",
        MODELO_ID,
        REVISION_ID,
        "labels",
        "02",
        "Operating expenses",
    )
    after_set = _revision_locale_path(registry_root).read_text(encoding="utf-8")

    remove_result = _invoke_modelo(
        runner,
        registry_root,
        "remove",
        "en",
        MODELO_ID,
        REVISION_ID,
        "labels",
        "02",
    )
    after_remove = _revision_locale_path(registry_root).read_text(encoding="utf-8")

    assert scaffolded.exit_code == 0, scaffolded.output
    assert "Updated" in scaffolded.output
    assert '"02" = "02"' in after_scaffold
    assert not (registry_root / "modelos" / MODELO_ID / "locales" / "en.toml").exists()
    assert set_result.exit_code == 0, set_result.output
    assert '"02" = "Operating expenses"' in after_set
    assert remove_result.exit_code == 0, remove_result.output
    assert '"02" = "Operating expenses"' not in after_remove


def test_set_command_rejects_unknown_schema_key(runner: CliRunner, registry_root: Path) -> None:
    """Set refuses keys that are not present in the selected registry revision."""
    result = _invoke_modelo(
        runner,
        registry_root,
        "set",
        "en",
        MODELO_ID,
        REVISION_ID,
        "labels",
        "not-a-casilla",
        "Invalid",
    )

    assert result.exit_code != 0, result.output
    assert "Modelo schema key not found" in result.output


def test_modelo_commands_do_not_mutate_eager_locale_catalogues(runner: CliRunner, registry_root: Path) -> None:
    """Modelo-local writes stay in registry-local TOML, not core locale YAML."""
    before = _eager_locale_hashes()

    scaffolded = _invoke_modelo(
        runner,
        registry_root,
        "scaffold",
        "en",
        MODELO_ID,
        REVISION_ID,
    )
    updated = _invoke_modelo(
        runner,
        registry_root,
        "set",
        "en",
        MODELO_ID,
        REVISION_ID,
        "labels",
        "01",
        "Revenue",
    )
    removed = _invoke_modelo(
        runner,
        registry_root,
        "remove",
        "en",
        MODELO_ID,
        REVISION_ID,
        "labels",
        "01",
    )

    assert scaffolded.exit_code == 0, scaffolded.output
    assert updated.exit_code == 0, updated.output
    assert removed.exit_code == 0, removed.output
    assert _eager_locale_hashes() == before


def test_set_command_does_not_mutate_official_spanish_schema_label(runner: CliRunner, registry_root: Path) -> None:
    """Setting an English label leaves the legally-bound schema label intact."""
    result = _invoke_modelo(
        runner,
        registry_root,
        "set",
        "en",
        MODELO_ID,
        REVISION_ID,
        "labels",
        "01",
        "Revenue",
    )
    modelo = load_modelo_directory(registry_root / "modelos" / MODELO_ID)
    casilla = next(item for item in modelo.revisions[REVISION_ID].casillas if item.id == "01")

    assert result.exit_code == 0, result.output
    assert casilla.label == "Ingresos"
    assert casilla.get_label("en") == "Revenue"


def _invoke_modelo(runner: CliRunner, registry_root: Path, *args: str):
    return runner.invoke(
        app,
        ["modelo", *args, "--registry-root", str(registry_root)],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )


def _remove_revision_label(registry_root: Path, key: str) -> None:
    locale_path = _revision_locale_path(registry_root)
    original = locale_path.read_text(encoding="utf-8")
    target_line = f'"{key}" = "Expenses"\n'
    assert target_line in original
    locale_path.write_text(original.replace(target_line, ""), encoding="utf-8")


def _revision_locale_path(registry_root: Path) -> Path:
    return registry_root / "modelos" / MODELO_ID / "revisions" / REVISION_ID / "locales" / "en.toml"


def _eager_locale_hashes() -> dict[str, str]:
    locales_dir = Path(__file__).resolve().parents[1]
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(locales_dir.glob("*.yml"))
    }
