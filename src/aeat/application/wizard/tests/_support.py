from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EmptyAnswersBase(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
