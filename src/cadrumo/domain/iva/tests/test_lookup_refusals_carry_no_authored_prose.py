"""Every IVA lookup refusal must reach the operator as a key, never as English.

The defect this module pins is invisible to a key-and-context assertion. A
refusal constructed as ``Error("some English sentence", translated_message=key)``
resolves through :func:`cadrumo.core.errors.resolve_error_message` to exactly
the same localised text as one constructed with the key alone, because the
resolver prefers the key. The English does not disappear: ``str(exc)`` prefers
the positional argument, so it reaches tracebacks, logs and every boundary that
renders the exception directly -- in Catalan, Spanish and Hungarian sessions as
much as in English ones.

So the assertion here is an ABSENCE, not an identity: with no authored
positional message, ``str(exc)`` degrades to the key itself. Re-adding a
sentence beside the key breaks these tests immediately, while leaving every
key-and-context assertion in the suite green.

The three catalogue refusals are driven against catalogues built from the real
frozen :class:`cadrumo.domain.iva.IvaRegulation` and
:class:`cadrumo.domain.iva.IvaCitation` models rather than the bundled one,
because the bundled catalogue is complete by construction and therefore cannot
reach the three conditions at all. These are real domain aggregates with real
validation, not stand-ins for one.
"""

from __future__ import annotations

from datetime import date

import pytest

from .. import (
    EUMemberState,
    IvaCatalogue,
    IvaCatalogueError,
    IvaCategory,
    IvaCategoryNotFoundError,
    IvaCitation,
    IvaRateKind,
    IvaRateNotFoundError,
    IvaRegulation,
    cite,
    lookup_rate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ON = date(2025, 6, 1)
#: A category the constructed catalogues deliberately leave out or mis-ground.
_PROBE_CATEGORY = IvaCategory.DOMESTIC_GENERAL


def _empty_catalogue() -> IvaCatalogue:
    """Return a real, valid catalogue that simply codifies nothing."""
    return IvaCatalogue(regulations={})


def _catalogue_without_legal_basis() -> IvaCatalogue:
    """Return a catalogue whose probe category is a citation-free sentinel."""
    return IvaCatalogue(
        regulations={
            _PROBE_CATEGORY: IvaRegulation(
                category=_PROBE_CATEGORY,
                requires_reverse_charge=False,
                requires_supplier_iva_id=False,
                manual_references=(),
                citations=(),
                notes="classifier sentinel; codifies no tax treatment",
                legal_basis_exempt=True,
            ),
        },
    )


def _catalogue_citing_an_unregistered_reference() -> IvaCatalogue:
    """Return a catalogue citing a well-formed id no legal catalogue carries."""
    return IvaCatalogue(
        regulations={
            _PROBE_CATEGORY: IvaRegulation(
                category=_PROBE_CATEGORY,
                requires_reverse_charge=False,
                requires_supplier_iva_id=False,
                manual_references=(),
                citations=(
                    IvaCitation(
                        legal_reference="ley-37-1992:art-90-uno-absent-from-registry",
                        quoted_text="El impuesto se exigirá al tipo del 21 por ciento.",
                        valid_from=date(2022, 1, 1),
                        valid_to=date(2026, 12, 31),
                    ),
                ),
                notes="",
                legal_basis_exempt=False,
            ),
        },
    )


def test_unregistered_member_state_refusal_carries_no_authored_sentence() -> None:
    """XI is absent from the rate table entirely."""
    with pytest.raises(IvaRateNotFoundError) as caught:
        lookup_rate(EUMemberState.XI, IvaRateKind.GENERAL, _ON)

    assert str(caught.value) == "errors.iva.rate_member_state_unregistered"


def test_unmatched_tier_refusal_carries_no_authored_sentence() -> None:
    """Denmark is in the table but carries no reducido tier."""
    with pytest.raises(IvaRateNotFoundError) as caught:
        lookup_rate(EUMemberState.DK, IvaRateKind.REDUCED, _ON)

    assert str(caught.value) == "errors.error.error_financial_iva_rate_not_found"


def test_cite_without_catalogue_or_date_carries_no_authored_sentence() -> None:
    """Neither an explicit catalogue nor an effective date was supplied."""
    with pytest.raises(IvaCatalogueError) as caught:
        cite(_PROBE_CATEGORY)

    assert str(caught.value) == "errors.iva.cite_requires_catalogue_or_date"


def test_missing_category_refusal_carries_no_authored_sentence() -> None:
    """The catalogue resolves but does not codify the requested category."""
    with pytest.raises(IvaCategoryNotFoundError) as caught:
        cite(_PROBE_CATEGORY, catalogue=_empty_catalogue())

    assert str(caught.value) == "errors.error.error_financial_iva_category_not_found"


def test_absent_legal_basis_refusal_carries_no_authored_sentence() -> None:
    """The category is codified but deliberately carries no citation."""
    with pytest.raises(IvaCatalogueError) as caught:
        cite(_PROBE_CATEGORY, catalogue=_catalogue_without_legal_basis())

    assert str(caught.value) == "errors.iva.category_has_no_legal_basis"


def test_unregistered_legal_reference_refusal_carries_no_authored_sentence() -> None:
    """The citation names an id the registry legal catalogue does not carry."""
    with pytest.raises(IvaCatalogueError) as caught:
        cite(_PROBE_CATEGORY, catalogue=_catalogue_citing_an_unregistered_reference())

    assert str(caught.value) == "errors.iva.citation_legal_reference_absent"


def test_every_lookup_refusal_key_is_distinct() -> None:
    """A copy-paste must not collapse two conditions onto one key.

    Six conditions, six keys. Two of them deliberately reuse the registered
    :class:`~cadrumo.core.errors.ErrorCode` message keys for their classes,
    which is correct where the class has exactly one operator meaning; the
    remaining four needed their own because their classes carry several.
    """
    keys = (
        "errors.iva.rate_member_state_unregistered",
        "errors.error.error_financial_iva_rate_not_found",
        "errors.iva.cite_requires_catalogue_or_date",
        "errors.error.error_financial_iva_category_not_found",
        "errors.iva.category_has_no_legal_basis",
        "errors.iva.citation_legal_reference_absent",
    )
    assert len(set(keys)) == len(keys)


@pytest.mark.parametrize(
    "key",
    (
        "errors.iva.rate_member_state_unregistered",
        "errors.error.error_financial_iva_rate_not_found",
        "errors.iva.cite_requires_catalogue_or_date",
        "errors.error.error_financial_iva_category_not_found",
        "errors.iva.category_has_no_legal_basis",
        "errors.iva.citation_legal_reference_absent",
    ),
)
def test_every_lookup_refusal_key_resolves_to_real_text(key: str) -> None:
    """A key that never landed in the catalogue must fail, not render bare.

    ``tr`` falls back to the key itself when no translation exists, so a
    refusal whose key was never authored looks identical to a migrated one at
    the exception boundary. Resolving each key and requiring the result to
    differ from the key is what separates the two.
    """
    from ....core.config import override_settings
    from ....core.i18n import tr

    for language in ("en", "es", "ca", "hu"):
        with override_settings(cadrumo_output_language=language):
            rendered = tr(key)
        assert rendered != key, f"{key} is unauthored in {language}"
        assert rendered.strip()
