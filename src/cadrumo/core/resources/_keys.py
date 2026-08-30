"""Typed key base models for the resource-management API.

Each :class:`ResourceCacheRepository` declares its own key model
or uses a trivial type for singleton and year-keyed resources.
Concrete keys such as :class:`ManualKey` inherit from
:class:`TypedResourceKey` when the lookup needs multiple fields.

Cache keys are Pydantic v2 models with ``frozen=True`` so they
are hashable for dict-backed Identity Maps. Singletons use
``None`` directly as the key; year-keyed Repositories use bare
``int`` values.
"""

from __future__ import annotations

from pydantic import BaseModel

from ..models import STRICT_FROZEN_CONFIG


class TypedResourceKey(BaseModel):
    """Common base for typed Repository keys.

    Each :class:`ResourceCacheRepository` that needs more than
    ``None`` or ``int`` as its key inherits from this base and
    adds its own fields. The ``frozen=True`` config makes the
    model hashable for Identity Map dict use.
    """

    model_config = STRICT_FROZEN_CONFIG
