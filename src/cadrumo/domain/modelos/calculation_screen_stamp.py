"""The screen declarations one calculation revision was computed against.

Some calculation notes exist only because the pinned registry declares
something the calculation screened for: a binding whose value is capped short
of filing grade is the first such declaration. A revision computed before a
declaration was added, or before one was removed, carries the notes of the old
screen. The stamp records which screen the calculation ran, so a later check,
export or filing can tell a current revision from a stale one without
re-adjudicating its values.

The stamp is optional on a revision. A revision stored before stamps existed
carries none, and that absence means its screen is unknown, never that it ran
an empty one. It joins the revision identity only when present, so stored ids
are unchanged.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG

SCREEN_STAMP_IDENTITY_KEY: Final = "screen_stamp"
"""The revision-identity payload key the stamp contributes when it is present."""


class CalculationScreenStamp(BaseModel):
    """One screen contract version and the digest of the screen declarations it read.

    ``contract_version`` is one integer for every screen together: a new screen,
    or a changed reading of an existing one, raises it. ``digest`` covers only
    the screen-relevant declarations of the revision's own registry revision,
    so a publication that changes nothing a screen reads leaves it unchanged.
    """

    model_config = STRICT_FROZEN_CONFIG

    contract_version: int = Field(ge=1)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    def identity_payload(self) -> dict[str, object]:
        """Return the stamp's contribution to its revision's content identity."""
        return {"contract_version": self.contract_version, "digest": self.digest}


__all__ = ["SCREEN_STAMP_IDENTITY_KEY", "CalculationScreenStamp"]
