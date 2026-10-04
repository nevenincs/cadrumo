"""Shared reconciliation findings for operator contract and renderer tests."""

from decimal import Decimal

from ...core.casilla_id import validated_casilla_id
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)


def reconciliation_findings() -> tuple[ModeloVerificationFinding, ...]:
    """Represent working drift, cross-model drift, and incomplete cross-model coverage."""
    common = {"period_code": "1T", "filing_year": 2025}
    specifications = (
        (
            "pulled_filing_casilla_mismatch",
            {
                **common,
                "casilla_number": "10",
                "computed_value": Decimal("6000.25"),
                "filed_value": Decimal("7250.50"),
                "mismatch_kind": "value_mismatch",
            },
        ),
        (
            "m303_m349_intracom_reconciliation_mismatch",
            {**common, "m303_total": Decimal("10000.25"), "m349_total": Decimal("8000.50"), "gap": Decimal("1999.75")},
        ),
        (
            "cross_model_reconciliation_incomplete",
            {**common, "modelo": "303", "sibling_modelo": "349", "own_missing_count": 2, "sibling_missing_count": 1},
        ),
    )
    return tuple(
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.ADVISORY
            if index == 2
            else ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=validated_casilla_id("10", surface="test") if index == 0 else None,
            message_locale_key=f"application.modelo.findings.{key}",
            message_facts=facts,
            legal_refs=("ley-37-1992:art-99",),
            source_refs=("test-reconciliation-evidence",),
        )
        for index, (key, facts) in enumerate(specifications)
    )
