"""Persona testimonial: a multi-currency freelance consultant.

Persona: a Spain-resident autonoma who invoices UK (GBP) and US (USD)
clients through Revolut and needs the foreign income plus its FX
conversion to land correctly in the Spanish modelos. This suite drives
the real ``aeat app ledger`` CLI against the operator-testimonial corpus
(``revolut-multi.csv`` carries the GBP/USD/EUR rows) and records, as
durable behaviour assertions, exactly what the operator can and cannot
SEE about currency and FX at import / list / review / export time.

The behaviour these gates pin (each is a real operator-visible fact, not a
synthetic expectation), after the ledger-fx-conversion feature landed
(``feat(ledger): ECB FX import conversion`` + ``surface value_in_eur +
fx_rate on list/review read payloads``):

* The native currency (GBP/USD/EUR) IS preserved on import and surfaced
  on ``list --format json`` (``currency`` field).
* The EUR-equivalent (``value_in_eur``) and the FX rate (``fx_rate``) ARE
  projected onto the operator-facing ``TransactionPayload`` -- so list /
  review / export JSON show the EUR amount and the applied rate. The
  operator CAN audit the conversion from every CLI read surface.
* The CLI import path wires the ECB euro reference-rate normalizer, so a
  GBP/USD row is imported with ``fx_rate``/``value_in_eur`` computed at
  import time; EUR-native rows stay unconverted (both fields None).

These are real-behaviour assertions over the real CLI; they fail loudly if
the projection or import-time conversion regresses, so they double as a
regression fence for the landed FX-conversion surface.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....tests import FIXTURES_DIR
from ....tests.cli_runner import invoke_cached_cli
from ....tests.ledger_cli import list_ledger_rows_via_cli as _list_rows
from ._isolated_profile_storage_fixtures import live_fx_seeded_backend
from ._ledger_corpus_support import _match, _oracle_rules

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CORPUS = FIXTURES_DIR / "financial" / "ledger-corpus"
_REVOLUT = _CORPUS / "revolut-multi.csv"


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


# This module needs live tests enabled because revolut-multi.csv carries
# GBP/USD rows, so importing it drives the CLI's live ECB euro reference-rate
# normalizer rather than the provider's now-guarded default (see
# fx._ecb_provider); that is exactly the isolation `live_fx_isolated_backend`
# already provides.


def _import_revolut() -> None:
    result = _invoke(["app", "ledger", "import", "--file", str(_REVOLUT), "--provider", "csv"])
    assert result.exit_code == 0, result.output


# The imported multi-currency statement is the starting state every test reads
# or disposes from, not the subject. Seeded once and copied per test, so each
# test keeps its own storage root and nothing it changes escapes.
_seeded_origin, live_fx_seeded_world = live_fx_seeded_backend(seed=_import_revolut)
__all__ = ["_seeded_origin", "live_fx_seeded_world"]


def _uk_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for r in rows:
        desc = r.get("description")
        if isinstance(desc, str) and "Payment from UK client" in desc:
            result.append(r)
    return result


def _us_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for r in rows:
        desc = r.get("description")
        if isinstance(desc, str) and "Payment from US client" in desc:
            result.append(r)
    return result


# --- import + currency preservation -----------------------------------------
def test_import_succeeds_and_persists_revolut_rows() -> None:
    """The operator imports the multi-currency Revolut export cleanly."""
    rows = _list_rows()
    assert rows, "import must persist the Revolut multicurrency rows"


def test_native_currency_is_preserved_on_import() -> None:
    """GBP and USD survive import and are visible on the list projection.

    What WORKS: the operator can confirm the native currency of every row
    -- a GBP invoice reads GBP, a USD invoice reads USD, the EUR top-up
    reads EUR. The currency axis is honest end to end.
    """
    rows = _list_rows()
    currencies = {r.get("currency") for r in rows}
    assert {"EUR", "GBP", "USD"} <= currencies, currencies

    for uk in _uk_rows(rows):
        assert uk["currency"] == "GBP", uk
    for us in _us_rows(rows):
        assert us["currency"] == "USD", us


def test_uk_and_us_client_receipts_are_incoming_foreign_income() -> None:
    """The UK/US client receipts land as INCOMING foreign-currency rows."""
    rows = _list_rows()
    uk = _uk_rows(rows)
    us = _us_rows(rows)
    assert uk and us, "corpus must carry UK (GBP) and US (USD) client receipts"
    assert all(r.get("direction") == "INCOMING" for r in uk + us)
    # The native amounts are the GBP/USD figures, not EUR-converted.
    for r in uk + us:
        amount_val = r.get("amount")
        if isinstance(amount_val, (int, float, str)):
            assert float(amount_val) > 0, amount_val


# --- classification against the oracle --------------------------------------
def test_classify_uk_us_receipts_as_export_business_income() -> None:
    """Classify the foreign client receipts as export business income.

    The oracle marks both ``Payment from UK client`` and
    ``Payment from US client`` as BUSINESS / export_third_country_zero_rated.
    The operator classifies them through the real CLI and the persisted
    classification reflects it.
    """
    rules = _oracle_rules()
    rows = _list_rows()
    targets = _uk_rows(rows)[:1] + _us_rows(rows)[:1]
    assert len(targets) == 2

    for row in targets:
        desc = row.get("description")
        tx_id = row.get("transaction_id")
        assert isinstance(desc, str)
        assert isinstance(tx_id, str)
        rule = _match(desc, rules)
        assert rule is not None, desc
        assert rule.get("classification") == "BUSINESS"
        assert rule.get("iva_category") == "export_third_country_zero_rated"
        result = _invoke(
            [
                "app",
                "ledger",
                "classify",
                tx_id,
                "--classification",
                "BUSINESS",
                "--iva-category",
                "export_third_country_zero_rated",
            ],
        )
        assert result.exit_code == 0, result.output

    by_id = {r.get("transaction_id"): r for r in _list_rows() if isinstance(r.get("transaction_id"), str)}
    for row in targets:
        tx_id = row.get("transaction_id")
        assert isinstance(tx_id, str)
        assert by_id.get(tx_id, {}).get("business_classification") == "BUSINESS"


# --- FX visibility: the core multicurrency testimonial ----------------------
def test_list_json_surfaces_eur_equivalent_and_fx_rate() -> None:
    """The operator CAN see the EUR conversion on list output.

    The domain ``Transaction`` declares ``value_in_eur`` and ``fx_rate``,
    and the operator-facing ``TransactionPayload`` now projects both (the
    ledger-fx-conversion read-payload feature). A GBP invoice shows
    currency=GBP plus its EUR-equivalent and the applied rate, so the
    operator can audit the conversion from the list surface.
    """
    rows = _list_rows()
    uk = _uk_rows(rows)[0]
    # The native currency/amount are present...
    assert uk["currency"] == "GBP"
    # ...and the EUR-equivalent + applied rate are projected for the foreign row.
    assert uk.get("value_in_eur") is not None, uk
    assert uk.get("fx_rate") is not None, uk


def test_export_json_surfaces_eur_equivalent_and_fx_rate(tmp_path: Path) -> None:
    """The JSONL export carries the EUR-equivalent and rate.

    The operator who exports for a gestor now hands over the converted EUR
    figure and FX provenance alongside the native GBP/USD amount -- the
    downstream reader does not have to re-source the rates independently.
    """
    out = tmp_path / "revolut-export.jsonl"
    exported = _invoke(["app", "ledger", "export", "--output", str(out), "--export-format", "jsonl"])
    assert exported.exit_code == 0, exported.output
    text = out.read_text(encoding="utf-8")
    assert "GBP" in text, "export must carry the native currency"
    assert "value_in_eur" in text, "export must surface the EUR-equivalent"
    assert "fx_rate" in text, "export must surface the applied FX rate"


def test_import_computes_eur_equivalent_for_foreign_rows() -> None:
    """The CLI import path computes the EUR-equivalent for foreign rows.

    ``import_ledger_source`` wires the ECB euro reference-rate normalizer,
    so a GBP/USD row is persisted with ``fx_rate``/``value_in_eur``
    computed at import time; EUR-native rows stay unconverted. We confirm
    by re-loading the persisted catalogue through the real repository and
    inspecting the domain field directly.
    """
    from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository

    repo = TransactionCatalogueRepository(bucket_id="00000000-0000-4000-8000-000000000000")
    catalogue = repo.load()
    foreign = [tx for tx in catalogue.values() if tx.raw.currency in {"GBP", "USD"}]
    eur = [tx for tx in catalogue.values() if tx.raw.currency == "EUR"]
    assert foreign, "persisted catalogue must contain GBP/USD rows"
    # The EUR-equivalent is computed at import: the operator has a converted value.
    assert all(tx.value_in_eur is not None for tx in foreign), (
        "CLI import did not compute value_in_eur for foreign rows"
    )
    assert all(tx.fx_rate is not None for tx in foreign)
    # EUR-native rows stay unconverted (no false conversion).
    assert all(tx.value_in_eur is None and tx.fx_rate is None for tx in eur)
