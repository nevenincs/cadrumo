"""The closed answers the pension contribution commands take on their command line."""

from __future__ import annotations

from enum import StrEnum


class PrevisionSocialSamePlanAnswer(StrEnum):
    """Whether the employer also contributed to the same plan, as the certificate or the operator states it."""

    YES = "yes"
    NO = "no"

    @property
    def stated(self) -> bool:
        """The answer as the record stores it."""
        return self is PrevisionSocialSamePlanAnswer.YES


__all__ = ["PrevisionSocialSamePlanAnswer"]
