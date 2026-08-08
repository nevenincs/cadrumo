"""Resolve the regulatory values an invoice-reading prompt enumerates.

The reading prompt names Spanish IVA rates, statutory retención rates, the
categories of document that print no tax at all, and the regime mentions an
issuer is obliged to print. Every one of those is a regulatory value, so
``aeat-registry-authority-flow`` puts its home in the registry rather than in the
module that happens to consume it -- they are versioned by filing year, and a
copy taken anywhere else bakes one year's law into that call site.

**Why the resolution lives HERE and not beside the prompt.** The prompt is
rendered in the ``llm`` package, which is an adapter over a model transport. An
adapter that reaches into :mod:`~domain.iva` and :mod:`~domain.transactions` to
look up a rate has made itself a second consumer of the calculation authorities,
and the hexagonal direction this project keeps says the application layer
resolves and the adapter receives. So the resolution is done once here and
handed down as ONE typed value object; the renderer substitutes what it is given
and can no longer reach an authority at all.

That is a stronger guarantee than "we remembered not to write ``21``". A literal
in a prompt is the least-audited literal in the codebase -- nothing type-checks
it, no gate reads it, and a stale rate keeps steering a reading model silently.
Removing the renderer's *access* to the authorities means the only rate it can
print is one this function resolved.

**Every overlapping record, not the one in force on a chosen day.** A period is a
span, and RD-ley 4/2024 stepped part of the reducido and super-reducido tiers
mid-year. Reading the table on one date inside such a period would omit a rate
that documents dated inside the same period genuinely print, and the prompt would
then be telling a model that a rate it can see on the page is not registered.

See Also:
    :class:`~core.Period`
        The law-determined coordinate rates are resolved against. It is the
        caller's ``(filing_year, code)``, never a stored revision id fed back
        into resolution.
    :class:`~domain.iva.IvaCategory`
        The closed set the no-printed-tax vocabulary is derived from.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG, Period
from ...domain.iva import IvaCategory

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "InvoiceExtractionAuthorityValues",
    "default_invoice_extraction_period",
    "resolve_invoice_extraction_authority_values",
]

_PCT_SCALE: Decimal = Decimal("100")


class InvoiceExtractionAuthorityValues(BaseModel):
    """Every regulatory value one compiled reading prompt enumerates.

    Carried as one frozen object rather than as loose arguments so the renderer
    receives a single thing it can neither widen nor supplement, and so a
    provenance stamp can answer "under which values was this document read?"
    without re-parsing the rendered prose.

    Attributes:
        period: The filing period the values were resolved for.
        iva_rate_pcts: Every registered Spanish IVA percentage whose effective
            window overlaps :attr:`period`, ascending. A percentage, because a
            document prints a percentage.
        retencion_rate_pcts: Every distinct RIRPF art. 95 retención percentage,
            ascending.
        no_printed_tax_categories: The :class:`~domain.iva.IvaCategory` members
            whose documents carry no tax figure at all. Typed members rather
            than rendered text, so the renderer owns presentation and this
            object stays the closed-set fact.
        regime_legend_phrases: The mentions RD 1619/2012 art. 6.1 obliges an
            issuer to print, in declaration order and verbatim.
    """

    model_config = STRICT_FROZEN_CONFIG

    period: Period
    iva_rate_pcts: tuple[Decimal, ...] = Field(min_length=1)
    retencion_rate_pcts: tuple[Decimal, ...] = Field(min_length=1)
    no_printed_tax_categories: tuple[IvaCategory, ...] = Field(min_length=1)
    regime_legend_phrases: tuple[str, ...] = Field(min_length=1)


def default_invoice_extraction_period() -> Period:
    """Return the period a reader falls back to when the caller names none.

    A document arriving for reading may not yet be bound to a filing period, so
    the reader needs a coordinate to resolve values against. The current civil
    year's annual period (``0A``) is the honest default: it is derived from the
    canonical civil-date authority (:func:`~core.time.today_madrid`) rather than
    guessed, and it spans the whole year, so its enumeration is the UNION of
    every value in force at any point in it -- never a mid-year window that would
    omit a rate a document legitimately prints.

    A caller that knows the document's period passes it explicitly and gets a
    narrower, more useful enumeration.

    Returns:
        :class:`~core.Period`: The current civil year's annual period.
    """
    from ...core.time import today_madrid

    return Period.from_year_and_code(today_madrid().year, "0A")


def _overlapping_iva_rate_pcts(period: Period) -> tuple[Decimal, ...]:
    """Return every registered Spanish IVA percentage overlapping ``period``.

    The authority is read at CALL time, not bound at import. A module-level
    ``from ... import load_iva_rate_table`` captures the function object once, so
    a registry change reaching the authority afterwards would not reach this
    resolver -- the compiled prompt would keep enumerating the rates that were in
    force when the process started. The same import-time-snapshot trap already
    caught the template scanner in this feature once.
    """
    from ...domain.iva import EUMemberState, load_iva_rate_table

    start = period.start_date
    end = period.end_date
    overlapping = {
        record.pct
        for record in load_iva_rate_table().get(EUMemberState.ES, ())
        if record.effective_from <= end and (record.effective_until is None or record.effective_until >= start)
    }
    return tuple(sorted(overlapping))


def _as_pcts(fractions: Iterable[Decimal]) -> tuple[Decimal, ...]:
    """Return ``fractions`` as ascending percentages.

    The retención parameters are stored as fractions (``0.15``) because that is
    how a transaction carries one; a printed invoice states the percentage, so
    the prompt is given percentages and the conversion happens once, here.
    """
    return tuple(sorted(fraction * _PCT_SCALE for fraction in fractions))


def resolve_invoice_extraction_authority_values(*, period: Period) -> InvoiceExtractionAuthorityValues:
    """Resolve every regulatory value the reading prompt for ``period`` enumerates.

    Args:
        period: The filing period whose in-force values the prompt should
            enumerate. It is the caller's law-determined coordinate; nothing
            stored is fed back into the resolution.

    Returns:
        :class:`InvoiceExtractionAuthorityValues`: The resolved values, ready to
        hand to a renderer that holds no authority of its own.

    Raises:
        PeriodError: When ``period`` carries no calendar span, so no rate window
            can be resolved against it.
        IvaCatalogueError: When the bundled IVA rate registry cannot be read.
        TransactionValidationError: When the retención parameters cannot be read.
    """
    from ...domain.iva import NO_PRINTED_TAX_IVA_CATEGORIES, regime_legend_phrases
    from ...domain.transactions import statutory_activity_retencion_rates

    return InvoiceExtractionAuthorityValues(
        period=period,
        iva_rate_pcts=_overlapping_iva_rate_pcts(period),
        retencion_rate_pcts=_as_pcts(statutory_activity_retencion_rates()),
        no_printed_tax_categories=tuple(sorted(NO_PRINTED_TAX_IVA_CATEGORIES, key=lambda member: member.value)),
        regime_legend_phrases=regime_legend_phrases(),
    )
