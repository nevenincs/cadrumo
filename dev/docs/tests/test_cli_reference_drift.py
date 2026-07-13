"""Committed-versus-regenerated CLI reference drift gate.

Every commit that changes the CLI surface must also regenerate the docs/cli/ subtree so the
committed pages match what ``dev.docs.cli_reference.generate_cli_reference``
emits. Without this gate, a verb/flag/help-text drift silently
diverges from the published reference and the docs-check lane
catches it only at the next manual regen.

Marked as ``unit`` plus ``hex_entrypoint`` because it verifies the CLI
reference projection without making external calls.
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest
import typer
from typer.main import get_command

from dev.docs.cli_reference import _render_param_table, generate_cli_reference_in_subprocess

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.docs]

_DOCS_ROOT = Path("docs")


def test_typer_positional_renders_as_argument() -> None:
    """A real Typer positional renders as an ``Argument``, never an ``Option``.

    Regression guard for the ``TyperArgument``-is-not-``click.Argument`` trap:
    Typer wraps a ``typer.Argument`` positional in a ``TyperArgument`` that does
    not subclass ``click.Argument``, so the prior ``isinstance`` classifier
    mislabelled it as an ``Option`` in the generated reference. Build a real
    single-command Typer app, materialise its Click command, and assert the
    rendered param table names the positional an ``Argument``.
    """
    app = typer.Typer()

    @app.command()
    def view(transaction_id: str = typer.Argument(..., help="The ledger transaction id.")) -> None:
        """Inspect a ledger transaction."""

    command = get_command(app)
    # A single-command Typer collapses to the leaf command directly; if Typer
    # kept a group, descend to the one registered subcommand.
    if hasattr(command, "commands"):
        command = next(iter(command.commands.values()))

    rendered = _render_param_table(list(command.params))

    assert "transaction_id" in rendered
    # The positional's own definition line must read *Argument, ...*, not Option.
    positional_line = next(line for line in rendered.splitlines() if "Argument" in line or "Option" in line)
    assert "*Argument, required.*" in positional_line
    assert "Option" not in positional_line


def test_committed_cli_reference_matches_regenerated_output(tmp_path: Path) -> None:
    """The committed docs/cli/ subtree must match a fresh regeneration.

    Calls :func:`generate_cli_reference_in_subprocess` against a tmp output
    root, then diffs every emitted page against its committed counterpart under
    ``docs/``. Generator returns paths relative to ``docs/`` (e.g.
    ``cli/app.rst``), so the diff anchors at the docs root. Any drift fails
    with a per-file listing so the operator can re-run the CLI reference
    regeneration to restore parity.

    Note: the CLI reference is generated at build time per the
    ``docs(build): generate the CLI reference at build time``
    decision (commit 740cbeb83). The committed pages exist as a
    reviewable snapshot; this gate ensures the snapshot stays in
    sync with what the generator would emit at the next build.
    """
    # The repository ships docs/ — backend_boundary forbids the
    # conditional-skip idiom in CLI unit tests (rollout meta-language).
    # Assert the precondition instead so a missing docs/ surfaces as
    # a hard test failure rather than a silent green.
    assert _DOCS_ROOT.is_dir(), f"docs/ directory required at {_DOCS_ROOT}"

    regenerated = generate_cli_reference_in_subprocess(tmp_path)
    docs_cli_root = _DOCS_ROOT / "cli"
    drift: list[str] = []
    for relative_path, rendered in regenerated.items():
        committed_path = _DOCS_ROOT / relative_path
        if not committed_path.is_file():
            drift.append(f"missing committed page: docs/{relative_path}")
            continue
        committed = committed_path.read_text(encoding="utf-8")
        if committed != rendered:
            diff = "\n".join(difflib.unified_diff(committed.splitlines(), rendered.splitlines()))
            drift.append(
                f"docs/{relative_path} drifted from generator output "
                f"(committed {len(committed)} chars; regenerated "
                f"{len(rendered)} chars)\n{diff}",
            )

    # Detect orphan pages (committed files the generator no longer emits).
    if docs_cli_root.is_dir():
        regenerated_relative = set(regenerated.keys())
        for committed in sorted(docs_cli_root.rglob("*.rst")):
            rel = committed.relative_to(_DOCS_ROOT).as_posix()
            if rel not in regenerated_relative:
                drift.append(f"orphan committed page: docs/{rel}")

    assert drift == [], (
        "Committed CLI reference drifted from generator output. "
        "Re-run the CLI reference regeneration and re-commit the "
        "affected pages.\n  " + "\n  ".join(drift)
    )
