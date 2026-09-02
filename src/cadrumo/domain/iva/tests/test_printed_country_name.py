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
* two different countries cannot claim one normalised name, which is the check
  that makes accent folding sound rather than merely convenient.

Model-free and network-free: a lookup against bundled registry data.

See Also:
    :func:`~domain.iva.territorial_scope_for_country`
        The single authority on what a country code establishes, which this
        rung composes with rather than duplicating.
    :func:`~domain.iva.territorial_scope_for_spanish_postal_code`
        The sub-national rung that answers what a Spanish name cannot.
"""

from __future__ import annotations

import tomllib

import pytest

from ....core.resources.bundled_data import bundled_path
from ..classification import IvaTerritorialScope
from ..country_vocabulary import _index_country_names
from ..errors import IvaCatalogueError
from ..establishment import (
    country_code_for_printed_country_name,
    territorial_scope_for_printed_country_name,
)
from ..schema import EUMemberState

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NORTHERN_IRELAND = "XI"


def _vocabulary() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return each bundled record as its declared code and printed names.

    Read from the file rather than restated here, so no assertion below can
    become a second copy of the table that drifts against it and passes while
    doing so.
    """
    payload = tomllib.loads(
        bundled_path("registry", "aeat", "iva", "country_names.toml").read_text(encoding="utf-8"),
    )
    records = tuple(
        (str(record["code"]), tuple(str(name) for name in record["names"])) for record in payload["country"]
    )
    assert records, "the vocabulary must carry at least one country"
    return records


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
        assert territorial_scope_for_printed_country_name(printed) is None

    def test_an_absent_name_yields_nothing(self) -> None:
        assert country_code_for_printed_country_name(None) is None
        assert territorial_scope_for_printed_country_name(None) is None

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
        assert territorial_scope_for_printed_country_name(printed) not in {
            IvaTerritorialScope.ES_MAINLAND,
            IvaTerritorialScope.ES_CANARIAS,
            IvaTerritorialScope.ES_CEUTA_MELILLA,
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

    def test_no_record_lists_a_name_its_own_fold_would_already_cover(self) -> None:
        """The gate that keeps accent folding load-bearing rather than decorative.

        A record carrying both "Mexico" and "México" resolves both even with the
        folding removed, so the variant tests above would pass on the DATA while
        the behaviour they name was gone. That is not hypothetical: the first
        draft of this vocabulary did exactly that, and the mutation that deleted
        the fold reddened nothing here until the twins came out. Refusing the
        redundancy is what stops it coming back.
        """
        from ..country_vocabulary import normalise_printed_country_name

        for code, names in _vocabulary():
            seen: dict[str, str] = {}
            for name in names:
                folded = normalise_printed_country_name(name)
                twin = seen.get(folded)
                assert twin is None, f"{code}: {name!r} is the fold of {twin!r}"
                seen[folded] = name

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
        assert territorial_scope_for_printed_country_name("Deutschland") is IvaTerritorialScope.EU_MEMBER

    def test_a_third_country_name_establishes_the_third_country_scope(self) -> None:
        assert territorial_scope_for_printed_country_name("Suiza") is IvaTerritorialScope.THIRD_COUNTRY

    def test_a_spanish_name_names_the_state_but_establishes_no_scope(self) -> None:
        """The composition proving nothing about Spain is decided twice.

        The name axis DOES recognise España -- it is a country the documents
        print. What it must not do is turn that into a territory, because ES
        holds three the law treats differently and only the postal code
        separates them.
        """
        assert country_code_for_printed_country_name("España") == "ES"
        assert territorial_scope_for_printed_country_name("España") is None


class TestTheVocabularyCoversWhatTheClassifierTurnsOn:
    """Derived from the catalogues, never listed a second time here."""

    def test_every_member_state_is_reachable_by_name(self) -> None:
        """A missing State is a real gap, so the expectation is the catalogue.

        Northern Ireland is excluded from the expectation deliberately, and the
        next test asserts the exclusion rather than leaving it implied.
        """
        covered = {code.upper() for code, _ in _vocabulary()}
        expected = {member.value.upper() for member in EUMemberState} - {_NORTHERN_IRELAND}
        assert expected <= covered, sorted(expected - covered)

    def test_no_printed_name_maps_to_northern_ireland(self) -> None:
        """An address cannot settle the XI jurisdiction, so no name may claim it.

        A Belfast address prints "United Kingdom"; the Protocol jurisdiction is
        established by a printed NIF-IVA prefix or not at all. A name mapping to
        XI would manufacture the goods jurisdiction from a postal address.
        """
        codes = {code.upper() for code, _ in _vocabulary()}
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
        for code, _ in _vocabulary():
            assert len(code) == 2 and code.isalpha() and code.isupper(), code

    def test_every_declared_name_reaches_its_own_record(self) -> None:
        """The one restatement-shaped assertion, and it is not one.

        The expectation is read from the file rather than written here, so this
        cannot drift into a second copy of the table. What it proves is a
        property the file alone does not: that the matcher's normalisation is
        the SAME normalisation the loader indexed under, which is exactly what
        would break if either side gained a transform the other lacked.
        """
        for code, names in _vocabulary():
            for name in names:
                assert country_code_for_printed_country_name(name) == code.upper(), name


class TestTheLoaderRefusesAnUnusableVocabulary:
    """Exercised against payloads, because a check only the bundled file can reach is unproven."""

    def test_two_countries_claiming_one_normalised_name_is_refused(self) -> None:
        """The check that makes accent folding sound rather than merely convenient.

        Folding is only safe while no two DIFFERENT countries fold together.
        Resolving such a collision to whichever record was read last would pick
        a tax territory by file ordering, so the table is refused whole.
        """
        payload = {
            "country": [
                {"code": "MX", "names": ["México"]},
                {"code": "AR", "names": ["Mexico"]},
            ],
        }
        with pytest.raises(IvaCatalogueError, match="claim"):
            _index_country_names(payload, source="probe")

    def test_one_country_repeating_a_spelling_is_accepted(self) -> None:
        """The permitted half, so the refusal above is not over-broad.

        Both spellings name the same code, so they cannot disagree; writing both
        out spares a reviewer having to know the folding rule.
        """
        payload = {"country": [{"code": "MX", "names": ["México", "Mexico"]}]}
        assert _index_country_names(payload, source="probe") == {"mexico": "MX"}

    @pytest.mark.parametrize(
        "record",
        [
            {"names": ["Nowhere"]},
            {"code": "", "names": ["Nowhere"]},
            {"code": "DEU", "names": ["Nowhere"]},
            {"code": "D1", "names": ["Nowhere"]},
        ],
    )
    def test_a_record_naming_no_alpha_two_code_is_refused(self, record: dict[str, object]) -> None:
        with pytest.raises(IvaCatalogueError, match="alpha-2"):
            _index_country_names({"country": [record]}, source="probe")

    def test_a_country_carrying_no_printed_name_is_refused(self) -> None:
        with pytest.raises(IvaCatalogueError, match="no printed name"):
            _index_country_names({"country": [{"code": "DE", "names": []}]}, source="probe")

    def test_a_blank_printed_name_is_refused(self) -> None:
        with pytest.raises(IvaCatalogueError, match="blank"):
            _index_country_names({"country": [{"code": "DE", "names": ["  "]}]}, source="probe")

    def test_an_empty_vocabulary_is_refused(self) -> None:
        with pytest.raises(IvaCatalogueError, match="empty"):
            _index_country_names({"country": []}, source="probe")

    def test_the_bundled_vocabulary_survives_its_own_refusals(self) -> None:
        """The shipped table passes every check above, checked here not implied."""
        payload = tomllib.loads(
            bundled_path("registry", "aeat", "iva", "country_names.toml").read_text(encoding="utf-8"),
        )
        indexed = _index_country_names(payload, source="bundled")
        assert len(indexed) > len({code for code in indexed.values()})
