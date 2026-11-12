"""M100 negative base-liquidables-general carry resolves on the live calculate path.

A prior finding described a manual transcription into casilla 0501.
The registry's actual carry vehicle is the Art. 50.3 Anexo C negative
base-liquidable-general stock: prior M100 casilla 1391 is copied by a
``previous_filing`` binding into next year's opening pending casilla 1388.
Casilla 0501 remains the separate Art. 50 compensation line and must not be
used as a manual carry ingress. Art. 48's 25%-limited base-imponible mechanism
is distinct.

These tests prove the live bucket-aggregation calculate path resolves the
existing previous-filing binding from real stored observations, with no caller
``--binding`` for the carry and no ``--casilla 0501`` input.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.inventory import InventoryLedgerRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.ready_profile_support import seed_persona_profile
from ....adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....application.aggregation.tests.test_inventory_source import inventory_ledger
from ....application.calculations.observations_repository import APP_FILING_SOURCE_KIND
from ....application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.errors.error_codes import resolve_error_message
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.tests.authored_editions import newest_authored_editions
from ....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_observations,
)
from ....domain.contribuyente.inventory.records import InventoryLedgerDocument
from ...adapter_composition_work_ports import build_calculation_action_ports
from .observation_seeding_support import save_stamped_observation
from .ready_profile_taxpayer import ready_profile_tax_id
from .work_income_support import record_work_income

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "cd7a6304-1000-4100-8100-000000000365"


__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


_PERIOD = "0A"
# The two newest Modelo 100 editions the registry authors; each carries the prior
# exercise's Art. 50.3 pending negative base into its own casilla 1388.
_CARRY_EDITIONS = newest_authored_editions("100", 2)
_NEWEST_EDITION = _CARRY_EDITIONS[-1]
# Calculations run in the Renta campaign after the newest edition's exercise.
_CLOCK = datetime(_NEWEST_EDITION + 1, 7, 1, 10, 0, tzinfo=UTC)
_QUARTERS = ("1T", "2T", "3T", "4T")

_OPENING_PENDING: CasillaId = validated_casilla_id("1388", surface="_OPENING_PENDING")
_APPLIED_PENDING: CasillaId = validated_casilla_id("1389", surface="_APPLIED_PENDING")
_GENERATED_PENDING: CasillaId = validated_casilla_id("1391", surface="_GENERATED_PENDING")
#: The prior return's remainders that open this year's older Anexo C rows (1380, 1382, 1385).
_PRIOR_ANEXO_C_REMAINDERS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(box, surface="_PRIOR_ANEXO_C_REMAINDERS") for box in ("1384", "1387", "1390")
)
_CASILLA_0501: CasillaId = validated_casilla_id("0501", surface="_CASILLA_0501")
_BASE_IMPONIBLE_GENERAL: CasillaId = validated_casilla_id("0435", surface="_BASE_IMPONIBLE_GENERAL")
_BASE_LIQUIDABLE_GENERAL: CasillaId = validated_casilla_id("0500", surface="_BASE_LIQUIDABLE_GENERAL")
_BASE_LIQUIDABLE_SOMETIDA: CasillaId = validated_casilla_id("0505", surface="_BASE_LIQUIDABLE_SOMETIDA")
#: A direct-estimation expense the filer enters by hand, with no activity income against it.
_ACTIVITY_MANUAL_EXPENSE: CasillaId = validated_casilla_id("0184", surface="_ACTIVITY_MANUAL_EXPENSE")
#: Work income above the level where the art. 20 reduction ends, so the base stays above the 2.000 applied.
_TRABAJO_INGRESOS = Decimal("40000.00")
_M130_PAGOS_OUTPUT: CasillaId = validated_casilla_id("19", surface="_M130_PAGOS_OUTPUT")
_M131_PAGOS_OUTPUT: CasillaId = validated_casilla_id("15", surface="_M131_PAGOS_OUTPUT")


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


def _seed_prior_m100_generated_pending(
    obs_repo: CalculationObservationRepository,
    *,
    source_year: int,
    value: Decimal,
) -> None:
    _save_observation(
        obs_repo,
        modelo="100",
        filing_year=source_year,
        period=_PERIOD,
        casilla_values={_GENERATED_PENDING: value, **dict.fromkeys(_PRIOR_ANEXO_C_REMAINDERS, Decimal("0"))},
    )


def _seed_zero_pagos_quarters(obs_repo: CalculationObservationRepository, *, filing_year: int) -> None:
    """Seed zero M130/M131 pago-fraccionado legs so M100 direct pago relations resolve."""
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


def _calculate_m100(
    secure_objects: SecureObjectRepository,
    *,
    filing_year: int,
    casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
) -> BucketAggregationCalculationResult:
    snapshot = published_authority_operation().snapshot("100", filing_year=filing_year, period=_PERIOD)
    work_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    with bundled_indexed_authority().operation() as operation:
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=filing_year,
            period=Period.from_year_and_code(filing_year, _PERIOD),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=work_repo,
                bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
            ),
            operation=operation,
            clock=_CLOCK,
        )
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            casilla_inputs=casilla_inputs,
            clock=_CLOCK,
        )


@pytest.mark.parametrize(
    ("filing_year", "prior_pending"),
    tuple(zip(_CARRY_EDITIONS, (Decimal("3210.00"), Decimal("4321.00")), strict=True)),
)
def test_m100_prior_negative_general_base_carries_without_manual_0501_input(
    secure_objects: SecureObjectRepository,
    filing_year: int,
    prior_pending: Decimal,
) -> None:
    """Prior M100 Art. 50.3 1391 auto-fills current 1388 without transcribing 0501."""
    obs_repo = CalculationObservationRepository(objects=secure_objects)
    seed_persona_profile("autonomo-fontanero", bucket_id=_BUCKET_ID, at=_CLOCK)
    binding_id: BindingId = "renta-base-liquidable-negativa-general-anterior"
    _seed_prior_m100_generated_pending(obs_repo, source_year=filing_year - 1, value=prior_pending)
    _seed_zero_pagos_quarters(obs_repo, filing_year=filing_year)

    result = _calculate_m100(secure_objects, filing_year=filing_year)
    revision = result.revision

    assert Decimal(revision.binding_overrides[binding_id]) == prior_pending
    assert Decimal(revision.input_values_by_casilla_id[_OPENING_PENDING]) == prior_pending
    assert Decimal(revision.casilla_values[_OPENING_PENDING]) == prior_pending
    assert _CASILLA_0501 not in revision.input_values_by_casilla_id
    assert Decimal(revision.casilla_values[_CASILLA_0501]) == Decimal("0")
    assert not any(diagnostic.binding_id == binding_id for diagnostic in result.source_diagnostics)


def test_m100_anexo_c_applied_amount_reduces_base_liquidable_not_base_imponible(
    secure_objects: SecureObjectRepository,
) -> None:
    """A real 1389 amount becomes 0501 and reduces 0505, leaving 0500 before the compensation.

    The AEAT design defines 0501 as the compensation applied "si la casilla [0500]
    es positiva y hasta el límite máximo de su importe", so 0500 is the base
    liquidable general before it and 0505 is the base after it.
    """
    obs_repo = CalculationObservationRepository(objects=secure_objects)
    seed_persona_profile("autonomo-fontanero", bucket_id=_BUCKET_ID, at=_CLOCK)
    # The filer carries on an economic activity, so its Anexo D inventory rows
    # feed the general base: without the year's ledger they are unresolved and
    # so is every base that sums them.
    InventoryLedgerRepository(objects=secure_objects).save(
        InventoryLedgerDocument(ledgers=(inventory_ledger("actividad"),))
    )
    _seed_prior_m100_generated_pending(obs_repo, source_year=_NEWEST_EDITION - 1, value=Decimal("4321.00"))
    _seed_zero_pagos_quarters(obs_repo, filing_year=_NEWEST_EDITION)

    with bundled_indexed_authority().operation() as operation:
        record_work_income(
            operation=operation,
            taxpayer_tax_id=ready_profile_tax_id(),
            filing_year=_NEWEST_EDITION,
            gross=_TRABAJO_INGRESOS,
        )
    baseline = _calculate_m100(secure_objects, filing_year=_NEWEST_EDITION).revision
    applied = _calculate_m100(
        secure_objects,
        filing_year=_NEWEST_EDITION,
        casilla_inputs={_APPLIED_PENDING: Decimal("2000.00")},
    ).revision

    assert Decimal(applied.casilla_values[_APPLIED_PENDING]) == Decimal("2000.00")
    assert Decimal(applied.casilla_values[_CASILLA_0501]) == Decimal("2000.00")
    assert Decimal(applied.casilla_values[validated_casilla_id("0435", surface="test")]) == Decimal(
        baseline.casilla_values[validated_casilla_id("0435", surface="test")]
    )
    assert Decimal(applied.casilla_values[_BASE_LIQUIDABLE_GENERAL]) == Decimal(
        baseline.casilla_values[_BASE_LIQUIDABLE_GENERAL]
    )
    assert Decimal(applied.casilla_values[_BASE_LIQUIDABLE_SOMETIDA]) == (
        Decimal(baseline.casilla_values[_BASE_LIQUIDABLE_SOMETIDA]) - Decimal("2000.00")
    )
    assert Decimal(applied.casilla_values[_GENERATED_PENDING]) == Decimal("0")


def test_m100_negative_general_base_is_carried_in_1391_and_taxes_nothing(
    secure_objects: SecureObjectRepository,
) -> None:
    """A loss-making year leaves 0500 negative, 0505 at zero and its magnitude in 1391.

    Art. 50.1 forbids the reductions from making the base negative, so 0500 is
    negative only because the base imponible general is, and it then equals it.
    Box 1391 holds this year's own negative base pending for the next four years.
    """
    obs_repo = CalculationObservationRepository(objects=secure_objects)
    seed_persona_profile("autonomo-fontanero", bucket_id=_BUCKET_ID, at=_CLOCK)
    InventoryLedgerRepository(objects=secure_objects).save(
        InventoryLedgerDocument(ledgers=(inventory_ledger("actividad"),))
    )
    _seed_prior_m100_generated_pending(obs_repo, source_year=_NEWEST_EDITION - 1, value=Decimal("0"))
    _seed_zero_pagos_quarters(obs_repo, filing_year=_NEWEST_EDITION)

    revision = _calculate_m100(
        secure_objects,
        filing_year=_NEWEST_EDITION,
        casilla_inputs={_ACTIVITY_MANUAL_EXPENSE: Decimal("5000.00")},
    ).revision

    base_imponible = Decimal(revision.casilla_values[_BASE_IMPONIBLE_GENERAL])
    assert base_imponible < Decimal("0")
    assert Decimal(revision.casilla_values[_BASE_LIQUIDABLE_GENERAL]) == base_imponible
    assert Decimal(revision.casilla_values[_CASILLA_0501]) == Decimal("0")
    assert Decimal(revision.casilla_values[_BASE_LIQUIDABLE_SOMETIDA]) == Decimal("0")
    assert Decimal(revision.casilla_values[_GENERATED_PENDING]) == -base_imponible


def test_m100_prior_return_without_the_older_remainders_refuses_naming_them(
    secure_objects: SecureObjectRepository,
) -> None:
    """A stored prior return that shows 1391 but not 1384, 1387 or 1390 names those boxes.

    The older origin rows open from the prior return's remainders. A box the
    return does not show is unknown, so the stock it opens cannot read as zero.
    """
    obs_repo = CalculationObservationRepository(objects=secure_objects)
    seed_persona_profile("autonomo-fontanero", bucket_id=_BUCKET_ID, at=_CLOCK)
    _save_observation(
        obs_repo,
        modelo="100",
        filing_year=_NEWEST_EDITION - 1,
        period=_PERIOD,
        casilla_values={_GENERATED_PENDING: Decimal("1500.00")},
    )
    _seed_zero_pagos_quarters(obs_repo, filing_year=_NEWEST_EDITION)

    with pytest.raises(RegistryValidationError) as refused:
        _calculate_m100(secure_objects, filing_year=_NEWEST_EDITION)

    assert refused.value.translated_message == "errors.calc.previous_filing_casillas_unobserved"
    context = refused.value.context or {}
    assert context["casilla_ids"] == "1384,1387,1390"
    assert (context["source_modelo"], context["source_filing_year"], context["source_period"]) == (
        "100",
        _NEWEST_EDITION - 1,
        _PERIOD,
    )
    words = resolve_error_message(refused.value, locale="es")
    assert words.startswith(f"La declaración del modelo 100 de {_NEWEST_EDITION - 1} (0A)")
    assert "las casillas 1384,1387,1390" in words


def test_m100_base_liquidable_carry_is_grounded_in_art_50_not_art_48() -> None:
    """The newest authored edition keeps Art. 48 only on the distinct base-imponible step."""
    snapshot = published_authority_operation().snapshot("100", filing_year=_NEWEST_EDITION, period=_PERIOD)
    revision = snapshot.revision
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    formulas = {formula.id: formula for formula in revision.formulas}
    binding = next(item for item in revision.bindings if item.id == "renta-base-liquidable-negativa-general-anterior")

    art_50 = "ley-35-2006:art-50"
    art_48 = "ley-35-2006:art-48"
    assert binding.legal_refs[0] == art_50
    assert art_48 not in binding.legal_refs
    for casilla_id in ("1388", "1391", "0501"):
        assert casillas[casilla_id].legal_refs[0] == art_50
        assert art_48 not in casillas[casilla_id].legal_refs
    prior_aplicada_maxima = "renta-base-liquidable-negativa-general-em1-aplicada-maxima"
    assert formulas[prior_aplicada_maxima].legal_refs == (art_50,)
    assert formulas["renta-base-liquidable-negativa-general-compensacion-total"].legal_refs == (art_50,)
    assert formulas["renta-base-imponible-general"].legal_refs[0] == art_48
    assert art_50 not in formulas["renta-base-imponible-general"].legal_refs
    prior_snapshot = published_authority_operation().snapshot("100", filing_year=_NEWEST_EDITION - 1, period=_PERIOD)
    prior_binding = next(
        item
        for item in prior_snapshot.revision.bindings
        if item.id == "renta-base-liquidable-negativa-general-anterior"
    )
    assert prior_binding.legal_refs == (art_50,)
