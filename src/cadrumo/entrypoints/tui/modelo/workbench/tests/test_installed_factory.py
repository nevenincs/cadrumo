"""The installed factory opens a workbench for exactly the declarations its generation admitted.

Built with a source and a door that are never reached: composing the factory
and opening a workbench read nothing, so a declaration the generation did not
list -- or listed with other coordinates -- is refused before any screen exists.
"""

from __future__ import annotations

import pytest

from ......application.modelo.casilla_help import ModeloCasillaHelpCardV1
from ......application.modelo.declarations_workspace import DeclarationsWorkspaceDeclarationRefV1
from ......application.modelo.workbench_read import ModeloWorkbenchFormReadV1
from ......core.casilla_id import CasillaId
from ......core.external_constants import OutputLanguage
from ......core.period import Period
from ......domain.modelos.work_unit import WorkUnitState
from ...lifecycle import ModeloWorkspaceLifecycleDoor
from ..installed import (
    ModeloWorkspaceDeclarationAdmissionError,
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


class _UnreadSource:
    """A source the workbench holds but, until it is mounted, never reads."""

    def read_form(self, language: OutputLanguage) -> ModeloWorkbenchFormReadV1:
        raise AssertionError("opening a workbench must not read its declaration")

    def help_card(
        self,
        casilla_id: CasillaId,
        *,
        registry_revision_id: str,
        calculation_revision_id: str | None,
        language: OutputLanguage,
    ) -> ModeloCasillaHelpCardV1:
        raise AssertionError("opening a workbench must not read its declaration")


def _factory(declarations: tuple[DeclarationsWorkspaceDeclarationRefV1, ...]):
    return compose_installed_modelo_workbench_factory(
        declarations=declarations,
        source=lambda _declaration: _UnreadSource(),
        door=_unreached_door,
    )


def test_an_admitted_declaration_opens_its_workbench() -> None:
    declaration = _declaration("a" * 64)

    screen = _factory((declaration,))(declaration)

    assert isinstance(screen, ModeloWorkbenchScreen)


def test_a_declaration_the_generation_did_not_admit_is_refused() -> None:
    factory = _factory((_declaration("a" * 64),))

    with pytest.raises(ModeloWorkspaceDeclarationAdmissionError):
        factory(_declaration("b" * 64))
    with pytest.raises(ModeloWorkspaceDeclarationAdmissionError):
        factory(_declaration("a" * 64, period_code="2T"))


def test_a_generation_listing_one_declaration_twice_is_refused() -> None:
    declaration = _declaration("a" * 64)

    with pytest.raises(ModeloWorkspaceDeclarationAdmissionError):
        _factory((declaration, declaration))


def test_a_generation_with_no_declarations_still_offers_a_factory_that_refuses_any_declaration() -> None:
    factory = _factory(())

    with pytest.raises(ModeloWorkspaceDeclarationAdmissionError):
        factory(_declaration("a" * 64))
