from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import IO, Any, cast, override

import pytest
import typer
import typer.main
from click.core import Command
from click.testing import CliRunner, Result

from ...core.i18n import OUTPUT_LANGUAGE_ENV_VAR
from ...tests._env import temporary_env


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

    @override
    def invoke(
        self,
        cli: Command | typer.Typer,
        args: str | Sequence[str] | None = None,
        input: str | bytes | IO[Any] | None = None,
        env: Mapping[str, str | None] | None = None,
        catch_exceptions: bool | None = None,
        color: bool = False,
        **extra: Any,
    ) -> Result:
        if isinstance(cli, typer.Typer):
            # Typer's get_command returns a runtime Click command, but its vendored
            # type alias does not line up with click.core.Command's stub.
            cli = cast(Command, typer.main.get_command(cli))
        return super().invoke(
            cli,
            args=args,
            input=input,
            env=env,
            catch_exceptions=catch_exceptions,
            color=color,
            **extra,
        )


@pytest.fixture(autouse=True)
def _force_english_output() -> Iterator[None]:
    """Pin CLI output to English so test assertions stay readable.

    The production default is ``es``; this fixture only affects test
    output, not runtime behaviour.
    """
    with temporary_env(**{OUTPUT_LANGUAGE_ENV_VAR: "en"}):
        yield


@pytest.fixture(autouse=True)
def _isolated_aeat_root(tmp_path: Path) -> Iterator[None]:
    """Point `Settings.aeat_local_storage_root` at the test's `tmp_path`."""
    with temporary_env(AEAT_LOCAL_STORAGE_ROOT=str(tmp_path)):
        yield


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a fresh Click ``CliRunner`` for CLI invocation tests.

    Shared by every CLI test module that exercises commands through
    ``runner.invoke(...)``; previously redeclared in ~21 modules with
    identical bodies. New tests should use this fixture directly
    rather than redeclaring it.
    """
    return _TyperAwareCliRunner()
