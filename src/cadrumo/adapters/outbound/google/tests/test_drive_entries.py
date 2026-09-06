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
- both lookups run the same ownership/backfill/refusal policy, so the
  behaviour cannot drift between them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import DriveResource

from .....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ....outbound.storage.errors import (
    OutboundStorageConflictError,
    OutboundStorageError,
    OutboundStorageValidationError,
)
from ..calc_sheets_apply import _ensure_folder, _find_folder, _find_spreadsheet
from ..drive_entries import (
    OWNERSHIP_KEY,
    OWNERSHIP_VALUE,
    build_owned_entry_query,
    escape_drive_query_name,
    require_drive_entry_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

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

    def list(self, *, q: str, fields: str, pageSize: int) -> _RecordedCall:  # noqa: N803 - Drive API kwarg name
        self._owner.queries.append(q)
        return _RecordedCall("list", {"_result": {"files": self._owner.entries}})

    def update(self, *, fileId: str, body: dict[str, Any], fields: str) -> _RecordedCall:  # noqa: N803 - Drive API kwarg name
        self._owner.updates.append(fileId)
        return _RecordedCall("update", {"_result": {"id": fileId, "appProperties": body["appProperties"]}})

    def create(self, *, body: dict[str, Any], fields: str) -> _RecordedCall:
        return _RecordedCall("create", {"_result": {"id": "created-id", "name": body["name"]}})


class _RecordedDrive:
    """Minimal Drive service double capturing queries and backfill updates."""

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
    """A name containing an apostrophe must not close the query literal early."""
    assert escape_drive_query_name("va'ult") == "va\\'ult"
    query = build_owned_entry_query(parent_id="root", name="va'ult", mime_type=_FOLDER_MIME)
    assert "name = 'va\\'ult'" in query
    assert "name = 'va'ult'" not in query


def test_backslash_is_escaped_before_the_apostrophe_escape() -> None:
    """The backslash replacement must run first so it cannot double-escape."""
    assert escape_drive_query_name("a\\b") == "a\\\\b"
    assert escape_drive_query_name("a\\'b") == "a\\\\\\'b"


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


def test_ensure_folder_refuses_an_id_less_owned_entry() -> None:
    """The caller that previously raised ``KeyError('id')`` now refuses cleanly."""
    drive = _RecordedDrive([_owned(None)])
    with pytest.raises(OutboundStorageValidationError):
        _ensure_folder(_as_drive_resource(drive), parent_id="root", name="target")


def test_spreadsheet_lookup_refuses_an_id_less_owned_entry() -> None:
    """The spreadsheet path enforces the same identity contract as the folder path."""
    drive = _RecordedDrive([_owned(None)])
    with pytest.raises(OutboundStorageValidationError):
        _find_spreadsheet(_as_drive_resource(drive), parent_id="folder", name="target")


def test_backfill_does_not_issue_an_update_for_an_id_less_entry() -> None:
    """Identity is validated before the marker-backfill call is issued."""
    drive = _RecordedDrive([{"name": "target"}])
    with pytest.raises(OutboundStorageValidationError):
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


def test_unmarked_entry_is_backfilled_and_adopted() -> None:
    """A pre-marker entry this app created is stamped, then returned."""
    drive = _RecordedDrive([{"id": "legacy-1", "name": "target"}])
    found = _find_folder(_as_drive_resource(drive), parent_id="root", name="target")
    assert found is not None
    assert found["id"] == "legacy-1"
    assert drive.updates == ["legacy-1"]


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
