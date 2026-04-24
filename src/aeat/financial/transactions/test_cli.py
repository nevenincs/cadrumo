"""CLI smoke tests for ``aeat financial txs``."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...cli import app as root_app
from .. import CsvProvider, OfxProvider, RawProvenance, SourceFormat
from ..providers import RawTransaction
from . import (
    BusinessClassification,
    LLMClassificationResponse,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    load_transactions,
    register_classifier,
    save_transactions,
    set_classification,
    unregister_classifier,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]

_RUNNER = CliRunner()
_CATALOGUE_FILENAME = "transactions.json"


def _sample_transaction(
    *,
    provider_id: str,
    amount: Decimal,
    description: str,
    classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
) -> Transaction:
    raw = RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=amount,
        currency="EUR",
        counterparty="Vendor SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=3,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 10, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": description},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING if amount < 0 else TransactionDirection.INCOMING,
            "business_classification": classification,
        }
    )


def _write_catalogue(tmp_path: Path) -> TransactionCatalogue:
    catalogue = TransactionCatalogue.from_transactions(
        [
            _sample_transaction(
                provider_id="provider-row-1",
                amount=Decimal("-45.00"),
                description="Train ticket",
            ),
            _sample_transaction(
                provider_id="provider-row-2",
                amount=Decimal("1200.00"),
                description="Client payment",
                classification=BusinessClassification.BUSINESS,
            ),
        ]
    )
    save_transactions(catalogue, tmp_path / _CATALOGUE_FILENAME)
    return catalogue


def _write_four_state_catalogue(tmp_path: Path) -> TransactionCatalogue:
    """Seed a catalogue with one transaction in each of the four pipeline states.

    Encodes the Kent success moment from #237 so tests can filter by
    every non-classified state and verify Kent sees only the subset he
    asked for.
    """
    catalogue = TransactionCatalogue.from_transactions(
        [
            _sample_transaction(
                provider_id="pipeline-state-1",
                amount=Decimal("-12.00"),
                description="New incoming",
                classification=BusinessClassification.NOT_YET_PROCESSED,
            ),
            _sample_transaction(
                provider_id="pipeline-state-2",
                amount=Decimal("-34.00"),
                description="Pipeline could not decide",
                classification=BusinessClassification.PROCESSED_UNCLASSIFIED,
            ),
            _sample_transaction(
                provider_id="pipeline-state-3",
                amount=Decimal("-56.00"),
                description="Explicitly skipped",
                classification=BusinessClassification.SKIPPED_BY_RULE,
            ),
            _sample_transaction(
                provider_id="pipeline-state-4",
                amount=Decimal("-78.00"),
                description="Failed validation",
                classification=BusinessClassification.FAILED_VALIDATION,
            ),
        ]
    )
    save_transactions(catalogue, tmp_path / _CATALOGUE_FILENAME)
    return catalogue


def test_financial_txs_list_filters_by_state_option(tmp_path: Path) -> None:
    """`aeat financial txs list --state PROCESSED_UNCLASSIFIED` should filter catalogue output."""
    catalogue = _write_four_state_catalogue(tmp_path)
    by_state = {transaction.business_classification: transaction.transaction_id for transaction in catalogue.values()}

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "list", "--state", "PROCESSED_UNCLASSIFIED"],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    assert by_state[BusinessClassification.PROCESSED_UNCLASSIFIED] in result.output
    for state in (
        BusinessClassification.NOT_YET_PROCESSED,
        BusinessClassification.SKIPPED_BY_RULE,
        BusinessClassification.FAILED_VALIDATION,
    ):
        assert by_state[state] not in result.output


def test_financial_txs_list_every_pipeline_state_is_independently_filterable(tmp_path: Path) -> None:
    """Kent success moment from #237: each of the four pipeline states filters independently."""
    catalogue = _write_four_state_catalogue(tmp_path)
    expected_by_state = {
        transaction.business_classification: transaction.transaction_id for transaction in catalogue.values()
    }

    for state in (
        BusinessClassification.NOT_YET_PROCESSED,
        BusinessClassification.PROCESSED_UNCLASSIFIED,
        BusinessClassification.SKIPPED_BY_RULE,
        BusinessClassification.FAILED_VALIDATION,
    ):
        result = _RUNNER.invoke(
            root_app,
            ["financial", "txs", "list", "--state", state.value],
            env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
        )
        assert result.exit_code == 0, result.output
        assert expected_by_state[state] in result.output
        for other_state, other_id in expected_by_state.items():
            if other_state is not state:
                assert other_id not in result.output


def test_financial_txs_list_deprecated_unclassified_flag_aliases_processed_unclassified(tmp_path: Path) -> None:
    """The hidden `--unclassified` flag must still resolve to `--state PROCESSED_UNCLASSIFIED`."""
    catalogue = _write_four_state_catalogue(tmp_path)
    expected = next(
        transaction.transaction_id
        for transaction in catalogue.values()
        if transaction.business_classification is BusinessClassification.PROCESSED_UNCLASSIFIED
    )

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "list", "--unclassified"],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    assert expected in result.output


def test_financial_txs_list_rejects_combination_of_state_and_unclassified(tmp_path: Path) -> None:
    """Passing both `--state` and `--unclassified` must exit with a clear error."""
    _write_four_state_catalogue(tmp_path)

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "list", "--state", "BUSINESS", "--unclassified"],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 2
    assert "mutually exclusive" in result.output


def test_financial_txs_classify_embeds_reason_into_history(tmp_path: Path) -> None:
    """`aeat financial txs classify --reason` should embed Kent's justification in history."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify",
            transaction.transaction_id,
            "--as",
            "BUSINESS",
            "--reason",
            "Kent flagged this as a client invoice",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["business_classification"] == "BUSINESS"
    restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    updated = restored.get(transaction.transaction_id)
    assert updated is not None
    assert len(updated.classification_history) == 1
    appended_head = updated.classification_history[0]
    assert appended_head.business_classification is BusinessClassification.NOT_YET_PROCESSED
    assert appended_head.category_id is None
    assert appended_head.notes == ""


def test_financial_txs_show_emits_json_payload(tmp_path: Path) -> None:
    """`aeat financial txs show <id>` should emit the stored transaction JSON."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "show", transaction.transaction_id],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["transaction_id"] == transaction.transaction_id
    assert payload["business_classification"] == "NOT_YET_PROCESSED"


def test_financial_txs_classify_updates_catalogue_file(tmp_path: Path) -> None:
    """`aeat financial txs classify` should persist a manual classification."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify",
            transaction.transaction_id,
            "--as",
            "MIXED",
            "--pct",
            "0.5",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["business_classification"] == "MIXED"
    assert payload["business_pct"] == "0.5"
    restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    updated = restored.get(transaction.transaction_id)
    assert updated is not None
    assert updated.business_classification is BusinessClassification.MIXED


def test_financial_txs_classify_rejects_invalid_business_pct_combo(tmp_path: Path) -> None:
    """`aeat financial txs classify` should exit cleanly on invalid percentage usage."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify",
            transaction.transaction_id,
            "--as",
            "BUSINESS",
            "--pct",
            "0.5",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 2
    assert "--pct can only be used together with --as MIXED" in result.output


def test_financial_txs_classify_accepts_category_and_reason(tmp_path: Path) -> None:
    """`aeat financial txs classify` should persist category and reason/notes."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify",
            transaction.transaction_id,
            "--as",
            "BUSINESS",
            "--category",
            "cuotas_autonomos_ss",
            "--reason",
            "Payment for social security",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["business_classification"] == "BUSINESS"
    assert payload["category_id"] == "cuotas_autonomos_ss"
    assert payload["notes"] == "Payment for social security"

    restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    updated = restored.get(transaction.transaction_id)
    assert updated is not None
    assert updated.category_id == "cuotas_autonomos_ss"
    assert updated.notes == "Payment for social security"


def test_financial_txs_classify_allows_metadata_only_update(tmp_path: Path) -> None:
    """Kent can add a category and notes without repeating the classification target."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(item for item in catalogue.values() if item.direction is TransactionDirection.OUTGOING)
    updated = set_classification(
        catalogue,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="manual",
        reason="Initial manual classification",
    )
    save_transactions(updated, tmp_path / _CATALOGUE_FILENAME)

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify",
            transaction.transaction_id,
            "--category",
            "asesoria_fiscal",
            "--reason",
            "Accountant subscription",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["business_classification"] == "BUSINESS"
    assert payload["category_id"] == "asesoria_fiscal"
    assert payload["notes"] == "Accountant subscription"


def test_financial_txs_classify_rejects_category_for_unprocessed_transaction(tmp_path: Path) -> None:
    """Kent should classify the transaction first before assigning a spending category."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(
        item for item in catalogue.values() if item.business_classification is BusinessClassification.NOT_YET_PROCESSED
    )

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify",
            transaction.transaction_id,
            "--category",
            "software_suscripcion",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 2
    assert "--category requires a business/private classification first" in result.output


def test_financial_txs_classify_rejects_category_for_incoming_payment(tmp_path: Path) -> None:
    """Expense categories must not be assignable to incoming payments."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(item for item in catalogue.values() if item.direction is TransactionDirection.INCOMING)

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify",
            transaction.transaction_id,
            "--as",
            "BUSINESS",
            "--category",
            "software_suscripcion",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 2
    assert "incoming payments should not be assigned an expense category" in result.output


def _write_ndjson_from_provider(tmp_path: Path, fixture_name: str, *, ofx: bool = False) -> tuple[Path, list[Decimal]]:
    provider = OfxProvider() if ofx else CsvProvider()
    fixture = Path("tests/fixtures/financial") / fixture_name
    rows = tuple(provider.ingest(fixture))
    target = tmp_path / ("raw.ofx.ndjson" if ofx else "raw.csv.ndjson")
    target.write_text("\n".join(row.model_dump_json() for row in rows) + "\n", encoding="utf-8")
    return target, sorted(row.amount for row in rows)


def test_financial_txs_build_creates_catalogue_from_csv_ingest_ndjson(tmp_path: Path) -> None:
    """`financial txs build` should preserve both rows from CSV ingest output."""
    source, expected_amounts = _write_ndjson_from_provider(tmp_path, "synthetic-transactions.csv")

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "build", str(source)],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    amounts = sorted(transaction.raw.amount for transaction in restored.values())
    assert len(restored) == 2
    assert amounts == expected_amounts


def test_financial_txs_build_creates_catalogue_from_ofx_ingest_ndjson(tmp_path: Path) -> None:
    """`financial txs build` should preserve both rows from OFX ingest output."""
    source, expected_amounts = _write_ndjson_from_provider(tmp_path, "synthetic-transactions.ofx", ofx=True)

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "build", str(source)],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    amounts = sorted(transaction.raw.amount for transaction in restored.values())
    assert len(restored) == 2
    assert amounts == expected_amounts


def test_financial_txs_build_refuses_to_overwrite_existing_catalogue_without_replace(tmp_path: Path) -> None:
    """Kent should hear a clear refusal instead of silently overwriting existing work."""
    _write_catalogue(tmp_path)
    source, _ = _write_ndjson_from_provider(tmp_path, "synthetic-transactions.csv")

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "build", str(source)],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 2
    assert "--replace" in result.output


def test_financial_txs_build_rejects_empty_ndjson(tmp_path: Path) -> None:
    """An empty NDJSON file should be treated as operator error, not a successful empty build."""
    source = tmp_path / "empty.ndjson"
    source.write_text("", encoding="utf-8")

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "build", str(source)],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 2
    assert "no RawTransaction rows were found" in result.output


def test_financial_txs_build_rejects_duplicate_raw_rows_cleanly(tmp_path: Path) -> None:
    """Duplicate raw rows should fail with a CLI error, not a traceback."""
    raw = RawTransaction(
        transaction_id="dup-row",
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=Decimal("-18.50"),
        currency="EUR",
        counterparty="Proveedor SL",
        description="Cuota repetida",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=8,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": "Cuota repetida"},
    )
    source = tmp_path / "duplicate.ndjson"
    line = raw.model_dump_json()
    source.write_text(f"{line}\n{line}\n", encoding="utf-8")

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "build", str(source)],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 2
    assert "unable to build transaction catalogue" in result.output
    assert "duplicate transaction_id" in result.output


def test_financial_txs_build_accepts_cp1252_encoded_ndjson(tmp_path: Path) -> None:
    """Kent's redirected Windows files should still build when the NDJSON lands in cp1252."""
    raw = RawTransaction(
        transaction_id="accented-row",
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=Decimal("-18.50"),
        currency="EUR",
        counterparty="Cafetería Sol",
        description="Suscripción gestión",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=7,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 11, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": "Suscripción gestión"},
    )
    source = tmp_path / "cp1252.ndjson"
    source.write_bytes((raw.model_dump_json() + "\n").encode("cp1252"))

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "build", str(source)],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    assert len(restored) == 1


def test_financial_txs_build_accepts_utf8_bom_ndjson(tmp_path: Path) -> None:
    """A UTF-8 BOM should not poison the first JSON line."""
    raw = RawTransaction(
        transaction_id="bom-row",
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=Decimal("-22.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description="Licencia anual",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=9,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 13, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": "Licencia anual"},
    )
    source = tmp_path / "bom.ndjson"
    source.write_bytes(("﻿" + raw.model_dump_json() + "\n").encode("utf-8"))

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "build", str(source)],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    assert len(restored) == 1


def test_financial_txs_build_accepts_direct_csv_source(tmp_path: Path) -> None:
    """Kent should be able to build directly from a CSV export without an intermediate NDJSON file."""
    fixture = Path("tests/fixtures/financial/synthetic-transactions.csv")

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "build", str(fixture)],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    assert len(restored) == 2


def _write_confidence_catalogue(tmp_path: Path) -> TransactionCatalogue:
    """Seed a catalogue with confidences set at distinct levels.

    Two transactions start as NOT_YET_PROCESSED; the CLI classifies them
    manually with different confidence levels, then a third remains
    unclassified. This mirrors the Kent scenario from #236.
    """
    catalogue = TransactionCatalogue.from_transactions(
        [
            _sample_transaction(
                provider_id="conf-row-low",
                amount=Decimal("-10.00"),
                description="Uncertain expense",
            ),
            _sample_transaction(
                provider_id="conf-row-high",
                amount=Decimal("-20.00"),
                description="Certain expense",
            ),
            _sample_transaction(
                provider_id="conf-row-bare",
                amount=Decimal("-5.00"),
                description="Still unclassified",
            ),
        ]
    )
    save_transactions(catalogue, tmp_path / _CATALOGUE_FILENAME)
    return catalogue


def test_financial_txs_classify_accepts_confidence_flag(tmp_path: Path) -> None:
    """`--confidence 0.42` must be persisted on the transaction (#236)."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify",
            transaction.transaction_id,
            "--as",
            "BUSINESS",
            "--reason",
            "rule match",
            "--confidence",
            "0.42",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["classification_confidence"] == "0.42"


def test_financial_txs_classify_defaults_manual_confidence_to_one(tmp_path: Path) -> None:
    """Omitting `--confidence` on a manual classify must default to 1.0 (#236)."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify",
            transaction.transaction_id,
            "--as",
            "BUSINESS",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["classification_confidence"] == "1.0"


def test_financial_txs_classify_rejects_invalid_confidence(tmp_path: Path) -> None:
    """A non-numeric `--confidence` must exit with code 2."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify",
            transaction.transaction_id,
            "--as",
            "BUSINESS",
            "--confidence",
            "abc",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 2
    assert "invalid --confidence value" in result.output


def test_financial_txs_classify_rejects_out_of_range_confidence(tmp_path: Path) -> None:
    """An out-of-range `--confidence` must exit with code 2."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify",
            transaction.transaction_id,
            "--as",
            "BUSINESS",
            "--confidence",
            "1.5",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 2
    assert "0..1 range" in result.output


def test_financial_txs_list_filters_by_confidence_below(tmp_path: Path) -> None:
    """`--confidence-below 0.5` must return only low-confidence classifications (#236)."""
    _write_confidence_catalogue(tmp_path)
    env = {"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)}

    def _classify(provider_id: str, classification: str, confidence: str) -> None:
        catalogue = load_transactions(tmp_path / _CATALOGUE_FILENAME)
        target_id = next(tx.transaction_id for tx in catalogue.values() if tx.raw.transaction_id == provider_id)
        result = _RUNNER.invoke(
            root_app,
            [
                "financial",
                "txs",
                "classify",
                target_id,
                "--as",
                classification,
                "--confidence",
                confidence,
            ],
            env=env,
        )
        assert result.exit_code == 0, result.output

    _classify("conf-row-low", "BUSINESS", "0.4")
    _classify("conf-row-high", "BUSINESS", "0.9")

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "list", "--confidence-below", "0.5"],
        env=env,
    )

    assert result.exit_code == 0, result.output
    catalogue = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    ids_by_provider = {tx.raw.transaction_id: tx.transaction_id for tx in catalogue.values()}
    assert ids_by_provider["conf-row-low"] in result.output
    assert ids_by_provider["conf-row-high"] not in result.output
    assert ids_by_provider["conf-row-bare"] not in result.output


def test_financial_txs_list_composes_state_and_confidence_filters(tmp_path: Path) -> None:
    """`--state BUSINESS --confidence-below 0.5` must AND the two filters (#236 + #237)."""
    _write_confidence_catalogue(tmp_path)
    env = {"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)}

    catalogue = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    low_id = next(tx.transaction_id for tx in catalogue.values() if tx.raw.transaction_id == "conf-row-low")
    high_id = next(tx.transaction_id for tx in catalogue.values() if tx.raw.transaction_id == "conf-row-high")
    bare_id = next(tx.transaction_id for tx in catalogue.values() if tx.raw.transaction_id == "conf-row-bare")

    for target_id, label, confidence in (
        (low_id, "BUSINESS", "0.4"),
        (high_id, "BUSINESS", "0.9"),
    ):
        assert (
            _RUNNER.invoke(
                root_app,
                [
                    "financial",
                    "txs",
                    "classify",
                    target_id,
                    "--as",
                    label,
                    "--confidence",
                    confidence,
                ],
                env=env,
            ).exit_code
            == 0
        )

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "list", "--state", "BUSINESS", "--confidence-below", "0.5"],
        env=env,
    )

    assert result.exit_code == 0, result.output
    assert low_id in result.output
    assert high_id not in result.output
    assert bare_id not in result.output


def test_financial_txs_list_rejects_out_of_range_confidence_below(tmp_path: Path) -> None:
    """An out-of-range `--confidence-below` must exit with code 2."""
    _write_catalogue(tmp_path)

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "list", "--confidence-below", "1.5"],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 2
    assert "0..1 range" in result.output


def test_financial_txs_list_empty_confidence_filter_guides_kent(tmp_path: Path) -> None:
    """When a confidence filter matches nothing, Kent must hear WHY, not a bare silence.

    A Kent whose catalogue contains only manual (confidence=1.0) or bare
    (confidence=None) classifications gets empty results from any
    sensible threshold. The message must tell him his manual
    classifications default to 1.0 and that a rule engine / LLM is
    what populates lower scores.
    """
    _write_catalogue(tmp_path)

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "list", "--confidence-below", "0.5"],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    assert "manual classifications default to confidence 1.0" in result.output
    assert "--confidence-below only surfaces results when a rule engine" in result.output


# ── classify-llm (no mocks: concrete test classifiers via registry) ─────


from dataclasses import dataclass  # noqa: E402 — local-only in this section


@dataclass(frozen=True)
class _ScriptedLLMClassifier:
    """Real LLMClassifier implementation that returns a scripted response.

    Used to exercise the classify-llm CLI end-to-end without shelling
    out to a real LLM. Not a mock: it's a plain dataclass with the
    two attributes the protocol requires.
    """

    response: LLMClassificationResponse
    decided_by_value: str

    @property
    def decided_by(self) -> str:
        return self.decided_by_value

    def classify(self, transaction: Transaction) -> LLMClassificationResponse:
        return self.response


from collections.abc import Iterator  # noqa: E402 — local to LLM CLI tests


@pytest.fixture
def scripted_provider() -> Iterator[str]:
    """Register a deterministic classifier; yield its provider name; unregister."""
    name = "test-scripted-0.75"
    response = LLMClassificationResponse(
        classification=BusinessClassification.BUSINESS,
        confidence=Decimal("0.75"),
        reason="scripted test decision",
    )
    classifier = _ScriptedLLMClassifier(response=response, decided_by_value=f"llm:{name}")
    register_classifier(name, lambda **_: classifier)
    try:
        yield name
    finally:
        unregister_classifier(name)


def test_classify_llm_single_persists_the_classifier_decision(
    tmp_path: Path,
    scripted_provider: str,
) -> None:
    """`aeat financial txs classify-llm <id> --provider <scripted>` writes the decision."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify-llm",
            transaction.transaction_id,
            "--provider",
            scripted_provider,
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    updated = restored.get(transaction.transaction_id)
    assert updated is not None
    assert updated.business_classification is BusinessClassification.BUSINESS
    assert updated.classification_confidence == Decimal("0.75")
    assert updated.classified_by == f"llm:{scripted_provider}"
    assert updated.classification_reason == "scripted test decision"


def test_classify_llm_dry_run_does_not_persist(
    tmp_path: Path,
    scripted_provider: str,
) -> None:
    """`--dry-run` must print results without mutating the catalogue."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())
    original_state = transaction.business_classification

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify-llm",
            transaction.transaction_id,
            "--provider",
            scripted_provider,
            "--dry-run",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    assert "dry-run" in result.output
    restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    reloaded = restored.get(transaction.transaction_id)
    assert reloaded is not None
    assert reloaded.business_classification is original_state


def test_classify_llm_all_only_targets_unclassified(
    tmp_path: Path,
    scripted_provider: str,
) -> None:
    """`--all` must classify only NOT_YET_PROCESSED transactions."""
    _write_catalogue(tmp_path)  # seeds one NOT_YET_PROCESSED + one BUSINESS

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "classify-llm", "--provider", scripted_provider, "--all"],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    assert "1 classified" in result.output
    restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    classifier_key = f"llm:{scripted_provider}"
    classifier_touched = [tx for tx in restored.values() if tx.classified_by == classifier_key]
    assert len(classifier_touched) == 1


def test_classify_llm_rejects_both_id_and_all(
    tmp_path: Path,
    scripted_provider: str,
) -> None:
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify-llm",
            transaction.transaction_id,
            "--provider",
            scripted_provider,
            "--all",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 2
    assert "mutually exclusive" in result.output


def test_classify_llm_rejects_missing_target(
    tmp_path: Path,
    scripted_provider: str,
) -> None:
    _write_catalogue(tmp_path)

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "classify-llm", "--provider", scripted_provider],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 2
    assert "transaction-id argument or use --all" in result.output


def test_classify_llm_populates_notes_field_for_parity_with_manual_path(
    tmp_path: Path,
    scripted_provider: str,
) -> None:
    """LLM path must write the same reason into `notes` as the manual path does."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "classify-llm", transaction.transaction_id, "--provider", scripted_provider],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    updated = restored.get(transaction.transaction_id)
    assert updated is not None
    assert updated.notes == updated.classification_reason
    assert updated.notes == "scripted test decision"


def _register_mixed_home_office_provider() -> str:
    """Register a classifier whose fixed response is a MIXED home-office row."""
    from ..categories import SpendingCategory
    from . import LLMClassificationResponse, register_classifier

    name = "test-home-office-mixed"
    fixed = LLMClassificationResponse(
        classification=BusinessClassification.MIXED,
        confidence=Decimal("0.6"),
        reason="home office rental — partial business use",
        category=SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO,
    )
    classifier = _ScriptedLLMClassifier(response=fixed, decided_by_value=f"llm:{name}")
    register_classifier(name, lambda **_: classifier)
    return name


def test_classify_llm_applies_default_ratio_from_category_profile(tmp_path: Path) -> None:
    """A MIXED classification with a home-office category must auto-apply default_ratio (0.30).

    Closes the two-disjoint-systems gap with #253: manual `classify --as MIXED --pct 0.30`
    already did the right thing; the LLM path was silently dropping the ratio and
    storing `business_pct=None`, which then failed Transaction validation.
    """
    from . import unregister_classifier

    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())
    provider_name = _register_mixed_home_office_provider()
    try:
        result = _RUNNER.invoke(
            root_app,
            ["financial", "txs", "classify-llm", transaction.transaction_id, "--provider", provider_name],
            env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
        )
        assert result.exit_code == 0, result.output
        restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
        updated = restored.get(transaction.transaction_id)
        assert updated is not None
        assert updated.business_classification is BusinessClassification.MIXED
        assert updated.business_pct == Decimal("0.30")
        assert updated.category_id == "arrendamiento_vivienda_afecto"
    finally:
        unregister_classifier(provider_name)


def test_classify_llm_pct_override_beats_profile_default(tmp_path: Path) -> None:
    """`--pct-override 0.5` must win over the profile's 0.30 default_ratio."""
    from . import unregister_classifier

    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())
    provider_name = _register_mixed_home_office_provider()
    try:
        result = _RUNNER.invoke(
            root_app,
            [
                "financial",
                "txs",
                "classify-llm",
                transaction.transaction_id,
                "--provider",
                provider_name,
                "--pct-override",
                "0.5",
            ],
            env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
        )
        assert result.exit_code == 0, result.output
        restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
        updated = restored.get(transaction.transaction_id)
        assert updated is not None
        assert updated.business_pct == Decimal("0.5")
    finally:
        unregister_classifier(provider_name)


def test_classify_llm_category_hint_forces_category(tmp_path: Path) -> None:
    """`--category-hint` must force the persisted category even when the LLM picked a different one."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    from ..categories import SpendingCategory
    from . import LLMClassificationResponse, register_classifier, unregister_classifier

    fixed = LLMClassificationResponse(
        classification=BusinessClassification.BUSINESS,
        confidence=Decimal("0.8"),
        reason="fixture",
        category=SpendingCategory.MATERIAL_OFICINA,
    )
    classifier = _ScriptedLLMClassifier(response=fixed, decided_by_value="llm:test-hint-override")
    register_classifier("test-hint-override", lambda **_: classifier)
    try:
        result = _RUNNER.invoke(
            root_app,
            [
                "financial",
                "txs",
                "classify-llm",
                transaction.transaction_id,
                "--provider",
                "test-hint-override",
                "--category-hint",
                "software_suscripcion",
            ],
            env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
        )
        assert result.exit_code == 0, result.output
        restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
        updated = restored.get(transaction.transaction_id)
        assert updated is not None
        assert updated.category_id == "software_suscripcion"
    finally:
        unregister_classifier("test-hint-override")


def test_classify_llm_reason_prepends_kent_text_to_llm_rationale(
    tmp_path: Path,
    scripted_provider: str,
) -> None:
    """Kent's `--reason` must be preserved alongside the LLM's reason."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify-llm",
            transaction.transaction_id,
            "--provider",
            scripted_provider,
            "--reason",
            "Kent checked the receipt",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    updated = restored.get(transaction.transaction_id)
    assert updated is not None
    assert "Kent checked the receipt" in updated.classification_reason
    assert "scripted test decision" in updated.classification_reason


def test_classify_llm_rejects_unknown_provider(tmp_path: Path) -> None:
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify-llm",
            transaction.transaction_id,
            "--provider",
            "not-a-real-provider",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 2
    assert "unknown LLM provider" in result.output
