"""Boundary proofs for the setup item contracts: identities, reasons, plans and their digest."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ...core.model_catalogue import ModelRole
from ...core.storage_taxonomy import StorageCategory
from ..dependency_contracts import (
    DEPENDENCY_PROGRESS_UNIT_CODE,
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyItemKind,
    DependencyNote,
    DependencyPlanEntry,
    DependencyPlanPart,
    DependencyProbeOutcome,
    DependencyProbeReading,
    DependencySetupPlan,
    DependencySetupStep,
    DependencySpaceCheck,
    DependencyStaleReason,
    DependencyState,
    DependencyStatusRow,
    combine_plan_parts,
    dependency_item_kind,
    dependency_phase_code,
    dependency_plan_digest,
    dependency_progress_subject,
    dependency_retry_notice_code,
    known_download_bytes_of,
    known_part_bytes_of,
    parse_dependency_retry_notice,
    required_free_bytes,
    shared_download_key,
)
from ..dependency_registry import dependency_item_declarations
from ..operations.models import OperationIdentity
from ..operations.persistence.events import OperationPhaseEvent, OperationProgressEvent

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_GIB = 1024**3
_IDENTITY = OperationIdentity(operation_id="a" * 64, definition_id="dependencies.setup", subject_ref="profile:active")
_NOW = datetime(2026, 10, 18, 9, 0, tzinfo=UTC)


def _entry(item_id: str = "browser", **overrides: object) -> DependencyPlanEntry:
    fields: dict[str, object] = {
        "item_id": item_id,
        "download_bytes": 300 * 1024**2,
        "source_hosts": ("cdn.playwright.dev",),
        "destination": StorageCategory.PLAYWRIGHT_BROWSERS,
    }
    fields.update(overrides)
    return DependencyPlanEntry.model_validate(fields)


def test_item_identities_are_the_two_kinds_and_nothing_else() -> None:
    assert dependency_item_kind("browser") is DependencyItemKind.BROWSER
    assert dependency_item_kind("local_ai") is DependencyItemKind.LOCAL_AI
    # The local AI's program and models are parts of one item, and the Google
    # account is the profile's own sign-in: none of them is an item.
    for refused in ("model_runtime", "local_model", "local_model.text_extraction", "google", "chromium"):
        with pytest.raises(ValueError):
            dependency_item_kind(refused)


def test_every_declared_item_yields_codes_the_operation_journal_accepts() -> None:
    for declaration in dependency_item_declarations():
        for step in DependencySetupStep:
            code = dependency_phase_code(declaration.item_id, step)
            assert code == f"dependencies.setup.{declaration.item_id}.{step.value}"
            event = OperationPhaseEvent(
                identity=_IDENTITY, revision=0, sequence=1, timestamp=_NOW, code=code, phase_code=code
            )
            assert event.phase_code == code
        progress = OperationProgressEvent(
            identity=_IDENTITY,
            revision=0,
            sequence=1,
            timestamp=_NOW,
            code="operation.progress",
            completed=1,
            total=2,
            unit_code=DEPENDENCY_PROGRESS_UNIT_CODE,
            subject_code=dependency_progress_subject(declaration.item_id),
        )
        assert progress.subject_code == declaration.item_id


def test_required_free_space_adds_a_fifth_and_one_gibibyte() -> None:
    assert required_free_bytes(0) == _GIB
    assert required_free_bytes(1) == 2 + _GIB
    assert required_free_bytes(5) == 6 + _GIB
    assert required_free_bytes(10 * _GIB) == 13 * _GIB
    with pytest.raises(ValueError):
        required_free_bytes(-1)


def test_space_check_never_reads_an_unmeasured_volume_as_enough() -> None:
    assert DependencySpaceCheck(free_bytes=None, required_bytes=0).sufficient is False
    assert DependencySpaceCheck(free_bytes=_GIB, required_bytes=_GIB).sufficient is True
    assert DependencySpaceCheck(free_bytes=_GIB - 1, required_bytes=_GIB).sufficient is False


def test_probe_readings_carry_exactly_the_reason_their_outcome_needs() -> None:
    stale = DependencyProbeReading(
        item_id="browser",
        mode=DependencyCheckMode.QUICK,
        outcome=DependencyProbeOutcome.DIFFERS,
        stale_reason=DependencyStaleReason.OLDER_REVISION,
    )
    assert stale.stale_reason is DependencyStaleReason.OLDER_REVISION
    refused = (
        {"outcome": DependencyProbeOutcome.DIFFERS},
        {"outcome": DependencyProbeOutcome.BLOCKED},
        {"outcome": DependencyProbeOutcome.FAILED},
        {"outcome": DependencyProbeOutcome.PRESENT, "failure_category": DependencyFailureCategory.UNEXPECTED},
        {"outcome": DependencyProbeOutcome.ABSENT, "blocked_reason": DependencyBlockedReason.OFFLINE},
        {"outcome": DependencyProbeOutcome.ABSENT, "note": DependencyNote.DOWNLOADED_NOT_LOADED},
    )
    for fields in refused:
        with pytest.raises(ValidationError):
            DependencyProbeReading.model_validate({"item_id": "browser", "mode": DependencyCheckMode.QUICK, **fields})


def test_status_rows_pair_a_recovery_button_with_its_operator_action() -> None:
    with pytest.raises(ValidationError, match="offered together"):
        DependencyStatusRow(
            item_id="browser",
            kind=DependencyItemKind.BROWSER,
            mode=DependencyCheckMode.QUICK,
            state=DependencyState.ABSENT,
            recovery_action_id="operator.provision.browser",
        )
    with pytest.raises(ValidationError, match="kind"):
        DependencyStatusRow(
            item_id="local_ai",
            kind=DependencyItemKind.BROWSER,
            mode=DependencyCheckMode.QUICK,
            state=DependencyState.ABSENT,
        )


def test_plan_entries_refuse_unnamed_destinations_and_repeated_hosts() -> None:
    with pytest.raises(ValidationError):
        _entry("google")
    with pytest.raises(ValidationError, match="where it stores"):
        _entry(destination=None)
    with pytest.raises(ValidationError, match="once"):
        _entry(source_hosts=("cdn.playwright.dev", "cdn.playwright.dev"))
    with pytest.raises(ValidationError):
        _entry(source_hosts=("https://cdn.playwright.dev",))
    outside = _entry("local_ai", destination=None, installs_outside_program=True, source_hosts=("ollama.com",))
    assert outside.installs_outside_program is True


def test_plan_space_requirement_must_follow_from_its_known_sizes() -> None:
    entries = (_entry(), _entry("local_ai", download_bytes=None, source_hosts=("ollama.com",)))
    plan = DependencySetupPlan(
        entries=entries,
        space=DependencySpaceCheck(free_bytes=None, required_bytes=required_free_bytes(300 * 1024**2)),
    )
    assert plan.known_download_bytes == 300 * 1024**2
    assert plan.has_unknown_size is True
    assert plan.installs_outside_program is False
    with pytest.raises(ValidationError, match="space requirement"):
        DependencySetupPlan(entries=entries, space=DependencySpaceCheck(free_bytes=None, required_bytes=_GIB))
    with pytest.raises(ValidationError, match="each item once"):
        DependencySetupPlan(
            entries=(_entry(), _entry()),
            space=DependencySpaceCheck(free_bytes=None, required_bytes=required_free_bytes(600 * 1024**2)),
        )


def test_plan_digest_binds_what_is_downloaded_and_not_the_free_space_reading() -> None:
    required = required_free_bytes(300 * 1024**2)
    plan = DependencySetupPlan(
        entries=(_entry(),), space=DependencySpaceCheck(free_bytes=50 * _GIB, required_bytes=required)
    )
    remeasured = plan.model_copy(update={"space": DependencySpaceCheck(free_bytes=7 * _GIB, required_bytes=required)})
    assert len(dependency_plan_digest(plan)) == 64
    assert dependency_plan_digest(remeasured) == dependency_plan_digest(plan)

    changed_size = _entry(download_bytes=301 * 1024**2)
    resized = DependencySetupPlan(
        entries=(changed_size,),
        space=DependencySpaceCheck(free_bytes=50 * _GIB, required_bytes=required_free_bytes(301 * 1024**2)),
    )
    rehosted = DependencySetupPlan(
        entries=(_entry(source_hosts=("playwright.download.prss.microsoft.com",)),),
        space=plan.space,
    )
    reversioned = DependencySetupPlan(entries=(_entry(target_version="1187"),), space=plan.space)
    digests = {dependency_plan_digest(candidate) for candidate in (plan, resized, rehosted, reversioned)}
    assert len(digests) == 4


def _program(download_bytes: int | None = None) -> DependencyPlanPart:
    return DependencyPlanPart(
        part_id="program",
        download_bytes=download_bytes,
        source_hosts=("github.com",),
        destination=None if download_bytes is None else StorageCategory.OLLAMA_HOME,
        installs_outside_program=download_bytes is None,
    )


def _model(role: ModelRole, target: str | None, size: int) -> DependencyPlanPart:
    return DependencyPlanPart(
        part_id=role.value,
        download_bytes=size,
        source_hosts=("registry.ollama.ai",),
        destination=StorageCategory.OLLAMA_MODELS,
        target_version=target,
    )


def test_roles_sharing_one_model_download_it_once_in_the_local_ai_plan() -> None:
    shared = 1_400_000_000
    parts = (
        _program(),
        _model(ModelRole.TEXT_EXTRACTION, "qwen3:1.7b@" + "a" * 64, shared),
        _model(ModelRole.COLUMN_ROLE_MAPPING, "qwen3:1.7b@" + "a" * 64, shared),
        _model(ModelRole.SUPPLY_NATURE_PROPOSAL, "qwen3:1.7b@" + "a" * 64, shared),
        _model(ModelRole.VISION_TRANSCRIPTION, "qwen2.5vl:3b@" + "b" * 64, 3_200_000_000),
    )
    assert known_part_bytes_of(parts) == shared + 3_200_000_000
    entry = combine_plan_parts("local_ai", parts, destination=StorageCategory.OLLAMA_MODELS)
    assert entry.download_bytes == shared + 3_200_000_000
    assert entry.source_hosts == ("github.com", "registry.ollama.ai")
    assert entry.installs_outside_program is True
    # The program's installer does not say how much it fetches.
    assert entry.has_unknown_size is True
    plan = DependencySetupPlan(
        entries=(entry,),
        space=DependencySpaceCheck(free_bytes=None, required_bytes=required_free_bytes(shared + 3_200_000_000)),
    )
    assert plan.known_download_bytes == shared + 3_200_000_000
    assert plan.has_unknown_size is True
    unversioned = (_model(ModelRole.TEXT_EXTRACTION, None, shared), _model(ModelRole.COLUMN_ROLE_MAPPING, None, shared))
    assert known_part_bytes_of(unversioned) == 2 * shared


def test_an_item_planned_in_parts_is_the_local_ai_and_exactly_their_sum() -> None:
    parts = (_program(0), _model(ModelRole.TEXT_EXTRACTION, "qwen3:1.7b@" + "a" * 64, 100))
    entry = combine_plan_parts("local_ai", parts, destination=StorageCategory.OLLAMA_MODELS)
    assert (entry.download_bytes, entry.has_unknown_size, entry.installs_outside_program) == (100, False, False)
    fields = entry.model_dump()
    for change, reason in (
        ({"item_id": "browser"}, "only the local AI"),
        ({"download_bytes": 101}, "known size of its parts"),
        ({"installs_outside_program": True}, "installs a program"),
        ({"source_hosts": ("registry.ollama.ai",)}, "hosts are its parts"),
        ({"target_version": "qwen3:1.7b"}, "versions in its parts"),
        ({"parts": (parts[0], parts[0])}, "each part once"),
    ):
        with pytest.raises(ValidationError, match=reason):
            DependencyPlanEntry.model_validate({**fields, **change})


def test_entries_share_a_download_only_with_the_same_destination_and_version() -> None:
    elsewhere = (
        _entry(target_version="1187"),
        _entry(
            "local_ai",
            target_version="1187",
            source_hosts=("github.com",),
            destination=StorageCategory.OLLAMA_HOME,
        ),
    )
    assert shared_download_key(elsewhere[0]) != shared_download_key(elsewhere[1])
    assert known_download_bytes_of(elsewhere) == 2 * 300 * 1024**2


def test_retry_notice_codes_carry_attempt_and_wait_and_parse_back() -> None:
    model = "local_ai"
    code = dependency_retry_notice_code(model, attempt=3, delay_s=7.2)
    assert code == f"dependencies.setup.{model}.retry.3.8"
    assert parse_dependency_retry_notice(code) == (model, 3, 8)
    assert parse_dependency_retry_notice(dependency_retry_notice_code("browser", attempt=2, delay_s=0.4)) == (
        "browser",
        2,
        1,
    )
    event = OperationPhaseEvent(identity=_IDENTITY, revision=0, sequence=1, timestamp=_NOW, code=code, phase_code=code)
    assert event.code == code
    for other in ("dependencies.setup.browser.download", "operation.progress", "dependencies.setup.chromium.retry.2.4"):
        assert parse_dependency_retry_notice(other) is None
    with pytest.raises(ValueError):
        dependency_retry_notice_code("browser", attempt=1, delay_s=2.0)
