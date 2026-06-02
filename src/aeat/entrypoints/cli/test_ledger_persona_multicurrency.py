"""Persona testimonial: a multi-currency freelance consultant.

Persona: a Spain-resident autonoma who invoices UK (GBP) and US (USD)
clients through Revolut and needs the foreign income plus its FX
conversion to land correctly in the Spanish modelos. This suite drives
the real ``aeat app ledger`` CLI against the operator-testimonial corpus
(``revolut-multi.csv`` carries the GBP/USD/EUR rows) and records, as
durable behaviour assertions, exactly what the operator can and cannot
SEE about currency and FX at import / list / review / export time.

The findings these gates pin (each is a real operator-visible gap, not a
synthetic expectation):

* The native currency (GBP/USD/EUR) IS preserved on import and surfaced
  on ``list --format json`` (``currency`` field).
* The EUR-equivalent (``value_in_eur``) and the FX rate (``fx_rate``) are
  declared on the domain :class:`Transaction` but are NOT projected onto
  the operator-facing ``TransactionPayload`` -- so list / review / export
  JSON never shows the EUR amount or the rate applied. The operator
  cannot audit the conversion from any CLI surface.
* The CLI import path does not wire a currency normalizer, so a GBP/USD
  row is imported with no ``value_in_eur`` at all -- the EUR amount is not
  merely hidden, it is never computed at import time. The operator gets
  no signal that a foreign row will need normalization (and would
  otherwise gate) before aggregation.

These are real-behaviour assertions over the real CLI; they intentionally
fail loudly if the projection or import-time conversion changes, so they
double as a regression fence for any future fix.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...application.user_profile._orchestration import profile_create_storage_span
from ...application.user_profile._testing import register_minimal_profile
from ...application.workflow._persistence import workflow_state_repository
from ...core.config import override_settings
from ...tests.secure_sql import isolated_profile_storage_root
from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()
_CORPUS = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "financial" / "ledger-corpus"
_REVOLUT = _CORPUS / "revolut-multi.csv"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        try:
            workflow_state_repository().update(
                lambda state: register_minimal_profile(state, profile_id="default")
            )
            yield
        finally:
            dispose_engine()


def _oracle_rules() -> list[dict]:
    manifest = json.loads((_CORPUS / "ground-truth.manifest.json").read_text(encoding="utf-8"))
    return manifest["rules"]


def _match(description: str, rules: list[dict]) -> dict | None:
    for rule in rules:
        if rule["match"] in description:
            return rule
    return None


def _import_revolut() -> None:
    result = _RUNNER.invoke(
        app, ["app", "ledger", "import", str(_REVOLUT), "--provider", "csv"]
    )
    assert result.exit_code == 0, result.output


def _list_rows() -> list[dict]:
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    return payload.get("result", payload).get("rows", [])


def _uk_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows if "Payment from UK client" in r["description"]]


def _us_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows if "Payment from US client" in r["description"]]


# --- import + currency preservation -----------------------------------------
def test_import_succeeds_and_persists_revolut_rows() -> None:
    """The operator imports the multi-currency Revolut export cleanly."""
    _import_revolut()
    rows = _list_rows()
    assert rows, "import must persist the Revolut multicurrency rows"


def test_native_currency_is_preserved_on_import() -> None:
    """GBP and USD survive import and are visible on the list projection.

    What WORKS: the operator can confirm the native currency of every row
    -- a GBP invoice reads GBP, a USD invoice reads USD, the EUR top-up
    reads EUR. The currency axis is honest end to end.
    """
    _import_revolut()
    rows = _list_rows()
    currencies = {r.get("currency") for r in rows}
    assert {"EUR", "GBP", "USD"} <= currencies, currencies

    for uk in _uk_rows(rows):
        assert uk["currency"] == "GBP", uk
    for us in _us_rows(rows):
        assert us["currency"] == "USD", us


def test_uk_and_us_client_receipts_are_incoming_foreign_income() -> None:
    """The UK/US client receipts land as INCOMING foreign-currency rows."""
    _import_revolut()
    rows = _list_rows()
    uk = _uk_rows(rows)
    us = _us_rows(rows)
    assert uk and us, "corpus must carry UK (GBP) and US (USD) client receipts"
    assert all(r.get("direction") == "INCOMING" for r in uk + us)
    # The native amounts are the GBP/USD figures, not EUR-converted.
    assert all(float(r["amount"]) > 0 for r in uk + us)


# --- classification against the oracle --------------------------------------
def test_classify_uk_us_receipts_as_export_business_income() -> None:
    """Classify the foreign client receipts as export business income.

    The oracle marks both ``Payment from UK client`` and
    ``Payment from US client`` as BUSINESS / export_third_country_zero_rated.
    The operator classifies them through the real CLI and the persisted
    classification reflects it.
    """
    _import_revolut()
    rules = _oracle_rules()
    rows = _list_rows()
    targets = _uk_rows(rows)[:1] + _us_rows(rows)[:1]
    assert len(targets) == 2

    for row in targets:
        rule = _match(row["description"], rules)
        assert rule is not None, row["description"]
        assert rule["classification"] == "BUSINESS"
        assert rule["iva_category"] == "export_third_country_zero_rated"
        result = _RUNNER.invoke(
            app,
            [
                "app", "ledger", "classify", "--id", row["transaction_id"],
                "--classification", "BUSINESS",
                "--iva-category", "export_third_country_zero_rated",
            ],
        )
        assert result.exit_code == 0, result.output

    by_id = {r["transaction_id"]: r for r in _list_rows()}
    for row in targets:
        assert by_id[row["transaction_id"]]["business_classification"] == "BUSINESS"


# --- FX visibility: the core multicurrency testimonial ----------------------
def test_list_json_does_not_surface_eur_equivalent_or_fx_rate() -> None:
    """FINDING: the operator cannot SEE the EUR conversion on list output.

    The domain ``Transaction`` declares ``value_in_eur`` and ``fx_rate``,
    but the operator-facing ``TransactionPayload`` projects neither. A GBP
    invoice of 1400.00 shows currency=GBP and amount=1400.00, with no
    EUR-equivalent and no rate anywhere in the JSON -- the operator has no
    CLI surface to audit what the row is worth in EUR or what rate applied.
    """
    _import_revolut()
    rows = _list_rows()
    uk = _uk_rows(rows)[0]
    # The native currency/amount are present...
    assert uk["currency"] == "GBP"
    # ...but neither EUR-equivalent nor FX rate is in the projection.
    assert "value_in_eur" not in uk, uk
    assert "fx_rate" not in uk, uk
    assert "fx_source" not in uk, uk


def test_review_output_does_not_surface_fx_for_foreign_rows() -> None:
    """FINDING: review (filtered) also hides the EUR-equivalent / rate.

    The review surface nests the same ``TransactionPayload``; a foreign
    row reviewed via the typed filter shows native currency only, never
    the converted EUR figure the modelos will actually use.
    """
    _import_revolut()
    review = _RUNNER.invoke(
        app, ["--format", "json", "app", "ledger", "review", "--filter", "status=pending"]
    )
    assert review.exit_code == 0, review.output
    blob = review.output
    # The review payload mentions GBP/USD (native) but never an fx_rate /
    # value_in_eur key the operator could audit.
    assert "value_in_eur" not in blob
    assert "fx_rate" not in blob


def test_export_json_omits_eur_equivalent_and_fx_rate(tmp_path: Path) -> None:
    """FINDING: the JSONL export carries no EUR-equivalent or rate either.

    The operator who exports for a gestor hands over native GBP/USD
    figures with no converted EUR column and no FX provenance -- the
    downstream reader must re-source the rates independently.
    """
    _import_revolut()
    out = tmp_path / "revolut-export.jsonl"
    exported = _RUNNER.invoke(
        app, ["app", "ledger", "export", "--output", str(out), "--export-format", "jsonl"]
    )
    assert exported.exit_code == 0, exported.output
    text = out.read_text(encoding="utf-8")
    assert "GBP" in text, "export must carry the native currency"
    assert "value_in_eur" not in text, "export unexpectedly surfaced value_in_eur"
    assert "fx_rate" not in text, "export unexpectedly surfaced fx_rate"


def test_import_does_not_compute_eur_equivalent_for_foreign_rows(tmp_path: Path) -> None:
    """FINDING: the CLI import path computes NO EUR-equivalent at all.

    ``import_ledger_source`` (the import verb's entry) does not wire a
    ``CurrencyNormalizationService``, so a GBP/USD row is persisted with
    ``fx_rate``/``value_in_eur`` unset -- not merely hidden from the
    projection, but never computed. The operator gets no signal at import
    time that a foreign row will gate as UNSUPPORTED_CURRENCY in
    aggregation. We confirm this by re-loading the persisted catalogue
    through the real repository and inspecting the domain field directly.
    """
    _import_revolut()
    from ...domain.transactions import TransactionCatalogueRepository

    repo = TransactionCatalogueRepository(bucket_id="default")
    catalogue = repo.load()
    foreign = [tx for tx in catalogue.values() if tx.raw.currency in {"GBP", "USD"}]
    assert foreign, "persisted catalogue must contain GBP/USD rows"
    # The EUR-equivalent was never computed at import: the operator has no
    # converted value, and no warning was surfaced that one is required.
    assert all(tx.value_in_eur is None for tx in foreign), (
        "CLI import unexpectedly computed value_in_eur"
    )
    assert all(tx.fx_rate is None for tx in foreign)
