"""Proofs for the local filing enrolment.

The load-bearing property is a prohibition: this action must not reach any AEAT
submission path, and what it records must never be classifiable as official
AEAT evidence.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.action.file`
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from .....application.calculations.observations_repository import ObservationSourceKind
from .....application.modelo.operation_definitions import (
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    ModeloWorkFileRequest,
)
from .....application.modelo.workspace_models import ModeloWorkspaceCapabilityName
from ..action import file as file_action
from ..actions import MODELO_ACTION_DISPATCH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WORK_UNIT_ID = "a" * 64
_REVISION_ID = "rev-2026-1T-0001"
_REPORT_ID = "vr-2026-1T-0001"


def _request(**overrides: object):
    kwargs: dict[str, object] = {
        "work_unit_id": _WORK_UNIT_ID,
        "calculation_revision_id": _REVISION_ID,
        "verification_report_id": _REPORT_ID,
        "actor_ref": "operator:test",
    }
    kwargs.update(overrides)
    return file_action.build_file_operation_request(**kwargs)  # type: ignore[arg-type]


def test_the_request_is_addressed_to_the_registered_file_operation() -> None:
    """A request naming anything else would submit into nothing."""
    request = _request()

    assert request.definition_id == MODELO_WORK_FILE_OPERATION_DEFINITION_ID
    assert isinstance(request.payload, ModeloWorkFileRequest)
    assert request.subject_ref == _WORK_UNIT_ID


def test_the_action_reaches_no_aeat_submission_path() -> None:
    """The standing prohibition, asserted structurally rather than trusted.

    Checked against the module's own AST so a submission path reached through
    a deferred function-local import cannot hide from a reader scanning the
    header. This application never files to the sede; a person does that
    outside it.
    """
    tree = ast.parse(pathlib.Path(inspect.getfile(file_action)).read_text(encoding="utf-8"))

    reached: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            reached.extend(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            reached.extend(alias.name for alias in node.names)

    forbidden = [name for name in reached if "sede" in name.lower() or "outbound.aeat" in name.lower()]
    assert not forbidden, f"the local filing action reaches an AEAT submission path: {forbidden}"


def test_a_local_filing_is_never_official_aeat_evidence() -> None:
    """What this records must not satisfy a gate that means "the AEAT saw it".

    `app_filing` is the source kind a local filing stamps, and it must answer
    False. The three official kinds are all AEAT-sourced -- a stamped
    justificante, a live sede capture, a CSV register entry -- and a local
    filing joining them would let a cross-period clean-state gate believe the
    AEAT accepted something it has never seen.
    """
    assert ObservationSourceKind.APP_FILING.is_official_aeat is False

    official = {kind.name for kind in ObservationSourceKind if kind.is_official_aeat}
    assert official == {"AEAT_SEDE_JUSTIFICANTE", "AEAT_SEDE_LIVE_CAPTURE", "AEAT_CSV_REGISTER"}, (
        f"the official-evidence set changed; a locally produced kind must never join it: {sorted(official)}"
    )


def test_approval_names_both_the_revision_and_the_verification() -> None:
    """Approving a revision alone would file on the strength of a stale look.

    A revision re-verified since the operator approved it is a different fact.
    Carrying the report id is what lets the platform tell those apart.
    """
    request = _request()

    assert request.payload.approval.calculation_revision_id == _REVISION_ID
    assert request.payload.approval.verification_report_id == _REPORT_ID


def test_the_action_does_not_resolve_the_approval_for_itself() -> None:
    """A self-resolved approval would always match and never refuse.

    Both ids are required parameters, so the caller must supply what the
    operator approved -- the same discipline the discard baseline follows.
    """
    signature = inspect.signature(file_action.build_file_operation_request)

    for name in ("calculation_revision_id", "verification_report_id"):
        assert signature.parameters[name].default is inspect.Parameter.empty, f"{name} must not have a default"


def test_the_elections_are_not_restated_by_this_module() -> None:
    """A second copy of a default is a second place for it to be wrong.

    These two decide whether a refund is compensated or paid out, so the
    request type's own declared defaults must apply when the operator chose
    nothing.
    """
    payload = _request().payload
    declared_refund = ModeloWorkFileRequest.model_fields["refund_election"].default
    declared_payment = ModeloWorkFileRequest.model_fields["payment_election"].default

    assert payload.refund_election == declared_refund
    assert payload.payment_election == declared_payment


def test_an_explicit_election_overrides_the_declared_default() -> None:
    """Passing through only when chosen must still let a choice reach the payload."""
    from .....core.refund_election import RefundElection

    chosen = next(member for member in RefundElection if member != ModeloWorkFileRequest.model_fields["refund_election"].default)
    payload = _request(refund_election=chosen).payload

    assert payload.refund_election == chosen


def test_the_action_is_gated_on_filing_draft_readiness() -> None:
    """The gate is the workspace's own, read from the dispatch row."""
    assert file_action.FILE_ACTION is MODELO_ACTION_DISPATCH[MODELO_WORK_FILE_OPERATION_DEFINITION_ID]
    assert file_action.FILE_ACTION.capability is ModeloWorkspaceCapabilityName.FILING_DRAFT_READINESS
    assert file_action.FILE_ACTION.destroys_subject is False


def test_submission_does_not_start_the_run() -> None:
    """Starting belongs to the presenting modal."""
    source = inspect.getsource(file_action.submit_file)

    assert "submission.submit(" in source
    assert "submission.start(" not in source


def test_a_blank_note_is_refused_while_an_absent_one_is_accepted() -> None:
    """Recording no note and recording an empty note are different claims."""
    assert _request().payload.notes is None
    assert _request(notes="filed by hand at the sede").payload.notes == "filed by hand at the sede"

    with pytest.raises(ValueError):
        _request(notes="")
