"""The Modelo 200 pagos fraccionados read each Modelo 202 instalment of the ejercicio.

Casillas 00601, 00603 and 00605 carry the primer, segundo and tercer pago
fraccionado (Manual práctico de Sociedades, "Pagos fraccionados"), and the cuota
diferencial is 00611 = 00599 - (00601 + 00603 + 00605). A filed instalment is
read off its filing. An unfiled one whose own verdict says nothing was owed
(Orden HFP/227/2017 art. 1.3) credits a proven 0.00 with that verdict as its
grounds. Any other unfiled instalment leaves its casilla, and the cuota
diferencial, unresolved. Every case runs the real observation store, the real
instalment resolution, the real relation resolver and the real formula engine.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.calculations.modelo_202_instalment_resolution import Modelo202InstalmentResolver
from .....application.calculations.observations_repository import ObservationSourceKind
from .....application.calculations.relation_prefill import resolve_relations_from_local_store
from .....application.overview.modelo202_instalment_evidence import (
    Modelo202InstalmentStores,
    bind_modelo_202_instalment_resolver,
)
from .....application.storage.calc_sheets.records import RelationValue
from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.period import Period
from .....domain.calculations.registry.applicability_modelo202 import Modelo202InstalmentOutcome, Modelo202Modality
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from .....domain.calculations.registry.schema import RegistrySnapshot
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.calculations.registry.tests.cross_dependency_calculation_support import casilla_inputs
from .....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_modelo_observation,
    revision_id_for_observation,
)
from .....domain.modelos.work_unit import WorkUnitCatalogue
from .....domain.transactions.models import TransactionCatalogue
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..calculation_observations import CalculationObservationRepository
from ..modelos_calculation import CalculationRevisionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ANNUAL = "0A"
_CUOTA_CASILLA = validated_casilla_id("DP200014B:00599")
_INSTALMENT_CASILLA_BY_PERIOD: dict[str, CasillaId] = {
    "1P": validated_casilla_id("DP200014B:00601"),
    "2P": validated_casilla_id("DP200014B:00603"),
    "3P": validated_casilla_id("DP200014B:00605"),
}
_CUOTA_DIFERENCIAL_CASILLA = validated_casilla_id("DP200014B:00611")
_CUOTA_INSTALMENT_CASILLA = validated_casilla_id("03")
_ORDINAL_BY_PERIOD = {"1P": "primero", "2P": "segundo", "3P": "tercero"}
_PRECEDING_TURNOVER_CARRY = "modelo-200-incn-periodo-impositivo-anterior"
_SELF_CARRIES = (
    "modelo-200-bin-pendiente-ejercicios-anteriores",
    "modelo-200-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores",
    "modelo-200-dotaciones-deterioro-creditos-saldo-cumplido-anteriores",
)


def _instalment_relations(period: str) -> tuple[str, str]:
    ordinal = _ORDINAL_BY_PERIOD[period]
    return (f"modelo-200-pago-fraccionado-{ordinal}-40-2", f"modelo-200-pago-fraccionado-{ordinal}-40-3")


def _ejercicio() -> int:
    """The settled ejercicio: the one before the horizon, whose Modelo 200 is filed in the horizon."""
    return filing_year_envelope().horizon - 1


def _save(
    repository: CalculationObservationRepository,
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: dict[CasillaId, Decimal],
) -> None:
    observation = registry_grounded_modelo_observation(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        casilla_values=casilla_values,
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind=ObservationSourceKind.APP_FILING,
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )


def _file_april_instalment(repository: CalculationObservationRepository) -> None:
    """The April instalment under modalidad cuota: 18 % of a 300.00 cuota, presented locally at 54.00."""
    _save(
        repository,
        modelo="202",
        filing_year=_ejercicio(),
        period="1P",
        casilla_values={_CUOTA_INSTALMENT_CASILLA: Decimal("54.00")},
    )


def _file_previous_modelo_200(repository: CalculationObservationRepository, cuota: Decimal) -> None:
    """The Modelo 200 one year back, whose cuota is the October and December base (LIS art. 40.2)."""
    _save(
        repository,
        modelo="200",
        filing_year=_ejercicio() - 1,
        period=_ANNUAL,
        casilla_values={_CUOTA_CASILLA: cuota},
    )


def _resolver(
    repository: CalculationObservationRepository,
    operation: PinnedAuthorityOperation,
    *,
    bucket_id: str,
    modality: Modelo202Modality | None,
    election_for: Callable[..., bool | None],
) -> Modelo202InstalmentResolver:
    return bind_modelo_202_instalment_resolver(
        Modelo202InstalmentStores(
            bucket_id=bucket_id,
            observations=repository,
            work_units=WorkUnitCatalogue,
            calculations=CalculationRevisionCatalogueRepository(),
            transactions=TransactionCatalogue,
            activity_start_date=None,
            election_for=election_for,
        ),
        modality=modality,
        operation=operation,
    )


def _snapshot(operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    return operation.snapshot("200", filing_year=_ejercicio(), period=_ANNUAL, grade=RegistryAuthorityGrade.CALCULATION)


def _relation_values(
    repository: CalculationObservationRepository,
    operation: PinnedAuthorityOperation,
    resolver: Modelo202InstalmentResolver | None,
) -> dict[str, RelationValue]:
    values = resolve_relations_from_local_store(
        _snapshot(operation),
        operation=operation,
        repository=repository,
        modelo_202_instalment_resolver=resolver,
    )
    return {str(item.relation): item for item in values.values}


def _calculate(
    operation: PinnedAuthorityOperation, relation_values: dict[str, RelationValue]
) -> dict[CasillaId, Decimal]:
    """Run the real Modelo 200 formulas over the resolved relations, marking the unresolved ones as the source mesh does."""
    resolved = {relation: item.value for relation, item in relation_values.items() if item.value is not None}
    result = calculate_registry_snapshot(
        _snapshot(operation),
        inputs=casilla_inputs(
            {
                "DP200012:00501": Decimal("8000"),
                "DP200013:00417": Decimal("0"),
                "DP200013:00418": Decimal("0"),
                "01032": Decimal("0"),
                "DP200014:00547": Decimal("0"),
                "DP200014:01033": Decimal("0"),
                "DP200014:01034": Decimal("0"),
            },
        ),
        enum_binding_values={"modelo-200-profile-legal-entity-form": "sl"},
        binding_values={
            "modelo-200-profile-new-entity-flag": Decimal("0"),
            "modelo-200-profile-incn-prior-12-months": Decimal("12000000"),
            # The rate reads the preceding período's turnover from its held return.
            _PRECEDING_TURNOVER_CARRY: Decimal("12000000"),
            "modelo-200-profile-tributacion-estado-porcentaje": Decimal("100"),
        },
        relation_values={**dict.fromkeys(_SELF_CARRIES, Decimal("0")), **resolved},
        unresolved_relation_ids=tuple(
            relation
            for relation, item in relation_values.items()
            if item.value is None and relation not in _SELF_CARRIES
        ),
        date_context={"filing_period": date(_ejercicio(), 12, 31)},
    )
    return dict(result.values)


def test_unowed_instalments_credit_zero_beside_the_filed_one(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """00601 reads the filed April instalment; 00603 and 00605 are a proven 0.00; 00611 resolves."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = CalculationObservationRepository()
        _file_april_instalment(repository)
        _file_previous_modelo_200(repository, Decimal("0.00"))
        resolver = _resolver(
            repository,
            authority_operation,
            bucket_id=profile.bucket_id,
            modality=Modelo202Modality.ART_40_2_OPTIONAL,
            election_for=lambda _instalment: False,
        )
        relations = _relation_values(repository, authority_operation, resolver)
        grounds = {period: resolver(Period.from_year_and_code(_ejercicio(), period)).grounds for period in ("2P", "3P")}

    cuota_1p, base_1p = (relations[relation] for relation in _instalment_relations("1P"))
    assert (cuota_1p.value, base_1p.value) == (Decimal("54.00"), Decimal("0"))
    for period in ("2P", "3P"):
        for relation in _instalment_relations(period):
            credited = relations[relation]
            assert credited.value == Decimal("0.00")
            assert credited.source_periods == (period,)
            verdict = grounds[period]
            assert verdict is not None
            assert verdict.outcome is Modelo202InstalmentOutcome.BASE_NOT_POSITIVE
            assert credited.note is not None
            assert verdict.reason in credited.note
            assert set(verdict.legal_refs) <= set(credited.legal_refs)

    values = _calculate(authority_operation, relations)
    assert values[_INSTALMENT_CASILLA_BY_PERIOD["1P"]] == Decimal("54.00")
    assert values[_INSTALMENT_CASILLA_BY_PERIOD["2P"]] == Decimal("0.00")
    assert values[_INSTALMENT_CASILLA_BY_PERIOD["3P"]] == Decimal("0.00")
    assert values[_CUOTA_DIFERENCIAL_CASILLA] == values[_CUOTA_CASILLA] - Decimal("54.00")


@pytest.mark.parametrize(
    ("previous_cuota", "modality", "election", "reason"),
    [
        pytest.param(None, Modelo202Modality.ART_40_2_OPTIONAL, False, "verdict_undecided", id="base-never-held"),
        pytest.param(Decimal("0.00"), None, False, "verdict_undecided", id="modality-unknown"),
        pytest.param(Decimal("500.00"), Modelo202Modality.ART_40_2_OPTIONAL, False, "owed_unfiled", id="base-positive"),
    ],
)
def test_an_unfiled_instalment_not_shown_unowed_stays_unresolved(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    previous_cuota: Decimal | None,
    modality: Modelo202Modality | None,
    election: bool | None,
    reason: str,
) -> None:
    """An undecided or owed-but-unfiled instalment leaves its casilla and 00611 unresolved, never zero."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = CalculationObservationRepository()
        _file_april_instalment(repository)
        if previous_cuota is not None:
            _file_previous_modelo_200(repository, previous_cuota)
        resolver = _resolver(
            repository,
            authority_operation,
            bucket_id=profile.bucket_id,
            modality=modality,
            election_for=lambda _instalment: election,
        )
        relations = _relation_values(repository, authority_operation, resolver)

    assert relations[_instalment_relations("1P")[0]].value == Decimal("54.00")
    for period in ("2P", "3P"):
        for relation in _instalment_relations(period):
            unresolved = relations[relation]
            assert unresolved.value is None
            assert unresolved.note is not None
            assert reason in unresolved.note

    values = _calculate(authority_operation, relations)
    assert values[_INSTALMENT_CASILLA_BY_PERIOD["1P"]] == Decimal("54.00")
    assert _INSTALMENT_CASILLA_BY_PERIOD["2P"] not in values
    assert _INSTALMENT_CASILLA_BY_PERIOD["3P"] not in values
    assert _CUOTA_DIFERENCIAL_CASILLA not in values
