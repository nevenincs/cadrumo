"""A declaration whose revision declares less than filing grade reads its real state in the list.

The published Modelo 390 for the horizon year is selected by the law at applicability
grade. The list reads it at the grade the revision declares, as the form does,
so an uncalculated 390 reads as a draft and its result box is read from the
same revision the form shows, while
asking the same revision for filing grade, as the export and recording gates
do, still refuses.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnitState
from ..declaration_summary import DeclarationSummaryState, declaration_summary
from ..declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1
from ..settlement_casilla import declaration_result_casilla_id
from ..work_form_service import modelo_form_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "390"
_YEAR = filing_year_envelope().horizon
_PERIOD = Period.from_year_and_code(_YEAR, "0A")


def test_the_390_revision_declares_less_than_filing_grade(operation: PinnedAuthorityOperation) -> None:
    revision = operation.revision_for_context(_MODELO, filing_year=_YEAR, period=_PERIOD.registry_token)

    assert revision.effective_authority_grade is not RegistryAuthorityGrade.FILING
    # The filing gates keep asking for filing grade, and the registry keeps refusing it here.
    with pytest.raises(RegistryValidationError):
        operation.snapshot(_MODELO, filing_year=_YEAR, period=_PERIOD.registry_token)


def test_an_uncalculated_applicability_graded_declaration_reads_as_a_draft(operation: PinnedAuthorityOperation) -> None:
    declaration = DeclarationsWorkspaceDeclarationRefV1(
        work_unit_id="e" * 64,
        modelo=ModeloCode(_MODELO),
        filing_year=_YEAR,
        period=_PERIOD,
        state=WorkUnitState.BORRADOR,
        has_current_calculation=False,
        has_current_filing=False,
    )

    summary = declaration_summary(declaration, revisions={}, verification=None, operation=operation)

    assert summary.state is DeclarationSummaryState.DRAFT
    assert summary.technical_reason is None


def test_the_list_and_the_form_read_the_same_revision_at_its_declared_grade(
    operation: PinnedAuthorityOperation,
) -> None:
    revision = operation.revision_for_context(_MODELO, filing_year=_YEAR, period=_PERIOD.registry_token)

    listed = modelo_form_snapshot(operation, ModeloCode(_MODELO), _YEAR, _PERIOD)
    formed = modelo_form_snapshot(operation, ModeloCode(_MODELO), _YEAR, _PERIOD, str(revision.id))

    assert listed.revision.id == formed.revision.id == revision.id
    # The row's result box is read from the same revision the form shows, whatever it declares.
    assert declaration_result_casilla_id(listed.revision) == declaration_result_casilla_id(formed.revision)


def test_a_refusal_of_the_calculation_gate_is_confined_to_its_row(operation: PinnedAuthorityOperation) -> None:
    """The gate asks for filing grade, which the registry refuses for this 390; the row reads as unreadable."""
    selected = operation.revision_for_context(_MODELO, filing_year=_YEAR, period=_PERIOD.registry_token)
    work_unit_id = "e" * 64
    instant = datetime(1980, 3, 10, 12, tzinfo=UTC)
    head = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_provenance=(),
            filing_instance_evidence=None,
        ),
        work_unit_id=work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=_MODELO, revision_id=selected.id, modelo_year=_YEAR, period=_PERIOD.registry_token
        ),
        state=CalculationRevisionState.BORRADOR,
        created_at=instant,
        updated_at=instant,
        source_provenance=(),
        filing_instance_evidence=None,
    )
    declaration = DeclarationsWorkspaceDeclarationRefV1(
        work_unit_id=work_unit_id,
        modelo=ModeloCode(_MODELO),
        filing_year=_YEAR,
        period=_PERIOD,
        state=WorkUnitState.BORRADOR,
        has_current_calculation=True,
        has_current_filing=False,
    )

    summary = declaration_summary(
        declaration, revisions={head.calculation_revision_id: head}, verification=None, operation=operation
    )

    assert summary.state is DeclarationSummaryState.UNREADABLE
    assert summary.result is None and summary.technical_reason is not None
