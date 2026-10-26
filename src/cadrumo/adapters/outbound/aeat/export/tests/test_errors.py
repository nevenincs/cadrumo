"""Smoke tests for the submission-engine error hierarchy."""

from __future__ import annotations

import pytest

from ......core.access_gate.errors import LiveSubmitForbiddenError
from ......core.errors.hierarchy import CadrumoError
from ......domain.submission.errors import SubmissionError, SubmissionPreflightError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_every_error_inherits_cadrumo_error() -> None:
    for exc_cls in (
        LiveSubmitForbiddenError,
        SubmissionError,
        SubmissionPreflightError,
    ):
        assert issubclass(exc_cls, CadrumoError)


def test_export_errors_are_canonical_access_gate_errors() -> None:
    from ......core.access_gate.errors import LiveSubmitForbiddenError as CoreLiveSubmitForbiddenError
    from ......domain.submission.errors import SubmissionError as DomainSubmissionError
    from ......domain.submission.errors import SubmissionPreflightError as DomainSubmissionPreflightError

    assert LiveSubmitForbiddenError is CoreLiveSubmitForbiddenError
    assert SubmissionError is DomainSubmissionError
    assert SubmissionPreflightError is DomainSubmissionPreflightError


def test_translated_message_does_not_leak_into_str() -> None:
    """str(exc) must surface the raw message arg, not the translated_message override."""
    exc = SubmissionPreflightError("draft not ready", translated_message="export.test_errors.translatable")
    assert str(exc) == "draft not ready"
    assert exc.translated_message != str(exc)


def test_preflight_catchable_as_submission_error() -> None:
    with pytest.raises(SubmissionError, match=r"draft not ready"):
        raise SubmissionPreflightError("draft not ready")
