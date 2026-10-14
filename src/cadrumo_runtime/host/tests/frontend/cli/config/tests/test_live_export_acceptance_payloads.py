"""Live acceptance refuses malformed CLI evidence before using identifiers."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from .live_export_acceptance import _cli_result, _text_field

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_cli_result_preserves_saved_revision_evidence() -> None:
    result = {
        "calculation_revision_id": "a" * 64,
        "saved": True,
        "input_values_by_casilla_id": {"05": "123.4500", "06": "0.00"},
        "publication": None,
    }
    assert (
        _cli_result(json.dumps({"active_profile": "Session02 Google Review", "result": result}), "saved-revision")
        == result
    )


@pytest.mark.parametrize("result", [None, [], "revision", 1, True])
def test_cli_result_refuses_nonobject_result(result: object) -> None:
    with pytest.raises(ValidationError):
        _cli_result(json.dumps({"active_profile": "Session02 Google Review", "result": result}), "saved-revision")


@pytest.mark.parametrize("profile", [None, "another profile", 1])
def test_cli_result_refuses_foreign_profile(profile: object) -> None:
    with pytest.raises(RuntimeError, match="unexpected CLI profile/result"):
        _cli_result(json.dumps({"active_profile": profile, "result": {}}), "saved-revision")


@pytest.mark.parametrize("payload", ["[]", "null", '"revision"', "{"])
def test_cli_result_refuses_invalid_envelope(payload: str) -> None:
    with pytest.raises(ValidationError):
        _cli_result(payload, "saved-revision")


@pytest.mark.parametrize("identifier", [None, 1, True, [], {}, ""])
def test_acceptance_refuses_nontext_identifier(identifier: object) -> None:
    with pytest.raises(RuntimeError, match="requires nonempty text"):
        _text_field({"calculation_revision_id": identifier}, "calculation_revision_id")
