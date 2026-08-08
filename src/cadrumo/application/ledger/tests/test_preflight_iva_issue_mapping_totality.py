"""The preflight module refuses to import with an unclassified IVA issue reason.

Preflight translates aggregation issue reasons into operator-facing readiness
issues through two bare dict subscripts, which are right to keep total by
construction: a reason arriving unmapped raises rather than resolving to a
wrong sentence. What stops that raise from ever being reachable is an
import-time guard in the preflight module itself, the same placement the
discrepancy-kind guard beside it uses, so an unclassified member fails the
import rather than one test run.

That placement is what these tests have to respect. Asserting the partition's
shape here would be tautological -- the import would have failed before the
assertion ran -- so the structural half is proved the only way it can be: by
re-executing the real module source against a mutated enum and watching it
refuse. What remains a test is the half no import-time check can do, which is
whether the declared emission sets still match what the shipped screens emit.

Two lanes renamed members of this one enum inside a day, and the first failure
masked the second entirely; the class this closes is that masking.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType

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
from .. import _preflight

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROBE_NAME = "MUTATION_PROBE_REASON"
_PROBE_VALUE = "mutation_probe_reason"


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


def _execute_preflight_module_copy(probe_name: str) -> ModuleType:
    """Execute the real preflight source as an independent module object.

    Loads it under a name inside its own package, so its relative imports
    resolve exactly as the canonical module's do, and never touches the
    canonical module in ``sys.modules``. Executing the shipped source is what
    makes this a proof rather than a restatement: the guard under test is the
    one that ships, not a copy of its condition written here.
    """
    source = Path(_preflight.__file__)
    spec = importlib.util.spec_from_file_location(f"{_preflight.__package__}.{probe_name}", source)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        pytest.fail(f"could not build a module spec for {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def unclassified_enum_member() -> Iterator[IvaLedgerAggregationIssueReason]:
    """Add a real member to the live enum, then remove it again.

    Adding rather than deleting, deliberately: deleting a member crashes
    production import through a missing attribute and would red on a signature
    that says nothing about this guard, so it would prove far less than the
    defect actually being simulated here.
    """
    enum = IvaLedgerAggregationIssueReason
    assert _PROBE_NAME not in enum.__members__, "probe member already present; the mutation would be a no-op"

    member = str.__new__(enum, _PROBE_VALUE)
    member._name_ = _PROBE_NAME
    member._value_ = _PROBE_VALUE
    enum._member_map_[_PROBE_NAME] = member
    enum._member_names_.append(_PROBE_NAME)
    enum._value2member_map_[_PROBE_VALUE] = member
    try:
        assert member in set(enum), "mutation ineffective: the probe member is not in set(enum)"
        yield member
    finally:
        enum._member_map_.pop(_PROBE_NAME, None)
        enum._value2member_map_.pop(_PROBE_VALUE, None)
        if _PROBE_NAME in enum._member_names_:
            enum._member_names_.remove(_PROBE_NAME)


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
    """The positive control: the guard passes on the real, unmutated enum.

    Without this the refusal below would be consistent with a module that
    cannot load at all, and a guard that always fires is not a guard.
    """
    module = _execute_preflight_module_copy("_preflight_control_probe")

    assert set(module._PREFLIGHT_REASON_BY_IVA_ISSUE) | set(module._IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT) == set(
        IvaLedgerAggregationIssueReason,
    )


def test_an_unclassified_member_fails_the_module_import(
    unclassified_enum_member: IvaLedgerAggregationIssueReason,
) -> None:
    """A member on neither side of the partition refuses at import, not at call."""
    with pytest.raises(RuntimeError) as excinfo:
        _execute_preflight_module_copy("_preflight_mutation_probe")

    message = str(excinfo.value)
    assert unclassified_enum_member.value in message
    assert "_IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT" in message


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
    for reason, rationale in _preflight._IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT.items():
        assert rationale.strip(), reason.value
