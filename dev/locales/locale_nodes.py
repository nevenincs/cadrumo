"""Recursive locale leaf types and absent-leaf identity."""

from enum import Enum, auto

# YAML locale values are either leaf strings or nested dicts of the same shape.
type LocaleNode = str | dict[str, "LocaleNode"] | None


_MODELO_SCHEMA_PREFIX = "modelo.schema."
"""The one key family whose catalogues accept an explicitly absent value.

Declared here rather than beside its other reader because the scaffold decides
what an unvalued key becomes, and that decision has to agree with the status
report's view of which keys may legitimately be null. Two copies of the literal
would let the writer and the reader disagree about the same key.
"""


class _MissingLocaleLeaf(Enum):
    """Single-member sentinel for a key absent from the catalogue.

    An ``object()`` sentinel forces the resolver's return type to widen to
    ``object``, which erases the node type for every caller. An enum member
    narrows under an identity test, so the union stays meaningful.
    """

    TOKEN = auto()


_MISSING_LOCALE_LEAF = _MissingLocaleLeaf.TOKEN
