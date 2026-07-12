from __future__ import annotations

import json

import pytest

from ._ledger_corpus_support import _CORPUS, _FILES, _import_corpus, _invoke, _list_rows
from ._ledger_corpus_support import _isolated_backend as _isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_import_full_corpus_persists_operating_scale() -> None:
    _import_corpus()
    rows = _list_rows()
    assert len(rows) >= 500, f"expected operating-scale corpus, got {len(rows)}"


def test_reimport_is_idempotent_dedups() -> None:
    _import_corpus()
    first = len(_list_rows())
    result = _invoke(
        ["--format", "json", "app", "ledger", "import", str(_CORPUS / _FILES[0]), "--provider", "csv"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["imported"] == 0, payload
    assert payload["skipped"] >= 1, payload
    assert len(_list_rows()) == first


def test_import_dry_run_does_not_persist() -> None:
    result = _invoke(
        ["app", "ledger", "import", str(_CORPUS / _FILES[0]), "--provider", "csv", "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    assert _list_rows() == []


def test_import_preserves_foreign_currencies() -> None:
    _import_corpus()
    currencies = {row.get("currency") for row in _list_rows()}
    assert {"EUR", "GBP", "USD"} <= currencies, currencies
