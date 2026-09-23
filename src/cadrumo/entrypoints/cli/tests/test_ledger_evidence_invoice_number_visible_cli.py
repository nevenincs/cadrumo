"""Real-CLI regression: every ``ledger evidence`` surface shows the invoice number as recorded.

The supplier's invoice number is what an operator checks before confirming a
purchase invoice. It was once rewritten to a ``sha256:`` prefix in every
evidence output, so an operator who typed ``--invoice-number`` could no longer
read back what they typed, while ``evidence confirm`` and ``invoice view``
showed the same number in clear.

Every case drives the real Typer CLI tree and a real encrypted bucket session.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ....tests.env_scope import scoped_cwd
from .ledger_ux_support import _invoke, _open_bucket_session

__all__ = ["_open_bucket_session"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_INVOICE_NUMBER = "F-2026/0142"
_UPDATED_NUMBER = "F-2026/0143"


def _result(arguments: list[str]) -> dict[str, object]:
    invoked = _invoke(["--format", "json", "app", "ledger", "evidence", *arguments])
    assert invoked.exit_code == 0, invoked.output
    result = json.loads(invoked.output)["result"]
    assert isinstance(result, dict)
    return {str(key): value for key, value in result.items()}


def test_evidence_add_view_list_and_update_show_the_invoice_number_as_recorded(tmp_path: Path) -> None:
    (tmp_path / "factura.pdf").write_bytes(b"%PDF-1.4 synthetic evidence")
    with scoped_cwd(tmp_path):
        added = _result(["add", "factura.pdf", "--supplier", "Acme SL", "--invoice-number", _INVOICE_NUMBER])
        evidence_id = str(added["evidence_id"])
        viewed = _result(["view", evidence_id])
        listed = _result(["list"])
        updated = _result(["update", evidence_id, "--invoice-number", _UPDATED_NUMBER])
        text_view = _invoke(["app", "ledger", "evidence", "view", evidence_id])

    assert added["invoice_number"] == _INVOICE_NUMBER
    assert viewed["invoice_number"] == _INVOICE_NUMBER
    rows = listed["rows"]
    assert isinstance(rows, list)
    assert [row["invoice_number"] for row in rows if row["evidence_id"] == evidence_id] == [_INVOICE_NUMBER]
    assert updated["invoice_number"] == _UPDATED_NUMBER
    assert text_view.exit_code == 0, text_view.output
    assert f"invoice_number\t{_UPDATED_NUMBER}" in text_view.output.splitlines()
