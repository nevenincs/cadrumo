"""A printed country NAME settles the country, or nothing does.

The country resolver takes a code, and a code is printed only where a NIF-IVA
is. Everywhere else the country appears in an address block as a name, in
whatever language the issuer writes in. Asking a reading stage for ``DE`` when
the page says "Deutschland" would be asking it to translate, and translation is
inference; transcribing the name verbatim and matching it against a bounded
vocabulary is a lookup. This is the gate over that lookup.

**What is worth testing here is not that the table contains what it contains.**
Asserting that every name resolves to the code written beside it would restate
the registry file in Python and pass while the matcher was broken. The
properties gated here are the ones that could actually be wrong:

* an unrecognised name yields NOTHING, and above all never Spain;
* a near miss is not a match, which is why the match is exact rather than the
  containment the regime-legend vocabulary uses;
* the printed variants a real document carries -- case, line breaks, ASCII-only
  spellings -- reach the same country;
* the vocabulary covers every Member State the intra-community branch turns on,
  derived from that catalogue rather than listed again here;
* no name maps to Northern Ireland, whose jurisdiction an address cannot settle;
* the published resolver exposes one normalised name for one country, which is
  the lookup contract that makes accent folding sound rather than merely
  convenient; malformed authoring rows are compiler-owned tests.

Model-free and network-free: a lookup against bundled registry data.

See Also:
    :func:`~domain.iva.territorial_scope_for_country`
        The single authority on what a country code establishes, which this
        rung composes with rather than duplicating.
    :func:`~domain.iva.territorial_scope_for_spanish_postal_code`
        The sub-national rung that answers what a Spanish name cannot.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.iva.classification import IvaTerritorialScope

from ..country_vocabulary import country_codes_by_printed_name, normalise_printed_country_name
from ..establishment import (
    country_code_for_printed_country_name,
    territorial_scope_for_country,
)
from ..schema import EUMemberState

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NORTHERN_IRELAND = "XI"


class TestAnUnrecognisedNameEstablishesNothing:
    """The safety property, and the one a wrong default would make invisible."""

    @pytest.mark.parametrize(
        "printed",
        [
            "Atlantis",
            "Wakanda",
            "Repubblica di San Marino",
            "Kazakhstan",
            "123",
            "-",
            "",
            "   ",
        ],
    )
    def test_a_name_outside_the_vocabulary_yields_no_country(self, printed: str) -> None:
        assert country_code_for_printed_country_name(printed) is None

    @pytest.mark.parametrize("printed", ["Atlantis", "Kazakhstan", "", "   "])
    def test_a_name_outside_the_vocabulary_yields_no_scope(self, printed: str) -> None:
        assert territorial_scope_for_country(country_code_for_printed_country_name(printed)) is None

    def test_an_absent_name_yields_nothing(self) -> None:
        assert country_code_for_printed_country_name(None) is None
        assert territorial_scope_for_country(country_code_for_printed_country_name(None)) is None

    @pytest.mark.parametrize(
        "printed",
        ["Atlantis", "Kazakhstan", "", "   ", "123", "Nigeria", "German"],
    )
    def test_no_unrecognised_name_ever_lands_in_spain(self, printed: str) -> None:
        """The direction that matters, stated as its own assertion.

        A miss resolving to the peninsula would be invisible in ordinary testing
        because the peninsula is the majority population, while silently placing
        a foreign party inside the territorio de aplicación del impuesto. So the
        Spanish outcomes are excluded by name rather than left implied by the
        ``is None`` assertions above.
        """
        assert country_code_for_printed_country_name(printed) != "ES"
        assert territorial_scope_for_country(country_code_for_printed_country_name(printed)) not in {
            IvaTerritorialScope._from_registry("es_mainland"),
            IvaTerritorialScope._from_registry("es_canarias"),
            IvaTerritorialScope._from_registry("es_ceuta_melilla"),
        }


class TestANearMissIsNotAMatch:
    """Exact after normalisation, which is why containment was rejected."""

    @pytest.mark.parametrize("printed", ["Niger", "Nigeria", "Papua New Guinea", "Guinea"])
    def test_a_country_name_containing_or_contained_by_a_vocabulary_entry_does_not_match(
        self,
        printed: str,
    ) -> None:
        """The trap containment matching would spring.

        None of these four is in the vocabulary, and each either contains or is
        contained by a plausible entry. Under containment matching at least one
        would resolve, and it would resolve to the wrong tax territory from a
        correctly printed name.
        """
        assert country_code_for_printed_country_name(printed) is None

    @pytest.mark.parametrize(
        "printed",
        ["German", "Germanys", "Alemani", "Franc", "Italiana", "Portugalia", "Chin", "Chad"],
    )
    def test_a_truncated_or_extended_spelling_does_not_match(self, printed: str) -> None:
        assert country_code_for_printed_country_name(printed) is None

    def test_a_name_embedded_in_a_wider_line_does_not_match(self) -> None:
        """An address line is not a country field.

        The regime-legend vocabulary matches by containment because a mención is
        a phrase inside prose. This axis is handed a transcribed field, so a full
        address line reaching it means the reading stage handed over the wrong
        thing -- and answering anyway would hide that.
        """
        assert country_code_for_printed_country_name("Musterstrasse 1, 10115 Berlin, Deutschland") is None


class TestThePrintedVariantsARealDocumentCarries:
    """Case, line breaks and ASCII-only spellings reach the same country."""

    @pytest.mark.parametrize(
        "printed",
        ["Deutschland", "DEUTSCHLAND", "deutschland", "  Deutschland  ", "Alemania", "Germany"],
    )
    def test_case_whitespace_and_language_variants_reach_germany(self, printed: str) -> None:
        assert country_code_for_printed_country_name(printed) == "DE"

    def test_a_name_broken_across_an_address_line_collapses(self) -> None:
        assert country_code_for_printed_country_name("Paises\n  Bajos") == "NL"
        assert country_code_for_printed_country_name("United\tKingdom") == "GB"

    @pytest.mark.parametrize(
        ("accented", "ascii_only", "expected"),
        [
            ("México", "Mexico", "MX"),
            ("Perú", "Peru", "PE"),
            ("Türkiye", "Turkiye", "TR"),
            ("España", "Espana", "ES"),
            ("Magyarország", "Magyarorszag", "HU"),
            ("România", "Romania", "RO"),
        ],
    )
    def test_an_ascii_only_printer_reaches_the_same_country(
        self,
        accented: str,
        ascii_only: str,
        expected: str,
    ) -> None:
        """Accent folding earning its place, on the population that needs it."""
        assert country_code_for_printed_country_name(accented) == expected
        assert country_code_for_printed_country_name(ascii_only) == expected

    def test_a_transliteration_convention_is_data_not_a_folding_rule(self) -> None:
        """``Oe`` is not something the accent fold produces.

        Both spellings resolve, but only one of them does so because of the
        fold; the other is in the table. Asserted together so a later
        simplification that dropped the listed form would red here rather than
        silently narrow the vocabulary.
        """
        assert country_code_for_printed_country_name("Österreich") == "AT"
        assert country_code_for_printed_country_name("Oesterreich") == "AT"


class TestTheRungComposesRatherThanDecides:
    """Scope comes from the country resolver; this axis only names the country."""

    def test_a_member_state_name_establishes_the_eu_scope(self) -> None:
        assert territorial_scope_for_country(
            country_code_for_printed_country_name("Deutschland")
        ) == IvaTerritorialScope._from_registry("eu_member")

    def test_a_third_country_name_establishes_the_third_country_scope(self) -> None:
        assert territorial_scope_for_country(
            country_code_for_printed_country_name("Suiza")
        ) == IvaTerritorialScope._from_registry("third_country")

    def test_a_spanish_name_names_the_state_but_establishes_no_scope(self) -> None:
        """The composition proving nothing about Spain is decided twice.

        The name axis DOES recognise España -- it is a country the documents
        print. What it must not do is turn that into a territory, because ES
        holds three the law treats differently and only the postal code
        separates them.
        """
        assert country_code_for_printed_country_name("España") == "ES"
        assert territorial_scope_for_country(country_code_for_printed_country_name("España")) is None


class TestTheVocabularyCoversWhatTheClassifierTurnsOn:
    """Derived from the catalogues, never listed a second time here."""

    def test_every_member_state_is_reachable_by_name(self) -> None:
        """A missing State is a real gap, so the expectation is the catalogue.

        Northern Ireland is excluded from the expectation deliberately, and the
        next test asserts the exclusion rather than leaving it implied.
        """
        covered = {code.upper() for code in country_codes_by_printed_name().values()}
        expected = {member.value.upper() for member in EUMemberState} - {_NORTHERN_IRELAND}
        assert expected <= covered, sorted(expected - covered)

    def test_no_printed_name_maps_to_northern_ireland(self) -> None:
        """An address cannot settle the XI jurisdiction, so no name may claim it.

        A Belfast address prints "United Kingdom"; the Protocol jurisdiction is
        established by a printed NIF-IVA prefix or not at all. A name mapping to
        XI would manufacture the goods jurisdiction from a postal address.
        """
        codes = {code.upper() for code in country_codes_by_printed_name().values()}
        assert _NORTHERN_IRELAND not in codes
        for printed in ("Northern Ireland", "Irlanda del Norte", "Ulster", "United Kingdom"):
            assert country_code_for_printed_country_name(printed) != _NORTHERN_IRELAND

    def test_no_sub_national_name_is_carried(self) -> None:
        """The excluded class, asserted rather than described in a comment."""
        for printed in ("England", "Scotland", "Wales", "Catalunya", "Bayern", "Baviera"):
            assert country_code_for_printed_country_name(printed) is None

    def test_a_bare_alpha_two_code_is_not_a_name(self) -> None:
        """Codes belong to the code rung; two authorities on one string is one too many."""
        for printed in ("DE", "FR", "ES", "de"):
            assert country_code_for_printed_country_name(printed) is None

    def test_every_declared_code_is_a_well_formed_alpha_two(self) -> None:
        for code in country_codes_by_printed_name().values():
            assert len(code) == 2 and code.isalpha() and code.isupper(), code

    def test_every_declared_name_reaches_its_own_record(self) -> None:
        """The one restatement-shaped assertion, and it is not one.

        The expectation comes from the published resolver rather than a copied
        table, so this checks that the matcher's normalisation is the SAME
        normalisation the resolver indexed under.
        """
        for name, code in country_codes_by_printed_name().items():
            assert country_code_for_printed_country_name(normalise_printed_country_name(name)) == code.upper(), name
