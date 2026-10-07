"""Native profile-worker acceptance for the registered Modelo 145 commands."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import override

import pytest
from click.testing import Result

from ....adapters.outbound.aeat.export.registry_record_renderer import RegistryFixedWidthRecordRenderer
from ....adapters.persistence.profile.m145_communication_records import build_m145_communication_records_ports
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.modelo.m145_communication_records import (
    M145CommunicationRecord,
    export_m145_communication_record,
    read_m145_communication_record,
    validate_m145_communication_record,
)
from ....application.user_profile.login_session import authenticate_profile_for_invocation, resolve_login_target
from ....core.config import override_settings
from ....core.redaction.rules import redact_structured_for_cli_output
from ....core.secure_object_write import SecureObjectWrite
from ....core.type_guards import is_str_keyed_dict
from ....domain.buckets.event import BucketEvent, BucketEventHistoryCatalogue, BucketEventObjectType, BucketEventType
from ....domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from .._modelo_payloads_m145 import (
    M145CommunicationExportResultPayload,
    M145CommunicationRecordPayload,
    M145CommunicationRecordResult,
    M145CommunicationValidationResultPayload,
)
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Modelo 145",
    "activities.description": "design",
    "censo.activity_start_date": "2025-01-01",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}
_FIELD_VALUES = {
    "perceptor.nif": "12345678Z",
    "perceptor.primer-apellido": "Garcia",
    "perceptor.segundo-apellido": "Lopez",
    "perceptor.nombre": "Ana",
    "perceptor.anio-nacimiento": "1981",
}
_ACTOR = "native-m145-operator"


def _invoke(profile: NativeCliProfileFixture, *command: str) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_cached_cli(
            (
                "--language",
                "en",
                "--format",
                "json",
                "--profile",
                profile.label,
                "--profile-secrets-stdin",
                *command,
            ),
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
    assert profile.passphrase not in result.output
    return result


def _reauthenticate(
    profile: NativeCliProfileFixture,
    *,
    authority_operation: PinnedAuthorityOperation,
) -> str:
    assert profile.label is not None
    close_active_bucket_session()
    login = authenticate_profile_for_invocation(
        name=profile.label,
        passphrase_callback=lambda: profile.passphrase,
        profile_decode_context=authority_operation.profile_decode_context(),
    )
    return str(login.bucket_id)


def _event_delta(
    before: BucketEventHistoryCatalogue,
    after: BucketEventHistoryCatalogue,
    *,
    bucket_id: str,
    expected_mutation: BucketEventType | None,
) -> BucketEvent | None:
    assert all(after.events.get(key) == event for key, event in before.events.items())
    added = tuple(event for key, event in after.events.items() if key not in before.events)
    activations = tuple(event for event in added if event.event_type is BucketEventType.PROFILE_ACTIVATED)
    mutations = tuple(event for event in added if event.event_type is expected_mutation) if expected_mutation else ()
    expected_count = 2 if expected_mutation is not None else 1
    assert len(added) == expected_count
    assert len(activations) == 1
    activation = activations[0]
    assert activation.bucket_id == bucket_id
    assert activation.event_type is BucketEventType.PROFILE_ACTIVATED
    assert activation.object_type is BucketEventObjectType.PROFILE
    assert activation.object_id == bucket_id
    assert activation.actor == "profile-login"
    assert activation.payload_version == 1
    assert dict(activation.payload) == {"active_profile": bucket_id}
    if expected_mutation is None:
        return None
    assert len(mutations) == 1
    return mutations[0]


def _assert_communication_event(
    event: BucketEvent,
    *,
    bucket_id: str,
    record: M145CommunicationRecord,
    event_type: BucketEventType,
    actor: str = _ACTOR,
    extra: dict[str, str] | None = None,
) -> None:
    assert event.bucket_id == bucket_id
    assert event.event_type is event_type
    assert event.object_type is BucketEventObjectType.COMMUNICATION_RECORD
    assert event.object_id == record.communication_record_id
    assert event.actor == actor
    assert event.payload_version == 2
    payload = {
        "communication_record_id": record.communication_record_id,
        "modelo": record.modelo,
        "communication_year": str(record.communication_year),
        "period": record.period_token.value,
        "revision_id": record.revision_id,
        "state": record.state.value,
    }
    if extra is not None:
        payload.update(extra)
    assert dict(event.payload) == payload


def _redacted_cli_payload(payload: object) -> dict[str, object]:
    redacted = redact_structured_for_cli_output(payload, reveal_identifiers=True)
    assert is_str_keyed_dict(redacted)
    return redacted


def _record_result_payload(operation: str, record: M145CommunicationRecord) -> dict[str, object]:
    payload: object = M145CommunicationRecordResult(
        operation=operation,
        record=M145CommunicationRecordPayload.from_record(record),
    ).model_dump(mode="json")
    return _redacted_cli_payload(payload)


def _payload_mismatch_paths(expected: object, actual: object, *, path: str = "$") -> tuple[str, ...]:
    """Name differing payload paths without exposing taxpayer values in failures."""
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        mismatches: list[str] = []
        keys = set(expected) | set(actual)
        for key in sorted(keys, key=str):
            child_path = f"{path}.{key}"
            if key not in expected:
                mismatches.append(f"{child_path} (unexpected)")
            elif key not in actual:
                mismatches.append(f"{child_path} (missing)")
            else:
                mismatches.extend(_payload_mismatch_paths(expected[key], actual[key], path=child_path))
        return tuple(mismatches)
    if isinstance(expected, list) and isinstance(actual, list):
        mismatches = []
        if len(expected) != len(actual):
            mismatches.append(f"{path} (length)")
        for index in range(min(len(expected), len(actual))):
            mismatches.extend(_payload_mismatch_paths(expected[index], actual[index], path=f"{path}[{index}]"))
        return tuple(mismatches)
    if type(expected) is not type(actual) or expected != actual:
        return (path,)
    return ()


class _NoWriteEventHistory(BucketEventHistoryRepositoryProtocol):
    """Let the canonical export service derive its complete result without saving its receipt."""

    def __init__(self, repository: BucketEventHistoryRepositoryProtocol) -> None:
        self._repository = repository
        self.proposed: BucketEventHistoryCatalogue | None = None

    @override
    def exists(self) -> bool:
        return self._repository.exists()

    @override
    def load(self) -> BucketEventHistoryCatalogue:
        return self._repository.load()

    @override
    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        self.proposed = catalogue

    @override
    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        return self._repository.to_secure_object_write(catalogue, expected_revision_id=expected_revision_id)


def test_native_m145_five_operations_preserve_full_values_history_and_refusals(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-m145-communication", facts=_PROFILE_FACTS)
        assert profile.label is not None
        bucket_id = str(resolve_login_target(profile.label).bucket_id)
        assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
        ports = build_m145_communication_records_ports(bucket_id=bucket_id)

        history_before_missing = ports.bucket_event_repository.load()
        missing = _invoke(
            profile,
            "app",
            "modelo",
            "m145",
            "validate",
            "0" * 12,
        )
        assert missing.exit_code == 2, missing.output
        assert "Traceback" not in missing.output
        missing_error = require_error_document(missing.output)["error"]
        assert missing_error["code"] == "REFUSED_M145_COMMUNICATION_RECORD_NOT_FOUND"
        assert missing_error["category"] == "REFUSED"
        assert missing_error["context"] == {"communication_record_id": "0" * 12}
        assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
        ports = build_m145_communication_records_ports(bucket_id=bucket_id)
        _event_delta(
            history_before_missing,
            ports.bucket_event_repository.load(),
            bucket_id=bucket_id,
            expected_mutation=None,
        )

        history_before_create = ports.bucket_event_repository.load()
        created = _invoke(
            profile,
            "app",
            "modelo",
            "m145",
            "create",
            "--year",
            "2026",
            "--casilla",
            "perceptor.nif=12345678Z",
            "--casilla",
            "perceptor.primer-apellido=Garcia",
            "--casilla",
            "perceptor.segundo-apellido=Lopez",
            "--casilla",
            "perceptor.nombre=Ana",
            "--casilla",
            "perceptor.anio-nacimiento=1981",
            "--note",
            "Native local communication",
        )
        assert created.exit_code == 0, created.output
        create_payload = unwrap_cli_result(created)
        record_id = create_payload["record"]["communication_record_id"]
        assert isinstance(record_id, str)
        assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
        ports = build_m145_communication_records_ports(bucket_id=bucket_id)
        record = read_m145_communication_record(
            record_id,
            bucket_id=bucket_id,
            ports=ports,
            operation=authority_operation,
        )
        expected_create_payload = _record_result_payload("modelo.m145.create", record)
        assert create_payload == expected_create_payload, (
            "create payload differs from the canonical M145 projection at: "
            + ", ".join(_payload_mismatch_paths(expected_create_payload, create_payload))
        )
        assert _FIELD_VALUES["perceptor.nif"] not in created.output
        assert create_payload["record"]["field_values"]["perceptor.nif"] != _FIELD_VALUES["perceptor.nif"]
        assert record.field_values == _FIELD_VALUES
        assert record.note == "Native local communication"
        created_event = _event_delta(
            history_before_create,
            ports.bucket_event_repository.load(),
            bucket_id=bucket_id,
            expected_mutation=BucketEventType.MODELO_145_COMMUNICATION_CREATED,
        )
        assert created_event is not None
        _assert_communication_event(
            created_event,
            bucket_id=bucket_id,
            record=record,
            event_type=BucketEventType.MODELO_145_COMMUNICATION_CREATED,
            actor=bucket_id,
        )

        history_before_transition_refusal = ports.bucket_event_repository.load()
        premature_completion = _invoke(
            profile,
            "app",
            "modelo",
            "m145",
            "mark-locally-completed",
            record_id[:12],
            "--by",
            _ACTOR,
        )
        assert premature_completion.exit_code == 2, premature_completion.output
        assert "Traceback" not in premature_completion.output
        transition_error = require_error_document(premature_completion.output)["error"]
        assert transition_error["code"] == "REFUSED_M145_COMMUNICATION_RECORD_TRANSITION"
        assert transition_error["category"] == "REFUSED"
        assert transition_error["context"] == {"communication_record_id": record_id, "state": "created"}
        assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
        ports = build_m145_communication_records_ports(bucket_id=bucket_id)
        unchanged = read_m145_communication_record(
            record_id,
            bucket_id=bucket_id,
            ports=ports,
            operation=authority_operation,
        )
        assert unchanged == record
        _event_delta(
            history_before_transition_refusal,
            ports.bucket_event_repository.load(),
            bucket_id=bucket_id,
            expected_mutation=None,
        )

        history_before_validate = ports.bucket_event_repository.load()
        validation = _invoke(profile, "app", "modelo", "m145", "validate", record_id[:12])
        assert validation.exit_code == 0, validation.output
        assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
        ports = build_m145_communication_records_ports(bucket_id=bucket_id)
        expected_validation = validate_m145_communication_record(
            record_id,
            bucket_id=bucket_id,
            ports=ports,
            operation=authority_operation,
        )
        expected_validation_payload = M145CommunicationValidationResultPayload.from_result(
            expected_validation
        ).model_dump(mode="json")
        assert unwrap_cli_result(validation) == _redacted_cli_payload(expected_validation_payload)
        assert expected_validation.valid is True
        _event_delta(
            history_before_validate,
            ports.bucket_event_repository.load(),
            bucket_id=bucket_id,
            expected_mutation=None,
        )

        history_before_export = ports.bucket_event_repository.load()
        preview_repository = _NoWriteEventHistory(ports.bucket_event_repository)
        preview_ports = replace(ports, bucket_event_repository=preview_repository)
        expected_export = export_m145_communication_record(
            record_id,
            bucket_id=bucket_id,
            renderer=RegistryFixedWidthRecordRenderer(),
            ports=preview_ports,
            operation=authority_operation,
            actor=_ACTOR,
        )
        assert preview_repository.proposed is not None
        assert ports.bucket_event_repository.load() == history_before_export
        exported = _invoke(profile, "app", "modelo", "m145", "export", record_id[:12], "--by", _ACTOR)
        assert exported.exit_code == 0, exported.output
        assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
        ports = build_m145_communication_records_ports(bucket_id=bucket_id)
        export_payload = unwrap_cli_result(exported)
        expected_export_payload = M145CommunicationExportResultPayload.from_result(expected_export).model_dump(
            mode="json",
        )
        assert export_payload == _redacted_cli_payload(expected_export_payload)
        export_event = _event_delta(
            history_before_export,
            ports.bucket_event_repository.load(),
            bucket_id=bucket_id,
            expected_mutation=BucketEventType.MODELO_145_COMMUNICATION_EXPORTED,
        )
        assert export_event is not None
        _assert_communication_event(
            export_event,
            bucket_id=bucket_id,
            record=record,
            event_type=BucketEventType.MODELO_145_COMMUNICATION_EXPORTED,
            extra={
                "export_layout_id": expected_export.export_layout_id,
                "payload_sha256": expected_export.payload_sha256,
                "byte_length": str(expected_export.byte_length),
                "record_count": str(expected_export.record_count),
            },
        )
        assert export_payload["payload_sha256"] == expected_export.payload_sha256
        canonical_payload_text = expected_export_payload["payload_text"]
        assert isinstance(canonical_payload_text, str)
        assert canonical_payload_text.startswith("<T145010>")
        assert canonical_payload_text.encode(expected_export.encoding) == expected_export.payload
        assert _FIELD_VALUES["perceptor.nif"] in canonical_payload_text
        assert _FIELD_VALUES["perceptor.nif"].encode(expected_export.encoding) in expected_export.payload
        actual_payload_text = export_payload["payload_text"]
        assert isinstance(actual_payload_text, str)
        assert actual_payload_text.encode(expected_export.encoding) == expected_export.payload

        history_before_delivery = ports.bucket_event_repository.load()
        delivered = _invoke(
            profile,
            "app",
            "modelo",
            "m145",
            "mark-delivered-to-payer",
            record_id[:12],
            "--by",
            _ACTOR,
        )
        assert delivered.exit_code == 0, delivered.output
        assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
        ports = build_m145_communication_records_ports(bucket_id=bucket_id)
        delivered_record = read_m145_communication_record(
            record_id,
            bucket_id=bucket_id,
            ports=ports,
            operation=authority_operation,
        )
        assert unwrap_cli_result(delivered) == _record_result_payload(
            "modelo.m145.mark_delivered_to_payer",
            delivered_record,
        )
        assert delivered_record.delivered_to_payer_at is not None
        delivered_event = _event_delta(
            history_before_delivery,
            ports.bucket_event_repository.load(),
            bucket_id=bucket_id,
            expected_mutation=BucketEventType.MODELO_145_COMMUNICATION_DELIVERED_TO_PAYER,
        )
        assert delivered_event is not None
        _assert_communication_event(
            delivered_event,
            bucket_id=bucket_id,
            record=delivered_record,
            event_type=BucketEventType.MODELO_145_COMMUNICATION_DELIVERED_TO_PAYER,
        )

        history_before_completion = ports.bucket_event_repository.load()
        completed = _invoke(
            profile,
            "app",
            "modelo",
            "m145",
            "mark-locally-completed",
            record_id[:12],
            "--by",
            _ACTOR,
        )
        assert completed.exit_code == 0, completed.output
        assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
        ports = build_m145_communication_records_ports(bucket_id=bucket_id)
        completed_record = read_m145_communication_record(
            record_id,
            bucket_id=bucket_id,
            ports=ports,
            operation=authority_operation,
        )
        assert unwrap_cli_result(completed) == _record_result_payload(
            "modelo.m145.mark_locally_completed",
            completed_record,
        )
        assert completed_record.delivered_to_payer_at == delivered_record.delivered_to_payer_at
        assert completed_record.locally_completed_at is not None
        completed_event = _event_delta(
            history_before_completion,
            ports.bucket_event_repository.load(),
            bucket_id=bucket_id,
            expected_mutation=BucketEventType.MODELO_145_COMMUNICATION_LOCALLY_COMPLETED,
        )
        assert completed_event is not None
        _assert_communication_event(
            completed_event,
            bucket_id=bucket_id,
            record=completed_record,
            event_type=BucketEventType.MODELO_145_COMMUNICATION_LOCALLY_COMPLETED,
        )
