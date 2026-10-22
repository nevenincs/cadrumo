"""Synthetic ledger rows that reach every value shape the transaction load path validates.

A load-path change is only proven equal on rows that exercise its branches: absent
and present registry tokens, every cash-accounting treatment, empty and populated
collections, foreign-currency conversion, source paths with directories, and
timestamps on both sides of a Madrid civil-date boundary. The rows are
deterministic and carry no real taxpayer data.

Build the rows inside a generation-pinned authority operation; their registry
tokens are validated against it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path, PurePosixPath, PureWindowsPath

from ....core.concepto_ingreso import ConceptoIngreso
from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.prorrata_exclusions import Art104TresExclusion
from ....core.tipos_actividad import TipoActividad
from ...iva.deduction_facts import IvaDeductionClassificationProvenance
from ...iva.prorrata import InputClassification
from ...iva.schema import (
    IvaCashAccountingPaymentEvidence,
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
)
from ..classification_origin import ClassificationOrigin
from ..enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ..lineage_models import ClassificationHistoryEntry
from ..models import Transaction
from ..raw_transaction import RawProvenance, RawTransaction, SourceFormat

#: Instants either side of a Madrid civil-date boundary. 2025-12-31 23:00 UTC is
#: midnight in Madrid (CET, UTC+1) and also a year boundary; 2026-06-30 22:00 UTC
#: is midnight in Madrid under summer time (CEST, UTC+2).
MADRID_MIDNIGHT_INSTANTS: tuple[datetime, ...] = (
    datetime(2025, 12, 31, 22, 59, 59, 999999, tzinfo=UTC),
    datetime(2025, 12, 31, 23, 0, tzinfo=UTC),
    datetime(2026, 6, 30, 21, 59, 59, 999999, tzinfo=UTC),
    datetime(2026, 6, 30, 22, 0, tzinfo=UTC),
)

_SOURCE_PATHS: tuple[Path, ...] = (
    Path("statement-2026.csv"),
    Path(PurePosixPath("/home/operator/statements/bank-2025.csv")),
    Path(PureWindowsPath(r"C:\Users\operator\Statements\bank.ofx")),
    Path("exports") / "nested" / "movements.xlsx",
)

_SOURCE_FORMATS: tuple[SourceFormat, ...] = (
    SourceFormat.CSV,
    SourceFormat.OFX,
    SourceFormat.XLSX,
    SourceFormat.MANUAL,
)


def _raw(index: int, variant: int, *, booked: date, amount: Decimal, currency: str) -> RawTransaction:
    ingested_at = MADRID_MIDNIGHT_INSTANTS[variant % len(MADRID_MIDNIGHT_INSTANTS)] + timedelta(days=variant // 4)
    return RawTransaction(
        provider_transaction_id=f"varied-row-{index:04d}",
        booked_date=booked,
        value_date=None if variant % 5 == 0 else booked + timedelta(days=variant % 3),
        amount=amount,
        currency=currency,
        counterparty=None if variant % 7 == 0 else f"Contraparte {variant % 11} SL",
        description=f"varied ledger row {index}",
        provenance=RawProvenance(
            source_path=_SOURCE_PATHS[variant % len(_SOURCE_PATHS)],
            source_sha256=f"{variant % 16:x}" * 64,
            source_row_index=index + 1,
            source_format=_SOURCE_FORMATS[variant % len(_SOURCE_FORMATS)],
            ingested_at=ingested_at,
            provider_name="varied seed provider",
        ),
        raw_fields={"Concepto": f"row {index}", "Importe": str(amount)} if variant % 2 else {},
    )


def _deduction_provenance(index: int) -> IvaDeductionClassificationProvenance:
    return IvaDeductionClassificationProvenance(
        authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
        source_locator=f"invoice:varied-{index}",
        evidence_digest="c" * 64,
    )


def _ordinary_row(index: int, variant: int, booked: date) -> dict[str, object]:
    """Domestic rows that rotate the plain enums, the shares and the optional text."""
    classification = (
        BusinessClassification.BUSINESS,
        BusinessClassification.PERSONAL,
        BusinessClassification.MIXED,
        BusinessClassification.NOT_YET_PROCESSED,
    )[variant % 4]
    classified = classification is not BusinessClassification.NOT_YET_PROCESSED
    classified_at = datetime(booked.year, booked.month, booked.day, 23, 30, tzinfo=UTC)
    payload: dict[str, object] = {
        "raw": _raw(index, variant, booked=booked, amount=Decimal("121.00"), currency="EUR"),
        "direction": TransactionDirection.OUTGOING if variant % 3 else TransactionDirection.INCOMING,
        "business_classification": classification,
        "business_pct": Decimal("0.35") if classification is BusinessClassification.MIXED else None,
        "group_label": None if variant % 2 else f"Grupo {variant % 5}",
        "source_jurisdiction": "ES" if variant % 6 else None,
        "notes": "  revisado  " if variant % 4 == 1 else "",
        "lifecycle_state": (TransactionLifecycleState.ACTIVE if variant % 9 else TransactionLifecycleState.ARCHIVED),
        "tipo_actividad": TipoActividad("A03") if variant % 5 == 2 else None,
        "classification_origin": (ClassificationOrigin.PERSON if classified and variant % 2 else None),
        "attachment_ids": (f"attachment-{index}", f"attachment-{index}-b") if variant % 4 == 3 else (),
    }
    if classified:
        payload["classified_at"] = classified_at
        payload["classified_by"] = "manual" if variant % 2 else f"rule:varied-{variant % 3}"
        payload["classification_confidence"] = Decimal("0.80") if variant % 3 == 0 else None
        payload["classification_history"] = (
            (
                ClassificationHistoryEntry(
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    classified_at=classified_at - timedelta(days=1),
                    classified_by="auto",
                ),
            )
            if variant % 2
            else ()
        )
    if variant % 2 == 0:
        payload["taxable_base"] = Decimal("100.00")
        payload["iva_rate"] = Decimal("0.21")
        payload["iva_amount"] = Decimal("21.00")
        payload["iva_category"] = IvaCategory("domestic_general")
    return payload


def _registry_token_row(index: int, variant: int, booked: date) -> dict[str, object]:
    """Rows that carry the registry-resolved tokens projected on the row's own date."""
    direction = TransactionDirection.OUTGOING if variant % 2 else TransactionDirection.INCOMING
    payload: dict[str, object] = {
        "raw": _raw(index, variant, booked=booked, amount=Decimal("100.00"), currency="EUR"),
        "direction": direction,
        "business_classification": BusinessClassification.BUSINESS,
        "group_label": None,
        "source_jurisdiction": "ES",
        "classified_at": datetime(booked.year, booked.month, booked.day, 12, 0, tzinfo=UTC),
        "classified_by": "manual",
        "taxable_base": Decimal("100.00"),
        "iva_amount": Decimal("0.00"),
        "iva_category": IvaCategory("domestic_exempt"),
        "exemption_article": IvaExemptionArticle("art_20_uno_8"),
    }
    if direction is TransactionDirection.OUTGOING:
        payload["input_classification"] = InputClassification.from_registry("common")
        payload["deduction_fact_kind"] = IvaDeductionFactKind.from_registry("domestic_current")
        payload["deduction_provenance"] = _deduction_provenance(index)
        payload["art_104_tres_exclusion"] = Art104TresExclusion("foreign_permanent_establishment")
    else:
        payload["concepto_ingreso"] = ConceptoIngreso.from_registry("subvencion_capital")
        payload["counterparty_country"] = "DE"
        payload["counterparty_identification_state"] = "DE"
    return payload


def _cash_accounting_row(index: int, variant: int, booked: date) -> dict[str, object]:
    """Rows under each non-ordinary cash-accounting treatment, with settlement evidence."""
    supplier = variant % 2 == 1
    operation_date = booked - timedelta(days=10)
    return {
        "raw": _raw(index, variant, booked=booked, amount=Decimal("1210.00"), currency="EUR"),
        "direction": TransactionDirection.OUTGOING if supplier else TransactionDirection.INCOMING,
        "business_classification": BusinessClassification.BUSINESS,
        "group_label": None,
        "source_jurisdiction": "ES",
        "classified_at": datetime(booked.year, booked.month, booked.day, 22, 59, tzinfo=UTC),
        "classified_by": "manual",
        "taxable_base": Decimal("1000.00"),
        "iva_rate": Decimal("0.21"),
        "iva_amount": Decimal("210.00"),
        "iva_category": IvaCategory("domestic_general"),
        "cash_accounting_treatment": IvaCashAccountingTreatment(
            "supplier_regime" if supplier else "taxpayer_regime",
        ),
        "operation_date": operation_date,
        "cash_accounting_payment_evidence": (
            IvaCashAccountingPaymentEvidence(
                payment_date=booked,
                taxable_base=Decimal("600.00"),
                iva_amount=Decimal("126.00"),
            ),
            IvaCashAccountingPaymentEvidence(
                payment_date=booked + timedelta(days=30),
                taxable_base=Decimal("400.00"),
                iva_amount=Decimal("84.00"),
            ),
        ),
    }


def _foreign_currency_row(index: int, variant: int, booked: date) -> dict[str, object]:
    """Foreign-currency rows, with and without a recorded conversion."""
    converted = variant % 2 == 0
    payload: dict[str, object] = {
        "raw": _raw(index, variant, booked=booked, amount=Decimal("250.00"), currency="USD"),
        "direction": TransactionDirection.OUTGOING,
        "business_classification": BusinessClassification.NOT_YET_PROCESSED,
        "group_label": None,
        "source_jurisdiction": "US",
        "counterparty_country": "US",
        "iva_category": IvaCategory("import_third_country"),
        "taxable_base": Decimal("250.00"),
        "iva_amount": Decimal("52.50"),
    }
    if converted:
        payload["fx_rate"] = Decimal("0.9200")
        payload["value_in_eur"] = Decimal("230.00")
        payload["rate_source"] = "ecb_reference"
        payload["rate_date"] = booked.isoformat()
    return payload


_SHAPES = (_ordinary_row, _registry_token_row, _cash_accounting_row, _foreign_currency_row)


def varied_transactions(count: int = 96) -> tuple[Transaction, ...]:
    """Return ``count`` deterministic rows that rotate through every row shape."""
    rows: list[Transaction] = []
    for index in range(count):
        booked = date(2025, 1, 1) + timedelta(days=(index * 7) % 540)
        payload = _SHAPES[index % len(_SHAPES)](index, index // len(_SHAPES), booked)
        # Fixed lifecycle stamps keep the rows identical from one build to the next.
        payload["created_at"] = datetime(2026, 1, 1, 0, 0, tzinfo=UTC) + timedelta(minutes=index)
        payload["modified_at"] = datetime(2026, 1, 1, 0, 0, tzinfo=UTC) + timedelta(minutes=index, seconds=1)
        rows.append(Transaction.model_validate(payload))
    return tuple(rows)
