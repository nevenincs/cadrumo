"""Each repair command that needs a profile's stores prints exactly what its registered operation returns.

The command runs in this process and the operation runs through its real
executor, both over one real encrypted profile. An operation's result is the
document a frontend shows, with real identifiers. It must equal the JSON data
the command prints when identifiers are revealed, and the command's default
print must be that same document after the command line's own output
redaction.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import AnyHttpUrl, BaseModel

from ...adapters.outbound.aeat.browser.site_health_records import SiteHealthEvidence, SiteHealthStatus
from ...adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from ...adapters.persistence.storage.secure_object_namespaces import (
    TEST_RUNTIME_PROFILE_NAMESPACE,
    TEST_SESSION_LIFECYCLE_NAMESPACE,
    SecureObjectNamespaceDefinition,
)
from ...adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...application.diagnostics_repair_documents import (
    RepairConnectivityDocument,
    RepairIntegrityObjectsDocument,
    RepairQuarantineDocument,
    RepairResetProgressDocument,
)
from ...application.diagnostics_repair_operations import (
    CONNECTIVITY_PROBE_OPERATION_DEFINITION_ID,
    SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID,
    SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID,
    WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID,
    ConnectivityProbeRequest,
    SecureObjectsCheckRequest,
    SecureObjectsQuarantineRequest,
    WorkflowProgressResetRequest,
    build_connectivity_probe_definition,
)
from ...application.ledger.tests.bulk_classify_operation_support import CommitFence, EffectEvents, PrivateOperands
from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.operations.operation_definition import OperationDefinition
from ...application.operations.owner import OperationExecutorContext
from ...application.workflow.persistence import workflow_state_repository
from ...application.workflow.state_models import WorkflowState
from ...core.config import override_settings
from ...core.errors.hierarchy import SiteHealthState
from ...core.operations import profile_operation_subject
from ...core.redaction.rules import CLI_PROFILE_ID_PLACEHOLDER, redact_structured_for_cli_output
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..cli.config import _repair_cli
from ..cli.tests.cli_runner import invoke_cached_cli, semantic_cli_output
from ..diagnostics_repair_composition import build_diagnostics_repair_operations

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE = UUID("97979797-9797-4797-8797-979797979797")
_SEEDED_PROGRESS_AT = datetime(2026, 4, 3, 10, 15, 42, tzinfo=UTC)
_OBSERVED = SiteHealthStatus(
    state=SiteHealthState.RATE_LIMITED,
    evidence=SiteHealthEvidence(
        url=AnyHttpUrl("https://probe.example.org/"),
        http_status=429,
        html_fragment="<html>synthetic rate limit page</html>",
        detected_markers=("retry-after:45",),
    ),
    observed_at=datetime(2026, 4, 3, 10, 16, 0, tzinfo=UTC),
    retry_after_seconds=45,
)


@contextmanager
def _profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """One real encrypted profile that is the active selection, its session open in this process."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        composed_profile_persistence_ports(),
    ):
        yield profile


def _store(profile: TestRuntimeProfile, definition: SecureObjectNamespaceDefinition) -> None:
    profile.repository.save(
        namespace=definition.namespace,
        object_key=definition.object_key_grammar,
        classification=definition.sensitivity,
        schema_version=1,
        written_at=datetime.now(UTC),
        payload=f"synthetic-{definition.key}".encode(),
    )


def _tear(profile: TestRuntimeProfile, definition: SecureObjectNamespaceDefinition) -> None:
    """Store one row and flip its last ciphertext byte, so its tag no longer authenticates."""
    _store(profile, definition)
    with sqlite3.connect(profile.paths.database_file) as connection:
        row_id, payload = connection.execute(
            "SELECT id, payload FROM secure_objects WHERE namespace = ? ORDER BY id DESC LIMIT 1",
            (definition.namespace,),
        ).fetchone()
        connection.execute(
            "UPDATE secure_objects SET payload = ? WHERE id = ?", (payload[:-1] + bytes([payload[-1] ^ 0xFF]), row_id)
        )
    connection.close()


@dataclass(frozen=True, slots=True)
class _Printed:
    """The JSON data one command prints, as it prints by default and with identifiers revealed."""

    default: dict[str, object]
    revealed: dict[str, object]


def _data(*arguments: str, reveal: bool = False) -> dict[str, object]:
    """Run the command once and return the JSON data it prints."""
    with override_settings(cadrumo_cli_reveal_identifiers=reveal):
        result = invoke_cached_cli(["--format", "json", *arguments])
    assert result.exit_code == 0, semantic_cli_output(result)
    envelope = json.loads(result.stdout)
    assert isinstance(envelope, dict)
    data = envelope["result"]
    assert isinstance(data, dict)
    members: dict[str, object] = {str(key): value for key, value in data.items()}
    return members


def _command(*arguments: str) -> _Printed:
    """Run a command that changes nothing twice: as it prints by default, and with identifiers revealed."""
    return _Printed(default=_data(*arguments), revealed=_data(*arguments, reveal=True))


def _hidden(document: dict[str, object]) -> dict[str, object]:
    """Return ``document`` after the command line's own output redaction."""
    hidden = redact_structured_for_cli_output(document, reveal_identifiers=False)
    members: dict[str, object] = {str(key): value for key, value in hidden.items()}
    return members


def _assert_prints(result: BaseModel, printed: _Printed) -> None:
    """Hold a command's two prints to the result: whole when revealed, redacted by default."""
    document = _document(result)
    assert printed.revealed == document
    assert printed.default == _hidden(document)


def _operate[ResultT: BaseModel](
    definition: OperationDefinition, payload: BaseModel, operation: PinnedAuthorityOperation, result_type: type[ResultT]
) -> ResultT:
    """Run one request through the definition's real executor and return the result it retained."""
    subject = profile_operation_subject(str(_PROFILE))
    operands = PrivateOperands()
    context = cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=OperationIdentity(
                    operation_id="b" * 64, definition_id=definition.definition_id, subject_ref=subject
                ),
                authority_operation=operation,
                cancellation=CommitFence(),
                events=EffectEvents(),
                operands=operands,
            ),
        ),
    )
    request = OperationRequest[BaseModel](definition_id=definition.definition_id, subject_ref=subject, payload=payload)
    asyncio.run(definition.executor_factory.create().execute(request, context))
    (result,) = operands.values
    assert definition.result_type is result_type
    assert isinstance(result, result_type)
    return result


def _definition(definition_id: str) -> OperationDefinition:
    operations = build_diagnostics_repair_operations()
    return next(item for item in operations.definitions if item.definition_id == definition_id)


def _document(result: BaseModel) -> dict[str, object]:
    """Return an operation's result as a frontend shows it."""
    members: dict[str, object] = {str(name): value for name, value in result.model_dump(mode="json").items()}
    return members


def test_integrity_objects_prints_what_the_check_operation_returns(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    definition = _definition(SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID)
    torn = TEST_RUNTIME_PROFILE_NAMESPACE.namespace

    with _profile(tmp_path) as profile:
        _store(profile, TEST_SESSION_LIFECYCLE_NAMESPACE)
        _tear(profile, TEST_RUNTIME_PROFILE_NAMESPACE)
        commanded = _command("config", "repair", "integrity", "objects")
        operated = _operate(
            definition,
            SecureObjectsCheckRequest(profile_id=_PROFILE),
            authority_operation,
            RepairIntegrityObjectsDocument,
        )
        commanded_narrow = _command("config", "repair", "integrity", "objects", "--namespace", torn)
        operated_narrow = _operate(
            definition,
            SecureObjectsCheckRequest(profile_id=_PROFILE, namespace=torn),
            authority_operation,
            RepairIntegrityObjectsDocument,
        )

    assert (operated.check.status, operated.unreadable_total) == ("fail", 1)
    assert [row.namespace for row in operated_narrow.namespaces] == [torn]
    _assert_prints(operated, commanded)
    _assert_prints(operated_narrow, commanded_narrow)


def test_quarantine_prints_what_the_quarantine_operation_returns(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    definition = _definition(SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID)

    with _profile(tmp_path) as profile:
        _store(profile, TEST_SESSION_LIFECYCLE_NAMESPACE)
        _tear(profile, TEST_RUNTIME_PROFILE_NAMESPACE)
        commanded_preview = _command("config", "repair", "quarantine", "--dry-run")
        operated_preview = _operate(
            definition,
            SecureObjectsQuarantineRequest(profile_id=_PROFILE, dry_run=True),
            authority_operation,
            RepairQuarantineDocument,
        )
        operated = _operate(
            definition,
            SecureObjectsQuarantineRequest(profile_id=_PROFILE, dry_run=False),
            authority_operation,
            RepairQuarantineDocument,
        )
        # The command meets the same torn row the operation moved, once for each way it prints.
        _tear(profile, TEST_RUNTIME_PROFILE_NAMESPACE)
        revealed = _data("config", "repair", "quarantine", "--yes", reveal=True)
        _tear(profile, TEST_RUNTIME_PROFILE_NAMESPACE)
        default = _data("config", "repair", "quarantine", "--yes")
        settled = _data("config", "repair", "quarantine", "--dry-run")

    assert (operated_preview.dry_run, operated_preview.unreadable_total) == (True, 1)
    assert (operated.dry_run, operated.unreadable_total) == (False, 1)
    _assert_prints(operated_preview, commanded_preview)
    assert revealed == _document(operated)
    assert default == _hidden(_document(operated))
    assert settled["unreadable_total"] == 0


def test_reset_progress_prints_what_the_reset_operation_returns(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    definition = _definition(WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID)

    with _profile(tmp_path):
        workflow_state_repository().save(WorkflowState(updated_at=_SEEDED_PROGRESS_AT))
        commanded_preview = _command("config", "repair", "reset-progress", "--dry-run")
        operated_preview = _operate(
            definition,
            WorkflowProgressResetRequest(profile_id=_PROFILE, dry_run=True),
            authority_operation,
            RepairResetProgressDocument,
        )
        operated = _operate(
            definition,
            WorkflowProgressResetRequest(profile_id=_PROFILE, dry_run=False),
            authority_operation,
            RepairResetProgressDocument,
        )
        operated_again = _operate(
            definition,
            WorkflowProgressResetRequest(profile_id=_PROFILE, dry_run=True),
            authority_operation,
            RepairResetProgressDocument,
        )
        # The command meets a saved record again, once for each way it prints, and each run
        # discards the record it described.
        workflow_state_repository().save(WorkflowState(updated_at=_SEEDED_PROGRESS_AT))
        revealed_before = _data("config", "repair", "reset-progress", "--dry-run", reveal=True)
        revealed = _data("config", "repair", "reset-progress", "--yes", reveal=True)
        workflow_state_repository().save(WorkflowState(updated_at=_SEEDED_PROGRESS_AT))
        default_before = _data("config", "repair", "reset-progress", "--dry-run")
        default = _data("config", "repair", "reset-progress", "--yes")
        commanded_again = _command("config", "repair", "reset-progress", "--dry-run")

    assert operated_preview.fingerprint is not None and operated_preview.fingerprint.reason_class == "readable"
    # The result names the profile whose progress it is by its real identifier; the command hides it by default.
    assert operated_preview.fingerprint.recovered_bucket_id == str(_PROFILE)
    assert str(_PROFILE) not in json.dumps(commanded_preview.default)
    assert CLI_PROFILE_ID_PLACEHOLDER in json.dumps(commanded_preview.default)
    _assert_prints(operated_preview, commanded_preview)
    assert _document(operated) == {**_document(operated_preview), "dry_run": False}
    assert revealed == {**revealed_before, "dry_run": False}
    assert default == {**default_before, "dry_run": False}
    # The discarded records were saved at different instants; every other member is the same.
    assert _without_written_at(_document(operated)) == _without_written_at(revealed)
    assert _without_written_at(_hidden(_document(operated))) == _without_written_at(default)
    _assert_prints(operated_again, commanded_again)
    assert operated_again.fingerprint is not None and operated_again.fingerprint.reason_class == "absent"


def _without_written_at(result: dict[str, object]) -> dict[str, object]:
    fingerprint = cast(dict[str, object], result["fingerprint"])
    return {**result, "fingerprint": {key: value for key, value in fingerprint.items() if key != "written_at"}}


def test_connectivity_prints_what_the_probe_operation_returns_for_the_same_observation(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    def observe() -> SiteHealthStatus:
        return _OBSERVED

    # The browser is the one part both sides are bound to here; neither reaches the network.
    monkeypatch.setattr(_repair_cli, "_probe_browser_connectivity", observe)
    definition = build_connectivity_probe_definition(observe)
    assert definition.definition_id == CONNECTIVITY_PROBE_OPERATION_DEFINITION_ID

    with _profile(tmp_path):
        commanded = _command("config", "repair", "connectivity")
        operated = _operate(
            definition, ConnectivityProbeRequest(profile_id=_PROFILE), authority_operation, RepairConnectivityDocument
        )

    assert (operated.target, operated.status.state) == ("aeat_sede", "rate_limited")
    assert (operated.status.evidence.http_status, operated.status.retry_after_seconds) == (429, 45)
    _assert_prints(operated, commanded)
