"""Independent synthetic personas and hand arithmetic for the IVA carry-forward acceptance journeys.

Every figure below is worked from the persona inputs with Decimal arithmetic and the rules of the
official sources cited beside it. Nothing is read from a cadrumo run and nothing here imports cadrumo,
so a disagreement between this oracle and the installed product is a finding about one of the two.

Sources, by the id each carries in the bundled registry's legal tables:

* ``ley-37-1992:art-90`` (Uno): the general rate is 21 per cent.
* ``ley-37-1992:art-99`` (Cinco): the excess of deductions over the cuotas devengadas of the period "podra ser
  compensado en las declaraciones-liquidaciones posteriores"; the taxpayer may instead opt for a refund.
* ``ley-37-1992:art-115`` (Uno): the refund of the balance existing at 31 December is requested in the
  autoliquidacion of the last period of the year.
* ``rd-1624-1992:art-71``: quarterly periods, and the annual summary declaration.
* ``boe-modelo-303-2024-form-pdf`` (Orden HAC/819/2024, annex): the printed calculation expressions of the
  modelo 303 casillas 27, 45, 46, 64, 69, 78, 87 and 110. The design of this annex applies from the third
  quarter of 2024; the registry resolver, not this module, decides which casilla id carries each number in
  every other year.
* ``aeat-manual-iva-2025`` (Manual practico IVA 2025, chapter 9, pp. 277-279): the worked example of casillas
  78, 85, 95, 97 and 662, reproduced as a test of this module's engine.
* ``aeat-modelo-390-2025-instructions``, ``aeat-modelo-390-2024-printed-calculations`` and
  ``boe-modelo-390-2026-printed-calculations``: the modelo 390 casilla definitions and printed expressions.

Figures left out because the bundled official texts do not support them: the modelo 390 base-imponible
casillas of the 21 per cent domestic operations. The instructions name ranges of casillas for all rates
together ("01 a 06, 700 a 703 y 667 a 670", "695 a 698, 190, 191, ...") without assigning one casilla to the
21 per cent rate, so no base casilla is asserted. The modelo 303 base casillas are likewise not asserted.

The maximum application of casilla 78 is shown by the AEAT manual's worked example, in which the applied
amount equals the whole positive result while the available balance suffices; the instruction text for
casilla 78 itself is not in the bundled corpus, so the example is the citation for that behaviour.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final

CENT: Final = Decimal("0.01")
ZERO: Final = Decimal("0.00")

#: Ley 37/1992 art. 90.Uno: "El Impuesto se exigira al tipo del 21 por ciento".
GENERAL_RATE: Final = Decimal("0.21")

QUARTERS: Final = ("1T", "2T", "3T", "4T")

#: The origin label of a balance carried in from before the filing year.
PRIOR_YEAR: Final = "prior-year"

REGISTRY_LEGAL: Final = "legal"
REGISTRY_SOURCES: Final = "sources"


@dataclass(frozen=True, slots=True)
class Citation:
    """One provision or official text, keyed as the bundled registry keys it, with the words relied on."""

    source_id: str
    registry_table: str
    locator: str
    quote: str


LIVA_ART_90_UNO: Final = Citation(
    "ley-37-1992:art-90", REGISTRY_LEGAL, "Uno", "El Impuesto se exigirá al tipo del 21 por ciento"
)
LIVA_ART_99_CINCO: Final = Citation(
    "ley-37-1992:art-99",
    REGISTRY_LEGAL,
    "Cinco",
    "el exceso podrá ser compensado en las declaraciones-liquidaciones posteriores",
)
LIVA_ART_99_CINCO_DEVOLUCION: Final = Citation(
    "ley-37-1992:art-99",
    REGISTRY_LEGAL,
    "Cinco, segundo parrafo",
    "el sujeto pasivo podrá optar por la devolución del saldo existente a su favor",
)
LIVA_ART_115_UNO: Final = Citation(
    "ley-37-1992:art-115",
    REGISTRY_LEGAL,
    "Uno",
    "en la autoliquidación correspondiente al último período de liquidación de dicho año",
)
RLIVA_ART_71_TRIMESTRE: Final = Citation(
    "rd-1624-1992:art-71", REGISTRY_LEGAL, "3", "El período de liquidación coincidirá con el trimestre natural."
)
RLIVA_ART_71_RESUMEN: Final = Citation(
    "rd-1624-1992:art-71", REGISTRY_LEGAL, "1", "así como la declaración resumen anual prevista en el apartado 7"
)

# The next two quotes start after the capital "T": the PDF text layer drops that glyph, and the quote
# check reads the text layer.
FORM_303_BOX_27: Final = Citation(
    "boe-modelo-303-2024-form-pdf",
    REGISTRY_SOURCES,
    "casilla 27",
    "otal cuota devengada (152 + 167 + 03 + 155 + 06 + 09 + 11 + 13 + 15 + 158 + 170 + 18 + 21 + 24 + 26)",
)
FORM_303_BOX_45: Final = Citation(
    "boe-modelo-303-2024-form-pdf",
    REGISTRY_SOURCES,
    "casilla 45",
    "otal a deducir (29 + 31 + 33 + 35 + 37 + 39 + 41 + 42 + 43 + 44)",
)
FORM_303_BOX_46: Final = Citation(
    "boe-modelo-303-2024-form-pdf", REGISTRY_SOURCES, "casilla 46", "Resultado régimen general (27 - 45)"
)
FORM_303_BOX_64: Final = Citation(
    "boe-modelo-303-2024-form-pdf", REGISTRY_SOURCES, "casilla 64", "Suma de resultados (46 + 58 + 76)"
)
FORM_303_BOX_87: Final = Citation(
    "boe-modelo-303-2024-form-pdf",
    REGISTRY_SOURCES,
    "casilla 87",
    "Cuotas a compensar de periodos previos pendientes para periodos posteriores (110 - 78)",
)
FORM_303_BOX_69: Final = Citation(
    "boe-modelo-303-2024-form-pdf",
    REGISTRY_SOURCES,
    "casilla 69",
    "Resultado de la autoliquidación (66 + 77 - 78 + 68 + 108)",
)
FORM_303_BOX_110: Final = Citation(
    "boe-modelo-303-2024-form-pdf",
    REGISTRY_SOURCES,
    "casilla 110",
    "Cuotas a compensar pendientes de periodos anteriores",
)
FORM_303_BOX_78: Final = Citation(
    "boe-modelo-303-2024-form-pdf",
    REGISTRY_SOURCES,
    "casilla 78",
    "Cuotas a compensar de periodos anteriores aplicadas en este periodo",
)
MANUAL_BOX_78_APPLICATION: Final = Citation(
    "aeat-manual-iva-2025",
    REGISTRY_SOURCES,
    "pp. 277-278, Ejemplo 1: casillas 110, 78 and 87 of the four quarters",
    "Casilla 85: 800 (importe cuotas a compensar procedentes ejercicios anteriores aplicado durante el",
)
MANUAL_BOX_110_CARRY: Final = Citation(
    "aeat-manual-iva-2025",
    REGISTRY_SOURCES,
    "pp. 277-278, Ejemplo 1: casilla 110 of the fourth quarter",
    "Generado en el 3er trimestre: 500 y no aplicado a ninguna autoliquidación posterior",
)

INSTRUCTIONS_390_BOX_47: Final = Citation(
    "aeat-modelo-390-2025-instructions",
    REGISTRY_SOURCES,
    "apartado 5, casilla 47",
    "Total cuotas de IVA y recargo de equivalencia: suma de las cuotas de IVA y del",
)
FORM_390_BOX_64: Final = Citation(
    "boe-modelo-390-2026-printed-calculations",
    REGISTRY_SOURCES,
    "casilla 64",
    "Suma de deducciones (49 + 513 + 51 + 521 + 53 + 55 + 57 + 59 + 598 + 61 + 661 + 62 + 652 + 63 + 522)",
)
FORM_390_BOX_65: Final = Citation(
    "boe-modelo-390-2026-printed-calculations",
    REGISTRY_SOURCES,
    "casilla 65",
    "Resultado régimen general (47 - 64)",
)
FORM_390_2024_BOX_65: Final = Citation(
    "aeat-modelo-390-2024-printed-calculations",
    REGISTRY_SOURCES,
    "casilla 65",
    "Resultado régimen general (47 - 64)",
)
INSTRUCTIONS_390_BOX_84: Final = Citation(
    "aeat-modelo-390-2025-instructions",
    REGISTRY_SOURCES,
    "apartado 7, casilla 84",
    "Resultado régimen general (casilla 65), Resultado régimen simplificado (casilla 83) y de la",
)
INSTRUCTIONS_390_BOX_85: Final = Citation(
    "aeat-modelo-390-2025-instructions",
    REGISTRY_SOURCES,
    "apartado 7, casilla 85",
    "Compensación de cuotas del ejercicio anterior: se consignará el importe de las",
)
INSTRUCTIONS_390_BOX_86: Final = Citation(
    "aeat-modelo-390-2025-instructions",
    REGISTRY_SOURCES,
    "apartado 7, casilla 86",
    "se hará constar con el signo que corresponda el resultado de la operación indicada: (86) = (84) + (659)",
)
INSTRUCTIONS_390_BOX_95: Final = Citation(
    "aeat-modelo-390-2025-instructions",
    REGISTRY_SOURCES,
    "apartado 9.1, casilla 95",
    "Total resultados a ingresar en las autoliquidaciones de IVA del ejercicio",
)
INSTRUCTIONS_390_BOX_97: Final = Citation(
    "aeat-modelo-390-2025-instructions",
    REGISTRY_SOURCES,
    "apartado 9.1, casilla 97",
    "A compensar: si el resultado de la última autoliquidación fue a compensar, consignará",
)
INSTRUCTIONS_390_BOX_98: Final = Citation(
    "aeat-modelo-390-2025-instructions",
    REGISTRY_SOURCES,
    "apartado 9.1, casilla 98",
    "A devolver: si el resultado de la última autoliquidación fue a devolver, consignará en esta",
)
INSTRUCTIONS_390_BOX_662: Final = Citation(
    "aeat-modelo-390-2025-instructions",
    REGISTRY_SOURCES,
    "apartado 9.1, casilla 662",
    "cuotas a compensar generadas en el",
)

#: The citations behind each figure, keyed ``<modelo>:<casilla>`` or by a named quantity.
FIGURE_CITATIONS: Final[Mapping[str, tuple[Citation, ...]]] = {
    "303:cuota": (LIVA_ART_90_UNO, RLIVA_ART_71_TRIMESTRE),
    "303:27": (FORM_303_BOX_27, LIVA_ART_90_UNO),
    "303:45": (FORM_303_BOX_45, LIVA_ART_90_UNO),
    "303:46": (FORM_303_BOX_46,),
    "303:64": (FORM_303_BOX_64,),
    "303:110": (FORM_303_BOX_110, LIVA_ART_99_CINCO, MANUAL_BOX_110_CARRY),
    "303:78": (FORM_303_BOX_78, LIVA_ART_99_CINCO, MANUAL_BOX_78_APPLICATION),
    "303:87": (FORM_303_BOX_87,),
    "303:69": (FORM_303_BOX_69,),
    "303:credit-at-end": (LIVA_ART_99_CINCO, FORM_303_BOX_87, MANUAL_BOX_110_CARRY),
    "390:47": (INSTRUCTIONS_390_BOX_47, RLIVA_ART_71_RESUMEN),
    "390:64": (FORM_390_BOX_64,),
    "390:65": (FORM_390_BOX_65, FORM_390_2024_BOX_65),
    "390:84": (INSTRUCTIONS_390_BOX_84,),
    "390:85": (INSTRUCTIONS_390_BOX_85, MANUAL_BOX_78_APPLICATION),
    "390:86": (INSTRUCTIONS_390_BOX_86,),
    "390:95": (INSTRUCTIONS_390_BOX_95,),
    "390:97": (INSTRUCTIONS_390_BOX_97, LIVA_ART_115_UNO),
    "390:98": (INSTRUCTIONS_390_BOX_98, LIVA_ART_99_CINCO_DEVOLUCION, LIVA_ART_115_UNO),
    "390:662": (INSTRUCTIONS_390_BOX_662,),
    "wallet": (LIVA_ART_99_CINCO, MANUAL_BOX_110_CARRY),
}


class LastPeriodElection(StrEnum):
    """What the taxpayer does with a negative result of the last period of the year."""

    COMPENSAR = "compensar"
    DEVOLVER = "devolver"


def money(value: Decimal) -> Decimal:
    """Return ``value`` as exact cents, refusing anything finer than a cent."""
    quantized = value.quantize(CENT)
    if quantized != value:
        raise ValueError(f"{value} is not a whole number of cents")
    return quantized


def cuota_from_base(base: Decimal) -> Decimal:
    """Return the cuota of ``base`` at the general rate, refusing a base whose cuota is not whole cents.

    The persona bases give exact cents, so no rounding rule is exercised or asserted here.
    """
    return money(base * GENERAL_RATE)


@dataclass(frozen=True, slots=True)
class PersonaInvoice:
    """One domestic invoice at the general rate, dated inside the filing year."""

    month: int
    day: int
    base: Decimal

    @property
    def cuota(self) -> Decimal:
        """The cuota at the 21 per cent general rate."""
        return cuota_from_base(self.base)


@dataclass(frozen=True, slots=True)
class PersonaQuarter:
    """The invoices of one quarter."""

    quarter: str
    sales: tuple[PersonaInvoice, ...]
    purchases: tuple[PersonaInvoice, ...]

    @property
    def cuota_devengada(self) -> Decimal:
        """The sum of the cuotas of the sales."""
        return money(sum((sale.cuota for sale in self.sales), ZERO))

    @property
    def cuota_deducible(self) -> Decimal:
        """The sum of the cuotas of the purchases."""
        return money(sum((purchase.cuota for purchase in self.purchases), ZERO))


@dataclass(frozen=True, slots=True)
class QuarterCuotas:
    """The two totals a quarter's autoliquidacion starts from."""

    quarter: str
    devengada: Decimal
    deducible: Decimal


@dataclass(frozen=True, slots=True)
class WalletLot:
    """One negative result carried forward, with what each later quarter applied from it."""

    origin: str
    generated: Decimal
    applied: tuple[tuple[str, Decimal], ...]

    @property
    def total_applied(self) -> Decimal:
        """The sum already applied from this lot."""
        return money(sum((amount for _quarter, amount in self.applied), ZERO))

    @property
    def remaining(self) -> Decimal:
        """What the lot still carries."""
        return money(self.generated - self.total_applied)


@dataclass(frozen=True, slots=True)
class Modelo303Quarter:
    """The casillas of one quarter's modelo 303 under the single-regime, state-territory case."""

    quarter: str
    box_27: Decimal
    box_45: Decimal
    box_46: Decimal
    box_64: Decimal
    box_110: Decimal
    box_78: Decimal
    box_87: Decimal
    box_69: Decimal
    credit_at_end: Decimal


@dataclass(frozen=True, slots=True)
class Modelo390Year:
    """The annual summary casillas the carry-forward chain determines."""

    box_47: Decimal
    box_64: Decimal
    box_65: Decimal
    box_84: Decimal
    box_85: Decimal
    box_86: Decimal
    box_95: Decimal
    box_97: Decimal
    box_98: Decimal
    box_662: Decimal


@dataclass(frozen=True, slots=True)
class YearOutcome:
    """The four autoliquidaciones, the annual summary and the wallet after the last quarter."""

    quarters: tuple[Modelo303Quarter, ...]
    annual: Modelo390Year
    wallet: tuple[WalletLot, ...]


def _apply_oldest_first(lots: list[WalletLot], *, quarter: str, amount: Decimal) -> None:
    """Take ``amount`` from the open lots, oldest first, recording the quarter that applied it."""
    left = amount
    for index, lot in enumerate(lots):
        if left <= ZERO:
            return
        take = min(lot.remaining, left)
        if take > ZERO:
            lots[index] = WalletLot(lot.origin, lot.generated, (*lot.applied, (quarter, take)))
            left = money(left - take)


def _open_balance(lots: Sequence[WalletLot]) -> Decimal:
    return money(sum((lot.remaining for lot in lots), ZERO))


def _work_quarter(lots: list[WalletLot], entry: QuarterCuotas, *, refunded: bool) -> Modelo303Quarter:
    """Work one autoliquidacion against the wallet, applying the balance oldest lot first and opening a new lot."""
    box_27, box_45 = money(entry.devengada), money(entry.deducible)
    box_46 = money(box_27 - box_45)
    box_64 = box_46
    box_110 = _open_balance(lots)
    box_78 = min(box_110, max(box_64, ZERO))
    _apply_oldest_first(lots, quarter=entry.quarter, amount=box_78)
    box_87 = money(box_110 - box_78)
    box_69 = money(box_64 - box_78)
    if box_69 < ZERO and not refunded:
        lots.append(WalletLot(entry.quarter, money(-box_69), ()))
    return Modelo303Quarter(
        quarter=entry.quarter,
        box_27=box_27,
        box_45=box_45,
        box_46=box_46,
        box_64=box_64,
        box_110=box_110,
        box_78=box_78,
        box_87=box_87,
        box_69=box_69,
        credit_at_end=_open_balance(lots),
    )


def _last_period_amount(last_result: Decimal, election: LastPeriodElection, wanted: LastPeriodElection) -> Decimal:
    """The negative last-period result, as a positive amount, when the taxpayer made the ``wanted`` election."""
    return money(-last_result) if last_result < ZERO and election is wanted else ZERO


def _annual_summary(
    results: Sequence[Modelo303Quarter], lots: Sequence[WalletLot], *, last: str, election: LastPeriodElection
) -> Modelo390Year:
    """The annual summary the year's quarters and the remaining wallet determine."""
    last_result = results[-1].box_69
    box_47 = money(sum((row.box_27 for row in results), ZERO))
    box_64 = money(sum((row.box_45 for row in results), ZERO))
    box_65 = money(box_47 - box_64)
    box_84 = box_65
    box_85 = money(sum((amount for lot in lots if lot.origin == PRIOR_YEAR for _quarter, amount in lot.applied), ZERO))
    return Modelo390Year(
        box_47=box_47,
        box_64=box_64,
        box_65=box_65,
        box_84=box_84,
        box_85=box_85,
        box_86=money(box_84 - box_85),
        box_95=money(sum((row.box_69 for row in results if row.box_69 > ZERO), ZERO)),
        box_97=_last_period_amount(last_result, election, LastPeriodElection.COMPENSAR),
        box_98=_last_period_amount(last_result, election, LastPeriodElection.DEVOLVER),
        box_662=money(sum((lot.remaining for lot in lots if lot.origin not in {PRIOR_YEAR, last}), ZERO)),
    )


def run_year(
    quarters: Sequence[QuarterCuotas],
    *,
    opening_prior_year_credit: Decimal = ZERO,
    last_period_election: LastPeriodElection = LastPeriodElection.COMPENSAR,
) -> YearOutcome:
    """Work the autoliquidaciones of a year in order and the annual summary they determine.

    Per quarter: the result is cuota devengada minus cuota deducible (303 casillas 27, 45, 46, 64). Casilla 110
    is the open balance; casilla 78 applies the whole positive result up to that balance, oldest lot first;
    casilla 87 is 110 - 78; casilla 69 is the result less casilla 78. A negative 69 opens a new lot, except that
    a last-quarter refund election (art. 99.Cinco, second paragraph) leaves no balance to compensate.
    """
    if not quarters:
        raise ValueError("a year has at least one quarter")
    lots: list[WalletLot] = []
    if opening_prior_year_credit != ZERO:
        lots.append(WalletLot(PRIOR_YEAR, money(opening_prior_year_credit), ()))
    last = quarters[-1].quarter
    results = [
        _work_quarter(
            lots, entry, refunded=entry.quarter == last and last_period_election is LastPeriodElection.DEVOLVER
        )
        for entry in quarters
    ]
    annual = _annual_summary(results, lots, last=last, election=last_period_election)
    return YearOutcome(quarters=tuple(results), annual=annual, wallet=tuple(lots))


def quarter_cuotas(persona_quarters: Sequence[PersonaQuarter]) -> tuple[QuarterCuotas, ...]:
    """Reduce persona invoices to the totals each quarter starts from."""
    return tuple(QuarterCuotas(row.quarter, row.cuota_devengada, row.cuota_deducible) for row in persona_quarters)


#: Persona A: activity from 1 January, opening balance seeded at zero, one sale and one purchase a quarter.
#: Months and days are the persona's dates; the filing year comes from the journey.
OPENING_CREDIT_A: Final = Decimal("0.00")

PERSONA_A_QUARTERS: Final[tuple[PersonaQuarter, ...]] = (
    PersonaQuarter(
        "1T",
        sales=(PersonaInvoice(2, 10, Decimal("1000.00")),),
        purchases=(PersonaInvoice(3, 5, Decimal("3000.00")),),
    ),
    PersonaQuarter(
        "2T",
        sales=(PersonaInvoice(5, 12, Decimal("1500.00")),),
        purchases=(PersonaInvoice(5, 20, Decimal("500.00")),),
    ),
    PersonaQuarter(
        "3T",
        sales=(PersonaInvoice(8, 15, Decimal("2000.00")),),
        purchases=(PersonaInvoice(8, 20, Decimal("500.00")),),
    ),
    PersonaQuarter(
        "4T",
        sales=(PersonaInvoice(11, 20, Decimal("1000.00")),),
        purchases=(PersonaInvoice(11, 25, Decimal("2000.00")),),
    ),
)


def persona_a_outcome() -> YearOutcome:
    """Work Persona A's year, filing a refund-free (compensar) last quarter."""
    return run_year(
        quarter_cuotas(PERSONA_A_QUARTERS),
        opening_prior_year_credit=OPENING_CREDIT_A,
        last_period_election=LastPeriodElection.COMPENSAR,
    )


def persona_a_override_amounts() -> Mapping[str, Decimal]:
    """Return the casilla 110 an operator must assert for each quarter that follows a carried credit.

    Casilla 110 of a quarter is the previous quarter's casilla 87 plus the credit that quarter generated, which
    is the open balance entering it. These amounts are operator assertions in the journey, not product output.
    """
    outcome = persona_a_outcome()
    return {row.quarter: row.box_110 for row in outcome.quarters if row.box_110 > ZERO}


#: Persona B: activity from two years before the filing year, no seeded balance, a single first-quarter sale.
PERSONA_B_ACTIVITY_START_YEARS_BEFORE_FILING: Final = 2


@dataclass(frozen=True, slots=True)
class PersonaBExpectation:
    """What Persona B's inputs fix and what they leave unknown.

    The sale fixes casillas 27, 45 and 46. The opening balance is unknown, not zero, because the taxpayer was
    active in earlier years and no balance was recorded: casilla 110 cannot be determined (art. 99.Cinco makes
    the compensation depend on the earlier balance), so a calculation must not be accepted with a zero.
    """

    sale: PersonaInvoice
    box_27: Decimal
    box_45: Decimal
    box_46: Decimal
    opening_balance_known: bool
    citations: tuple[Citation, ...]


def persona_b_expectation() -> PersonaBExpectation:
    """Return Persona B's fixed figures and its unknown opening balance."""
    sale = PersonaInvoice(2, 10, Decimal("1000.00"))
    cuotas = run_year((QuarterCuotas("1T", sale.cuota, ZERO),)).quarters[0]
    return PersonaBExpectation(
        sale=sale,
        box_27=cuotas.box_27,
        box_45=cuotas.box_45,
        box_46=cuotas.box_46,
        opening_balance_known=False,
        citations=(LIVA_ART_99_CINCO, FORM_303_BOX_110),
    )
