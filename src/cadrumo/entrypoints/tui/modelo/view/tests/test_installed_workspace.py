"""Installed navigation proof for admitted Declarations-to-Modelo handoff."""

from __future__ import annotations

import pytest

from ......application.modelo.declarations_workspace import DeclarationsWorkspaceDeclarationRefV1
from ......core.external_constants import OutputLanguage
from ......domain.modelos.work_unit import WorkUnitState
from ...installed_workspace import (
    ModeloWorkspaceDeclarationAdmissionError,
    compose_installed_modelo_workspace_factory,
)
from ..overview import ModeloWorkspaceOverviewScreen
from .conftest import resolve_real_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _declaration(projection) -> DeclarationsWorkspaceDeclarationRefV1:
    target = projection.target
    assert target.work_unit_id is not None
    assert target.work_state is not None
    return DeclarationsWorkspaceDeclarationRefV1(
        work_unit_id=target.work_unit_id,
        modelo=target.modelo,
        filing_year=target.filing_year,
        period=target.period,
        state=target.work_state,
        has_current_calculation=False,
        has_current_filing=False,
    )


def test_installed_factory_opens_existing_workspace_overview_from_one_admitted_generation(
    bucket_and_repository,
) -> None:
    """The production join reuses the route table and preserves the exact projection."""
    bucket_id, repository = bucket_and_repository
    projection = resolve_real_result(bucket_id, repository, OutputLanguage.ES).projection
    declaration = _declaration(projection)

    factory = compose_installed_modelo_workspace_factory(
        bucket_id=bucket_id,
        declarations=(declaration,),
        projections=(projection,),
    )

    screen = factory(declaration)

    assert isinstance(screen, ModeloWorkspaceOverviewScreen)
    assert screen._session.projection is projection
    assert screen._session.graded_refusal is None


def test_installed_factory_carries_the_named_graded_refusal_into_its_opened_session(
    bucket_and_repository,
) -> None:
    """A refusal keyed by this exact work unit reaches the session it explains, and no other."""
    from ......application.modelo.work_addressing import ModeloExactWorkUnitTarget
    from ......application.modelo.workspace import graded_snapshot_refusal
    from ......application.modelo.workspace_models import (
        ModeloWorkspaceCapabilityName,
        ModeloWorkspaceExactWorkUnitTargetV1,
        ModeloWorkspaceRefusalCode,
    )

    bucket_id, repository = bucket_and_repository
    projection = resolve_real_result(bucket_id, repository, OutputLanguage.ES).projection
    declaration = _declaration(projection)
    target = projection.target
    refusal = graded_snapshot_refusal(
        ModeloWorkspaceRefusalCode.CALCULATION_UNAVAILABLE,
        requested_target=ModeloWorkspaceExactWorkUnitTargetV1(
            target=ModeloExactWorkUnitTarget(work_unit_id=target.work_unit_id, bucket_id=target.bucket_id)
        ),
        selected_target=target,
        capability=ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION,
        reconsideration_condition="calculate this work unit, then request a graded snapshot again",
        facts=(),
        evidence=(),
        source_disposition=None,
        recovery_action=None,
    ).refusal

    factory = compose_installed_modelo_workspace_factory(
        bucket_id=bucket_id,
        declarations=(declaration,),
        projections=(projection,),
        graded_refusals={str(target.work_unit_id): refusal},
    )

    screen = factory(declaration)

    assert isinstance(screen, ModeloWorkspaceOverviewScreen)
    assert screen._session.graded_refusal is refusal

    # A generation with no entry for this unit opens the same projection honestly refusal-free.
    unrefused_factory = compose_installed_modelo_workspace_factory(
        bucket_id=bucket_id,
        declarations=(declaration,),
        projections=(projection,),
    )
    unrefused_screen = unrefused_factory(declaration)
    assert isinstance(unrefused_screen, ModeloWorkspaceOverviewScreen)
    assert unrefused_screen._session.graded_refusal is None


def test_installed_factory_refuses_a_declaration_that_disagrees_with_its_captured_session(
    bucket_and_repository,
) -> None:
    """A stale identity cannot use a current session merely by sharing an id."""
    bucket_id, repository = bucket_and_repository
    projection = resolve_real_result(bucket_id, repository, OutputLanguage.ES).projection
    declaration = _declaration(projection)
    contradictory = DeclarationsWorkspaceDeclarationRefV1(
        work_unit_id=declaration.work_unit_id,
        modelo=declaration.modelo,
        filing_year=declaration.filing_year,
        period=declaration.period,
        state=WorkUnitState.DESCARTADO,
        has_current_calculation=declaration.has_current_calculation,
        has_current_filing=declaration.has_current_filing,
    )

    with pytest.raises(ModeloWorkspaceDeclarationAdmissionError, match="contradicts"):
        compose_installed_modelo_workspace_factory(
            bucket_id=bucket_id,
            declarations=(contradictory,),
            projections=(projection,),
        )
