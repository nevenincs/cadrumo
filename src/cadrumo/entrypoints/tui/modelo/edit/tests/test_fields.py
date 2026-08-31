"""Proofs that the scalar controls keep the four distinctions apart.

Driven against a real admission over the bundled registry, through the real
session facade. Nothing here fakes a parse outcome: a control that only
distinguishes zero from absent when a stub says so has not been shown to
distinguish them at all.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.edit.fields`
        The module under test, and the statement of the four distinctions.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ......application.modelo.edit_contract import ModeloEditCompatibilityTupleV1, ModeloEditMutationFamily
from ......application.modelo.edit_session import open_modelo_edit_session
from ......application.modelo.work_addressing import ModeloExactWorkUnitTarget
from ......application.modelo.workspace_models import ModeloWorkspaceExactWorkUnitTargetV1
from ......application.operations.registry import OperationSchemaIdentityV1
from ......core.external_constants import OutputLanguage
from ......core.period import Period
from ......domain.calculations.registry.authority import bundled_authority
from ......domain.calculations.registry.temporal import select_revision
from ......domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ......domain.modelos.codes import ModeloCode
from ......domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ..fields import ScalarFieldSet

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_MODELO = "130"
_FILING_YEAR = 2026
_DIGEST = "a" * 64


def _identity() -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1(schema_id="modelo.edit.contract", schema_version=1, schema_fingerprint=_DIGEST)


def _field_set() -> ScalarFieldSet:
    from ......application.modelo._edit_services import (
        modelo_edit_request_schema_identity,
        modelo_edit_result_schema_identity,
    )

    period = Period.from_year_and_code(_FILING_YEAR, "1T")
    modelo = ModeloCode(_MODELO)
    revision_id = select_revision(
        bundled_authority().validate_modelo(modelo), filing_year=_FILING_YEAR, period="1T"
    ).id
    now = datetime(2026, 1, 10, tzinfo=UTC)
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo=modelo, filing_year=_FILING_YEAR, period=period, revision_id=revision_id
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision_id,
        name=f"{_MODELO}-{_FILING_YEAR}-1T",
        created_at=now,
        updated_at=now,
    )
    outcome = open_modelo_edit_session(
        ModeloWorkspaceExactWorkUnitTargetV1(
            target=ModeloExactWorkUnitTarget(work_unit_id=work_unit.work_unit_id, bucket_id=work_unit.bucket_id)
        ),
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        bucket_id=work_unit.bucket_id,
        work_catalogue=WorkUnitCatalogue.from_work_units((work_unit,)),
        calculation_catalogue=CalculationRevisionCatalogue(),
        compatibility=ModeloEditCompatibilityTupleV1(
            contract_set_digest=_DIGEST,
            operation_definition_id="modelo.calculate",
            definition_contract_digest=_DIGEST,
            request_schema=modelo_edit_request_schema_identity(),
            result_schema=modelo_edit_result_schema_identity(),
            review_projection_contract_version=None,
            review_schema=None,
            workspace_refresh_target_schema=_identity(),
            financial_operand_schema=_identity(),
        ),
    )
    assert outcome.session is not None, f"admission refused: {outcome.message_key}"
    return ScalarFieldSet.for_session(outcome.session, locale=OutputLanguage.ES)


def test_controls_exist_only_for_casillas_the_admission_permits() -> None:
    """A control cannot be built for an address the contract will not accept."""
    fields = _field_set()

    assert fields.casilla_ids(), "the real M130 admission permits no scalar; the proof would be vacuous"
    with pytest.raises(KeyError, match="permitted surface"):
        fields.state("999999")


def test_zero_is_an_answer_and_not_an_absence() -> None:
    """Declaring zero stages a value; it must not read as an untouched control."""
    fields = _field_set()
    casilla_id = fields.casilla_ids()[0]

    state = fields.submit_lexeme(casilla_id, "0")

    assert state.touched is True
    assert state.is_unresolved is False
    assert fields.blocks_review() is False


def test_an_unparsed_lexeme_blocks_review_rather_than_staging_or_raising() -> None:
    """The operator's rejected text is remembered, and review refuses until it is resolved.

    All three properties matter together: staging it would submit nonsense,
    forgetting it would report the field as unchanged while the screen shows
    the text, and raising would make ordinary mistyping an error condition.
    """
    fields = _field_set()
    casilla_id = fields.casilla_ids()[0]

    state = fields.submit_lexeme(casilla_id, "not-a-number")

    assert state.touched is True, "a refused lexeme is still an interaction"
    assert state.is_unresolved is True
    assert fields.blocks_review() is True
    blockers = fields.unresolved()
    assert [item.casilla_id for item in blockers] == [casilla_id]
    # Non-retention belongs to the C3 accessibility suite, which proves it with
    # a unique sentinel across every reachable surface. Duplicating a weaker
    # form here would give two answers to one question.


def test_resolving_the_lexeme_releases_the_review_block() -> None:
    """A block is a state to leave, not a latch."""
    fields = _field_set()
    casilla_id = fields.casilla_ids()[0]
    fields.submit_lexeme(casilla_id, "not-a-number")
    assert fields.blocks_review() is True

    fields.submit_lexeme(casilla_id, "12.34")

    assert fields.blocks_review() is False
    assert fields.state(casilla_id).is_unresolved is False


def test_clearing_and_reverting_are_different_answers() -> None:
    """Clear submits a removal and stays touched; revert withdraws the edit entirely."""
    fields = _field_set()
    casilla_id = fields.casilla_ids()[0]

    cleared = fields.clear(casilla_id)
    assert cleared.touched is True, "clearing is an answer, not an absence"

    reverted = fields.revert(casilla_id)
    assert reverted.touched is False, "reverting returns the control to unanswered"


def test_clearing_resolves_an_outstanding_lexeme() -> None:
    """Replacing refused text with a definite instruction leaves nothing outstanding."""
    fields = _field_set()
    casilla_id = fields.casilla_ids()[0]
    fields.submit_lexeme(casilla_id, "not-a-number")

    fields.clear(casilla_id)

    assert fields.blocks_review() is False


def test_an_untouched_control_stages_nothing() -> None:
    """The unchanged distinction: building the controls is not answering them."""
    fields = _field_set()

    assert all(not fields.state(casilla_id).touched for casilla_id in fields.casilla_ids())
    assert fields.blocks_review() is False
