"""Correspondence gate: every in-scope module has a stub, no stub is orphaned.

Delegates all discovery and drift logic to :class:`dev.docs.apidocs.manager.ApiStubManager`
so this file is the single enforcement surface for module-to-stub correspondence.
Run ``python -m dev.docs.apidocs scaffold`` to regenerate stubs; run
``python -m dev.docs.apidocs scaffold --check`` for a zero-drift gate.

Run via::

    uv run --no-sync pytest dev/docs/tests/test_api_stubs.py -m "unit and hex_core" -q
"""

from __future__ import annotations

import pytest

from cadrumo.core.directory_scan import iter_directory, scan_directory

from ..._paths import REPO_ROOT
from ..apidocs.manager import ApiStubManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT
_SRC_CADRUMO = _REPO_ROOT / "src" / "cadrumo"
_DOCS_API = _REPO_ROOT / "docs" / "api"


def test_every_source_module_has_a_stub() -> None:
    """Every in-scope ``src/cadrumo/`` module must have a ``docs/api/`` stub.

    The assertion fails with the symmetric difference so both missing stubs
    and orphaned stubs are reported in one shot.  Run
    ``python -m dev.docs.apidocs scaffold`` to regenerate the stub tree.
    """
    manager = ApiStubManager(src_cadrumo=_SRC_CADRUMO, docs_api=_DOCS_API)
    drift = manager.check()

    # Proof of scan: a walk that found no modules reports exactly what a
    # conformant tree reports, so the clean result below is only evidence
    # if the source tree was genuinely enumerated.
    assert any(iter_directory(_SRC_CADRUMO, pattern="*.py", recursive=True)), (
        f"no source modules found under {_SRC_CADRUMO}; the stub check scanned nothing"
    )

    messages: list[str] = []
    if drift.missing_stubs:
        listed = "\n  ".join(drift.missing_stubs)
        messages.append(f"Modules without a stub ({len(drift.missing_stubs)}):\n  {listed}")
    if drift.orphan_stubs:
        listed = "\n  ".join(drift.orphan_stubs)
        messages.append(f"Stub targets with no matching module ({len(drift.orphan_stubs)}):\n  {listed}")
    if drift.stale_stubs:
        listed = "\n  ".join(drift.stale_stubs)
        messages.append(f"Stubs whose content differs from the generator ({len(drift.stale_stubs)}):\n  {listed}")

    assert not messages, "\n\n".join(messages)


def test_the_committed_stub_tree_carries_untranslated_terminators() -> None:
    """No committed stub on disk carries a translated terminator.

    The correspondence gate above reads generated content through the manager,
    which now compares bytes; this reads the real committed files directly, so
    it stays true even if the generator's own comparison were ever loosened
    again. It is the read nothing in the tree performed: on 2026-07-28, 60 of
    the 1240 stubs here carried CRLF while every git-shaped review reported the
    tree clean, because ``.gitattributes`` normalises to LF on the index side.

    The carriage-return assertion is decisive only on a platform whose line
    separator is not already LF, which is where the drift was measured; on a
    line-feed platform it holds trivially and costs nothing.
    """
    rst_paths = scan_directory(_DOCS_API, pattern="*.rst")
    assert rst_paths, f"no stub files found under {_DOCS_API}; this gate scanned nothing"

    translated = [rst_path.name for rst_path in rst_paths if b"\r\n" in rst_path.read_bytes()]

    assert not translated, (
        f"{len(translated)} of {len(rst_paths)} committed stubs carry translated terminators, so their "
        f"on-disk bytes differ from their committed bytes and no diff can show it; "
        f"run `python -m dev.docs.apidocs scaffold` to rewrite them: {translated[:10]}"
    )
