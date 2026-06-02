"""Committed-versus-regenerated CLI reference drift gate.

Closes docs-architecture W02.P07.S23: every commit that changes the
CLI surface must also regenerate the docs/cli/ subtree so the
committed pages match what ``_doc_reference.generate_cli_reference``
emits. Without this gate, a verb/flag/help-text drift silently
diverges from the published reference and the docs-check lane
catches it only at the next manual regen.

Marked for the docs-check lane (``-m docs``) so the fast unit
gate is unaffected; ``just docs-check`` runs it as part of the
documentation pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ._doc_reference import generate_cli_reference

pytestmark = [pytest.mark.unit, pytest.mark.docs, pytest.mark.domain_persistence]

_DOCS_ROOT = Path("docs")


def test_committed_cli_reference_matches_regenerated_output(tmp_path: Path) -> None:
    """The committed docs/cli/ subtree must match a fresh regeneration.

    Calls :func:`generate_cli_reference` against a tmp output root,
    then diffs every emitted page against its committed counterpart
    under ``docs/``. Generator returns paths relative to ``docs/``
    (e.g. ``cli/app.rst``), so the diff anchors at the docs root.
    Any drift fails with a per-file listing so the operator can
    re-run the CLI reference regeneration to restore parity.

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

    regenerated = generate_cli_reference(tmp_path)
    docs_cli_root = _DOCS_ROOT / "cli"
    drift: list[str] = []
    for relative_path, rendered in regenerated.items():
        committed_path = _DOCS_ROOT / relative_path
        if not committed_path.is_file():
            drift.append(f"missing committed page: docs/{relative_path}")
            continue
        committed = committed_path.read_text(encoding="utf-8")
        if committed != rendered:
            drift.append(
                f"docs/{relative_path} drifted from generator output "
                f"(committed {len(committed)} chars; regenerated "
                f"{len(rendered)} chars)"
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
        "affected pages.\n  "
        + "\n  ".join(drift)
    )
