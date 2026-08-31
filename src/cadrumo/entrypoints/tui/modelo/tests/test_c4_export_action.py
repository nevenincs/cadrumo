"""Proofs for the fichero export enrolment.

The load-bearing property is a confidentiality one: the exported bytes must
never reach the operations journal, which is a different store with a different
lifetime from the encrypted one holding a taxpayer's filing artefacts.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.action.export`
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from .....application.export.google_operation import GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID
from .....application.modelo.operation_definitions import (
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    ModeloExportPublicResultV1,
    ModeloExportRequest,
    build_modelo_export_definition,
)
from .....application.modelo.workspace_models import ModeloWorkspaceCapabilityName
from .....application.operations.registry import OperationCancellation
from ..action import export as export_action
from ..actions import MODELO_ACTION_DISPATCH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WORK_UNIT_ID = "a" * 64
_REVISION_ID = "rev-2026-1T-0001"
_OUTPUT_PATH = "C:/exports/modelo-130-2026-1T.txt"


def _request(**overrides: object):
    kwargs: dict[str, object] = {
        "work_unit_id": _WORK_UNIT_ID,
        "calculation_revision_id": _REVISION_ID,
        "output_path": _OUTPUT_PATH,
        "actor_ref": "operator:test",
    }
    kwargs.update(overrides)
    return export_action.build_export_operation_request(**kwargs)  # type: ignore[arg-type]


def test_the_request_is_addressed_to_the_registered_modelo_export() -> None:
    """A request naming anything else would submit into nothing."""
    request = _request()

    assert request.definition_id == MODELO_EXPORT_OPERATION_DEFINITION_ID
    assert isinstance(request.payload, ModeloExportRequest)
    assert request.subject_ref == _WORK_UNIT_ID


def test_this_is_not_the_spreadsheet_export_that_bypasses_the_supervisor() -> None:
    """Two distinct registered operations, and only one carries the known bypass.

    Pinned because the names invite conflation. `export.google-sheets` is
    reached from the CLI by calling the service's execute directly, so its runs
    are unjournalled and unleased -- a defect recorded against the architecture
    lane. This enrolment is a different operation and submits through the
    composed supervisor, so it must not inherit that finding by association.
    """
    assert MODELO_EXPORT_OPERATION_DEFINITION_ID != GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID
    assert export_action.EXPORT_ACTION.action_id == MODELO_EXPORT_OPERATION_DEFINITION_ID


def test_the_exported_bytes_never_enter_the_request_or_the_result() -> None:
    """The confidentiality property, asserted over both whole field sets.

    An operation request is journalled, and a filing artefact is a taxpayer's
    complete declared position -- the most sensitive thing this application
    produces. Carrying the bytes would copy them out of the encrypted store
    into the operations journal, a different store with a different lifetime.
    The path is carried because a LOCATION is not CONTENT.

    Checked over every declared field rather than by naming a suspect, so a
    content-bearing field arriving later under any spelling fails here.
    """
    request_fields = set(ModeloExportRequest.model_fields)
    result_fields = set(ModeloExportPublicResultV1.model_fields)

    assert request_fields == {"calculation_revision_id", "output_path", "actor"}, (
        f"the export request's field set changed; check nothing carries artefact content: {sorted(request_fields)}"
    )
    for field in request_fields | result_fields:
        assert not any(token in field for token in ("bytes", "content", "payload_data", "artefact_body")), (
            f"a content-bearing field reached the journalled export contract: {field}"
        )


def test_the_subject_is_the_work_unit_so_two_exports_serialise() -> None:
    """Concurrent exports would produce files whose relative currency is unknowable."""
    first = _request(calculation_revision_id="rev-a")
    second = _request(calculation_revision_id="rev-b")

    assert first.subject_ref == second.subject_ref == _WORK_UNIT_ID


def test_cancellation_is_unsupported_so_no_surface_may_offer_it() -> None:
    """A half-written fichero is worse than one the operator waited for.

    Read from the operation, and checked structurally on the module so prose
    explaining the constraint stays permitted while a request is refused.
    """
    definition = build_modelo_export_definition()
    assert definition.capabilities.cancellation is OperationCancellation.UNSUPPORTED

    tree = ast.parse(pathlib.Path(inspect.getfile(export_action)).read_text(encoding="utf-8"))
    requests = [
        ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and "cancel" in ast.unparse(node.func).lower()
    ]
    assert not requests, f"the export enrolment requests cancellation, which its operation refuses: {requests}"


def test_the_action_is_gated_on_filing_export_readiness() -> None:
    """The gate is the workspace's own, read from the dispatch row."""
    assert export_action.EXPORT_ACTION is MODELO_ACTION_DISPATCH[MODELO_EXPORT_OPERATION_DEFINITION_ID]
    assert export_action.EXPORT_ACTION.capability is ModeloWorkspaceCapabilityName.FILING_EXPORT_READINESS
    assert export_action.EXPORT_ACTION.destroys_subject is False


def test_the_module_reaches_no_export_writer_or_adapter() -> None:
    """The wrong path succeeds, so it is refused structurally rather than by review."""
    tree = ast.parse(pathlib.Path(inspect.getfile(export_action)).read_text(encoding="utf-8"))

    reached: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            reached.extend(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            reached.extend(alias.name for alias in node.names)

    forbidden = [name for name in reached if "adapters" in name or "export_draft" in name or "filing.export" in name]
    assert not forbidden, f"the export action reaches a writer or adapter directly: {forbidden}"


def test_submission_does_not_start_the_run() -> None:
    """Starting belongs to the presenting modal."""
    source = inspect.getsource(export_action.submit_export)

    assert "submission.submit(" in source
    assert "submission.start(" not in source


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_destination_is_refused_before_submission(blank: str) -> None:
    """An export to nowhere would journal and lease work that cannot settle."""
    with pytest.raises(ValueError):
        _request(output_path=blank)
