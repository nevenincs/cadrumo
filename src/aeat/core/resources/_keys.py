"""Typed key models for the resource-management API.

Each Repository declares its own ``Key`` model (or uses a
trivial type for singletons / year-keyed resources). The
top-level ``ResourceKey`` discriminated union enumerates the
typed key variants for every Repository implementation.

Cache keys are Pydantic v2 models with ``frozen=True`` so they
are hashable for dict-backed Identity Maps. Singletons use
``None`` directly as the key; year-keyed Repositories use bare
``int`` values.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

_FROZEN_STRICT = ConfigDict(strict=True, frozen=True, extra="forbid")


class TypedResourceKey(BaseModel):
    """Common base for typed Repository keys.

    Each Repository that needs more than ``None`` or ``int`` as
    its key inherits from this base and adds its own fields.
    The ``frozen=True`` config makes the model hashable for
    Identity Map dict use.
    """

    model_config = _FROZEN_STRICT
