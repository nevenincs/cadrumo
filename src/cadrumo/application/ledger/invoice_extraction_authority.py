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

from contextlib import suppress
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core.decimal.constants import HUNDRED, ZERO
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.iva.schema import IvaCategory

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = [
    "InvoiceExtractionAuthorityValues",
    "default_invoice_extraction_period",
    "resolve_invoice_extraction_authority_values",
]


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
    from ...core.time.clock import today_madrid

    return Period.from_year_and_code(today_madrid().year, "0A")


def _overlapping_iva_rate_pcts(
    period: Period,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[Decimal, ...]:
    """Return every registered Spanish IVA percentage overlapping ``period``.

    Every lookup goes through the retained typed IVA facade at the exact devengo
    day being considered. Iterating the period makes a mid-period transition
    visible without reading the legacy table or taking a consumer-local
    authority snapshot.
    """
    from ...domain.calculations.registry.iva_rate_kind_catalogue import resolve_iva_rate_kind_catalogue
    from ...domain.invoices.enums import iva_rate_percentage, resolve_iva_rate_slot
    from ...domain.iva.errors import IvaRateNotFoundError
    from ...domain.iva.lookup import coexisting_tier_rates, lookup_rate
    from ...domain.iva.schema import spanish_eu_member_state

    overlapping: set[Decimal] = set()
    on_date = period.start_date
    while on_date <= period.end_date:
        catalogue = resolve_iva_rate_kind_catalogue(effective_date=on_date, authority=operation)
        kinds = tuple(definition.token for definition in catalogue.definitions)
        for kind in kinds:
            if kind == catalogue.zero_token:
                # RATE_0 is a permanent registry slot, while 0062's zero rows
                # are date-bounded temporary measures.  Project the slot's
                # zero value through 0094 instead of treating the absence of a
                # temporary 0062 row as proof that zero is unavailable.
                zero_slot = resolve_iva_rate_slot(ZERO, on_date)
                zero_fraction = iva_rate_percentage(zero_slot, on_date)
                if zero_fraction is not None:
                    overlapping.add(zero_fraction * HUNDRED)
                continue
            with suppress(IvaRateNotFoundError):
                overlapping.add(
                    lookup_rate(
                        spanish_eu_member_state(effective_date=on_date, authority=operation),
                        kind,
                        on_date,
                        operation=operation,
                    ).pct,
                )
            overlapping.update(
                rate.pct
                for rate in coexisting_tier_rates(
                    spanish_eu_member_state(effective_date=on_date, authority=operation),
                    kind,
                    on_date,
                    operation=operation,
                )
            )
        on_date += timedelta(days=1)
    return tuple(sorted(overlapping))


def _as_pcts(fractions: Iterable[Decimal]) -> tuple[Decimal, ...]:
    """Return ``fractions`` as ascending percentages.

    The retención parameters are stored as fractions (``0.15``) because that is
    how a transaction carries one; a printed invoice states the percentage, so
    the prompt is given percentages and the conversion happens once, here.
    """
    return tuple(sorted(fraction * HUNDRED for fraction in fractions))


def resolve_invoice_extraction_authority_values(
    *,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> InvoiceExtractionAuthorityValues:
    """Resolve every regulatory value the reading prompt for ``period`` enumerates.

    Args:
        period: The filing period whose in-force values the prompt should
            enumerate. It is the caller's law-determined coordinate; nothing
            stored is fed back into the resolution.
        operation: The caller-owned pinned authority operation used for every
            IVA/category/legend component selected here.

    Returns:
        :class:`InvoiceExtractionAuthorityValues`: The resolved values, ready to
        hand to a renderer that holds no authority of its own.

    Raises:
        PeriodError: When ``period`` carries no calendar span, so no rate window
            can be resolved against it.
        IvaCatalogueError: When the bundled IVA rate registry cannot be read.
        TransactionValidationError: When the retención parameters cannot be read.
    """
    from ...domain.iva.components import registry_category_projection
    from ...domain.iva.regime_legend import regime_legend_phrases, resolve_regime_legends
    from ...domain.transactions.retencion_facts import statutory_activity_retencion_rates

    return InvoiceExtractionAuthorityValues(
        period=period,
        iva_rate_pcts=_overlapping_iva_rate_pcts(period, operation=operation),
        retencion_rate_pcts=_as_pcts(statutory_activity_retencion_rates(effective_date=period.end_date)),
        no_printed_tax_categories=tuple(
            sorted(
                registry_category_projection(
                    "no_printed_tax",
                    effective_date=period.end_date,
                    authority=operation,
                ),
                key=lambda member: member.value,
            ),
        ),
        regime_legend_phrases=regime_legend_phrases(
            resolve_regime_legends(operation=operation, effective_date=period.end_date),
        ),
    )
