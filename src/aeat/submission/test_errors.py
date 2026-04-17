"""Smoke tests for the submission-engine error hierarchy."""

from __future__ import annotations

import pytest

from ..errors import AeatError
from . import (
    SubmissionError,
    SubmissionFormFillError,
    SubmissionPreflightError,
    SubmissionRejectionError,
)

pytestmark = pytest.mark.unit


def test_every_error_inherits_aeat_error() -> None:
    for exc_cls in (
        SubmissionError,
        SubmissionPreflightError,
        SubmissionFormFillError,
        SubmissionRejectionError,
    ):
        assert issubclass(exc_cls, AeatError)


def test_translatable_message_preserved() -> None:
    from ..i18n import Translatable

    translatable: Translatable = {
        "en": "draft not ready",
        "es": "borrador no listo",
        "hu": "piszkozat nem kész",
    }
    exc = SubmissionPreflightError("draft not ready", translated_message=translatable)
    assert exc.translated_message == translatable
    assert str(exc) == "draft not ready"


def test_subclasses_catchable_as_submission_error() -> None:
    with pytest.raises(SubmissionError):
        raise SubmissionFormFillError("form fill broke")
    with pytest.raises(SubmissionError):
        raise SubmissionRejectionError("aeat rejected it")
