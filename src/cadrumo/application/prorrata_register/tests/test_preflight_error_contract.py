"""Prorrata preflight errors retain the finite projection evidence."""

from __future__ import annotations

import pytest

from ....core.errors.error_codes import ErrorCategory, get_registered_error_code
from ..mutation_steps import ProrrataPreflightRefusalError, build_prorrata_refusal_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_preflight_refusal_keeps_projection_evidence_and_registered_category() -> None:
    """Registering the error does not replace its existing public reason shape."""
    error = ProrrataPreflightRefusalError(
        "provenance_required", "Supply the provenance.", accepted_provenances=("operator",)
    )

    projection = build_prorrata_refusal_projection(
        reason=error.reason, detail=error.detail, accepted_provenances=error.accepted_provenances
    )
    registered = get_registered_error_code(error)

    assert projection.reason == "provenance_required"
    assert projection.detail == "Supply the provenance."
    assert projection.accepted_provenances == ("operator",)
    assert registered.code == "REFUSED_PRORRATA_PREFLIGHT"
    assert registered.category is ErrorCategory.REFUSED
    assert registered.retryable is False
