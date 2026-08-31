"""The country code a STRUCTURED record states, in whichever code system it uses.

A printed document states a country as a name; a machine-readable one states it
as a code, and the two syntaxes this reader accepts disagree about which code
system. UBL states the ISO alpha-2 form and Facturae states the alpha-3 form --
``ESP`` where every country surface in this codebase is keyed ``ES``.

**The failure this closes is invisible, which is what makes it worth a suite.**
An alpha-3 code handed to the alpha-2 resolver fails a length check and returns
``None``, and ``None`` is exactly what a document stating no country returns. So
a Facturae invoice whose country element is present, read and parsed establishes
nothing, and the establishment ladder's postal rung -- gated on country evidence
positively naming Spain -- stays shut for the whole Spanish national format. No
exception, no diagnostic, no operator-visible signal.

The correspondence closing it is registry DATA, a column in the same bundled
vocabulary the printed names are matched against, so both code systems and every
printed name resolve onto one code in one reviewable place. The cases below are
in two halves: what the lookup answers, and what the loader refuses to load. The
second half is what makes the first trustworthy -- a table that can load a
contradiction resolves a country by file ordering.

See Also:
    :func:`~domain.iva.country_code_for_stated_country_code`
        The lookup under test.
    :func:`~domain.iva.country_code_for_printed_country_name`
        Its printed-document counterpart, reading the same table's other column.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping

import pytest

from ....core.resources.bundled_data import bundled_path
from ....tests.country_vocabulary_specimens import an_uncatalogued_alpha3
from ..errors import IvaCatalogueError
from ..establishment import _index_country_alpha3, country_code_for_stated_country_code

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _bundled() -> dict[str, object]:
    raw_payload = tomllib.loads(
        bundled_path("registry", "aeat", "iva", "country_names.toml").read_text(encoding="utf-8"),
    )
    payload: dict[str, object] = {}
    for key, value in raw_payload.items():
        assert isinstance(key, str)
        payload[key] = value
    return payload


def _bundled_country_records() -> list[Mapping[str, object]]:
    """Read the shipped country rows, asserting only that they ARE rows.

    Deliberately typed no tighter than that. A row missing ``alpha3``, or
    repeating one another row already carries, is precisely what the gates
    below look for on the shipped file -- so a model requiring the column
    would refuse the defect at parse time and leave every assertion passing
    over a population that can no longer contain it.
    """
    records = _bundled()["country"]
    assert isinstance(records, list), "the shipped catalogue no longer stores countries as an array of tables"
    rows: list[Mapping[str, object]] = []
    for record in records:
        assert isinstance(record, dict), f"country row is not a table: {record!r}"
        rows.append(record)
    return rows


class TestTheLookup:
    """What a stated code resolves to, and what it deliberately does not."""

    @pytest.mark.parametrize(
        ("stated", "expected"),
        [
            ("ESP", "ES"),
            ("DEU", "DE"),
            ("PRT", "PT"),
            ("GRC", "GR"),
            ("USA", "US"),
        ],
    )
    def test_an_alpha3_code_resolves_through_the_registry_column(self, stated: str, expected: str) -> None:
        """The correspondence is a lookup, and these are the cases that matter here.

        Greece is carried deliberately: its IVA prefix diverges from its ISO code
        (``EL`` against ``GR``), and every catalogue downstream is ISO-keyed, so a
        column that resolved it to the prefix would put two answers into the tree
        for one country.
        """
        assert country_code_for_stated_country_code(stated) == expected

    @pytest.mark.parametrize("stated", ["ES", "es", " es ", "De"])
    def test_an_alpha2_code_passes_through_normalised(self, stated: str) -> None:
        """The already-correct system is normalised and handed on, never re-decided."""
        assert country_code_for_stated_country_code(stated) == stated.strip().upper()

    @pytest.mark.parametrize("stated", [None, "", "  ", "E", "ESPA", "E5P", "12"])
    def test_an_unreadable_code_establishes_nothing(self, stated: str | None) -> None:
        """Unreadable evidence is a normal outcome of reading, not an error.

        And it resolves to nothing rather than to anything: the peninsula is the
        majority population, so a domestic default here would be invisible in
        testing while placing foreign parties inside the territorio de aplicación
        del impuesto.
        """
        assert country_code_for_stated_country_code(stated) is None

    def test_an_alpha3_outside_the_vocabulary_establishes_nothing(self) -> None:
        """The table is bounded, so an unlisted country degrades safely.

        The specimen is DERIVED from the vocabulary rather than named, so the
        case proves the bound rather than a particular country's absence. The
        table is a reviewable tax-facing vocabulary rather than a general country
        database, and which codes sit outside it is a decision that moves.

        This case has twice been reddened by its own fixture: written over
        ``BOL`` it broke when Bolivia was added, and rewritten over ``THA`` it
        would have broken again on the next argued widening. Both times the
        behaviour was fine and only the pin had gone stale, which is the argument
        for deriving it.
        """
        assert country_code_for_stated_country_code(an_uncatalogued_alpha3()) is None

    def test_no_stated_code_resolves_to_spain_by_accident(self) -> None:
        """Only Spain's own codes name Spain, which is the rung's whole trigger.

        The postal rung opens on country evidence positively naming Spain, so any
        other code resolving to ``ES`` would open the Spanish province lookup for
        a foreign party and answer it with a well-formed wrong territory.
        """
        spanish = {
            code
            for code in ("ESP", "ES", "PRT", "PT", "FRA", "FR", "AND", "AD", "MAR", "MA")
            if country_code_for_stated_country_code(code) == "ES"
        }
        assert spanish == {"ESP", "ES"}


class TestTheBundledColumn:
    """The shipped table's own invariants, asserted against the file rather than a copy."""

    def test_every_record_carries_an_alpha3_code(self) -> None:
        """The column is required, so no country can be silently unresolvable.

        Read from the file rather than restated, so this cannot become a second
        copy of the table that drifts against it and passes while doing so.
        """
        records = _bundled_country_records()
        assert records
        missing = [record["code"] for record in records if not str(record.get("alpha3", "")).strip()]
        assert not missing, f"records carrying no alpha-3 code: {missing}"

    def test_the_column_names_each_country_exactly_once(self) -> None:
        """One alpha-3 per country and one country per alpha-3, on the shipped data."""
        records = _bundled_country_records()
        codes = [str(record["alpha3"]) for record in records]
        assert len(set(codes)) == len(codes)
        assert len(_index_country_alpha3(_bundled(), source="bundled")) == len(codes)

    def test_northern_ireland_is_absent_from_both_columns(self) -> None:
        """``XI`` is an IVA jurisdiction rather than an ISO country, and has no alpha-3.

        Asserted because the name column deliberately excludes it too: it is
        established by a printed NIF-IVA prefix or not at all, and a country
        record inventing an alpha-3 for it would be fabricated data.
        """
        indexed = _index_country_alpha3(_bundled(), source="bundled")
        assert "XI" not in indexed.values()


class TestWhatTheLoaderRefuses:
    """The refusals that make the lookup trustworthy, reachable with a payload.

    Exercised against payloads rather than only against the bundled file, because
    a refusal that can be reached only by corrupting shipped data is a refusal
    nothing proves.
    """

    def test_a_record_carrying_no_alpha3_is_refused(self) -> None:
        """Optional would be indistinguishable from "this country has no alpha-3".

        Both yield nothing at the call site, and the caller reads nothing as "the
        document stated no country" -- the exact silent blank the column exists to
        close, reintroduced by an omission nobody would notice.
        """
        with pytest.raises(IvaCatalogueError, match="no alpha-3 code"):
            _index_country_alpha3({"country": [{"code": "DE", "names": ["Alemania"]}]}, source="probe")

    @pytest.mark.parametrize("alpha3", ["", "DE", "DEUT", "D3U", "  "])
    def test_a_malformed_alpha3_is_refused(self, alpha3: str) -> None:
        with pytest.raises(IvaCatalogueError, match="no alpha-3 code"):
            _index_country_alpha3({"country": [{"code": "DE", "alpha3": alpha3}]}, source="probe")

    def test_two_countries_claiming_one_alpha3_are_refused(self) -> None:
        """That code would name two countries, and the last read would win silently.

        The direct analogue of the name-collision refusal beside it: a code that
        cannot name one country cannot establish one, so the table is refused
        whole rather than resolved by file ordering.
        """
        payload = {
            "country": [
                {"code": "DE", "alpha3": "DEU"},
                {"code": "AT", "alpha3": "DEU"},
            ],
        }
        with pytest.raises(IvaCatalogueError, match="claimed by both"):
            _index_country_alpha3(payload, source="probe")

    def test_one_country_stating_two_alpha3_codes_is_refused(self) -> None:
        """The same contradiction from the other side: a record disagreeing with itself."""
        payload = {
            "country": [
                {"code": "DE", "alpha3": "DEU"},
                {"code": "DE", "alpha3": "GER"},
            ],
        }
        with pytest.raises(IvaCatalogueError, match="two different alpha-3 codes"):
            _index_country_alpha3(payload, source="probe")

    def test_a_country_repeated_consistently_is_accepted(self) -> None:
        """The permitted half, so the two refusals above are not over-broad."""
        payload = {
            "country": [
                {"code": "DE", "alpha3": "DEU"},
                {"code": "DE", "alpha3": "DEU"},
            ],
        }
        assert _index_country_alpha3(payload, source="probe") == {"DEU": "DE"}

    def test_a_record_naming_no_alpha2_code_is_refused(self) -> None:
        with pytest.raises(IvaCatalogueError, match="alpha-2"):
            _index_country_alpha3({"country": [{"alpha3": "DEU"}]}, source="probe")

    def test_an_empty_column_is_refused(self) -> None:
        with pytest.raises(IvaCatalogueError, match="no alpha-3 correspondence"):
            _index_country_alpha3({"country": []}, source="probe")
