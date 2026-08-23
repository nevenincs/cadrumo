"""The Sphinx ``builder-inited`` build-gate surface for cli-sequences.

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

import os
from pathlib import Path
from typing import TYPE_CHECKING

from sphinx.errors import SphinxError

if TYPE_CHECKING:
    from sphinx.application import Sphinx

__all__ = [
    "SEQUENCE_CHECK_SKIP_ENV",
    "check_sequence_goldens",
    "emit_cli_tree",
    "should_check_sequences",
    "should_emit_cli_tree",
]

#: Force a fresh ``cli-tree.json`` regardless of build mode (mirrors the CLI
#: reference hook's ``CADRUMO_DOCS_FORCE_CLI_REFERENCE`` seam).
_FORCE_EMIT_ENV = "CADRUMO_DOCS_FORCE_CLI_TREE"
#: Skip the ``cli-tree.json`` projection unconditionally.
_SKIP_EMIT_ENV = "CADRUMO_DOCS_SKIP_CLI_TREE"
#: Skip the golden check unconditionally. The check's verdict depends only on
#: the enrolled pages, the committed goldens, and the CLI's behaviour — never
#: on the build's scope, language, or builder — so a caller driving SEVERAL
#: builds over one docs tree in one verification lane may run the check once
#: and skip the byte-identical repeats. A caller that sets this owes the check
#: elsewhere in the same lane: the pytest goldens gate
#: (``dev/docs/tests/test_sequence_goldens.py``) for the test harness and the
#: POT extraction, and the first-built site root for the deploy, which refuses
#: to publish unless exactly one of its four roots ran the check. A lone build
#: never sets it; the hook stays connected and red-on-divergence.
#:
#: Public because the deploy composes its per-root environments from it: a
#: second literal copy of the key could drift from this one silently, which is
#: exactly how a renamed env key disables a gate without anyone noticing.
SEQUENCE_CHECK_SKIP_ENV = "CADRUMO_DOCS_SKIP_SEQUENCE_CHECK"


def should_emit_cli_tree(output_path: Path, *, specific_sources: list[Path] | None) -> bool:
    """Return whether this build must (re)build the ``cli-tree.json`` projection.

    The projection is a walk of the live ``aeat`` command tree — it derives from
    the CLI surface, never from a docs page — so an incremental docs-only
    changed-page build cannot change it and must not pay the projection's
    subprocess cost. Mirrors the sibling ``_should_generate_cli_reference`` guard
    in ``docs/conf.py``: regenerate on a full/update build, when the output is
    absent, or when forced; skip on an incremental changed-page build whose
    artifact already exists. Two env seams force or skip unconditionally.

    Args:
        output_path: The projection destination (:func:`default_cli_tree_path`).
        specific_sources: The changed-page specific-source set of an incremental
            build, or ``None`` for a normal full/update build.
    """
    if os.environ.get(_FORCE_EMIT_ENV):
        return True
    if os.environ.get(_SKIP_EMIT_ENV):
        return False
    if specific_sources is None:
        return True
    return not output_path.is_file()


def emit_cli_tree(app: Sphinx, *, specific_sources: list[Path] | None = None) -> None:
    """Write a fresh ``_static/cli-tree.json`` projection when the build needs it.

    Runs at ``builder-inited`` (before the read phase) so a build that needs the
    projection ships the current live help catalogue the browser widget fetches.
    The file is gitignored and regenerated, never committed. An incremental
    changed-page build whose artifact already exists is skipped so it does not
    pay the projection's subprocess cost for a value that cannot have changed
    (see :func:`should_emit_cli_tree`).

    Args:
        app: The Sphinx application; ``app.srcdir`` is the build source tree.
        specific_sources: The changed-page specific-source set, or ``None`` for a
            full/update build.
    """
    from .cli_tree import default_cli_tree_path, write_cli_tree

    output_path = default_cli_tree_path(Path(app.srcdir))
    if not should_emit_cli_tree(output_path, specific_sources=specific_sources):
        return
    write_cli_tree(output_path)


def should_check_sequences() -> bool:
    """Return whether this build must run the cli-sequence golden check.

    ``True`` unless the explicit ``CADRUMO_DOCS_SKIP_SEQUENCE_CHECK`` opt-out is
    set. The opt-out exists for a verification lane that drives several Sphinx
    builds over the same docs tree (full scope, user scope, one per language):
    the check subprocess pins its own environment (English output, scrubbed
    ``CADRUMO_*``), so its verdict is identical across those builds, and the
    lane runs it exactly once instead of once per build — through the dedicated
    pytest goldens gate for the test harness and the POT extraction, and through
    the first-built site root for the deploy, which refuses to publish unless
    exactly one root ran it. A build that is not part of such a lane never sets
    the opt-out, so an ordinary docs build keeps failing on a golden divergence.
    """
    return not os.environ.get(SEQUENCE_CHECK_SKIP_ENV)


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
    from .sequences import check_sequences_in_subprocess, refresh_invocation

    if not should_check_sequences():
        return
    docs_root = Path(app.srcdir)
    goldens_root = _config_root(app, "cadrumo_sequences_goldens_root")

    problems: list[str] = []
    if pages is None:
        # A full build checks every enrolled page; shard the pages across a
        # BOUNDED pool of child interpreters (each sequence keeps its own fresh
        # hermetic sandbox, so execution is unchanged — only the scheduling
        # is). Width 4 is the same bounded-not-auto footprint the gate builds
        # use for Sphinx ``-j`` (see ``.github/ci-control-plane.md`` on sizing
        # for co-residency, never for the whole machine).
        problems.extend(
            check_sequences_in_subprocess(
                docs_root=docs_root,
                goldens_root=goldens_root,
                jobs=4,
            ),
        )
    else:
        for page in pages:
            problems.extend(
                check_sequences_in_subprocess(
                    docs_root=docs_root,
                    goldens_root=goldens_root,
                    page=page,
                ),
            )

    if problems:
        detail = "\n".join(problems)
        raise SphinxError(
            f"{len(problems)} cli-sequence divergence(s) from committed goldens:\n{detail}\n"
            f"If the new behaviour is intended, update the golden(s) with: {refresh_invocation()}",
        )
