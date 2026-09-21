"""Truthful AS1-AS12 evidence state for the activity-asset capability."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class AcceptanceStatus(StrEnum):
    """Permitted terminal states for an acceptance scenario."""

    PROVEN = "proven"
    FAILED = "failed"
    BLOCKED = "blocked"
    UNEXERCISED = "unexercised"


@dataclass(frozen=True, slots=True)
class AssetAcceptanceEvidence:
    """One scenario's current result and the narrow evidence behind it."""

    scenario: str
    status: AcceptanceStatus
    evidence: tuple[str, ...]
    blocker: str | None = None


ASSET_ACCEPTANCE_EVIDENCE: tuple[AssetAcceptanceEvidence, ...] = (
    AssetAcceptanceEvidence(
        "AS1",
        AcceptanceStatus.BLOCKED,
        ("encrypted history restart reconstruction proven", "CLI and TUI create operations registered"),
        "installed frontend-to-encrypted-store restart journey has not been executed",
    ),
    AssetAcceptanceEvidence(
        "AS2",
        AcceptanceStatus.BLOCKED,
        ("ordinary expense, resale stock, and unsafe full-cost regression are pinned",),
        "installed classification-to-asset journey remains unexercised",
    ),
    AssetAcceptanceEvidence(
        "AS3",
        AcceptanceStatus.PROVEN,
        ("published 2025 Modelo 100 authority selection resolves exact regime/class keys",),
    ),
    AssetAcceptanceEvidence(
        "AS4",
        AcceptanceStatus.PROVEN,
        ("schedule tests cover partial periods, year boundaries, caps, and cents rounding",),
    ),
    AssetAcceptanceEvidence(
        "AS5",
        AcceptanceStatus.PROVEN,
        ("immutable corrections, opening history refusal, disposal boundary, and claim supersession are tested",),
    ),
    AssetAcceptanceEvidence(
        "AS6",
        AcceptanceStatus.PROVEN,
        ("construction/land, direct ownership, area allocation, and double-allocation refusal are tested",),
    ),
    AssetAcceptanceEvidence(
        "AS7",
        AcceptanceStatus.PROVEN,
        (
            "published 2025 low-value authority enforces the EUR 300 unit threshold and EUR 25,000 cap",
            "explicit elections, effective-claim replay/correction, and CAS-time concurrent cap checks are tested",
        ),
    ),
    AssetAcceptanceEvidence(
        "AS8",
        AcceptanceStatus.PROVEN,
        ("effective claim IDs feed additive M130 YTD and exclusive M100 material/intangible destinations",),
    ),
    AssetAcceptanceEvidence(
        "AS9",
        AcceptanceStatus.BLOCKED,
        (
            "reciprocal linkage and the independent initial-deduction, regularization, disposal, "
            "and missing-facts rules are tested",
        ),
        "the live source-mesh integration fixture does not satisfy the required taxpayer-profile readiness contract",
    ),
    AssetAcceptanceEvidence(
        "AS10",
        AcceptanceStatus.PROVEN,
        ("missing history, unknown authority class, stale evidence, conflicts, and unsupported ownership fail closed",),
    ),
    AssetAcceptanceEvidence(
        "AS11",
        AcceptanceStatus.BLOCKED,
        ("direct CLI-only/TUI-only creation and both continuation directions pass through shared operations",),
        "independent installed-process journeys over isolated encrypted stores have not been executed",
    ),
    AssetAcceptanceEvidence(
        "AS12",
        AcceptanceStatus.BLOCKED,
        ("claim projections retain pinned authority and source provenance",),
        "asset-derived validated official export journey is owned by the shared exporter and remains unexercised",
    ),
)


def annual_linear_charge_oracle(*, allocated_basis: Decimal, annual_rate: Decimal) -> Decimal:
    """Independent cents oracle for a full 365-day year, without product imports."""
    return (allocated_basis * annual_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


__all__ = [
    "ASSET_ACCEPTANCE_EVIDENCE",
    "AcceptanceStatus",
    "AssetAcceptanceEvidence",
    "annual_linear_charge_oracle",
]
