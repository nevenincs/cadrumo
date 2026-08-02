"""Real-behavior tests: the maintenance result family carries UTC instants.

The public result models are populated by the services from ``core.time.now()``,
which is always UTC -- so on the path everyone reads, nothing was ever wrong.
That is precisely why the bare ``datetime`` annotations survived: the models
are also the boundary a programmatic or MCP consumer constructs and
deserializes across, and there the contract was "UTC by convention of the
current caller" rather than UTC.

Every result in the family is covered rather than a representative one. The
whole failure mode is a single field declared the ordinary way while its
neighbours are enrolled, so a test that samples the family cannot see the
member it missed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import BaseModel, ValidationError

from .._contracts import (
    ArchiveBucketResult,
    DeleteBucketResult,
    ExportBucketResult,
    ImportBucketResult,
    InspectBucketArchiveResult,
    RenameBucketResult,
    RestoreBucketResult,
)
from .._sandbox import (
    ArchiveSandboxResult,
    DiscardSandboxResult,
    MergeSandboxResult,
    RestoreSandboxResult,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_UTC_INSTANT = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)
_NAIVE_INSTANT = datetime(2026, 4, 1, 10, 0, 0)
_OFFSET_INSTANT = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=2)))

_RESULT_MODELS: tuple[type[BaseModel], ...] = (
    RenameBucketResult,
    DeleteBucketResult,
    ArchiveBucketResult,
    RestoreBucketResult,
    ExportBucketResult,
    ImportBucketResult,
    InspectBucketArchiveResult,
    DiscardSandboxResult,
    ArchiveSandboxResult,
    RestoreSandboxResult,
    MergeSandboxResult,
)


def _instant_fields(model: type[BaseModel]) -> tuple[str, ...]:
    return tuple(name for name in model.model_fields if name in {"occurred_at", "created_at"})


@pytest.mark.parametrize("model", _RESULT_MODELS, ids=[m.__name__ for m in _RESULT_MODELS])
def test_every_result_declares_a_lifecycle_instant(model: type[BaseModel]) -> None:
    """The premise of the sweep: each of these carries an instant to protect."""
    assert _instant_fields(model), model.__name__


@pytest.mark.parametrize("model", _RESULT_MODELS, ids=[m.__name__ for m in _RESULT_MODELS])
@pytest.mark.parametrize("instant", (_NAIVE_INSTANT, _OFFSET_INSTANT), ids=("naive", "offset"))
def test_result_refuses_a_non_utc_instant(model: type[BaseModel], instant: datetime) -> None:
    for field in _instant_fields(model):
        with pytest.raises(ValidationError) as excinfo:
            model.model_validate({field: instant})
        assert any(error["loc"] == (field,) for error in excinfo.value.errors()), (
            f"{model.__name__}.{field} accepted a non-UTC instant"
        )


@pytest.mark.parametrize("model", _RESULT_MODELS, ids=[m.__name__ for m in _RESULT_MODELS])
def test_a_utc_instant_is_not_the_field_that_fails(model: type[BaseModel]) -> None:
    """Positive control: the refusals above are about the instant, not the model.

    These models carry required fields this test does not supply, so validation
    fails either way. What distinguishes the two cases is whether the instant
    field is among the errors -- and here it must not be.
    """
    for field in _instant_fields(model):
        with pytest.raises(ValidationError) as excinfo:
            model.model_validate({field: _UTC_INSTANT})
        assert not any(error["loc"] == (field,) for error in excinfo.value.errors()), (
            f"{model.__name__}.{field} rejected a valid UTC instant"
        )
