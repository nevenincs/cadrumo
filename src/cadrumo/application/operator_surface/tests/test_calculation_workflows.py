"""Supported calculation workflows projected from operator reconciliation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .. import (
    LiveLeafInventoryRow,
    ModeloCalculationRouteId,
    OperatorSurfaceContractError,
    OperatorSurfaceReconciliation,
    ReconciledOperatorLeaf,
    SupportedModeloCalculationWorkflow,
    SupportedModeloCalculationWorkflowCatalogue,
    build_supported_modelo_calculation_workflow_catalogue,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _leaf(subject_leaf_key: str, canonical_cli_path: tuple[str, ...]) -> ReconciledOperatorLeaf:
    return ReconciledOperatorLeaf(
        live_leaf=LiveLeafInventoryRow(
            subject_leaf_key=subject_leaf_key,
            canonical_cli_path=canonical_cli_path,
            provenance="resolved Click command tree",
        ),
        result_schema=None,
        input_schema=None,
        mounted_family=None,
        profile_policy=None,
        surface_exposure=None,
        exclusions=(),
    )


def _reconciliation(*leaves: ReconciledOperatorLeaf) -> OperatorSurfaceReconciliation:
    return OperatorSurfaceReconciliation(leaves=leaves)


def test_catalogue_projects_live_subject_ids_and_canonical_paths_in_deterministic_order() -> None:
    reconciliation = _reconciliation(
        _leaf("quickfile", ("app", "quickfile")),
        _leaf("overview.status", ("app", "overview", "status")),
        _leaf("modelo.work.wizard", ("app", "modelo", "work", "wizard")),
        _leaf("modelo.work.calculate", ("app", "modelo", "work", "calculate")),
    )

    catalogue = build_supported_modelo_calculation_workflow_catalogue(reconciliation)

    assert tuple(row.command_id for row in catalogue.workflows) == (
        "modelo.work.calculate",
        "modelo.work.wizard",
        "quickfile",
    )
    assert tuple(row.entrypoint_id for row in catalogue.workflows) == ("cli", "cli", "cli")
    assert tuple(row.route_id for row in catalogue.workflows) == (
        ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
        ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
        ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
    )
    assert tuple(row.canonical_cli_path for row in catalogue.workflows) == (
        ("app", "modelo", "work", "calculate"),
        ("app", "modelo", "work", "wizard"),
        ("app", "quickfile"),
    )


def test_missing_live_leaf_cannot_remain_supported() -> None:
    catalogue = build_supported_modelo_calculation_workflow_catalogue(
        _reconciliation(_leaf("modelo.work.calculate", ("app", "modelo", "work", "calculate"))),
    )

    assert catalogue.supports(
        entrypoint_id="cli",
        command_id="modelo.work.calculate",
        route_id=ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
        canonical_cli_path=("app", "modelo", "work", "calculate"),
    )
    assert {row.command_id for row in catalogue.workflows} == {"modelo.work.calculate"}


def test_catalogue_refuses_duplicate_live_identity_or_canonical_path() -> None:
    with pytest.raises(OperatorSurfaceContractError, match="duplicate supported calculation workflow identity"):
        build_supported_modelo_calculation_workflow_catalogue(
            _reconciliation(
                _leaf("quickfile", ("app", "quickfile")),
                _leaf("quickfile", ("app", "quickfile")),
            ),
        )


@pytest.mark.parametrize(
    ("command_id", "drifted_path"),
    (
        ("modelo.work.calculate", ("app", "quickfile")),
        ("modelo.work.wizard", ("app", "modelo", "work", "calculate")),
        ("quickfile", ("app", "modelo", "work", "wizard")),
    ),
)
def test_catalogue_refuses_live_command_path_drift(
    command_id: str,
    drifted_path: tuple[str, ...],
) -> None:
    with pytest.raises(OperatorSurfaceContractError, match="workflow path drift"):
        build_supported_modelo_calculation_workflow_catalogue(
            _reconciliation(_leaf(command_id, drifted_path)),
        )


def test_catalogue_refuses_declaration_without_a_qualifying_live_leaf() -> None:
    with pytest.raises(OperatorSurfaceContractError, match="contains no supported"):
        build_supported_modelo_calculation_workflow_catalogue(
            _reconciliation(_leaf("overview.status", ("app", "overview", "status"))),
        )


def test_catalogue_models_refuse_unknown_ids_bad_paths_and_nondeterministic_rows() -> None:
    with pytest.raises(ValidationError, match="route_id"):
        SupportedModeloCalculationWorkflow.model_validate(
            {
                "command_id": "modelo.work.calculate",
                "canonical_cli_path": ("app", "modelo", "work", "calculate"),
            },
        )
    with pytest.raises(ValidationError, match="route_id"):
        SupportedModeloCalculationWorkflow.model_validate(
            {
                "command_id": "modelo.work.calculate",
                "route_id": "phantom_calculation_route",
                "canonical_cli_path": ("app", "modelo", "work", "calculate"),
            },
        )
    with pytest.raises(ValidationError, match="unsupported modelo calculation workflow"):
        SupportedModeloCalculationWorkflow(
            command_id="modelo.work.file",
            route_id=ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
            canonical_cli_path=("app", "modelo", "work", "file"),
        )
    with pytest.raises(ValidationError, match="canonical CLI path tokens"):
        SupportedModeloCalculationWorkflow(
            command_id="quickfile",
            route_id=ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
            canonical_cli_path=("app", " quickfile"),
        )
    calculate = SupportedModeloCalculationWorkflow(
        command_id="modelo.work.calculate",
        route_id=ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
        canonical_cli_path=("app", "modelo", "work", "calculate"),
    )
    quickfile = SupportedModeloCalculationWorkflow(
        command_id="quickfile",
        route_id=ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
        canonical_cli_path=("app", "quickfile"),
    )
    with pytest.raises(ValidationError, match="deterministic identity order"):
        SupportedModeloCalculationWorkflowCatalogue(workflows=(quickfile, calculate))


def test_catalogue_support_requires_exact_route_path_and_command_identity() -> None:
    catalogue = build_supported_modelo_calculation_workflow_catalogue(
        _reconciliation(_leaf("modelo.work.calculate", ("app", "modelo", "work", "calculate"))),
    )
    exact = {
        "entrypoint_id": "cli",
        "command_id": "modelo.work.calculate",
        "route_id": ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
        "canonical_cli_path": ("app", "modelo", "work", "calculate"),
    }
    assert catalogue.supports(**exact)
    assert not catalogue.supports(
        entrypoint_id="cli",
        command_id="modelo.work.wizard",
        route_id=ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
        canonical_cli_path=("app", "modelo", "work", "calculate"),
    )
    assert not catalogue.supports(
        entrypoint_id="cli",
        command_id="modelo.work.calculate",
        route_id=ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
        canonical_cli_path=("app", "quickfile"),
    )


def test_public_facade_exposes_the_workflow_catalogue() -> None:
    from .. import __all__

    assert {
        "ModeloCalculationRouteId",
        "SupportedModeloCalculationWorkflow",
        "SupportedModeloCalculationWorkflowCatalogue",
        "build_supported_modelo_calculation_workflow_catalogue",
    } <= set(__all__)
