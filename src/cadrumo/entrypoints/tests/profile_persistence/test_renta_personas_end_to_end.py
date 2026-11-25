"""The employee, employee-autonomo and payer personas, from registered operations to exported bytes.

Every payer certificate and absence attestation is recorded through its registered
operation over the real encrypted store, and the annual Modelo 100 is calculated,
verified and exported over the published authority. Each expected figure is worked
by hand from the rules below; none is read back from a run.

Employee. Two employers certify what they withheld (RIRPF art. 108.3 makes the
payer's certificate the evidence of the retention). The credit of casilla 0596 is
each certificate's retencion plus its ingreso a cuenta in full, passed on to the
taxpayer or not (LIRPF arts. 79.e and 99.6):

    employer A   retencion 3.120,00
    employer B   retencion   600,00 + ingreso a cuenta 200,00 (passed on in full)
    0596         3.120,00 + 600,00 + 200,00 = 3.920,00

The taxpayer also declares movable-capital income, on which no Spanish payer
withheld: the credit of casilla 0597 is a proven zero only because the taxpayer
attests it, and stays unresolved without the attestation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.tests.retencion_observation_authoring import replace_retencion_observations
from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.aggregation.retenciones import RetencionObservation
from cadrumo.application.modelo.calculation_note_gate import ModeloCalculationBlockedError, blocking_calculation_issues
from cadrumo.core.aggregation import AggregationCaptureKind, BindingSourceKind, RetencionScheme
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.calculation_revision import CalculationRevision

from .m130_m100_annual_support import BUCKET_ID, import_official_m130_result_observation, seed_prior_year_m100
from .renta_persona_support import (
    ACTIVITY_KEY,
    ACTIVITY_KEY_CASILLA,
    PAYER_A,
    PAYER_B,
    ActivityExpense,
    ActivityInvoice,
    Persona,
    attest_no_withholding,
    calculate_and_file_quarter,
    calculate_annual,
    record_certificate,
    register_refund_account,
    seed_activity_ledger,
    seed_profile,
    verify_and_export,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return BUCKET_ID


def _box(revision: CalculationRevision, casilla: str) -> Decimal:
    return Decimal(revision.casilla_values[validated_casilla_id(casilla)])


_EMPLOYEE = Persona(categories="trabajo,capital_mobiliario")


def _record_employers(operation: PinnedAuthorityOperation, directory: Path) -> None:
    record_certificate(
        operation,
        directory=directory,
        payer=PAYER_A,
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion="3120.00",
        importe_integro="24000.00",
    )
    record_certificate(
        operation,
        directory=directory,
        payer=PAYER_B,
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion="600.00",
        ingreso_a_cuenta="200.00",
        repercutido="200.00",
        importe_integro="6000.00",
        valoracion_especie="1000.00",
    )


def test_employee_credits_the_certified_retention_and_cannot_export_an_undisclosed_capital_income(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    seed_profile(_EMPLOYEE)
    seed_prior_year_m100(secure_objects)
    _record_employers(operation, tmp_path)
    attest_no_withholding(operation, RetencionSoportadaClase.CAPITAL_MOBILIARIO)
    register_refund_account(secure_objects)

    annual = calculate_annual(secure_objects)

    # oracle: Ley 35/2006 arts. 79.e and 99.6 with Reglamento del IRPF art. 108.3: 3.120,00 + 600,00 + 200,00.
    assert _box(annual, "0596") == Decimal("3920.00")
    # The attested class is a proven zero, and no activity, rental or gain credit exists for this taxpayer.
    assert [_box(annual, casilla) for casilla in ("0597", "0598", "0599", "0603", "0604")] == [Decimal("0")] * 5
    # oracle: Ley 35/2006 art. 99.1: 0609 totals the pagos a cuenta, here the work credit alone.
    assert _box(annual, "0609") == Decimal("3920.00")
    # oracle: Modelo 100 casilla 0007 = 0004 + 0005 - 0006 = 1.000,00 + 200,00 - 200,00.
    assert _box(annual, "0007") == Decimal("1000.00")

    # The persona declares movable-capital income but holds no savings position, so that income is unknown
    # and is never read as zero: verifying, and so exporting, is refused for the undisclosed family.
    with pytest.raises(ModeloCalculationBlockedError) as refused:
        verify_and_export(annual, secure_objects, tmp_path / "modelo-100-employee.xml", _EMPLOYEE)
    assert refused.value.context is not None
    assert refused.value.context["reason"] == "income_family_not_computed"
    assert refused.value.context["source_ref"] == "income-family:capital_mobiliario"
    assert not (tmp_path / "modelo-100-employee.xml").exists()


def test_the_unattested_movable_capital_credit_stays_unresolved(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Without payer records or an attestation, a declared class is unresolved: never read as zero."""
    seed_profile(_EMPLOYEE)
    seed_prior_year_m100(secure_objects)
    _record_employers(operation, tmp_path)

    annual = calculate_annual(secure_objects)

    assert _box(annual, "0596") == Decimal("3920.00")
    assert validated_casilla_id("0597") not in annual.casilla_values
    assert validated_casilla_id("0609") not in annual.casilla_values


# ---------------------------------------------------------------------------------------------
# Employee-autonomo: salary plus an activity under estimacion directa simplificada, accrual criterion.
#
# The activity invoices carry the retention each client applied (Reglamento del IRPF art. 95.1):
#
#     quarter  base      rate  retention  paid on
#     1T       4.000,00  15 %     600,00  20 Feb
#     2T       3.500,00  15 %     525,00  20 May
#     3T       2.000,00   7 %     140,00  20 Aug
#     4T       2.500,00   7 %     175,00  20 Nov
#
# so the cumulative retention of casilla 06 runs 600 / 1.125 / 1.265 / 1.440, and the annual credit of
# casilla 0599 is 1.440,00 (Ley 35/2006 art. 99.1; Reglamento art. 110.3.a).
# ---------------------------------------------------------------------------------------------
_D = Decimal
_INVOICES = (
    ActivityInvoice(
        "F-2024-001", date(2024, 2, 10), date(2024, 2, 20), _D("4000.00"), _D("840.00"), _D("0.15"), _D("600.00")
    ),
    ActivityInvoice(
        "F-2024-002", date(2024, 5, 10), date(2024, 5, 20), _D("3500.00"), _D("735.00"), _D("0.15"), _D("525.00")
    ),
    ActivityInvoice(
        "F-2024-003", date(2024, 8, 10), date(2024, 8, 20), _D("2000.00"), _D("420.00"), _D("0.07"), _D("140.00")
    ),
    ActivityInvoice(
        "F-2024-004", date(2024, 11, 10), date(2024, 11, 20), _D("2500.00"), _D("525.00"), _D("0.07"), _D("175.00")
    ),
)
_EXPENSES = (
    ActivityExpense("expense-office", date(2024, 2, 5), date(2024, 2, 20), "material_oficina", _D("500.00")),
    ActivityExpense("expense-software", date(2024, 5, 10), date(2024, 5, 22), "software_suscripcion", _D("700.00")),
    ActivityExpense("expense-phone", date(2024, 8, 1), date(2024, 8, 12), "telefonia_movil", _D("300.00")),
    ActivityExpense("expense-advisory", date(2024, 11, 1), date(2024, 11, 8), "asesoria_fiscal", _D("900.00")),
)
_QUARTERS = ("1T", "2T", "3T", "4T")
_AUTONOMO = Persona(
    categories="trabajo,actividad_economica",
    regime="directa_simplificada",
    criterion="devengo",
    activity_start=date(2023, 3, 1),
)
# The same taxpayer under estimacion directa normal, for the quarter figures the simplified modality changes.
_AUTONOMO_NORMAL = Persona(
    categories="trabajo,actividad_economica",
    regime="directa_normal",
    criterion="devengo",
    activity_start=date(2023, 3, 1),
)
# An activity-only taxpayer on the normal modality, whose quarters need no work-income certificate.
_ACTIVITY_ONLY = Persona(
    categories="actividad_economica",
    regime="directa_normal",
    criterion="devengo",
    activity_start=date(2023, 3, 1),
)
_ACTIVITY_INPUTS = {ACTIVITY_KEY_CASILLA: ACTIVITY_KEY}


def test_the_quarters_credit_the_cumulative_activity_withholding_in_casilla_06(
    secure_objects: SecureObjectRepository,
) -> None:
    """Casilla 01 and casilla 06 follow the ledger and the invoices' retentions, whatever the modality."""
    seed_profile(_AUTONOMO)
    seed_prior_year_m100(secure_objects)
    seed_activity_ledger(secure_objects, _INVOICES, _EXPENSES)

    quarters = {period: calculate_and_file_quarter(secure_objects, period) for period in _QUARTERS}

    # oracle: Reglamento del IRPF art. 110.3.a: cumulative from 1 January, 600 / 600 + 525 / ... / 1.440.
    assert {period: _box(revision, "01") for period, revision in quarters.items()} == {
        "1T": _D("4000.00"),
        "2T": _D("7500.00"),
        "3T": _D("9500.00"),
        "4T": _D("12000.00"),
    }
    assert {period: _box(revision, "06") for period, revision in quarters.items()} == {
        "1T": _D("600.00"),
        "2T": _D("1125.00"),
        "3T": _D("1265.00"),
        "4T": _D("1440.00"),
    }


def test_the_quarters_of_a_normal_modality_taxpayer_pay_the_hand_derived_pago_fraccionado(
    secure_objects: SecureObjectRepository,
) -> None:
    """Estimacion directa normal: casilla 02 is the expenses alone, so each quarter follows the 20 % rule by hand.

    Cumulative net income 3.500 / 6.300 / 8.000 / 9.600 gives casilla 04 (20 %) of 700 / 1.260 / 1.600 /
    1.920. Casilla 07 is casilla 04 less the earlier positive quarters (05) and the cumulative retention (06):

        1T  700 -   0 -  600 = 100
        2T 1260 - 100 - 1125 =  35
        3T 1600 - 135 - 1265 = 200
        4T 1920 - 335 - 1440 = 145

    Together 480 = 20 % of 9.600 less the year's 1.440 withholding.
    """
    seed_profile(_AUTONOMO_NORMAL)
    seed_prior_year_m100(secure_objects)
    seed_activity_ledger(secure_objects, _INVOICES, _EXPENSES)

    quarters = {period: calculate_and_file_quarter(secure_objects, period) for period in _QUARTERS}

    # oracle: Reglamento del IRPF art. 110.3.a and the Modelo 130 instructions, casillas 02 to 07.
    expected = {"1T": _D("100.00"), "2T": _D("35.00"), "3T": _D("200.00"), "4T": _D("145.00")}
    assert {period: _box(revision, "07") for period, revision in quarters.items()} == expected
    assert {period: _box(revision, "19") for period, revision in quarters.items()} == expected
    assert sum((_box(revision, "19") for revision in quarters.values()), _D("0")) == _D("480.00")


# The quarters a simplified-modality taxpayer files, worked by hand from the Modelo 130 instructions, which
# put the gastos de dificil justificacion of Reglamento art. 30.2.4a (5 % of the net income before them) in
# casilla 02 beside the expenses:
#
#     quarter  01     02 (expenses + 5 %)   03     04 (20 %)  05   06     07
#     1T        4.000    500 + 175 =   675  3.325    665       0   600    65
#     2T        7.500  1.200 + 315 = 1.515  5.985  1.197      65  1.125   7
#     3T        9.500  1.500 + 400 = 1.900  7.600  1.520      72  1.265 183
#     4T       12.000  2.400 + 480 = 2.880  9.120  1.824     255  1.440 129
#
# 65 + 7 + 183 + 129 = 384 = 1.824 - 1.440. The taxpayer files them and imports each receipt.
_SIMPLIFIED_QUARTER_RESULTS = {"1T": _D("65.00"), "2T": _D("7.00"), "3T": _D("183.00"), "4T": _D("129.00")}


def _import_filed_quarters(secure_objects: SecureObjectRepository, *, fourth_quarter_retenciones: Decimal) -> None:
    """Import the four quarters the taxpayer filed, each as the AEAT-attested receipt it holds."""
    for period, result in _SIMPLIFIED_QUARTER_RESULTS.items():
        import_official_m130_result_observation(
            secure_objects,
            period=period,
            c19_value=result,
            observed_also={validated_casilla_id("06"): fourth_quarter_retenciones} if period == "4T" else None,
        )


def _record_employer(operation: PinnedAuthorityOperation, directory: Path) -> None:
    record_certificate(
        operation,
        directory=directory,
        payer=PAYER_A,
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion="3000.00",
        importe_integro="24000.00",
    )


def _calculate_autonomo_annual(secure_objects: SecureObjectRepository) -> CalculationRevision:
    return calculate_annual(secure_objects, text_casilla_inputs=_ACTIVITY_INPUTS)


def test_employee_autonomo_files_credits_equal_to_their_oracles_and_the_fourth_quarter_agrees(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    seed_profile(_AUTONOMO)
    seed_prior_year_m100(secure_objects)
    seed_activity_ledger(secure_objects, _INVOICES, _EXPENSES)
    _record_employer(operation, tmp_path)
    _import_filed_quarters(secure_objects, fourth_quarter_retenciones=_D("1440.00"))
    register_refund_account(secure_objects)

    annual = _calculate_autonomo_annual(secure_objects)

    # oracle: Reglamento del IRPF art. 108.3: the employer's certified retention.
    assert _box(annual, "0596") == _D("3000.00")
    # oracle: Ley 35/2006 art. 99.1: the retention of the four invoices, 600 + 525 + 140 + 175.
    assert _box(annual, "0599") == _D("1440.00")
    # oracle: Reglamento art. 110.3.a: 20 % of 9.120 net income, less the 1.440 withholding.
    assert _box(annual, "0604") == _D("384.00")
    # oracle: Ley 35/2006 art. 99.1: 3.000 + 1.440 + 384.
    assert _box(annual, "0609") == _D("4824.00")
    # oracle: Reglamento art. 30.2.4a: 12.000 - 2.400 expenses - 5 % of 9.600 = 12.000 - 2.880.
    assert _box(annual, "0224") == _D("9120.00")
    # The filed fourth quarter's casilla 06 states the same 1.440, so that cross-check finds nothing to dispute.
    assert not [issue for issue in annual.source_issues if issue.reason == "credit_source_disagreement"]
    assert not [
        issue
        for issue in annual.source_issues
        if issue.reason == "credit_cross_check_absent" and issue.source_ref == "filed:130:4T:06"
    ]

    payload = verify_and_export(annual, secure_objects, tmp_path / "modelo-100-autonomo.xml", _AUTONOMO)
    assert payload


def test_without_an_inventory_book_the_activity_net_income_stays_unresolved(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The same taxpayer with no inventory book has no casilla 0224: the book's rows are unread, not zero."""
    seed_profile(_AUTONOMO)
    seed_prior_year_m100(secure_objects)
    seed_activity_ledger(secure_objects, _INVOICES, _EXPENSES, inventory_book=False)
    _record_employer(operation, tmp_path)
    _import_filed_quarters(secure_objects, fourth_quarter_retenciones=_D("1440.00"))
    register_refund_account(secure_objects)

    annual = _calculate_autonomo_annual(secure_objects)

    assert validated_casilla_id("0224") not in annual.casilla_values


def test_a_fourth_quarter_that_states_another_retention_withholds_the_filing(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    seed_profile(_AUTONOMO)
    seed_prior_year_m100(secure_objects)
    seed_activity_ledger(secure_objects, _INVOICES, _EXPENSES)
    _record_employer(operation, tmp_path)
    _import_filed_quarters(secure_objects, fourth_quarter_retenciones=_D("1400.00"))

    annual = _calculate_autonomo_annual(secure_objects)

    (disagreement,) = [issue for issue in annual.source_issues if issue.reason == "credit_source_disagreement"]
    assert disagreement in blocking_calculation_issues(annual)


# ---------------------------------------------------------------------------------------------
# Timing: a withholding paid after the quarter it was practised on.
#
# One 1.000,00 invoice at 15 % (150,00 withheld, 210,00 IVA) is accrued on 20 March and settled net,
# 1.060,00, on 10 April. Reglamento del IRPF art. 110.3.a deducts a retention only once practised, and
# a payer practises it when it pays (Ley 35/2006 art. 99.1; TEAC resolution of 00/03187/2011), so:
#
#     1T  casilla 01 = 1.000,00 (accrued in March)   casilla 06 =   0,00 (paid in April)
#     2T  casilla 01 = 1.000,00                      casilla 06 = 150,00
#
# The annual credit of casilla 0599 is 150,00 either way: the income belongs to the ejercicio it
# accrues in, and so does the withholding (Ley 35/2006 art. 14; Reglamento art. 7).
# ---------------------------------------------------------------------------------------------
_LATE_PAYMENT = ActivityInvoice(
    "F-2024-LATE", date(2024, 3, 20), date(2024, 4, 10), _D("1000.00"), _D("210.00"), _D("0.15"), _D("150.00")
)
# Accrued on 20 December and paid on 10 January of the next ejercicio: the same 150,00 of withholding.
_YEAR_END_PAYMENT = ActivityInvoice(
    "F-2024-YEAR-END", date(2024, 12, 20), date(2025, 1, 10), _D("1000.00"), _D("210.00"), _D("0.15"), _D("150.00")
)


def test_a_retention_paid_after_the_quarter_defers_casilla_06_and_still_counts_in_0599(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    seed_profile(_ACTIVITY_ONLY)
    seed_prior_year_m100(secure_objects)
    seed_activity_ledger(secure_objects, (_LATE_PAYMENT,), ())

    first = calculate_and_file_quarter(secure_objects, "1T")
    second = calculate_and_file_quarter(secure_objects, "2T")

    # oracle: Reglamento del IRPF art. 110.3.a: practised on 10 April, so deducted from the second quarter on.
    assert (_box(first, "01"), _box(first, "06")) == (_D("1000.00"), _D("0"))
    assert (_box(second, "01"), _box(second, "06")) == (_D("1000.00"), _D("150.00"))

    annual = calculate_annual(
        secure_objects,
        casilla_inputs={},
        text_casilla_inputs=_ACTIVITY_INPUTS,
    )
    # oracle: Ley 35/2006 art. 14: accrued in 2024, so the withholding is a 2024 credit.
    assert _box(annual, "0599") == _D("150.00")


def test_a_retention_paid_after_the_year_leaves_the_fourth_quarter_but_credits_0599_without_a_dispute(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    seed_profile(_ACTIVITY_ONLY)
    seed_prior_year_m100(secure_objects)
    seed_activity_ledger(secure_objects, (_YEAR_END_PAYMENT,), ())
    # The fourth quarter was filed on the income alone: 20 % of 1.000,00 and, the payment falling in the
    # next ejercicio, no withholding deducted (Reglamento del IRPF art. 110.3.a).
    for period, result in (("1T", "0.00"), ("2T", "0.00"), ("3T", "0.00"), ("4T", "200.00")):
        import_official_m130_result_observation(
            secure_objects,
            period=period,
            c19_value=_D(result),
            observed_also={validated_casilla_id("06"): _D("0.00")} if period == "4T" else None,
        )

    annual = calculate_annual(secure_objects, casilla_inputs={}, text_casilla_inputs=_ACTIVITY_INPUTS)

    # oracle: Ley 35/2006 art. 14 and Reglamento art. 7: accrued in December 2024, a 2024 credit.
    assert _box(annual, "0599") == _D("150.00")
    # The 150,00 the fourth quarter left out is timing the receipt's own payment date explains, so it is no dispute.
    assert not [issue for issue in annual.source_issues if issue.reason == "credit_source_disagreement"]


# ---------------------------------------------------------------------------------------------
# Payer: the employee-autonomo also pays a freelancer (Modelo 111) and a landlord (Modelo 115), so
# the withholding it practised on them sits in the payer-side store. That withholding is the
# perceptor's credit (Ley 35/2006 art. 99.1; Reglamento del IRPF arts. 76 and 108), never the
# payer's own, so every credit of the annual return stays at the figures of the persona above.
#
#     Modelo 111 retention per quarter   150 / 225 /  75 / 300   (750 for the year)
#     Modelo 115 retention per quarter   190 each quarter        (760 for the year)
# ---------------------------------------------------------------------------------------------
_PAYER_SIDE_111 = {"1T": _D("150.00"), "2T": _D("225.00"), "3T": _D("75.00"), "4T": _D("300.00")}
_PAYER_SIDE_115 = {"1T": _D("190.00"), "2T": _D("190.00"), "3T": _D("190.00"), "4T": _D("190.00")}
_FREELANCER = "B00010165"
_LANDLORD = "B00015016"


def _seed_payer_side_store(secure_objects: SecureObjectRepository) -> None:
    repository = RetencionObservationRepositoryAdapter(objects=secure_objects)
    for modelo, perceptor, scheme, withheld in (
        ("111", _FREELANCER, "actividades_profesionales", _PAYER_SIDE_111),
        ("115", _LANDLORD, "arrendamiento_urbano", _PAYER_SIDE_115),
    ):
        for period, amount in withheld.items():
            replace_retencion_observations(
                repository,
                modelo=modelo,
                filing_year=2024,
                period=Period.from_year_and_code(2024, period),
                observations=[
                    RetencionObservation(
                        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                        source_object_id=f"{modelo}-{period}",
                        perceptor_nif=perceptor,
                        perceptor_name="Perceptor Sintetico",
                        scheme=RetencionScheme(scheme),
                        taxable_base=amount * 5,
                        retencion_amount=amount,
                        accrued_on={"1T": "2024-02-10", "2T": "2024-05-10", "3T": "2024-08-10", "4T": "2024-11-10"}[
                            period
                        ],
                    )
                ],
                source_kind=AggregationCaptureKind.AGGREGATE_PULL,
            )


def test_a_payer_persona_keeps_every_credit_and_still_verifies_and_exports(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    seed_profile(_AUTONOMO)
    seed_prior_year_m100(secure_objects)
    seed_activity_ledger(secure_objects, _INVOICES, _EXPENSES)
    _record_employer(operation, tmp_path)
    _import_filed_quarters(secure_objects, fourth_quarter_retenciones=_D("1440.00"))
    _seed_payer_side_store(secure_objects)
    register_refund_account(secure_objects)

    annual = _calculate_autonomo_annual(secure_objects)

    credits = {casilla: _box(annual, casilla) for casilla in ("0596", "0597", "0598", "0599", "0603", "0604", "0609")}
    # The same figures as the persona without the payer-side store.
    assert credits == {
        "0596": _D("3000.00"),
        "0597": _D("0"),
        "0598": _D("0"),
        "0599": _D("1440.00"),
        "0603": _D("0"),
        "0604": _D("384.00"),
        "0609": _D("4824.00"),
    }
    payer_side = {*_PAYER_SIDE_111.values(), *_PAYER_SIDE_115.values(), _D("750.00"), _D("760.00")}
    assert not payer_side & set(credits.values())

    payload = verify_and_export(annual, secure_objects, tmp_path / "modelo-100-payer.xml", _AUTONOMO)
    assert payload
