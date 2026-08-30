"""Real-behavior tests for the IVA saturation primitives.

Covers :func:`cadrumo.domain.iva.resolve_category_rate` (category→rate-fraction
resolution against the registry rate authority, and the not-derivable
surfacing for every non-domestic category) and
:func:`cadrumo.domain.iva.split_gross_at_rate` (the inverse gross→base/IVA split
with AEAT half-up rounding). Expected rate fractions are asserted against the
grounded ``rates.toml`` values (Spain general 21 / reduced 10 / super-reduced 4
/ zero 0), not hand-computed from a formula under test.

Authority: ``llm-ledger-classification-design``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..saturation import IvaRateResolution, resolve_category_rate, split_gross_at_rate
from ..schema import IvaCategory, IvaRateKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ON_DATE = date(2025, 6, 1)


def test_domestic_positive_rate_resolves_to_registry_fraction() -> None:
    """Domestic general/reduced/super-reduced resolve to the grounded fraction."""
    cases: tuple[tuple[IvaCategory, Decimal, IvaRateKind], ...] = (
        (IvaCategory.DOMESTIC_GENERAL, Decimal("0.21"), IvaRateKind.GENERAL),
        (IvaCategory.DOMESTIC_REDUCED, Decimal("0.10"), IvaRateKind.REDUCED),
        (IvaCategory.DOMESTIC_SUPER_REDUCED, Decimal("0.04"), IvaRateKind.SUPER_REDUCED),
    )

    for category, expected_rate, expected_kind in cases:
        resolution = resolve_category_rate(category, on_date=_ON_DATE)
        assert resolution.derivable is True, category
        assert resolution.reason == "", category
        assert resolution.rate_kind is expected_kind, category
        assert resolution.rate is not None, category
        assert resolution.rate == expected_rate, category


def test_zero_and_exempt_derive_zero_rate() -> None:
    """Zero-rated and exempt categories derive a derivable zero fraction."""
    cases: tuple[tuple[IvaCategory, IvaRateKind], ...] = (
        (IvaCategory.DOMESTIC_ZERO, IvaRateKind.ZERO),
        (IvaCategory.DOMESTIC_EXEMPT, IvaRateKind.EXEMPT),
    )

    for category, expected_kind in cases:
        resolution = resolve_category_rate(category, on_date=_ON_DATE)
        assert resolution.derivable is True, category
        assert resolution.rate == Decimal("0"), category
        assert resolution.rate_kind is expected_kind, category
        assert resolution.reason == "", category


_NON_DERIVABLE_CATEGORIES = [
    IvaCategory.DOMESTIC_NOT_SUBJECT,
    IvaCategory.DOMESTIC_REVERSE_CHARGE,
    IvaCategory.INTRA_COMMUNITY_SUPPLY,
    IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
    IvaCategory.INTRA_COMMUNITY_TRIANGULATION,
    IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
    IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
    IvaCategory.IMPORT_THIRD_COUNTRY,
    IvaCategory.RECARGO_EQUIVALENCIA,
    IvaCategory.REGIMEN_SIMPLIFICADO,
    IvaCategory.REAGP_COMPENSATION,
    IvaCategory.OPERACION_NO_SUJETA,
    IvaCategory.ERRONEOUS_INVOICE,
    IvaCategory.UNKNOWN,
]


def test_non_domestic_categories_surface_not_derivable() -> None:
    """Every non-derivable category returns derivable=False with a reason, no rate."""
    for category in _NON_DERIVABLE_CATEGORIES:
        resolution = resolve_category_rate(category, on_date=_ON_DATE)
        assert resolution.derivable is False, category
        assert resolution.rate is None, category
        assert resolution.rate_kind is None, category
        assert resolution.reason != "", category


def test_eu_iva_non_derivable_reasons_are_advisory_not_filing_certainty() -> None:
    """EU IVA / reverse-charge reasons must not read like legal filing certainty."""
    cases: tuple[tuple[IvaCategory, tuple[str, ...]], ...] = (
        (
            IvaCategory.DOMESTIC_REVERSE_CHARGE,
            ("potential domestic reverse charge", "verify the operation evidence", "supply the self-assessed"),
        ),
        (
            IvaCategory.INTRA_COMMUNITY_SUPPLY,
            ("potential intra-community supply", "verify the customer IVA ID", "reporting evidence"),
        ),
        (
            IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            ("potential intra-community acquisition", "verify the acquisition evidence", "self-assessed base"),
        ),
        (
            IvaCategory.INTRA_COMMUNITY_TRIANGULATION,
            ("potential intra-community triangulation", "verify the triangulation conditions"),
        ),
    )

    for category, required_fragments in cases:
        resolution = resolve_category_rate(category, on_date=_ON_DATE)

        assert resolution.derivable is False, category
        assert all(fragment in resolution.reason for fragment in required_fragments), category
        assert "exempt with right to deduct" not in resolution.reason, category
        assert "operator confirms" not in resolution.reason, category


def test_export_non_derivable_reasons_remain_advisory_and_evidence_oriented() -> None:
    cases: tuple[tuple[IvaCategory, tuple[str, ...]], ...] = (
        (
            IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
            ("potential export", "verify the export evidence", "before treating it as zero-rated"),
        ),
        (
            IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
            ("potential operation assimilated to an export", "verify the qualifying", "before treating it as exempt"),
        ),
    )

    for category, required_fragments in cases:
        resolution = resolve_category_rate(category, on_date=_ON_DATE)

        assert resolution.derivable is False, category
        assert all(fragment in resolution.reason for fragment in required_fragments), category
        assert "operator confirms" not in resolution.reason, category
        assert "filing certainty" not in resolution.reason, category


def test_every_iva_category_is_resolvable_without_raising() -> None:
    """The resolver covers the closed IvaCategory set with no KeyError."""
    for category in IvaCategory:
        resolution = resolve_category_rate(category, on_date=_ON_DATE)
        assert isinstance(resolution, IvaRateResolution)


def test_split_gross_at_21_pct_matches_worked_example() -> None:
    """121.00 at 21% inverse-splits to 100.00 base + 21.00 IVA."""
    base, iva = split_gross_at_rate(Decimal("121.00"), Decimal("0.21"))
    assert base == Decimal("100.00")
    assert iva == Decimal("21.00")
    assert base + iva == Decimal("121.00")


def test_split_gross_rounding_edge_case_reconstitutes_gross() -> None:
    """A rounding-residual gross still satisfies base + iva == gross to the cent."""
    gross = Decimal("100.00")
    base, iva = split_gross_at_rate(gross, Decimal("0.21"))
    # 100 / 1.21 = 82.6446... -> 82.64; iva = 100.00 - 82.64 = 17.36
    assert base == Decimal("82.64")
    assert iva == Decimal("17.36")
    assert base + iva == gross


def test_split_gross_at_zero_rate_yields_whole_base_and_zero_iva() -> None:
    """A zero rate puts the whole gross in the base with a zero IVA amount."""
    base, iva = split_gross_at_rate(Decimal("100.00"), Decimal("0"))
    assert base == Decimal("100.00")
    assert iva == Decimal("0.00")


def test_resolve_then_split_round_trips_for_general_rate() -> None:
    """The two primitives compose: resolve a fraction, split a gross with it."""
    resolution = resolve_category_rate(IvaCategory.DOMESTIC_GENERAL, on_date=_ON_DATE)
    assert resolution.rate is not None
    base, iva = split_gross_at_rate(Decimal("121.00"), resolution.rate)
    assert base == Decimal("100.00")
    assert iva == Decimal("21.00")


# ── the tier→value question is ambiguous while a temporary rate coexists ──
#
# RDL 4/2024 art. 1 (BOE-A-2024-12944) put a temporary rate on PART of the
# reduced and super-reducido tiers' supplies while the rest stayed on the
# ordinary rate, so between those dates the tier does not have "a" rate. Which
# one applies turns on WHAT was supplied, and no bundled AEAT surface carries
# that goods axis. The dates below are the registry's own effective windows.
_SUPER_REDUCED_COEXISTENCE = date(2024, 10, 15)  # 4 % ordinary, 2 % temporary
_REDUCED_COEXISTENCE = date(2024, 8, 15)  # 10 % ordinary, 5 % temporary


def test_ambiguous_tier_refuses_instead_of_returning_the_ordinary_rate() -> None:
    """A tier carrying two in-force rates must not answer with the ordinary one.

    Returning 4 % for a super-reducido line that RDL 4/2024 art. 1 actually
    taxed at 2 % would split the gross at the wrong rate, understating the base
    and OVERSTATING the cuota — an over-declaration no gate in this tree
    watches. The contract this module states for itself is that it never
    guesses a number, so the honest answer is the non-derivable one.
    """
    for category, on_date in (
        (IvaCategory.DOMESTIC_SUPER_REDUCED, _SUPER_REDUCED_COEXISTENCE),
        (IvaCategory.DOMESTIC_REDUCED, _REDUCED_COEXISTENCE),
    ):
        resolution = resolve_category_rate(category, on_date=on_date)
        assert resolution.derivable is False, category
        assert resolution.rate is None, category
        # The refusal names the competing rates so the operator can choose,
        # rather than reporting a bare "not derivable" for a tier that
        # plainly has a rate.
        assert "more than one rate" in resolution.reason, category


def test_ambiguity_refusal_is_scoped_to_the_window_and_the_moved_tiers() -> None:
    """Only the affected tiers, and only inside the statute's own window.

    The guard must not become a blanket refusal: the general tier never moved,
    and both tiers resolve normally on either side of the temporary window. A
    refusal that over-fired here would block ordinary classification for every
    reduced-rate supply in the country.
    """
    # The general tier is untouched on the very dates the others are ambiguous.
    for on_date in (_SUPER_REDUCED_COEXISTENCE, _REDUCED_COEXISTENCE):
        general = resolve_category_rate(IvaCategory.DOMESTIC_GENERAL, on_date=on_date)
        assert general.derivable is True
        assert general.rate == Decimal("0.21")

    # After every temporary window lapses, both tiers resolve again.
    for category, expected in (
        (IvaCategory.DOMESTIC_SUPER_REDUCED, Decimal("0.04")),
        (IvaCategory.DOMESTIC_REDUCED, Decimal("0.10")),
    ):
        resolution = resolve_category_rate(category, on_date=date(2025, 6, 1))
        assert resolution.derivable is True, category
        assert resolution.rate == expected, category

    # The tiers moved on DIFFERENT dates, so "inside the window" is per tier.
    # Super-reducido only ever coexisted Oct-Dec 2024 (RD-ley 4/2024's 2 %), so
    # it still resolves in March 2024.
    super_reduced = resolve_category_rate(IvaCategory.DOMESTIC_SUPER_REDUCED, on_date=date(2024, 3, 1))
    assert super_reduced.derivable is True
    assert super_reduced.rate == Decimal("0.04")

    # Reducido is different, and this test previously asserted otherwise on a
    # false premise. RDL 20/2022 art. 72 put seed oils and pasta at 5 % from
    # 2023-01-01 to 2024-06-30 while the rest of the tier stayed at 10 %, so
    # March 2024 is INSIDE a coexistence window, not before one. The earlier
    # assertion only held because those rate rows were absent from the registry;
    # the tier was ambiguous in law the whole time and the table could not say so.
    reduced = resolve_category_rate(IvaCategory.DOMESTIC_REDUCED, on_date=date(2024, 3, 1))
    assert reduced.derivable is False, (
        "reducido cannot be derived in March 2024: 5 % and 10 % both applied, to "
        "different goods, and no bundled surface carries the goods axis"
    )
