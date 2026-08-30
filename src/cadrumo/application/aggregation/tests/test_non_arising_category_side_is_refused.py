"""A category on the side it cannot occur on describes no operation, and is refused.

Several IVA categories are directional by law. LIVA art. 25 exempts an entrega
intracomunitaria — something the taxpayer SUPPLIES; there is no received side of
one, because the received counterpart of an intra-community movement is a
different category with its own treatment. The Axis-A component table declares
this per (category, kind) pair as ``DOES_NOT_ARISE`` and names the counterpart in
the row's note. Nothing on the ledger ingest path read that column, so a row
declaring the impossible pairing was accepted and projected.

THE ERROR DIRECTION IS OVER-DEDUCTION, which is why this is worth a refusal
rather than an advisory. A mis-sided intra-community supply routes to
``SOPORTADO`` and claims input IVA on an operation that cannot exist. Every other
gate around this engine watches under-declaration; this one watches the taxpayer
over-claiming, and there is no second surface behind it.

A SIBLING OF THE ZERO-CUOTA SCREEN, NOT AN EXTENSION OF IT. "This operation has
no cuota" and "this operation does not exist" are different questions, and the
table answers them in different columns: a non-arising pair declares every
component ``UNKNOWN`` rather than ``ZERO_BY_LAW``, so
``category_cuota_is_zero_by_law`` correctly returns False here. Folding the two
into one screen would have made the cuota check fire on operations that
legitimately bear no cuota.

NO PAIR COUNT IS ASSERTED. The table declares some number of non-arising pairs
today; asserting it would encode this moment and detect nothing afterwards. The
tests below derive their population from the table at runtime, so a pair added or
retired is covered without an edit — and one non-arising pair
(``recargo_equivalencia`` issued) is refused earlier for an unrelated reason,
which the derivation accommodates rather than special-cases.

Real-behaviour: real :class:`~domain.transactions.Transaction` rows through the
real ``aggregate_iva_ledger_observations`` classifier. No mocks, stubs, skips or
xfail. The population is constructed rows exercising what the classifier ACCEPTS,
not taxpayer data, which this repository does not hold.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import IvaDeductionEvidenceAuthority, IvaDeductionFactKind, Period
from ....domain.calculations.registry.ledger_bindings import IvaLedgerObservation
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.components import IVA_CATEGORY_COMPONENTS, IvaKindApplicability
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.schema import EUMemberState, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .._invoice_kind import invoice_kind_for_direction
from .._iva_ledger import IvaLedgerAggregationIssueReason
from ._iva_authority_support import aggregate_iva_ledger_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_PERIOD = Period.from_year_and_code(2024, "4T")
_ON = date(2024, 11, 6)
_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")


def _transaction(
    row_id: str,
    *,
    direction: TransactionDirection,
    category: IvaCategory,
    eu_member_state: EUMemberState | None = EUMemberState.DE,
    iva_rate: Decimal = Decimal("0.21"),
    iva_amount: Decimal = _CUOTA,
) -> Transaction:
    """One ordinary rated row, differing between tests only in category and side.

    The gross is derived from the substrate rather than fixed, because the
    :class:`Transaction` model reconstitutes it and a zero-cuota row's gross is
    its base alone.
    """
    payload = {
        "raw": RawTransaction(
            provider_transaction_id=row_id,
            booked_date=_ON,
            value_date=_ON,
            amount=_BASE + iva_amount,
            currency="EUR",
            counterparty="Contraparte",
            description=f"operacion {row_id}",
            provenance=RawProvenance(
                source_path=Path("ledger.csv"),
                source_sha256="b" * 64,
                source_row_index=1,
                source_format=SourceFormat.MANUAL,
                ingested_at=datetime(2024, 12, 1, 12, 0, tzinfo=UTC),
                provider_name="manual-ledger",
            ),
            raw_fields={"source_kind": "ledger_transaction"},
        ),
        "direction": direction,
        "group_label": None,
        "source_jurisdiction": "ES",
        "business_classification": BusinessClassification.BUSINESS,
        "business_pct": None,
        "taxable_base": _BASE,
        "iva_rate": iva_rate,
        "iva_amount": iva_amount,
        "iva_category": category,
        "counterparty_country": (eu_member_state.value.upper() if eu_member_state is not None else None),
        # The D5 gate reads the identification and runs BEFORE the side screen
        # these tests exercise. Supplied so an intra-community row reaches the
        # screen under test instead of being refused upstream.
        "counterparty_identification_state": eu_member_state,
        "exemption_article": None,
        "art_104_tres_exclusion": None,
        "prorrata_reference": None,
        "lifecycle_state": TransactionLifecycleState.ACTIVE,
        "fx_rate": None,
        "value_in_eur": None,
        "classified_at": datetime(2024, 12, 2, 13, 0, tzinfo=UTC),
        "classified_by": "manual",
    }
    if direction is TransactionDirection.OUTGOING:
        if category in {
            IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
        }:
            payload["deduction_fact_kind"] = IvaDeductionFactKind.INTRA_EU_CURRENT
            authority = IvaDeductionEvidenceAuthority.INTRA_EU_SELF_ASSESSMENT
        else:
            payload["deduction_fact_kind"] = IvaDeductionFactKind.DOMESTIC_CURRENT
            authority = IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE
        payload["deduction_provenance"] = IvaDeductionClassificationProvenance(
            authority=authority,
            source_locator=f"fixture:{row_id}",
            evidence_digest="f" * 64,
        )
    return Transaction.model_validate(payload)


def _aggregate(transaction: Transaction) -> tuple[Sequence[IvaLedgerObservation], list[str]]:
    catalogue = TransactionCatalogue.model_validate({"transactions": {transaction.transaction_id: transaction}})
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)
    return aggregation.observations, [issue.reason.value for issue in aggregation.issues]


def _direction_for(kind: InvoiceKind) -> TransactionDirection:
    """The ledger direction the classifier reads back as ``kind``.

    Derived by inverting the production mapping rather than hardcoded, so a
    change to which direction means which side cannot leave these fixtures
    quietly testing the opposite of what they claim.
    """
    for direction in (TransactionDirection.INCOMING, TransactionDirection.OUTGOING):
        if invoice_kind_for_direction(direction) is kind:
            return direction
    raise AssertionError(f"no ledger direction maps to {kind!r}")


def _non_arising_pairs() -> list[tuple[IvaCategory, InvoiceKind]]:
    """Every pair the table declares impossible, read at runtime."""
    return [
        (category, kind)
        for (category, kind), row in IVA_CATEGORY_COMPONENTS.items()
        if row.applicability is IvaKindApplicability.DOES_NOT_ARISE
    ]


def test_the_table_declares_pairs_to_guard() -> None:
    """Anti-vacuity. Without it, an emptied table makes every check below agree.

    Deliberately "at least one" rather than a count: the number is today's
    table, and pinning it would turn a legitimate new declaration into a red
    gate while detecting nothing about the guard itself.
    """
    assert _non_arising_pairs(), (
        "the component table declares no non-arising pair, so the guard below has nothing to refuse "
        "and these tests assert nothing"
    )


def test_a_mis_sided_intra_community_supply_is_refused() -> None:
    """The worked case, and the one that was minting deducible IVA.

    An entrega intracomunitaria the taxpayer RECEIVED is not an operation. Left
    unguarded the row projected to ``SOPORTADO`` and claimed 210.00 of input IVA
    the taxpayer never bore.
    """
    observations, reasons = _aggregate(
        _transaction(
            "row-ics-received",
            direction=_direction_for(InvoiceKind.RECEIVED),
            category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        ),
    )
    assert list(observations) == [], "a mis-sided intra-community supply produced a deducible observation"
    assert reasons == [IvaLedgerAggregationIssueReason.NON_ARISING_CATEGORY_FOR_INVOICE_SIDE.value]


def test_the_same_category_on_its_own_side_is_untouched() -> None:
    """Positive control, and the one that matters most.

    The refusal must reject the SIDE, never the category. An entrega
    intracomunitaria the taxpayer supplied is an ordinary exempt operation whose
    base belongs on the return; a guard keyed on the category alone would delete
    every intra-community supply a taxpayer makes.

    Its cuota is zero because the operation carries none — art. 25 exempts it —
    which the sibling zero-cuota screen enforces separately.
    """
    observations, reasons = _aggregate(
        _transaction(
            "row-ics-issued",
            direction=_direction_for(InvoiceKind.ISSUED),
            category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
            iva_rate=Decimal("0"),
            iva_amount=Decimal("0"),
        ),
    )

    assert reasons == []
    assert len(observations) == 1
    assert observations[0].base_amount == _BASE, "the legitimate intra-community supply lost its base imponible"


def test_an_ordinary_two_sided_category_is_untouched_on_both_sides() -> None:
    """Second positive control: most categories arise on both sides.

    ``domestic_general`` is not directional, so neither side may be refused. A
    guard that read the applicability column wrongly — or read it for the wrong
    pair — would empty the return here.
    """
    for kind in (InvoiceKind.ISSUED, InvoiceKind.RECEIVED):
        observations, reasons = _aggregate(
            _transaction(
                f"row-general-{kind.value}",
                direction=_direction_for(kind),
                category=IvaCategory.DOMESTIC_GENERAL,
                eu_member_state=None,
            ),
        )
        assert reasons == [], f"an ordinary domestic row was refused on the {kind.value} side"
        assert len(observations) == 1


def test_every_declared_non_arising_pair_is_refused_at_ingest() -> None:
    """The population is the table's, so a pair added later is covered unedited.

    Some pairs are unconstructible as a ledger row and some are refused earlier
    for an unrelated reason; both are recorded rather than skipped, because a
    derivation that quietly dropped its hard cases would report full coverage
    over whatever remained. What must hold is that NO declared non-arising pair
    reaches an observation.
    """
    refused_here: list[str] = []
    refused_elsewhere: list[str] = []
    unconstructible: list[str] = []
    for category, kind in _non_arising_pairs():
        label = f"{category.value}/{kind.value}"
        try:
            transaction = _transaction(
                f"row-{label}",
                direction=_direction_for(kind),
                category=category,
            )
        except ValueError:
            unconstructible.append(label)
            continue
        observations, reasons = _aggregate(transaction)
        assert list(observations) == [], f"{label} describes no operation yet produced an observation"
        if IvaLedgerAggregationIssueReason.NON_ARISING_CATEGORY_FOR_INVOICE_SIDE.value in reasons:
            refused_here.append(label)
        else:
            refused_elsewhere.append(f"{label} -> {reasons}")

    assert refused_here, (
        "no declared non-arising pair was refused by THIS guard; every one was caught upstream or "
        f"unconstructible, so the guard is unreachable. elsewhere={refused_elsewhere} "
        f"unconstructible={unconstructible}"
    )


def test_the_refusal_names_the_counterpart_the_operator_probably_meant() -> None:
    """An operator told only "this cannot arise" will guess at the fix.

    The table's own note names the category that IS this side's counterpart, so
    the refusal carries it rather than restating it. Asserted on the note's
    content rather than on a literal sentence, so re-wording the table does not
    red this while dropping the note does.
    """
    transaction = _transaction(
        "row-detail",
        direction=_direction_for(InvoiceKind.RECEIVED),
        category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
    )
    catalogue = TransactionCatalogue.model_validate({"transactions": {transaction.transaction_id: transaction}})
    detail = aggregate_iva_ledger_observations(catalogue, period=_PERIOD).issues[0].detail

    note = IVA_CATEGORY_COMPONENTS[(IvaCategory.INTRA_COMMUNITY_SUPPLY, InvoiceKind.RECEIVED)].retencion_note
    assert IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE.value in note, (
        "the table's note no longer names the counterpart, so the refusal below cannot carry it"
    )
    assert IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE.value in detail
    assert IvaCategory.INTRA_COMMUNITY_SUPPLY.value in detail
