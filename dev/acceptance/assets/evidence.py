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
        AcceptanceStatus.PROVEN,
        (
            "installed TUI creates and corrects encrypted asset history through public operations",
            "a fresh installed TUI process reconstructs the two-revision history and canonical revision identity",
        ),
    ),
    AssetAcceptanceEvidence(
        "AS2",
        AcceptanceStatus.PROVEN,
        (
            "ordinary expense, resale stock, and unsafe full-cost regression are pinned",
            "installed filing calculation adds the single EUR 300 claim to total expenses and the material destination "
            "without consuming acquisition cost twice",
        ),
    ),
    AssetAcceptanceEvidence(
        "AS3",
        AcceptanceStatus.PROVEN,
        (
            "the revision election resolves through published 2025 Modelo 100 authority: method admission by "
            "modality, table-class groups, coefficient bounds and weighting",
        ),
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
        AcceptanceStatus.PROVEN,
        (
            "reciprocal linkage and the independent initial-deduction, regularization, disposal, "
            "and missing-facts rules are tested",
        ),
    ),
    AssetAcceptanceEvidence(
        "AS10",
        AcceptanceStatus.PROVEN,
        ("missing history, unknown authority class, stale evidence, conflicts, and unsupported ownership fail closed",),
    ),
    AssetAcceptanceEvidence(
        "AS11",
        AcceptanceStatus.PROVEN,
        (
            "installed TUI-to-CLI continuation preserves two revisions and the EUR 540 constant-percentage "
            "non-consuming handoff",
            "installed CLI-to-TUI continuation exposes the asset and canonical revision identity in a fresh process",
        ),
    ),
    AssetAcceptanceEvidence(
        "AS12",
        AcceptanceStatus.PROVEN,
        (
            "claim projections retain pinned authority and source provenance",
            "installed M130/M100 calculation carries one EUR 300 constant-percentage claim and the generated "
            "Modelo 100 XML passes "
            "the pinned official 2025 XSD",
        ),
    ),
)


def annual_linear_charge_oracle(*, allocated_basis: Decimal, annual_rate: Decimal) -> Decimal:
    """Independent cents oracle for a full 365-day year, without product imports."""
    return (allocated_basis * annual_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def first_year_constant_percentage_oracle(
    *,
    allocated_basis: Decimal,
    linear_coefficient: Decimal,
    weighting: Decimal,
) -> Decimal:
    """Independent cents oracle for a full first year under RIS art. 5.1."""
    return (allocated_basis * linear_coefficient * weighting).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


__all__ = [
    "ASSET_ACCEPTANCE_EVIDENCE",
    "AcceptanceStatus",
    "AssetAcceptanceEvidence",
    "annual_linear_charge_oracle",
    "first_year_constant_percentage_oracle",
]
