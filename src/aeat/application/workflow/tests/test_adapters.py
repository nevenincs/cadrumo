"""Tests for workflow concrete adapter boundaries."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest

from .. import default_engine
from .._errors import WorkflowError
from .._protocols import (
    DeadlineEngineProtocol,
    ModeloDraftBuilderProtocol,
    SubmissionEngineProtocol,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _boundary_value[T](_protocol: type[T]) -> T:
    return cast(T, object())


_DefaultEngineCall = Callable[[], object]


@pytest.mark.parametrize(
    ("call", "message_key"),
    (
        (
            lambda: default_engine(),
            "application.workflow.errors.adapter_missing_submission_engine",
        ),
        (
            lambda: default_engine(
                submission_engine=_boundary_value(SubmissionEngineProtocol),
                deadline_engine=None,
                filing_draft_builder=None,
                inputs_provider=None,
            ),
            "application.workflow.errors.adapter_missing_deadline_engine",
        ),
        (
            lambda: default_engine(
                submission_engine=_boundary_value(SubmissionEngineProtocol),
                deadline_engine=_boundary_value(DeadlineEngineProtocol),
                filing_draft_builder=None,
                inputs_provider=None,
            ),
            "application.workflow.errors.adapter_missing_filing_draft_builder",
        ),
        (
            lambda: default_engine(
                submission_engine=_boundary_value(SubmissionEngineProtocol),
                deadline_engine=_boundary_value(DeadlineEngineProtocol),
                filing_draft_builder=_boundary_value(ModeloDraftBuilderProtocol),
                inputs_provider=None,
            ),
            "application.workflow.errors.adapter_missing_inputs_provider",
        ),
    ),
    ids=(
        "missing-submission-engine",
        "missing-deadline-engine",
        "missing-filing-draft-builder",
        "missing-inputs-provider",
    ),
)
def test_default_engine_required_adapter_guards(
    call: _DefaultEngineCall,
    message_key: str,
) -> None:
    with pytest.raises(WorkflowError) as raised:
        call()
    assert raised.value.translated_message == message_key
