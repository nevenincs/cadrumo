"""Closed value sets for the IRNR (non-resident income tax) treaty surface.

Two closed axes governing the Modelo 210 IRNR rate-resolution path — and,
by design, every future IRNR consumer (M216 retenciones a no residentes) —
are declared here as :class:`enum.StrEnum` per the core-authority discipline
(closed axes live in ``core/``, hydrated at boundaries, asserted as members in
tests, surfaced as click ``Choice`` at the CLI):

* :class:`TipoRentaIrnr` — the income-type axis an IRNR filer tags each item
  with. It keys the TRLIRNR baseline rate table, the treaty override rows, and
  the Art. 25.1.b pension tariff branch. It was previously a free-text casilla
  value with no enum home, which forced adjacent verification work to route a
  categorical-equality predicate around the untyped axis.

* :class:`ConvenioOverrideKind` — how a bilateral double-taxation treaty
  (Convenio para evitar la doble imposición, CDI) override acts on the domestic
  rate. Making the kind typed data turns "más favorable" / limitation-of-benefits
  from a numeric coincidence (a flat treaty rate that happens to be lower than
  the domestic baseline) into a computable decision.

Both enums are consumed by the cross-cutting ``registry/aeat/treaties/`` authoring
tree and its :class:`~aeat.domain.calculations.registry.ConvenioAuthority`
projection. The registry TOML stays free-form (a plain string token); the loader
hydrates the enum at the boundary.
"""

from __future__ import annotations

from enum import StrEnum


class TipoRentaIrnr(StrEnum):
    """The IRNR income-type axis (TRLIRNR RDLeg 5/2004 arts. 24-25).

    Each member's value is the byte-identical token stored in the registry
    ``tipo_renta`` casilla and used as the lookup key for the baseline rate
    table (``m210-tipo-gravamen-2025``), the treaty override rows, and the
    Art. 25.1.b pension tariff branch. The value set is closed by the TRLIRNR
    rate schedule; a new income category is added here first.

    Members:
        GENERAL: Art. 25.1.a general non-resident rate (24%).
        UE_RESIDENTE: Art. 25.1.a reduced rate for EU/EEA residents (19%).
        PENSION: Art. 25.1.b progressive pension tariff (bracket table).
        DIVIDEND: Art. 25.1.f.1º dividends / other income from participation
            in an entity's own funds (19%).
        INTEREST: Art. 25.1.f.2º interest / capital-cession income (19%).
        GANANCIA_PATRIMONIAL: Art. 25.1.f.3º capital gains (19%).
        INMOBILIARIA: Art. 13.1.h imputed urban real-estate income (24% base).
    """

    GENERAL = "general"
    UE_RESIDENTE = "ue_residente"
    PENSION = "pension"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    GANANCIA_PATRIMONIAL = "ganancia_patrimonial"
    INMOBILIARIA = "inmobiliaria"


class ConvenioOverrideKind(StrEnum):
    """How a double-taxation treaty override acts on the domestic IRNR rate.

    The override is one branch of the single tipo-de-gravamen resolution path,
    not a second resolver. On a matched treaty override row the resolver applies
    the kind:

    Members:
        FLAT: The treaty rate REPLACES the domestic baseline outright.
        CEILING: The treaty caps the source-state rate ("may not exceed X%");
            the resolver applies ``min(domestic, treaty)`` so the "más favorable"
            outcome is computed rather than assumed.
        ALLOCATION_DOMESTIC_TARIFF: The treaty allocates taxation to Spain but
            fixes no rate; the amount is delegated to the domestic tariff (e.g.
            the Art. 25.1.b progressive pension tariff). Rows of this kind carry
            no ``rate``.
        EXEMPT: The source state may not tax the income; the resolver yields a
            zero rate. Rows of this kind carry no ``rate``.
    """

    FLAT = "flat"
    CEILING = "ceiling"
    ALLOCATION_DOMESTIC_TARIFF = "allocation_domestic_tariff"
    EXEMPT = "exempt"

    @property
    def carries_rate(self) -> bool:
        """True when a row of this kind MUST declare a numeric ``rate``.

        ``FLAT`` and ``CEILING`` operate on a treaty rate; ``ALLOCATION_DOMESTIC_TARIFF``
        and ``EXEMPT`` do not (the amount is delegated to the domestic tariff or
        driven to zero). Consumed by the treaty-row validator so a malformed row
        (a rate on an exempt override, or a missing rate on a ceiling) fails at
        registry-build time.
        """
        return self in (ConvenioOverrideKind.FLAT, ConvenioOverrideKind.CEILING)
