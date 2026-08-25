"""The ledger review envelope must describe exactly one real outcome.

Canonical :class:`~application.ledger.models.LedgerReviewRow` requires a
content-addressed transaction id, a 10-character date, and non-empty amount,
description and status. ``LedgerReviewRowPayload`` redeclared those as
unconstrained strings, and ``LedgerReviewResult`` made every list and detail
field optional, so an empty envelope, a filter-only shape, or a half-populated
detail all validated with no branch invariant -- an operator could not tell an
empty result from a malformed one.

The valid list, empty and detail branches below are the positive controls: an
invariant that refused everything would pass every refusal case and fail those.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....application.ledger.models import LedgerReviewRow
from .._ledger_payloads import LedgerReviewResult, LedgerReviewRowPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TRANSACTION_ID = "c0ffee" + "0" * 58


def _row_fields(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": _TRANSACTION_ID,
        "date": "2026-05-01",
        "amount": "121.00",
        "description": "material oficina",
        "status": "pending",
    }
    base.update(overrides)
    return base


def test_a_canonical_row_projects_onto_the_transport_row() -> None:
    """Positive control: the shape the backend actually produces must validate."""
    canonical = LedgerReviewRow.model_validate(_row_fields())
    payload = LedgerReviewRowPayload(
        id=canonical.id,
        date=canonical.date,
        amount=canonical.amount,
        description=canonical.description,
        status=canonical.status,
    )

    assert payload.id == canonical.id
    assert payload.date == canonical.date
    assert payload.status == canonical.status


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": "bad"},
        {"id": "Z" * 64},
        {"date": "bad"},
        {"date": "2026-5-1"},
        {"amount": ""},
        {"description": ""},
        {"status": ""},
    ],
    ids=["short-id", "non-hex-id", "short-date", "unpadded-date", "blank-amount", "blank-description", "blank-status"],
)
def test_the_transport_row_refuses_what_the_canonical_row_refuses(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        LedgerReviewRowPayload.model_validate(_row_fields(**overrides))
    with pytest.raises(ValidationError):
        LedgerReviewRow.model_validate(_row_fields(**overrides))


def test_the_list_branch_validates() -> None:
    result = LedgerReviewResult.model_validate(
        {"rows": [_row_fields()], "filters": ["status=pending"]},
    )

    assert result.rows is not None
    assert len(result.rows) == 1
    assert result.id is None


def test_the_empty_result_branch_validates() -> None:
    """A positional id with no match is a real outcome, not a malformed envelope."""
    result = LedgerReviewResult.model_validate({"rows": [], "filters": []})

    assert result.rows == []
    assert result.filters == []


def test_the_detail_branch_validates() -> None:
    result = LedgerReviewResult.model_validate(
        {
            "id": _TRANSACTION_ID,
            "date": "2026-05-01",
            "amount": "121.00",
            "description": "material oficina",
            "review_status": "pending",
            "verbose": False,
        },
    )

    assert result.id == _TRANSACTION_ID
    assert result.rows is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"filters": []},
        {"rows": [_row_fields()]},
        {"verbose": True},
        {"id": _TRANSACTION_ID},
        {"id": _TRANSACTION_ID, "date": "2026-05-01"},
    ],
    ids=["empty", "filters-only", "rows-only", "verbose-only", "id-only", "partial-detail"],
)
def test_an_incomplete_branch_is_refused(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        LedgerReviewResult.model_validate(payload)


def test_mixing_the_list_and_detail_branches_is_refused() -> None:
    with pytest.raises(ValidationError):
        LedgerReviewResult.model_validate(
            {
                "rows": [],
                "filters": [],
                "id": _TRANSACTION_ID,
                "date": "2026-05-01",
                "amount": "121.00",
                "description": "material oficina",
                "review_status": "pending",
            },
        )


@pytest.mark.parametrize(
    "overrides",
    [{"id": "bad"}, {"date": "bad"}, {"amount": ""}, {"description": ""}, {"review_status": ""}],
    ids=["bad-id", "bad-date", "blank-amount", "blank-description", "blank-status"],
)
def test_a_malformed_detail_branch_is_refused(overrides: dict[str, object]) -> None:
    detail: dict[str, object] = {
        "id": _TRANSACTION_ID,
        "date": "2026-05-01",
        "amount": "121.00",
        "description": "material oficina",
        "review_status": "pending",
    }
    detail.update(overrides)

    with pytest.raises(ValidationError):
        LedgerReviewResult.model_validate(detail)


def test_a_malformed_nested_row_is_refused_inside_the_list_branch() -> None:
    """Nested rows validate strictly, so a bad row cannot ride a valid envelope."""
    with pytest.raises(ValidationError):
        LedgerReviewResult.model_validate(
            {"rows": [_row_fields(id="bad")], "filters": []},
        )
