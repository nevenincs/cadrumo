"""The Modelo 100 withholding credits come from the payer records the taxpayer holds (LIVE path).

Casillas 0596, 0597 and 0603 credit the withholding and the ingresos a cuenta
the taxpayer BORE on work, movable-capital and capital-gain income. Each payer
certifies its figures (RIRPF art. 108.3); the operator records one certificate
per payer, and the calculation sums the class's records. The credit is the
retencion plus the ingreso a cuenta in full, even where the payer passed the
ingreso a cuenta on to the taxpayer (LIRPF arts. 79.e and 99.6).

This module drives the live operator calculate path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`)
over records written through the real write port, and proves:

* two work payers credit 0596 with their summed retencion and ingreso a cuenta;
* a class whose income the profile declares but whose payers are not recorded
  stays unresolved rather than reading as zero;
* a borrador snapshot holding a different 0596 figure is a cross-check only:
  the recorded credit stands, and the borrador is not named as its source;
* the credit reconciliation compares each credit with its declared cross-checks:
  an agreeing borrador says nothing, a disagreeing one withholds filing with
  both figures, and a cross-check with nothing to compare is noted without
  withholding anything;
* the activity withholding in 0599 is compared with the payer certificates of
  activity income, and a residual difference withholds filing;
* under accrual a certificate is compared by the year the payer paid, so an
  invoice accrued in December and paid in January is timing, not a difference.

Real encrypted-SQLite stores, real published authority, real source mesh, real
calculation engine; no mocks. Every identifier and figure is synthetic.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.snapshots import SecureSnapshotRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.retencion_soportada_seed import seed_payer_certificate
from ....adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.secure_object_namespaces import LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....application.aggregation.source_precedence import CallerOverrideDisposition, precedence_ladder_sources
from ....application.aggregation.tests.renta_inmueble_support import (
    TENANT_NIF,
    inmueble,
    lease,
    profile_facts,
    rent,
)
from ....application.calculations.observations_repository import APP_FILING_SOURCE_KIND
from ....application.live.borrador_100 import (
    Borrador100Snapshot,
    Borrador100SnapshotRepository,
    BorradorSnapshotNotFoundError,
    borrador_100_snapshot_object_key,
)
from ....application.live.errors import LiveApplicationInputError
from ....application.live.snapshot_base import SnapshotLifecycleState
from ....application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.calculation_note_gate import (
    ModeloCalculationBlockedError,
    blocking_calculation_issues,
    require_work_unit_calculation_unblocked,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....core.retencion_soportada import RetencionSoportadaClase
from ....core.tipos_actividad import TipoActividad
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from ....domain.contribuyente.arrendamiento_record import Inquilino, InquilinoEdad
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.invoices.tests.catalogue_support import build_invoice_catalogue
from ....domain.iva.schema import InvoiceKind, IvaCategory
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.calculation_revision_sources import CalculationSourceIssue
from ....domain.modelos.filing_kind_evidence import observed_filing_kind_for_local_revision
from ....domain.modelos.filing_record import FilingDeclarationKind
from ....domain.modelos.source_disagreement import DisagreementDecimalValue, SourceDisagreementRole
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from .file_flow_test_support import calculation_ports_for_test
from .observation_seeding_support import save_stamped_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "7d2e9a41-3c58-4f06-8b1e-5a9c0d4e7f22"
_TAX_ID = "12345678Z"

__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


_YEAR = newest_authored_edition("100")
_T0 = datetime(_YEAR + 1, 4, 2, 9, 0, tzinfo=UTC)
_T1 = datetime(_YEAR + 1, 4, 2, 10, 0, tzinfo=UTC)
_ANNUAL_PERIOD = "0A"
_QUARTERS: tuple[str, ...] = ("1T", "2T", "3T", "4T")
_R210_SIMULATOR_URL = aeat_url("www2", configured_path("sede_paths", "r210_simulator_open_ajax"))

_TRABAJO_CASILLA: CasillaId = validated_casilla_id("0596", surface="_TRABAJO_CASILLA")
_CAPITAL_CASILLA: CasillaId = validated_casilla_id("0597", surface="_CAPITAL_CASILLA")
_GANANCIA_CASILLA: CasillaId = validated_casilla_id("0603", surface="_GANANCIA_CASILLA")
_PAGOS_FRACCIONADOS_CASILLA: CasillaId = validated_casilla_id("0604", surface="_PAGOS_FRACCIONADOS_CASILLA")
_TOTAL_PAGOS_A_CUENTA_CASILLA: CasillaId = validated_casilla_id("0609", surface="_TOTAL_PAGOS_A_CUENTA_CASILLA")
_BASE_LIQUIDABLE_NEGATIVA_CASILLA: CasillaId = validated_casilla_id("1391", surface="_BASE_LIQUIDABLE_NEGATIVA")
#: The prior return's remainders that open this year's older Anexo C rows (1380, 1382, 1385).
_PRIOR_ANEXO_C_REMAINDERS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(box, surface="_PRIOR_ANEXO_C_REMAINDERS") for box in ("1384", "1387", "1390")
)
_M130_PAGOS_OUTPUT: CasillaId = validated_casilla_id("19", surface="_M130_PAGOS_OUTPUT")
_M131_PAGOS_OUTPUT: CasillaId = validated_casilla_id("15", surface="_M131_PAGOS_OUTPUT")
_M130_RETENCIONES: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES")

_TRABAJO_BINDING: BindingId = "renta-retencion-soportada-trabajo"
_CAPITAL_BINDING: BindingId = "renta-retencion-soportada-capital-mobiliario"
_GANANCIA_BINDING: BindingId = "renta-retencion-soportada-ganancia-patrimonial"

# Hand-derived oracle. Payer A certifies a 1.200,00 retencion and a 300,00 ingreso
# a cuenta it passed on; payer B certifies a 450,00 retencion. The credit is each
# retencion plus each ingreso a cuenta in full: 1.200,00 + 300,00 + 450,00.
_EXPECTED_TRABAJO_CREDIT = Decimal("1950.00")
# Four Modelo 130 quarters of 100,00 and a Modelo 131 true zero.
_M130_QUARTER = Decimal("100.00")
_EXPECTED_PAGOS_FRACCIONADOS = Decimal("400.00")
_EXPECTED_TOTAL_PAGOS_A_CUENTA = Decimal("2350.00")
# What the AEAT borrador printed for 0596: a figure the records contradict.
_BORRADOR_TRABAJO_FIGURE = Decimal("1800.00")


def _seed_profile(
    *, income_categories: str, rental_activity: bool = False, extra_facts: tuple[UserProfileFact, ...] = ()
) -> None:
    record = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="economic activity"),
                # Advertising services (IAE group 844) is an activity and not an urban rental; group 861.1,
                # "alquiler de viviendas", is the urban rental carried on as an activity.
                UserProfileFact(path="activities.iae_epigraph", value="861.1" if rental_activity else "844"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value=income_categories),
                UserProfileFact(path="censo.activity_start_date", value=date(_YEAR - 5, 1, 1)),
                UserProfileFact(path="withholding.colegio_concertado", value=False),
                UserProfileFact(path="renta_taxpayer.birth_date", value=date(_YEAR - 45, 3, 15)),
                UserProfileFact(path="renta_taxpayer.sex", value="H"),
                UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
                UserProfileFact(path="renta_taxpayer.marriage_full_year", value=False),
                UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
                UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
                UserProfileFact(path="renta_filing.declaration_type", value="1"),
                UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
                UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
                *extra_facts,
            )
        ),
        created_at=_T0,
        updated_at=_T0,
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(record)


def _seed_work_payers(operation: PinnedAuthorityOperation) -> None:
    seed_payer_certificate(
        operation=operation,
        taxpayer_tax_id=_TAX_ID,
        ejercicio=_YEAR,
        payer_tax_id="B00010082",
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion=Decimal("1200.00"),
        ingreso_a_cuenta=Decimal("300.00"),
        ingreso_a_cuenta_repercutido=Decimal("300.00"),
        importe_integro_dinerario=Decimal("8000.00"),
        valoracion_especie=Decimal("1500.00"),
    )
    seed_payer_certificate(
        operation=operation,
        taxpayer_tax_id=_TAX_ID,
        ejercicio=_YEAR,
        payer_tax_id="A00010009",
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion=Decimal("450.00"),
        importe_integro_dinerario=Decimal("3000.00"),
    )


def _save_filing(
    repository: CalculationObservationRepository,
    *,
    modelo: str,
    period: str,
    casilla_values: dict[CasillaId, Decimal],
    filing_year: int,
) -> None:
    save_stamped_observation(
        repository,
        RegistryModeloObservation(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observations=registry_grounded_observations(
                modelo=modelo, filing_year=filing_year, period=period, casilla_values=casilla_values
            ),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_T0,
        filing_kind=observed_filing_kind_for_local_revision(
            FilingDeclarationKind.ORIGINAL, source_locator=f"local-filing:{modelo}:{filing_year}:{period}"
        ),
    )


def _seed_filed_history(
    secure_objects: SecureObjectRepository, *, fourth_quarter_retenciones: Decimal | None = None
) -> None:
    """The prior year's zero carry and this year's locally filed pagos fraccionados.

    ``fourth_quarter_retenciones`` is the retencion the filed fourth-quarter
    Modelo 130 deducted in casilla 06; without it that return states none.
    """
    repository = CalculationObservationRepository(objects=secure_objects)
    _save_filing(
        repository,
        modelo="100",
        period=_ANNUAL_PERIOD,
        casilla_values=dict.fromkeys((_BASE_LIQUIDABLE_NEGATIVA_CASILLA, *_PRIOR_ANEXO_C_REMAINDERS), Decimal("0")),
        filing_year=_YEAR - 1,
    )
    for period in _QUARTERS:
        _save_filing(
            repository,
            modelo="130",
            period=period,
            casilla_values={
                _M130_PAGOS_OUTPUT: _M130_QUARTER,
                **(
                    {_M130_RETENCIONES: fourth_quarter_retenciones}
                    if period == "4T" and fourth_quarter_retenciones is not None
                    else {}
                ),
            },
            filing_year=_YEAR,
        )
        _save_filing(
            repository,
            modelo="131",
            period=period,
            casilla_values={_M131_PAGOS_OUTPUT: Decimal("0")},
            filing_year=_YEAR,
        )


def _borrador_repository(objects: SecureObjectRepository) -> Borrador100SnapshotRepository:
    return SecureSnapshotRepository(
        bucket_id=_BUCKET_ID,
        payload_model=Borrador100Snapshot,
        namespace_definition=LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE,
        object_key=borrador_100_snapshot_object_key,
        not_found_factory=lambda snapshot_id: BorradorSnapshotNotFoundError(
            translated_message="application.live.borrador.errors.snapshot_not_found",
            context={"snapshot_id": snapshot_id},
        ),
        ambiguous_prefix_factory=lambda snapshot_id, snapshot_ids: BorradorSnapshotNotFoundError(
            translated_message="application.live.borrador.errors.snapshot_prefix_ambiguous",
            context={"snapshot_id": snapshot_id, "match_count": len(snapshot_ids)},
        ),
        domain_label="borrador",
        input_error_cls=LiveApplicationInputError,
        objects=objects,
    )


def _caller_binding_values() -> dict[BindingId, Decimal]:
    """Zero every caller-owned binding; the mesh resolves the profile, relations and payer records."""
    snapshot = published_authority_operation().snapshot("100", filing_year=_YEAR, period=_ANNUAL_PERIOD)
    resolved_elsewhere = frozenset({"profile", "relation_prefill", "retencion_soportada"}) | {
        kind.value for kind in precedence_ladder_sources(CallerOverrideDisposition.LOCK)
    }
    return {
        binding.id: Decimal("0") for binding in snapshot.revision.bindings if binding.source not in resolved_elsewhere
    }


def _calculate(
    secure_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
    borrador: Borrador100SnapshotRepository | None = None,
    borrador_snapshot_id: str | None = None,
    casilla_inputs: dict[CasillaId, Decimal] | None = None,
) -> BucketAggregationCalculationResult:
    wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    snapshot = published_authority_operation().snapshot("100", filing_year=_YEAR, period=_ANNUAL_PERIOD)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _ANNUAL_PERIOD),
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(
            work_unit_repository=wu_repo,
            bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
        ),
        clock=_T0,
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        work_unit_repository=wu_repo,
        borrador_snapshot_repository=borrador,
    ) as ports:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            binding_values=_caller_binding_values(),
            casilla_inputs=casilla_inputs,
            borrador_snapshot_id=borrador_snapshot_id,
            ports=ports,
            clock=_T1,
        )


def test_two_work_payers_credit_0596_with_their_retencion_and_ingreso_a_cuenta_in_full(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    _seed_profile(income_categories="trabajo,actividad_economica")
    _seed_filed_history(secure_objects)
    _seed_work_payers(operation)

    revision = _calculate(secure_objects, operation=operation).revision

    values = revision.casilla_values
    assert Decimal(values[_TRABAJO_CASILLA]) == _EXPECTED_TRABAJO_CREDIT
    assert Decimal(revision.binding_overrides[_TRABAJO_BINDING]) == _EXPECTED_TRABAJO_CREDIT
    # The profile declares no movable-capital or capital-gain income, which proves those credits zero.
    assert Decimal(values[_CAPITAL_CASILLA]) == Decimal("0")
    assert Decimal(values[_GANANCIA_CASILLA]) == Decimal("0")
    assert Decimal(values[_PAGOS_FRACCIONADOS_CASILLA]) == _EXPECTED_PAGOS_FRACCIONADOS
    assert Decimal(values[_TOTAL_PAGOS_A_CUENTA_CASILLA]) == _EXPECTED_TOTAL_PAGOS_A_CUENTA
    credit_casillas = {_TRABAJO_CASILLA, _CAPITAL_CASILLA, _GANANCIA_CASILLA}
    assert not [
        issue
        for issue in revision.source_issues
        if issue.reason == "unresolved_binding" and issue.casilla_id in credit_casillas
    ]


def test_a_declared_class_without_payer_records_stays_unresolved_rather_than_zero(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """Movable-capital income is declared and no payer of it recorded: 0597 is unresolved, never zero."""
    _seed_profile(income_categories="trabajo,actividad_economica,capital_mobiliario")
    _seed_filed_history(secure_objects)
    _seed_work_payers(operation)

    result = _calculate(secure_objects, operation=operation)

    unresolved = {
        diagnostic.binding_id for diagnostic in result.source_diagnostics if diagnostic.reason == "unresolved_binding"
    }
    assert _CAPITAL_BINDING in unresolved
    assert _TRABAJO_BINDING not in unresolved
    revision = result.revision
    assert _CAPITAL_BINDING not in revision.binding_overrides
    assert Decimal(revision.casilla_values[_TRABAJO_CASILLA]) == _EXPECTED_TRABAJO_CREDIT
    assert revision.casilla_values.get(_CAPITAL_CASILLA) is None
    assert revision.casilla_values.get(_TOTAL_PAGOS_A_CUENTA_CASILLA) is None


def test_a_borrador_holding_another_0596_figure_does_not_replace_the_recorded_credit(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    _seed_profile(income_categories="trabajo,actividad_economica")
    _seed_filed_history(secure_objects)
    _seed_work_payers(operation)
    borrador = _borrador_repository(secure_objects)
    snapshot = Borrador100Snapshot(
        snapshot_id="b" * 64,
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _ANNUAL_PERIOD),
        registry_snapshot_ref=published_authority_operation()
        .snapshot("100", filing_year=_YEAR, period=_ANNUAL_PERIOD)
        .snapshot_ref,
        captured_at=_T0,
        source_url=_R210_SIMULATOR_URL,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values={_TRABAJO_BINDING: _BORRADOR_TRABAJO_FIGURE},
    )
    borrador.save(snapshot)

    revision = _calculate(
        secure_objects, operation=operation, borrador=borrador, borrador_snapshot_id=snapshot.snapshot_id
    ).revision

    assert revision.borrador_snapshot_id == snapshot.snapshot_id
    assert Decimal(revision.casilla_values[_TRABAJO_CASILLA]) == _EXPECTED_TRABAJO_CREDIT
    assert Decimal(revision.binding_overrides[_TRABAJO_BINDING]) == _EXPECTED_TRABAJO_CREDIT
    assert _TRABAJO_BINDING not in revision.bindings_sourced_from_borrador
    assert Decimal(revision.casilla_values[_TOTAL_PAGOS_A_CUENTA_CASILLA]) == _EXPECTED_TOTAL_PAGOS_A_CUENTA


_ACTIVIDAD_CASILLA: CasillaId = validated_casilla_id("0599", surface="_ACTIVIDAD_CASILLA")
_ACTIVIDAD_BINDING: BindingId = "renta-ledger-actividad-retenciones-0599"
# A payer of activity income certifies 150,00 withheld; the ledger holds no invoice that declares it.
_ACTIVIDAD_PAYER_RETENCION = Decimal("150.00")


def _save_borrador(
    secure_objects: SecureObjectRepository, binding_values: dict[BindingId, Decimal]
) -> tuple[Borrador100SnapshotRepository, str]:
    borrador = _borrador_repository(secure_objects)
    snapshot = Borrador100Snapshot(
        snapshot_id="c" * 64,
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _ANNUAL_PERIOD),
        registry_snapshot_ref=published_authority_operation()
        .snapshot("100", filing_year=_YEAR, period=_ANNUAL_PERIOD)
        .snapshot_ref,
        captured_at=_T0,
        source_url=_R210_SIMULATOR_URL,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values=binding_values,
    )
    borrador.save(snapshot)
    return borrador, snapshot.snapshot_id


def _credit_issues(revision: CalculationRevision, reason: str, casilla: CasillaId) -> list[CalculationSourceIssue]:
    return [issue for issue in revision.source_issues if issue.reason == reason and issue.casilla_id == casilla]


def test_a_borrador_agreeing_with_the_recorded_credit_raises_no_finding(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    _seed_profile(income_categories="trabajo,actividad_economica")
    _seed_filed_history(secure_objects)
    _seed_work_payers(operation)
    borrador, snapshot_id = _save_borrador(secure_objects, {_TRABAJO_BINDING: _EXPECTED_TRABAJO_CREDIT})

    revision = _calculate(
        secure_objects, operation=operation, borrador=borrador, borrador_snapshot_id=snapshot_id
    ).revision

    assert not _credit_issues(revision, "credit_source_disagreement", _TRABAJO_CASILLA)
    assert not _credit_issues(revision, "credit_cross_check_absent", _TRABAJO_CASILLA)
    assert Decimal(revision.casilla_values[_TRABAJO_CASILLA]) == _EXPECTED_TRABAJO_CREDIT


def test_a_borrador_disagreeing_with_the_recorded_credit_withholds_filing_with_both_figures(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    _seed_profile(income_categories="trabajo,actividad_economica")
    _seed_filed_history(secure_objects)
    _seed_work_payers(operation)
    borrador, snapshot_id = _save_borrador(secure_objects, {_TRABAJO_BINDING: _BORRADOR_TRABAJO_FIGURE})

    result = _calculate(secure_objects, operation=operation, borrador=borrador, borrador_snapshot_id=snapshot_id)
    revision = result.revision

    (issue,) = _credit_issues(revision, "credit_source_disagreement", _TRABAJO_CASILLA)
    assert issue in blocking_calculation_issues(revision)
    fact = issue.disagreement
    assert fact is not None
    assert fact.selected_role is SourceDisagreementRole.VALUE_SOURCE
    stated = {entry.role: entry.value for entry in fact.sources}
    assert stated == {
        SourceDisagreementRole.VALUE_SOURCE: DisagreementDecimalValue.of(_EXPECTED_TRABAJO_CREDIT),
        SourceDisagreementRole.CROSS_CHECK: DisagreementDecimalValue.of(_BORRADOR_TRABAJO_FIGURE),
    }
    # The recorded credit is still the value; the borrador only disagrees with it.
    assert Decimal(revision.casilla_values[_TRABAJO_CASILLA]) == _EXPECTED_TRABAJO_CREDIT
    assert any(
        diagnostic.reason == "credit_source_disagreement" and diagnostic.casilla_id == _TRABAJO_CASILLA
        for diagnostic in result.source_diagnostics
    )


def test_a_credit_without_a_borrador_is_noted_as_not_cross_checked_and_still_files(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    _seed_profile(income_categories="trabajo,actividad_economica")
    _seed_filed_history(secure_objects)
    _seed_work_payers(operation)

    revision = _calculate(secure_objects, operation=operation).revision

    for casilla in (_TRABAJO_CASILLA, _CAPITAL_CASILLA, _GANANCIA_CASILLA):
        (absent,) = _credit_issues(revision, "credit_cross_check_absent", casilla)
        assert absent not in blocking_calculation_issues(revision)
        assert not _credit_issues(revision, "credit_source_disagreement", casilla)


def test_activity_withholding_the_payer_certifies_and_the_ledger_does_not_declare_withholds_filing(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    _seed_profile(income_categories="trabajo,actividad_economica")
    _seed_filed_history(secure_objects)
    _seed_work_payers(operation)
    seed_payer_certificate(
        operation=operation,
        taxpayer_tax_id=_TAX_ID,
        ejercicio=_YEAR,
        payer_tax_id="B11111111",
        income_class=RetencionSoportadaClase.ACTIVIDAD_ECONOMICA,
        retencion=_ACTIVIDAD_PAYER_RETENCION,
        importe_integro_dinerario=Decimal("1000.00"),
    )

    revision = _calculate(secure_objects, operation=operation).revision

    ledger_value = Decimal(revision.casilla_values[_ACTIVIDAD_CASILLA])
    assert ledger_value != _ACTIVIDAD_PAYER_RETENCION
    (issue,) = _credit_issues(revision, "credit_source_disagreement", _ACTIVIDAD_CASILLA)
    assert issue in blocking_calculation_issues(revision)
    assert issue.disagreement is not None
    stated = {entry.role: entry.value for entry in issue.disagreement.sources}
    assert stated[SourceDisagreementRole.VALUE_SOURCE] == DisagreementDecimalValue.of(ledger_value)
    assert stated[SourceDisagreementRole.CROSS_CHECK] == DisagreementDecimalValue.of(_ACTIVIDAD_PAYER_RETENCION)
    # The payer record is read by the comparison, so it is not reported as unrouted.
    assert not [issue for issue in revision.source_issues if issue.reason == "unrouted_observation"]


def test_activity_withholding_agreeing_with_the_borrador_and_without_payer_records(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    _seed_profile(income_categories="trabajo,actividad_economica")
    _seed_filed_history(secure_objects)
    _seed_work_payers(operation)
    baseline = _calculate(secure_objects, operation=operation).revision
    ledger_value = Decimal(baseline.casilla_values[_ACTIVIDAD_CASILLA])
    borrador, snapshot_id = _save_borrador(secure_objects, {_ACTIVIDAD_BINDING: ledger_value})

    revision = _calculate(
        secure_objects, operation=operation, borrador=borrador, borrador_snapshot_id=snapshot_id
    ).revision

    assert not _credit_issues(revision, "credit_source_disagreement", _ACTIVIDAD_CASILLA)
    # No payer of activity income is recorded, so that comparison has nothing to read.
    assert [
        issue
        for issue in _credit_issues(revision, "credit_cross_check_absent", _ACTIVIDAD_CASILLA)
        if issue.source_ref == "income_class:actividad_economica"
    ]


_ARRENDAMIENTO_CASILLA: CasillaId = validated_casilla_id("0598", surface="_ARRENDAMIENTO_CASILLA")
_RENTAL_ACTIVITY_BINDING: BindingId = "renta-retencion-soportada-arrendamiento-actividad"
# The tenant of a non-activity urban rental certifies 190,00 withheld.
_TENANT_PAYER = "B22222222"
_TENANT_RETENCION = Decimal("190.00")


def _seed_tenant(operation: PinnedAuthorityOperation) -> None:
    seed_payer_certificate(
        operation=operation,
        taxpayer_tax_id=_TAX_ID,
        ejercicio=_YEAR,
        payer_tax_id=_TENANT_PAYER,
        income_class=RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO,
        retencion=_TENANT_RETENCION,
        importe_integro_dinerario=Decimal("1000.00"),
    )


def _let_property(tenant_nif: str) -> tuple[UserProfileFact, ...]:
    """A dwelling held all year and let since the year before to one tenant, as profile facts."""
    let = lease(
        start=date(_YEAR - 1, 9, 1),
        inquilinos=(Inquilino(nif=tenant_nif, franja_edad=InquilinoEdad.OTRA, extranjero=False),),
    )
    facts = profile_facts((inmueble(ejercicio=_YEAR),), (let,))
    return tuple(UserProfileFact(path=path, value=value) for path, value in facts.items())


@pytest.mark.parametrize(
    ("tenant_nif", "placed"),
    [(_TENANT_PAYER, _TENANT_RETENCION), (TENANT_NIF, Decimal("0.00"))],
    ids=["the-certifying-payer-is-the-tenant", "the-certifying-payer-is-no-tenant"],
)
def test_the_property_withholding_in_0598_is_compared_with_the_tenants_certificates(
    secure_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
    tenant_nif: str,
    placed: Decimal,
) -> None:
    """A certificate reaches 0153 through the lease that names its payer; one no lease names stays a disagreement."""
    _seed_profile(
        income_categories="trabajo,actividad_economica,capital_inmobiliario",
        extra_facts=_let_property(tenant_nif),
    )
    _seed_filed_history(secure_objects)
    _seed_work_payers(operation)
    _seed_tenant(operation)
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions(
            tuple(
                rent(
                    f"rent-{month}",
                    amount=Decimal("100.00"),
                    booked=date(_YEAR, month, 1),
                    business_classification=BusinessClassification.PERSONAL,
                    lifecycle_state=TransactionLifecycleState.ACTIVE,
                    classified_at=_T0,
                    classified_by="manual",
                )
                for month in range(1, 13)
            )
        )
    )

    revision = _calculate(secure_objects, operation=operation).revision

    # The rental is not an activity (group 844), so its activity part is a proven zero.
    assert Decimal(revision.casilla_values[_ARRENDAMIENTO_CASILLA]) == placed
    disagreements = _credit_issues(revision, "credit_source_disagreement", _ARRENDAMIENTO_CASILLA)
    if placed == _TENANT_RETENCION:
        assert not disagreements
        return
    (issue,) = disagreements
    assert issue in blocking_calculation_issues(revision)
    assert issue.disagreement is not None
    stated = {entry.role: (entry.source_ref, entry.value) for entry in issue.disagreement.sources}
    assert stated == {
        SourceDisagreementRole.VALUE_SOURCE: ("casilla:0153", DisagreementDecimalValue.of(placed)),
        SourceDisagreementRole.CROSS_CHECK: (
            "income_class:arrendamiento_inmueble_urbano",
            DisagreementDecimalValue.of(_TENANT_RETENCION),
        ),
    }


def test_a_declared_rental_activity_without_its_certificates_leaves_0598_unresolved(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """Group 861 declares an urban rental carried on as an activity, so its withholding needs the payer evidence."""
    _seed_profile(income_categories="trabajo,actividad_economica", rental_activity=True)
    _seed_filed_history(secure_objects)
    _seed_work_payers(operation)

    result = _calculate(secure_objects, operation=operation)

    assert _RENTAL_ACTIVITY_BINDING in {
        diagnostic.binding_id for diagnostic in result.source_diagnostics if diagnostic.reason == "unresolved_binding"
    }
    assert result.revision.casilla_values.get(_ARRENDAMIENTO_CASILLA) is None


def test_an_unresolved_rental_activity_credit_refuses_verify_by_its_box_before_any_draft_is_built(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """The binding is a formula operand with no box of its own, so its note names the box it leaves open.

    Verify refuses on the stored note before the workflow ever builds a draft, so the operator reads
    which credit is missing instead of a draft that failed to build.
    """
    _seed_profile(income_categories="trabajo,actividad_economica", rental_activity=True)
    _seed_filed_history(secure_objects)
    _seed_work_payers(operation)

    revision = _calculate(secure_objects, operation=operation).revision

    (unresolved,) = [
        issue
        for issue in blocking_calculation_issues(revision)
        if issue.reason == "unresolved_binding" and issue.binding_source is BindingSourceKind.RETENCION_SOPORTADA
    ]
    assert unresolved.casilla_id == _ARRENDAMIENTO_CASILLA
    assert unresolved.fact is not None
    assert (
        dict(unresolved.fact.values)["income_class"] == RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO_ACTIVIDAD
    )
    work_unit = (
        WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
        .load()
        .work_units[revision.work_unit_id]
    )
    with pytest.raises(ModeloCalculationBlockedError) as refused:
        require_work_unit_calculation_unblocked(
            work_unit=work_unit, revision=revision, action="verify", operation=operation
        )
    context = refused.value.context
    assert context is not None
    assert context["reason"] == "unresolved_binding"


_PAYER_CREDIT = Decimal("500.00")
_BORRADOR_CREDIT_CLASSES = pytest.mark.parametrize(
    ("income_class", "category", "casilla", "binding"),
    [
        (RetencionSoportadaClase.TRABAJO, "trabajo", _TRABAJO_CASILLA, _TRABAJO_BINDING),
        (RetencionSoportadaClase.CAPITAL_MOBILIARIO, "capital_mobiliario", _CAPITAL_CASILLA, _CAPITAL_BINDING),
        (RetencionSoportadaClase.GANANCIA_PATRIMONIAL, "ganancias_patrimoniales", _GANANCIA_CASILLA, _GANANCIA_BINDING),
    ],
    ids=["0596", "0597", "0603"],
)


@_BORRADOR_CREDIT_CLASSES
@pytest.mark.parametrize(
    ("borrador_figure", "disagrees"), [(_PAYER_CREDIT, False), (Decimal("499.99"), True)], ids=["agree", "differ"]
)
def test_each_certificate_credit_is_cross_checked_by_the_borrador_to_the_cent(
    secure_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
    income_class: RetencionSoportadaClase,
    category: str,
    casilla: CasillaId,
    binding: BindingId,
    borrador_figure: Decimal,
    disagrees: bool,
) -> None:
    _seed_profile(income_categories=f"actividad_economica,{category}")
    _seed_filed_history(secure_objects)
    seed_payer_certificate(
        operation=operation,
        taxpayer_tax_id=_TAX_ID,
        ejercicio=_YEAR,
        payer_tax_id="B33333333",
        income_class=income_class,
        retencion=_PAYER_CREDIT,
        importe_integro_dinerario=Decimal("2500.00"),
    )
    borrador, snapshot_id = _save_borrador(secure_objects, {binding: borrador_figure})

    revision = _calculate(
        secure_objects, operation=operation, borrador=borrador, borrador_snapshot_id=snapshot_id
    ).revision

    assert Decimal(revision.casilla_values[casilla]) == _PAYER_CREDIT
    assert not _credit_issues(revision, "credit_cross_check_absent", casilla)
    disagreements = _credit_issues(revision, "credit_source_disagreement", casilla)
    assert len(disagreements) == (1 if disagrees else 0)
    assert all(issue in blocking_calculation_issues(revision) for issue in disagreements)


# Hand-derived oracle for the payer-year comparison. One invoice of 1.000,00 plus
# 210,00 IVA less 150,00 retained (15 %), issued 20 December of the year before and
# paid net, 1.060,00, on 10 January. Under accrual its income and its 150,00 belong
# to the year before, so 0599 holds 0,00 this year, while the payer certifies the
# 150,00 in the year it paid: the receipt's own payment date explains the gap.
_BOUNDARY_BASE = Decimal("1000.00")
_BOUNDARY_IVA = Decimal("210.00")
_BOUNDARY_RETENCION = Decimal("150.00")
_BOUNDARY_ISSUED = date(_YEAR - 1, 12, 20)
_BOUNDARY_PAID = date(_YEAR, 1, 10)


def _accrual_facts() -> tuple[UserProfileFact, ...]:
    return tuple(
        UserProfileFact.model_validate(
            {"path": path, "value": value, "valid_from": date(year, 1, 1), "valid_to": date(year, 12, 31)}
        )
        for year in (_YEAR - 1, _YEAR)
        for path, value in (
            ("irpf.activity_income_imputation_criterion", "devengo"),
            ("irpf.codigo_comercio_accounting", False),
        )
    )


def _boundary_receipt(invoice_id: str | None, *, paid: date = _BOUNDARY_PAID) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id="cobro-boundary",
                booked_date=paid,
                value_date=paid,
                amount=_BOUNDARY_BASE + _BOUNDARY_IVA - _BOUNDARY_RETENCION,
                currency="EUR",
                counterparty="Cliente SL",
                description="cobro factura",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="e" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=_T0,
                    provider_name="CSV provider",
                ),
                raw_fields={},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": "actividad_economica",
            "taxable_base": _BOUNDARY_BASE,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _T0,
            "classified_by": "manual",
            "invoice_id": invoice_id,
        },
    )


def _boundary_invoice(receipt_id: str, *, issued: date = _BOUNDARY_ISSUED) -> Invoice:
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "F-BOUNDARY",
            "issued_at": issued,
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "bucket_id": _BUCKET_ID,
            "base_total": _BOUNDARY_BASE,
            "iva_total": _BOUNDARY_IVA,
            "grand_total": _BOUNDARY_BASE + _BOUNDARY_IVA,
            "currency": "EUR",
            "lines": (
                InvoiceLine(
                    description="Servicios profesionales",
                    quantity=Decimal("1"),
                    unit_price=_BOUNDARY_BASE,
                    subtotal=_BOUNDARY_BASE,
                    iva_rate=IvaRate.from_registry("RATE_21"),
                    iva_amount=_BOUNDARY_IVA,
                ),
            ),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory("domestic_general"),
            "retention_rate": Decimal("0.15"),
            "retention_amount": _BOUNDARY_RETENCION,
            "linked_transaction_ids": (receipt_id,),
        },
    )


def _seed_boundary_invoice(
    secure_objects: SecureObjectRepository, *, issued: date = _BOUNDARY_ISSUED, paid: date = _BOUNDARY_PAID
) -> None:
    invoice = _boundary_invoice(_boundary_receipt(None, paid=paid).transaction_id, issued=issued)
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((_boundary_receipt(invoice.invoice_id, paid=paid),))
    )
    InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(build_invoice_catalogue((invoice,)))


def _seed_activity_payer(operation: PinnedAuthorityOperation, retencion: Decimal) -> None:
    seed_payer_certificate(
        operation=operation,
        taxpayer_tax_id=_TAX_ID,
        ejercicio=_YEAR,
        payer_tax_id="B00015016",
        income_class=RetencionSoportadaClase.ACTIVIDAD_ECONOMICA,
        retencion=retencion,
        importe_integro_dinerario=_BOUNDARY_BASE,
    )


def _accrual_boundary_revision(
    secure_objects: SecureObjectRepository, operation: PinnedAuthorityOperation, certified: Decimal
) -> CalculationRevision:
    _seed_profile(income_categories="trabajo,actividad_economica", extra_facts=_accrual_facts())
    _seed_filed_history(secure_objects)
    _seed_work_payers(operation)
    _seed_boundary_invoice(secure_objects)
    _seed_activity_payer(operation, certified)
    return _calculate(secure_objects, operation=operation).revision


def test_a_certificate_of_withholding_accrued_the_year_before_and_paid_this_year_is_timing(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    revision = _accrual_boundary_revision(secure_objects, operation, _BOUNDARY_RETENCION)

    assert Decimal(revision.casilla_values[_ACTIVIDAD_CASILLA]) == Decimal("0")
    assert not _credit_issues(revision, "credit_source_disagreement", _ACTIVIDAD_CASILLA)
    assert all(
        issue.source_ref != "income_class:actividad_economica"
        for issue in _credit_issues(revision, "credit_cross_check_absent", _ACTIVIDAD_CASILLA)
    )


def test_a_certificate_the_payment_dates_do_not_explain_still_withholds_filing(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """The payer certifies 200,00; the receipt paid this year explains 150,00, leaving 50,00."""
    revision = _accrual_boundary_revision(secure_objects, operation, Decimal("200.00"))

    (issue,) = _credit_issues(revision, "credit_source_disagreement", _ACTIVIDAD_CASILLA)
    assert issue in blocking_calculation_issues(revision)
    assert issue.disagreement is not None
    stated = {entry.role: entry.value for entry in issue.disagreement.sources}
    assert stated[SourceDisagreementRole.VALUE_SOURCE] == DisagreementDecimalValue.of(Decimal("0"))
    assert stated[SourceDisagreementRole.CROSS_CHECK] == DisagreementDecimalValue.of(Decimal("200.00"))


_FILED_RETENCIONES_REF = "filed:130:4T:06"


def _filed_issues(revision: CalculationRevision, reason: str) -> list[CalculationSourceIssue]:
    return [
        issue
        for issue in _credit_issues(revision, reason, _ACTIVIDAD_CASILLA)
        if issue.source_ref == _FILED_RETENCIONES_REF
    ]


def test_the_activity_credit_agreeing_with_the_filed_fourth_quarter_retenciones_raises_no_finding(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """No activity income bears withholding, and the filed fourth quarter deducted none."""
    _seed_profile(income_categories="trabajo,actividad_economica")
    _seed_filed_history(secure_objects, fourth_quarter_retenciones=Decimal("0"))
    _seed_work_payers(operation)

    revision = _calculate(secure_objects, operation=operation).revision

    assert Decimal(revision.casilla_values[_ACTIVIDAD_CASILLA]) == Decimal("0")
    assert not _filed_issues(revision, "credit_source_disagreement")
    assert not _filed_issues(revision, "credit_cross_check_absent")


def test_filed_fourth_quarter_retenciones_the_records_do_not_explain_withhold_filing(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """The filed fourth quarter deducted 100,00 that no activity income of the year bears."""
    _seed_profile(income_categories="trabajo,actividad_economica")
    _seed_filed_history(secure_objects, fourth_quarter_retenciones=Decimal("100.00"))
    _seed_work_payers(operation)

    revision = _calculate(secure_objects, operation=operation).revision

    (issue,) = _filed_issues(revision, "credit_source_disagreement")
    assert issue in blocking_calculation_issues(revision)
    assert issue.disagreement is not None
    stated = {entry.role: entry.value for entry in issue.disagreement.sources}
    assert stated[SourceDisagreementRole.VALUE_SOURCE] == DisagreementDecimalValue.of(Decimal("0"))
    assert stated[SourceDisagreementRole.CROSS_CHECK] == DisagreementDecimalValue.of(Decimal("100.00"))


def _seed_rental_activity_receipt(secure_objects: SecureObjectRepository) -> None:
    """A rental activity (A01) invoice of the year, paid in the year with 150,00 withheld."""
    invoice = _boundary_invoice(_boundary_receipt(None, paid=_IN_YEAR_PAID).transaction_id, issued=_IN_YEAR_ISSUED)
    receipt = _boundary_receipt(invoice.invoice_id, paid=_IN_YEAR_PAID).model_copy(
        update={"tipo_actividad": TipoActividad.A01_ARRENDADORES_BIENES_INMUEBLES}
    )
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((receipt,))
    )
    InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(build_invoice_catalogue((invoice,)))


_IN_YEAR_ISSUED = date(_YEAR, 6, 10)
_IN_YEAR_PAID = date(_YEAR, 6, 20)


def test_a_fourth_quarter_that_deducted_the_rental_activity_retenciones_is_itemisation(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """The annual activity credit leaves the 150,00 to the rental credit; the pago fraccionado deducts it."""
    _seed_profile(income_categories="trabajo,actividad_economica")
    _seed_filed_history(secure_objects, fourth_quarter_retenciones=_BOUNDARY_RETENCION)
    _seed_work_payers(operation)
    _seed_rental_activity_receipt(secure_objects)

    revision = _calculate(secure_objects, operation=operation).revision

    assert Decimal(revision.casilla_values[_ACTIVIDAD_CASILLA]) == Decimal("0")
    assert not _filed_issues(revision, "credit_source_disagreement")
    assert not _filed_issues(revision, "credit_cross_check_absent")


def test_a_fourth_quarter_that_left_out_the_rental_activity_retenciones_withholds_filing(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """The records bear 150,00 the pago fraccionado could deduct; the filed return deducted none."""
    _seed_profile(income_categories="trabajo,actividad_economica")
    _seed_filed_history(secure_objects, fourth_quarter_retenciones=Decimal("0"))
    _seed_work_payers(operation)
    _seed_rental_activity_receipt(secure_objects)

    revision = _calculate(secure_objects, operation=operation).revision

    (issue,) = _filed_issues(revision, "credit_source_disagreement")
    assert issue in blocking_calculation_issues(revision)
    assert issue.disagreement is not None
    stated = {entry.role: entry.value for entry in issue.disagreement.sources}
    assert stated[SourceDisagreementRole.CROSS_CHECK] == DisagreementDecimalValue.of(Decimal("0"))


def test_a_filed_fourth_quarter_without_its_retenciones_is_noted_as_not_cross_checked(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    _seed_profile(income_categories="trabajo,actividad_economica")
    _seed_filed_history(secure_objects)
    _seed_work_payers(operation)

    revision = _calculate(secure_objects, operation=operation).revision

    (absent,) = _filed_issues(revision, "credit_cross_check_absent")
    assert absent not in blocking_calculation_issues(revision)
