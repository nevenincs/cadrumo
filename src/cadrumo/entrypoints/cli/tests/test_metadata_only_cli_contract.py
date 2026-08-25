"""Fresh-process contracts for metadata-only CLI discovery surfaces."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import cast

import pytest

from ....adapters.persistence.storage import close_active_bucket_session
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FORBIDDEN_PREFIXES = (
    "cadrumo.domain.calculations.registry",
    "cadrumo.adapters.persistence.storage",
    "cadrumo_harness",
    "cadrumo.entrypoints.tui",
    "cryptography",
    "keyring",
)


def _probe(arguments: tuple[str, ...], *, locale: str) -> dict[str, object]:
    script = textwrap.dedent(
        f"""
        import json
        import os
        import sys
        from click.testing import CliRunner
        from typer.main import get_command

        os.environ["CADRUMO_OUTPUT_LANGUAGE"] = {locale!r}
        from cadrumo.entrypoints.cli import app
        result = CliRunner().invoke(get_command(app), {list(arguments)!r})
        forbidden = sorted(
            name for name in sys.modules
            if any(name == prefix or name.startswith(prefix + ".") for prefix in {_FORBIDDEN_PREFIXES!r})
        )
        print(json.dumps({{"exit_code": result.exit_code, "output": result.output, "forbidden": forbidden}}))
        """
    )
    # Security rationale: argv is the current trusted
    # interpreter plus an in-repo constant script; no operator input reaches it.
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return cast(dict[str, object], json.loads(completed.stdout))


@pytest.mark.parametrize(
    ("arguments", "expected_by_locale", "exit_code"),
    (
        (("--help",), {"es": "CADRUMO - flujo local", "en": "CADRUMO - local-first"}, 0),
        (("config", "--help"), {"es": "aeat config", "en": "aeat config"}, 0),
        (("app", "--help"), {"es": "Operaciones de declaración fiscal", "en": "aeat app - operational tax work"}, 0),
        (("--version",), {"es": "CADRUMO ", "en": "CADRUMO "}, 0),
        (("app", "status"), {"es": "overview status", "en": "overview status"}, 2),
        (("definitely-unknown",), {"es": "No such command", "en": "No such command"}, 2),
        (("--format", "json", "--help"), {"es": '"schema_version": "2"', "en": '"schema_version": "2"'}, 0),
        (
            ("--format", "json", "app", "status"),
            {"es": '"code":"REFUSED_CLI_BOUNDARY"', "en": '"code":"REFUSED_CLI_BOUNDARY"'},
            2,
        ),
    ),
)
@pytest.mark.parametrize("locale", ("es", "en"))
def test_metadata_surfaces_preserve_contract_without_forbidden_imports(
    arguments: tuple[str, ...],
    expected_by_locale: dict[str, str],
    exit_code: int,
    locale: str,
) -> None:
    observation = _probe(arguments, locale=locale)

    assert observation["exit_code"] == exit_code
    assert expected_by_locale[locale] in cast(str, observation["output"])
    assert observation["forbidden"] == []
    if arguments[:2] == ("--format", "json"):
        document = cast(dict[str, object], json.loads(cast(str, observation["output"])))
        assert document["active_profile"] is None


@pytest.mark.parametrize(
    ("locale", "expected_help"),
    (("es", "Gestionar configuración local"), ("en", "Manage local configuration")),
)
def test_root_shell_completion_reads_registration_metadata_only(locale: str, expected_help: str) -> None:
    script = textwrap.dedent(
        f"""
        import json
        import sys
        import typer
        from typer.main import get_command

        import os
        os.environ["CADRUMO_OUTPUT_LANGUAGE"] = {locale!r}
        from cadrumo.entrypoints.cli import app

        command = get_command(app)
        context = typer.Context(command, info_name="aeat")
        try:
            items = command.shell_complete(context, "c")
        finally:
            context.close()
        forbidden = sorted(
            name for name in sys.modules
            if any(name == prefix or name.startswith(prefix + ".") for prefix in {_FORBIDDEN_PREFIXES!r})
        )
        print(json.dumps({{"items": [[item.value, item.help] for item in items], "forbidden": forbidden}}))
        """
    )
    # Security rationale: same fixed interpreter/script
    # boundary as `_probe`; a fresh module table is the property under test.
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    observation = cast(dict[str, object], json.loads(completed.stdout))

    items = cast(list[list[str]], observation["items"])
    assert [item[0] for item in items] == ["config"]
    assert expected_help in items[0][1]
    assert observation["forbidden"] == []


def test_callback_refusal_still_carries_the_real_active_profile(tmp_path: Path) -> None:
    """Only parse-time failures lose identity; callback envelopes retain it."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_cli_profile(label="operator", facts={})
        try:
            result = invoke_cached_cli(
                ["--format", "json", "config", "reset", "start", "--yes", "--override-retention"],
            )
        finally:
            close_active_bucket_session()

    assert result.exit_code == 2, result.output
    document = cast(dict[str, object], json.loads(result.output))
    assert document["active_profile"] == "operator"
    assert document["command"] == "config.reset.start"
