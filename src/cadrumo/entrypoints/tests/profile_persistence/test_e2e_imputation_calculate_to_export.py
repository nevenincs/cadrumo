"""Renta imputation from persisted ledger rows to exported bytes, for Modelo 130 and Modelo 100.

Real encrypted store, real resolvers, real calculate, verify and export actions.
Every expected figure is worked by hand from the rows below.

Rows of the ejercicio, as (banked, accrues, amount):

    income  C  15 Feb       15 Feb       4.000,00
    income  B  20 May       15 Feb       3.500,00
    income  A  20 Jan next   5 Nov       2.500,00
    expense E1 10 Jul        1 Apr         700,00
    expense E2  1 Feb next   1 Dec         900,00

Under accrual: casilla 01 runs 7.500 / 7.500 / 7.500 / 10.000 and casilla 02
0 / 700 / 700 / 1.600, so the annual return shows income 10.000, expenses 1.600
and net 8.400. First-quarter casilla 04 is 20 per cent of 7.500, 1.500.

Under the cash election A and E2 fall in the next ejercicio, whatever their
stated dates say: income 7.500, expenses 700, net 6.800, and the return carries
the election in casilla 0169.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from defusedxml import ElementTree as DefusedElementTree

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.justificante_metadata import persist_justificante_metadata
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from cadrumo.adapters.persistence.profile.tests.retencion_soportada_seed import seed_absence_attestation
from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.modelo.action_errors import ModeloInstalmentElectionRefusedError
from cadrumo.application.modelo.export_contracts import ModeloExportCommand
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.payment_instalment_election import PaymentInstalmentElection
from cadrumo.core.period import Period
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.filing_record import ExternalEvidenceKind
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record

from .general_iva_profile_facts_support import renta_single_taxpayer_facts
from .imputation_export_support import (
    CASH,
    DEVENGO,
    NEXT_YEAR,
    OFFICIAL_M130_C19,
    REFUND_IBAN,
    persist_ledger,
    register_refund_account,
    verify_and_export,
)
from .m130_m100_annual_support import (
    BUCKET_ID,
    FILE_AT,
    M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA,
    M100_ANNUAL_PERIOD,
    M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA,
    M100_RENDIMIENTO_SOURCE_1479_CASILLA,
    M100_RENDIMIENTO_SOURCE_1553_CASILLA,
    M100_RENDIMIENTO_SOURCE_1577_CASILLA,
    PRIOR_YEAR,
    PRIOR_YEAR_NET_INCOME,
    T0,
    TAX_ID,
    YEAR,
    autonomaworkflow_profile,
    calculate_revision_from_bucket_aggregation,
    export_revision_for_test,
    import_filing_evidence_for_test,
    import_official_m130_result_observation,
    m100_non_relation_zero_bindings,
    seed_prior_year_m100,
)
from .test_e2e_ledger_m130_quarters_to_m100_annual import (
    M100_ACTIVITY_INCOME_CASILLA,
    M100_ACTIVITY_KEY,
    M100_ACTIVITY_KEY_CASILLA,
    M100_NORMAL_DEDUCTIBLE_EXPENSES_CASILLA,
    M130_INGRESOS_CASILLA,
    calculate_and_file_m130_quarter,
)

__all__ = ["secure_objects"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_M130_GASTOS: CasillaId = validated_casilla_id("02")
_M130_NET: CasillaId = validated_casilla_id("03")
_M130_RATE_SHARE: CasillaId = validated_casilla_id("04")
_M130_NEGATIVE_CARRIED: CasillaId = validated_casilla_id("saldo-negativo-fin-periodo")
_M130_QUARTER_PAYMENT: CasillaId = validated_casilla_id("07")
_CASH_ELECTION_CASILLA: CasillaId = validated_casilla_id("0169")
_CASH_ELECTION_XML_TAG = "E1ITEMP"
_MODALIDAD_XML_TAG = "E1MED"
_M100_RESULT_CASILLA: CasillaId = validated_casilla_id("0670")
# An instant inside the 2024 annual return's filing window, so the window is not what refuses a split.
_WITHIN_THE_FILING_WINDOW = datetime(2025, 6, 2, 12, 0, tzinfo=UTC)
# The payments on account that leave exactly one cent of this fixture's liability unpaid.
_PAYMENTS_LEAVING_ONE_CENT = {
    "1T": Decimal("300.00"),
    "2T": Decimal("178.42"),
    "3T": Decimal("0.00"),
    "4T": Decimal("0.00"),
}


@pytest.fixture
def bucket_id() -> str:
    return BUCKET_ID


def _seed_profile(criterion: str, *stated: UserProfileFact) -> None:

    dated = tuple(
        UserProfileFact.model_validate(
            {"path": path, "value": value, "valid_from": date(year, 1, 1), "valid_to": date(year, 12, 31)}
        )
        for year in (YEAR, NEXT_YEAR)
        for path, value in (
            ("irpf.activity_income_imputation_criterion", criterion),
            ("irpf.codigo_comercio_accounting", False),
        )
    )
    seed_test_profile_record(
        create_user_profile_record(
            context=profile_creation_context_for_test(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path="identity.tax_id", value=TAX_ID),
                    UserProfileFact(path="identity.name", value="Annual"),
                    UserProfileFact(path="identity.surnames", value="Renta Tester"),
                    UserProfileFact(path="activities.description", value="design services"),
                    UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
                    *renta_single_taxpayer_facts(birth_date=date(1980, 3, 15)),
                    *dated,
                    *stated,
                )
            ),
            created_at=T0,
            updated_at=T0,
        )
    )


def _annual(objects: SecureObjectRepository) -> CalculationRevision:
    units = WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=objects)
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("100", filing_year=YEAR, period="0A")
        unit = create_work_unit(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=YEAR,
            period=Period.from_year_and_code(YEAR, "0A"),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=units,
                bucket_event_repository=BucketEventHistoryRepository(objects=objects),
            ),
            operation=operation,
            clock=T0,
        )
    return calculate_revision_from_bucket_aggregation(
        unit.work_unit_id,
        binding_values=m100_non_relation_zero_bindings(),
        text_casilla_inputs={M100_ACTIVITY_KEY_CASILLA: M100_ACTIVITY_KEY},
        work_unit_repository=units,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=objects),
        clock=T0,
    ).revision


def _seed_official_prior_year_m100(objects: SecureObjectRepository) -> None:
    """Carry the prior return as AEAT-attested, the standing a verified Modelo 130 reads it at."""
    units = WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=objects)
    events = BucketEventHistoryRepository(objects=objects)
    casilla_values = {
        casilla: Decimal(0)
        for casilla in (
            M100_RENDIMIENTO_SOURCE_1479_CASILLA,
            M100_RENDIMIENTO_SOURCE_1553_CASILLA,
            M100_RENDIMIENTO_SOURCE_1577_CASILLA,
            M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA,
        )
    } | {M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: PRIOR_YEAR_NET_INCOME}
    reference = f"JUST100{PRIOR_YEAR}0AIMPUTACION"
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("100", filing_year=PRIOR_YEAR, period=M100_ANNUAL_PERIOD)
        unit = create_work_unit(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=PRIOR_YEAR,
            period=Period.from_year_and_code(PRIOR_YEAR, M100_ANNUAL_PERIOD),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(work_unit_repository=units, bucket_event_repository=events),
            operation=operation,
            clock=FILE_AT,
        )
    persist_justificante_metadata(
        reference,
        modelo="100",
        filing_year=PRIOR_YEAR,
        period=M100_ANNUAL_PERIOD,
        captured_at=FILE_AT,
        tax_id=TAX_ID,
    )
    import_filing_evidence_for_test(
        work_unit_id=unit.work_unit_id,
        casilla_values=casilla_values,
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id=reference,
        actor="imputation-e2e",
        work_unit_repository=units,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=objects),
        filing_repository=ModeloRecordCatalogueRepository(objects=objects),
        bucket_event_repository=events,
        expected_tax_id=TAX_ID,
        clock=FILE_AT,
    )
    repository = CalculationObservationRepository(objects=objects)
    repository.save(
        repository.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="100",
                filing_year=PRIOR_YEAR,
                period=M100_ANNUAL_PERIOD,
                observations=registry_grounded_observations(
                    modelo="100",
                    filing_year=PRIOR_YEAR,
                    period=M100_ANNUAL_PERIOD,
                    casilla_values=casilla_values,
                ),
            ),
            source_kind="aeat_sede_justificante",
            captured_at=FILE_AT,
            stamped_revision_id=snapshot.revision.id,
            source_metadata={
                "aeat_register_status": "ALTA",
                "aeat_expediente_id": f"EXP-100-{PRIOR_YEAR}",
                "aeat_justificante_csv": reference,
                "authenticated_identity": TAX_ID,
            },
        )
    )


def _money(revision: CalculationRevision, casilla: CasillaId) -> Decimal:
    return Decimal(revision.casilla_values[casilla])


def _settlement(payload: bytes) -> dict[str, str | None]:
    """The settlement rows the record states in ``DatosIngresoDevolucion``, by field id."""
    root = DefusedElementTree.fromstring(payload)
    blocks = [element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "DatosIngresoDevolucion"]
    assert len(blocks) == 1
    return {
        element.tag.rsplit("}", 1)[-1]: element.text
        for element in blocks[0].iter()
        if len(element) == 0 and element.text is not None
    }


def _election_marks(payload: bytes) -> list[str | None]:
    return _tag_texts(payload, _CASH_ELECTION_XML_TAG)


def _tag_texts(payload: bytes, tag: str) -> list[str | None]:
    root = DefusedElementTree.fromstring(payload)
    return [element.text for element in root.iter() if element.tag.rsplit("}", 1)[-1] == tag]


@pytest.mark.parametrize(
    ("period", "ingresos", "gastos"),
    [
        ("1T", "7500.00", "0.00"),
        ("2T", "7500.00", "700.00"),
        ("3T", "7500.00", "700.00"),
        ("4T", "10000.00", "1600.00"),
    ],
)
def test_m130_under_accrual_places_stated_rows_by_their_quarter_through_export(
    secure_objects: SecureObjectRepository, tmp_path: Path, period: str, ingresos: str, gastos: str
) -> None:
    _seed_profile(DEVENGO)
    persist_ledger(secure_objects)
    _seed_official_prior_year_m100(secure_objects)
    for earlier in ("1T", "2T", "3T", "4T")[: ("1T", "2T", "3T", "4T").index(period)]:
        import_official_m130_result_observation(
            secure_objects,
            period=earlier,
            c19_value=OFFICIAL_M130_C19[earlier],
            observed_also={_M130_NEGATIVE_CARRIED: Decimal(0), _M130_QUARTER_PAYMENT: OFFICIAL_M130_C19[earlier]},
        )

    revision = calculate_and_file_m130_quarter(secure_objects, period=period)

    assert _money(revision, M130_INGRESOS_CASILLA) == Decimal(ingresos)
    assert _money(revision, _M130_GASTOS) == Decimal(gastos)
    net = Decimal(ingresos) - Decimal(gastos)
    assert _money(revision, _M130_NET) == net
    assert _money(revision, _M130_RATE_SHARE) == net / 5

    payload = verify_and_export(revision, secure_objects, tmp_path / f"modelo-130-{period}.txt")
    assert payload


@pytest.mark.parametrize(
    ("criterion", "income", "expenses", "net", "marks"),
    [
        (DEVENGO, "10000.00", "1600.00", "8400.00", False),
        (CASH, "7500.00", "700.00", "6800.00", True),
    ],
)
def test_m100_places_stated_rows_by_the_criterion_through_export(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    criterion: str,
    income: str,
    expenses: str,
    net: str,
    marks: bool,
) -> None:
    _seed_profile(criterion)
    persist_ledger(secure_objects)
    seed_prior_year_m100(secure_objects)
    for period, result in OFFICIAL_M130_C19.items():
        import_official_m130_result_observation(secure_objects, period=period, c19_value=result)
    # The profile declares activity income without an IAE epigraph, so whether the activity includes an urban
    # rental, whose withholding credits casilla 0598, is not proven: the operator attests that no payer withheld.
    seed_absence_attestation(
        operation=published_authority_operation(),
        ejercicio=YEAR,
        income_class=RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO_ACTIVIDAD,
    )

    annual = _annual(secure_objects)

    assert _money(annual, M100_ACTIVITY_INCOME_CASILLA) == Decimal(income)
    assert _money(annual, M100_NORMAL_DEDUCTIBLE_EXPENSES_CASILLA) == Decimal(expenses)
    assert _money(annual, M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA) == Decimal(net)

    register_refund_account(secure_objects)
    payload = verify_and_export(annual, secure_objects, tmp_path / f"modelo-100-{criterion}.xml")
    with pytest.raises(ModeloInstalmentElectionRefusedError) as split:
        export_revision_for_test(
            ModeloExportCommand(
                calculation_revision_id=annual.calculation_revision_id,
                output_path=tmp_path / "split.xml",
                actor="imputation-e2e",
                instalment_election=PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_PAID,
            ),
            workflow_profile=autonomaworkflow_profile(),
            export_ports=modelo_export_ports_for_test(
                bucket_id=BUCKET_ID, taxpayer_tax_id=TAX_ID, secure_objects=secure_objects
            ),
        )
    # The split holds for the 2024 ejercicio too, so this return's refund is what refuses it, as nothing to pay.
    assert split.value.context is not None and split.value.context["reason"] == "nothing_to_pay"
    assert not (tmp_path / "split.xml").exists()
    assert _election_marks(payload) == (["1"] if marks else [])
    result = _money(annual, _M100_RESULT_CASILLA)
    assert result < 0
    assert _settlement(payload) == {
        "TIPODECLARACION": "D",
        "DEV_IMPORTE": f"{-result:.2f}",
        "DEV_CUENTACORRIENTE": REFUND_IBAN,
    }
    assert _money(annual, _CASH_ELECTION_CASILLA) == Decimal(1 if marks else 0)


def test_a_split_of_an_amount_whose_second_instalment_is_nothing_is_refused_with_its_reason(
    secure_objects: SecureObjectRepository, tmp_path: Path
) -> None:
    """One cent to pay leaves nothing for a second instalment: the split is refused as such, not as a failed write."""
    _seed_profile(DEVENGO)
    persist_ledger(secure_objects)
    seed_prior_year_m100(secure_objects)
    for period, payment in _PAYMENTS_LEAVING_ONE_CENT.items():
        import_official_m130_result_observation(secure_objects, period=period, c19_value=payment)
    # Activity income without an IAE epigraph does not prove whether an urban rental, whose withholding credits
    # casilla 0598, is part of it: the operator attests that no payer withheld.
    seed_absence_attestation(
        operation=published_authority_operation(),
        ejercicio=YEAR,
        income_class=RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO_ACTIVIDAD,
    )

    annual = _annual(secure_objects)

    owed = _money(annual, _M100_RESULT_CASILLA)
    assert owed == Decimal("0.01"), owed
    payload = verify_and_export(annual, secure_objects, tmp_path / "at-once.xml")
    with pytest.raises(ModeloInstalmentElectionRefusedError) as split:
        export_revision_for_test(
            ModeloExportCommand(
                calculation_revision_id=annual.calculation_revision_id,
                output_path=tmp_path / "split.xml",
                actor="imputation-e2e",
                instalment_election=PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_PAID,
            ),
            workflow_profile=autonomaworkflow_profile(),
            export_ports=modelo_export_ports_for_test(
                bucket_id=BUCKET_ID, taxpayer_tax_id=TAX_ID, secure_objects=secure_objects
            ),
            clock=_WITHIN_THE_FILING_WINDOW,
        )
    assert split.value.translated_message == "errors.refused.refused_modelo_instalment_election"
    assert split.value.context is not None
    assert split.value.context["reason"] == "second_instalment_nothing", split.value.context["reason"]
    assert not (tmp_path / "split.xml").exists()
    assert _settlement(payload) == {"TIPODECLARACION": "I", "ING_IMPORTE": "0.01"}


@pytest.mark.parametrize(
    ("regime", "clave"),
    [("directa_normal", "N"), ("directa_simplificada", "S")],
)
def test_m100_states_the_direct_estimation_modality_as_its_design_clave_through_export(
    secure_objects: SecureObjectRepository, tmp_path: Path, regime: str, clave: str
) -> None:
    """Casilla 0168 (E1MED, tipo_OpcionesSyN) carries N for normal and S for simplificada.

    The box is a text clave in the official design, not a yes/no flag, so the
    exported record must hold the letter the design defines for the declared
    regime. Before the clave was bound, the box reached the record empty.
    """
    _seed_profile(DEVENGO, UserProfileFact(path="irpf.estimation_regime", value=regime))
    persist_ledger(secure_objects)
    seed_prior_year_m100(secure_objects)
    for period, result in OFFICIAL_M130_C19.items():
        import_official_m130_result_observation(secure_objects, period=period, c19_value=result)
    seed_absence_attestation(
        operation=published_authority_operation(),
        ejercicio=YEAR,
        income_class=RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO_ACTIVIDAD,
    )

    annual = _annual(secure_objects)
    register_refund_account(secure_objects)
    payload = verify_and_export(annual, secure_objects, tmp_path / f"modelo-100-{regime}.xml")

    stated = _tag_texts(payload, _MODALIDAD_XML_TAG)
    assert stated == [clave], stated
