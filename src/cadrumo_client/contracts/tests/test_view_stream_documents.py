"""View stream control documents accept and refuse exactly as the shared vectors say."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from ..view_stream import (
    VIEW_CREDIT_MAX_IMAGES,
    VIEW_IMAGE_MAX_BYTES,
    ViewClosedReason,
    ViewDownstreamFrame,
    ViewNoticeCode,
    ViewUpstreamFrame,
)
from ..view_transfer import (
    VIEW_MAX_TRANSFER_ID,
    VIEW_MAX_TRANSFER_SIZE,
    VIEW_TRANSFER_CREDIT_MAX_CHUNKS,
    ViewConnectionDownstreamFrame,
    ViewConnectionUpstreamFrame,
    ViewDownloadOutcome,
    ViewFileChooserOutcome,
    ViewTransferDirection,
)
from .view_stream_vector_source import VECTORS_PATH, main, render

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_VECTORS: dict[str, Any] = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
_FRAMES: dict[str, type[ViewConnectionDownstreamFrame] | type[ViewConnectionUpstreamFrame]] = {
    "downstream": ViewConnectionDownstreamFrame,
    "upstream": ViewConnectionUpstreamFrame,
}
_IMAGE_STREAM_FRAMES: dict[str, type[ViewDownstreamFrame] | type[ViewUpstreamFrame]] = {
    "downstream": ViewDownstreamFrame,
    "upstream": ViewUpstreamFrame,
}
_TRANSFER_KINDS = frozenset(
    {
        "view.download",
        "view.file_chooser",
        "view.download_answer",
        "view.file_chooser_answer",
        "view.upload",
        "view.transfer_complete",
        "view.transfer_credit",
        "view.transfer_cancel",
    }
)


def _validate(case: dict[str, Any]) -> dict[str, Any]:
    frame = _FRAMES[case["direction"]].model_validate_json(json.dumps(case["document"]))
    return frame.root.model_dump(mode="json", exclude_none=True)


def test_the_vectors_file_is_its_owners_current_output() -> None:
    assert VECTORS_PATH.read_text(encoding="utf-8") == render()
    assert main(["--check"]) == 0


def test_the_layout_matches_the_contract_bounds() -> None:
    layout = _VECTORS["layout"]
    assert layout["image_max_bytes"] == VIEW_IMAGE_MAX_BYTES
    assert layout["credit_max_images"] == VIEW_CREDIT_MAX_IMAGES
    assert layout["chunk_header_bytes"] + layout["chunk_body_bytes"] == layout["frame_max_bytes"]
    assert layout["transfer_credit_max_chunks"] == VIEW_TRANSFER_CREDIT_MAX_CHUNKS
    assert layout["transfer_id_max"] == VIEW_MAX_TRANSFER_ID
    assert layout["transfer_size_max"] == VIEW_MAX_TRANSFER_SIZE == 2**64 - 1


@pytest.mark.parametrize("case", _VECTORS["documents"]["accepted"], ids=lambda case: case["name"])
def test_an_accepted_document_round_trips_unchanged(case: dict[str, Any]) -> None:
    assert _validate(case) == case["document"]


@pytest.mark.parametrize("case", _VECTORS["documents"]["refused"], ids=lambda case: case["name"])
def test_a_refused_document_is_refused(case: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _validate(case)


def test_the_accepted_vectors_cover_every_document_kind() -> None:
    kinds = {(case["direction"], case["document"]["kind"]) for case in _VECTORS["documents"]["accepted"]}
    assert kinds == {
        ("downstream", "view.image"),
        ("downstream", "view.state"),
        ("downstream", "view.notice"),
        ("downstream", "view.closed"),
        ("upstream", "view.credit"),
        ("upstream", "view.input"),
        ("upstream", "view.navigate"),
        ("upstream", "view.resize"),
        ("upstream", "view.dialog"),
        ("upstream", "view.close"),
        ("downstream", "view.download"),
        ("downstream", "view.file_chooser"),
        ("downstream", "view.transfer_complete"),
        ("downstream", "view.transfer_credit"),
        ("downstream", "view.transfer_cancel"),
        ("upstream", "view.download_answer"),
        ("upstream", "view.file_chooser_answer"),
        ("upstream", "view.upload"),
        ("upstream", "view.transfer_complete"),
        ("upstream", "view.transfer_credit"),
        ("upstream", "view.transfer_cancel"),
    }
    events = {
        case["document"]["event"]["type"] for case in _VECTORS["documents"]["accepted"] if "event" in case["document"]
    }
    assert events == {"pointer", "wheel", "key", "text"}


def test_every_notice_code_and_closed_reason_has_one_valid_spelling() -> None:
    dialog = {"dialog_id": 1, "dialog_kind": "alert", "message": ""}
    for code in ViewNoticeCode:
        document: dict[str, Any] = {"kind": "view.notice", "code": code.value}
        if code is ViewNoticeCode.DIALOG_OPENED:
            document["dialog"] = dialog
        assert _validate({"direction": "downstream", "document": document}) == document
    for reason in ViewClosedReason:
        document = {"kind": "view.closed", "reason": reason.value}
        assert _validate({"direction": "downstream", "document": document}) == document


def test_the_image_stream_frames_stay_closed_to_transfer_documents() -> None:
    for case in _VECTORS["documents"]["accepted"]:
        frame = _IMAGE_STREAM_FRAMES[case["direction"]]
        if case["document"]["kind"] in _TRANSFER_KINDS:
            with pytest.raises(ValidationError):
                frame.model_validate_json(json.dumps(case["document"]))
        else:
            assert (
                frame.model_validate_json(json.dumps(case["document"])).root.model_dump(mode="json", exclude_none=True)
                == case["document"]
            )


def test_every_download_and_chooser_outcome_has_one_valid_spelling() -> None:
    for download in ViewDownloadOutcome:
        document: dict[str, Any] = {"kind": "view.download_answer", "transfer_id": 1, "outcome": download.value}
        assert _validate({"direction": "upstream", "document": document}) == document
    for chooser in ViewFileChooserOutcome:
        files = 0 if chooser is ViewFileChooserOutcome.CANCELLED else 2
        document = {"kind": "view.file_chooser_answer", "chooser_id": 1, "outcome": chooser.value, "file_count": files}
        assert _validate({"direction": "upstream", "document": document}) == document
    for direction in ViewTransferDirection:
        document = {"kind": "view.transfer_cancel", "direction": direction.value, "transfer_id": 1}
        assert _validate({"direction": "downstream", "document": document}) == document


def test_no_transfer_document_bounds_a_files_size_count_or_rate() -> None:
    sha256 = "0" * 64
    largest = {"kind": "view.transfer_complete", "transfer_id": 1, "size": VIEW_MAX_TRANSFER_SIZE, "sha256": sha256}
    assert _validate({"direction": "downstream", "document": largest}) == largest
    many = {
        "kind": "view.file_chooser_answer",
        "chooser_id": 1,
        "outcome": "supplied",
        "file_count": VIEW_MAX_TRANSFER_ID,
    }
    assert _validate({"direction": "upstream", "document": many}) == many
