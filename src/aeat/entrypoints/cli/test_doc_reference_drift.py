"""Drift gate for the committed CLI reference pages.

Regenerates the CLI reference in-memory (via a subprocess with
``AEAT_OUTPUT_LANGUAGE=en``) and asserts byte-for-byte identity against the
committed ``docs/cli/`` pages.  A drift — caused by adding, renaming, or
retiring a command without regenerating the committed reference — fails here.

This test intentionally materialises the full CLI tree and the schema registry,
so it carries the ``docs`` marker that excludes it from the fast unit lane and
runs via ``just docs-check`` / CI.

The subprocess contract mirrors :mod:`test_lazy_command_tree` and
:func:`aeat.entrypoints.cli._doc_reference.generate_cli_reference_in_subprocess`:
a fresh interpreter with ``AEAT_OUTPUT_LANGUAGE=en`` in its environment so
``tr()`` help strings resolve to English before any CLI module is imported.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.docs, pytest.mark.unit, pytest.mark.domain_application]

_DOCS_CLI_DIR = Path(__file__).parent.parent.parent.parent.parent / "docs" / "cli"


def _project_root() -> Path:
    """Return the project root, inferred from the location of this test file."""
    return Path(__file__).parent.parent.parent.parent.parent


def test_committed_cli_reference_matches_generated_output() -> None:
    """Regenerated CLI reference must match every committed ``docs/cli/*.rst`` page.

    Spawns a fresh subprocess with ``AEAT_OUTPUT_LANGUAGE=en`` to materialise
    the CLI tree and schema registry in a clean import state, then compares the
    generated RST content against what is committed under ``docs/cli/``.

    Failures indicate that a command was added, renamed, retired, or had its
    schema changed without regenerating the committed reference.  Run
    :func:`aeat.entrypoints.cli._doc_reference.generate_cli_reference_in_subprocess`
    (or ``just docs-gen``) to regenerate.
    """
    from aeat.entrypoints.cli._doc_reference import generate_cli_reference_in_subprocess

    docs_root = _project_root() / "docs"
    cli_dir = docs_root / "cli"

    if not cli_dir.exists():
        pytest.fail(
            f"docs/cli/ directory does not exist at {cli_dir}. "
            "Run the CLI reference generator to create it."
        )

    committed: dict[str, str] = {}
    for rst_file in sorted(cli_dir.glob("*.rst")):
        rel = f"cli/{rst_file.name}"
        committed[rel] = rst_file.read_text(encoding="utf-8")

    if not committed:
        pytest.fail("docs/cli/ directory exists but contains no .rst files.")

    # Regenerate in a subprocess to guarantee en-language pinning before import.
    # Use a temporary directory so the subprocess output does not overwrite the
    # committed pages during the drift check.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_docs = Path(tmp) / "docs"
        tmp_docs.mkdir()
        regenerated = generate_cli_reference_in_subprocess(tmp_docs)

    drifted: list[str] = []
    for rel_path, committed_content in sorted(committed.items()):
        regen_content = regenerated.get(rel_path)
        if regen_content is None:
            drifted.append(
                f"{rel_path}: present in committed docs but missing from regenerated output"
            )
        elif regen_content != committed_content:
            drifted.append(
                f"{rel_path}: content differs between committed and regenerated versions"
            )

    for rel_path in sorted(regenerated):
        if rel_path not in committed:
            drifted.append(
                f"{rel_path}: present in regenerated output but not committed to docs/cli/"
            )

    assert not drifted, (
        "CLI reference drift detected. Regenerate docs/cli/ and commit the result:\n"
        + "\n".join(f"  - {d}" for d in drifted)
    )
