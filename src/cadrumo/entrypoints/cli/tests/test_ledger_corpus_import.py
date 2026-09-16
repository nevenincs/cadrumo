from __future__ import annotations

import json

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....domain.transactions.models import TransactionCatalogue
from ._isolated_profile_storage_fixtures import recorded_fx_isolated_backend
from ._ledger_corpus_support import _CORPUS, _FILES, _import_corpus, _invoke
from .ledger_cli import list_ledger_rows_via_cli as _list_rows

__all__ = ["recorded_fx_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_import_full_corpus_persists_operating_scale() -> None:
    _import_corpus()
    rows = _list_rows()
    assert len(rows) >= 500, f"expected operating-scale corpus, got {len(rows)}"


def test_reimport_is_idempotent_dedups() -> None:
    _import_corpus()
    first = len(_list_rows())
    result = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(_CORPUS / _FILES[0]), "--provider", "csv"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["imported"] == 0, payload
    assert payload["skipped"] >= 1, payload
    assert len(_list_rows()) == first


def test_import_dry_run_does_not_persist() -> None:
    result = _invoke(
        ["app", "ledger", "import", "--file", str(_CORPUS / _FILES[0]), "--provider", "csv", "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    assert _list_rows() == []


def test_import_preserves_foreign_currencies() -> None:
    _import_corpus()
    currencies = {row.get("currency") for row in _list_rows()}
    assert {"EUR", "GBP", "USD"} <= currencies, currencies


def test_each_imported_file_reads_the_ledger_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The catalogue a source is checked against is the one it is written into.

    Import used to read the stored ledger twice per file -- once to diagnose the
    source, once more to merge it -- decrypting and validating every row again.
    """
    _import_corpus()
    loads: list[str] = []
    load = TransactionCatalogueRepository.load

    def counting(self: TransactionCatalogueRepository) -> TransactionCatalogue:
        loads.append(self.bucket_id)
        return load(self)

    monkeypatch.setattr(TransactionCatalogueRepository, "load", counting)
    result = _invoke(["app", "ledger", "import", "--file", str(_CORPUS / _FILES[0]), "--provider", "csv"])

    assert result.exit_code == 0, result.output
    assert len(loads) == 1
