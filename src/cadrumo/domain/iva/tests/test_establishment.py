"""A printed country resolves to a scope, or to nothing, and never to Spain.

The failure this gates runs one way. An establishment resolved too eagerly turns
an intra-community or reverse-charge operation into a domestic one, and that
value is plausible at every boundary it later crosses: the amounts still close,
the filing still validates, and the only thing it contradicts is the
counterparty's own declaration, which the pipeline never sees again. An absent
establishment, by contrast, is visible and blocks nothing that was not already
undetermined.

So the assertions here are asymmetric on purpose. Correct resolutions are checked
once each; the refusal to produce a Spanish scope is checked from several
directions, because that is the single value this module must never invent.

Model-free and network-free: a pure function over strings.

See Also:
    :func:`~domain.iva.territorial_scope_for_country`
        The resolver under gate.
"""

from __future__ import annotations

import pytest

from ..classification import IvaTerritorialScope
from ..establishment import SPAIN_COUNTRY_CODE, territorial_scope_for_country
from ..schema import EUMemberState

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

SPANISH_SCOPES = frozenset(
    {
        IvaTerritorialScope.ES_MAINLAND,
        IvaTerritorialScope.ES_CANARIAS,
        IvaTerritorialScope.ES_CEUTA_MELILLA,
    },
)


class TestTheResolverNeverInventsASpanishScope:
    """The one value this module must not produce, checked from every angle."""

    @pytest.mark.parametrize("printed", ["ES", "es", " es ", "Es"])
    def test_a_spanish_code_resolves_to_nothing_however_it_is_printed(self, printed: str) -> None:
        """The State is named; the IVA territory inside it is not.

        Spain holds three territories treated differently by law -- the peninsula
        and Balearics inside the TAI, Canarias under IGIC, Ceuta and Melilla
        under IPSI. A country code cannot tell them apart, so resolving it to the
        mainland would place every Canarian and Ceutan party inside a territory
        their operations are not subject to.
        """
        assert territorial_scope_for_country(printed) is None

    @pytest.mark.parametrize("printed", [None, "", "   ", "E", "DEU", "D1", "12", "??"])
    def test_absent_or_malformed_evidence_resolves_to_nothing(self, printed: str | None) -> None:
        """Unreadable evidence is a normal outcome of reading, not an error."""
        assert territorial_scope_for_country(printed) is None

    def test_no_input_whatsoever_produces_a_spanish_scope(self) -> None:
        """The property stated over the whole reachable input space, not a sample.

        Every Member State code, a spread of third countries, and every malformed
        shape the reader can hand over. A single assertion over the union is what
        makes this a property rather than a list of cases that happen to pass.
        """
        probes: list[str | None] = [None, "", "  ", "E", "DEU", "D1", "??", "ZZ", "US", "CH", "JP", "GB"]
        probes += [member.value for member in EUMemberState]
        probes += [member.value.upper() for member in EUMemberState]

        resolved = {territorial_scope_for_country(probe) for probe in probes}

        assert resolved & SPANISH_SCOPES == set()

    def test_the_spanish_code_is_the_one_the_member_catalogue_carries(self) -> None:
        """Fixture anchor: the refusal is keyed to a real catalogue member.

        Without this the refusal could be pinned to a code the catalogue does not
        contain, and the test would keep passing while the real Spanish code
        resolved straight through the EU branch.
        """
        assert SPAIN_COUNTRY_CODE in {member.value.upper() for member in EUMemberState}


class TestTheResolverAnswersWhereTheEvidenceIsDecisive:
    """Refusing everything would satisfy the class above; these stop that."""

    @pytest.mark.parametrize("printed", ["DE", "de", " fr ", "IT", "XI"])
    def test_another_member_state_resolves_to_the_eu_scope(self, printed: str) -> None:
        assert territorial_scope_for_country(printed) is IvaTerritorialScope.EU_MEMBER

    @pytest.mark.parametrize("printed", ["US", "CH", "JP", "GB"])
    def test_a_well_formed_non_member_resolves_to_the_third_country_scope(self, printed: str) -> None:
        """Not domestic, and not silently absent either: outside is a real answer."""
        assert territorial_scope_for_country(printed) is IvaTerritorialScope.THIRD_COUNTRY

    def test_every_member_state_except_spain_resolves_to_the_eu_scope(self) -> None:
        """Derived from the catalogue, so a State joining or leaving is covered."""
        for member in EUMemberState:
            code = member.value.upper()
            expected = None if code == SPAIN_COUNTRY_CODE else IvaTerritorialScope.EU_MEMBER

            assert territorial_scope_for_country(code) is expected, code

    def test_the_eu_branch_is_not_reachable_by_accident(self) -> None:
        """A country outside the Member State catalogue must not fall into the member scope.

        The discriminating control for the class above: without it, a resolver
        returning EU_MEMBER for everything it recognised would pass every member
        assertion here.

        The probes are CATALOGUED non-members, and that is the substantive half.
        This control was once written over ``ZZ`` and ``QQ``, which worked only
        while the resolver answered on SHAPE -- so the control and the defect
        shared a premise, and a code naming no country was standing in for a
        country outside the EU. A real third country is what the branch has to
        be discriminated against.
        """
        assert territorial_scope_for_country("NO") is IvaTerritorialScope.THIRD_COUNTRY
        assert territorial_scope_for_country("BR") is IvaTerritorialScope.THIRD_COUNTRY
