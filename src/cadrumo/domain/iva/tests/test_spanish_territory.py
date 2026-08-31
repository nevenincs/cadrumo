"""A printed Spanish postal code settles the territory, or nothing does.

The country axis deliberately refuses Spain: ``ES`` names the Member State while
the IVA territory inside it stays undetermined, and Spain holds three the law
treats differently — the peninsula and Balearics inside the territorio de
aplicación del impuesto, Canarias under IGIC, Ceuta and Melilla under IPSI, the
latter two outside LIVA entirely (Ley 37/1992 art. 3.Dos). This is the axis that
finally answers it, from the one sub-national identifier a document reliably
prints.

**The asymmetry is the safety property.** A well-formed code outside the excluded
prefixes resolves to the mainland, because the registry enumerates only the
exclusions and absence from it means inside. But an ABSENT or malformed code
resolves to nothing, never to the mainland — the peninsula is the majority
population, so a default there would be invisible in testing and would silently
place Canarian and Ceutan parties inside a territory their operations are not
subject to. That is the restrictive-provision-as-default failure one level below
the country axis that already refuses it.

Model-free and network-free: a lookup against bundled registry data.

See Also:
    :func:`~domain.iva.territorial_scope_for_country`
        The country axis, which returns nothing for Spain by design.
"""

from __future__ import annotations

import pytest

from ..classification import IvaTerritorialScope
from ..establishment import territorial_scope_for_country, territorial_scope_for_spanish_postal_code

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_OUTSIDE_THE_TAI = frozenset({IvaTerritorialScope.ES_CANARIAS, IvaTerritorialScope.ES_CEUTA_MELILLA})


class TestTheExcludedTerritoriesAreRecognised:
    """The population the TAI does not govern, which is the whole point of the axis."""

    @pytest.mark.parametrize("printed", ["35001", "35500", "38010", "38700"])
    def test_a_canarian_code_resolves_outside_the_tai(self, printed: str) -> None:
        assert territorial_scope_for_spanish_postal_code(printed) is IvaTerritorialScope.ES_CANARIAS

    @pytest.mark.parametrize("printed", ["51001", "51002"])
    def test_a_ceuta_code_resolves_outside_the_tai(self, printed: str) -> None:
        assert territorial_scope_for_spanish_postal_code(printed) is IvaTerritorialScope.ES_CEUTA_MELILLA

    @pytest.mark.parametrize("printed", ["52001", "52006"])
    def test_a_melilla_code_resolves_outside_the_tai(self, printed: str) -> None:
        assert territorial_scope_for_spanish_postal_code(printed) is IvaTerritorialScope.ES_CEUTA_MELILLA

    def test_every_excluded_prefix_comes_from_the_registry(self) -> None:
        """Read from the bundled table, so a boundary change moves here with it.

        Asserted by reading the registry and checking each declared prefix
        resolves to the scope it declares, rather than by listing prefixes here
        — a second copy in the gate would drift against the first and pass while
        doing so.
        """
        import tomllib

        from ....core.resources._boundary import bundled_path

        payload = tomllib.loads(
            bundled_path("registry", "aeat", "iva", "territories.toml").read_text(encoding="utf-8"),
        )
        records = payload["territory"]

        assert records, "the registry must enumerate at least one excluded territory"
        for record in records:
            expected = IvaTerritorialScope(record["scope"])
            for prefix in record["postal_prefixes"]:
                assert territorial_scope_for_spanish_postal_code(f"{prefix}001") is expected, prefix
                assert expected in _OUTSIDE_THE_TAI, f"{prefix} claims a scope inside the TAI"


class TestTheMainlandIsNeverInvented:
    """An answer only where the code was actually readable."""

    @pytest.mark.parametrize("printed", [None, "", "   ", "2800", "280011", "abcde", "28 001", "ES28001"])
    def test_absent_or_malformed_evidence_resolves_to_nothing(self, printed: str | None) -> None:
        assert territorial_scope_for_spanish_postal_code(printed) is None

    def test_no_unreadable_input_produces_a_territory(self) -> None:
        """The property over the whole unreadable space, not a sample."""
        unreadable: list[str | None] = [None, "", " ", "1", "12", "123", "1234", "123456", "1a345", "  28001  x"]

        assert {territorial_scope_for_spanish_postal_code(probe) for probe in unreadable} == {None}


class TestAWellFormedCodeOutsideTheExclusionsIsTheMainland:
    """Positive control: refusing everything would satisfy the class above."""

    @pytest.mark.parametrize("printed", ["28001", "08001", "41001", "07800", "46001"])
    def test_a_peninsular_or_balearic_code_resolves_to_the_mainland(self, printed: str) -> None:
        assert territorial_scope_for_spanish_postal_code(printed) is IvaTerritorialScope.ES_MAINLAND

    def test_the_balearics_are_inside_the_tai(self) -> None:
        """Named separately because it is the island group that IS inside.

        Pinned because "islands are outside" is the plausible wrong
        generalisation, and Ley 37/1992 art. 3.Dos places the Balearics inside
        the territory while excluding the Canaries.
        """
        assert territorial_scope_for_spanish_postal_code("07001") is IvaTerritorialScope.ES_MAINLAND


class TestTheTwoAxesComposeWithoutOverlapping:
    """The country axis refuses Spain precisely so this one can answer it."""

    def test_the_country_axis_still_refuses_a_spanish_code(self) -> None:
        """If this ever answers, the two axes have started competing."""
        assert territorial_scope_for_country("ES") is None

    def test_the_postal_axis_answers_what_the_country_axis_would_not(self) -> None:
        assert territorial_scope_for_country("ES") is None
        assert territorial_scope_for_spanish_postal_code("35001") is IvaTerritorialScope.ES_CANARIAS
