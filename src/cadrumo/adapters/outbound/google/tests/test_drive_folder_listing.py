"""Real-client tests for :func:`list_drive_folder_documents`.

The Drive-folder bulk sweep (#262, Drive half) lists the PDF/image children
of a ``drive.file``-reachable folder so a caller can bulk-fetch every
invoice in one sweep. This gate exercises the listing end to end against a
real ``google-api-python-client`` resource pointed at a local HTTP endpoint
(no mocks of the Google client itself):

* a folder with N PDF/image children and a nested folder returns exactly the
  N documents, filtering the folder entry out and never crawling into it;
* pagination via ``nextPageToken`` is followed until exhausted, and every
  page's ``files`` are aggregated;
* a non-invoice MIME type child (e.g. a spreadsheet) is filtered out and
  counted in ``skipped_non_document_count`` rather than silently dropped;
* a 403 response is translated to the typed, scope-named permission refusal
  the single-document resolver uses, never a bare transport error.
"""

from __future__ import annotations

import pytest

from .....core import ActionConditionality, NoRecoveryOutcome
from ...storage import OutboundStorageNetworkError, OutboundStoragePermissionError, OutboundStorageValidationError
from .._document_link_resolver import list_drive_folder_documents
from ._drive_media_server import drive_files_list_endpoint

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FOLDER_ID = "1FoldEr12345678901234567890AB"


def _assert_closed_outcome(
    error: BaseException,
    *,
    condition_id: str,
    facts: dict[str, str | int | bool],
    outcome: NoRecoveryOutcome,
) -> None:
    """Assert a fact-only refusal whose no-recovery contract is explicit."""
    verdict = error.terminal_precondition_verdict
    assert verdict.failed_condition_id == condition_id
    assert verdict.evidence[0].values == facts
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.missing_argument_names == ()
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is outcome


def test_lists_pdf_and_image_children_and_skips_nested_folder() -> None:
    """A folder with 2 PDFs, 1 image, and a nested folder returns 3 documents."""
    page = {
        "files": [
            {"id": "file-pdf-1", "name": "invoice-1.pdf", "mimeType": "application/pdf"},
            {"id": "file-pdf-2", "name": "invoice-2.pdf", "mimeType": "application/pdf"},
            {"id": "file-img-1", "name": "receipt.jpg", "mimeType": "image/jpeg"},
            {"id": "nested-folder", "name": "subfolder", "mimeType": "application/vnd.google-apps.folder"},
        ],
    }
    with drive_files_list_endpoint(pages=[page]) as endpoint:
        listing = list_drive_folder_documents(folder_id=_FOLDER_ID, credentials=None, service=endpoint.service)

    assert listing.skipped_non_document_count == 0
    assert {document.file_id for document in listing.documents} == {"file-pdf-1", "file-pdf-2", "file-img-1"}
    assert len(endpoint.requested_queries) == 1


def test_filters_non_invoice_mime_type_and_counts_it_skipped() -> None:
    """A spreadsheet child is filtered out and counted, not silently dropped."""
    page = {
        "files": [
            {"id": "file-pdf-1", "name": "invoice.pdf", "mimeType": "application/pdf"},
            {
                "id": "file-sheet-1",
                "name": "expenses.xlsx",
                "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            },
        ],
    }
    with drive_files_list_endpoint(pages=[page]) as endpoint:
        listing = list_drive_folder_documents(folder_id=_FOLDER_ID, credentials=None, service=endpoint.service)

    assert [document.file_id for document in listing.documents] == ["file-pdf-1"]
    assert listing.skipped_non_document_count == 1


def test_follows_pagination_until_exhausted() -> None:
    """Every page's files are aggregated; the sweep stops when nextPageToken is absent."""
    page_one = {
        "files": [{"id": "file-1", "name": "a.pdf", "mimeType": "application/pdf"}],
        "nextPageToken": "page-2",
    }
    page_two = {
        "files": [{"id": "file-2", "name": "b.pdf", "mimeType": "application/pdf"}],
    }
    with drive_files_list_endpoint(pages=[page_one, page_two]) as endpoint:
        listing = list_drive_folder_documents(folder_id=_FOLDER_ID, credentials=None, service=endpoint.service)

    assert {document.file_id for document in listing.documents} == {"file-1", "file-2"}
    assert len(endpoint.requested_queries) == 2


def test_repeated_page_token_refuses_before_an_unbounded_drive_sweep() -> None:
    """A real generated client sees two pages before the repeated token is refused."""
    repeated_page = {"files": [], "nextPageToken": "again"}
    with (
        drive_files_list_endpoint(pages=[repeated_page, repeated_page]) as endpoint,
        pytest.raises(OutboundStorageNetworkError, match="repeated nextPageToken"),
    ):
        list_drive_folder_documents(folder_id=_FOLDER_ID, credentials=None, service=endpoint.service)
    assert len(endpoint.requested_queries) == 2


@pytest.mark.parametrize(
    ("entry", "entry_mapping"),
    (
        ({"name": "invoice.pdf", "mimeType": "application/pdf"}, True),
        ({"id": None, "name": "invoice.pdf", "mimeType": "application/pdf"}, True),
        ({"id": "", "name": "invoice.pdf", "mimeType": "application/pdf"}, True),
        ({"id": "file-1", "mimeType": "application/pdf"}, True),
        ({"id": "file-1", "name": "", "mimeType": "application/pdf"}, True),
        ({"id": "file-1", "name": "invoice.pdf"}, True),
        ({"id": "file-1", "name": "invoice.pdf", "mimeType": ""}, True),
        ("not-a-file-mapping", False),
    ),
)
def test_malformed_successful_file_entry_refuses_at_the_drive_boundary(entry: object, entry_mapping: bool) -> None:
    """A real generated client maps malformed 2xx file rows to a typed error."""
    with (
        drive_files_list_endpoint(pages=[{"files": [entry]}]) as endpoint,
        pytest.raises(OutboundStorageValidationError, match="malformed file entry") as excinfo,
    ):
        list_drive_folder_documents(folder_id=_FOLDER_ID, credentials=None, service=endpoint.service)

    assert excinfo.value.context == {
        "action": "drive.files.list",
        "folder_id": _FOLDER_ID,
        "entry_index": "0",
    }
    _assert_closed_outcome(
        excinfo.value,
        condition_id="google.document_link.folder_entry_valid",
        facts={"folder_id": _FOLDER_ID, "entry_index": 0, "entry_mapping": entry_mapping},
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_non_list_successful_files_field_is_a_validation_outcome() -> None:
    with (
        drive_files_list_endpoint(pages=[{"files": {"id": "not-a-list"}}]) as endpoint,
        pytest.raises(OutboundStorageValidationError, match="non-list files field") as excinfo,
    ):
        list_drive_folder_documents(folder_id=_FOLDER_ID, credentials=None, service=endpoint.service)

    _assert_closed_outcome(
        excinfo.value,
        condition_id="google.document_link.folder_files_list_valid",
        facts={"folder_id": _FOLDER_ID, "files_list_valid": False},
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_empty_folder_returns_no_documents() -> None:
    """An empty (or fully-filtered) folder returns zero documents, not an error."""
    with drive_files_list_endpoint(pages=[{"files": []}]) as endpoint:
        listing = list_drive_folder_documents(folder_id=_FOLDER_ID, credentials=None, service=endpoint.service)

    assert listing.documents == ()
    assert listing.skipped_non_document_count == 0


def test_permission_denied_folder_refuses_with_scope_named_error() -> None:
    """A 403 (folder outside drive.file) refuses with the scope-named permission error."""
    with (
        drive_files_list_endpoint(pages=[{"error": {"code": 403, "message": "denied"}}], status=403) as endpoint,
        pytest.raises(OutboundStoragePermissionError) as excinfo,
    ):
        list_drive_folder_documents(folder_id=_FOLDER_ID, credentials=None, service=endpoint.service)

    assert excinfo.value.context is not None
    assert excinfo.value.context["required_scope"] == "https://www.googleapis.com/auth/drive.readonly"
    assert excinfo.value.context["folder_id"] == _FOLDER_ID
    _assert_closed_outcome(
        excinfo.value,
        condition_id="google.document_link.folder_scope_sufficient",
        facts={
            "folder_id": _FOLDER_ID,
            "required_scope": "https://www.googleapis.com/auth/drive.readonly",
            "scope_sufficient": False,
        },
        outcome=NoRecoveryOutcome.SAFETY,
    )
