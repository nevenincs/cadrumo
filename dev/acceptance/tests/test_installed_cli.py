"""The shared installed CLI runner keeps a refusal's typed reason and nothing else."""

from __future__ import annotations

import pytest

from ..installed_cli import CommandEvidence, typed_refusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _envelope(error: object) -> dict[str, object]:
    return {"status": "error", "error": error}


def test_a_custody_refusal_names_its_category_and_typed_reason() -> None:
    document = _envelope(
        {"code": "REFUSED_STORAGE_PROFILE_CUSTODY", "category": "REFUSED", "context": {"refusal": "KDF_RESOURCE_LIMIT"}}
    )

    assert typed_refusal(document) == "REFUSED/KDF_RESOURCE_LIMIT"


def test_a_reason_without_a_token_shaped_category_is_kept_alone() -> None:
    document = _envelope(
        {"code": "X", "category": "refused softly", "context": {"refusal": "KDF_SUPERVISION_UNAVAILABLE"}}
    )

    assert typed_refusal(document) == "KDF_SUPERVISION_UNAVAILABLE"


@pytest.mark.parametrize(
    "error",
    [
        None,
        "free text",
        {"code": "REFUSED_CLI_BOUNDARY", "category": "REFUSED", "context": None},
        {"code": "X", "category": "REFUSED", "context": {"refusal": "the store at C:\\Users\\someone is locked"}},
        {"code": "X", "category": "REFUSED", "context": {"refusal": 42}},
        {"code": "X", "category": "REFUSED", "context": {"other": "KDF_RESOURCE_LIMIT"}},
    ],
)
def test_anything_but_an_enum_token_reason_is_dropped(error: object) -> None:
    assert typed_refusal(_envelope(error)) is None


def test_evidence_built_positionally_still_compares_equal_without_a_refusal() -> None:
    assert CommandEvidence("app ledger list", 2, "non_json_failure", ()) == CommandEvidence(
        command="app ledger list", returncode=2, status="non_json_failure", notice_codes=(), refusal=None
    )
