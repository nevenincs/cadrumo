"""Proofs for the amendment enrolment.

Amendment is the only action in this cohort addressed to something already
filed with the tax authority, and its contract is correspondingly stricter: a
reason is mandatory, at least one correction is required, and the corrected
values cross as exact characters.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.action.amend`
"""

from __future__ import annotations

import ast
import inspect
import pathlib
from collections.abc import Mapping

import pytest

from .....application.modelo.operation_definitions import (
    MODELO_WORK_AMEND_OPERATION_DEFINITION_ID,
    ModeloWorkAmendRequest,
)
from .....application.operations.models import OperationRequest
from .....domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from ..action import amend as amend_action
from ..actions import MODELO_ACTION_DISPATCH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FILING_RECORD_ID = "fr-2026-1T-0001"
_KIND = next(iter(CalculationRevisionAmendmentKind))


def _request(
    *,
    from_filing_record_id: str = _FILING_RECORD_ID,
    amendment_kind: CalculationRevisionAmendmentKind = _KIND,
    overrides: Mapping[str, str] | None = None,
    reason: str = "corrected the declared base",
    actor_ref: str = "operator:test",
) -> OperationRequest[ModeloWorkAmendRequest]:
    return amend_action.build_amend_operation_request(
        from_filing_record_id=from_filing_record_id,
        amendment_kind=amendment_kind,
        overrides={"01": "150.00"} if overrides is None else overrides,
        reason=reason,
        actor_ref=actor_ref,
    )


def test_the_request_is_addressed_to_the_registered_amend_operation() -> None:
    """A request naming anything else would submit into nothing."""
    request = _request()

    assert request.definition_id == MODELO_WORK_AMEND_OPERATION_DEFINITION_ID
    assert isinstance(request.payload, ModeloWorkAmendRequest)


def test_the_subject_is_the_filed_record_and_not_a_work_unit() -> None:
    """An amendment corrects something already filed, so that is what contends.

    Two amendments of the same filed return describe competing corrections to
    one declaration and must serialise. Keying the subject on a work unit
    would let them proceed concurrently, and the authority would receive two
    corrections with no established order.
    """
    request = _request()

    assert request.subject_ref == _FILING_RECORD_ID
    assert request.payload.baseline.from_filing_record_id == _FILING_RECORD_ID


def test_a_reason_is_mandatory_unlike_the_discard_action() -> None:
    """An amendment tells the authority a filed figure was wrong.

    Discard's reason is optional because abandoning local work owes nobody an
    explanation. This one does not have that luxury, and the difference is a
    deliberate asymmetry rather than an inconsistency.
    """
    assert ModeloWorkAmendRequest.model_fields["reason"].is_required()

    with pytest.raises(ValueError):
        _request(reason="")


def test_an_amendment_with_no_corrections_is_refused() -> None:
    """Re-filing identical numbers would tell the authority something changed.

    The contract requires at least one override, so an empty correction set
    cannot reach the journal.
    """
    with pytest.raises(ValueError):
        _request(overrides={})


def test_corrections_cross_as_the_exact_characters_submitted() -> None:
    """On a correction to a filed return, the digits are the whole content.

    The value is a pattern-checked string rather than a Decimal, because a
    Decimal accepts number-or-string and emits string -- so a journalled
    request would not round-trip to what the operator typed.
    """
    payload = _request(overrides={"01": "1234.56", "02": "-99.10"}).payload

    submitted = {override.casilla_id: override.value for override in payload.overrides}
    assert submitted == {"01": "1234.56", "02": "-99.10"}
    assert all(isinstance(override.value, str) for override in payload.overrides)


def test_one_casilla_cannot_be_corrected_twice_in_one_amendment() -> None:
    """A mapping input makes the contradiction unrepresentable.

    A sequence would admit the same casilla twice with different corrections
    and leave the contract to decide which one counted.
    """
    signature = inspect.signature(amend_action.build_amend_operation_request)
    annotation = str(signature.parameters["overrides"].annotation)

    assert "Mapping" in annotation, f"overrides must be a mapping, not a sequence: {annotation}"


def test_a_malformed_correction_value_is_refused_before_submission() -> None:
    """A value that is not a decimal figure would journal work that cannot settle."""
    with pytest.raises(ValueError):
        _request(overrides={"01": "not-a-number"})


def test_the_amend_wizard_is_a_different_action_and_is_not_enrolled_here() -> None:
    """Enrolling one action does not assign another a disposition.

    `modelo.work.amend_wizard` stays owned by the guided-flow renderer. It is
    absent from the dispatch table because it has no registered operation, and
    conflating the two would claim this row replaced a surface it never
    touched.
    """
    assert "modelo.work.amend_wizard" not in MODELO_ACTION_DISPATCH
    assert amend_action.AMEND_ACTION.action_id == MODELO_WORK_AMEND_OPERATION_DEFINITION_ID


def test_the_module_reaches_no_amendment_writer() -> None:
    """The wrong path succeeds, so it is refused structurally rather than by review."""
    tree = ast.parse(pathlib.Path(inspect.getfile(amend_action)).read_text(encoding="utf-8"))

    reached: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            reached.extend(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            reached.extend(alias.name for alias in node.names)

    forbidden = [name for name in reached if "_amendment_actions" in name or "amend_modelo_revision" in name]
    assert not forbidden, f"the amend action reaches an amendment writer directly: {forbidden}"


def test_submission_does_not_start_the_run() -> None:
    """Starting belongs to the presenting modal."""
    source = inspect.getsource(amend_action.submit_amend)

    assert "submission.submit(" in source
    assert "submission.start(" not in source
