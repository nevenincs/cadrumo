"""Contract tests for the shared Drive owned-entry lookup policy.

The folder and spreadsheet lookups in
:mod:`~adapters.outbound.google.calc_sheets_apply` were two hand-copies of
one ownership decision, and neither validated that an adopted entry carried a
usable ``id``. Both defects are exercised here against a real in-process
Drive double that records the queries it receives, so the assertions run on
the production call path rather than on a patched helper.

Three properties are pinned:

- an apostrophe in a configured name is escaped into the query literal rather
  than closing it early;
- an app-owned entry with an absent or blank ``id`` is refused with a typed
  storage error instead of surfacing a raw :exc:`KeyError` to the caller;
- both lookups run the same ownership and refusal policy, so the
  behaviour cannot drift between them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import DriveResource

from .....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ...storage.errors import (
    OutboundStorageConflictError,
    OutboundStorageError,
    OutboundStorageValidationError,
)
from ..drive_entries import (
    OWNERSHIP_KEY,
    OWNERSHIP_VALUE,
    build_owned_entry_query,
    find_owned_drive_entry,
    is_app_owned,
    require_drive_entry_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _find_folder(drive, *, parent_id: str, name: str):
    return find_owned_drive_entry(
        drive,
        parent_id=parent_id,
        name=name,
        mime_type="application/vnd.google-apps.folder",
        list_action="drive.files.list",
        conflict_message="foreign folder",
    )


def _find_spreadsheet(drive, *, parent_id: str, name: str):
    return find_owned_drive_entry(
        drive,
        parent_id=parent_id,
        name=name,
        mime_type="application/vnd.google-apps.spreadsheet",
        list_action="drive.files.list.spreadsheet",
        conflict_message="foreign spreadsheet",
    )


@pytest.mark.parametrize(
    ("app_properties", "expected"),
    [
        ({OWNERSHIP_KEY: OWNERSHIP_VALUE}, True),
        ({OWNERSHIP_KEY: OWNERSHIP_VALUE, "other": "kept"}, True),
        ({}, False),
        ({OWNERSHIP_KEY: "someone-else"}, False),
        ({"unrelated": "value"}, False),
    ],
)
def test_only_the_exact_marker_counts_as_app_owned(app_properties: dict[str, str], expected: bool) -> None:
    assert is_app_owned(app_properties) is expected


_FOLDER_MIME = "application/vnd.google-apps.folder"
_SPREADSHEET_MIME = "application/vnd.google-apps.spreadsheet"


def _assert_closed_operator_review(
    error: OutboundStorageError,
    *,
    condition_id: str,
    facts: dict[str, str | int | bool],
) -> None:
    """Assert a fact-only state/validation refusal has no invented recovery action."""
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == condition_id
    assert len(verdict.evidence) == 1
    evidence = verdict.evidence[0]
    assert evidence.condition_id == condition_id
    assert evidence.evidence_id == f"{condition_id}.observation"
    assert evidence.provenance is ActionEvidenceProvenance.RUNTIME_OBSERVATION
    assert evidence.values == facts
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.missing_argument_names == ()
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


class _RecordedCall:
    """One captured Drive API invocation."""

    def __init__(self, kind: str, payload: dict[str, Any]) -> None:
        self.kind = kind
        self.payload = payload

    def execute(self, **kwargs: object) -> dict[str, Any]:
        # ``execute_request`` forwards ``num_retries``; accepting the real
        # kwargs keeps these tests on the production executor path.
        return self.payload.get("_result", {})


class _RecordedFiles:
    """Drive ``files()`` resource returning scripted listings."""

    def __init__(self, owner: _RecordedDrive) -> None:
        self._owner = owner

    def list(self, **request: object) -> _RecordedCall:
        query = request["q"]
        assert isinstance(query, str)
        assert isinstance(request["fields"], str)
        assert isinstance(request["pageSize"], int)
        self._owner.queries.append(query)
        return _RecordedCall("list", {"_result": {"files": self._owner.entries}})

    def update(self, **request: object) -> _RecordedCall:
        file_id = request["fileId"]
        body = request["body"]
        assert isinstance(file_id, str)
        assert isinstance(body, dict)
        assert isinstance(request["fields"], str)
        self._owner.updates.append(file_id)
        return _RecordedCall("update", {"_result": {"id": file_id, "appProperties": body["appProperties"]}})

    def create(self, *, body: dict[str, Any], fields: str) -> _RecordedCall:
        return _RecordedCall("create", {"_result": {"id": "created-id", "name": body["name"]}})


class _RecordedDrive:
    """Minimal Drive service double capturing queries and any update issued."""

    def __init__(self, entries: object) -> None:
        self.entries = entries
        self.queries: list[str] = []
        self.updates: list[str] = []

    def files(self) -> _RecordedFiles:
        return _RecordedFiles(self)


def _as_drive_resource(drive: _RecordedDrive) -> DriveResource:
    """Name the vendor type the recorded double stands in for.

    ``DriveResource`` is ``@typing.type_check_only``, so the double cannot
    subclass it; the cast lives here alone rather than at each call site,
    and the double stays concrete so tests can still read ``queries`` and
    ``updates`` off it.
    """
    return cast("DriveResource", drive)


def _owned(entry_id: str | None, name: str = "target") -> dict[str, Any]:
    entry: dict[str, Any] = {"name": name, "appProperties": {OWNERSHIP_KEY: OWNERSHIP_VALUE}}
    if entry_id is not None:
        entry["id"] = entry_id
    return entry


def test_apostrophe_in_name_is_escaped_into_the_query_literal() -> None:
    query = build_owned_entry_query(parent_id="root", name="va'ult", mime_type=_FOLDER_MIME)
    assert "name = 'va\\'ult'" in query
    assert "name = 'va'ult'" not in query


def test_query_builder_escapes_parent_id_name_and_mime_literals() -> None:
    query = build_owned_entry_query(parent_id="root'\\id", name="va'ult", mime_type="mime'type")

    assert query == (
        "'root\\'\\\\id' in parents and name = 'va\\'ult' and mimeType = 'mime\\'type' and trashed = false"
    )


def test_folder_lookup_escapes_the_configured_name_on_the_real_call_path() -> None:
    """The escaping reaches the query the production lookup actually sends."""
    drive = _RecordedDrive([])
    _find_folder(_as_drive_resource(drive), parent_id="root", name="va'ult")
    assert drive.queries == [build_owned_entry_query(parent_id="root", name="va'ult", mime_type=_FOLDER_MIME)]
    assert "va\\'ult" in drive.queries[0]


def test_spreadsheet_lookup_escapes_the_configured_name_identically() -> None:
    """Both lookups escape through the one shared query builder."""
    drive = _RecordedDrive([])
    _find_spreadsheet(_as_drive_resource(drive), parent_id="folder", name="plan's book")
    assert "plan\\'s book" in drive.queries[0]
    assert _SPREADSHEET_MIME in drive.queries[0]


@pytest.mark.parametrize("bad_id", [None, "", "   "])
def test_owned_entry_without_a_usable_id_is_refused_not_indexed(bad_id: str | None) -> None:
    """An id-less owned entry raises a typed storage error, never ``KeyError``."""
    drive = _RecordedDrive([_owned(bad_id)])
    with pytest.raises(OutboundStorageValidationError) as excinfo:
        _find_folder(_as_drive_resource(drive), parent_id="root", name="target")
    assert "without a usable id" in str(excinfo.value)
    _assert_closed_operator_review(
        excinfo.value,
        condition_id="google.drive_entry.identifier_valid",
        facts={
            "parent_id": "root",
            "entry_name": "target",
            "identifier_present": False,
            "identifier_type": type(bad_id).__name__,
        },
    )


def test_spreadsheet_lookup_refuses_an_id_less_owned_entry() -> None:
    """The spreadsheet path enforces the same identity contract as the folder path."""
    drive = _RecordedDrive([_owned(None)])
    with pytest.raises(OutboundStorageValidationError):
        _find_spreadsheet(_as_drive_resource(drive), parent_id="folder", name="target")


def test_unmarked_entry_without_an_id_is_refused_without_any_update() -> None:
    """An unmarked entry is refused on ownership before its identity matters."""
    drive = _RecordedDrive([{"name": "target"}])
    with pytest.raises(OutboundStorageConflictError):
        _find_folder(_as_drive_resource(drive), parent_id="root", name="target")
    assert drive.updates == []


def test_non_list_files_response_is_an_explicit_validation_outcome() -> None:
    with pytest.raises(OutboundStorageValidationError) as excinfo:
        _find_folder(_as_drive_resource(_RecordedDrive({"id": "not-a-list"})), parent_id="root", name="target")

    _assert_closed_operator_review(
        excinfo.value,
        condition_id="google.drive_entry.list_response_valid",
        facts={"parent_id": "root", "entry_name": "target", "entries_list_valid": False},
    )


def test_non_mapping_drive_entry_is_an_explicit_validation_outcome() -> None:
    with pytest.raises(OutboundStorageValidationError) as excinfo:
        _find_folder(_as_drive_resource(_RecordedDrive(["not-a-mapping"])), parent_id="root", name="target")

    _assert_closed_operator_review(
        excinfo.value,
        condition_id="google.drive_entry.entry_mapping_valid",
        facts={"parent_id": "root", "entry_name": "target", "entry_index": 0, "entry_mapping": False},
    )


def test_non_mapping_ownership_metadata_is_an_explicit_validation_outcome() -> None:
    with pytest.raises(OutboundStorageValidationError) as excinfo:
        _find_folder(
            _as_drive_resource(
                _RecordedDrive([{"id": "candidate", "name": "target", "appProperties": "not-a-mapping"}])
            ),
            parent_id="root",
            name="target",
        )

    _assert_closed_operator_review(
        excinfo.value,
        condition_id="google.drive_entry.ownership_metadata_valid",
        facts={
            "parent_id": "root",
            "entry_name": "target",
            "entry_index": 0,
            "ownership_metadata_mapping": False,
        },
    )


def test_unmarked_entry_is_refused_on_both_lookups_and_never_stamped() -> None:
    """A same-named entry without the marker is not adopted, and nothing is written to it."""
    folder_drive = _RecordedDrive([{"id": "unmarked-1", "name": "target"}])
    with pytest.raises(OutboundStorageConflictError) as folder_error:
        _find_folder(_as_drive_resource(folder_drive), parent_id="root", name="target")
    _assert_closed_operator_review(
        folder_error.value,
        condition_id="google.drive_entry.ownership_aligned",
        facts={"parent_id": "root", "entry_name": "target", "ownership_aligned": False},
    )
    assert folder_drive.updates == []
    spreadsheet_drive = _RecordedDrive([{"id": "unmarked-2", "name": "target", "appProperties": {}}])
    with pytest.raises(OutboundStorageConflictError) as spreadsheet_error:
        _find_spreadsheet(_as_drive_resource(spreadsheet_drive), parent_id="folder", name="target")
    _assert_closed_operator_review(
        spreadsheet_error.value,
        condition_id="google.drive_entry.ownership_aligned",
        facts={"parent_id": "folder", "entry_name": "target", "ownership_aligned": False},
    )
    assert spreadsheet_drive.updates == []


def test_foreign_owned_entry_is_refused_on_both_lookups() -> None:
    """Foreign Drive content is never adopted, by either lookup."""
    foreign = [{"id": "foreign-1", "name": "target", "appProperties": {"someone_else": "yes"}}]
    with pytest.raises(OutboundStorageConflictError) as folder_error:
        _find_folder(_as_drive_resource(_RecordedDrive(list(foreign))), parent_id="root", name="target")
    _assert_closed_operator_review(
        folder_error.value,
        condition_id="google.drive_entry.ownership_aligned",
        facts={"parent_id": "root", "entry_name": "target", "ownership_aligned": False},
    )
    with pytest.raises(OutboundStorageConflictError) as spreadsheet_error:
        _find_spreadsheet(_as_drive_resource(_RecordedDrive(list(foreign))), parent_id="folder", name="target")
    _assert_closed_operator_review(
        spreadsheet_error.value,
        condition_id="google.drive_entry.ownership_aligned",
        facts={"parent_id": "folder", "entry_name": "target", "ownership_aligned": False},
    )


def test_owned_entry_with_a_usable_id_round_trips() -> None:
    """The positive control: a well-formed owned entry is returned unchanged."""
    drive = _RecordedDrive([_owned("owned-1")])
    found = _find_folder(_as_drive_resource(drive), parent_id="root", name="target")
    assert found is not None
    assert require_drive_entry_id(found, name="target", parent_id="root") == "owned-1"
    assert drive.updates == []


def test_missing_entry_returns_none() -> None:
    """An empty listing is a legitimate absence, not a refusal."""
    assert _find_folder(_as_drive_resource(_RecordedDrive([])), parent_id="root", name="target") is None
    assert _find_spreadsheet(_as_drive_resource(_RecordedDrive([])), parent_id="folder", name="target") is None
