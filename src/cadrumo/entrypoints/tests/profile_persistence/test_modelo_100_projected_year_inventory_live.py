"""A projected Modelo 100 year reads the Anexo D inventory rows through the edition it is carried from.

Casillas 0177, 0181 and 0182 come from the activity inventory ledger. A year no
edition authors resolves the newest edition's declarations, so the rows the
filer's ledger holds for that year must reach the calculation exactly as they
do in the authored year, rather than being refused because the year differs
from the one the governed fact was first written for.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.inventory import InventoryLedgerRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....application.aggregation.tests.test_inventory_source import inventory_ledger
from ....application.calculations.observations_repository import APP_FILING_SOURCE_KIND
from ....application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation, binding_source_casilla_ids
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition, projected_exercise
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from ....domain.contribuyente.inventory.records import InventoryLedgerDocument
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...adapter_composition_work_ports import build_calculation_action_ports
from .general_iva_profile_facts_support import renta_single_taxpayer_facts
from .observation_seeding_support import save_stamped_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

__all__ = ["secure_objects"]

_BUCKET_ID = "cd7a6304-1000-4100-8100-000000000366"
_PERIOD = "0A"
_NEWEST_EDITION = newest_authored_edition("100")
_PROJECTED_YEAR = projected_exercise("100")
_CLOCK = datetime(_PROJECTED_YEAR, 7, 1, 10, 0, tzinfo=UTC)
_QUARTERS = ("1T", "2T", "3T", "4T")

_GENERATED_PENDING: CasillaId = validated_casilla_id("1391", surface="_GENERATED_PENDING")
_PRIOR_ANEXO_C_REMAINDERS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(box, surface="_PRIOR_ANEXO_C_REMAINDERS") for box in ("1384", "1387", "1390")
)
_SAVINGS_CARRY_PREFIX = "renta-saldo-negativo-"
_SAVINGS_CARRY_SUFFIX = "-pendiente-inicio"
_M130_PAGOS_OUTPUT: CasillaId = validated_casilla_id("19", surface="_M130_PAGOS_OUTPUT")
_M131_PAGOS_OUTPUT: CasillaId = validated_casilla_id("15", surface="_M131_PAGOS_OUTPUT")
_INVENTORY_INCREASE = "renta-inventory-activity-closing-increase-0177"
_INVENTORY_ACQUISITION = "renta-inventory-activity-acquisition-cost-0181"
_INVENTORY_DECREASE = "renta-inventory-activity-closing-decrease-0182"


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _seed_taxpayer_with_an_activity(secure_objects: SecureObjectRepository) -> None:
    record = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="censo.activity_start_date", value=date(_NEWEST_EDITION - 5, 1, 1)),
                *renta_single_taxpayer_facts(birth_date=date(_NEWEST_EDITION - 45, 3, 15)),
                UserProfileFact(path="renta_family.unidad_familiar_otros_miembros_base", value=Decimal("0")),
                UserProfileFact(path="renta_family.madrid_nacimiento_adopcion_eligible_count", value=Decimal("0")),
            )
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(record)


def _save_observation(
    obs_repo: CalculationObservationRepository,
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: dict[CasillaId, Decimal],
) -> None:
    save_stamped_observation(
        obs_repo,
        RegistryModeloObservation(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observations=registry_grounded_observations(
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                casilla_values=casilla_values,
            ),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_CLOCK,
    )


def _prior_savings_remainders(filing_year: int) -> tuple[CasillaId, ...]:
    """The prior-return boxes the year's negative savings carries (LIRPF art. 49) open from."""
    with bundled_indexed_authority().operation() as operation:
        bindings = operation.reading_snapshot("100", filing_year=filing_year, period=_PERIOD).revision.bindings
    return tuple(
        casilla_id
        for binding in bindings
        if binding.provider.kind == "previous_filing"
        and binding.id.startswith(_SAVINGS_CARRY_PREFIX)
        and binding.id.endswith(_SAVINGS_CARRY_SUFFIX)
        for casilla_id in binding_source_casilla_ids(binding)
    )


def _seed_earlier_filings(obs_repo: CalculationObservationRepository, *, filing_year: int) -> None:
    """Seed the prior return's zero Anexo C and savings remainders and the year's zero pago-fraccionado quarters."""
    remainders = (*_PRIOR_ANEXO_C_REMAINDERS, *_prior_savings_remainders(filing_year))
    _save_observation(
        obs_repo,
        modelo="100",
        filing_year=filing_year - 1,
        period=_PERIOD,
        casilla_values={_GENERATED_PENDING: Decimal("0"), **dict.fromkeys(remainders, Decimal("0"))},
    )
    for period in _QUARTERS:
        _save_observation(
            obs_repo,
            modelo="130",
            filing_year=filing_year,
            period=period,
            casilla_values={_M130_PAGOS_OUTPUT: Decimal("0")},
        )
        _save_observation(
            obs_repo,
            modelo="131",
            filing_year=filing_year,
            period=period,
            casilla_values={_M131_PAGOS_OUTPUT: Decimal("0")},
        )


def _calculate(secure_objects: SecureObjectRepository, *, filing_year: int) -> BucketAggregationCalculationResult:
    with bundled_indexed_authority().operation() as operation:
        revision_id = operation.reading_snapshot("100", filing_year=filing_year, period=_PERIOD).revision.id
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=filing_year,
            period=Period.from_year_and_code(filing_year, _PERIOD),
            revision_id=revision_id,
            ports=WorkLifecyclePorts(
                work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
                bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
            ),
            operation=operation,
            clock=_CLOCK,
        )
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            clock=_CLOCK,
        )


def _unresolved_bindings(result: BucketAggregationCalculationResult) -> list[tuple[str, str | None]]:
    return sorted(
        (diagnostic.reason, diagnostic.binding_id)
        for diagnostic in result.source_diagnostics
        if diagnostic.reason in {"unresolved_binding", "unresolved_derived_binding"}
    )


def _inventory_rows(result: BucketAggregationCalculationResult) -> dict[str, dict[str, Decimal]]:
    rows = result.revision.row_binding_values
    return {
        binding_id: {row: Decimal(value) for row, value in rows.get(binding_id, {}).items()}
        for binding_id in (_INVENTORY_ACQUISITION, _INVENTORY_INCREASE, _INVENTORY_DECREASE)
    }


def test_a_projected_year_calculates_the_inventory_rows_the_filer_holds_as_the_newest_edition_does(
    secure_objects: SecureObjectRepository,
) -> None:
    obs_repo = CalculationObservationRepository(objects=secure_objects)
    _seed_taxpayer_with_an_activity(secure_objects)
    InventoryLedgerRepository(objects=secure_objects).save(
        InventoryLedgerDocument(
            ledgers=(
                inventory_ledger("actividad", year=_NEWEST_EDITION),
                inventory_ledger("actividad", year=_PROJECTED_YEAR),
            )
        )
    )
    for year in (_NEWEST_EDITION, _PROJECTED_YEAR):
        _seed_earlier_filings(obs_repo, filing_year=year)

    authored = _calculate(secure_objects, filing_year=_NEWEST_EDITION)
    projected = _calculate(secure_objects, filing_year=_PROJECTED_YEAR)

    expected = {
        _INVENTORY_ACQUISITION: {"1": Decimal("100.00")},
        _INVENTORY_INCREASE: {"1": Decimal("100.00")},
        _INVENTORY_DECREASE: {"1": Decimal("0.00")},
    }
    assert _inventory_rows(authored) == expected
    assert _inventory_rows(projected) == expected
    # Whatever else the filer's profile leaves unresolved is the same in both years: nothing is held back
    # only because the year differs from the one the inventory applicability was first stated for.
    assert _unresolved_bindings(projected) == _unresolved_bindings(authored)
    assert not any(
        binding_id in {_INVENTORY_ACQUISITION, _INVENTORY_INCREASE, _INVENTORY_DECREASE}
        for _reason, binding_id in _unresolved_bindings(projected)
    )
