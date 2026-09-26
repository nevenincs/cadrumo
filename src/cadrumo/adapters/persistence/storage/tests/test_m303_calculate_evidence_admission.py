"""Calculate-operation admission of ordinary Modelo 303 evidence through real secure custody.

The executor authors filing evidence from the operator's answers and an attestation held in
encrypted attachment custody, so these checks run against the persistence adapters rather
than in the application package.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    seed_modelo_ready_profile_record,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo import calculation_actions as calculation_actions_module
from cadrumo.application.modelo import operation_definitions as definitions_module
from cadrumo.application.modelo.action_errors import (
    M303Exonerado390AttestationUnadmissibleError,
    M303FilingEvidenceError,
    ModeloProfileReadinessError,
)
from cadrumo.application.modelo.calculation_action_ports import CalculationActionPorts, CalculationActionPortsFactory
from cadrumo.application.modelo.m303_exonerado_390_applicability_attestation import (
    M303Exonerado390ApplicabilityAttestationRequest,
    admit_m303_exonerado_390_applicability_attestation,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.operations import OperationEffect
from cadrumo.core.period import Period
from cadrumo.domain.attachments.enums import AttachmentKind, AttachmentSource
from cadrumo.domain.attachments.m303_filing_evidence import (
    M303Exonerado390ApplicabilityAssertion,
    M303Exonerado390ApplicabilityAttestation,
    M303Exonerado390ApplicabilityProfileWitness,
)
from cadrumo.domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
from cadrumo.domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from cadrumo.domain.user_profile.values import UserProfileFact

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_M303_BUCKET_ID = "3a1f0b2c-4d5e-4f60-8a71-92b3c4d5e6f7"
#: DP30301 Nota 4 asks the Modelo 390 exemption only in the last settlement period, so the attestation cases use 4T.
_M303_PERIOD = Period.from_year_and_code(2025, "4T")
_M303_CLOCK = datetime(2026, 1, 2, 10, tzinfo=UTC)
_M303_OBSERVED_AT = datetime(2025, 12, 31, 12, tzinfo=UTC)
_OUTSIDE_LAST_PERIOD = "modelo.work.calculate.m303_filing_evidence.exonerado_390_attestation_outside_last_period"


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
    evidence: definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2 | None,
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
) -> definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2:
    admission = admit_m303_exonerado_390_applicability_attestation(
        bucket_id=_M303_BUCKET_ID,
        request=M303Exonerado390ApplicabilityAttestationRequest(
            filing_year=2025,
            period=_M303_PERIOD,
            asserted_value=M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE,
            observed_at=_M303_OBSERVED_AT,
        ),
        actor="operator",
        operation=operation,
        store=store,
        clock=lambda: _M303_CLOCK,
    )
    return definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
        joint_return_elected=False,
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
) -> definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2:
    """Ingest canonical attestation bytes under a deliberately chosen kind or assertion."""
    payload = M303Exonerado390ApplicabilityAttestation(
        schema_version=1,
        role="m303_exonerado_390_applicability",
        asserted_value=value,
        filing_year=2025,
        period=_M303_PERIOD,
        observed_at=_M303_OBSERVED_AT,
        profile_witness=M303Exonerado390ApplicabilityProfileWitness.from_profile_record(profiles.load(_M303_BUCKET_ID)),
    ).canonical_json_bytes()
    attachment = add_attachment(
        store,
        content=AttachmentBytesContent(data=payload),
        request=AttachmentIngestionRequest(
            kind=kind,
            source=AttachmentSource.INLINE,
            source_reference="m303-exonerado-390-applicability:2025:4T",
            mime_type="application/vnd.cadrumo.m303-exonerado-390-applicability+json",
            captured_at=_M303_CLOCK,
            bucket_id=_M303_BUCKET_ID,
            captured_by="operator",
            source_command="test:crafted-attestation",
        ),
    )
    return definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
        joint_return_elected=False,
        m303_exonerado_390_attachment_id=attachment.attachment_id,
        m303_exonerado_390_sha256=attachment.sha256,
    )


def _unknown_digest(
    _store: AttachmentStore, _profiles: ProfileRecordRepository, _operation: PinnedAuthorityOperation
) -> definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2:
    return definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
        joint_return_elected=False,
        m303_exonerado_390_attachment_id="e" * 64,
        m303_exonerado_390_sha256="e" * 64,
    )


def _wrong_role(
    store: AttachmentStore, profiles: ProfileRecordRepository, _operation: PinnedAuthorityOperation
) -> definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2:
    return _crafted_attestation(store, profiles, kind=AttachmentKind.METADATA_BLOB)


def _wrong_period(
    store: AttachmentStore, _profiles: ProfileRecordRepository, operation: PinnedAuthorityOperation
) -> definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2:
    admission = admit_m303_exonerado_390_applicability_attestation(
        bucket_id=_M303_BUCKET_ID,
        request=M303Exonerado390ApplicabilityAttestationRequest(
            filing_year=2025,
            period=Period.from_year_and_code(2025, "12"),
            asserted_value=M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE,
            observed_at=_M303_OBSERVED_AT,
        ),
        actor="operator",
        operation=operation,
        store=store,
        clock=lambda: _M303_CLOCK,
    )
    return definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
        joint_return_elected=False,
        m303_exonerado_390_attachment_id=admission.attachment_id,
        m303_exonerado_390_sha256=admission.sha256,
    )


def _stale_profile_witness(
    store: AttachmentStore, profiles: ProfileRecordRepository, operation: PinnedAuthorityOperation
) -> definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2:
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
) -> definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2:
    evidence = _m303_attestation_input(operation=operation, store=store)
    _crafted_attestation(store, profiles, value=M303Exonerado390ApplicabilityAssertion.APPLICABLE)
    return evidence


_EvidenceBuilder = Callable[
    [AttachmentStore, ProfileRecordRepository, PinnedAuthorityOperation],
    definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2,
]

_UNADMISSIBLE_EVIDENCE: dict[str, tuple[_EvidenceBuilder, type[CadrumoError]]] = {
    "unknown_digest": (_unknown_digest, M303Exonerado390AttestationUnadmissibleError),
    "wrong_role": (_wrong_role, M303Exonerado390AttestationUnadmissibleError),
    "wrong_period": (_wrong_period, M303Exonerado390AttestationUnadmissibleError),
    "stale_profile_witness": (_stale_profile_witness, M303Exonerado390AttestationUnadmissibleError),
    "conflicting_assertion": (_conflicting_assertion, M303Exonerado390AttestationUnadmissibleError),
}


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
    assert authored.m303.annual_volume_nonzero is None
    assert authored.m303.exonerado_390 is not None


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
    evidence_input = definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
        joint_return_elected=False,
        m303_exonerado_390_attachment_id="b" * 64,
        m303_exonerado_390_sha256="c" * 64,
    )
    executor = definitions_module.ModeloWorkCalculateExecutor(
        calculation_action_ports_factory=_calculation_ports_factory(work_unit),
        attachment_store_factory=lambda _bucket_id: pytest.fail("mismatched pair must not open attachment custody"),
    )
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M303_BUCKET_ID),
        pytest.raises(M303Exonerado390AttestationUnadmissibleError),
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
    """The executor derives the period from the work unit; a month before 12 refuses a supplied attestation."""
    _refuse_calculation_entry(monkeypatch)
    work_unit = _m303_work_unit(
        operation,
        filing_year=2025,
        period=Period.from_year_and_code(2025, "01"),
    )
    evidence_input = definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
        joint_return_elected=False,
        m303_exonerado_390_attachment_id="b" * 64,
        m303_exonerado_390_sha256="b" * 64,
    )
    executor = definitions_module.ModeloWorkCalculateExecutor(
        calculation_action_ports_factory=_calculation_ports_factory(work_unit),
        attachment_store_factory=lambda _bucket_id: AttachmentStore(),
    )
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M303_BUCKET_ID),
        pytest.raises(M303FilingEvidenceError) as raised,
    ):
        asyncio.run(executor.execute(_calculate_request(work_unit, evidence_input), _calculate_context(operation)))

    assert raised.value.precondition_failure is not None
    assert raised.value.precondition_failure.scenario_id == _OUTSIDE_LAST_PERIOD


def test_calculate_executor_refuses_m303_evidence_for_another_modelo_before_calculation(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ordinary M303 envelope has no meaning for another modelo's revision."""
    _refuse_calculation_entry(monkeypatch)
    work_unit = _m303_work_unit(operation, modelo="131")
    evidence_input = definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
        joint_return_elected=False,
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


def test_calculate_executor_authors_a_period_before_the_last_from_the_joint_return_answer_alone(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """1T asks only the joint-return election; the executor authors it without opening attachment custody."""
    first_quarter = Period.from_year_and_code(2025, "1T")
    work_unit = _m303_work_unit(operation, period=first_quarter)
    captured: dict[str, object] = {}

    def calculate(work_unit_id: str, *, ports: object, actor: str, filing_instance_evidence: object) -> object:
        del work_unit_id, ports, actor
        captured["filing_instance_evidence"] = filing_instance_evidence
        return SimpleNamespace(revision=SimpleNamespace(calculation_revision_id="d" * 64))

    monkeypatch.setattr(
        calculation_actions_module,
        "calculate_modelo_revision_from_bucket_aggregation_with_diagnostics",
        calculate,
    )
    executor = definitions_module.ModeloWorkCalculateExecutor(
        calculation_action_ports_factory=_calculation_ports_factory(work_unit),
        attachment_store_factory=lambda _bucket_id: AttachmentStore(),
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M303_BUCKET_ID):
        seed_modelo_ready_profile_record(_M303_BUCKET_ID, clock=_M303_CLOCK)
        with bound_test_profile_record(_M303_BUCKET_ID):
            result = asyncio.run(
                executor.execute(
                    _calculate_request(
                        work_unit,
                        definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(joint_return_elected=True),
                    ),
                    _calculate_context(operation),
                )
            )

    assert result == "d" * 64
    authored = cast(FilingInstanceEvidence, captured["filing_instance_evidence"])
    assert authored.m303.period == first_quarter
    assert authored.m303.joint_return_elected is True
    assert authored.m303.exonerado_390 is None
    assert authored.m303.annual_volume_nonzero is None


def test_calculate_executor_refuses_the_last_period_without_an_attestation(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """4T asks the exemption, so the joint-return answer alone is refused before the revision writer."""
    _refuse_calculation_entry(monkeypatch)
    work_unit = _m303_work_unit(operation)
    executor = definitions_module.ModeloWorkCalculateExecutor(
        calculation_action_ports_factory=_calculation_ports_factory(work_unit),
        attachment_store_factory=lambda _bucket_id: AttachmentStore(),
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M303_BUCKET_ID):
        seed_modelo_ready_profile_record(_M303_BUCKET_ID, clock=_M303_CLOCK)
        with bound_test_profile_record(_M303_BUCKET_ID), pytest.raises(M303FilingEvidenceError) as raised:
            asyncio.run(
                executor.execute(
                    _calculate_request(
                        work_unit,
                        definitions_module.ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(joint_return_elected=False),
                    ),
                    _calculate_context(operation),
                )
            )

    assert raised.value.precondition_failure is not None
    assert raised.value.precondition_failure.scenario_id == "modelo.work.calculate.m303_filing_evidence.missing"
