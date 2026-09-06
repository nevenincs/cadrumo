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

from ....adapters.outbound.storage.errors import (
    OutboundStorageNetworkError,
    OutboundStoragePermissionError,
    OutboundStorageValidationError,
)
from ..evidence_sweep import EvidenceSweepRefusal, classify_evidence_sweep_failure

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
