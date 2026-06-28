"""Shared pydantic model configuration constants.

Provides the canonical :data:`STRICT_FROZEN_CONFIG` used across domain,
application, and adapter pydantic models that require strict-mode, frozen,
no-extra-fields configuration. It is a :class:`pydantic.ConfigDict` value shared
by records that need immutable boundary contracts.

Modules with intentionally divergent ``ConfigDict`` values (e.g.
``arbitrary_types_allowed=True`` in storage adapter models, or
``validate_assignment=True`` in JSON contract models) must keep their own
module-local config constant and must NOT import :data:`STRICT_FROZEN_CONFIG`
from here.
"""

from __future__ import annotations

from pydantic import ConfigDict

#: Canonical pydantic ConfigDict for strict-mode, frozen, no-extra-fields models.
#:
#: Modules that require a different config (e.g. ``arbitrary_types_allowed=True``
#: for ORM-mapped types, or ``validate_assignment=True`` for mutable contract
#: types) must declare a module-local constant instead.
STRICT_FROZEN_CONFIG: ConfigDict = ConfigDict(strict=True, frozen=True, extra="forbid")

__all__ = ["STRICT_FROZEN_CONFIG"]
