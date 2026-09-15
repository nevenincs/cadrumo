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

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo.domain.calculations.registry.eu_member_state_catalogue import resolve_eu_member_state_catalogue

from ..classification import IvaTerritorialScope
from ..establishment import SPAIN_COUNTRY_CODE, territorial_scope_for_country

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

SPANISH_SCOPES = frozenset(
    {
        IvaTerritorialScope.from_registry("es_mainland"),
        IvaTerritorialScope.from_registry("es_canarias"),
        IvaTerritorialScope.from_registry("es_ceuta_melilla"),
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
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            assert territorial_scope_for_country(printed, operation=_authority_operation_for_test) is None

    @pytest.mark.parametrize("printed", [None, "", "   ", "E", "DEU", "D1", "12", "??"])
    def test_absent_or_malformed_evidence_resolves_to_nothing(self, printed: str | None) -> None:
        """Unreadable evidence is a normal outcome of reading, not an error."""
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            assert territorial_scope_for_country(printed, operation=_authority_operation_for_test) is None

    def test_no_input_whatsoever_produces_a_spanish_scope(self) -> None:
        """The property stated over the whole reachable input space, not a sample.

        Every Member State code, a spread of third countries, and every malformed
        shape the reader can hand over. A single assertion over the union is what
        makes this a property rather than a list of cases that happen to pass.
        """
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            probes: list[str | None] = [None, "", "  ", "E", "DEU", "D1", "??", "ZZ", "US", "CH", "JP", "GB"]
            member_states = resolve_eu_member_state_catalogue(authority=_authority_operation_for_test).all_states
            probes += [member.value for member in member_states]
            probes += [member.value.upper() for member in member_states]

            resolved = {
                territorial_scope_for_country(probe, operation=_authority_operation_for_test) for probe in probes
            }

            assert resolved & SPANISH_SCOPES == set()

    def test_the_spanish_code_is_the_one_the_member_catalogue_carries(self) -> None:
        """Fixture anchor: the refusal is keyed to a real catalogue member.

        Without this the refusal could be pinned to a code the catalogue does not
        contain, and the test would keep passing while the real Spanish code
        resolved straight through the EU branch.
        """
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            member_states = resolve_eu_member_state_catalogue(authority=_authority_operation_for_test).all_states
            assert SPAIN_COUNTRY_CODE in {member.value.upper() for member in member_states}


class TestTheResolverAnswersWhereTheEvidenceIsDecisive:
    """Refusing everything would satisfy the class above; these stop that."""

    @pytest.mark.parametrize("printed", ["DE", "de", " fr ", "IT", "XI"])
    def test_another_member_state_resolves_to_the_eu_scope(self, printed: str) -> None:
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            assert territorial_scope_for_country(
                printed, operation=_authority_operation_for_test
            ) is IvaTerritorialScope.from_registry("eu_member")

    @pytest.mark.parametrize("printed", ["US", "CH", "JP", "GB"])
    def test_a_well_formed_non_member_resolves_to_the_third_country_scope(self, printed: str) -> None:
        """Not domestic, and not silently absent either: outside is a real answer."""
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            assert territorial_scope_for_country(
                printed, operation=_authority_operation_for_test
            ) is IvaTerritorialScope.from_registry("third_country")

    def test_every_member_state_except_spain_resolves_to_the_eu_scope(self) -> None:
        """Derived from the catalogue, so a State joining or leaving is covered."""
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            member_states = resolve_eu_member_state_catalogue(authority=_authority_operation_for_test).all_states
            for member in member_states:
                code = member.value.upper()
                expected = None if code == SPAIN_COUNTRY_CODE else IvaTerritorialScope.from_registry("eu_member")

                assert territorial_scope_for_country(code, operation=_authority_operation_for_test) is expected, code

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
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            assert territorial_scope_for_country(
                "NO", operation=_authority_operation_for_test
            ) is IvaTerritorialScope.from_registry("third_country")
            assert territorial_scope_for_country(
                "BR", operation=_authority_operation_for_test
            ) is IvaTerritorialScope.from_registry("third_country")
