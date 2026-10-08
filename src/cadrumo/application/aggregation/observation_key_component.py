"""Admission of the free-string components that compose an observation repository key."""

from __future__ import annotations

from ...core.i18n.translatable import Translatable as tr
from ...core.repository_id import repository_id_violation
from .errors import AggregationValidationError


def validate_observation_key_component(token: str, *, context: str) -> str:
    """Reject key components that would compose an unsafe repository id."""
    violation = repository_id_violation(token)
    if violation is None:
        return token
    raise AggregationValidationError(
        tr("errors.integrity.integrity_storage_path_containment"),
        context={"path_context": context, "violation": violation.value},
    )
