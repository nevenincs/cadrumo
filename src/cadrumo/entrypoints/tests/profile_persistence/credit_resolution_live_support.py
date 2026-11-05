"""A Modelo 100 whose withholding credits disagree with the borrador, over real encrypted stores.

The suffered-withholding credit casillas 0596 and 0597 are valued from payer
certificates and cross-checked with the AEAT borrador. This module seeds a
profile, its certificates and the filed history a Modelo 100 reads, and
calculates the one annual work unit as often as a test asks, each time with the
borrador figures it is given. Every identifier and figure is synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.credit_resolution_records import CreditResolutionRepositoryAdapter
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.snapshots import SecureSnapshotRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.retencion_soportada_seed import seed_payer_certificate
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
from ....domain.modelos.work_unit import WorkUnit
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from .file_flow_test_support import calculation_ports_for_test
from .observation_seeding_support import save_stamped_observation

__all__ = [
    "BUCKET_ID",
    "CAPITAL_BINDING",
    "CAPITAL_CASILLA",
    "EXPECTED_CAPITAL_CREDIT",
    "EXPECTED_TRABAJO_CREDIT",
    "TRABAJO_BINDING",
    "TRABAJO_CASILLA",
    "YEAR",
    "CreditLiveHarness",
]

BUCKET_ID = "7d2e9a41-3c58-4f06-8b1e-5a9c0d4e7f23"
_TAX_ID = "12345678Z"
YEAR = newest_authored_edition("100")
_T0 = datetime(YEAR + 1, 4, 2, 9, 0, tzinfo=UTC)
_T1 = datetime(YEAR + 1, 4, 2, 10, 0, tzinfo=UTC)
_ANNUAL_PERIOD = "0A"
_QUARTERS: tuple[str, ...] = ("1T", "2T", "3T", "4T")
_R210_SIMULATOR_URL = aeat_url("www2", configured_path("sede_paths", "r210_simulator_open_ajax"))

TRABAJO_CASILLA: CasillaId = validated_casilla_id("0596", surface="TRABAJO_CASILLA")
CAPITAL_CASILLA: CasillaId = validated_casilla_id("0597", surface="CAPITAL_CASILLA")
TRABAJO_BINDING: BindingId = "renta-retencion-soportada-trabajo"
CAPITAL_BINDING: BindingId = "renta-retencion-soportada-capital-mobiliario"
_BASE_LIQUIDABLE_NEGATIVA_CASILLA: CasillaId = validated_casilla_id("1391", surface="_BASE_LIQUIDABLE_NEGATIVA")
_PRIOR_ANEXO_C_REMAINDERS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(box, surface="_PRIOR_ANEXO_C_REMAINDERS") for box in ("1384", "1387", "1390")
)
_M130_PAGOS_OUTPUT: CasillaId = validated_casilla_id("19", surface="_M130_PAGOS_OUTPUT")
_M131_PAGOS_OUTPUT: CasillaId = validated_casilla_id("15", surface="_M131_PAGOS_OUTPUT")

# Hand-derived oracles. Payer A certifies a 1.200,00 retencion and a 300,00 ingreso a cuenta; payer B certifies a
# 450,00 retencion: 1.200,00 + 300,00 + 450,00. One capital payer certifies a 500,00 retencion.
EXPECTED_TRABAJO_CREDIT = Decimal("1950.00")
EXPECTED_CAPITAL_CREDIT = Decimal("500.00")


def _seed_profile() -> None:
    record = _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=BUCKET_ID,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="activities.iae_epigraph", value="844"),
                UserProfileFact(
                    path="taxpayer_type.irpf_income_categories", value="trabajo,capital_mobiliario,actividad_economica"
                ),
                UserProfileFact(path="censo.activity_start_date", value=date(YEAR - 5, 1, 1)),
                UserProfileFact(path="withholding.colegio_concertado", value=False),
                UserProfileFact(path="renta_taxpayer.birth_date", value=date(YEAR - 45, 3, 15)),
                UserProfileFact(path="renta_taxpayer.sex", value="H"),
                UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
                UserProfileFact(path="renta_taxpayer.marriage_full_year", value=False),
                UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
                UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
                UserProfileFact(path="renta_filing.declaration_type", value="1"),
                UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
                UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
            )
        ),
        created_at=_T0,
        updated_at=_T0,
        context=_profile_creation_context_for_test(),
    )
    seed_test_profile_record(record)


def _seed_payers(operation: PinnedAuthorityOperation) -> None:
    for payer, retencion, ingreso_a_cuenta in (("B00010082", "1200.00", "300.00"), ("A00010009", "450.00", "0.00")):
        seed_payer_certificate(
            operation=operation,
            taxpayer_tax_id=_TAX_ID,
            ejercicio=YEAR,
            payer_tax_id=payer,
            income_class=RetencionSoportadaClase.TRABAJO,
            retencion=Decimal(retencion),
            ingreso_a_cuenta=Decimal(ingreso_a_cuenta),
        )
    seed_payer_certificate(
        operation=operation,
        taxpayer_tax_id=_TAX_ID,
        ejercicio=YEAR,
        payer_tax_id="C00010231",
        income_class=RetencionSoportadaClase.CAPITAL_MOBILIARIO,
        retencion=EXPECTED_CAPITAL_CREDIT,
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


def _seed_filed_history(secure_objects: SecureObjectRepository) -> None:
    """The prior year's zero carry and this year's locally filed pagos fraccionados."""
    repository = CalculationObservationRepository(objects=secure_objects)
    _save_filing(
        repository,
        modelo="100",
        period=_ANNUAL_PERIOD,
        casilla_values=dict.fromkeys((_BASE_LIQUIDABLE_NEGATIVA_CASILLA, *_PRIOR_ANEXO_C_REMAINDERS), Decimal("0")),
        filing_year=YEAR - 1,
    )
    for period in _QUARTERS:
        _save_filing(
            repository,
            modelo="130",
            period=period,
            casilla_values={_M130_PAGOS_OUTPUT: Decimal("100.00")},
            filing_year=YEAR,
        )
        _save_filing(
            repository,
            modelo="131",
            period=period,
            casilla_values={_M131_PAGOS_OUTPUT: Decimal("0")},
            filing_year=YEAR,
        )


def _borrador_repository(objects: SecureObjectRepository) -> Borrador100SnapshotRepository:
    return SecureSnapshotRepository(
        bucket_id=BUCKET_ID,
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
    snapshot = published_authority_operation().snapshot("100", filing_year=YEAR, period=_ANNUAL_PERIOD)
    resolved_elsewhere = frozenset({"profile", "relation_prefill", "retencion_soportada"}) | {
        kind.value for kind in precedence_ladder_sources(CallerOverrideDisposition.LOCK)
    }
    return {
        binding.id: Decimal("0") for binding in snapshot.revision.bindings if binding.source not in resolved_elsewhere
    }


@dataclass(slots=True)
class CreditLiveHarness:
    """One annual Modelo 100 work unit over a seeded profile, calculated afresh on demand."""

    secure_objects: SecureObjectRepository
    operation: PinnedAuthorityOperation
    work_unit: WorkUnit
    borrador: Borrador100SnapshotRepository
    _next_snapshot: int = 0
    _calculations: int = 0

    @classmethod
    def seed(cls, secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation) -> CreditLiveHarness:
        """Seed the profile, the payers and the filed history, and create the annual work unit."""
        _seed_profile()
        _seed_filed_history(secure_objects)
        _seed_payers(operation)
        work_units = WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)
        snapshot = published_authority_operation().snapshot("100", filing_year=YEAR, period=_ANNUAL_PERIOD)
        work_unit = create_work_unit(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=YEAR,
            period=Period.from_year_and_code(YEAR, _ANNUAL_PERIOD),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=work_units,
                bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
            ),
            clock=_T0,
            operation=operation,
        )
        return cls(
            secure_objects=secure_objects,
            operation=operation,
            work_unit=work_unit,
            borrador=_borrador_repository(secure_objects),
        )

    @property
    def resolutions(self) -> CreditResolutionRepositoryAdapter:
        """The profile's store of accepted disagreements."""
        return CreditResolutionRepositoryAdapter(objects=self.secure_objects)

    @property
    def work_units(self) -> WorkUnitCatalogueRepository:
        """The profile's work-unit catalogue."""
        return WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=self.secure_objects)

    @property
    def calculations(self) -> CalculationRevisionCatalogueRepository:
        """The profile's calculation-revision catalogue."""
        return CalculationRevisionCatalogueRepository(objects=self.secure_objects)

    def save_borrador(self, binding_values: dict[BindingId, Decimal]) -> str:
        """Store a borrador snapshot stating ``binding_values`` and return its id."""
        self._next_snapshot += 1
        snapshot_id = f"{self._next_snapshot:x}".rjust(64, "c")
        self.borrador.save(
            Borrador100Snapshot(
                snapshot_id=snapshot_id,
                bucket_id=BUCKET_ID,
                modelo="100",
                filing_year=YEAR,
                period=Period.from_year_and_code(YEAR, _ANNUAL_PERIOD),
                registry_snapshot_ref=published_authority_operation()
                .snapshot("100", filing_year=YEAR, period=_ANNUAL_PERIOD)
                .snapshot_ref,
                captured_at=_T0,
                source_url=_R210_SIMULATOR_URL,
                state=SnapshotLifecycleState.ACTIVE,
                binding_values=binding_values,
            )
        )
        return snapshot_id

    def calculate(
        self, borrador_binding_values: dict[BindingId, Decimal] | None = None
    ) -> BucketAggregationCalculationResult:
        """Calculate the work unit, comparing the credits with a borrador that states ``borrador_binding_values``."""
        snapshot_id = None if borrador_binding_values is None else self.save_borrador(borrador_binding_values)
        self._calculations += 1
        with calculation_ports_for_test(
            bucket_id=BUCKET_ID,
            calculation_repository=self.calculations,
            invoice_repository=InvoiceCatalogueRepository(bucket_id=BUCKET_ID, objects=self.secure_objects),
            transaction_repository=TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=self.secure_objects),
            work_unit_repository=self.work_units,
            borrador_snapshot_repository=self.borrador,
        ) as ports:
            return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                self.work_unit.work_unit_id,
                binding_values=_caller_binding_values(),
                borrador_snapshot_id=snapshot_id,
                ports=ports,
                clock=_T1 + timedelta(minutes=self._calculations),
            )

    def current_work_unit(self) -> WorkUnit:
        """Return the work unit as the catalogue now stores it, with its current calculation pointer."""
        return self.work_units.load().work_units[self.work_unit.work_unit_id]
