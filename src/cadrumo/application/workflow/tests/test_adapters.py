"""Tests for workflow concrete adapter boundaries."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

import pytest

from cadrumo.application.workflow.adapters import default_engine
from ..engine import WorkflowEngine
from ..errors import WorkflowError
from ..protocols import (
    DeadlineEngineProtocol,
    ModeloDraftBuilderProtocol,
    ModeloInputsProviderProtocol,
    SubmissionEngineProtocol,
)

if TYPE_CHECKING:
    from ....adapters.outbound.aeat.auth import AeatSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _boundary_value[T](_protocol: type[T]) -> T:
    return cast(T, object())


_DefaultEngineCall = Callable[[], object]


def _default_engine_without_submission_engine() -> object:
    return default_engine()


def _default_engine_without_deadline_engine() -> object:
    return default_engine(
        submission_engine=_boundary_value(SubmissionEngineProtocol),
        deadline_engine=None,
        filing_draft_builder=None,
        inputs_provider=None,
    )


def _default_engine_without_filing_draft_builder() -> object:
    return default_engine(
        submission_engine=_boundary_value(SubmissionEngineProtocol),
        deadline_engine=_boundary_value(DeadlineEngineProtocol),
        filing_draft_builder=None,
        inputs_provider=None,
    )


def _default_engine_without_inputs_provider() -> object:
    return default_engine(
        submission_engine=_boundary_value(SubmissionEngineProtocol),
        deadline_engine=_boundary_value(DeadlineEngineProtocol),
        filing_draft_builder=_boundary_value(ModeloDraftBuilderProtocol),
        inputs_provider=None,
    )


@pytest.mark.parametrize(
    ("call", "message_key"),
    (
        (
            _default_engine_without_submission_engine,
            "application.workflow.errors.adapter_missing_submission_engine",
        ),
        (
            _default_engine_without_deadline_engine,
            "application.workflow.errors.adapter_missing_deadline_engine",
        ),
        (
            _default_engine_without_filing_draft_builder,
            "application.workflow.errors.adapter_missing_filing_draft_builder",
        ),
        (
            _default_engine_without_inputs_provider,
            "application.workflow.errors.adapter_missing_inputs_provider",
        ),
    ),
)
def test_default_engine_required_adapter_guards(call: _DefaultEngineCall, message_key: str) -> None:
    with pytest.raises(WorkflowError) as raised:
        call()
    assert raised.value.translated_message == message_key


def test_default_engine_leaves_notifications_unwired_without_a_bucket_scoped_capture() -> None:
    """A supplied session must not revive the adapter-level notification fetch."""
    engine = default_engine(
        submission_engine=_boundary_value(SubmissionEngineProtocol),
        deadline_engine=_boundary_value(DeadlineEngineProtocol),
        filing_draft_builder=_boundary_value(ModeloDraftBuilderProtocol),
        session=cast("AeatSession", object()),
        inputs_provider=_boundary_value(ModeloInputsProviderProtocol),
    )

    assert isinstance(engine, WorkflowEngine)
    assert engine._notifications_source is None
