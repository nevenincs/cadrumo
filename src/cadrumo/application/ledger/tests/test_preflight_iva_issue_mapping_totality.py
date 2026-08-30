"""The preflight module refuses to import with an unclassified IVA issue reason.

Preflight translates aggregation issue reasons into operator-facing readiness
issues through two bare dict subscripts, which are right to keep total by
construction: a reason arriving unmapped raises rather than resolving to a
wrong sentence. What stops that raise from ever being reachable is an
import-time guard in the preflight module itself, the same placement the
discrepancy-kind guard beside it uses, so an unclassified member fails the
import rather than one test run.

That placement is what these tests respect. The checked-in suite imports the
real module, asserts the native partition and operator-action projection are
total, and exercises the shipped screens to prove their declared emission sets.
The import-refusal bite belongs in execution evidence rather than in a test that
mutates a live enum.

Two lanes renamed members of this one enum inside a day, and the first failure
masked the second entirely; the class this closes is that masking.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

# Imported absolutely, not as `from .. import <module>`: the test needs
# the MODULE object, and the package-facade gate reads any `from ..
# import` edge as reaching through the inert namespace.
import cadrumo.application.ledger.preflight as preflight_module

from ....core import BindingSourceKind, OperatorActionAxis
from ....domain.iva import EUMemberState, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...aggregation import (
    IVA_LEDGER_COUNTERPARTY_GATE_REASONS,
    IVA_LEDGER_MISSING_FACT_REASONS,
    IvaLedgerAggregationIssueReason,
    iva_ledger_missing_fact_reasons,
    validate_iva_ledger_counterparty_category,
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
            "counterparty_country": (
                counterparty_eu_member_state.value.upper() if counterparty_eu_member_state is not None else None
            ),
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


def test_the_shipped_module_imports_with_every_member_classified() -> None:
    """The real imported module classifies every native issue exactly once."""
    assert set(preflight_module._PREFLIGHT_REASON_BY_IVA_ISSUE) | set(
        preflight_module._IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT
    ) == set(
        IvaLedgerAggregationIssueReason,
    )


def test_declared_emission_sets_match_the_shipped_screens() -> None:
    """The declared emission sets equal what the real screens actually emit.

    The half no import-time check can carry, because it has to run the screens
    over real transactions. Without it the import guard would be comparing a
    hand-list against itself: a screen that starts emitting a newly added
    reason would satisfy every set comparison at import and still arrive at a
    subscript with no entry.
    """
    assert _observed_missing_fact_reasons() == IVA_LEDGER_MISSING_FACT_REASONS
    assert _observed_counterparty_gate_reasons() == IVA_LEDGER_COUNTERPARTY_GATE_REASONS


def test_every_not_reaching_entry_states_its_reason() -> None:
    """The unreachable side is a judgement record, not a mute list.

    Not expressible as a set comparison, so it stays here: the import guard
    checks which members are classified, never whether the classification says
    anything.
    """
    for reason, rationale in preflight_module._IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT.items():
        assert rationale.strip(), reason.value


def test_every_native_iva_ledger_issue_projects_to_an_operator_action() -> None:
    projection = preflight_module.OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE

    assert set(projection) == set(IvaLedgerAggregationIssueReason)
    assert set(projection.values()) <= set(OperatorActionAxis)
    assert projection[IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE] is OperatorActionAxis.IMPORT_LEDGER_DATA
    assert (
        projection[IvaLedgerAggregationIssueReason.CUOTA_ON_ZERO_RATED_ROW]
        is OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE
    )
    assert (
        projection[IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE]
        is OperatorActionAxis.RESOLVE_IDENTITY
    )
