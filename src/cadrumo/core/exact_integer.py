"""Exact-integer admission for integer tags on strict wire and record models.

Pydantic's strict mode refuses a float or a boolean for a plain ``int`` field,
but not for an integer ``Literal`` or an ``IntEnum``: those match by value, so
``1.0``, ``1e0`` and ``true`` all validate as the tag ``1`` from JSON and from
Python alike. A version tag or an exit code written by another implementation
is a token, and a native reader that refuses those spellings would then
disagree with the Python owner about the same bytes.

Annotate such a field with :data:`EXACT_INTEGER`, for example
``schema_version: Annotated[Literal[1], EXACT_INTEGER] = 1``. The validator runs
before the field's own validation and admits only a genuine ``int`` or an
``IntEnum`` member; the field's type still decides which values are valid.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Final

from pydantic import BeforeValidator

__all__ = ["EXACT_INTEGER", "require_exact_integer"]


def require_exact_integer(value: object) -> object:
    """Return ``value`` when it is an ``int`` or an ``IntEnum`` member; refuse anything else.

    ``bool`` is an ``int`` subclass and is refused, as are floats with no
    fractional part and numeric strings.
    """
    if type(value) is int or isinstance(value, IntEnum):
        return value
    raise ValueError("an exact integer is required")


EXACT_INTEGER: Final = BeforeValidator(require_exact_integer)
"""Field metadata that applies :func:`require_exact_integer` before the field's validation."""
