"""One unreachable file is recorded; a broken transport ends the sweep.

The distinction is the whole point. A bulk pull that continues past ANY failure
produces a report claiming every remaining document was individually refused for
a scope reason, when the real cause was one connection dropping — wrong about
every row, and stated with the same confidence as the rows that are right.

A sweep that continues past NONE of them is equally useless: ``drive.file`` can
only see files the app created or the operator picked, so an ordinary folder
contains unreachable documents by construction and the first one would abort the
run.
"""

from __future__ import annotations

import pytest

from ....adapters.outbound.google.document_link_resolver import DriveFolderDocument
from ....adapters.outbound.storage.errors import (
    OutboundStorageNetworkError,
    OutboundStoragePermissionError,
    OutboundStorageValidationError,
)
from ..evidence_sweep import EvidenceSweepRefusal, classify_evidence_sweep_failure, sweep_evidence_folder

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_a_file_outside_the_granted_scope_refuses_only_that_file() -> None:
    """The 403/404 case, and the only one the sweep survives."""
    error = OutboundStoragePermissionError(
        "Drive file 'abc' is not reachable under the drive.file scope",
        context={"file_id": "abc", "required_scope": "drive.readonly"},
    )

    assert classify_evidence_sweep_failure(error) is EvidenceSweepRefusal.FILE_NOT_REACHABLE


def test_a_transport_failure_ends_the_sweep() -> None:
    """Not a fact about the document, so it must not become a per-file row.

    Recorded per-file, a dropped connection would report the whole remaining
    folder as scope-refused and send the operator to grant a scope that would
    not have helped.
    """
    error = OutboundStorageNetworkError("Drive files.get_media failed", context={"file_id": "abc"})

    assert classify_evidence_sweep_failure(error) is None


def test_a_malformed_media_payload_ends_the_sweep() -> None:
    """A non-bytes body says the transport is misbehaving, not that the file is private."""
    error = OutboundStorageValidationError(
        "Drive files.get_media returned a non-bytes payload",
        context={"file_id": "abc"},
    )

    assert classify_evidence_sweep_failure(error) is None


def test_an_unrelated_failure_ends_the_sweep() -> None:
    """The default is to propagate.

    A classifier that swallowed the unknown case would turn a defect anywhere in
    the fetch-and-store path into a quiet "refused" row, which is the failure
    mode this whole module exists to prevent.
    """
    assert classify_evidence_sweep_failure(RuntimeError("something else entirely")) is None


def test_exactly_one_refusal_continues_a_sweep() -> None:
    """Pinned as a count so a second per-file refusal has to argue for itself.

    Widening this set is how a transport problem quietly becomes a folder full
    of confident, wrong per-file rows.
    """
    assert list(EvidenceSweepRefusal) == [EvidenceSweepRefusal.FILE_NOT_REACHABLE]


def _document(file_id: str, name: str = "factura.pdf") -> DriveFolderDocument:
    return DriveFolderDocument.model_validate({"id": file_id, "name": name, "mimeType": "application/pdf"})


def _unreachable() -> OutboundStoragePermissionError:
    return OutboundStoragePermissionError(
        "Drive file is not reachable under the drive.file scope",
        context={"required_scope": "drive.readonly"},
    )


def test_one_unreachable_file_does_not_abort_the_rest_of_the_sweep() -> None:
    """The behaviour the CLI documented and did not implement.

    Under ``drive.file`` the app sees only files it created or the operator
    picked, so an ordinary folder contains unreachable children by
    construction. Aborting on the first one made bulk pull useless on realistic
    input, and the traceback told the operator nothing about the files that
    had already been stored.
    """
    fetched: list[str] = []

    def fetch(document: DriveFolderDocument) -> str:
        if document.file_id == "b":
            raise _unreachable()
        fetched.append(document.file_id)
        return f"att-{document.file_id}"

    sweep = sweep_evidence_folder(documents=[_document("a"), _document("b"), _document("c")], fetch=fetch)

    assert fetched == ["a", "c"]
    assert sweep.fetched_count == 2
    assert sweep.refused_count == 1


def test_every_listed_document_gets_exactly_one_row_in_order() -> None:
    """The report is against the folder, not against what happened to succeed.

    A caller reconciling the sweep with the folder it listed needs the refused
    files present and positioned, not omitted.
    """

    def fetch(document: DriveFolderDocument) -> str:
        if document.file_id == "b":
            raise _unreachable()
        return f"att-{document.file_id}"

    sweep = sweep_evidence_folder(documents=[_document("a"), _document("b"), _document("c")], fetch=fetch)

    assert [row.file_id for row in sweep.documents] == ["a", "b", "c"]
    assert sweep.documents[1].refusal is EvidenceSweepRefusal.FILE_NOT_REACHABLE
    assert sweep.documents[1].attachment_id is None


def test_a_transport_failure_stops_the_sweep_at_the_document_that_failed() -> None:
    """It must not be recorded per-file, and the rest must not be attempted.

    Continuing would call a dead transport once per remaining document and
    report the whole folder as scope-refused.
    """
    attempted: list[str] = []

    def fetch(document: DriveFolderDocument) -> str:
        attempted.append(document.file_id)
        if document.file_id == "b":
            raise OutboundStorageNetworkError("Drive files.get_media failed", context={})
        return f"att-{document.file_id}"

    with pytest.raises(OutboundStorageNetworkError):
        sweep_evidence_folder(documents=[_document("a"), _document("b"), _document("c")], fetch=fetch)

    assert attempted == ["a", "b"]


def test_the_counts_cannot_disagree_with_the_rows() -> None:
    """Derived, not tracked — which is the bug that shipped.

    The CLI kept ``refused_count`` in a separate variable it never
    incremented, so the summary claimed zero refusals while the rows printed
    underneath it said otherwise.
    """

    def fetch(document: DriveFolderDocument) -> str:
        if document.file_id in {"b", "d"}:
            raise _unreachable()
        return f"att-{document.file_id}"

    sweep = sweep_evidence_folder(documents=[_document(x) for x in "abcd"], fetch=fetch)

    assert sweep.fetched_count == sum(1 for row in sweep.documents if row.fetched)
    assert sweep.refused_count == sum(1 for row in sweep.documents if row.refusal is not None)
    assert sweep.fetched_count + sweep.refused_count == len(sweep.documents)


def test_a_row_never_claims_both_an_attachment_and_a_refusal() -> None:
    """Fetched and refused are mutually exclusive, and each row proves it."""

    def fetch(document: DriveFolderDocument) -> str:
        if document.file_id == "b":
            raise _unreachable()
        return f"att-{document.file_id}"

    sweep = sweep_evidence_folder(documents=[_document("a"), _document("b")], fetch=fetch)

    for row in sweep.documents:
        assert (row.attachment_id is None) != (row.refusal is None)


def test_an_empty_folder_sweeps_to_an_empty_report() -> None:
    """Nothing matched is not a failure, and its counts are zero, not absent."""
    sweep = sweep_evidence_folder(documents=[], fetch=lambda document: "unreachable")

    assert sweep.documents == ()
    assert sweep.fetched_count == 0
    assert sweep.refused_count == 0
