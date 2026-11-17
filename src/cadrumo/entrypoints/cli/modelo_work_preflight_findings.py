"""Findings served by an admitted declaration edit check."""

from __future__ import annotations

from ...application.modelo.action_errors import modelo_edit_refusal_error
from ...application.modelo.edit_models import ModeloEditRefusedV1
from ...application.modelo.workbench_operations import ModeloEditPreflightProjectionV1


def checked(review: ModeloEditPreflightProjectionV1) -> list[str]:
    """The check's findings in words, refusing the staged change the check refused."""
    if isinstance(review.outcome, ModeloEditRefusedV1):
        raise modelo_edit_refusal_error(review.outcome.refusal)
    return [finding.words for finding in review.findings]
