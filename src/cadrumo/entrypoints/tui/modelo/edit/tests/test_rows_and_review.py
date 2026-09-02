"""Proofs for repeated-row addressing and the mandatory review gate.

Driven through the real session facade over a real admission. The row set and
the gate are exercised directly rather than through a mounted application,
because what has to be correct here is addressing and refusal, and a proof that
requires a running terminal proves those least reliably.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.edit.rows`
    :mod:`cadrumo.entrypoints.tui.modelo.edit.review`
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ......application.modelo.edit_contract import ModeloEditCompatibilityTupleV1, ModeloEditMutationFamily
from ......application.modelo.edit_session import ModeloEditSession, open_modelo_edit_session
from ......application.modelo.work_addressing import ModeloExactWorkUnitTarget
from ......application.modelo.workspace_models import ModeloWorkspaceExactWorkUnitTargetV1
from ......application.operations.registry import OperationSchemaIdentityV1
from ......core.external_constants import OutputLanguage
from ......core.period import Period
from ......domain.calculations.registry.authority import bundled_authority
from ......domain.calculations.registry.temporal import select_revision
from ......domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ......domain.modelos.codes import ModeloCode
from ......domain.modelos.row_models import Modelo349OperadorRow
from ......domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ..fields import ScalarFieldSet
from ..review import ReviewGate, ReviewRefusal, ReviewSummary, UnsavedChoice
from ..rows import RepeatedRowSet

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_MODELO = "130"
_FILING_YEAR = 2026
_DIGEST = "a" * 64


def _identity() -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1(schema_id="modelo.edit.contract", schema_version=1, schema_fingerprint=_DIGEST)


def _session() -> ModeloEditSession:
    from ......application.modelo.edit_services import (
        modelo_edit_request_schema_identity,
        modelo_edit_result_schema_identity,
    )

    period = Period.from_year_and_code(_FILING_YEAR, "1T")
    modelo = ModeloCode(_MODELO)
    revision_id = select_revision(bundled_authority().validate_modelo(modelo), filing_year=_FILING_YEAR, period="1T").id
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
    return outcome.session


def _row(nif: str = "DE123456789") -> Modelo349OperadorRow:
    return Modelo349OperadorRow(
        codigo_pais="DE",
        nif_comunitario=nif,
        razon_social="Beispiel GmbH",
        clave_operacion="E",
        importe=Decimal("100.00"),
    )


def test_a_row_is_addressed_by_its_natural_key_and_not_by_position() -> None:
    """Staging two rows keeps both, addressed by identity rather than order."""
    rows = RepeatedRowSet.for_session(_session())

    first = rows.stage(_row("DE123456789"), detail_row_kind="operador")
    second = rows.stage(_row("FR987654321"), detail_row_kind="operador")

    keys = rows.staged_keys()
    # Compared against the addresses staging REPORTED rather than against
    # hand-written keys. An earlier version of this test wrote "DE123456789"
    # and passed while the row's real key was the compound
    # "DE123456789|E" -- so it was asserting a key no row ever had.
    assert [key.natural_key for key in keys] == [first.natural_key, second.natural_key]
    assert first.natural_key == "DE123456789|E", "the key is the row's compound business identity"


def test_restaging_the_same_key_replaces_rather_than_duplicates() -> None:
    """A row is whole: the operator's second version of it is the version."""
    rows = RepeatedRowSet.for_session(_session())
    first = rows.stage(_row(), detail_row_kind="operador")
    second = rows.stage(_row(), detail_row_kind="operador")
    assert first == second, "the same row must derive the same address both times"

    assert len(rows.staged_keys()) == 1


def test_removing_is_distinct_from_reverting_the_operators_own_staging() -> None:
    """Remove submits a deletion; revert withdraws the edit entirely."""
    rows = RepeatedRowSet.for_session(_session())
    key = rows.stage(_row(), detail_row_kind="operador")

    removed = rows.remove(_row(), detail_row_kind="operador")
    assert removed == key
    assert [k.natural_key for k in rows.staged_keys()] == [key.natural_key]

    assert rows.revert(key) is True
    assert rows.staged_keys() == ()
    assert rows.revert(key) is False


def test_an_incomplete_draft_is_never_submitted() -> None:
    """A half-written declaration must not reach the session.

    The draft stays open so the operator can finish it, rather than being
    discarded or staged in a partial state -- both of which would lose work
    the operator can still see on screen.
    """
    rows = RepeatedRowSet.for_session(_session())
    draft = rows.open_draft("draft-1", "operador")

    assert draft.is_complete is False
    assert rows.commit_draft("draft-1") is None
    assert rows.staged_keys() == ()
    assert len(rows.drafts()) == 1, "an incomplete draft stays open rather than being dropped"


def test_a_completed_draft_stages_once_and_stops_being_a_draft() -> None:
    """Committing moves the row from surface state into the staged submission."""
    rows = RepeatedRowSet.for_session(_session())
    draft = rows.open_draft("draft-1", "operador")
    draft.natural_key = "DE123456789"
    draft.row = _row()

    key = rows.commit_draft("draft-1")

    assert key is not None
    assert [k.natural_key for k in rows.staged_keys()] == ["DE123456789|E"]
    assert rows.drafts() == (), "a committed draft must not remain open and stage twice"


def test_reopening_a_draft_correlation_does_not_create_a_second_row() -> None:
    """A re-render that reopens the same draft is idempotent."""
    rows = RepeatedRowSet.for_session(_session())

    first = rows.open_draft("draft-1", "operador")
    second = rows.open_draft("draft-1", "operador")

    assert first is second
    assert len(rows.drafts()) == 1


def test_review_refuses_an_empty_edit_rather_than_offering_a_no_op() -> None:
    """Reviewing nothing invites confirming a submission with no intents."""
    session = _session()
    gate = ReviewGate.over(
        session, ScalarFieldSet.for_session(session, locale=OutputLanguage.ES), RepeatedRowSet.for_session(session)
    )

    result = gate.review(work_catalogue=WorkUnitCatalogue(), calculation_catalogue=CalculationRevisionCatalogue())

    assert isinstance(result, ReviewRefusal)
    assert result.message_key == "flows.modelo_edit.review.nothing_staged"


def test_an_unresolved_lexeme_blocks_review_and_names_the_control() -> None:
    """The gate refuses BEFORE preflight, and says which control to return to.

    Naming the address is what makes the refusal actionable: a gate that
    reports errors without saying where sends the operator searching.
    """
    session = _session()
    fields = ScalarFieldSet.for_session(session, locale=OutputLanguage.ES)
    casilla_id = fields.casilla_ids()[0]
    fields.submit_lexeme(casilla_id, "not-a-number")
    gate = ReviewGate.over(session, fields, RepeatedRowSet.for_session(session))

    result = gate.review(work_catalogue=WorkUnitCatalogue(), calculation_catalogue=CalculationRevisionCatalogue())

    assert isinstance(result, ReviewRefusal)
    assert result.message_key == "flows.modelo_edit.review.unresolved_entries"
    assert result.blocking_casilla_ids == (casilla_id,)


def test_a_staged_edit_reviews_and_reports_its_changed_addresses() -> None:
    """A reviewable edit carries every changed semantic address, not a widget list."""
    session = _session()
    fields = ScalarFieldSet.for_session(session, locale=OutputLanguage.ES)
    casilla_id = fields.casilla_ids()[0]
    fields.submit_lexeme(casilla_id, "12.34")
    rows = RepeatedRowSet.for_session(session)
    staged = rows.stage(_row(), detail_row_kind="operador")
    gate = ReviewGate.over(session, fields, rows)

    result = gate.review(work_catalogue=WorkUnitCatalogue(), calculation_catalogue=CalculationRevisionCatalogue())

    assert isinstance(result, ReviewSummary)
    assert result.changed_casilla_ids == (casilla_id,)
    assert [key.natural_key for key in result.changed_row_keys] == [staged.natural_key]
    assert result.preflight is not None, "the contract's own verdict must be carried through"


def test_leaving_with_staged_work_offers_exactly_stay_or_abandon() -> None:
    """There is no silent save on navigation: an unreviewed edit was never approved."""
    session = _session()
    fields = ScalarFieldSet.for_session(session, locale=OutputLanguage.ES)
    fields.submit_lexeme(fields.casilla_ids()[0], "5.00")
    gate = ReviewGate.over(session, fields, RepeatedRowSet.for_session(session))

    assert gate.leaving_with_unsaved_changes() is True

    gate.abandon()

    assert gate.leaving_with_unsaved_changes() is False
    assert {UnsavedChoice.STAY, UnsavedChoice.ABANDON} == {"stay", "abandon"}


def test_a_staged_row_reaches_the_operation_payload_with_its_components_intact() -> None:
    """The submit path carries the row AND re-derives its address from components.

    This is the proof that closes the identity-component asymmetry rather
    than merely documenting it. The wire address is built from the components
    captured when the row was staged, never by splitting the joined key, so
    the payload's components must re-join to exactly the natural key the
    session reports -- including the separator between them.

    Drives the whole path rather than the mirror alone: a mirror proven in
    isolation can still be wired up wrongly at the one site that uses it.
    """
    session = _session()
    rows = RepeatedRowSet.for_session(session)
    key = rows.stage(_row(), detail_row_kind="operador")

    request = session.submit()

    staged = request.submission.detail_row_intents
    assert len(staged) == 1
    address = staged[0].address
    assert "|".join(address.identity_components) == key.natural_key
    assert len(address.identity_components) > 1, (
        "a single-component key would not exercise the join, and this row's key is compound"
    )
    assert staged[0].row is not None, "an update intent must carry its row"
    assert staged[0].row.nif_comunitario == "DE123456789"
    # The amount crosses as characters, exactly as the scalar path does.
    assert staged[0].row.importe == "100.00"


def test_a_removal_reaches_the_payload_addressed_but_carrying_no_row() -> None:
    """A delete addresses the row without restating it.

    Removal still needs the row at the API, because the components are not
    recoverable from the key -- but what crosses is the address alone, which
    is what the intent kind means.
    """
    session = _session()
    rows = RepeatedRowSet.for_session(session)
    key = rows.remove(_row(), detail_row_kind="operador")

    staged = session.submit().submission.detail_row_intents

    assert len(staged) == 1
    assert staged[0].row is None
    assert "|".join(staged[0].address.identity_components) == key.natural_key
