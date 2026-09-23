"""Conformance over every enrolled modelo lifecycle operation.

The denominator here is DERIVED from the definitions module, never listed. A
hand-maintained list of enrolments to check cannot report the enrolment nobody
added to it, so a seventh operation landing tomorrow is covered by every
assertion below without anyone remembering to extend this file.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import textwrap
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    seed_modelo_ready_profile_record,
)
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....core.errors.hierarchy import CadrumoError
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.operations import OperationDurability, OperationEffect, OperationLifecycle
from ....core.period import Period
from ....domain.attachments.enums import AttachmentKind, AttachmentSource
from ....domain.attachments.m303_filing_evidence import (
    M303Exonerado390ApplicabilityAssertion,
    M303Exonerado390ApplicabilityAttestation,
    M303Exonerado390ApplicabilityProfileWitness,
)
from ....domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from ....domain.buckets.event import BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....domain.user_profile.values import UserProfileFact
from ...operations.capabilities import OperationRequestStoragePolicy, OperationSensitiveInputPolicy
from ...operations.models import CredentialFreeOperationRequest, OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.persistence.journal import OperationPersistedSnapshot
from ...operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from ...operations.supervisor import OperationSupervisor
from ...user_profile.profile_record_repository import ProfileRecordRepository
from .. import calculation_actions as calculation_actions_module
from .. import operation_definitions as definitions_module
from ..action_errors import (
    M303ApplicabilityAttestationUnadmissibleError,
    M303FilingEvidenceError,
    ModeloProfileReadinessError,
)
from ..calculation_action_ports import CalculationActionPorts, CalculationActionPortsFactory
from ..m303_exonerado_390_applicability_attestation import (
    M303Exonerado390ApplicabilityAttestationRequest,
    admit_m303_exonerado_390_applicability_attestation,
)

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

_M303_BUCKET_ID = "3a1f0b2c-4d5e-4f60-8a71-92b3c4d5e6f7"
_M303_PERIOD = Period.from_year_and_code(2025, "1T")
_M303_CLOCK = datetime(2025, 4, 1, 10, tzinfo=UTC)


class _CalculateEvents:
    """Minimal executor event recorder; evidence stays in the typed writer call."""

    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _CalculateContext:
    """Narrow executor context containing the real pinned authority."""

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self.authority_operation = operation
        self.events = _CalculateEvents()


def _calculate_context(operation: PinnedAuthorityOperation) -> OperationExecutorContext:
    """Project the exercised executor fields onto the full owner context protocol."""
    return cast(OperationExecutorContext, _CalculateContext(operation))


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


def _m303_work_unit(
    operation: PinnedAuthorityOperation,
    *,
    filing_year: int = 2025,
    period: Period = _M303_PERIOD,
    modelo: str = "303",
    bucket_id: str = _M303_BUCKET_ID,
) -> WorkUnit:
    snapshot = operation.snapshot(modelo, filing_year=filing_year, period=period.registry_token)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=snapshot.revision.id,
        name=f"{modelo}-{filing_year}-{period.registry_token}",
        created_at=_M303_CLOCK,
        updated_at=_M303_CLOCK,
    )


def _work_unit_read_ports(ports: object) -> CalculationActionPorts:
    """Present a work-unit-only stub as the bundle; the executor reads nothing else before admission."""
    return cast(CalculationActionPorts, ports)


def _calculation_ports_factory(work_unit: WorkUnit) -> CalculationActionPortsFactory:
    """Return the executor's exact work-unit read capability and no writer."""

    repository = SimpleNamespace(
        bucket_id=work_unit.bucket_id,
        load=lambda: WorkUnitCatalogue(work_units={work_unit.work_unit_id: work_unit}),
    )

    def build(
        *, bucket_id: str, operation: PinnedAuthorityOperation, profile_record: object | None = None
    ) -> CalculationActionPorts:
        del bucket_id, operation, profile_record
        return _work_unit_read_ports(SimpleNamespace(work_unit_repository=repository))

    return build


def _calculate_request(
    work_unit: WorkUnit,
    evidence: definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1 | None,
) -> OperationRequest[definitions_module.ModeloWorkCalculateRequest]:
    return OperationRequest(
        definition_id=definitions_module.MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        subject_ref=work_unit.work_unit_id,
        payload=definitions_module.ModeloWorkCalculateRequest(
            work_unit_id=work_unit.work_unit_id,
            actor="operator",
            ordinary_m303_filing_evidence=evidence,
        ),
    )


def _m303_attestation_input(
    *,
    operation: PinnedAuthorityOperation,
    store: AttachmentStore,
) -> definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1:
    admission = admit_m303_exonerado_390_applicability_attestation(
        bucket_id=_M303_BUCKET_ID,
        request=M303Exonerado390ApplicabilityAttestationRequest(
            filing_year=2025,
            period=_M303_PERIOD,
            asserted_value=M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE,
            observed_at=datetime(2025, 3, 31, 12, tzinfo=UTC),
        ),
        actor="operator",
        operation=operation,
        store=store,
        clock=lambda: _M303_CLOCK,
    )
    return definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1(
        joint_return_elected=False,
        annual_volume_nonzero=False,
        m303_exonerado_390_attachment_id=admission.attachment_id,
        m303_exonerado_390_sha256=admission.sha256,
    )


def _refuse_calculation_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the canonical revision writer unreachable; every refusal must precede it."""

    def calculate(*_args: object, **_kwargs: object) -> object:
        pytest.fail("a refused M303 evidence request must not enter revision calculation")

    monkeypatch.setattr(
        calculation_actions_module,
        "calculate_modelo_revision_from_bucket_aggregation_with_diagnostics",
        calculate,
    )


def _crafted_attestation(
    store: AttachmentStore,
    profiles: ProfileRecordRepository,
    *,
    value: M303Exonerado390ApplicabilityAssertion = M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE,
    kind: AttachmentKind = AttachmentKind.M303_EXONERADO_390_APPLICABILITY_ATTESTATION,
) -> definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1:
    """Ingest canonical attestation bytes under a deliberately chosen kind or assertion."""
    payload = M303Exonerado390ApplicabilityAttestation(
        schema_version=1,
        role="m303_exonerado_390_applicability",
        asserted_value=value,
        filing_year=2025,
        period=_M303_PERIOD,
        observed_at=datetime(2025, 3, 31, 12, tzinfo=UTC),
        profile_witness=M303Exonerado390ApplicabilityProfileWitness.from_profile_record(profiles.load(_M303_BUCKET_ID)),
    ).canonical_json_bytes()
    attachment = add_attachment(
        store,
        content=AttachmentBytesContent(data=payload),
        request=AttachmentIngestionRequest(
            kind=kind,
            source=AttachmentSource.INLINE,
            source_reference="m303-exonerado-390-applicability:2025:1T",
            mime_type="application/vnd.cadrumo.m303-exonerado-390-applicability+json",
            captured_at=_M303_CLOCK,
            bucket_id=_M303_BUCKET_ID,
            captured_by="operator",
            source_command="test:crafted-attestation",
        ),
    )
    return definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1(
        joint_return_elected=False,
        annual_volume_nonzero=False,
        m303_exonerado_390_attachment_id=attachment.attachment_id,
        m303_exonerado_390_sha256=attachment.sha256,
    )


def _unknown_digest(
    _store: AttachmentStore, _profiles: ProfileRecordRepository, _operation: PinnedAuthorityOperation
) -> definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1:
    return definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1(
        joint_return_elected=False,
        annual_volume_nonzero=False,
        m303_exonerado_390_attachment_id="e" * 64,
        m303_exonerado_390_sha256="e" * 64,
    )


def _wrong_role(
    store: AttachmentStore, profiles: ProfileRecordRepository, _operation: PinnedAuthorityOperation
) -> definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1:
    return _crafted_attestation(store, profiles, kind=AttachmentKind.METADATA_BLOB)


def _wrong_period(
    store: AttachmentStore, _profiles: ProfileRecordRepository, operation: PinnedAuthorityOperation
) -> definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1:
    admission = admit_m303_exonerado_390_applicability_attestation(
        bucket_id=_M303_BUCKET_ID,
        request=M303Exonerado390ApplicabilityAttestationRequest(
            filing_year=2025,
            period=Period.from_year_and_code(2025, "2T"),
            asserted_value=M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE,
            observed_at=datetime(2025, 6, 30, 12, tzinfo=UTC),
        ),
        actor="operator",
        operation=operation,
        store=store,
        clock=lambda: datetime(2025, 7, 1, 10, tzinfo=UTC),
    )
    return definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1(
        joint_return_elected=False,
        annual_volume_nonzero=False,
        m303_exonerado_390_attachment_id=admission.attachment_id,
        m303_exonerado_390_sha256=admission.sha256,
    )


def _stale_profile_witness(
    store: AttachmentStore, profiles: ProfileRecordRepository, operation: PinnedAuthorityOperation
) -> definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1:
    evidence = _m303_attestation_input(operation=operation, store=store)
    current = profiles.load(_M303_BUCKET_ID)
    profiles.apply_fact_changes(
        _M303_BUCKET_ID,
        facts=tuple(
            UserProfileFact(path=fact.path, value="Ana Maria") if fact.path == "identity.name" else fact
            for fact in current.facts
        ),
        expected_revision=current.record_revision,
        expected_content_digest=current.content_digest,
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
        event_payload={},
        now=current.updated_at + timedelta(minutes=1),
    )
    return evidence


def _conflicting_assertion(
    store: AttachmentStore, profiles: ProfileRecordRepository, operation: PinnedAuthorityOperation
) -> definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1:
    evidence = _m303_attestation_input(operation=operation, store=store)
    _crafted_attestation(store, profiles, value=M303Exonerado390ApplicabilityAssertion.APPLICABLE)
    return evidence


_EvidenceBuilder = Callable[
    [AttachmentStore, ProfileRecordRepository, PinnedAuthorityOperation],
    definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1,
]

_UNADMISSIBLE_EVIDENCE: dict[str, tuple[_EvidenceBuilder, type[CadrumoError]]] = {
    "unknown_digest": (_unknown_digest, M303ApplicabilityAttestationUnadmissibleError),
    "wrong_role": (_wrong_role, M303ApplicabilityAttestationUnadmissibleError),
    "wrong_period": (_wrong_period, M303ApplicabilityAttestationUnadmissibleError),
    "stale_profile_witness": (_stale_profile_witness, M303ApplicabilityAttestationUnadmissibleError),
    "conflicting_assertion": (_conflicting_assertion, M303ApplicabilityAttestationUnadmissibleError),
}


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


def test_calculate_executor_authors_explicit_false_m303_evidence_before_delegating(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The four supplied M303 inputs reach the canonical writer as typed derived evidence."""
    work_unit = _m303_work_unit(operation)
    captured: dict[str, object] = {}

    def calculate(
        work_unit_id: str,
        *,
        ports: object,
        actor: str,
        filing_instance_evidence: object,
    ) -> object:
        captured.update(
            work_unit_id=work_unit_id,
            ports=ports,
            actor=actor,
            filing_instance_evidence=filing_instance_evidence,
        )
        return SimpleNamespace(revision=SimpleNamespace(calculation_revision_id="d" * 64))

    monkeypatch.setattr(
        calculation_actions_module,
        "calculate_modelo_revision_from_bucket_aggregation_with_diagnostics",
        calculate,
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M303_BUCKET_ID):
        seed_modelo_ready_profile_record(_M303_BUCKET_ID, clock=_M303_CLOCK)
        with bound_test_profile_record(_M303_BUCKET_ID):
            store = AttachmentStore()
            evidence_input = _m303_attestation_input(operation=operation, store=store)
            executor = definitions_module.ModeloWorkCalculateExecutor(
                calculation_action_ports_factory=_calculation_ports_factory(work_unit),
                attachment_store_factory=lambda bucket_id: store,
            )

            result = asyncio.run(
                executor.execute(_calculate_request(work_unit, evidence_input), _calculate_context(operation))
            )

    assert result == "d" * 64
    assert captured["work_unit_id"] == work_unit.work_unit_id
    assert captured["actor"] == "operator"
    authored = cast(FilingInstanceEvidence, captured["filing_instance_evidence"])
    assert authored.m303.period == _M303_PERIOD
    assert authored.m303.joint_return_elected is False
    assert authored.m303.annual_volume_nonzero is False


def test_calculate_executor_refuses_missing_m303_evidence_without_entering_calculation(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing ordinary envelope is a refusal, never an empty revision."""
    _refuse_calculation_entry(monkeypatch)
    work_unit = _m303_work_unit(operation)
    executor = definitions_module.ModeloWorkCalculateExecutor(
        calculation_action_ports_factory=_calculation_ports_factory(work_unit),
        attachment_store_factory=lambda _bucket_id: pytest.fail(
            "missing M303 evidence must not open attachment custody"
        ),
    )
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M303_BUCKET_ID),
        pytest.raises(M303FilingEvidenceError) as raised,
    ):
        asyncio.run(executor.execute(_calculate_request(work_unit, None), _calculate_context(operation)))

    assert raised.value.precondition_failure is not None
    assert raised.value.precondition_failure.scenario_id == "modelo.work.calculate.m303_filing_evidence.missing"


def test_calculate_executor_refuses_mismatched_m303_attachment_pair_before_calculation(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The split public attachment coordinates must still name one admitted object."""
    _refuse_calculation_entry(monkeypatch)
    work_unit = _m303_work_unit(operation)
    evidence_input = definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1(
        joint_return_elected=False,
        annual_volume_nonzero=False,
        m303_exonerado_390_attachment_id="b" * 64,
        m303_exonerado_390_sha256="c" * 64,
    )
    executor = definitions_module.ModeloWorkCalculateExecutor(
        calculation_action_ports_factory=_calculation_ports_factory(work_unit),
        attachment_store_factory=lambda _bucket_id: pytest.fail("mismatched pair must not open attachment custody"),
    )
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M303_BUCKET_ID),
        pytest.raises(M303ApplicabilityAttestationUnadmissibleError),
    ):
        asyncio.run(executor.execute(_calculate_request(work_unit, evidence_input), _calculate_context(operation)))


@pytest.mark.parametrize("case", sorted(_UNADMISSIBLE_EVIDENCE))
def test_calculate_executor_refuses_unadmissible_attestations_before_any_revision(
    case: str,
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Custody, role, coordinate, freshness and conflict defects refuse before the revision writer."""
    build_evidence, expected_error = _UNADMISSIBLE_EVIDENCE[case]
    work_unit = _m303_work_unit(operation)
    _refuse_calculation_entry(monkeypatch)
    context = _CalculateContext(operation)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M303_BUCKET_ID):
        seed_modelo_ready_profile_record(_M303_BUCKET_ID, clock=_M303_CLOCK)
        with bound_test_profile_record(_M303_BUCKET_ID) as profiles:
            store = AttachmentStore()
            evidence_input = build_evidence(store, profiles, operation)
            executor = definitions_module.ModeloWorkCalculateExecutor(
                calculation_action_ports_factory=_calculation_ports_factory(work_unit),
                attachment_store_factory=lambda _bucket_id: store,
            )
            with pytest.raises(expected_error):
                asyncio.run(
                    executor.execute(
                        _calculate_request(work_unit, evidence_input),
                        cast(OperationExecutorContext, context),
                    )
                )

    assert OperationEffect.UPDATED not in context.events.effects


def test_calculate_executor_refuses_evidence_admitted_under_another_profile_bucket(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Custody is opened for the work unit's own bucket; another bucket's admitted attestation never answers it."""
    foreign_bucket_id = "9b2e0c1d-5f6a-4b70-9c81-a2b3c4d5e6f8"
    work_unit = _m303_work_unit(operation, bucket_id=foreign_bucket_id)
    _refuse_calculation_entry(monkeypatch)
    opened: list[str] = []
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M303_BUCKET_ID):
        seed_modelo_ready_profile_record(_M303_BUCKET_ID, clock=_M303_CLOCK)
        with bound_test_profile_record(_M303_BUCKET_ID):
            store = AttachmentStore()
            evidence_input = _m303_attestation_input(operation=operation, store=store)

            def open_store(bucket_id: str) -> AttachmentStore:
                opened.append(bucket_id)
                return store

            executor = definitions_module.ModeloWorkCalculateExecutor(
                calculation_action_ports_factory=_calculation_ports_factory(work_unit),
                attachment_store_factory=open_store,
            )
            with pytest.raises(ModeloProfileReadinessError):
                asyncio.run(
                    executor.execute(_calculate_request(work_unit, evidence_input), _calculate_context(operation))
                )

    assert opened == [foreign_bucket_id]


def test_calculate_executor_leaves_other_modelo_calculation_without_m303_evidence(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-M303 calculation keeps its evidence-free path and never opens attachment custody."""
    work_unit = _m303_work_unit(operation, modelo="131")
    captured: dict[str, object] = {}

    def calculate(work_unit_id: str, *, ports: object, actor: str, filing_instance_evidence: object) -> object:
        del ports
        captured.update(work_unit_id=work_unit_id, actor=actor, filing_instance_evidence=filing_instance_evidence)
        return SimpleNamespace(revision=SimpleNamespace(calculation_revision_id="f" * 64))

    monkeypatch.setattr(
        calculation_actions_module,
        "calculate_modelo_revision_from_bucket_aggregation_with_diagnostics",
        calculate,
    )
    executor = definitions_module.ModeloWorkCalculateExecutor(
        calculation_action_ports_factory=_calculation_ports_factory(work_unit),
        attachment_store_factory=lambda _bucket_id: pytest.fail(
            "non-M303 calculation must not open attachment custody"
        ),
    )
    context = _CalculateContext(operation)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M303_BUCKET_ID):
        result = asyncio.run(
            executor.execute(_calculate_request(work_unit, None), cast(OperationExecutorContext, context))
        )

    assert result == "f" * 64
    assert captured == {"work_unit_id": work_unit.work_unit_id, "actor": "operator", "filing_instance_evidence": None}
    assert context.events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]


def test_calculate_executor_refuses_ordinary_evidence_outside_its_filing_context(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The executor derives axes from work; a monthly work unit cannot select the quarterly evidence branch."""
    _refuse_calculation_entry(monkeypatch)
    work_unit = _m303_work_unit(
        operation,
        filing_year=2025,
        period=Period.from_year_and_code(2025, "01"),
    )
    evidence_input = definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1(
        joint_return_elected=False,
        annual_volume_nonzero=False,
        m303_exonerado_390_attachment_id="b" * 64,
        m303_exonerado_390_sha256="b" * 64,
    )
    executor = definitions_module.ModeloWorkCalculateExecutor(
        calculation_action_ports_factory=_calculation_ports_factory(work_unit),
        attachment_store_factory=lambda _bucket_id: AttachmentStore(),
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M303_BUCKET_ID), pytest.raises(M303FilingEvidenceError):
        asyncio.run(executor.execute(_calculate_request(work_unit, evidence_input), _calculate_context(operation)))


def test_calculate_executor_refuses_m303_evidence_for_another_modelo_before_calculation(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ordinary M303 envelope has no meaning for another modelo's revision."""
    _refuse_calculation_entry(monkeypatch)
    work_unit = _m303_work_unit(operation, modelo="131")
    evidence_input = definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV1(
        joint_return_elected=False,
        annual_volume_nonzero=False,
        m303_exonerado_390_attachment_id="b" * 64,
        m303_exonerado_390_sha256="b" * 64,
    )
    executor = definitions_module.ModeloWorkCalculateExecutor(
        calculation_action_ports_factory=_calculation_ports_factory(work_unit),
        attachment_store_factory=lambda _bucket_id: pytest.fail("non-M303 evidence must not open attachment custody"),
    )
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M303_BUCKET_ID),
        pytest.raises(M303FilingEvidenceError) as raised,
    ):
        asyncio.run(executor.execute(_calculate_request(work_unit, evidence_input), _calculate_context(operation)))

    assert raised.value.precondition_failure is not None
    assert (
        raised.value.precondition_failure.scenario_id == "modelo.work.calculate.m303_filing_evidence.unsupported_modelo"
    )


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
