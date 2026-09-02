"""Real-behaviour proofs for the operator-level edit session facade.

Every test drives the facade the way a frontend would -- operator coordinates
in, operator-level outcomes out -- against a real admission over the bundled
registry. Nothing here constructs an Edit Contract V1 intent, address or
baseline, because a frontend cannot, and a test that reached for one would be
proving a boundary it had just stepped over.

See Also:
    :mod:`cadrumo.application.modelo.edit_session`
        The module under test, and the reasoning for keeping the contract
        records on this side of the package boundary.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.temporal import select_revision
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...operations.registry import OperationSchemaIdentityV1
from ..edit_contract import ModeloEditCompatibilityTupleV1, ModeloEditMutationFamily
from ..edit_services import modelo_edit_request_schema_identity, modelo_edit_result_schema_identity
from ..edit_session import (
    ModeloEditSession,
    ModeloEditSessionClosedError,
    open_modelo_edit_session,
)
from ..work_addressing import ModeloExactWorkUnitTarget
from ..workspace_models import ModeloWorkspaceExactWorkUnitTargetV1

if TYPE_CHECKING:
    from ..workspace_models import ModeloWorkspaceTargetV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_MODELO = "130"
_FILING_YEAR = 2026
_DIGEST = "a" * 64


def _schema_identity() -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1(schema_id="modelo.edit.contract", schema_version=1, schema_fingerprint=_DIGEST)


def _compatibility() -> ModeloEditCompatibilityTupleV1:
    return ModeloEditCompatibilityTupleV1(
        contract_set_digest=_DIGEST,
        operation_definition_id="modelo.calculate",
        definition_contract_digest=_DIGEST,
        request_schema=modelo_edit_request_schema_identity(),
        result_schema=modelo_edit_result_schema_identity(),
        review_projection_contract_version=None,
        review_schema=None,
        workspace_refresh_target_schema=_schema_identity(),
        financial_operand_schema=_schema_identity(),
    )


def _work_unit() -> WorkUnit:
    period = Period.from_year_and_code(_FILING_YEAR, "1T")
    modelo = ModeloCode(_MODELO)
    revision_id = select_revision(bundled_authority().validate_modelo(modelo), filing_year=_FILING_YEAR, period="1T").id
    now = datetime(2026, 1, 10, tzinfo=UTC)
    return WorkUnit(
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


def _target_for(work_unit: WorkUnit) -> ModeloWorkspaceTargetV1:
    return ModeloWorkspaceExactWorkUnitTargetV1(
        target=ModeloExactWorkUnitTarget(work_unit_id=work_unit.work_unit_id, bucket_id=work_unit.bucket_id)
    )


def _open() -> ModeloEditSession:
    work_unit = _work_unit()
    outcome = open_modelo_edit_session(
        _target_for(work_unit),
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        bucket_id=work_unit.bucket_id,
        work_catalogue=WorkUnitCatalogue.from_work_units((work_unit,)),
        calculation_catalogue=CalculationRevisionCatalogue(),
        compatibility=_compatibility(),
    )
    assert outcome.session is not None, f"admission refused: {outcome.message_key}"
    return outcome.session


def test_a_frontend_never_receives_an_edit_contract_record() -> None:
    """No public member of the session exposes a contract intent, address or baseline.

    The whole reason this module exists rather than a TUI-side session: the
    operator ruling was that the frontend holds an opaque handle. Asserted
    structurally rather than by reading the source, so a later method that
    returns a baseline fails here instead of silently widening the boundary.
    """
    session = _open()

    forbidden = ("Baseline", "Intent", "Submission", "AddressV1", "SurfaceEntry")
    exposed: list[str] = []
    for name in dir(session):
        if name.startswith("_"):
            continue
        value = getattr(session, name, None)
        if callable(value):
            continue
        for item in value if isinstance(value, tuple) else (value,):
            if any(token in type(item).__name__ for token in forbidden):
                exposed.append(f"{name} -> {type(item).__name__}")

    assert not exposed, f"the session handed a frontend an Edit Contract record: {exposed}"

    # Non-vacuity: the probe must be able to see the module's own public
    # records, or "nothing forbidden" would mean "nothing inspected".
    assert {f.name for f in fields(session.writable_scalars()[0])} == {"casilla_id", "data_type"}


def test_the_admitted_writable_surface_reaches_the_frontend_as_plain_strings() -> None:
    """A frontend can learn what to render without holding a surface record."""
    session = _open()

    writable = session.writable_scalars()

    assert writable, "the real M130 admission declares no writable scalar; the proof would be vacuous"
    assert all(isinstance(entry.casilla_id, str) and entry.casilla_id for entry in writable)
    assert all(isinstance(entry.data_type, str) and entry.data_type for entry in writable)


def test_a_typed_value_is_staged_and_a_second_answer_replaces_the_first() -> None:
    """Staging is keyed by casilla, so the operator's latest answer is the one submitted."""
    session = _open()
    casilla_id = session.writable_scalars()[0].casilla_id

    first = session.set_casilla(casilla_id, "1234.56", input_kind=InputKind.MANUAL, locale=OutputLanguage.ES)
    second = session.set_casilla(casilla_id, "99.00", input_kind=InputKind.MANUAL, locale=OutputLanguage.ES)

    assert first.accepted and second.accepted
    # One dirty address, not two: a list per address would submit both and
    # leave the contract to decide which answer won.
    assert session.dirty_casilla_ids() == (casilla_id,)


def test_an_unparseable_lexeme_is_an_outcome_rather_than_an_exception() -> None:
    """A mistyped value is ordinary on an editing surface and must not raise.

    It must also not stage: a refused parse that left the previous value
    staged would submit a number the operator has since replaced with
    nonsense, and one that staged the nonsense would submit an unparsed
    lexeme.
    """
    session = _open()
    casilla_id = session.writable_scalars()[0].casilla_id

    outcome = session.set_casilla(casilla_id, "not-a-number", input_kind=InputKind.MANUAL, locale=OutputLanguage.ES)

    assert outcome.accepted is False
    assert outcome.message_key, "a refusal must name a localisation key the surface can render"
    # Non-retention is NOT re-asserted here. It is proven properly in
    # entrypoints/tui/modelo/tests/test_c3_editor_accessibility.py with a unique
    # sentinel and an anti-tautology control; a second weaker copy using a
    # plausible value can pass while the real proof fails, which is worse than
    # no copy at all.
    assert session.dirty_casilla_ids() == ()


def test_clearing_is_distinct_from_discarding_the_operators_own_edit() -> None:
    """Clear submits a removal; discard reverts the staging and submits nothing."""
    session = _open()
    casilla_id = session.writable_scalars()[0].casilla_id

    session.clear_casilla(casilla_id)
    assert session.dirty_casilla_ids() == (casilla_id,)

    assert session.discard_casilla(casilla_id) is True
    assert session.dirty_casilla_ids() == ()
    assert session.discard_casilla(casilla_id) is False


def test_abandon_discards_every_staged_edit_and_closes_the_session() -> None:
    """Abandoning is explicit and final; a closed session refuses to stage again."""
    session = _open()
    casilla_id = session.writable_scalars()[0].casilla_id
    session.set_casilla(casilla_id, "10.00", input_kind=InputKind.MANUAL, locale=OutputLanguage.ES)
    assert session.is_dirty

    session.abandon()

    assert session.is_closed
    assert session.is_dirty is False
    with pytest.raises(ModeloEditSessionClosedError):
        session.set_casilla(casilla_id, "20.00", input_kind=InputKind.MANUAL, locale=OutputLanguage.ES)


def test_a_fresh_session_is_not_dirty() -> None:
    """Opening a session is not editing it."""
    session = _open()

    assert session.is_dirty is False
    assert session.dirty_casilla_ids() == ()
    assert session.dirty_row_keys() == ()
