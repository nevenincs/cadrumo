"""The installed factory opens a workbench for exactly the declarations its generation admitted.

Built over the real pinned authority with repositories and a door that are
never reached: composing the factory and opening a workbench read nothing, so a
declaration the generation did not list -- or listed with other coordinates --
is refused before any screen exists.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from ......application.modelo.declarations_workspace import DeclarationsWorkspaceDeclarationRefV1
from ......core.period import Period
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ......domain.modelos.work_unit import WorkUnitState
from ...lifecycle import ModeloWorkspaceLifecycleDoor
from ..installed import (
    ModeloWorkspaceDeclarationAdmissionError,
    WorkbenchRepositories,
    compose_installed_modelo_workbench_factory,
)
from ..screen import ModeloWorkbenchScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _declaration(work_unit_id: str, period_code: str = "1T") -> DeclarationsWorkspaceDeclarationRefV1:
    return DeclarationsWorkspaceDeclarationRefV1(
        work_unit_id=work_unit_id,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, period_code),
        state=WorkUnitState.BORRADOR,
        has_current_calculation=False,
        has_current_filing=False,
    )


def _unreached_door(*_arguments: object) -> ModeloWorkspaceLifecycleDoor:
    raise AssertionError("opening a workbench must not build a lifecycle door")


def _factory(operation: PinnedAuthorityOperation, declarations: tuple[DeclarationsWorkspaceDeclarationRefV1, ...]):
    unreached = cast(Any, object())
    return compose_installed_modelo_workbench_factory(
        bucket_id="13000000-0000-4000-8000-000000000999",
        declarations=declarations,
        operation=operation,
        repositories=lambda: WorkbenchRepositories(
            work_units=unreached, calculations=unreached, verifications=unreached
        ),
        door=_unreached_door,
    )


def test_an_admitted_declaration_opens_its_workbench(operation: PinnedAuthorityOperation) -> None:
    declaration = _declaration("a" * 64)

    screen = _factory(operation, (declaration,))(declaration)

    assert isinstance(screen, ModeloWorkbenchScreen)


def test_a_declaration_the_generation_did_not_admit_is_refused(operation: PinnedAuthorityOperation) -> None:
    factory = _factory(operation, (_declaration("a" * 64),))

    with pytest.raises(ModeloWorkspaceDeclarationAdmissionError):
        factory(_declaration("b" * 64))
    with pytest.raises(ModeloWorkspaceDeclarationAdmissionError):
        factory(_declaration("a" * 64, period_code="2T"))


def test_a_generation_listing_one_declaration_twice_is_refused(operation: PinnedAuthorityOperation) -> None:
    declaration = _declaration("a" * 64)

    with pytest.raises(ModeloWorkspaceDeclarationAdmissionError):
        _factory(operation, (declaration, declaration))
