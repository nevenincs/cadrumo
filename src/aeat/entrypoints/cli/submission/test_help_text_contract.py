"""Lock --help text shape for every submission CLI subcommand (wave 132).

Kent discovers the CLI by running ``aeat submission --help`` and
``aeat submission <cmd> --help``. The help text is the
first-contact surface and a public contract: a future docstring
refactor that accidentally drops the verb, the Kent-observable
outcome, or the key flag must fail this test.

For each subcommand we assert:

1. The top-level help listing includes the subcommand name and
   a short verb describing what it does.
2. ``<cmd> --help`` surfaces the subcommand's own usage line
   with its canonical Kent-facing verb.
"""

from __future__ import annotations

import re

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_runner = CliRunner()

# Rich wraps styled CLI help text with ANSI escape codes. On narrow
# terminals (the CI runners, ~80 cols) Rich can inject styling between
# the characters of a flag (e.g. ``--json`` becomes
# ``-\x1b[0m\x1b[1;36m-json``), so plain substring matches on the raw
# ``result.stdout`` miss the flag even though it is visibly present.
# Strip the codes before every discoverability assertion.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Return ``text`` with ANSI styling codes stripped."""
    return _ANSI_RE.sub("", text)


_SUBCOMMANDS: dict[str, list[str]] = {
    "preflight": ["preflight"],
    "export": ["export", "Export"],
    "verify": ["verify", "Re-parse"],
    "diff": ["diff", "Diff"],
    "schemas": ["schemas", "List"],
    "check-nif": ["check-nif", "Validate"],
    "show": ["show", "Pretty-print"],
    "list": ["list"],
}


class TestTopLevelHelpListsEveryCommand:
    def test_help_shows_all_registered_subcommands(self) -> None:
        result = _runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for name in _SUBCOMMANDS:
            assert name in result.stdout, f"aeat submission --help missing subcommand {name!r}"


class TestPerSubcommandHelpShape:
    @pytest.mark.parametrize(
        ("name", "tokens"),
        list(_SUBCOMMANDS.items()),
        ids=list(_SUBCOMMANDS.keys()),
    )
    def test_subcommand_help_exits_0_and_names_verb(self, name: str, tokens: list[str]) -> None:
        result = _runner.invoke(app, [name, "--help"])
        assert result.exit_code == 0, f"{name} --help exited {result.exit_code}: {result.stdout}"
        for token in tokens:
            assert token in result.stdout, (
                f"{name} --help output missing token {token!r}. Full output:\n{result.stdout}"
            )


class TestKeyFlagsAreDiscoverable:
    """Every flag Kent depends on (--json, --iban, --nombre, --apellidos, etc.)
    must appear in the subcommand's --help so he can discover it without
    reading the source."""

    def test_export_help_surfaces_key_flags(self) -> None:
        result = _runner.invoke(app, ["export", "--help"])
        assert result.exit_code == 0
        stdout = _strip_ansi(result.stdout)
        for flag in ("--nombre", "--apellidos", "--tipo", "--iban", "--swift", "--output-dir"):
            assert flag in stdout, f"export --help missing {flag!r}"

    def test_verify_help_surfaces_json_flag(self) -> None:
        result = _runner.invoke(app, ["verify", "--help"])
        assert result.exit_code == 0
        stdout = _strip_ansi(result.stdout)
        assert "--json" in stdout
        assert "--modelo" in stdout
        assert "--ejercicio" in stdout

    def test_diff_help_surfaces_json_flag(self) -> None:
        result = _runner.invoke(app, ["diff", "--help"])
        assert result.exit_code == 0
        assert "--json" in _strip_ansi(result.stdout)

    def test_schemas_help_surfaces_json_flag(self) -> None:
        result = _runner.invoke(app, ["schemas", "--help"])
        assert result.exit_code == 0
        assert "--json" in _strip_ansi(result.stdout)

    def test_check_nif_help_surfaces_json_flag(self) -> None:
        result = _runner.invoke(app, ["check-nif", "--help"])
        assert result.exit_code == 0
        assert "--json" in _strip_ansi(result.stdout)
