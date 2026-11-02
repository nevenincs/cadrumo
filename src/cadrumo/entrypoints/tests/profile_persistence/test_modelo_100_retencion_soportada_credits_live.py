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
  the recorded credit stands, and the borrador is not named as its source.

Real encrypted-SQLite stores, real published authority, real source mesh, real
calculation engine; no mocks. Every identifier and figure is synthetic.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
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
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from ....domain.modelos.filing_kind_evidence import observed_filing_kind_for_local_revision
from ....domain.modelos.filing_record import FilingDeclarationKind
from ....domain.user_profile.tests.general_regime_facts import GENERAL_REGIME_NATURAL_PERSON_FACTS
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
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
_M130_PAGOS_OUTPUT: CasillaId = validated_casilla_id("19", surface="_M130_PAGOS_OUTPUT")
_M131_PAGOS_OUTPUT: CasillaId = validated_casilla_id("15", surface="_M131_PAGOS_OUTPUT")

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


def _seed_profile(*, income_categories: str) -> None:
    record = _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value=_TAX_ID),
            UserProfileFact(path="identity.name", value="Test"),
            UserProfileFact(path="identity.surnames", value="Operator"),
            UserProfileFact(path="activities.description", value="economic activity"),
            *GENERAL_REGIME_NATURAL_PERSON_FACTS,
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
        ),
        created_at=_T0,
        updated_at=_T0,
        context=_profile_creation_context_for_test(),
    )
    seed_test_profile_record(record)


def _seed_work_payers(operation: PinnedAuthorityOperation) -> None:
    seed_payer_certificate(
        operation=operation,
        taxpayer_tax_id=_TAX_ID,
        ejercicio=_YEAR,
        payer_tax_id="B00000000",
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
        payer_tax_id="A00000000",
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion=Decimal("450.00"),
        importe_integro_dinerario=Decimal("3000.00"),
    )


def _save_filing(
    repository: CalculationObservationRepository,
    *,
    modelo: str,
    period: str,
    casilla_id: CasillaId,
    value: Decimal,
    filing_year: int,
) -> None:
    save_stamped_observation(
        repository,
        RegistryModeloObservation(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observations=registry_grounded_observations(
                modelo=modelo, filing_year=filing_year, period=period, casilla_values={casilla_id: value}
            ),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_T0,
        filing_kind=observed_filing_kind_for_local_revision(
            FilingDeclarationKind.ORIGINAL, source_locator=f"local-filing:{modelo}:{filing_year}:{period}"
        ),
    )


def _seed_filed_history(secure_objects: SecureObjectRepository) -> None:
    """The prior year's zero carry and this year's locally filed pagos fraccionados."""
    repository = CalculationObservationRepository(objects=secure_objects)
    _save_filing(
        repository,
        modelo="100",
        period=_ANNUAL_PERIOD,
        casilla_id=_BASE_LIQUIDABLE_NEGATIVA_CASILLA,
        value=Decimal("0"),
        filing_year=_YEAR - 1,
    )
    for period in _QUARTERS:
        _save_filing(
            repository,
            modelo="130",
            period=period,
            casilla_id=_M130_PAGOS_OUTPUT,
            value=_M130_QUARTER,
            filing_year=_YEAR,
        )
        _save_filing(
            repository,
            modelo="131",
            period=period,
            casilla_id=_M131_PAGOS_OUTPUT,
            value=Decimal("0"),
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
