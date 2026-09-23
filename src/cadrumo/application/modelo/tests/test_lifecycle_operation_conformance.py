"""Conformance over every enrolled modelo lifecycle operation.

The denominator here is DERIVED from the definitions module, never listed. A
hand-maintained list of enrolments to check cannot report the enrolment nobody
added to it, so a seventh operation landing tomorrow is covered by every
assertion below without anyone remembering to extend this file.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from ....core.models import STRICT_FROZEN_CONFIG
from ....core.operations import OperationDurability, OperationEffect, OperationLifecycle
from ...operations.capabilities import OperationRequestStoragePolicy, OperationSensitiveInputPolicy
from ...operations.models import CredentialFreeOperationRequest, OperationIdentity, OperationRequest
from ...operations.persistence.journal import OperationPersistedSnapshot
from ...operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from ...operations.supervisor import OperationSupervisor
from .. import operation_definitions as definitions_module

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Arguments every enrolment factory may ask for. A factory that needs
#: something absent here fails loudly rather than being skipped.
_FACTORY_ARGUMENTS: dict[str, Any] = {
    "actor": "operator",
    "profile_resolver": lambda operation: None,
    "command_builder": lambda revision, path: None,
    "operator_scope_ports": object(),
    "work_lifecycle_ports_factory": lambda: None,
    "verification_repository_bundle_factory": lambda bucket_id: None,
    "certificate_secret_backend_factory": lambda: None,
    "filing_action_ports_factory": lambda **_: None,
    "export_ports_factory": lambda **_: None,
    "amendment_action_ports_factory": lambda **_: None,
    "calculation_action_ports_factory": lambda **_: None,
    "attachment_store_factory": lambda _bucket_id: None,
    "receipt_repository_factory": lambda **_: None,
}

_KNOWN_AUTHORITIES = {
    "rename_work_unit",
    "discard_work_unit",
    "calculate_modelo_revision_from_bucket_aggregation_with_diagnostics",
    "verify_modelo_revision",
    "file_modelo_revision",
    "export_modelo_revision",
    "amend_modelo_revision",
    "apply_modelo_edit",
}

_M303_CLOCK = datetime(2025, 4, 1, 10, tzinfo=UTC)


class _LegacyCalculateRequestV1(CredentialFreeOperationRequest):
    """The prior journal-safe request shape used by a pending v1 invocation."""

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: str
    actor: str


class _LegacyCalculateExecutor:
    """Unreachable historical executor used only to reproduce its public contract."""

    async def execute(self, request: OperationRequest[_LegacyCalculateRequestV1], context: object) -> str | None:
        del request, context
        return None


def _definition_factories() -> dict[str, Any]:
    """Return every enrolment factory this module exports."""
    factories = {
        name: getattr(definitions_module, name)
        for name in definitions_module.__all__
        if name.startswith("build_") and name.endswith("_definition")
    }
    if not factories:
        pytest.fail("no enrolment factory is exported; the conformance denominator would be empty")
    return factories


def _build(factory: Any) -> OperationDefinition:
    """Invoke one factory with only the arguments it declares."""
    parameters = inspect.signature(factory).parameters
    missing = [name for name in parameters if name not in _FACTORY_ARGUMENTS]
    if missing:
        pytest.fail(f"{factory.__name__} needs arguments this conformance suite cannot supply: {missing}")
    built = factory(**{name: _FACTORY_ARGUMENTS[name] for name in parameters})
    assert isinstance(built, OperationDefinition)
    return built


def _definitions() -> dict[str, OperationDefinition]:
    return {name: _build(factory) for name, factory in _definition_factories().items()}


def test_the_denominator_covers_every_declared_definition_id() -> None:
    """Every declared operation id has an enrolment, and every enrolment an id."""
    declared = {
        getattr(definitions_module, name)
        for name in definitions_module.__all__
        if name.endswith("_OPERATION_DEFINITION_ID")
    }
    enrolled = {definition.definition_id for definition in _definitions().values()}

    assert declared, "no operation id is declared"
    assert declared == enrolled, f"declared and enrolled ids diverge: {declared ^ enrolled}"


def test_no_two_enrolments_redeclare_one_subject() -> None:
    """An id or a schema id claimed twice would make one enrolment unreachable."""
    definitions = list(_definitions().values())
    ids = [definition.definition_id for definition in definitions]

    assert len(set(ids)) == len(ids), f"duplicate definition ids: {ids}"

    registrations = [
        getattr(definitions_module, name)(definition)
        for name, definition in (
            (factory_name.replace("_definition", "_registration"), definition)
            for factory_name, definition in _definitions().items()
        )
        if hasattr(definitions_module, name)
    ]
    schema_ids = [binding.identity.schema_id for reg in registrations for binding in reg.schema_bindings]

    assert len(set(schema_ids)) == len(schema_ids), f"duplicate schema ids: {schema_ids}"


@pytest.mark.parametrize("factory_name", sorted(_definition_factories()))
def test_each_enrolment_is_recorded_and_stores_its_request_safely(factory_name: str) -> None:
    """Lifecycle work is durable; sensitive filings and edits use secure references."""
    definition = _build(_definition_factories()[factory_name])

    assert definition.capabilities.durability is OperationDurability.RECORDED
    if definition.definition_id in {
        definitions_module.MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
        definitions_module.MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    }:
        assert definition.capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
        assert definition.capabilities.sensitive_input is OperationSensitiveInputPolicy.SECURE_REFERENCE
        assert not issubclass(definition.request_type, CredentialFreeOperationRequest)
        return
    assert definition.capabilities.request_storage is OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL
    assert issubclass(definition.request_type, CredentialFreeOperationRequest)


def test_calculate_request_requires_each_ordinary_m303_fact_and_preserves_explicit_false() -> None:
    """Missing M303 declarations cannot be mistaken for a genuine false election."""
    values = {
        "work_unit_id": "a" * 64,
        "actor": "operator",
        "ordinary_m303_filing_evidence": {
            "joint_return_elected": False,
            "annual_volume_nonzero": False,
            "m303_exonerado_390_attachment_id": "b" * 64,
            "m303_exonerado_390_sha256": "b" * 64,
        },
    }

    request = definitions_module.ModeloWorkCalculateRequest.model_validate(values)

    assert request.ordinary_m303_filing_evidence is not None
    assert request.ordinary_m303_filing_evidence.joint_return_elected is False
    assert request.ordinary_m303_filing_evidence.annual_volume_nonzero is False
    for missing in ("joint_return_elected", "annual_volume_nonzero"):
        invalid = request.model_dump(mode="python")
        del invalid["ordinary_m303_filing_evidence"][missing]
        with pytest.raises(ValidationError):
            definitions_module.ModeloWorkCalculateRequest.model_validate(invalid)


def test_calculate_request_schema_v2_declares_the_secure_m303_contract() -> None:
    """The changed request cannot be replayed as the old journal-safe shape."""
    definition = _build(definitions_module.build_modelo_work_calculate_definition)
    registration = definitions_module.build_modelo_work_calculate_registration(definition)

    request_schema = registration.contract.request_schema
    assert request_schema.schema_id == "modelo.work.calculate.request"
    assert request_schema.schema_version == 2


def test_current_calculate_contract_refuses_a_pending_v1_invocation() -> None:
    """A recorded v1 request cannot resume under the secure v2 calculation contract."""
    current = _build(definitions_module.build_modelo_work_calculate_definition)
    current_registration = definitions_module.build_modelo_work_calculate_registration(current)
    legacy_definition = OperationDefinition(
        definition_id=current.definition_id,
        request_type=_LegacyCalculateRequestV1,
        result_type=current.result_type,
        executor_factory=OperationExecutorFactory(
            request_type=_LegacyCalculateRequestV1,
            executor_type=_LegacyCalculateExecutor,
            build=_LegacyCalculateExecutor,
        ),
        phase_codes=current.phase_codes,
        interaction_kinds=current.interaction_kinds,
        capabilities=current.capabilities.model_copy(
            update={
                "request_storage": OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
                "sensitive_input": OperationSensitiveInputPolicy.NONE,
            }
        ),
        reconciliation_policy=current.reconciliation_policy,
        permitted_frontends=current.permitted_frontends,
    )
    legacy_registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=legacy_definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.calculate.request",
            schema_version=1,
            model_type=_LegacyCalculateRequestV1,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.calculate.result",
            schema_version=1,
            model_type=definitions_module.ModeloWorkCalculatePublicResultV1,
        ),
        workspace_refresh_target_schema=next(
            binding
            for binding in current_registration.schema_bindings
            if binding.identity.schema_id.endswith(".workspace_refresh_target")
        ),
        workspace_refresh_adapter=definitions_module.resolve_modelo_work_unit_refresh_target,
    )
    supervisor = OperationSupervisor.__new__(OperationSupervisor)
    supervisor.registry = OperationRegistry(
        definitions=(current,),
        public_registrations=(current_registration,),
    )
    pending = OperationPersistedSnapshot(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=current.definition_id,
            subject_ref="b" * 64,
        ),
        definition_contract_digest=legacy_registration.contract.definition_contract_digest,
        request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
        request_reference="c" * 64,
        credential_free_request_json=_LegacyCalculateRequestV1(
            work_unit_id="b" * 64, actor="operator"
        ).model_dump_json(),
        revision=0,
        lifecycle=OperationLifecycle.CREATED,
        started_at=_M303_CLOCK,
        updated_at=_M303_CLOCK,
        execution_deadline=None,
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        cancellation_deferred=False,
    )

    with pytest.raises(ValueError, match="definition contract no longer reproduces"):
        supervisor._require_pinned_definition(pending)


@pytest.mark.parametrize("factory_name", sorted(_definition_factories()))
def test_each_enrolment_admits_an_uncertain_outcome(factory_name: str) -> None:
    """An interrupted lifecycle write must be reportable as unknown."""
    definition = _build(_definition_factories()[factory_name])

    assert OperationEffect.UNKNOWN in definition.capabilities.permitted_effects


@pytest.mark.parametrize("factory_name", sorted(_definition_factories()))
def test_each_executor_delegates_to_exactly_one_known_writer(factory_name: str) -> None:
    """Every enrolment supervises one authority and invents no second path."""
    definition = _build(_definition_factories()[factory_name])
    source = inspect.getsource(definition.executor_factory.executor_type)
    tree = ast.parse(textwrap.dedent(source))
    # A writer is delegated to either by calling it or by handing it to a
    # deferred invoker such as ``functools.partial``.
    called = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for target in (node.func, *node.args)
        if isinstance(target, ast.Name)
    }
    writers = called & _KNOWN_AUTHORITIES

    assert len(writers) == 1, f"{factory_name} delegates to {writers or 'no known writer'}"


@pytest.mark.parametrize("factory_name", sorted(_definition_factories()))
def test_no_executor_opens_its_own_repository(factory_name: str) -> None:
    """The writer owns the atomic set; an enrolment that reached past it would tear it."""
    definition = _build(_definition_factories()[factory_name])
    source = inspect.getsource(definition.executor_factory.executor_type)

    for forbidden in ("Repository(", "upsert_", "BucketEventHistory"):
        assert forbidden not in source, f"{factory_name} opens a write path around its writer: {forbidden}"


@pytest.mark.parametrize("factory_name", sorted(_definition_factories()))
def test_no_result_receipt_carries_operand_material(factory_name: str) -> None:
    """A result names and fingerprints; it never ships the material itself."""
    definition = _build(_definition_factories()[factory_name])
    result_type = definition.result_type

    assert result_type is not None, f"{factory_name} declares no result receipt"
    for field in result_type.model_fields:
        for carrier in ("bytes", "content", "payload", "document", "secret"):
            assert carrier not in field.lower(), f"{factory_name} result carries material: {field}"


@pytest.mark.parametrize("factory_name", sorted(_definition_factories()))
def test_no_executor_reaches_a_remote_surface(factory_name: str) -> None:
    """Live submission is prohibited, so no enrolment may transmit anywhere."""
    definition = _build(_definition_factories()[factory_name])
    source = inspect.getsource(definition.executor_factory.executor_type)
    tree = ast.parse(textwrap.dedent(source))
    reached = (
        {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        | {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        | {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    )

    for forbidden in ("submit", "httpx", "requests", "presentar", "upload"):
        assert not any(forbidden in name.lower() for name in reached), (
            f"{factory_name} reaches a remote surface: {forbidden}"
        )
