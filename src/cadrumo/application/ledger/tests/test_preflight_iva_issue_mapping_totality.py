"""Every IVA aggregation issue reason is classified for the preflight layer.

Preflight translates aggregation issue reasons into operator-facing readiness
issues through two bare dict subscripts, which are total by construction: a
reason that arrives unmapped raises rather than resolving to a wrong sentence.
That is the right failure mode and this gate keeps it from ever firing, by
refusing to let a new :class:`IvaLedgerAggregationIssueReason` member ship
without a decision about which side of the boundary it falls on.

The gate is a partition, not a tally. It asserts the mapped set and the
declared not-reaching set are disjoint and together cover the enum exactly, so
it bites on an added member regardless of how many members exist -- a count
would encode this afternoon and detect nothing tomorrow.

Two lanes renamed members of this one enum inside a day, and the first
``AttributeError`` masked the second failure entirely; the class this closes is
that masking, not either instance.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import BindingSourceKind
from ....domain.iva import EUMemberState, IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionDirection,
    TransactionLifecycleState,
)
from ...aggregation import (
    IVA_LEDGER_COUNTERPARTY_GATE_REASONS,
    IVA_LEDGER_MISSING_FACT_REASONS,
    IvaLedgerAggregationIssueReason,
    iva_ledger_missing_fact_reasons,
    validate_iva_ledger_counterparty_category,
)
from .._preflight import (
    _IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT,
    _PREFLIGHT_DETAIL_BY_IVA_ISSUE,
    _PREFLIGHT_REASON_BY_IVA_ISSUE,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _transaction(
    *,
    iva_category: IvaCategory | None,
    counterparty_eu_member_state: EUMemberState | None,
    counterparty_identification_state: EUMemberState | None,
    taxable_base: Decimal | None = Decimal("100.00"),
    iva_rate: Decimal | None = Decimal("0.21"),
    iva_amount: Decimal | None = Decimal("21.00"),
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id="totality-probe",
                booked_date=date(2026, 4, 5),
                value_date=date(2026, 4, 5),
                amount=Decimal("121.00"),
                currency="EUR",
                counterparty="Cliente o proveedor",
                description="ledger row totality-probe",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="c" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": BindingSourceKind.LEDGER_TRANSACTION.value},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "business_pct": None,
            "category_id": None,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "iva_category": iva_category,
            "counterparty_eu_member_state": counterparty_eu_member_state,
            "counterparty_identification_state": counterparty_identification_state,
            "irpf_category": None,
            "usage_ratio_id": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _observed_counterparty_gate_reasons() -> frozenset[IvaLedgerAggregationIssueReason]:
    """Return every reason the real counterparty gate emits across its inputs.

    Exercises the shipped screen rather than restating its branches, so the
    declared set is pinned to behaviour: a branch that starts emitting a
    different reason moves this set and reds the parity assertion below.
    """
    states: tuple[EUMemberState | None, ...] = (None, EUMemberState.ES, EUMemberState.DE)
    observed: set[IvaLedgerAggregationIssueReason] = set()
    for category in (*IvaCategory, None):
        for eu_member_state in states:
            for identification_state in states:
                issue = validate_iva_ledger_counterparty_category(
                    _transaction(
                        iva_category=category,
                        counterparty_eu_member_state=eu_member_state,
                        counterparty_identification_state=identification_state,
                        # A zero-cuota row, so base equals gross and the probe
                        # satisfies the self-assessed gross invariant as well as
                        # the ordinary base+cuota one across every category. The
                        # counterparty gate reads neither field.
                        taxable_base=Decimal("121.00"),
                        iva_rate=Decimal("0"),
                        iva_amount=Decimal("0"),
                    ),
                )
                if issue is not None:
                    observed.add(issue.reason)
    return frozenset(observed)


def _observed_missing_fact_reasons() -> frozenset[IvaLedgerAggregationIssueReason]:
    """Return every reason the real missing-fact screen emits, all facts absent."""
    return frozenset(
        iva_ledger_missing_fact_reasons(
            _transaction(
                iva_category=None,
                counterparty_eu_member_state=None,
                counterparty_identification_state=None,
                taxable_base=None,
                iva_rate=None,
                iva_amount=None,
            ),
        ),
    )


def test_partition_covers_every_aggregation_issue_reason() -> None:
    """Each enum member is either mapped into preflight or declared unreachable."""
    classified = set(_PREFLIGHT_REASON_BY_IVA_ISSUE) | set(_IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT)
    unclassified = set(IvaLedgerAggregationIssueReason) - classified
    assert not unclassified, (
        "IvaLedgerAggregationIssueReason members reach the ledger preflight translation "
        "with no decision recorded: map them in _PREFLIGHT_REASON_BY_IVA_ISSUE if preflight "
        "can receive them, or record why it cannot in "
        f"_IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT -- {sorted(r.value for r in unclassified)}"
    )


def test_partition_sides_are_disjoint() -> None:
    """No member is both mapped and declared unreachable."""
    both = set(_PREFLIGHT_REASON_BY_IVA_ISSUE) & set(_IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT)
    assert not both, sorted(r.value for r in both)


def test_partition_classifies_nothing_outside_the_enum() -> None:
    """Neither side carries a stale member the enum no longer declares."""
    members = set(IvaLedgerAggregationIssueReason)
    assert set(_PREFLIGHT_REASON_BY_IVA_ISSUE) <= members
    assert set(_IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT) <= members


def test_every_not_reaching_entry_states_its_reason() -> None:
    """The unreachable side is a judgement record, not a mute list."""
    for reason, rationale in _IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT.items():
        assert rationale.strip(), reason.value


def test_reason_mapping_covers_both_preflight_facing_screens() -> None:
    """Every reason preflight's two screens emit resolves to a preflight reason."""
    reaching = IVA_LEDGER_MISSING_FACT_REASONS | IVA_LEDGER_COUNTERPARTY_GATE_REASONS
    assert reaching <= set(_PREFLIGHT_REASON_BY_IVA_ISSUE)


def test_detail_mapping_covers_the_missing_fact_screen() -> None:
    """Every missing-fact reason carries a detail sentence.

    The counterparty gate is deliberately absent: it composes its own localised
    detail, which preflight carries through rather than re-authoring.
    """
    assert set(_PREFLIGHT_DETAIL_BY_IVA_ISSUE) >= IVA_LEDGER_MISSING_FACT_REASONS


def test_declared_emission_sets_match_the_shipped_screens() -> None:
    """The declared emission sets equal what the real screens actually emit.

    Without this the two declarations above would be hand-lists asserting
    themselves, and a branch emitting a newly added reason would satisfy the
    coverage gates while still reaching preflight unmapped.
    """
    assert _observed_missing_fact_reasons() == IVA_LEDGER_MISSING_FACT_REASONS
    assert _observed_counterparty_gate_reasons() == IVA_LEDGER_COUNTERPARTY_GATE_REASONS
