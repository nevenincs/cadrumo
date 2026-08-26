"""Proofs for the registered modelo.work.rename operation."""

from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core import OperationDurability, OperationEffect
from ...operations.capabilities import OperationConflictScope, OperationRequestStoragePolicy
from ...operations.models import CredentialFreeOperationRequest
from ..operation_definitions import (
    MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
    ModeloWorkRenameExecutor,
    ModeloWorkRenamePublicResultV1,
    ModeloWorkRenameRequest,
    build_modelo_work_rename_definition,
    build_modelo_work_rename_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _definition():
    return build_modelo_work_rename_definition(actor="operator")


def test_the_definition_enrolls_the_declared_lifecycle_subject() -> None:
    """The operation id is the one the lifecycle writer already names."""
    definition = _definition()

    assert definition.definition_id == MODELO_WORK_RENAME_OPERATION_DEFINITION_ID
    assert definition.definition_id == "modelo.work.rename"


def test_a_rename_is_recorded_and_never_resumed() -> None:
    """A rename is durable and interrupts rather than resuming after owner loss."""
    capabilities = _definition().capabilities

    assert capabilities.durability is OperationDurability.RECORDED
    assert capabilities.conflict_scope is OperationConflictScope.DEFINITION_SUBJECT
    assert OperationEffect.UNKNOWN in capabilities.permitted_effects


def test_the_request_is_credential_free_and_journalable() -> None:
    """A rename names a unit and a label, so the request is safe to journal."""
    definition = _definition()

    assert definition.capabilities.request_storage is OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL
    assert issubclass(ModeloWorkRenameRequest, CredentialFreeOperationRequest)


def test_the_request_refuses_an_empty_unit_or_name() -> None:
    """A rename with no subject or no label is refused at the boundary."""
    with pytest.raises(ValidationError):
        ModeloWorkRenameRequest(work_unit_id="", new_name="Q1")
    with pytest.raises(ValidationError):
        ModeloWorkRenameRequest(work_unit_id="unit-1", new_name="")


def test_the_public_result_is_a_projection_not_the_stored_record() -> None:
    """The result carries no lifecycle state a consumer could depend on."""
    fields = set(ModeloWorkRenamePublicResultV1.model_fields)

    assert fields == {"result_version", "work_unit_id", "name", "bucket_id"}
    assert "state" not in fields
    assert "updated_at" not in fields


def test_the_executor_delegates_and_recreates_no_lifecycle_policy() -> None:
    """The executor calls the single writer and decides nothing itself.

    This is the whole point of the enrolment: if the supervised path re-derived
    the rules, a lifecycle refusal would depend on which door the operator came
    through.
    """
    source = inspect.getsource(ModeloWorkRenameExecutor)
    tree = ast.parse(textwrap.dedent(source))
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}

    assert "rename_work_unit" in called
    for forbidden in ("WorkUnitCatalogueRepository", "BucketEventHistoryRepository", "upsert_work_unit"):
        assert forbidden not in source, f"the executor reaches past its writer: {forbidden}"
    assert "DESCARTADO" not in source, "discard policy belongs to the writer, not the enrolment"


def test_the_registration_binds_stable_public_schemas() -> None:
    """Request and result each answer to a versioned public schema id."""
    registration = build_modelo_work_rename_registration(_definition())
    schema_ids = {binding.identity.schema_id for binding in registration.schema_bindings}

    assert "modelo.work.rename.request" in schema_ids
    assert "modelo.work.rename.result" in schema_ids


def test_the_definition_module_is_public_and_importable_directly() -> None:
    """A composition root outside this package must be able to import it."""
    module = __import__("cadrumo.application.modelo.operation_definitions", fromlist=["__all__"])
    package = __import__("cadrumo.application.modelo", fromlist=["__name__"])

    assert not Path(module.__file__ or "").name.startswith("_")
    for name in module.__all__:
        assert not hasattr(package, name), f"the modelo package binds {name}"
