from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import IO, Any, cast, override

import pytest
import typer
import typer.main
from click.core import Command
from click.testing import CliRunner, Result

from ...application.workflow import workflow_state_repository
from ...core.config import reset_settings_cache
from ...core.i18n import OUTPUT_LANGUAGE_ENV_VAR, clear_output_language_cache
from ...tests import temporary_env
from ...tests.profile_capsule import open_test_profile_session
from ...tests.secure_sql import isolated_profile_storage_root
from ...tests.user_profile import register_minimal_profile


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


@pytest.fixture
def overview_cli_backend(tmp_path: Path) -> Iterator[None]:
    """Provide the profile-backed storage lifecycle required by overview CLI tests."""

    profile_id = "11111111-1111-4111-8111-111111111111"
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session(profile_id),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id=profile_id)
        )
        yield


@pytest.fixture
def open_bucket_cli_backend(tmp_path: Path) -> Iterator[None]:
    """Open the dedicated ledger UX bucket lifecycle for one requesting test."""
    from .tests._ledger_ux_support import _open_ledger_ux_session

    with _open_ledger_ux_session(tmp_path):
        yield


@pytest.fixture(autouse=True)
def _force_english_output() -> Iterator[None]:
    """Pin CLI output to English so test assertions stay readable.

    The production default is ``es``; this fixture only affects test
    output, not runtime behaviour.

    Writing the variable is not a pin on its own.
    :class:`~cadrumo.core.config.Settings` is built once per active-profile
    pointer state and then held, so an instance constructed before this
    fixture ran carries no explicit ``cadrumo_output_language``; the
    resolver finds the field absent from ``model_fields_set`` and falls
    through to whatever language the machine's active profile happens to
    carry. Dropping the held instances at both boundaries is what turns the
    write into a pin, and it leaves the language resolution independent of
    whether anything else in the test happens to force a rebuild.

    :func:`~cadrumo.core.config.override_settings` is the usual door for a
    settings value, but it is the wrong one at package-wide autouse scope:
    it snapshots EVERY field for the whole block, so a test that creates a
    profile or logs in would keep reading the route captured before that
    happened. The variable plus an invalidation keeps the pointer-keyed
    rebuild intact, and it reaches the console subprocesses a number of
    these tests spawn, which an in-process override cannot.
    """
    with temporary_env(**{OUTPUT_LANGUAGE_ENV_VAR: "en"}):
        reset_settings_cache()
        clear_output_language_cache()
        try:
            yield
        finally:
            reset_settings_cache()
            clear_output_language_cache()


@pytest.fixture(autouse=True)
def _isolated_cadrumo_root(tmp_path: Path) -> Iterator[None]:
    """Point `Settings.cadrumo_local_storage_root` at the test's `tmp_path`."""
    with temporary_env(CADRUMO_LOCAL_STORAGE_ROOT=str(tmp_path)):
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
