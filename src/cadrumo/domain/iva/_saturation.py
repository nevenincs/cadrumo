"""Grounded saturation primitives for the :mod:`cadrumo.domain.iva` subpackage.

Two reusable primitives that let a caller turn a selected
:class:`IvaCategory` and a transaction gross into the regulated euro
substrate (rate, taxable base, IVA amount) **without ever guessing a
number**:

* :func:`resolve_category_rate` maps an :class:`IvaCategory` to its
  :class:`IvaRateKind` and looks the applicable rate up via
  :func:`cadrumo.domain.iva.lookup_rate`, returning it as a decimal
  *fraction* (``Decimal("0.21")``) wrapped in a typed
  :class:`IvaRateResolution`. Domestic general / reduced / super-reduced
  derive a positive rate; domestic zero and exempt derive ``0``; every
  category with no simple derivable positive domestic rate
  (intra-community, export, reverse-charge, recargo, import,
  régimen simplificado, no-sujeta, erroneous, unknown) returns a
  ``derivable=False`` resolution carrying an explicit operator-facing
  reason — never a fabricated rate.

  A domestic tier ALSO refuses while a temporary statute has it carrying
  two rates at once. Asking a tier for "its" rate is well defined only
  while the tier has one: RDL 4/2024 art. 1 moved part of the reduced and
  super-reducido supplies onto a temporary rate and left the rest on the
  ordinary one, and which of the two applies turns on WHAT was supplied —
  an axis no bundled AEAT surface carries. Answering with the ordinary
  rate there would split a gross at the wrong rate, understating the base
  and overstating the cuota, so the ambiguity is surfaced rather than
  resolved by guess. :func:`~cadrumo.domain.iva.rate_kinds_for_declared_rate`
  is the well-defined inverse for a caller that already holds a rate.

* :func:`split_gross_at_rate` performs the inverse split of a gross at a
  rate fraction into ``(taxable_base, iva_amount)`` quantised with the
  AEAT-mandated :func:`cadrumo.core.money.round_to_cents` (ROUND_HALF_UP).

The split formula is the canonical inverse of an IVA-inclusive gross:
``base = round_to_cents(gross / (1 + rate))`` and
``iva = round_to_cents(gross - base)``. Quantising the base first and
deriving the IVA as the remainder guarantees ``base + iva == gross`` to
the cent regardless of the rounding residual, which is exactly the
invariant the :class:`cadrumo.domain.transactions.Transaction` model
enforces.

The rate values
are grounded in ``registry/aeat/iva/rates.toml`` (Spain general 21 /
reduced 10 / super-reduced 4 / zero 0; LIVA art. 90/91, year-scoped).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.money import round_to_cents
from ._lookup import coexisting_tier_rates, lookup_rate
from ._schema import EUMemberState, IvaCategory, IvaRateKind, IvaRateRecord
from .errors import IvaRateNotFoundError

_ONE_HUNDRED = Decimal("100")
_ONE = Decimal("1")
_ZERO = Decimal("0")

# Spanish domestic categories whose rate is a single registry rate tier.
# Maps the operator-/LLM-selected IvaCategory onto the IvaRateKind whose
# registry record carries the authoritative percentage. Zero and exempt
# both resolve to a zero fraction (no positive IVA), so they are handled
# explicitly below rather than via a positive lookup.
_CATEGORY_TO_RATE_KIND: dict[IvaCategory, IvaRateKind] = {
    IvaCategory.DOMESTIC_GENERAL: IvaRateKind.GENERAL,
    IvaCategory.DOMESTIC_REDUCED: IvaRateKind.REDUCED,
    IvaCategory.DOMESTIC_SUPER_REDUCED: IvaRateKind.SUPER_REDUCED,
    IvaCategory.DOMESTIC_ZERO: IvaRateKind.ZERO,
    IvaCategory.DOMESTIC_EXEMPT: IvaRateKind.EXEMPT,
}

# Per-category explanation for every IvaCategory whose IVA rate cannot be
# derived from a single Spanish domestic rate tier. The reason is
# operator-facing: it states why the system declines to guess and what the
# operator must supply.
_NON_DERIVABLE_REASONS: dict[IvaCategory, str] = {
    IvaCategory.DOMESTIC_NOT_SUBJECT: (
        "not subject to Spanish IVA (no devengo); no rate is derivable here, "
        "but this reason does not confirm the filing treatment"
    ),
    IvaCategory.OPERACION_NO_SUJETA: (
        "not subject to Spanish IVA (no devengo); no rate is derivable here, "
        "but this reason does not confirm the filing treatment"
    ),
    IvaCategory.REAGP_COMPENSATION: (
        "régimen especial de la agricultura, ganadería y pesca: no IVA rate is "
        "derivable here because none is charged — LIVA art. 130.Cinco sets a "
        "compensación a tanto alzado of 12 % of the sale price for explotaciones "
        "agrícolas o forestales and 10,5 % for ganaderas o pesqueras, which is "
        "not an IVA tipo; supply the compensación from the self-issued document "
        "LIVA art. 134.Tres requires"
    ),
    IvaCategory.DOMESTIC_REVERSE_CHARGE: (
        "potential domestic reverse charge (inversión del sujeto pasivo): "
        "no rate is derivable here; verify the operation evidence and supply "
        "the self-assessed base and cuota explicitly"
    ),
    IvaCategory.INTRA_COMMUNITY_SUPPLY: (
        "potential intra-community supply: no Spanish rate is derivable here; "
        "verify the customer IVA ID, cross-border transport, and reporting "
        "evidence before treating it as exempt"
    ),
    IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE: (
        "potential intra-community acquisition under reverse charge: no rate "
        "is derivable here; verify the acquisition evidence and supply the "
        "self-assessed base and cuota explicitly"
    ),
    IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY: (
        "potential intra-community service supply: no Spanish rate is "
        "derivable here because art. 69.Uno.1.o locates the service where the "
        "recipient is established; verify the customer IVA ID and that no "
        "art. 70 regla especial brings the service back into the TAI"
    ),
    IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE: (
        "potential intra-community service acquisition under reverse charge: "
        "no rate is derivable here; verify the acquisition evidence and supply "
        "the self-assessed base and cuota explicitly"
    ),
    IvaCategory.INTRA_COMMUNITY_TRIANGULATION: (
        "potential intra-community triangulation: no Spanish rate is derivable "
        "here; verify the triangulation conditions and reporting evidence"
    ),
    IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED: (
        "potential export to a third country: no domestic rate is derivable "
        "here; verify the export evidence before treating it as zero-rated"
    ),
    IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED: (
        "potential operation assimilated to an export: no domestic rate is "
        "derivable here; verify the qualifying ship, aircraft, provisioning, "
        "or related service facts before treating it as exempt"
    ),
    IvaCategory.IMPORT_THIRD_COUNTRY: (
        "import from a third country: IVA is assessed at customs against the "
        "import base — derivation is left to the operator"
    ),
    IvaCategory.RECARGO_EQUIVALENCIA: (
        "recargo de equivalencia: a surcharge on top of the IVA rate that "
        "varies by product tier — derivation is left to the operator"
    ),
    IvaCategory.REGIMEN_SIMPLIFICADO: (
        "régimen simplificado: IVA is determined by activity modules, not by "
        "an inverse split of the gross — derivation is left to the operator"
    ),
    IvaCategory.ERRONEOUS_INVOICE: (
        "erroneous invoice: the line is flagged for correction; no rate is derivable until the operator resolves it"
    ),
    IvaCategory.UNKNOWN: (
        "unknown IVA situation: the category has not been determined — no rate "
        "can be derived until the operator selects a concrete category"
    ),
}


def _ambiguous_tier_reason(
    rate_kind: IvaRateKind,
    coexisting: tuple[IvaRateRecord, ...],
    on_date: date,
) -> str:
    """Word the refusal for a tier carrying more than one rate on ``on_date``.

    Names every rate actually in force so the operator can pick, rather than
    reporting a bare "not derivable" for a tier that plainly has a rate.
    """
    ordinary = ", ".join(f"{record.pct} %" for record in _ordinary_tier_rates(rate_kind, on_date))
    temporary = ", ".join(f"{record.pct} %" for record in coexisting)
    return (
        f"the {rate_kind.value.replace('_', '-')} tier carries more than one rate on "
        f"{on_date.isoformat()}: {ordinary or 'its ordinary rate'} for most supplies and "
        f"{temporary} for the supplies a temporary statute moved. Which one applies turns on "
        "WHAT was supplied, an axis no bundled AEAT surface carries, so the base and cuota "
        "cannot be derived from the category alone -- record the rate (or the base and cuota) "
        "from the invoice"
    )


def _ordinary_tier_rates(rate_kind: IvaRateKind, on_date: date) -> tuple[IvaRateRecord, ...]:
    """Return the tier's ordinary in-force rate, for wording the refusal only."""
    try:
        return (lookup_rate(EUMemberState.ES, rate_kind, on_date),)
    except IvaRateNotFoundError:
        return ()


class IvaRateResolution(BaseModel):
    """Typed outcome of resolving an :class:`IvaCategory` to a rate fraction.

    A resolution is *self-documenting*: it never silently substitutes a
    fabricated rate for a category the system cannot ground. When
    :attr:`derivable` is ``True`` the :attr:`rate` carries the applicable
    rate as a decimal fraction in ``[0, 1]`` (e.g. ``Decimal("0.21")``;
    ``Decimal("0")`` for zero-rated and exempt categories). When
    :attr:`derivable` is ``False`` the :attr:`rate` is ``None`` and
    :attr:`reason` states why the operator must complete the field.

    Attributes:
        category: The :class:`IvaCategory` that was resolved.
        derivable: ``True`` when a Spanish domestic rate fraction was
            derived, ``False`` when the category has no simple derivable
            domestic rate and the operator must complete it.
        rate: The applicable IVA rate as a decimal fraction in ``[0, 1]``
            when :attr:`derivable`, else ``None``.
        rate_kind: The :class:`IvaRateKind` the category maps to when
            :attr:`derivable`, else ``None``.
        reason: An operator-facing explanation present only when the rate
            is not derivable; the empty string otherwise.
    """

    model_config = STRICT_FROZEN_CONFIG

    category: IvaCategory = Field(description="The IvaCategory that was resolved.")
    derivable: bool = Field(description="Whether a domestic rate fraction was derived.")
    rate: Decimal | None = Field(
        default=None,
        ge=_ZERO,
        le=_ONE,
        description="Applicable IVA rate as a decimal fraction in [0, 1], or None.",
    )
    rate_kind: IvaRateKind | None = Field(
        default=None,
        description="The IvaRateKind the category maps to, or None.",
    )
    reason: str = Field(
        default="",
        description="Operator-facing reason when the rate is not derivable.",
    )


def resolve_category_rate(category: IvaCategory, *, on_date: date) -> IvaRateResolution:
    """Resolve an :class:`IvaCategory` to its Spanish IVA rate fraction.

    Maps ``category`` to its :class:`IvaRateKind` and looks the applicable
    rate up via :func:`cadrumo.domain.iva.lookup_rate` for
    :attr:`EUMemberState.ES` on ``on_date``, returning the percentage as a
    decimal *fraction* (``IvaRateRecord.pct / 100``). Domestic
    general / reduced / super-reduced derive a positive fraction; domestic
    zero and exempt derive ``Decimal("0")``. Every category with no simple
    derivable positive domestic rate returns a ``derivable=False``
    resolution carrying an operator-facing reason — the system never
    guesses a rate for those.

    Args:
        category: The selected IVA category to resolve.
        on_date: The effective date used to resolve the registry rate.

    Returns:
        A typed :class:`IvaRateResolution`. ``derivable`` is ``True`` with a
        ``rate`` fraction for domestic categories; ``False`` with a
        ``reason`` for every non-derivable category.

    Raises:
        IvaRateNotFoundError: If a domestic category maps to a rate kind
            that the registry has no record for on ``on_date`` (a registry
            gap, not a category-shape problem).
    """
    rate_kind = _CATEGORY_TO_RATE_KIND.get(category)
    if rate_kind is None:
        return IvaRateResolution(
            category=category,
            derivable=False,
            rate=None,
            rate_kind=None,
            reason=_NON_DERIVABLE_REASONS[category],
        )
    coexisting = coexisting_tier_rates(EUMemberState.ES, rate_kind, on_date)
    if coexisting:
        return IvaRateResolution(
            category=category,
            derivable=False,
            rate=None,
            rate_kind=rate_kind,
            reason=_ambiguous_tier_reason(rate_kind, coexisting, on_date),
        )
    if rate_kind in (IvaRateKind.ZERO, IvaRateKind.EXEMPT):
        return IvaRateResolution(
            category=category,
            derivable=True,
            rate=_ZERO,
            rate_kind=rate_kind,
            reason="",
        )
    record = lookup_rate(EUMemberState.ES, rate_kind, on_date)
    return IvaRateResolution(
        category=category,
        derivable=True,
        rate=record.pct / _ONE_HUNDRED,
        rate_kind=rate_kind,
        reason="",
    )


def split_gross_at_rate(gross: Decimal, rate: Decimal) -> tuple[Decimal, Decimal]:
    """Inverse-split an IVA-inclusive gross into ``(taxable_base, iva_amount)``.

    Computes the IVA-exclusive base and the IVA charged from an
    IVA-inclusive gross at ``rate`` (a decimal *fraction*, e.g.
    ``Decimal("0.21")``), quantising with the AEAT-mandated
    :func:`cadrumo.core.money.round_to_cents` (ROUND_HALF_UP). The base is
    quantised first and the IVA is taken as the quantised remainder
    (``gross - base``), so ``taxable_base + iva_amount == gross`` holds to
    the cent regardless of the rounding residual.

    A ``rate`` of ``0`` (zero-rated or exempt) yields the whole gross as
    the base and a zero IVA amount.

    Args:
        gross: The IVA-inclusive gross amount. Expected non-negative (the
            caller passes ``abs(amount)`` for a signed transaction); a
            signed value is split as given.
        rate: The IVA rate as a decimal fraction in ``[0, 1]``.

    Returns:
        A ``(taxable_base, iva_amount)`` tuple, each quantised to euro
        cents, whose sum equals ``round_to_cents(gross)`` to the cent.
    """
    if rate == _ZERO:
        base = round_to_cents(gross)
        return base, round_to_cents(gross - base)
    base = round_to_cents(gross / (_ONE + rate))
    return base, round_to_cents(gross - base)


__all__ = [
    "IvaRateResolution",
    "resolve_category_rate",
    "split_gross_at_rate",
]
