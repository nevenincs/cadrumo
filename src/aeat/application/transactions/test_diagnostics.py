"""Unit tests for the typed ledger-import diagnostic surface."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from . import (
    LedgerImportDiagnostic,
    LedgerImportDiagnosticKind,
    LedgerImportDiagnosticSeverity,
    build_ledger_import_diagnostic,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_SOURCE_PATH = Path("imports/n26-2026Q1.csv")


from ...core.i18n import Translatable


def _message() -> Translatable:
    return Translatable("transactions.test_diagnostics.message")


def test_kind_enum_carries_cli_values() -> None:
    assert LedgerImportDiagnosticKind.ORIGINAL_FILE.value == "original-file"
    assert LedgerImportDiagnosticKind.GAP.value == "gap"
    assert LedgerImportDiagnosticKind.DUPLICATE.value == "duplicate"
    assert LedgerImportDiagnosticKind.PARSER.value == "parser"


def test_severity_enum_orders_info_warning_error() -> None:
    assert {item.value for item in LedgerImportDiagnosticSeverity} == {"info", "warning", "error"}


def test_factory_round_trips_canonical_fields() -> None:
    diag = build_ledger_import_diagnostic(
        kind=LedgerImportDiagnosticKind.GAP,
        severity=LedgerImportDiagnosticSeverity.WARNING,
        message=_message(),
        source_path=_SOURCE_PATH,
        source_locator="period=2026-03",
        affected_transaction_ids=("aa" * 32,),
    )
    assert diag.kind is LedgerImportDiagnosticKind.GAP
    assert diag.severity is LedgerImportDiagnosticSeverity.WARNING
    assert diag.message
    assert diag.source_path == _SOURCE_PATH
    assert diag.source_locator == "period=2026-03"
    assert diag.affected_transaction_ids == ("aa" * 32,)


def test_diagnostic_rejects_message_without_authoritative_spanish() -> None:
    with pytest.raises(ValueError):
        build_ledger_import_diagnostic(
            kind=LedgerImportDiagnosticKind.PARSER,
            severity=LedgerImportDiagnosticSeverity.ERROR,
            message=Translatable("translation"),
        )


def test_diagnostic_rejects_blank_source_locator() -> None:
    with pytest.raises(ValueError):
        build_ledger_import_diagnostic(
            kind=LedgerImportDiagnosticKind.PARSER,
            severity=LedgerImportDiagnosticSeverity.ERROR,
            message=_message(),
            source_locator="   ",
        )


def test_diagnostic_is_frozen() -> None:
    diag = build_ledger_import_diagnostic(
        kind=LedgerImportDiagnosticKind.DUPLICATE,
        severity=LedgerImportDiagnosticSeverity.INFO,
        message=_message(),
    )
    with pytest.raises(ValidationError):
        diag.severity = LedgerImportDiagnosticSeverity.ERROR  # type: ignore[misc]


def test_diagnostic_rejects_unknown_kind() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LedgerImportDiagnostic.model_validate(
            {
                "kind": "fictional-kind",
                "severity": "error",
                "message": _message(),
            }
        )
