"""The grammar for the dotted identifier keys that address operator surfaces.

Two shapes recur wherever a condition, action, scenario or command is named:
a FIELD KEY, one or more lowercase segments joined by dots, and a NAMESPACED
ID, the same grammar requiring at least two segments so a bare word cannot pass
as a namespaced name.

Both regexes were written out six times -- twice in core and once each in the
modelo preconditions, the operator-action catalogue and the operator-surface
models. The redeclarations were not carelessness: the canonical constants lived
in an underscore-private core module and were absent from the package's export
map, so no consumer outside core could reach them at all. A constant nobody can
import is a constant everybody retypes, which is why this module is public.

:obj:`NamespacedId` carries its bounds as well as its pattern, because every
one of its eleven sites paired the pattern with the same minimum of three and
maximum of a hundred and sixty. :obj:`FIELD_KEY_PATTERN` stays a bare pattern:
its sites legitimately differ on length -- an argument name is capped shorter
than a source key -- so a single alias would impose a bound one of them does
not want.
"""

from __future__ import annotations

from typing import Annotated, Final

from pydantic import StringConstraints

FIELD_KEY_PATTERN: Final[str] = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$"
"""One or more lowercase dot-joined segments: a single word is a valid field key."""

NAMESPACED_ID_PATTERN: Final[str] = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"
"""Two or more lowercase dot-joined segments: a bare word is not a namespaced id."""

NamespacedId = Annotated[
    str,
    StringConstraints(pattern=NAMESPACED_ID_PATTERN, min_length=3, max_length=160),
]
"""A dotted namespaced identifier -- a condition, action, scenario or leaf key."""

__all__ = ["FIELD_KEY_PATTERN", "NAMESPACED_ID_PATTERN", "NamespacedId"]
