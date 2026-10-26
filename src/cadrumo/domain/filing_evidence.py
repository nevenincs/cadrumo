"""Nominal reference to evidence supporting one filing fact."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, StringConstraints

from ..core.models import STRICT_FROZEN_CONFIG

_EvidenceReferenceValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]


class FilingEvidenceReference(BaseModel):
    """One typed evidence identity carried by immutable filing facts.

    The wrapper is deliberately nominal: an attachment id, source locator, or
    arbitrary string cannot satisfy a filing-evidence field without being
    admitted explicitly at the evidence-collection boundary.
    """

    model_config = STRICT_FROZEN_CONFIG

    reference: _EvidenceReferenceValue


__all__ = ["FilingEvidenceReference"]
