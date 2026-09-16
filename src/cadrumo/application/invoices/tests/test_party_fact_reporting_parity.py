"""The reported population and the declaring branches must not drift apart.

The Modelo 349 clave map says which categories are reported against a
counterparty's NIF-IVA. The rule table says which branches consume the State that
identifies that counterparty. They are authored independently and must agree in
one direction: a category cannot enter the reported population without its
minting branch declaring the fact, or the producer silently stops demanding an
identification for an operation that files one.

Crosses a layer boundary on purpose -- the clave map is an application-level
projection and the rule table is domain substrate -- which is what makes the
check worth having rather than a restatement of either side. The domain side is
asked through the projected classification rows, which answer what the
table can mint.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....core.aggregation import IntracomOperationType
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from ....domain.iva.classification import (
    IvaClassificationRule,
    PartyFact,
    resolve_iva_classification_inputs,
)
from ....domain.iva.schema import IvaCategory
from ..source_resolver import iva_category_for_operation_type

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def _classifiable_categories(
    rules: tuple[IvaClassificationRule, ...],
    *,
    consuming: PartyFact | None = None,
) -> frozenset[IvaCategory]:
    """Return the categories the rows mint, optionally only those consuming ``consuming``."""
    return frozenset(
        rule.category
        for rule in rules
        if rule.category is not None and (consuming is None or consuming in rule.consumes)
    )


def _classification_rules() -> tuple[IvaClassificationRule, ...]:
    """Project the current registry-owned IVA classification rows."""
    with bundled_indexed_authority().operation() as operation:
        return resolve_iva_classification_inputs(effective_date=date.today(), operation=operation).rules


class TestEveryReportedCategoryIsMintedByADeclaringBranch:
    """Cross-checks two independent declarations that must not drift apart.

    The Modelo 349 clave map says which categories are reported against a
    counterparty's NIF-IVA; the rule table says which branches consume the State
    that identifies it. If a category enters the first without its minting rule
    entering the second, the producer stops demanding an identification for an
    operation that files one — the silent-blank direction.

    One-directional by design: a branch may legitimately declare the consumption
    for an operation the clave fallback does not yet reach.
    """

    def test_every_clave_reported_category_has_a_declaring_rule(self) -> None:
        rules = _classification_rules()
        declaring = _classifiable_categories(rules, consuming=PartyFact.IVA_IDENTIFICATION_STATE)
        mintable = _classifiable_categories(rules)
        catalogue = resolve_iva_category_catalogue()
        reported = {
            category
            for operation_key in (
                "issued.intra_community_supply",
                "issued.intra_community_service_supply",
                "received.intra_community_acquisition_reverse_charge",
                "received.intra_community_service_acquisition_reverse_charge",
            )
            for category in (
                iva_category_for_operation_type(
                    IntracomOperationType(catalogue.operation_type(operation_key)),
                ),
            )
            if category is not None
        }
        undeclared = sorted(category.value for category in (reported & mintable) - declaring)
        assert undeclared == []

    def test_the_declaring_subset_is_a_real_narrowing(self) -> None:
        """Guards the accessor: an inert filter would make the check pass vacuously.

        If ``consuming=`` returned every category, the parity assertion above
        could never fail whatever the clave map said. The narrowing must be
        strict and non-empty -- only the intra-community rows read the
        identifying State, and they are the rows the clave map reports.
        """
        rules = _classification_rules()
        declaring = _classifiable_categories(rules, consuming=PartyFact.IVA_IDENTIFICATION_STATE)
        mintable = _classifiable_categories(rules)
        assert declaring
        assert declaring < mintable
