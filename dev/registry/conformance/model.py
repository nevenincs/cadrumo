"""Shared strict model for conformance projections."""

from pydantic import BaseModel

from cadrumo.core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN_CONFIG


class ConformanceModel(BaseModel):
    """Strict frozen base for composed conformance facts."""

    model_config = _STRICT_FROZEN_CONFIG
