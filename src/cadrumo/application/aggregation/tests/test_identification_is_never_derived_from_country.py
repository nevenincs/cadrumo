"""Nothing derives an IVA identification from a country of establishment.

The two facts answer different questions -- where a party IS, and which Member
State IVA-identifies it -- and they diverge in real trade. Ley 37/1992 art. 25
exempts on the second. Substituting the first for it lands in money in both
directions, so this module keeps the substitution out rather than trusting each
consumer to remember which fact it holds.

Two teeth, deliberately different in kind:

- A BEHAVIOURAL sweep, which is the load-bearing one: it drives the real
  aggregation over rows whose two facts disagree and asserts the outcome tracks
  identification. A source-level check cannot see a derivation written through
  a helper, and this one does not care how the code is spelled.
- A STRUCTURAL sweep over the aggregation modules, which catches a
  freshly-written ``EUMemberState(invoice.counterparty_country.lower())`` before
  it has a consumer to misbehave through.
"""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.period import Period
from ....domain.iva.schema import EUMemberState, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .iva_authority_support import aggregate_iva_ledger_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERIOD = Period.from_year_and_code(2026, "2T")

#: Aggregation modules the sweep reads. The gate is scoped to the layer that
#: owns the art. 25 decision; the domain models it reads from are covered by
#: the behavioural half, which exercises them for real.
_SWEPT_MODULES = ("_iva_ledger.py", "_modelo_bindings.py", "_oss_ioss.py", "_counterpart.py")

#: The country-shaped sources an identification must never be built from.
_COUNTRY_SOURCES = frozenset(
    {
        "counterparty_country",
        "counterparty_eu_member_state",
        "issuer_country",
        "country_code",
    },
)


def _raw(provider_id: str) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 4, 15),
        value_date=date(2026, 4, 15),
        amount=Decimal("4000.00"),
        currency="EUR",
        counterparty="Acquirer",
        description=f"sweep {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 16, 9, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _row(provider_id: str, *, established_in: EUMemberState | None, identified_in: EUMemberState | None) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("4000.00"),
            "iva_rate": Decimal("0"),
            "iva_amount": Decimal("0"),
            "iva_category": IvaCategory.INTRA_COMMUNITY_SUPPLY,
            "counterparty_country": (established_in.value.upper() if established_in is not None else None),
            "counterparty_identification_state": identified_in,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
        },
    )


def _accepted(transaction: Transaction) -> bool:
    aggregation = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions([transaction]),
        period=_PERIOD,
    )
    return aggregation.issues == () and len(aggregation.observations) == 1


@pytest.mark.parametrize(
    ("established_in", "identified_in", "accepted"),
    [
        # Identification decides, across every establishment it can pair with.
        (EUMemberState.ES, EUMemberState.DE, True),
        (EUMemberState.FR, EUMemberState.DE, True),
        (None, EUMemberState.DE, True),
        (EUMemberState.DE, EUMemberState.ES, False),
        (EUMemberState.ES, EUMemberState.ES, False),
        (None, EUMemberState.ES, False),
        # Absent identification is absent, whatever the establishment says.
        (EUMemberState.DE, None, False),
        (EUMemberState.ES, None, False),
        (None, None, False),
    ],
)
def test_the_outcome_tracks_identification_and_ignores_establishment(
    established_in: EUMemberState | None,
    identified_in: EUMemberState | None,
    accepted: bool,
) -> None:
    """The establishment axis is varied freely and never moves the result.

    Read down the table: for a fixed identification the verdict is constant
    across all three establishments, and it changes only when the
    identification does. That is what "nothing derives one from the other"
    means operationally.
    """
    row = _row(f"sweep-{established_in}-{identified_in}", established_in=established_in, identified_in=identified_in)
    assert _accepted(row) is accepted


def test_no_aggregation_module_builds_an_identification_from_a_country() -> None:
    """No swept module constructs an ``EUMemberState`` out of a country-shaped name.

    Catches the specific regression shape: reaching for the address field and
    widening it into the registration type. Assignment TO an
    ``*identification_state*`` target from a country-shaped attribute is caught
    the same way.
    """
    package_root = Path(__file__).resolve().parent.parent
    offences: list[str] = []

    for module_name in _SWEPT_MODULES:
        module_path = package_root / module_name
        assert module_path.is_file(), f"swept module {module_name} has moved; fix the sweep, do not drop it"
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))

        for node in ast.walk(tree):
            # EUMemberState(<something country-shaped>)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "EUMemberState"
                and _mentions_a_country_source(node)
            ):
                offences.append(f"{module_name}:{node.lineno} builds an EUMemberState from a country-shaped source")

            # <...>identification_state<...> = <something country-shaped>
            if (
                isinstance(node, ast.Assign)
                and _targets_identification(node.targets)
                and _mentions_a_country_source(node.value)
            ):
                offences.append(f"{module_name}:{node.lineno} assigns an identification from a country-shaped source")

    assert not offences, "identification must never be derived from a country:\n" + "\n".join(offences)


def _mentions_a_country_source(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr in _COUNTRY_SOURCES:
            return True
        if isinstance(child, ast.Name) and child.id in _COUNTRY_SOURCES:
            return True
        if isinstance(child, ast.Constant) and isinstance(child.value, str) and child.value in _COUNTRY_SOURCES:
            return True
    return False


def _targets_identification(targets: list[ast.expr]) -> bool:
    for target in targets:
        for child in ast.walk(target):
            if isinstance(child, ast.Attribute) and "identification_state" in child.attr:
                return True
            if isinstance(child, ast.Name) and "identification_state" in child.id:
                return True
            if (
                isinstance(child, ast.Constant)
                and isinstance(child.value, str)
                and "identification_state" in child.value
            ):
                return True
    return False
