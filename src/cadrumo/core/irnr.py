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
tree and its :class:`~domain.calculations.registry.ConvenioAuthority`
projection. The registry TOML stays free-form (a plain string token); the loader
hydrates the enum at the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


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

        INMOBILIARIA: Art. 13.1.h imputed urban real-estate income (the source
            article), taxed at the Art. 25.1.a general 24% rate.

        CANONES: Art. 25.1.a cánones (royalties). The consolidated Art. 25.1
            carries no cánones-specific letter, so royalties are taxed at the
            general rendimiento rate (24%, or the Art. 25.1.a reduced 19% for
            EU/EEA residents). Bilateral treaties routinely cap or exempt the
            source-state cánones rate via their Art. 12.
    """

    GENERAL = "general"
    UE_RESIDENTE = "ue_residente"
    PENSION = "pension"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    GANANCIA_PATRIMONIAL = "ganancia_patrimonial"
    INMOBILIARIA = "inmobiliaria"
    CANONES = "canones"


class M210PayerMode(StrEnum):
    """Closed payer-identity modes for one Modelo 210 renta component.

    Modelo 210 agrupación normally requires a single identified payer. The
    statutory code-35 exception represents several payers for grouped rental
    income; it is an explicit mode, never a missing payer identifier. The same
    legal vocabulary is shared by persisted M210 ledger classifications and
    M210 declaration-detail rows.
    """

    SINGLE_PAYER = "single_payer"
    MULTIPLE_PAYERS_CODE_35 = "multiple_payers_code_35"


class M210GrossIncomeSourceMode(StrEnum):
    """Authority selected for Modelo 210 ``rendimientos_integros`` on one revision."""

    MANUAL = "manual"
    LEDGER = "ledger"


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


class TipoRentaGroundingTier(StrEnum):
    """How firmly the bundled corpus grounds an official code's rate concept.

    The official Modelo 210 tipo-de-renta code axis (Orden EHA/3316/2010,
    "HOJA INFORMATIVA 210 - TIPOS DE RENTA") is a numeric code list, but the
    rate each code bears is only bundled-verifiable for the codes whose rate
    concept is named by a bundled TRLIRNR Art. 25 letter (the shipped corpus
    carries Art. 25 letters a, b, and f only; the special-rate letters
    c/d/e/g/h are absent). This tier records, per
    declared code, how its :class:`TipoRentaIrnr` rate concept is grounded:

    Members:
        RATE_VERIFIED: The rate concept is explicitly modelled by the bundled
            corpus — a bundled Art. 25 special letter that names the income
            (25.1.b pensions, 25.1.f dividends / interest / capital gains) or a
            dedicated bundled mechanism (Art. 13.1.h imputed real-estate).

        RESIDUAL: The code is an ordinary rendimiento with no special regime,
            mapped to :attr:`TipoRentaIrnr.GENERAL` on the Art. 25.1.a "con
            carácter general, el 24 por ciento" residual clause. A later fetch
            of the full consolidated Art. 25 that reveals a special rate for
            such a code is a CORRECTION of this row, never a contradiction of
            its grounding.
    """

    RATE_VERIFIED = "rate_verified"
    RESIDUAL = "residual"


@dataclass(frozen=True, slots=True)
class OfficialTipoRentaCode:
    """One official Modelo 210 tipo-de-renta code and its rate projection.

    The operator enters the two-digit official code the form asks for; the
    engine keeps :class:`TipoRentaIrnr` as its rate key. This record is the
    single projection from the official code to that conceptual key, carried
    with the grounding that justifies the mapping. The official codes are
    many-to-one onto the rate concepts (every ordinary rendimiento folds into
    ``general``), which is why the code axis is declared alongside — not in
    place of — the conceptual enum.

    Attributes:
        code: The two-digit official code, byte-identical to the "Tipo" column
            of the bundled HOJA INFORMATIVA 210 (Orden EHA/3316/2010).
        concept: The :class:`TipoRentaIrnr` rate concept the code folds into.
        rate_legal_ref: The legal-catalogue id (a TRLIRNR article) that
            establishes the concept's rate for this code. The load-bearing
            grounding is registry-resident: the ``m210-tipo-renta-code-2025``
            parameter carries the ``legal_refs`` the canonical registry
            legal-grounding gate validates against the bundled corpus.
        grounding_tier: Whether the rate concept is directly rate-verified from
            the bundled corpus or rests on the Art. 25.1.a residual clause.
    """

    code: str
    concept: TipoRentaIrnr
    rate_legal_ref: str
    grounding_tier: TipoRentaGroundingTier


# The official tipo-de-renta codes whose rate concept is grounded against the
# bundled corpus (Orden EHA/3316/2010 HOJA INFORMATIVA 210 for the code list;
# TRLIRNR Art. 25.1.a/b/f + Art. 13.1.h for the rate concept). The cánones codes
# 08/09/10/11/12/32 are declared here on the Art. 25.1.a residual clause: the
# consolidated Art. 25.1 carries no cánones-specific letter, so cánones is the
# general rendimiento rate. The remaining fetch-gated codes — asistencia técnica
# 13 (cánones-ADJACENT in the HOJA INFORMATIVA, a possible non-bundled special
# letter, NOT cánones proper), reaseguros 19 (Art. 25.1.e), navegación 20
# (Art. 25.1.d), imposición complementaria 27 (Art. 19.2), and premios de
# loterías 31 (D.A. 5ª gravamen especial) — are NOT declared here: their rate is
# not bundle-verifiable, and force-mapping any to a rate would fabricate it. They
# enrol code-by-code once the full consolidated Art. 25 is fetched.
OFFICIAL_M210_TIPO_RENTA_CODES: tuple[OfficialTipoRentaCode, ...] = (
    OfficialTipoRentaCode(
        "01", TipoRentaIrnr.GENERAL, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RESIDUAL
    ),
    OfficialTipoRentaCode(
        "02", TipoRentaIrnr.INMOBILIARIA, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RATE_VERIFIED
    ),
    OfficialTipoRentaCode(
        "03", TipoRentaIrnr.GENERAL, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RESIDUAL
    ),
    OfficialTipoRentaCode(
        "04", TipoRentaIrnr.DIVIDEND, "trlirnr-rdleg-5-2004:art-25.1.f", TipoRentaGroundingTier.RATE_VERIFIED
    ),
    OfficialTipoRentaCode(
        "05", TipoRentaIrnr.INTEREST, "trlirnr-rdleg-5-2004:art-25.1.f", TipoRentaGroundingTier.RATE_VERIFIED
    ),
    OfficialTipoRentaCode(
        "06", TipoRentaIrnr.INTEREST, "trlirnr-rdleg-5-2004:art-25.1.f", TipoRentaGroundingTier.RATE_VERIFIED
    ),
    OfficialTipoRentaCode(
        "07", TipoRentaIrnr.INTEREST, "trlirnr-rdleg-5-2004:art-25.1.f", TipoRentaGroundingTier.RATE_VERIFIED
    ),
    OfficialTipoRentaCode(
        "08", TipoRentaIrnr.CANONES, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RESIDUAL
    ),
    OfficialTipoRentaCode(
        "09", TipoRentaIrnr.CANONES, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RESIDUAL
    ),
    OfficialTipoRentaCode(
        "10", TipoRentaIrnr.CANONES, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RESIDUAL
    ),
    OfficialTipoRentaCode(
        "11", TipoRentaIrnr.CANONES, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RESIDUAL
    ),
    OfficialTipoRentaCode(
        "12", TipoRentaIrnr.CANONES, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RESIDUAL
    ),
    OfficialTipoRentaCode(
        "14", TipoRentaIrnr.GENERAL, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RESIDUAL
    ),
    OfficialTipoRentaCode(
        "15", TipoRentaIrnr.GENERAL, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RESIDUAL
    ),
    OfficialTipoRentaCode(
        "16", TipoRentaIrnr.GENERAL, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RESIDUAL
    ),
    OfficialTipoRentaCode(
        "17", TipoRentaIrnr.GENERAL, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RESIDUAL
    ),
    OfficialTipoRentaCode(
        "18", TipoRentaIrnr.PENSION, "trlirnr-rdleg-5-2004:art-25.1.b", TipoRentaGroundingTier.RATE_VERIFIED
    ),
    OfficialTipoRentaCode(
        "21", TipoRentaIrnr.GENERAL, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RESIDUAL
    ),
    OfficialTipoRentaCode(
        "22", TipoRentaIrnr.GENERAL, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RESIDUAL
    ),
    OfficialTipoRentaCode(
        "24",
        TipoRentaIrnr.GANANCIA_PATRIMONIAL,
        "trlirnr-rdleg-5-2004:art-25.1.f",
        TipoRentaGroundingTier.RATE_VERIFIED,
    ),
    OfficialTipoRentaCode(
        "25",
        TipoRentaIrnr.GANANCIA_PATRIMONIAL,
        "trlirnr-rdleg-5-2004:art-25.1.f",
        TipoRentaGroundingTier.RATE_VERIFIED,
    ),
    OfficialTipoRentaCode(
        "26",
        TipoRentaIrnr.GANANCIA_PATRIMONIAL,
        "trlirnr-rdleg-5-2004:art-25.1.f",
        TipoRentaGroundingTier.RATE_VERIFIED,
    ),
    OfficialTipoRentaCode(
        "28",
        TipoRentaIrnr.GANANCIA_PATRIMONIAL,
        "trlirnr-rdleg-5-2004:art-25.1.f",
        TipoRentaGroundingTier.RATE_VERIFIED,
    ),
    OfficialTipoRentaCode(
        "29", TipoRentaIrnr.DIVIDEND, "trlirnr-rdleg-5-2004:art-25.1.f", TipoRentaGroundingTier.RATE_VERIFIED
    ),
    OfficialTipoRentaCode(
        "30", TipoRentaIrnr.DIVIDEND, "trlirnr-rdleg-5-2004:art-25.1.f", TipoRentaGroundingTier.RATE_VERIFIED
    ),
    OfficialTipoRentaCode(
        "32", TipoRentaIrnr.CANONES, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RESIDUAL
    ),
    OfficialTipoRentaCode(
        "33",
        TipoRentaIrnr.GANANCIA_PATRIMONIAL,
        "trlirnr-rdleg-5-2004:art-25.1.f",
        TipoRentaGroundingTier.RATE_VERIFIED,
    ),
    OfficialTipoRentaCode(
        "34",
        TipoRentaIrnr.GANANCIA_PATRIMONIAL,
        "trlirnr-rdleg-5-2004:art-25.1.f",
        TipoRentaGroundingTier.RATE_VERIFIED,
    ),
    OfficialTipoRentaCode(
        "35", TipoRentaIrnr.GENERAL, "trlirnr-rdleg-5-2004:art-25.1.a", TipoRentaGroundingTier.RESIDUAL
    ),
    OfficialTipoRentaCode(
        "36",
        TipoRentaIrnr.GANANCIA_PATRIMONIAL,
        "trlirnr-rdleg-5-2004:art-25.1.f",
        TipoRentaGroundingTier.RATE_VERIFIED,
    ),
    OfficialTipoRentaCode(
        "37", TipoRentaIrnr.INTEREST, "trlirnr-rdleg-5-2004:art-25.1.f", TipoRentaGroundingTier.RATE_VERIFIED
    ),
    OfficialTipoRentaCode(
        "38",
        TipoRentaIrnr.GANANCIA_PATRIMONIAL,
        "trlirnr-rdleg-5-2004:art-25.1.f",
        TipoRentaGroundingTier.RATE_VERIFIED,
    ),
)


M210_TIPO_RENTA_CODE_PROJECTION: MappingProxyType[str, TipoRentaIrnr] = MappingProxyType(
    {entry.code: entry.concept for entry in OFFICIAL_M210_TIPO_RENTA_CODES}
)
"""Read-only official-code → :class:`TipoRentaIrnr` projection.

Derived from :data:`OFFICIAL_M210_TIPO_RENTA_CODES`; the single mapping the CLI
hydrates to resolve an operator-entered official code to its rate concept. Keys
are the byte-identical two-digit official codes; values are the rate concept the
engine dispatches on. The registry-build parity gate
(``validate_m210_tipo_renta_code_projection_parity``) cross-checks this
projection against the registry-declared ``m210-tipo-renta-code-2025`` code set
in both directions, so a declared code without a projection — or a projected
code the registry does not declare — fails the build.
"""


def project_m210_tipo_renta_code(code: str) -> TipoRentaIrnr:
    """Project an official Modelo 210 tipo-de-renta ``code`` to its rate concept.

    Args:
        code: A two-digit official code from the HOJA INFORMATIVA 210.

    Returns:
        The :class:`TipoRentaIrnr` rate concept the code folds into.

    Raises:
        KeyError: When ``code`` is not a declared, rate-grounded official code.
            A fetch-gated code (whose rate is not yet bundle-verifiable) raises
            here rather than resolving to a fabricated rate.
    """
    return M210_TIPO_RENTA_CODE_PROJECTION[code]


# Official HOJA INFORMATIVA 210 codes that are REAL AEAT tipo-de-renta codes but
# whose rate is NOT yet grounded against the bundled corpus (the bundled TRLIRNR
# extract carries only Art. 25 letters a/b/f): asistencia técnica 13
# (cánones-ADJACENT in the HOJA INFORMATIVA — a possible non-bundled special
# letter, NOT cánones proper, so deliberately NOT promoted with the cánones
# codes), reaseguros 19 (Art. 25.1.e), navegación 20 (Art. 25.1.d), imposición
# complementaria 27 (Art. 19.2), and premios de loterías 31 (D.A. 5ª gravamen
# especial). They are NOT in the declared projection — mapping them would
# fabricate a rate — but they are distinguished here from a genuinely-invalid
# code so the CLI boundary can tell an operator "fetch-gated, not yet grounded"
# rather than "invalid". The cánones codes 08/09/10/11/12/32 were promoted into
# OFFICIAL_M210_TIPO_RENTA_CODES: cánones is the general rendimiento rate under
# the Art. 25.1.a residual clause (the consolidated Art. 25.1 carries no
# cánones-specific letter), so their rate concept is bundle-grounded.
FETCH_GATED_M210_TIPO_RENTA_CODES: frozenset[str] = frozenset({"13", "19", "20", "27", "31"})
