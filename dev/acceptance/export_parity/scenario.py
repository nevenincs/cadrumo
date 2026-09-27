"""Year-parameterised synthetic facts and independent arithmetic for the export parity store.

One natural person runs a professional activity under estimación directa normal
from 2022. Every fact here is synthetic; every expected value is computed from
these constants and the cited rule, never read from Cadrumo.

Rules the oracle restates:
- IVA general rate 21% (Ley 37/1992 art. 90); insurance is exempt (art. 20.1.16).
- Withholding on the declarant's professional income: 7% in the activity start
  year and the two following, 15% afterwards (RIRPF art. 101.5.a).
- Withholding the declarant practises: 15% on a professional's fees
  (RIRPF art. 101.5.a) and 19% on urban office rent (RIRPF art. 101.8, 111.1).
- Linear amortization at the table's maximum coefficient, prorated by days in
  service (LIS art. 12.1.a; RIRPF art. 30 by reference).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

SCENARIO_VERSION = "export-parity-multiyear-v1"
YEARS = (2022, 2023, 2024, 2025)
QUARTERS = ("1T", "2T", "3T", "4T")
ACTIVITY_START = date(2022, 1, 1)
TAXPAYER_TAX_ID = "12345678Z"
CENT = Decimal("0.01")
IVA_GENERAL = Decimal("0.21")
PROFESSIONAL_WITHHOLDING = Decimal("0.15")
NEW_ACTIVITY_WITHHOLDING = Decimal("0.07")
RENT_WITHHOLDING = Decimal("0.19")
RETA_MONTHLY = Decimal("300.00")
#: Quarter -> (invoice month, invoice day, bank day).
_QUARTER_MONTHS = {"1T": 2, "2T": 5, "3T": 8, "4T": 11}


def money(value: Decimal) -> Decimal:
    """Round to euro cents, half up, as AEAT forms do."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class Counterparty:
    """A synthetic counterparty with a checksum-valid tax identifier."""

    name: str
    tax_id: str


CLIENT = Counterparty("Synthetic Client SL", "A58818501")
SUPPLIER = Counterparty("Synthetic Office Supplies SL", "B12345674")
ADVISER = Counterparty("Synthetic Tax Adviser", "00000001R")
LANDLORD = Counterparty("Synthetic Urban Landlord", "00000002W")
SOFTWARE_VENDOR = Counterparty("Synthetic Software Vendor", "00000003A")
INSURER = Counterparty("Synthetic Insurer", "00000004G")


class WithholdingDuty(StrEnum):
    """Which periodic return a received invoice's withholding belongs to."""

    NONE = "none"
    PROFESSIONAL = "modelo_111"
    URBAN_RENT = "modelo_115"


@dataclass(frozen=True, slots=True)
class IssuedInvoice:
    """One professional invoice the declarant issues and its incoming payment."""

    key: str
    period: str
    invoice_date: date
    payment_date: date
    base: Decimal
    withholding_rate: Decimal

    @property
    def iva(self) -> Decimal:
        """Output IVA charged on the base."""
        return money(self.base * IVA_GENERAL)

    @property
    def withholding(self) -> Decimal:
        """IRPF withheld by the client."""
        return money(self.base * self.withholding_rate)

    @property
    def receipt(self) -> Decimal:
        """Amount the client pays: base plus IVA less withholding."""
        return self.base + self.iva - self.withholding


@dataclass(frozen=True, slots=True)
class ReceivedInvoice:
    """One deductible purchase with its outgoing payment and purchase evidence."""

    key: str
    period: str
    counterparty: Counterparty
    category: str
    invoice_date: date
    payment_date: date
    base: Decimal
    iva_rate: Decimal
    duty: WithholdingDuty = WithholdingDuty.NONE
    #: Assets are amortized, not expensed; their invoice still carries deductible IVA.
    asset_id: str | None = None

    @property
    def iva(self) -> Decimal:
        """Input IVA borne on the base."""
        return money(self.base * self.iva_rate)

    @property
    def withholding(self) -> Decimal:
        """IRPF the declarant withholds from the supplier, by duty."""
        rate = {
            WithholdingDuty.NONE: Decimal("0"),
            WithholdingDuty.PROFESSIONAL: PROFESSIONAL_WITHHOLDING,
            WithholdingDuty.URBAN_RENT: RENT_WITHHOLDING,
        }[self.duty]
        return money(self.base * rate)

    @property
    def payment(self) -> Decimal:
        """Amount paid: base plus IVA less withholding."""
        return self.base + self.iva - self.withholding


#: LIVA art. 108.Dos: goods acquired for no more than this are not bienes de inversion.
IVA_INVESTMENT_GOOD_FLOOR = Decimal("3005.06")


@dataclass(frozen=True, slots=True)
class ActivityAsset:
    """One asset in the activity register, acquired through a received invoice."""

    asset_id: str
    kind: str
    method: str
    class_key: str
    coefficient: Decimal
    in_service: date
    basis: Decimal

    @property
    def is_iva_investment_good(self) -> bool:
        """Whether IVA treats the asset as a bien de inversion.

        LIVA art. 108: tangible goods used for more than a year, excluding any
        whose acquisition value does not exceed 3,005.06 EUR. Anything else is an
        ordinary current input for IVA, whatever its income-tax amortization.
        """
        return self.kind == "material" and self.basis > IVA_INVESTMENT_GOOD_FLOOR

    def charge_for(self, year: int) -> Decimal:
        """Linear charge for ``year``: basis x coefficient x days in service / days in year."""
        if year < self.in_service.year:
            return Decimal("0")
        start = self.in_service if year == self.in_service.year else date(year, 1, 1)
        year_days = (date(year + 1, 1, 1) - date(year, 1, 1)).days
        service_days = (date(year + 1, 1, 1) - start).days
        return money(self.basis * self.coefficient * Decimal(service_days) / Decimal(year_days))


ASSETS = (
    ActivityAsset(
        "laptop-2022",
        "material",
        "linear",
        "equipo-proceso-informacion",
        Decimal("0.25"),
        date(2022, 3, 1),
        Decimal("1500.00"),
    ),
    ActivityAsset(
        "furniture-2023", "material", "linear", "mobiliario", Decimal("0.10"), date(2023, 6, 1), Decimal("3600.00")
    ),
    ActivityAsset(
        "software-2024",
        "intangible",
        "linear",
        "intangible-software",
        Decimal("0.33"),
        date(2024, 2, 1),
        Decimal("900.00"),
    ),
    ActivityAsset(
        "machine-2025",
        "material",
        "constant_percentage",
        "maquinaria",
        Decimal("0.30"),
        date(2025, 1, 1),
        Decimal("1000.00"),
    ),
)

#: Issued taxable bases per year and quarter; 2023 is a loss year.
_ISSUED_BASES: dict[int, tuple[Decimal, ...]] = {
    2022: (Decimal("3000"), Decimal("3500"), Decimal("4000"), Decimal("4500")),
    2023: (Decimal("1500"), Decimal("1000"), Decimal("4400"), Decimal("4500")),
    2024: (Decimal("5000"), Decimal("5200"), Decimal("5400"), Decimal("5600")),
    2025: (Decimal("6000"), Decimal("6200"), Decimal("6400"), Decimal("6600")),
}


def _withholding_rate(year: int) -> Decimal:
    """7% in the activity start year and the two following (RIRPF art. 101.5.a)."""
    return NEW_ACTIVITY_WITHHOLDING if year <= ACTIVITY_START.year + 2 else PROFESSIONAL_WITHHOLDING


@dataclass(frozen=True, slots=True)
class YearScenario:
    """Every ledger fact of one tax year."""

    year: int
    issued: tuple[IssuedInvoice, ...]
    received: tuple[ReceivedInvoice, ...]
    reta_months: tuple[date, ...]

    def received_in(self, period: str) -> tuple[ReceivedInvoice, ...]:
        """Received invoices dated in ``period``."""
        return tuple(item for item in self.received if item.period == period)

    def issued_in(self, period: str) -> tuple[IssuedInvoice, ...]:
        """Issued invoices dated in ``period``."""
        return tuple(item for item in self.issued if item.period == period)


def _period_of(day: date) -> str:
    return QUARTERS[(day.month - 1) // 3]


def build_year(year: int) -> YearScenario:
    """Build the stable synthetic ledger facts for ``year``."""
    if year not in YEARS:
        raise ValueError(f"year {year} is outside the scenario years {YEARS}")
    issued = tuple(
        IssuedInvoice(
            key=f"issued-{year}-{period}",
            period=period,
            invoice_date=date(year, _QUARTER_MONTHS[period], 15),
            payment_date=date(year, _QUARTER_MONTHS[period], 20),
            base=base,
            withholding_rate=_withholding_rate(year),
        )
        for period, base in zip(QUARTERS, _ISSUED_BASES[year], strict=True)
    )
    received: list[ReceivedInvoice] = []
    for period in QUARTERS:
        month = _QUARTER_MONTHS[period]
        recurring = (
            ("material", SUPPLIER, "material_oficina", Decimal("150.00"), IVA_GENERAL, WithholdingDuty.NONE),
            ("software", SOFTWARE_VENDOR, "software_suscripcion", Decimal("60.00"), IVA_GENERAL, WithholdingDuty.NONE),
            ("adviser", ADVISER, "asesoria_fiscal", Decimal("300.00"), IVA_GENERAL, WithholdingDuty.PROFESSIONAL),
            ("rent", LANDLORD, "arrendamiento_local", Decimal("900.00"), IVA_GENERAL, WithholdingDuty.URBAN_RENT),
        )
        for name, counterparty, category, base, rate, duty in recurring:
            received.append(
                ReceivedInvoice(
                    key=f"{name}-{year}-{period}",
                    period=period,
                    counterparty=counterparty,
                    category=category,
                    invoice_date=date(year, month, 5),
                    payment_date=date(year, month, 8),
                    base=base,
                    iva_rate=rate,
                    duty=duty,
                )
            )
    received.append(
        ReceivedInvoice(
            key=f"insurance-{year}",
            period="1T",
            counterparty=INSURER,
            category="seguros_responsabilidad_civil",
            invoice_date=date(year, 1, 10),
            payment_date=date(year, 1, 12),
            base=Decimal("480.00"),
            iva_rate=Decimal("0"),
        )
    )
    if year == 2023:
        received.append(
            ReceivedInvoice(
                key="training-2023",
                period="2T",
                counterparty=SUPPLIER,
                category="formacion_profesional",
                invoice_date=date(2023, 5, 12),
                payment_date=date(2023, 5, 14),
                base=Decimal("2000.00"),
                iva_rate=IVA_GENERAL,
            )
        )
    for asset in ASSETS:
        if asset.in_service.year == year:
            received.append(
                ReceivedInvoice(
                    key=f"asset-{asset.asset_id}",
                    period=_period_of(asset.in_service),
                    counterparty=SOFTWARE_VENDOR if asset.kind == "intangible" else SUPPLIER,
                    category="hardware_amortizable" if asset.kind != "intangible" else "software_suscripcion",
                    invoice_date=asset.in_service,
                    payment_date=asset.in_service,
                    base=asset.basis,
                    iva_rate=IVA_GENERAL,
                    asset_id=asset.asset_id,
                )
            )
    reta_months = tuple(date(year, month, 28) for month in range(1, 13))
    return YearScenario(year=year, issued=issued, received=tuple(received), reta_months=reta_months)


@dataclass(frozen=True, slots=True)
class M303QuarterOracle:
    """Hand arithmetic for one ordinary Modelo 303 quarter before compensation."""

    period: str
    devengado: Decimal
    #: Input IVA on current purchases (Modelo 303 operaciones interiores corrientes).
    deducible_current: Decimal
    #: Input IVA on bienes de inversion (Modelo 303 operaciones interiores con bienes de inversion).
    deducible_investment: Decimal

    @property
    def deducible(self) -> Decimal:
        """All deductible input IVA of the quarter."""
        return self.deducible_current + self.deducible_investment

    @property
    def quarter_result(self) -> Decimal:
        """Devengado less deducible, before compensation."""
        return self.devengado - self.deducible


def m303_quarter(year: int, period: str) -> M303QuarterOracle:
    """Output IVA on issued invoices less input IVA on received invoices of the quarter."""
    scenario = build_year(year)
    investment_ids = {asset.asset_id for asset in ASSETS if asset.is_iva_investment_good}
    received = scenario.received_in(period)
    return M303QuarterOracle(
        period=period,
        devengado=sum((item.iva for item in scenario.issued_in(period)), Decimal("0")),
        deducible_current=sum((item.iva for item in received if item.asset_id not in investment_ids), Decimal("0")),
        deducible_investment=sum((item.iva for item in received if item.asset_id in investment_ids), Decimal("0")),
    )


def _m303_compensation_chain(year: int) -> tuple[tuple[Decimal, Decimal], ...]:
    """(result after compensation, cuotas left to compensate) for each quarter of ``year``.

    A negative quarter is compensated in later periods (LIVA art. 99.5). The
    activity start year opens with nothing to compensate; any later year opens
    with what the previous year's last quarter left pending.
    """
    pending = Decimal("0") if year == ACTIVITY_START.year else m303_compensation_pending_after(year - 1, QUARTERS[-1])
    chain: list[tuple[Decimal, Decimal]] = []
    for period in QUARTERS:
        net = m303_quarter(year, period).quarter_result - pending
        pending = -net if net < 0 else Decimal("0")
        chain.append((max(net, Decimal("0")), pending))
    return tuple(chain)


def m303_compensation_pending_after(year: int, period: str) -> Decimal:
    """Cuotas a compensar that quarter ``period`` of ``year`` leaves for later periods.

    A quarter whose result, after applying what earlier quarters left, is a
    result a ingresar leaves a proven zero, never an unknown.
    """
    return _m303_compensation_chain(year)[QUARTERS.index(period)][1]


def m303_results_with_compensation(year: int) -> tuple[Decimal, ...]:
    """Quarter results after carrying negative results forward inside the year.

    A negative quarter is compensated in later quarters (LIVA art. 99.5). The
    scenario keeps every year's fourth quarter non-negative, so no carry crosses
    into the next year.
    """
    chain = _m303_compensation_chain(year)
    pending = chain[-1][1]
    if pending:
        raise ValueError(f"scenario year {year} leaves {pending} IVA to compensate across years")
    return tuple(result for result, _pending in chain)


def withholding_practised(year: int, period: str, duty: WithholdingDuty) -> tuple[Decimal, Decimal, int]:
    """(base, withholding, recipients) the declarant practised in one quarter for one periodic return."""
    items = tuple(item for item in build_year(year).received_in(period) if item.duty is duty)
    return (
        sum((item.base for item in items), Decimal("0")),
        sum((item.withholding for item in items), Decimal("0")),
        len({item.counterparty.tax_id for item in items}),
    )


@dataclass(frozen=True, slots=True)
class ActivityYearOracle:
    """Annual activity totals from ledger facts and the asset register."""

    income: Decimal
    invoiced_expenses: Decimal
    reta: Decimal
    amortization: Decimal
    withholding_suffered: Decimal

    @property
    def net(self) -> Decimal:
        """Net activity yield: income less every deductible expense."""
        return self.income - self.invoiced_expenses - self.reta - self.amortization


def activity_year(year: int) -> ActivityYearOracle:
    """Activity income and deductible expenses of ``year`` (assets amortized, not expensed)."""
    scenario = build_year(year)
    return ActivityYearOracle(
        income=sum((item.base for item in scenario.issued), Decimal("0")),
        invoiced_expenses=sum((item.base for item in scenario.received if item.asset_id is None), Decimal("0")),
        reta=RETA_MONTHLY * len(scenario.reta_months),
        amortization=sum((asset.charge_for(year) for asset in ASSETS), Decimal("0")),
        withholding_suffered=sum((item.withholding for item in scenario.issued), Decimal("0")),
    )


__all__ = [
    "ACTIVITY_START",
    "ADVISER",
    "ASSETS",
    "CLIENT",
    "INSURER",
    "IVA_INVESTMENT_GOOD_FLOOR",
    "LANDLORD",
    "QUARTERS",
    "SCENARIO_VERSION",
    "SOFTWARE_VENDOR",
    "SUPPLIER",
    "TAXPAYER_TAX_ID",
    "YEARS",
    "ActivityAsset",
    "ActivityYearOracle",
    "Counterparty",
    "IssuedInvoice",
    "M303QuarterOracle",
    "ReceivedInvoice",
    "WithholdingDuty",
    "YearScenario",
    "activity_year",
    "build_year",
    "m303_compensation_pending_after",
    "m303_quarter",
    "m303_results_with_compensation",
    "money",
    "withholding_practised",
]
