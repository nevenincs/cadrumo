"""Versioned synthetic inputs and independent arithmetic for RETENCIONES-01."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

BRIEF_ID = "RETENCIONES-01"
BRIEF_REVISION = "0.1"
PATTERN_ID = "ACCEPTANCE-01"
PATTERN_REVISION = "1.1"
SCENARIO_VERSION = "retenciones-resident-common-regime-v1"
SUPPORTED_YEAR = 2025
CENT = Decimal("0.01")


class EvidenceState(StrEnum):
    """States that acceptance must never collapse into one another."""

    MISSING = "missing"
    ZERO_WITH_RELEVANT_PAYMENT = "zero_with_relevant_payment"
    NO_RELEVANT_PAYMENT = "no_relevant_payment"
    NOT_APPLICABLE = "not_applicable"
    AVAILABLE = "available"


class Direction(StrEnum):
    """Whether the autonomo pays or suffers the withholding."""

    PAID_FOR_RECIPIENT = "paid_for_recipient"
    SUFFERED_ON_OWN_SALE = "suffered_on_own_sale"


@dataclass(frozen=True, slots=True)
class Payment:
    """One independently declared payment fact and its source identity."""

    source_id: str
    recipient_id: str
    recipient_name: str
    modelo: str
    annual_modelo: str
    scheme: str
    invoice_date: date
    paid_on: date
    taxable_base: Decimal
    withheld: Decimal
    direction: Direction = Direction.PAID_FOR_RECIPIENT
    annual_key: str | None = None
    annual_subkey: str | None = None
    property_reference: str | None = None

    @property
    def period(self) -> str:
        """Return the calendar quarter determined by payment, not invoice date."""
        return f"{((self.paid_on.month - 1) // 3) + 1}T"


@dataclass(frozen=True, slots=True)
class PeriodicOracle:
    """Expected periodic totals calculated only from scenario constants."""

    modelo: str
    period: str
    payment_count: int
    recipient_count: int
    taxable_base: Decimal
    withheld: Decimal


@dataclass(frozen=True, slots=True)
class AnnualOracle:
    """Expected annual control totals and substantive detail cardinality."""

    modelo: str
    recipient_count: int
    detail_record_count: int
    taxable_base: Decimal
    withheld: Decimal


@dataclass(frozen=True, slots=True)
class RetencionesScenario:
    """One source definition shared by every frontend path."""

    year: int
    payments: tuple[Payment, ...]
    own_sale_withholding: Payment
    nonresident_boundary: Payment
    missing_state: EvidenceState
    no_activity_state: EvidenceState
    periodic_oracle: tuple[PeriodicOracle, ...]
    annual_oracle: tuple[AnnualOracle, ...]
    revisions: tuple[tuple[str, str], ...]


def money(value: Decimal) -> Decimal:
    """Round fixture arithmetic to euro cents without product code."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _periodic_oracle(payments: tuple[Payment, ...]) -> tuple[PeriodicOracle, ...]:
    keys = sorted({(row.modelo, row.period) for row in payments if row.direction is Direction.PAID_FOR_RECIPIENT})
    result: list[PeriodicOracle] = []
    for modelo, period in keys:
        rows = tuple(
            row
            for row in payments
            if row.modelo == modelo and row.period == period and row.direction is Direction.PAID_FOR_RECIPIENT
        )
        result.append(
            PeriodicOracle(
                modelo=modelo,
                period=period,
                payment_count=len(rows),
                recipient_count=len({row.recipient_id for row in rows}),
                taxable_base=money(sum((row.taxable_base for row in rows), Decimal("0"))),
                withheld=money(sum((row.withheld for row in rows), Decimal("0"))),
            )
        )
    return tuple(result)


def _annual_oracle(payments: tuple[Payment, ...]) -> tuple[AnnualOracle, ...]:
    result: list[AnnualOracle] = []
    for modelo in ("180", "190", "193"):
        rows = tuple(
            row for row in payments if row.annual_modelo == modelo and row.direction is Direction.PAID_FOR_RECIPIENT
        )
        detail_keys = {
            (row.recipient_id, row.property_reference)
            if modelo == "180"
            else (row.recipient_id, row.annual_key, row.annual_subkey)
            for row in rows
        }
        result.append(
            AnnualOracle(
                modelo=modelo,
                recipient_count=len({row.recipient_id for row in rows}),
                detail_record_count=len(detail_keys),
                taxable_base=money(sum((row.taxable_base for row in rows), Decimal("0"))),
                withheld=money(sum((row.withheld for row in rows), Decimal("0"))),
            )
        )
    return tuple(result)


def build_scenario(year: int = SUPPORTED_YEAR) -> RetencionesScenario:
    """Build the pinned resident/common-regime withholding scenario.

    The professional 15% and urban-rental 19% rates are grounded in RIRPF
    arts. 95 and 100. The payroll percentage is an independently supplied
    payroll fact, not a rate engine. Capital income is deliberately scoped to
    the supported 123/193 branch and uses a supplied 19% payment fact.
    """
    if year != SUPPORTED_YEAR:
        raise ValueError(f"{SCENARIO_VERSION} is grounded only for {SUPPORTED_YEAR}")

    payments = (
        Payment(
            source_id="professional-q1",
            recipient_id="00000000T",
            recipient_name="Professional One",
            modelo="111",
            annual_modelo="190",
            scheme="actividades_profesionales",
            invoice_date=date(year, 3, 15),
            paid_on=date(year, 3, 31),
            taxable_base=Decimal("1000"),
            withheld=Decimal("150"),
            annual_key="G",
            annual_subkey="01",
        ),
        Payment(
            source_id="professional-cross-quarter",
            recipient_id="00000000T",
            recipient_name="Professional One",
            modelo="111",
            annual_modelo="190",
            scheme="actividades_profesionales",
            invoice_date=date(year, 3, 31),
            paid_on=date(year, 4, 2),
            taxable_base=Decimal("500"),
            withheld=Decimal("75"),
            annual_key="G",
            annual_subkey="01",
        ),
        Payment(
            source_id="payroll-q1",
            recipient_id="00000001R",
            recipient_name="Employee One",
            modelo="111",
            annual_modelo="190",
            scheme="rendimientos_trabajo",
            invoice_date=date(year, 3, 31),
            paid_on=date(year, 3, 31),
            taxable_base=Decimal("2000"),
            withheld=Decimal("240"),
            annual_key="A",
            annual_subkey="01",
        ),
        Payment(
            source_id="professional-zero-q4",
            recipient_id="00000002W",
            recipient_name="Professional Zero",
            modelo="111",
            annual_modelo="190",
            scheme="actividades_profesionales",
            invoice_date=date(year, 11, 15),
            paid_on=date(year, 11, 30),
            taxable_base=Decimal("500"),
            withheld=Decimal("0"),
            annual_key="G",
            annual_subkey="01",
        ),
        Payment(
            source_id="rent-property-a-q1",
            recipient_id="00000003A",
            recipient_name="Landlord One",
            modelo="115",
            annual_modelo="180",
            scheme="arrendamiento_urbano",
            invoice_date=date(year, 3, 1),
            paid_on=date(year, 3, 5),
            taxable_base=Decimal("3000"),
            withheld=Decimal("570"),
            property_reference="1234567VK4713C0001XY",
        ),
        Payment(
            source_id="rent-property-b-q2",
            recipient_id="00000003A",
            recipient_name="Landlord One",
            modelo="115",
            annual_modelo="180",
            scheme="arrendamiento_urbano",
            invoice_date=date(year, 6, 1),
            paid_on=date(year, 6, 5),
            taxable_base=Decimal("2000"),
            withheld=Decimal("380"),
            property_reference="9872023VH5797S0001WX",
        ),
        Payment(
            source_id="capital-q3",
            recipient_id="00000004G",
            recipient_name="Capital Recipient",
            modelo="123",
            annual_modelo="193",
            scheme="intereses",
            invoice_date=date(year, 8, 1),
            paid_on=date(year, 8, 15),
            taxable_base=Decimal("1000"),
            withheld=Decimal("190"),
            annual_key="B",
            annual_subkey="01",
        ),
    )
    own_sale = Payment(
        source_id="own-sale-withholding",
        recipient_id="12345678Z",
        recipient_name="Synthetic Autonomo",
        modelo="111",
        annual_modelo="190",
        scheme="actividades_profesionales",
        invoice_date=date(year, 2, 1),
        paid_on=date(year, 2, 10),
        taxable_base=Decimal("1000"),
        withheld=Decimal("150"),
        direction=Direction.SUFFERED_ON_OWN_SALE,
        annual_key="G",
        annual_subkey="01",
    )
    nonresident = Payment(
        source_id="nonresident-boundary",
        recipient_id="X0000000T",
        recipient_name="Nonresident Recipient",
        modelo="216",
        annual_modelo="296",
        scheme="nonresident_unscoped",
        invoice_date=date(year, 9, 1),
        paid_on=date(year, 9, 5),
        taxable_base=Decimal("1000"),
        withheld=Decimal("190"),
    )
    return RetencionesScenario(
        year=year,
        payments=payments,
        own_sale_withholding=own_sale,
        nonresident_boundary=nonresident,
        missing_state=EvidenceState.MISSING,
        no_activity_state=EvidenceState.NO_RELEVANT_PAYMENT,
        periodic_oracle=_periodic_oracle(payments),
        annual_oracle=_annual_oracle(payments),
        revisions=(
            ("111", "2019-y-siguientes"),
            ("115", "2019-y-siguientes"),
            ("123", "2024-y-siguientes"),
            ("180", "2023-y-siguientes"),
            ("190", "2025-y-siguientes"),
            ("193", "2025-y-siguientes"),
        ),
    )
