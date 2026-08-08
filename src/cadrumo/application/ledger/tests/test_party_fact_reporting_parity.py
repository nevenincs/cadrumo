"""The reported population and the declaring branches must not drift apart.

The Modelo 349 clave map says which categories are reported against a
counterparty's NIF-IVA. The rule table says which branches consume the State that
identifies that counterparty. They are authored independently and must agree in
one direction: a category cannot enter the reported population without its
minting branch declaring the fact, or the producer silently stops demanding an
identification for an operation that files one.

Crosses a layer boundary on purpose -- the clave map is an application-level
projection and the rule table is domain substrate -- which is what makes the
check worth having rather than a restatement of either side.
"""

from __future__ import annotations

import pytest

from ....domain.iva import PartyFact

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


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
        from ....application.invoices._source_resolver import _CLAVE_BY_KIND_AND_CATEGORY
        from ....domain.iva._classification import _CLASSIFICATION_RULES

        declaring = {
            rule.category for rule in _CLASSIFICATION_RULES if PartyFact.VAT_IDENTIFICATION_STATE in rule.consumes
        }
        reported = {category for _, category in _CLAVE_BY_KIND_AND_CATEGORY}
        mintable = {rule.category for rule in _CLASSIFICATION_RULES}
        undeclared = sorted(category.value for category in (reported & mintable) - declaring)
        assert undeclared == []
