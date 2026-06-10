from pathlib import Path
from typing import Any, override

import pytest
import typer
import typer.main
from click.testing import CliRunner, Result

from ...core.i18n import OUTPUT_LANGUAGE_ENV_VAR


class _TyperAwareCliRunner(CliRunner):
    """CliRunner that auto-wraps ``typer.Typer`` objects to ``click.Command``.

    click 8.x's :meth:`CliRunner.invoke` reads ``cli.name`` directly; passing
    a bare ``typer.Typer`` instance raises ``AttributeError: 'Typer' object
    has no attribute 'name'``. Production callers always go through
    ``typer.main.get_command(app)`` before invoking the CLI; the test fixture
    mirrors that wrapping so test sites can pass the Typer surface directly
    (the established project pattern across ~200 CLI tests) without an
    explicit ``get_command`` call at every invoke site.
    """

    # CliRunner.invoke accepts varargs/kwargs that shift across click minor versions;
    # concrete typing would couple it to one click release. KWARGS-ANY-RATIONALE-CLIRUNNER-INVOKE-OVERRIDE
    @override
    def invoke(self, cli: Any, *args: Any, **kwargs: Any) -> Result:  # type: ignore[override]  # TYPE-IGNORE-RATIONALE-CLIRUNNER-INVOKE-OVERRIDE
        if isinstance(cli, typer.Typer):
            cli = typer.main.get_command(cli)
        return super().invoke(cli, *args, **kwargs)


@pytest.fixture(autouse=True)
def _force_english_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin CLI output to English so test assertions stay readable.

    The production default is ``es``; this fixture only affects test
    output, not runtime behaviour.
    """
    monkeypatch.setenv(OUTPUT_LANGUAGE_ENV_VAR, "en")


@pytest.fixture(autouse=True)
def _isolated_aeat_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point `Settings.aeat_local_storage_root` at the test's `tmp_path`."""
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path))


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a fresh Click ``CliRunner`` for CLI invocation tests.

    Shared by every CLI test module that exercises commands through
    ``runner.invoke(...)``; previously redeclared in ~21 modules with
    identical bodies. New tests should use this fixture directly
    rather than redeclaring it.
    """
    return _TyperAwareCliRunner()
