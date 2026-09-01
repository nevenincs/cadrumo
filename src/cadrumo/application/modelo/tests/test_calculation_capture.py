"""Real-behavior proofs for the public modelo calculation capture contract."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....tests.registry_observations import registry_grounded_observations
from ....tests.registry_revision import active_registry_revision_id
from ..calculation import (
    ModeloCalculationCapture,
    ModeloCalculationCaptureError,
    ModeloCalculationCurrentCoordinate,
    capture_modelo_calculation,
    read_modelo_calculation_current_coordinate,
)
from ..calculation_actions import get_calculation_revision

if TYPE_CHECKING:
    from ._file_flow_support import _Repos

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 3, 4, 9, 0, 0, tzinfo=UTC)
_MODELO = ModeloCode("130")
_OUTPUT_CASILLA = validated_casilla_id("19", surface="test.calculation_capture")


def _seed_calculation(
    repos: _Repos, *, output: Decimal = Decimal("125.00")
) -> tuple[str, CalculationRevisionCatalogueRepository]:
    """Persist one real work unit and calculation revision through real storage."""
    work_repo, calculation_repo, _filing_repo, _verification_repo, _events = repos
    period = Period.from_year_and_code(2026, "1T")
    revision_id = active_registry_revision_id(modelo="130", filing_year=2026, period="1T")
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=_MODELO,
        filing_year=2026,
        period=period,
        revision_id=revision_id,
    )
    work_repo.save(
        upsert_work_unit(
            work_repo.load(),
            WorkUnit(
                work_unit_id=work_unit_id,
                bucket_id=bucket_id,
                modelo=_MODELO,
                filing_year=2026,
                period=period,
                revision_id=revision_id,
                name="130-2026-1T-capture",
                created_at=_T0,
                updated_at=_T0,
            ),
        )
    )
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_OUTPUT_CASILLA: str(output)},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA: output},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    calculation_repo.save(
        upsert_calculation_revision(
            calculation_repo.load(),
            CalculationRevision(
                calculation_revision_id=calculation_revision_id,
                work_unit_id=work_unit_id,
                state=CalculationRevisionState.BORRADOR,
                input_values_by_casilla_id={_OUTPUT_CASILLA: str(output)},
                casilla_values={_OUTPUT_CASILLA: output},
                observations=registry_grounded_observations(
                    modelo="130",
                    filing_year=2026,
                    period="1T",
                    casilla_values={_OUTPUT_CASILLA: output},
                ),
                created_at=_T0,
                updated_at=_T0,
                filing_instance_evidence=None,
                source_provenance=(),
            ),
        )
    )
    return calculation_revision_id, calculation_repo


def test_capture_republishes_the_authority_revision_without_reconstruction(repos: _Repos) -> None:
    """The capture carries the authority's record whole, provenance included."""
    calculation_revision_id, calculation_repo = _seed_calculation(repos)

    authoritative = get_calculation_revision(calculation_revision_id, calculation_repository=calculation_repo)
    captured = capture_modelo_calculation(calculation_revision_id, calculation_repository=calculation_repo)

    assert captured.revision == authoritative
    assert captured.revision.model_fields_set == authoritative.model_fields_set
    assert captured.revision.observations == authoritative.observations


def test_capture_is_singleflight_and_refuses_a_superseded_coordinate(repos: _Repos) -> None:
    """An unchanged catalogue shares a generation; a write supersedes the capture."""
    calculation_revision_id, calculation_repo = _seed_calculation(repos)

    first = capture_modelo_calculation(calculation_revision_id, calculation_repository=calculation_repo)
    second = capture_modelo_calculation(calculation_revision_id, calculation_repository=calculation_repo)

    assert first.generation == second.generation
    assert first.comparison_domain == second.comparison_domain

    current = read_modelo_calculation_current_coordinate(
        calculation_revision_id,
        calculation_repository=calculation_repo,
    )
    assert first.require_current(current) is first

    _seed_calculation(repos, output=Decimal("321.00"))

    advanced = read_modelo_calculation_current_coordinate(
        calculation_revision_id,
        calculation_repository=calculation_repo,
    )

    assert advanced.generation > first.generation
    with pytest.raises(ModeloCalculationCaptureError):
        first.require_current(advanced)


def test_capture_exposes_no_parallel_path_and_no_inferred_field(repos: _Repos) -> None:
    """The capture adds a coordinate only; it derives no second calculation shape."""
    from dataclasses import fields

    calculation_revision_id, calculation_repo = _seed_calculation(repos)

    captured = capture_modelo_calculation(calculation_revision_id, calculation_repository=calculation_repo)

    assert {field.name for field in fields(ModeloCalculationCapture)} == {
        "revision",
        "comparison_domain",
        "generation",
    }
    assert {field.name for field in fields(ModeloCalculationCurrentCoordinate)} == {
        "comparison_domain",
        "generation",
    }
    assert captured.comparison_domain != str(calculation_revision_id)


def test_calculation_capture_contract_is_owned_by_its_defining_module() -> None:
    """Every capture symbol is defined here and bound nowhere in the package namespace."""
    from ....application import modelo as modelo_namespace

    for owned in (
        ModeloCalculationCapture,
        ModeloCalculationCurrentCoordinate,
        ModeloCalculationCaptureError,
        capture_modelo_calculation,
        read_modelo_calculation_current_coordinate,
    ):
        assert owned.__module__ == "cadrumo.application.modelo.calculation"
        assert not hasattr(modelo_namespace, owned.__name__)
