"""The Sphinx ``builder-inited`` build-gate surface for cli-sequences (ADR D6).

This is the docs-build half of the two-surfaces-one-engine gate: the Sphinx
build runs the engine's check mode from a ``builder-inited`` hook so a golden
divergence or a failed ``@expect`` reds the docs build, and a peer pytest gate
(``dev/docs/tests/test_sequence_goldens.py``) calls the same
:func:`~dev.docs.sequences.check_sequences` so CI catches drift without a full
docs build. Neither surface re-implements execution or comparison — both wire
the one engine.

``docs/conf.py`` connects :func:`emit_cli_tree` and :func:`check_sequence_goldens`
to ``builder-inited``; the same functions are importable by an isolated fixture
Sphinx build so the gate can be exercised in a tmp docs tree without touching the
committed docs (the golden/seed roots redirect through the directive's
``cadrumo_sequences_goldens_root`` config seam).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sphinx.errors import SphinxError

if TYPE_CHECKING:
    from sphinx.application import Sphinx

__all__ = [
    "check_sequence_goldens",
    "emit_cli_tree",
]


def emit_cli_tree(app: Sphinx) -> None:
    """Write a fresh ``_static/cli-tree.json`` projection into the build source tree.

    Runs at ``builder-inited`` (before the read phase) so every build — full or
    changed-page — ships the current live help catalogue the frontend widget
    fetches. The file is gitignored and regenerated on every build, never
    committed.
    """
    from dev.docs.cli_tree import default_cli_tree_path, write_cli_tree

    write_cli_tree(default_cli_tree_path(Path(app.srcdir)))


def _config_root(app: Sphinx, name: str) -> Path | None:
    """Return a directory-typed Sphinx config seam as a ``Path``, or ``None``."""
    value = getattr(app.config, name, None)
    return Path(value) if value else None


def check_sequence_goldens(app: Sphinx, *, pages: list[str] | None = None) -> None:
    """Execute the enrolled sequences and fail the build on any golden divergence.

    Calls the one engine check function
    (:func:`~dev.docs.sequences.check_sequences`) against the pages under the
    build's source tree, comparing each executed transcript to its committed
    golden. A non-empty problem set raises :class:`~sphinx.errors.SphinxError`
    carrying every problem verbatim (each already names the page, sequence,
    frame, argv, and diff) plus the exact ``refresh`` remedy, halting the build.

    Args:
        app: The Sphinx application; ``app.srcdir`` is the pages tree and its
            ``cadrumo_sequences_goldens_root`` config seam redirects the goldens.
        pages: When given, restrict the check to these docname-style page paths
            (the incremental changed-page set); ``None`` checks every enrolled
            page (a full build).
    """
    from dev.docs.sequences import check_sequences, refresh_invocation

    docs_root = Path(app.srcdir)
    goldens_root = _config_root(app, "cadrumo_sequences_goldens_root")

    problems: list[str] = []
    if pages is None:
        found, _advisories = check_sequences(docs_root=docs_root, goldens_root=goldens_root)
        problems.extend(found)
    else:
        for page in pages:
            found, _advisories = check_sequences(docs_root=docs_root, goldens_root=goldens_root, page=page)
            problems.extend(found)

    if problems:
        detail = "\n".join(problems)
        raise SphinxError(
            f"{len(problems)} cli-sequence divergence(s) from committed goldens:\n{detail}\n"
            f"If the new behaviour is intended, update the golden(s) with: {refresh_invocation()}",
        )
