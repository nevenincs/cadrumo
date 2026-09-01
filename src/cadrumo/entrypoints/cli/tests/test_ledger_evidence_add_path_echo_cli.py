"""Real-CLI regression: ``ledger evidence add`` echoes the operator's argv path verbatim.

The evidence-identity fix stores the argv-faithful ``source_path`` on the record
and the ``--format json`` envelope. This gate pins the separator handling: the
echo must be the operator's argv string VERBATIM, never a ``pathlib.Path``
``str()`` rendering (which normalizes ``/`` to ``\\`` on Windows). Without this,
the persisted path and the envelope flap between a Windows dev box and Linux CI
for the same fixture, breaking cross-OS replay goldens. Byte access still
resolves the path; only the echoed provenance breadcrumb is argv-verbatim.

Every case drives the real Typer CLI tree and a real encrypted bucket session.
No mocks, stubs, or monkeypatch of the write path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ....tests.env_scope import scoped_cwd
from .ledger_ux_support import _invoke, _open_bucket_session

__all__ = ["_open_bucket_session"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_evidence_add_echoes_forward_slash_argv_path_verbatim(tmp_path: Path) -> None:
    """A forward-slash relative argv path is echoed forward-slash, even on Windows.

    The CLI takes the source path as a raw ``str`` (not a ``Path``), so the
    operator's separators survive onto the record and envelope unchanged. This is
    a genuine regression gate on Windows, where a ``Path`` argument would render
    ``fixtures\\factura.pdf``; on POSIX the assertion holds trivially since ``/``
    is already the native separator.
    """
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "factura.pdf").write_bytes(b"%PDF-1.4 argv-verbatim")

    argv_path = "fixtures/factura.pdf"  # forward slashes, exactly as an operator types
    with scoped_cwd(tmp_path):
        added = _invoke(["--format", "json", "app", "ledger", "evidence", "add", argv_path, "--supplier", "Acme SL"])
    assert added.exit_code == 0, added.output

    record = json.loads(added.output)["result"]
    assert record["source_path"] == argv_path, (
        "evidence add must echo the operator's argv path verbatim (separators preserved), never the "
        f"OS-native Path rendering; got {record['source_path']!r}"
    )
    assert "\\" not in record["source_path"], "argv separators must not be normalized to backslashes"
