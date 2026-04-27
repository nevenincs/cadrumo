"""Static guardrails enforcing the permanent live-submit CLI excision.

This module mechanically prevents the
:mod:`aeat.cli.submission.submit` command from being reintroduced
into the default CLI surface. See
``.vault/adr/2026-04-18-live-submit-cli-excision-adr.md`` and the
2026-04-27 permanent-forbid policy ADR.

Three assertions:

1. Importing :mod:`aeat.cli.submission.submit` raises
   :class:`ModuleNotFoundError`.
2. The :class:`typer.Typer` app under :mod:`aeat.cli.submission`
   does NOT register a command named ``submit``.
3. The string ``button#firmar-y-enviar`` (the modelo-130
   "sign and send" CSS selector) does not appear anywhere under
   :mod:`aeat.cli`. The click is a submitter-internal detail and
   must never leak into the CLI tree.
"""

from __future__ import annotations

import re
from importlib import import_module
from pathlib import Path

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


_CLI_ROOT = Path(__file__).resolve().parents[1]
_RUNNER = CliRunner()


def test_submit_module_is_absent() -> None:
    with pytest.raises(ModuleNotFoundError):
        import_module("aeat.cli.submission.submit")


def test_typer_app_does_not_register_submit() -> None:
    registered = {cmd.name for cmd in app.registered_commands}
    assert "submit" not in registered, (
        f"submission CLI must not register `submit`; got {sorted(registered)!r}. "
        "See .vault/adr/2026-04-18-live-submit-cli-excision-adr.md."
    )
    assert {"preflight", "dry-run", "export", "verify", "diff", "schemas", "check-nif", "show", "list"}.issubset(
        registered
    )


def test_submission_help_states_live_submit_is_not_on_default_cli() -> None:
    assert app.info.help is not None
    assert "never submits to AEAT" in app.info.help


def test_no_modelo_click_selector_in_cli_tree() -> None:
    """The literal AEAT submit-button selector must not appear in CLI code."""
    needle = re.compile(re.escape("button#firmar-y-enviar"))
    offenders: list[tuple[str, int, str]] = []
    for path in sorted(_CLI_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        if path.name == "test_no_submit_command.py":
            # The needle pattern itself appears here; self-exclude.
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if needle.search(line):
                offenders.append((str(path), lineno, line))
    assert offenders == [], (
        f"AEAT submit-click selector leaked into CLI tree: {offenders!r}. "
        "The selector belongs to aeat.submission._submitters.modelo130 only."
    )
