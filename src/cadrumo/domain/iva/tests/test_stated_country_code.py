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
printed name resolve onto one code in one reviewable place. The lookup cases
below stay in the domain owner; malformed source rows and schema refusals are
owned by the development compiler, which validates a candidate before it can be
published.

See Also:
    :func:`~domain.iva.country_code_for_stated_country_code`
        The lookup under test.
    :func:`~domain.iva.country_code_for_printed_country_name`
        Its printed-document counterpart, reading the same table's other column.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ....tests.country_vocabulary_specimens import an_uncatalogued_alpha3
from ..establishment import country_code_for_stated_country_code

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            assert country_code_for_stated_country_code(stated, operation=_authority_operation_for_test) == expected

    @pytest.mark.parametrize("stated", ["ES", "es", " es ", "De"])
    def test_an_alpha2_code_passes_through_normalised(self, stated: str) -> None:
        """The already-correct system is normalised and handed on, never re-decided."""
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            assert (
                country_code_for_stated_country_code(stated, operation=_authority_operation_for_test)
                == stated.strip().upper()
            )

    @pytest.mark.parametrize("stated", [None, "", "  ", "E", "ESPA", "E5P", "12"])
    def test_an_unreadable_code_establishes_nothing(self, stated: str | None) -> None:
        """Unreadable evidence is a normal outcome of reading, not an error.

        And it resolves to nothing rather than to anything: the peninsula is the
        majority population, so a domestic default here would be invisible in
        testing while placing foreign parties inside the territorio de aplicación
        del impuesto.
        """
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            assert country_code_for_stated_country_code(stated, operation=_authority_operation_for_test) is None

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
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            assert (
                country_code_for_stated_country_code(an_uncatalogued_alpha3(), operation=_authority_operation_for_test)
                is None
            )

    def test_no_stated_code_resolves_to_spain_by_accident(self) -> None:
        """Only Spain's own codes name Spain, which is the rung's whole trigger.

        The postal rung opens on country evidence positively naming Spain, so any
        other code resolving to ``ES`` would open the Spanish province lookup for
        a foreign party and answer it with a well-formed wrong territory.
        """
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            spanish = {
                code
                for code in ("ESP", "ES", "PRT", "PT", "FRA", "FR", "AND", "AD", "MAR", "MA")
                if country_code_for_stated_country_code(code, operation=_authority_operation_for_test) == "ES"
            }
            assert spanish == {"ESP", "ES"}
