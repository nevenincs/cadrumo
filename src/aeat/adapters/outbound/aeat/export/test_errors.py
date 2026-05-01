"""Smoke tests for the submission-engine error hierarchy."""

from __future__ import annotations

import pytest

from .....core.errors import AeatError
from . import (
    LiveSubmitForbiddenError,
    SubmissionError,
    SubmissionPreflightError,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


def test_every_error_inherits_aeat_error() -> None:
    for exc_cls in (
        LiveSubmitForbiddenError,
        SubmissionError,
        SubmissionPreflightError,
    ):
        assert issubclass(exc_cls, AeatError)


def test_export_errors_are_canonical_access_gate_errors() -> None:
    from .....core.access_gate import (
        LiveSubmitForbiddenError as CoreLiveSubmitForbiddenError,
    )
    from .....core.access_gate import (
        SubmissionError as CoreSubmissionError,
    )
    from .....core.access_gate import (
        SubmissionPreflightError as CoreSubmissionPreflightError,
    )
    from .....domain.submission import (
        LiveSubmitForbiddenError as DomainLiveSubmitForbiddenError,
    )
    from .....domain.submission import (
        SubmissionError as DomainSubmissionError,
    )
    from .....domain.submission import (
        SubmissionPreflightError as DomainSubmissionPreflightError,
    )

    assert LiveSubmitForbiddenError is CoreLiveSubmitForbiddenError is DomainLiveSubmitForbiddenError
    assert SubmissionError is CoreSubmissionError is DomainSubmissionError
    assert SubmissionPreflightError is CoreSubmissionPreflightError is DomainSubmissionPreflightError


def test_translatable_message_preserved() -> None:
    from .....core.i18n import Translatable

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
        raise LiveSubmitForbiddenError()
