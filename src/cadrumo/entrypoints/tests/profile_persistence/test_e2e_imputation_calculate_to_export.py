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

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from defusedxml import ElementTree as DefusedElementTree

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.own_accounts import OwnAccountRepository
from cadrumo.adapters.persistence.profile.tests.justificante_metadata import persist_justificante_metadata
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.modelo.action_errors import ModeloInstalmentElectionRefusedError
from cadrumo.application.modelo.export_contracts import ModeloExportCommand
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.payment_instalment_election import PaymentInstalmentElection
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.invoices.catalogue import InvoiceCatalogue
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.filing_record import ExternalEvidenceKind
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.own_accounts import (
    OwnAccountDesignation,
    OwnAccountHolding,
    OwnAccountRegister,
    OwnAccountRole,
    OwnBankAccountDetails,
)
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record

from .test_e2e_ledger_m130_quarters_to_m100_annual import (
    _BUCKET_ID,
    _FILE_AT,
    _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA,
    _M100_ACTIVITY_INCOME_CASILLA,
    _M100_ANNUAL_PERIOD,
    _M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA,
    _M100_NORMAL_DEDUCTIBLE_EXPENSES_CASILLA,
    _M100_RENDIMIENTO_SOURCE_1479_CASILLA,
    _M100_RENDIMIENTO_SOURCE_1553_CASILLA,
    _M100_RENDIMIENTO_SOURCE_1577_CASILLA,
    _M130_INGRESOS_CASILLA,
    _OPERATOR_SCOPE_PORTS,
    _PRIOR_YEAR,
    _PRIOR_YEAR_NET_INCOME,
    _T0,
    _TAX_ID,
    _YEAR,
    M100_ACTIVITY_KEY,
    M100_ACTIVITY_KEY_CASILLA,
    _autonomaworkflow_profile,
    _calculate_and_file_m130_quarter,
    _calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    _expense_transaction,
    _export_modelo_revision,
    _import_external_filing_evidence,
    _import_official_m130_result_observation,
    _income_transaction,
    _m100_non_relation_zero_bindings,
    _seed_prior_year_m100,
    _verify_modelo_revision,
    ready_clave_settings,
)

__all__ = ["secure_objects"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_NEXT = _YEAR + 1
_DEVENGO = "devengo"
_CASH = "cobros_y_pagos"
_M130_GASTOS: CasillaId = validated_casilla_id("02")
_M130_NET: CasillaId = validated_casilla_id("03")
_M130_RATE_SHARE: CasillaId = validated_casilla_id("04")
_M130_NEGATIVE_CARRIED: CasillaId = validated_casilla_id("saldo-negativo-fin-periodo")
_M130_QUARTER_PAYMENT: CasillaId = validated_casilla_id("07")
_CASH_ELECTION_CASILLA: CasillaId = validated_casilla_id("0169")
_CASH_ELECTION_XML_TAG = "E1ITEMP"
_M100_RESULT_CASILLA: CasillaId = validated_casilla_id("0670")
_REFUND_IBAN = "ES9121000418450200051332"
_OFFICIAL_M130_C19 = {
    "1T": Decimal("300.00"),
    "2T": Decimal("360.00"),
    "3T": Decimal("400.00"),
    "4T": Decimal("460.00"),
}


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _income(row_id: str, banked: date, accrues: date, amount: str) -> Transaction:
    template = _income_transaction("1T")
    value = Decimal(amount)
    raw = template.raw.model_copy(
        update={
            "provider_transaction_id": row_id,
            "booked_date": banked,
            "value_date": banked,
            "amount": value,
            "description": row_id,
        }
    )
    stored = template.model_dump(mode="python", exclude={"transaction_id"})
    return Transaction.model_validate({**stored, "raw": raw, "taxable_base": value, "accrual_date": accrues})


def _expense(row_id: str, banked: date, accrues: date, category: str, amount: str) -> Transaction:
    row = _expense_transaction(
        row_id, value_date=banked, category=SpendingCategory.from_registry(category), taxable_base=Decimal(amount)
    )
    return row.model_copy(update={"accrual_date": accrues})


def _persist_ledger(objects: SecureObjectRepository) -> None:
    rows = (
        _income("income-c", date(_YEAR, 2, 15), date(_YEAR, 2, 15), "4000.00"),
        _income("income-b", date(_YEAR, 5, 20), date(_YEAR, 2, 15), "3500.00"),
        _income("income-a", date(_NEXT, 1, 20), date(_YEAR, 11, 5), "2500.00"),
        _expense("expense-e1", date(_YEAR, 7, 10), date(_YEAR, 4, 1), "software_suscripcion", "700.00"),
        _expense("expense-e2", date(_NEXT, 2, 1), date(_YEAR, 12, 1), "asesoria_fiscal", "900.00"),
    )
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).save(
        TransactionCatalogue.from_transactions(rows)
    )
    InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).save(InvoiceCatalogue())


def _seed_profile(criterion: str) -> None:
    from .test_e2e_ledger_m130_quarters_to_m100_annual import (
        GENERAL_REGIME_NATURAL_PERSON_FACTS,
        renta_single_taxpayer_facts,
    )

    dated = tuple(
        UserProfileFact.model_validate(
            {"path": path, "value": value, "valid_from": date(year, 1, 1), "valid_to": date(year, 12, 31)}
        )
        for year in (_YEAR, _NEXT)
        for path, value in (
            ("irpf.activity_income_imputation_criterion", criterion),
            ("irpf.codigo_comercio_accounting", False),
        )
    )
    seed_test_profile_record(
        create_user_profile_record(
            context=profile_creation_context_for_test(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.name", value="Annual"),
                UserProfileFact(path="identity.surnames", value="Renta Tester"),
                UserProfileFact(path="activities.description", value="design services"),
                *GENERAL_REGIME_NATURAL_PERSON_FACTS,
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
                *renta_single_taxpayer_facts(birth_date=date(1980, 3, 15)),
                *dated,
            ),
            created_at=_T0,
            updated_at=_T0,
        )
    )


def _annual(objects: SecureObjectRepository) -> CalculationRevision:
    units = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("100", filing_year=_YEAR, period="0A")
        unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, "0A"),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=units,
                bucket_event_repository=BucketEventHistoryRepository(objects=objects),
            ),
            operation=operation,
            clock=_T0,
        )
    return _calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        unit.work_unit_id,
        binding_values=_m100_non_relation_zero_bindings(),
        text_casilla_inputs={M100_ACTIVITY_KEY_CASILLA: M100_ACTIVITY_KEY},
        work_unit_repository=units,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=objects),
        clock=_T0,
    ).revision


def _verify_and_export(revision: CalculationRevision, objects: SecureObjectRepository, output: Path) -> bytes:
    report = _verify_modelo_revision(
        revision.calculation_revision_id,
        actor="imputation-e2e",
        workflow_profile=_autonomaworkflow_profile(),
        settings=ready_clave_settings(_TAX_ID),
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    assert report.granted_verificado_completo is True, report.findings
    receipt = _export_modelo_revision(
        ModeloExportCommand(
            calculation_revision_id=revision.calculation_revision_id, output_path=output, actor="imputation-e2e"
        ),
        workflow_profile=_autonomaworkflow_profile(),
        export_ports=modelo_export_ports_for_test(
            bucket_id=_BUCKET_ID, taxpayer_tax_id=_TAX_ID, secure_objects=objects
        ),
    )
    payload = output.read_bytes()
    assert receipt.byte_size == len(payload)
    return payload


def _seed_official_prior_year_m100(objects: SecureObjectRepository) -> None:
    """Carry the prior return as AEAT-attested, the standing a verified Modelo 130 reads it at."""
    units = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
    events = BucketEventHistoryRepository(objects=objects)
    casilla_values = {
        casilla: Decimal(0)
        for casilla in (
            _M100_RENDIMIENTO_SOURCE_1479_CASILLA,
            _M100_RENDIMIENTO_SOURCE_1553_CASILLA,
            _M100_RENDIMIENTO_SOURCE_1577_CASILLA,
            _M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA,
        )
    } | {_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: _PRIOR_YEAR_NET_INCOME}
    reference = f"JUST100{_PRIOR_YEAR}0AIMPUTACION"
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("100", filing_year=_PRIOR_YEAR, period=_M100_ANNUAL_PERIOD)
        unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=_PRIOR_YEAR,
            period=Period.from_year_and_code(_PRIOR_YEAR, _M100_ANNUAL_PERIOD),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(work_unit_repository=units, bucket_event_repository=events),
            operation=operation,
            clock=_FILE_AT,
        )
    persist_justificante_metadata(
        reference,
        modelo="100",
        filing_year=_PRIOR_YEAR,
        period=_M100_ANNUAL_PERIOD,
        captured_at=_FILE_AT,
        tax_id=_TAX_ID,
    )
    _import_external_filing_evidence(
        work_unit_id=unit.work_unit_id,
        casilla_values=casilla_values,
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id=reference,
        actor="imputation-e2e",
        work_unit_repository=units,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=objects),
        filing_repository=ModeloRecordCatalogueRepository(objects=objects),
        bucket_event_repository=events,
        expected_tax_id=_TAX_ID,
        clock=_FILE_AT,
    )
    repository = CalculationObservationRepository(objects=objects)
    repository.save(
        repository.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="100",
                filing_year=_PRIOR_YEAR,
                period=_M100_ANNUAL_PERIOD,
                observations=registry_grounded_observations(
                    modelo="100",
                    filing_year=_PRIOR_YEAR,
                    period=_M100_ANNUAL_PERIOD,
                    casilla_values=casilla_values,
                ),
            ),
            source_kind="aeat_sede_justificante",
            captured_at=_FILE_AT,
            stamped_revision_id=snapshot.revision.id,
            source_metadata={
                "aeat_register_status": "ALTA",
                "aeat_expediente_id": f"EXP-100-{_PRIOR_YEAR}",
                "aeat_justificante_csv": reference,
                "authenticated_identity": _TAX_ID,
            },
        )
    )


def _money(revision: CalculationRevision, casilla: CasillaId) -> Decimal:
    return Decimal(revision.casilla_values[casilla])


def _register_refund_account(objects: SecureObjectRepository) -> None:
    """Designate a Spanish own account to receive the refund, as the export's account page needs."""

    def change(register: OwnAccountRegister) -> OwnAccountRegister:
        account_id = register.next_account_id()
        return register.with_new_account(
            OwnBankAccountDetails(label="Devolución", holding=OwnAccountHolding.TITULAR, iban=_REFUND_IBAN)
        ).with_designation(OwnAccountDesignation(role=OwnAccountRole.REFUND, own_account_id=account_id))

    OwnAccountRepository(objects=objects).mutate(change)


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
    root = DefusedElementTree.fromstring(payload)
    return [element.text for element in root.iter() if element.tag.rsplit("}", 1)[-1] == _CASH_ELECTION_XML_TAG]


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
    _seed_profile(_DEVENGO)
    _persist_ledger(secure_objects)
    _seed_official_prior_year_m100(secure_objects)
    for earlier in ("1T", "2T", "3T", "4T")[: ("1T", "2T", "3T", "4T").index(period)]:
        _import_official_m130_result_observation(
            secure_objects,
            period=earlier,
            c19_value=_OFFICIAL_M130_C19[earlier],
            observed_also={_M130_NEGATIVE_CARRIED: Decimal(0), _M130_QUARTER_PAYMENT: _OFFICIAL_M130_C19[earlier]},
        )

    revision = _calculate_and_file_m130_quarter(secure_objects, period=period)

    assert _money(revision, _M130_INGRESOS_CASILLA) == Decimal(ingresos)
    assert _money(revision, _M130_GASTOS) == Decimal(gastos)
    net = Decimal(ingresos) - Decimal(gastos)
    assert _money(revision, _M130_NET) == net
    assert _money(revision, _M130_RATE_SHARE) == net / 5

    payload = _verify_and_export(revision, secure_objects, tmp_path / f"modelo-130-{period}.txt")
    assert payload


@pytest.mark.parametrize(
    ("criterion", "income", "expenses", "net", "marks"),
    [
        (_DEVENGO, "10000.00", "1600.00", "8400.00", False),
        (_CASH, "7500.00", "700.00", "6800.00", True),
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
    _persist_ledger(secure_objects)
    _seed_prior_year_m100(secure_objects)
    for period, result in _OFFICIAL_M130_C19.items():
        _import_official_m130_result_observation(secure_objects, period=period, c19_value=result)

    annual = _annual(secure_objects)

    assert _money(annual, _M100_ACTIVITY_INCOME_CASILLA) == Decimal(income)
    assert _money(annual, _M100_NORMAL_DEDUCTIBLE_EXPENSES_CASILLA) == Decimal(expenses)
    assert _money(annual, _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA) == Decimal(net)

    _register_refund_account(secure_objects)
    payload = _verify_and_export(annual, secure_objects, tmp_path / f"modelo-100-{criterion}.xml")
    with pytest.raises(ModeloInstalmentElectionRefusedError) as split:
        _export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=annual.calculation_revision_id,
                output_path=tmp_path / "split.xml",
                actor="imputation-e2e",
                instalment_election=PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_PAID,
            ),
            workflow_profile=_autonomaworkflow_profile(),
            export_ports=modelo_export_ports_for_test(
                bucket_id=_BUCKET_ID, taxpayer_tax_id=_TAX_ID, secure_objects=secure_objects
            ),
        )
    assert split.value.context is not None and split.value.context["reason"] == "nothing_to_pay"
    assert not (tmp_path / "split.xml").exists()
    assert _election_marks(payload) == (["1"] if marks else [])
    result = _money(annual, _M100_RESULT_CASILLA)
    assert result < 0
    assert _settlement(payload) == {
        "TIPODECLARACION": "D",
        "DEV_IMPORTE": f"{-result:.2f}",
        "DEV_CUENTACORRIENTE": _REFUND_IBAN,
    }
    assert _money(annual, _CASH_ELECTION_CASILLA) == Decimal(1 if marks else 0)
