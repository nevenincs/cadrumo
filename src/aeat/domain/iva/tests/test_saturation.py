"""Real-behavior tests for the IVA saturation primitives.

Covers :func:`aeat.domain.iva.resolve_category_rate` (category→rate-fraction
resolution against the registry rate authority, and the not-derivable
surfacing for every non-domestic category) and
:func:`aeat.domain.iva.split_gross_at_rate` (the inverse gross→base/IVA split
with AEAT half-up rounding). Expected rate fractions are asserted against the
grounded ``rates.toml`` values (Spain general 21 / reduced 10 / super-reduced 4
/ zero 0), not hand-computed from a formula under test.

Authority: ``llm-ledger-classification-design``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .. import (
    IvaCategory,
    IvaRateKind,
    IvaRateResolution,
    resolve_category_rate,
    split_gross_at_rate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ON_DATE = date(2025, 6, 1)


@pytest.mark.parametrize(
    ("category", "expected_rate", "expected_kind"),
    [
        (IvaCategory.DOMESTIC_GENERAL_21, Decimal("0.21"), IvaRateKind.GENERAL),
        (IvaCategory.DOMESTIC_REDUCED_10, Decimal("0.10"), IvaRateKind.REDUCED),
        (IvaCategory.DOMESTIC_SUPER_REDUCED_4, Decimal("0.04"), IvaRateKind.SUPER_REDUCED),
    ],
)
def test_domestic_positive_rate_resolves_to_registry_fraction(
    category: IvaCategory,
    expected_rate: Decimal,
    expected_kind: IvaRateKind,
) -> None:
    """Domestic general/reduced/super-reduced resolve to the grounded fraction."""
    resolution = resolve_category_rate(category, on_date=_ON_DATE)
    assert resolution.derivable is True
    assert resolution.reason == ""
    assert resolution.rate_kind is expected_kind
    assert resolution.rate is not None
    assert resolution.rate == expected_rate


@pytest.mark.parametrize(
    ("category", "expected_kind"),
    [
        (IvaCategory.DOMESTIC_ZERO, IvaRateKind.ZERO),
        (IvaCategory.DOMESTIC_EXEMPT, IvaRateKind.EXEMPT),
    ],
)
def test_zero_and_exempt_derive_zero_rate(category: IvaCategory, expected_kind: IvaRateKind) -> None:
    """Zero-rated and exempt categories derive a derivable zero fraction."""
    resolution = resolve_category_rate(category, on_date=_ON_DATE)
    assert resolution.derivable is True
    assert resolution.rate == Decimal("0")
    assert resolution.rate_kind is expected_kind
    assert resolution.reason == ""


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
    IvaCategory.OPERACION_NO_SUJETA,
    IvaCategory.ERRONEOUS_INVOICE,
    IvaCategory.UNKNOWN,
]


@pytest.mark.parametrize("category", _NON_DERIVABLE_CATEGORIES)
def test_non_domestic_categories_surface_not_derivable(category: IvaCategory) -> None:
    """Every non-derivable category returns derivable=False with a reason, no rate."""
    resolution = resolve_category_rate(category, on_date=_ON_DATE)
    assert resolution.derivable is False
    assert resolution.rate is None
    assert resolution.rate_kind is None
    assert resolution.reason != ""


@pytest.mark.parametrize(
    ("category", "required_fragments"),
    [
        (
            IvaCategory.DOMESTIC_REVERSE_CHARGE,
            ("potential domestic reverse charge", "verify the operation evidence", "supply the self-assessed"),
        ),
        (
            IvaCategory.INTRA_COMMUNITY_SUPPLY,
            ("potential intra-community supply", "verify the customer VAT ID", "reporting evidence"),
        ),
        (
            IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            ("potential intra-community acquisition", "verify the acquisition evidence", "self-assessed base"),
        ),
        (
            IvaCategory.INTRA_COMMUNITY_TRIANGULATION,
            ("potential intra-community triangulation", "verify the triangulation conditions"),
        ),
    ],
)
def test_eu_vat_non_derivable_reasons_are_advisory_not_filing_certainty(
    category: IvaCategory,
    required_fragments: tuple[str, ...],
) -> None:
    """EU VAT / reverse-charge reasons must not read like legal filing certainty."""
    resolution = resolve_category_rate(category, on_date=_ON_DATE)

    assert resolution.derivable is False
    assert all(fragment in resolution.reason for fragment in required_fragments)
    assert "exempt with right to deduct" not in resolution.reason
    assert "operator confirms" not in resolution.reason


@pytest.mark.parametrize(
    ("category", "required_fragments"),
    [
        (
            IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
            ("potential export", "verify the export evidence", "before treating it as zero-rated"),
        ),
        (
            IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
            ("potential operation assimilated to an export", "verify the qualifying", "before treating it as exempt"),
        ),
    ],
)
def test_export_non_derivable_reasons_remain_advisory_and_evidence_oriented(
    category: IvaCategory,
    required_fragments: tuple[str, ...],
) -> None:
    resolution = resolve_category_rate(category, on_date=_ON_DATE)

    assert resolution.derivable is False
    assert all(fragment in resolution.reason for fragment in required_fragments)
    assert "operator confirms" not in resolution.reason
    assert "filing certainty" not in resolution.reason


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
    resolution = resolve_category_rate(IvaCategory.DOMESTIC_GENERAL_21, on_date=_ON_DATE)
    assert resolution.rate is not None
    base, iva = split_gross_at_rate(Decimal("121.00"), resolution.rate)
    assert base == Decimal("100.00")
    assert iva == Decimal("21.00")
