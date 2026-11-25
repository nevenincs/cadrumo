"""Two salaried savers calculate, verify and export a Modelo 100 whose savings boxes and detail records are hand-worked.

The depositor holds a savings account and a term deposit at one bank and half of a
deposit at another; the shareholder holds shares of three Spanish issuers in one
securities account and pays a half-yearly custody fee for each. Every interest or
dividend payment is a whole number of euros gross, so its 19 % withholding is exact
to the cent and the bank credits 81 % of it; the ledger holds those net credits and
the fees, the payer certificates hold each payer's gross and withholding.

Sources of the hand figures:
- LIRPF art. 25.1.a (dividends) and 25.2 (interest of accounts and deposits) are
  integrated gross, without deducting the withholding (Manual práctico de Renta,
  capítulo 4, "Rendimientos del capital mobiliario", casillas 0027 and 0029:
  "sin descontar la retención practicada sobre dicho rendimiento").
- LIRPF art. 26.1.a: only the administration and custody fees of valores
  negociables are deductible (casilla 0037).
- RIRPF art. 90.1: the withholding on rendimientos del capital mobiliario is
  19 %, applied to the full consideration (RIRPF art. 93.1); the payer certifies
  the holder's share of gross and withholding (RIRPF art. 108.3).
- LIRPF arts. 46.b and 49.1.a: the net capital mobiliario of these kinds forms the
  savings base; art. 56.2: the mínimo personal goes first to the general base.
- LIRPF arts. 66.1 and 76: the state and the autonomic savings scales are 9.5 %
  each up to 6000.00.
- LIRPF art. 79: the withholding suffered is deducted from the cuota (casilla 0597).
- LIRPF art. 17, 19.2.f and 20: work income, the 2000.00 of otros gastos, and no
  art. 20 reduction above a neto previo of 19747.50.

Real encrypted store, real registered certificate operation, real calculate,
verify and export; the detail records are read back through the edition's XML
input dictionary and XSD.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.capital_mobiliario_position_bindings import CapitalMobiliarioQuantity
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.transactions.enums import TransactionDirection

from .m100_saver_support import (
    LinkedRow,
    SavingsPosition,
    detail_records,
    position_facts,
    savings_carries_stated_zero,
    seed_linked_rows,
)
from .m130_m100_annual_support import BUCKET_ID, YEAR
from .renta_persona_support import (
    PAYER_A,
    Persona,
    calculate_annual,
    record_certificate,
    register_refund_account,
    seed_profile,
    verify_and_export,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

__all__ = ["secure_objects"]

_SAVER = Persona(categories="trabajo,capital_mobiliario")

# Synthetic CIFs of sociedades anónimas from the generic test pool (counters 1101 to 1105). With the counter
# 000110d, the even positions add 0 + 1 + 0 = 1 and the odd positions double to 0 + 0 + 2 + (2d digit-summed),
# so the control is (10 - (3 + 2d digit-summed)) mod 10: 5 for 1, 3 for 2, 1 for 3, 9 for 4, 6 for 5.
_BANK_MERIDIANO = "A00011015"
_BANK_ALCOTAN = "A00011023"
_ISSUER_MONCAYO = "A00011031"
_ISSUER_FINISTERRE = "A00011049"
_ISSUER_VEGA = "A00011056"

_GROSS = CapitalMobiliarioQuantity.GROSS.value
_WITHHELD = CapitalMobiliarioQuantity.WITHHOLDING.value
_EXPENSES = CapitalMobiliarioQuantity.EXPENSES.value
_INTEREST_RECORD = "RegistroB11"
_DIVIDEND_RECORD = "RegistroB13"


@pytest.fixture
def bucket_id() -> str:
    return BUCKET_ID


def _calculate(
    objects: SecureObjectRepository,
    directory: Path,
    operation: PinnedAuthorityOperation,
    *,
    positions: dict[str, SavingsPosition],
    rows: tuple[LinkedRow, ...],
    work: tuple[str, str],
    payers: tuple[tuple[str, str, str], ...],
) -> CalculationRevision:
    """Seed the saver's profile, certificates and linked rows, then calculate the annual return."""
    seed_profile(_SAVER, extra_facts=position_facts(positions))
    integro, retencion = work
    record_certificate(
        operation,
        directory=directory,
        payer=PAYER_A,
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion=retencion,
        importe_integro=integro,
    )
    for payer, payer_integro, payer_retencion in payers:
        record_certificate(
            operation,
            directory=directory,
            payer=payer,
            income_class=RetencionSoportadaClase.CAPITAL_MOBILIARIO,
            retencion=payer_retencion,
            importe_integro=payer_integro,
        )
    seed_linked_rows(objects, rows)
    register_refund_account(objects)
    return calculate_annual(objects, binding_values=savings_carries_stated_zero(operation))


def _boxes(revision: CalculationRevision, expected: dict[str, str]) -> dict[str, Decimal | None]:
    """The calculated value of each expected casilla, ``None`` where the calculation left it open."""
    found: dict[str, Decimal | None] = {}
    for casilla in expected:
        value = revision.casilla_values.get(validated_casilla_id(casilla))
        found[casilla] = None if value is None else Decimal(str(value))
    return found


def _as_decimals(expected: dict[str, str]) -> dict[str, Decimal | None]:
    return {casilla: Decimal(amount) for casilla, amount in expected.items()}


def _sorted(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: Decimal(row[_GROSS]))


# -- The depositor -----------------------------------------------------------------------------------------------

_DEPOSITOR_POSITIONS = {
    # A savings account held alone for years.
    "0": SavingsPosition("cuenta", _BANK_MERIDIANO, "Banco Meridiano de Ahorro", "100.00", date(YEAR - 9, 3, 2)),
    # A one-year deposit at the same bank, paid at maturity on 15 October.
    "1": SavingsPosition(
        "deposito", _BANK_MERIDIANO, "Banco Meridiano de Ahorro", "100.00", date(YEAR - 1, 10, 15), date(YEAR, 10, 15)
    ),
    # A six-month deposit held half and half with her sister, paid at maturity on 30 June into the joint account.
    "2": SavingsPosition(
        "deposito", _BANK_ALCOTAN, "Banco Alcotan de Depositos", "50.00", date(YEAR - 1, 12, 30), date(YEAR, 6, 30)
    ),
}

# Net credits, each 81 % of a whole-euro gross (RIRPF art. 90.1, 19 % withheld):
#   account   31.00 -> 25.11, 29.00 -> 23.49, 33.00 -> 26.73, 27.00 -> 21.87: gross 120.00, withheld 22.80, net 97.20
#   deposit   900.00 -> 729.00: withheld 171.00
#   joint     1600.00 -> 1296.00: withheld 304.00; her half is 800.00 gross, 152.00 withheld, 648.00 net
_DEPOSITOR_ROWS = (
    LinkedRow("aho-int-03", "0", "intereses", "25.11", date(YEAR, 3, 31)),
    LinkedRow("aho-int-06", "0", "intereses", "23.49", date(YEAR, 6, 30)),
    LinkedRow("aho-int-09", "0", "intereses", "26.73", date(YEAR, 9, 30)),
    LinkedRow("aho-int-12", "0", "intereses", "21.87", date(YEAR, 12, 31)),
    LinkedRow("aho-dep-10", "1", "intereses", "729.00", date(YEAR, 10, 15)),
    LinkedRow("aho-dep-06", "2", "intereses", "1296.00", date(YEAR, 6, 30)),
)

# Each bank's certificate (RIRPF art. 108.3): Banco Meridiano 120.00 + 900.00 = 1020.00 gross and
# 22.80 + 171.00 = 193.80 withheld (check: net 97.20 + 729.00 + 193.80 = 1020.00); Banco Alcotán her half,
# 800.00 and 152.00 (check: 1296.00 x 50 % + 152.00 = 800.00).
_DEPOSITOR_PAYERS = ((_BANK_MERIDIANO, "1020.00", "193.80"), (_BANK_ALCOTAN, "800.00", "152.00"))

# Work certificate: 28000.00 gross, 4480.00 withheld (16 %), no Social Security stated on it.
_DEPOSITOR_WORK = ("28000.00", "4480.00")

_DEPOSITOR_BOXES = {
    # 0027 intereses (LIRPF art. 25.2, gross): 120.00 + 900.00 + 800.00 = 1820.00.
    "0027": "1820.00",
    # 0029 dividendos: none.
    "0029": "0.00",
    # 0036 total ingresos íntegros = 1820.00.
    "0036": "1820.00",
    # 0037 custody fees of valores negociables (LIRPF art. 26.1.a): she holds none.
    "0037": "0.00",
    # 0038 rendimiento neto = 1820.00 - 0.00; 0041 after no art. 26.2 reduction.
    "0038": "1820.00",
    "0041": "1820.00",
    # 0429 saldo neto positivo to the savings base (LIRPF art. 49.1.a).
    "0429": "1820.00",
    # 0460 base imponible del ahorro: no gains or losses, no carry pending (stated 0.00).
    "0460": "1820.00",
    # 0510 base liquidable del ahorro: no general-base remanente (LIRPF art. 50).
    "0510": "1820.00",
    # 0435 base imponible general: work 28000.00 - otros gastos 2000.00 (art. 19.2.f); no art. 20 reduction above
    # 19747.50 of neto previo.
    "0435": "26000.00",
    # 0522 mínimo to the savings base: 5550.00 (art. 57) is absorbed by the general base 26000.00 (art. 56.2).
    "0522": "0.00",
    # 0540 / 0541 cuota on the savings base: 1820.00 x 9.5 % = 172.90 each (LIRPF arts. 66.1 and 76).
    "0540": "172.90",
    "0541": "172.90",
    # 0596 work withholding; 0597 capital mobiliario withholding: 193.80 + 152.00 = 345.80 (LIRPF art. 79).
    "0596": "4480.00",
    "0597": "345.80",
}

# One RegistroB11 occurrence per position. The Meridiano payer feeds two occurrences, so each gross is the
# position's net over 81 % and its withholding 19 % of that gross: 97.20 / 0.81 = 120.00 -> 22.80, and
# 729.00 / 0.81 = 900.00 -> 171.00, which add up to the certified 193.80. The joint deposit is its payer's only
# occurrence: her share of the cash 648.00 plus the certified 152.00 = 800.00. No expense is written.
_DEPOSITOR_RECORDS = {
    _INTEREST_RECORD: [
        {_GROSS: "120.00", _WITHHELD: "22.80"},
        {_GROSS: "800.00", _WITHHELD: "152.00"},
        {_GROSS: "900.00", _WITHHELD: "171.00"},
    ],
}


def test_the_depositor_exports_one_interest_record_per_position(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    revision = _calculate(
        secure_objects,
        tmp_path,
        operation,
        positions=_DEPOSITOR_POSITIONS,
        rows=_DEPOSITOR_ROWS,
        work=_DEPOSITOR_WORK,
        payers=_DEPOSITOR_PAYERS,
    )
    assert _boxes(revision, _DEPOSITOR_BOXES) == _as_decimals(_DEPOSITOR_BOXES)

    payload = verify_and_export(revision, secure_objects, tmp_path / "modelo-100.xml", _SAVER)

    written = {record: _sorted(rows) for record, rows in detail_records(operation, payload).items() if rows}
    assert written == _DEPOSITOR_RECORDS, written


# -- The shareholder ---------------------------------------------------------------------------------------------

_SHAREHOLDER_POSITIONS = {
    "0": SavingsPosition(
        "valores_negociables", _ISSUER_MONCAYO, "Energias Renovables Moncayo", "100.00", date(YEAR - 8, 5, 12)
    ),
    "1": SavingsPosition(
        "valores_negociables",
        _ISSUER_FINISTERRE,
        "Infraestructuras Portuarias Finisterre",
        "100.00",
        date(YEAR - 5, 2, 3),
    ),
    "2": SavingsPosition(
        "valores_negociables", _ISSUER_VEGA, "Alimentacion Vega del Segura", "100.00", date(YEAR - 3, 9, 18)
    ),
}

_FEE = TransactionDirection.OUTGOING

# Net dividends, each 81 % of a whole-euro gross (RIRPF art. 90.1):
#   Moncayo     180.00 -> 145.80, 220.00 -> 178.20: gross 400.00, withheld 76.00, net 324.00
#   Finisterre  650.00 -> 526.50: withheld 123.50
#   Vega        4 x (75.00 -> 60.75): gross 300.00, withheld 57.00, net 243.00
# Custody fees per security and half-year, IVA included (10.00, 15.00 and 5.00 plus 21 %): 12.10, 18.15, 6.05.
_SHAREHOLDER_ROWS = (
    LinkedRow("acc-div-e1", "0", "dividendos", "145.80", date(YEAR, 1, 15)),
    LinkedRow("acc-div-e2", "0", "dividendos", "178.20", date(YEAR, 7, 15)),
    LinkedRow("acc-cus-e06", "0", "gasto_administracion_deposito", "12.10", date(YEAR, 6, 30), _FEE),
    LinkedRow("acc-cus-e12", "0", "gasto_administracion_deposito", "12.10", date(YEAR, 12, 31), _FEE),
    LinkedRow("acc-div-i1", "1", "dividendos", "526.50", date(YEAR, 5, 20)),
    LinkedRow("acc-cus-i06", "1", "gasto_administracion_deposito", "18.15", date(YEAR, 6, 30), _FEE),
    LinkedRow("acc-cus-i12", "1", "gasto_administracion_deposito", "18.15", date(YEAR, 12, 31), _FEE),
    LinkedRow("acc-div-a03", "2", "dividendos", "60.75", date(YEAR, 3, 10)),
    LinkedRow("acc-div-a06", "2", "dividendos", "60.75", date(YEAR, 6, 10)),
    LinkedRow("acc-div-a09", "2", "dividendos", "60.75", date(YEAR, 9, 10)),
    LinkedRow("acc-div-a12", "2", "dividendos", "60.75", date(YEAR, 12, 10)),
    LinkedRow("acc-cus-a06", "2", "gasto_administracion_deposito", "6.05", date(YEAR, 6, 30), _FEE),
    LinkedRow("acc-cus-a12", "2", "gasto_administracion_deposito", "6.05", date(YEAR, 12, 31), _FEE),
)

# Each issuer's certificate: Moncayo 400.00 / 76.00 (324.00 + 76.00 = 400.00); Finisterre 650.00 / 123.50
# (526.50 + 123.50 = 650.00); Vega 300.00 / 57.00 (243.00 + 57.00 = 300.00).
_SHAREHOLDER_PAYERS = (
    (_ISSUER_MONCAYO, "400.00", "76.00"),
    (_ISSUER_FINISTERRE, "650.00", "123.50"),
    (_ISSUER_VEGA, "300.00", "57.00"),
)

# Work certificate: 42000.00 gross, 8400.00 withheld (20 %), no Social Security stated on it.
_SHAREHOLDER_WORK = ("42000.00", "8400.00")

_SHAREHOLDER_BOXES = {
    # 0027 intereses: none.
    "0027": "0.00",
    # 0029 dividendos (LIRPF art. 25.1.a, gross): 400.00 + 650.00 + 300.00 = 1350.00.
    "0029": "1350.00",
    "0036": "1350.00",
    # 0037 custody fees (LIRPF art. 26.1.a): 2 x 12.10 + 2 x 18.15 + 2 x 6.05 = 24.20 + 36.30 + 12.10 = 72.60.
    "0037": "72.60",
    # 0038 rendimiento neto = 1350.00 - 72.60 = 1277.40; 0041 after no art. 26.2 reduction.
    "0038": "1277.40",
    "0041": "1277.40",
    "0429": "1277.40",
    "0460": "1277.40",
    "0510": "1277.40",
    # 0435 base imponible general: 42000.00 - 2000.00 = 40000.00; no art. 20 reduction.
    "0435": "40000.00",
    "0522": "0.00",
    # 0540 / 0541: 1277.40 x 9.5 % = 121.353, rounded to 121.35 each.
    "0540": "121.35",
    "0541": "121.35",
    # 0597: 76.00 + 123.50 + 57.00 = 256.50.
    "0596": "8400.00",
    "0597": "256.50",
}

# One RegistroB13 occurrence per issuer, each its payer's only one: gross = net + certified withholding, and the
# fees of that security as IMP3. No interest record is written.
_SHAREHOLDER_RECORDS = {
    _DIVIDEND_RECORD: [
        {_GROSS: "300.00", _WITHHELD: "57.00", _EXPENSES: "12.10"},
        {_GROSS: "400.00", _WITHHELD: "76.00", _EXPENSES: "24.20"},
        {_GROSS: "650.00", _WITHHELD: "123.50", _EXPENSES: "36.30"},
    ],
}


def test_the_shareholder_exports_one_dividend_record_per_issuer_with_its_custody_fees(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    revision = _calculate(
        secure_objects,
        tmp_path,
        operation,
        positions=_SHAREHOLDER_POSITIONS,
        rows=_SHAREHOLDER_ROWS,
        work=_SHAREHOLDER_WORK,
        payers=_SHAREHOLDER_PAYERS,
    )
    assert _boxes(revision, _SHAREHOLDER_BOXES) == _as_decimals(_SHAREHOLDER_BOXES)

    payload = verify_and_export(revision, secure_objects, tmp_path / "modelo-100.xml", _SAVER)

    written = {record: _sorted(rows) for record, rows in detail_records(operation, payload).items() if rows}
    assert written == _SHAREHOLDER_RECORDS, written
