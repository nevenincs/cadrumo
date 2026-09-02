"""Whether something must be supplied or may be omitted.

A two-member modality that five surfaces had each declared for themselves: profile keys
before declaration export, manual casilla entry, diagnostic findings, the CLI's repair
findings, and a diagnostics helper's parameter. The subject differs at every one of
them; the question does not.

Deliberately generic and deliberately not a ``bool``. A boolean field named
``required`` reads the same in a payload whether it was set or defaulted, and it cannot
grow a third member. The vocabularies that DO need a third member -- an unknown, a
not-applicable, a zero-by-law -- are separate types and must stay separate; this one is
for the surfaces where the answer is genuinely one of two.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

__all__ = ["Requirement", "RequirementValue"]


class Requirement(StrEnum):
    """Whether a value must be supplied."""

    REQUIRED = "required"
    """Must be supplied; its absence is a defect the surface reports."""

    OPTIONAL = "optional"
    """May be omitted, and its absence is not by itself a finding."""


RequirementValue = Literal[Requirement.REQUIRED, Requirement.OPTIONAL]
"""The same vocabulary for a strict model field or payload surface.

A bare enum under strict validation refuses the plain token a serialised finding
carries, so those fields take this literal over the members above rather than restating
the pair.
"""
