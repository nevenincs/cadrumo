"""The installation area's catalogue and forms are read from the runtime's act table, not written beside it."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.installation_requests import (
    INSTALLATION_ACT_CONTRACTS,
    ArchiveImportRequest,
    InstallationAct,
    InstallationActContract,
    InstallationActFacts,
    InstallationCompleted,
    InstallationHostPath,
    RepairLogsRequest,
    RepairProfileRequest,
    StorageReclaimRequest,
)

from .....application.operations.registry import OperationFrontendProjection
from .....core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .....core.storage_taxonomy import StorageArea
from ..acts import (
    CONFIRMATION_FIELD,
    ActFieldKind,
    ActInputError,
    InstallationFamily,
    family_of,
    offer_contract,
    offered_act,
    offered_acts,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_COORDINATES = {"request_id", "frontend", "action"}


def test_every_act_of_the_runtime_table_is_offered_exactly_once() -> None:
    offered = [entry.act for entry in offered_acts()]

    assert sorted(offered) == sorted(INSTALLATION_ACT_CONTRACTS)
    assert len(offered) == len(set(offered)) == len(InstallationAct)


def test_every_request_member_becomes_a_form_field_except_the_ones_the_interface_fills() -> None:
    for entry in offered_acts():
        members = set(entry.contract.request.model_fields) - _COORDINATES - {CONFIRMATION_FIELD}

        assert {field.name for field in entry.fields} == members, entry.act
        assert entry.asks_confirmation == (CONFIRMATION_FIELD in entry.contract.request.model_fields), entry.act


def test_a_field_is_asked_for_by_the_type_its_request_model_declares() -> None:
    kinds = {(entry.act, field.name): field.kind for entry in offered_acts() for field in entry.fields}

    assert kinds[InstallationAct.STORAGE_RECLAIM, "area"] is ActFieldKind.CHOICE
    assert kinds[InstallationAct.ARCHIVE_INSPECT, "path"] is ActFieldKind.PATH
    assert kinds[InstallationAct.REVIEW_PACKAGE_VERIFY_SIGNATURE, "signature"] is ActFieldKind.PATH
    assert kinds[InstallationAct.REVIEW_PACKAGE_VERIFY_SIGNATURE, "public_key"] is ActFieldKind.TEXT
    assert kinds[InstallationAct.REPORT_VERIFY_DOCUMENT, "trusted_key"] is ActFieldKind.TEXT
    assert kinds[InstallationAct.RECOVERY_ENROLL, "profile_id"] is ActFieldKind.UUID
    assert kinds[InstallationAct.REPAIR_LOGS, "lines"] is ActFieldKind.INTEGER
    assert kinds[InstallationAct.REPAIR_PROFILE, "clear_active"] is ActFieldKind.BOOLEAN
    assert kinds[InstallationAct.RESET_STATUS, "operation_id"] is ActFieldKind.TEXT

    reclaim = offered_act(InstallationAct.STORAGE_RECLAIM).fields[0]
    assert reclaim.required and reclaim.choices == tuple(area.value for area in StorageArea)
    logs = offered_act(InstallationAct.REPAIR_LOGS).fields[0]
    assert not logs.required and logs.default == 20


def test_an_act_added_to_the_table_is_offered_with_a_working_form_and_a_family() -> None:
    class _Nested(BaseModel):
        model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

        depth: int

    class _LaterRequest(BaseModel):
        model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

        request_id: UUID
        frontend: OperationFrontendProjection
        action: Literal["storage_check"] = "storage_check"
        source: InstallationHostPath
        limits: _Nested
        tags: tuple[str, ...] = ()
        confirmed: bool = False

    later = offer_contract(
        InstallationActContract(
            InstallationAct.STORAGE_CHECK,
            _LaterRequest,
            InstallationCompleted,
            InstallationActFacts(changes_records=True, reaches_network=False),
        )
    )

    assert later.family is InstallationFamily.STORAGE and later.asks_confirmation
    assert {field.name: field.kind for field in later.fields} == {
        "source": ActFieldKind.PATH,
        "limits": ActFieldKind.JSON,
        "tags": ActFieldKind.JSON,
    }
    request = later.contract.request.model_validate(
        later.request({"source": "relative/file.bin", "limits": '{"depth": 3}', "tags": '["a", "b"]'}, confirmed=True)
    )
    assert isinstance(request, _LaterRequest)
    assert Path(request.source).is_absolute() and Path(request.source).name == "file.bin"
    assert request.limits.depth == 3 and request.tags == ("a", "b") and request.confirmed
    assert family_of(InstallationAct.REPORT_VERIFY_DOCUMENT) is InstallationFamily.VERIFICATION


def test_a_request_is_built_as_the_wire_would_carry_it_and_names_this_frontend() -> None:
    reclaim = offered_act(InstallationAct.STORAGE_RECLAIM)

    unconfirmed = reclaim.request({"area": "cache"})
    confirmed = reclaim.request({"area": "cache"}, confirmed=True)

    assert isinstance(unconfirmed, StorageReclaimRequest) and isinstance(confirmed, StorageReclaimRequest)
    assert unconfirmed.area is StorageArea.CACHE and unconfirmed.frontend is OperationFrontendProjection.TUI
    assert (unconfirmed.confirmed, confirmed.confirmed) == (False, True)
    assert unconfirmed.request_id != confirmed.request_id
    assert not reclaim.changes_records(unconfirmed) and reclaim.changes_records(confirmed)


def test_a_confirmed_request_that_still_changes_nothing_is_not_a_change() -> None:
    repair = offered_act(InstallationAct.REPAIR_PROFILE)

    inspecting = repair.request({"profile": "Synthetic", "clear_active": False}, confirmed=True)
    clearing = repair.request({"clear_active": True}, confirmed=True)

    assert isinstance(inspecting, RepairProfileRequest) and inspecting.profile == "Synthetic"
    assert not repair.changes_records(inspecting)
    assert repair.changes_records(clearing)


@pytest.mark.parametrize(
    ("act", "values", "faulty"),
    [
        (InstallationAct.STORAGE_RECLAIM, {"area": ""}, ("area",)),
        (InstallationAct.STORAGE_RECLAIM, {"area": "not-an-area"}, ("area",)),
        (InstallationAct.REPAIR_LOGS, {"lines": "many"}, ("lines",)),
        (InstallationAct.REPAIR_LOGS, {"lines": "999999"}, ("lines",)),
        (InstallationAct.RECOVERY_ENROLL, {"profile_id": "not-a-uuid"}, ("profile_id",)),
        (InstallationAct.RESET_STATUS, {"operation_id": "private-short-value"}, ("operation_id",)),
        (InstallationAct.ARCHIVE_IMPORT_PREPARE, {"label": "", "path": ""}, ("label", "path")),
    ],
)
def test_malformed_input_names_the_members_at_fault_and_never_their_values(
    act: InstallationAct, values: dict[str, object], faulty: tuple[str, ...]
) -> None:
    with pytest.raises(ActInputError) as refused:
        offered_act(act).request(values)

    assert refused.value.fields == faulty
    for value in values.values():
        if value:
            assert str(value) not in str(refused.value)
            assert str(value) not in repr(refused.value.__dict__)
    # Whatever the parser said about the value stays out of the error's chain.
    assert refused.value.__cause__ is None
    assert refused.value.__context__ is None or refused.value.__suppress_context__


def test_optional_members_left_empty_are_left_out_and_defaults_stand() -> None:
    logs = offered_act(InstallationAct.REPAIR_LOGS).request({"lines": ""})
    counted = offered_act(InstallationAct.REPAIR_LOGS).request({"lines": " 7 "})

    assert isinstance(logs, RepairLogsRequest) and logs.lines == 20
    assert isinstance(counted, RepairLogsRequest) and counted.lines == 7


def test_the_digest_of_an_archive_import_is_supplied_by_the_read_that_prepares_it() -> None:
    importing = offered_act(InstallationAct.ARCHIVE_IMPORT)
    digest_field = next(field for field in importing.fields if field.name == "source_digest")

    assert importing.prerequisite is not None
    assert importing.prerequisite.act is InstallationAct.ARCHIVE_IMPORT_PREPARE
    assert digest_field.supplied_by is InstallationAct.ARCHIVE_IMPORT_PREPARE and not digest_field.required
    preparing = offered_act(importing.prerequisite.act)
    assert {field.name for field in preparing.fields} <= {field.name for field in importing.fields}
    # Left empty it is not a request yet: the interface reads the source first.
    with pytest.raises(ActInputError) as incomplete:
        importing.request({"label": "Restored", "path": str(Path.cwd() / "archive.tar.gz")})
    assert incomplete.value.fields == ("source_digest",)
    digest = "ab" * 32
    request = importing.request(
        {"label": "Restored", "path": str(Path.cwd() / "archive.tar.gz"), "source_digest": digest}
    )
    assert isinstance(request, ArchiveImportRequest) and str(request.source_digest) == digest
    assert request.request_id != uuid4()
