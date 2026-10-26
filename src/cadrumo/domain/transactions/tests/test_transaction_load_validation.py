"""The stored-row validation path keeps every value and every refusal.

A loaded ledger row is a JSON payload validated by :class:`Transaction`. These
tests run that real validation over rows that reach each branch the load path
takes, and over payloads mutated into each refusal it raises, so a change that
makes the path cheaper cannot change what a row becomes or how it is refused.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date, datetime

import pytest
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from ....core.errors.hierarchy import CoreValidationError
from ....core.time.clock import frozen_clock, today_madrid
from ....core.type_adapters import STRICT_STR_KEYED_MAPPING_ADAPTER
from ...calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...calculations.registry.errors import RegistryValidationError
from ..enums import TransactionDirection
from ..errors import TransactionValidationError
from ..models import Transaction
from ..raw_transaction import RawProvenance
from .varied_ledger_seed import MADRID_MIDNIGHT_INSTANTS, varied_transactions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Validate every row inside one generation-pinned authority operation."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _payload(transaction: Transaction) -> dict[str, object]:
    return STRICT_STR_KEYED_MAPPING_ADAPTER.validate_python(json.loads(transaction.model_dump_json()))


def _first_payload(*, treatment: str) -> dict[str, object]:
    for transaction in varied_transactions():
        if transaction.cash_accounting_treatment == treatment:
            return _payload(transaction)
    raise AssertionError(f"the varied seed carries no {treatment!r} row")


def _single_refusal(payload: dict[str, object]) -> ErrorDetails:
    with pytest.raises(ValidationError) as caught:
        Transaction.model_validate_json(json.dumps(payload))
    errors = caught.value.errors()
    assert len(errors) == 1
    return errors[0]


def _registered_cause(error: ErrorDetails) -> BaseException | None:
    context = error.get("ctx", {})
    raised = context.get("error")
    assert isinstance(raised, ValueError)
    return raised.__cause__


def test_reloading_a_stored_row_reproduces_it_exactly() -> None:
    """Every varied row reloads to an equal record with an equal JSON form."""
    rows = varied_transactions()

    for row in rows:
        stored = row.model_dump_json()
        reloaded = Transaction.model_validate_json(stored)

        assert reloaded == row
        assert reloaded.model_dump(mode="json") == row.model_dump(mode="json")
        assert reloaded.model_dump_json() == stored
        assert reloaded.model_fields_set == set(Transaction.model_fields)
        assert Transaction.model_validate_json(reloaded.model_dump_json()).model_fields_set == (
            reloaded.model_fields_set
        )


def test_the_seed_reaches_every_load_branch() -> None:
    """The identity proof above is only as wide as the shapes the seed carries."""
    rows = varied_transactions()

    assert {str(row.cash_accounting_treatment) for row in rows} == {"none", "taxpayer_regime", "supplier_regime"}
    assert any(row.attachment_ids for row in rows)
    assert any(not row.attachment_ids for row in rows)
    assert any(row.cash_accounting_payment_evidence for row in rows)
    assert any(row.classification_history for row in rows)
    assert any(row.concepto_ingreso is not None for row in rows)
    assert any(row.concepto_ingreso is None for row in rows)
    assert any(row.input_classification is not None for row in rows)
    assert any(row.deduction_fact_kind is not None for row in rows)
    assert any(row.counterparty_identification_state is not None for row in rows)
    assert any(row.art_104_tres_exclusion is not None for row in rows)
    assert any(row.exemption_article is not None for row in rows)
    assert any(row.tipo_actividad is not None for row in rows)
    assert any(row.classification_origin is not None for row in rows)
    assert any(row.fx_rate is not None for row in rows)
    assert any(row.raw.currency != "EUR" and row.fx_rate is None for row in rows)
    assert {row.raw.provenance.ingested_at for row in rows} >= set(MADRID_MIDNIGHT_INSTANTS)


@pytest.mark.parametrize("instant", MADRID_MIDNIGHT_INSTANTS)
def test_rows_reload_unchanged_on_either_side_of_madrid_midnight(instant: datetime) -> None:
    """The dated vocabularies a row is checked against follow the Madrid date of each validation."""
    payloads = [row.model_dump_json() for row in varied_transactions()]
    expected = [json.loads(payload) for payload in payloads]

    with frozen_clock(instant):
        reloaded = [Transaction.model_validate_json(payload) for payload in payloads]

    assert [row.model_dump(mode="json") for row in reloaded] == expected


def test_the_midnight_instants_straddle_a_madrid_civil_date() -> None:
    """Each pair of instants is one microsecond apart and falls on two Madrid dates."""
    before_winter, after_winter, before_summer, after_summer = MADRID_MIDNIGHT_INSTANTS
    observed: list[date] = []
    for instant in MADRID_MIDNIGHT_INSTANTS:
        with frozen_clock(instant):
            observed.append(today_madrid())

    assert observed == [date(2025, 12, 31), date(2026, 1, 1), date(2026, 6, 30), date(2026, 7, 1)]
    assert (after_winter - before_winter).total_seconds() == pytest.approx(1e-6)
    assert (after_summer - before_summer).total_seconds() == pytest.approx(1e-6)


def test_an_undeclared_cash_accounting_treatment_is_refused_by_the_registry() -> None:
    payload = _first_payload(treatment="none")
    payload["cash_accounting_treatment"] = "deferred"

    error = _single_refusal(payload)

    assert error["loc"] == ()
    assert error["msg"] == "Value error, cash-accounting treatment 'deferred' is not declared by the facts registry"
    assert isinstance(_registered_cause(error), RegistryValidationError)


def test_settlement_evidence_on_the_ordinary_treatment_is_refused() -> None:
    payload = _first_payload(treatment="taxpayer_regime")
    payload["cash_accounting_treatment"] = "none"

    error = _single_refusal(payload)

    assert error["loc"] == ()
    assert error["msg"] == (
        "Value error, cash_accounting_payment_evidence requires a non-NONE cash_accounting_treatment"
    )
    assert isinstance(_registered_cause(error), TransactionValidationError)


def test_the_supplier_regime_is_refused_on_an_incoming_row() -> None:
    payload = _first_payload(treatment="supplier_regime")
    assert payload["direction"] == TransactionDirection.OUTGOING.value
    payload["direction"] = TransactionDirection.INCOMING.value

    error = _single_refusal(payload)

    assert error["loc"] == ()
    assert error["msg"] == (
        "Value error, supplier-regime cash-accounting treatment is only valid on received/purchase rows"
    )
    assert isinstance(_registered_cause(error), TransactionValidationError)


def test_a_cash_accounting_row_without_its_operation_date_is_refused() -> None:
    payload = _first_payload(treatment="taxpayer_regime")
    payload["operation_date"] = None

    error = _single_refusal(payload)

    assert error["loc"] == ()
    assert error["msg"] == "Value error, operation_date is required when cash_accounting_treatment is not NONE"
    assert isinstance(_registered_cause(error), TransactionValidationError)


def test_the_supplier_regime_stays_valid_on_an_outgoing_row() -> None:
    payload = _first_payload(treatment="supplier_regime")

    restored = Transaction.model_validate_json(json.dumps(payload))

    assert restored.cash_accounting_treatment == "supplier_regime"
    assert restored.direction is TransactionDirection.OUTGOING


def test_an_unknown_plain_enum_token_is_refused_on_its_field() -> None:
    payload = _first_payload(treatment="none")
    payload["direction"] = "sideways"

    error = _single_refusal(payload)

    assert error["loc"] == ("direction",)
    assert error["type"] == "enum"
    assert error["input"] == "sideways"


def test_an_absent_required_enum_is_refused_rather_than_defaulted() -> None:
    payload = _first_payload(treatment="none")
    payload["direction"] = None

    error = _single_refusal(payload)

    assert error["loc"] == ("direction",)
    assert error["type"] == "enum"


def test_an_undeclared_registry_token_is_refused_on_its_field() -> None:
    payload = _first_payload(treatment="none")
    payload["concepto_ingreso"] = "bogus_concepto"

    error = _single_refusal(payload)

    assert error["loc"] == ("concepto_ingreso",)
    assert "bogus_concepto" in error["msg"]
    assert isinstance(_registered_cause(error), TransactionValidationError)


def test_absent_optional_tokens_stay_absent() -> None:
    payload = _first_payload(treatment="none")
    for field in (
        "concepto_ingreso",
        "deduction_fact_kind",
        "input_classification",
        "counterparty_identification_state",
        "iva_category",
        "exemption_article",
        "art_104_tres_exclusion",
        "tipo_actividad",
        "classification_origin",
    ):
        payload[field] = None
    payload["deduction_provenance"] = None
    payload["counterparty_country"] = None
    payload["taxable_base"] = None
    payload["iva_rate"] = None
    payload["iva_amount"] = None

    restored = Transaction.model_validate_json(json.dumps(payload))

    assert restored.concepto_ingreso is None
    assert restored.deduction_fact_kind is None
    assert restored.input_classification is None
    assert restored.counterparty_identification_state is None
    assert restored.iva_category is None
    assert restored.exemption_article is None
    assert restored.art_104_tres_exclusion is None
    assert restored.tipo_actividad is None
    assert restored.classification_origin is None


def test_collections_freeze_to_tuples_whether_empty_absent_or_populated() -> None:
    payload = _first_payload(treatment="none")
    payload["attachment_ids"] = []
    del payload["edit_lineage"]
    payload["classification_history"] = []

    empty = Transaction.model_validate_json(json.dumps(payload))
    payload["attachment_ids"] = [" attachment-a ", "attachment-b"]
    populated = Transaction.model_validate_json(json.dumps(payload))

    assert empty.attachment_ids == ()
    assert empty.edit_lineage == ()
    assert empty.classification_history == ()
    assert populated.attachment_ids == ("attachment-a", "attachment-b")


def test_a_null_collection_is_refused_rather_than_emptied() -> None:
    """A stored row always writes its collections as arrays, so ``null`` is not one of them."""
    payload = _first_payload(treatment="none")
    payload["edit_lineage"] = None

    error = _single_refusal(payload)

    assert error["loc"] == ("edit_lineage",)
    assert error["type"] == "tuple_type"


def test_a_collection_that_is_not_an_array_is_refused() -> None:
    payload = _first_payload(treatment="none")
    payload["attachment_ids"] = "attachment-a"

    error = _single_refusal(payload)

    assert error["loc"] == ("attachment_ids",)
    assert error["type"] == "tuple_type"


def test_duplicate_collection_members_are_refused() -> None:
    payload = _first_payload(treatment="none")
    payload["attachment_ids"] = ["attachment-a", " attachment-a"]

    error = _single_refusal(payload)

    assert error["loc"] == ("attachment_ids",)
    assert error["msg"] == "Value error, identifier fields must not contain duplicates"
    assert isinstance(_registered_cause(error), TransactionValidationError)


@pytest.mark.parametrize(
    ("ingested_at", "message"),
    [
        ("2026-01-01T12:00:00", "datetime must be timezone-aware UTC"),
        ("2026-01-01T12:00:00+01:00", "datetime must be in UTC"),
    ],
)
def test_a_raw_ingest_instant_outside_utc_is_refused(ingested_at: str, message: str) -> None:
    payload = _first_payload(treatment="none")
    raw = payload["raw"]
    assert isinstance(raw, dict)
    provenance = raw["provenance"]
    assert isinstance(provenance, dict)
    provenance["ingested_at"] = ingested_at

    error = _single_refusal(payload)

    assert error["loc"] == ("raw", "provenance", "ingested_at")
    assert error["msg"] == f"Value error, {message}"


@pytest.mark.parametrize(
    ("ingested_at", "message"),
    [
        ("2026-01-01T12:00:00", "datetime must be timezone-aware UTC"),
        ("2026-01-01T12:00:00+01:00", "datetime must be in UTC"),
    ],
)
def test_a_raw_provenance_instant_outside_utc_names_the_core_utc_rule(ingested_at: str, message: str) -> None:
    payload = _first_payload(treatment="none")
    raw = payload["raw"]
    assert isinstance(raw, dict)
    provenance = raw["provenance"]
    assert isinstance(provenance, dict)
    provenance["ingested_at"] = ingested_at

    with pytest.raises(ValidationError) as caught:
        RawProvenance.model_validate_json(json.dumps(provenance))
    errors = caught.value.errors()

    assert len(errors) == 1
    assert errors[0]["loc"] == ("ingested_at",)
    assert errors[0]["msg"] == f"Value error, {message}"
    assert isinstance(_registered_cause(errors[0]), CoreValidationError)
