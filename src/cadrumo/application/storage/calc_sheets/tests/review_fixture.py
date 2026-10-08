"""Synthetic saved review facts with independently stated amounts and attribution."""

from decimal import Decimal
from uuid import UUID

from .....domain.calculations.registry.schema_references import RegistrySnapshotRef
from .....domain.modelos.ledger_filing_snapshot import LedgerEvidenceRow
from ....export.review_snapshot import (
    CalculationReviewSelection,
    EvidenceDisposition,
    EvidenceInventoryItem,
    LedgerReviewSelection,
    ReviewAmount,
    ReviewContribution,
    ReviewFinding,
    ReviewSnapshot,
    ReviewSnapshotContent,
    ReviewSourceKind,
    ReviewStatus,
    seal_review_snapshot,
)


def review_snapshot(*, ledger_only: bool = False, amount: str = "25.20") -> ReviewSnapshot:
    """A captured 120 EUR purchase with 25.20 IVA; no current ledger is consulted."""
    selection = (
        LedgerReviewSelection(profile_id=UUID(int=1), ledger_snapshot_id="a" * 64)
        if ledger_only
        else CalculationReviewSelection(
            profile_id=UUID(int=1),
            work_unit_id="b" * 64,
            calculation_revision_id="c" * 64,
            modelo="303",
            filing_year=2026,
            period="1T",
            registry_snapshot_ref=RegistrySnapshotRef(modelo="303", revision_id="2026", modelo_year=2026, period="1T"),
            authority_generation="d" * 64,
            registry_digest="e" * 64,
        )
    )
    return seal_review_snapshot(
        ReviewSnapshotContent(
            selection=selection,
            status=ReviewStatus.PROVISIONAL,
            amounts=()
            if ledger_only
            else (
                ReviewAmount(
                    amount_id="iva",
                    casilla_id="29",
                    value=Decimal(amount),
                    unit="money",
                    currency="EUR",
                    rounding="0.01 HALF_UP",
                    contribution_ids=("purchase",),
                    formula_reference="recorded-formula",
                ),
            ),
            ledger_rows=(
                LedgerEvidenceRow(
                    transaction_id="1" * 64,
                    fingerprint="f" * 64,
                    booked_date="2026-01-12",
                    amount=Decimal("145.20"),
                    currency="EUR",
                    direction="outflow",
                    business_classification="business",
                    taxable_base=Decimal("120.00"),
                    iva_amount=Decimal("25.20"),
                    lifecycle_state="confirmed",
                    counterparty='=IMPORTXML("https://example.invalid", "x")',
                    attachment_ids=("invoice-1",),
                    legal_refs=("law",),
                    source_refs=("official-source",),
                ),
            ),
            contributions=(
                ReviewContribution(
                    contribution_id="purchase",
                    kind=ReviewSourceKind.LEDGER_ROW,
                    source_id="1" * 64,
                    source_revision="captured-1",
                    evidence_ids=("invoice-1",),
                    detail="+external literal",
                ),
            ),
            evidence=(
                EvidenceInventoryItem(
                    evidence_id="invoice-1",
                    source_revision="captured-1",
                    disposition=EvidenceDisposition.MISSING,
                    reason="Historical payload unavailable",
                ),
            ),
            findings=(
                ReviewFinding(
                    code="missing_payload", detail="Historical payload unavailable", related_ids=("invoice-1",)
                ),
            ),
        )
    )


def review_label(key: str) -> str:
    """Readable fixture labels, independent of production localization enrollment."""
    notices = {
        "baseline_notice": "Saved local baseline. This review is not a filing or verification.",
        "index_only_notice": "Evidence index only. Original payloads are supplied separately; missing items remain missing.",
        "external_notes_notice": "Edit your findings and scenarios here. Cadrumo never imports these edits.",
        "ledger_notice": "Captured ledger rows. Amounts are magnitudes; direction is recorded separately.",
        "ledger_scope_notice": "Explicit ledger snapshot. No calculation contribution is implied.",
        "attribution_notice": "Only explicit captured attribution connects sources to results.",
        "unattributed": "No captured calculation attribution",
        "not_captured": "Not captured",
        "no_captured_rows": "This snapshot contains no rows for this section.",
        "not_ledger_source": "Source is not a ledger row",
        "no_inventory_reference": "No captured inventory reference",
        "exact_decimal_notice": "Exact decimal text preserves the saved value and scale beside the numeric display.",
        "not_captured_notice": "Not captured means the snapshot has no value; it does not mean zero or not applicable.",
    }
    return notices.get(key, key.replace("_", " ").capitalize())
