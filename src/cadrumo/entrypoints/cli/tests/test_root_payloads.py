"""Contract tests for flat root-callback output payloads."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....application.operator_surface import RootLandingReport, build_help_document
from ....application.overview import OverviewStatusReport
from .._root_payloads import AppRootResult, RootStatusResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    "payload",
    (
        build_help_document("root").model_dump(mode="json"),
        RootLandingReport(
            active_profile=None,
            command="aeat config profile create NAME",
            message="Create a profile before starting tax work.",
        ).model_dump(mode="json"),
        OverviewStatusReport(
            transactions=0,
            invoices=0,
            drafts=0,
            unreadable_rows=0,
        ).model_dump(mode="json"),
    ),
)
def test_root_status_payload_preserves_each_canonical_branch(payload: dict[str, object]) -> None:
    assert RootStatusResult.model_validate(payload).model_dump(mode="json") == payload


@pytest.mark.parametrize(
    "payload",
    ({}, {"bogus": "value"}, {"transactions": -1, "unexpected": True}),
)
def test_root_status_payload_rejects_noncanonical_branches(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        RootStatusResult.model_validate(payload)


def test_app_root_payload_accepts_only_the_canonical_help_document() -> None:
    payload = build_help_document("app").model_dump(mode="json")

    assert AppRootResult.model_validate(payload).model_dump(mode="json") == payload
    with pytest.raises(ValidationError):
        AppRootResult.model_validate({"bogus": "value"})
