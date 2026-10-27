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
from .view_stream_vector_source import VECTORS_PATH, main, render

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_VECTORS: dict[str, Any] = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
_FRAMES: dict[str, type[ViewDownstreamFrame] | type[ViewUpstreamFrame]] = {
    "downstream": ViewDownstreamFrame,
    "upstream": ViewUpstreamFrame,
}


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
    }
    events = {
        case["document"]["event"]["type"] for case in _VECTORS["documents"]["accepted"] if "event" in case["document"]
    }
    assert events == {"pointer", "wheel", "key", "text"}


def test_every_notice_code_and_closed_reason_has_one_valid_spelling() -> None:
    offer = {"offer_id": "f" * 32, "url": "https://sede.agenciatributaria.gob.es/x"}
    dialog = {"dialog_id": 1, "dialog_kind": "alert", "message": ""}
    for code in ViewNoticeCode:
        document: dict[str, Any] = {"kind": "view.notice", "code": code.value}
        if code is ViewNoticeCode.DIALOG_OPENED:
            document["dialog"] = dialog
        elif code not in {ViewNoticeCode.REQUEST_REFUSED, ViewNoticeCode.INPUT_REFUSED}:
            document["offer"] = offer
        assert _validate({"direction": "downstream", "document": document}) == document
    for reason in ViewClosedReason:
        document = {"kind": "view.closed", "reason": reason.value}
        assert _validate({"direction": "downstream", "document": document}) == document
