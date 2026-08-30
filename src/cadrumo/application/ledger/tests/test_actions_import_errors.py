"""Manual ledger import parse and source path refusal tests."""

from __future__ import annotations

import logging

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    LedgerSourceImportCommand,
    Path,
    SecureObjectRepository,
    TransactionDirection,
    TransactionValidationError,
    _repositories,
    import_ledger_source,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_import_rejects_zero_amount_row_at_parse_boundary(tmp_path: Path) -> None:
    """A zero-amount source row is refused at the parse boundary, like the manual path."""
    statement = tmp_path / "bank-zero.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,0.00,EUR,n26-zero\n",
        encoding="utf-8",
    )
    with pytest.raises(TransactionValidationError) as exc_info:
        import_ledger_source(
            LedgerSourceImportCommand(path=statement, provider="csv", dry_run=True),
        )
    assert exc_info.value.translated_message == "errors.transaction.ledger_import_failed"
    assert "zero amount" in str((exc_info.value.context or {}).get("reason", ""))


def test_import_ledger_source_missing_file_raises_localised_error(tmp_path: Path) -> None:
    """A missing source file raises a tr()-localised error, not naked English."""
    from ....core.errors.error_codes import resolve_error_message

    missing = tmp_path / "no-such-statement.csv"
    with pytest.raises(TransactionValidationError) as excinfo:
        import_ledger_source(
            LedgerSourceImportCommand(path=missing, provider="csv", dry_run=True, verify=False, source=missing),
        )

    error = excinfo.value
    assert error.translated_message == "errors.financial.source_file_not_found"
    assert error.context == {"path": str(missing)}
    rendered = resolve_error_message(error)
    assert "El archivo de origen no existe" in rendered
    assert str(missing) in rendered


def test_import_ledger_source_auto_missing_file_is_clean_refusal_without_probe_noise(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``--provider auto`` on a missing file refuses cleanly without probe noise."""
    from ....core.errors.error_codes import resolve_error_message

    missing = tmp_path / "no-such-statement.csv"
    with (
        caplog.at_level("ERROR", logger="cadrumo.adapters.inbound.financial.providers"),
        pytest.raises(TransactionValidationError) as excinfo,
    ):
        import_ledger_source(
            LedgerSourceImportCommand(path=missing, provider="auto", dry_run=True),
        )

    error = excinfo.value
    assert error.translated_message == "errors.financial.source_file_not_found"
    assert error.context == {"path": str(missing)}
    rendered = resolve_error_message(error)
    assert str(missing) in rendered
    assert "auto-detection" not in rendered
    probe_errors = [
        record
        for record in caplog.records
        if record.levelno >= logging.ERROR and record.name.startswith("cadrumo.adapters.inbound.financial.providers")
    ]
    assert probe_errors == []


def test_import_ledger_source_auto_unsupported_file_raises_localised_import_error(tmp_path: Path) -> None:
    """Auto-detection failures use the translated import refusal contract."""
    from ....core.errors.error_codes import resolve_error_message

    unsupported = tmp_path / "statement.txt"
    unsupported.write_text("not a bank statement\n", encoding="utf-8")

    with pytest.raises(TransactionValidationError) as excinfo:
        import_ledger_source(
            LedgerSourceImportCommand(path=unsupported, provider="auto", dry_run=True),
        )

    error = excinfo.value
    assert error.translated_message == "errors.transaction.ledger_import_failed"
    assert error.context is not None
    assert error.context["path"] == str(unsupported)
    rendered = resolve_error_message(error)
    assert rendered
    assert str(unsupported) in rendered
    assert "auto-detection" not in rendered


def test_import_dedup_keeps_opposite_direction_same_amount_narrative_date(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Opposite cashflow directions are distinct imported movements."""
    transaction_repository, event_repository = _repositories(secure_objects)
    incoming = tmp_path / "incoming.csv"
    incoming.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID,direction\n"
        "2026-04-17,Client SL,Mirror movement,48.40,EUR,n26-in,INCOMING\n",
        encoding="utf-8",
    )
    outgoing = tmp_path / "outgoing.csv"
    outgoing.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID,direction\n"
        "2026-04-17,Client SL,Mirror movement,48.40,EUR,n26-out,OUTGOING\n",
        encoding="utf-8",
    )

    first = import_ledger_source(
        LedgerSourceImportCommand(bucket_id=_BUCKET_ID, path=incoming, provider="csv"),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    second = import_ledger_source(
        LedgerSourceImportCommand(bucket_id=_BUCKET_ID, path=outgoing, provider="csv"),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )

    assert first.imported == 1
    assert first.skipped == 0
    assert second.imported == 1
    assert second.skipped == 0
    assert {transaction.direction for transaction in transaction_repository.load().values()} == {
        TransactionDirection.INCOMING,
        TransactionDirection.OUTGOING,
    }


def test_import_dedup_keeps_same_numeric_amount_in_different_currencies(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Currency is part of imported movement identity."""
    transaction_repository, event_repository = _repositories(secure_objects)
    eur = tmp_path / "eur.csv"
    eur.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID,direction\n"
        "2026-04-17,Client SL,Subscription,100.00,EUR,n26-eur,OUTGOING\n",
        encoding="utf-8",
    )
    usd = tmp_path / "usd.csv"
    usd.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID,direction\n"
        "2026-04-17,Client SL,Subscription,100.00,USD,n26-usd,OUTGOING\n",
        encoding="utf-8",
    )

    first = import_ledger_source(
        LedgerSourceImportCommand(bucket_id=_BUCKET_ID, path=eur, provider="csv"),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    second = import_ledger_source(
        LedgerSourceImportCommand(bucket_id=_BUCKET_ID, path=usd, provider="csv"),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )

    assert first.imported == 1
    assert first.skipped == 0
    assert second.imported == 1
    assert second.skipped == 0
    assert {transaction.raw.currency for transaction in transaction_repository.load().values()} == {"EUR", "USD"}


def test_import_ledger_source_verify_missing_original_file_raises_localised_error(tmp_path: Path) -> None:
    """A missing verification source is reported through the financial-source key."""
    from ....core.errors.error_codes import resolve_error_message

    statement = tmp_path / "bank.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    missing_original = tmp_path / "missing-original.pdf"

    with pytest.raises(TransactionValidationError) as excinfo:
        import_ledger_source(
            LedgerSourceImportCommand(
                path=statement,
                provider="csv",
                dry_run=True,
                verify=True,
                source=missing_original,
            ),
        )

    error = excinfo.value
    assert error.translated_message == "errors.financial.source_file_not_found"
    assert error.context == {"path": str(missing_original)}
    rendered = resolve_error_message(error)
    assert rendered
    assert str(missing_original) in rendered
