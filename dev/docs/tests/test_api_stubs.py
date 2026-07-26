"""Correspondence gate: every in-scope module has a stub, no stub is orphaned.

Delegates all discovery and drift logic to :class:`dev.docs.apidocs.ApiStubManager`
so this file is the single enforcement surface for module-to-stub correspondence.
Run ``python -m dev.docs.apidocs scaffold`` to regenerate stubs; run
``python -m dev.docs.apidocs scaffold --check`` for a zero-drift gate.

Run via::

    uv run --no-sync pytest dev/docs/tests/test_api_stubs.py -m "unit and hex_core" -q
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.docs.apidocs import ApiStubManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = Path(__file__).resolve().parents[3]
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
    assert any(_SRC_CADRUMO.rglob("*.py")), (
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
