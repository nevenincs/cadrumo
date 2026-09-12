"""Frozen relation-id to binding-id join captured from the pre-absorption corpus.

Relations were a separate identified registry family whose declarations have
since been absorbed into the binding providers that replaced them. The authored
corpus therefore no longer carries a relation id at all, so the correspondence
between a retired relation id and the binding that inherited its join point
cannot be recovered from the live registry: it exists only as the frozen table
captured while both families were still declared.

Persisted calculation revisions written before the absorption carry override
keys in the retired vocabulary, so the table has to ship with the product for
the stored-data migration that rekeys them. It lives beside the migration that
consumes it, as a packaged resource read through ``importlib.resources``, rather
than in the development tree the capture tool writes to -- a migration that
could only run from a source checkout would silently leave an installed user's
stored overrides in the retired vocabulary forever.

The table is frozen by construction: it describes a corpus state that no longer
exists, so nothing can legitimately add a row to it. It is many-to-one -- two
retired relation ids that differed only on a temporal axis the binding now
carries as typed data map onto the same binding -- and consumers must handle
that collapse rather than assume injectivity.
"""

from __future__ import annotations

from functools import cache
from importlib.resources import files  # nosemgrep
from types import MappingProxyType
from typing import Final

from pydantic import TypeAdapter, ValidationError

from ....core.external_constants import UTF_8_ENCODING
from ....domain.calculations.registry.ids import BindingId, RelationId

_JOIN_RESOURCE_NAME: Final[str] = "relation_binding_join.json"
_JOIN_DOCUMENT_KEY: Final[str] = "relation_binding_join"
_JOIN_DOCUMENT_ADAPTER: Final[TypeAdapter[dict[str, dict[RelationId, BindingId]]]] = TypeAdapter(
    dict[str, dict[RelationId, BindingId]],
)


class RelationBindingJoinError(RuntimeError):
    """Raised when the bundled relation-to-binding join cannot be read as declared.

    A packaging fault, not a data condition: the table ships inside the wheel,
    so an absent resource or a payload that is not a flat string-to-string map
    means the distribution itself is broken. It refuses rather than degrading to
    an empty join, because an empty join would make the migration report every
    stored override as unmappable and destroy exactly the evidence it exists to
    preserve.
    """


@cache
def bundled_relation_binding_join() -> MappingProxyType[RelationId, BindingId]:
    """Return the frozen retired-relation-id to binding-id join.

    Cached because the table is immutable product data rather than profile
    state, and read lazily so importing this module costs nothing in a process
    that never migrates.

    Returns:
        A read-only mapping from each retired relation id to the binding id
        that inherited its join point. Many-to-one: distinct keys may share a
        value.

    Raises:
        RelationBindingJoinError: The bundled resource is absent, is not a
            valid join table, or carries no map under its declared document key.
    """
    resource = files(__package__).joinpath(_JOIN_RESOURCE_NAME)
    try:
        raw = resource.read_text(encoding=UTF_8_ENCODING)
    except (FileNotFoundError, OSError) as exc:
        raise RelationBindingJoinError(
            f"bundled relation-to-binding join resource {_JOIN_RESOURCE_NAME!r} is not readable",
        ) from exc
    try:
        document = _JOIN_DOCUMENT_ADAPTER.validate_json(raw)
    except ValidationError as exc:
        # The ids are validated against their own registry grammar rather than
        # merely being checked for stringhood, so a table row that could never
        # name a real binding is a packaging failure here instead of an
        # unresolvable override key at migration time.
        raise RelationBindingJoinError(
            f"bundled relation-to-binding join resource {_JOIN_RESOURCE_NAME!r} is not a valid join table",
        ) from exc
    join = document.get(_JOIN_DOCUMENT_KEY)
    if join is None:
        raise RelationBindingJoinError(
            f"bundled relation-to-binding join carries no {_JOIN_DOCUMENT_KEY!r} object",
        )
    return MappingProxyType(dict(join))


def bundled_relation_binding_join_targets() -> frozenset[BindingId]:
    """Return every binding id the frozen join resolves onto.

    The migration needs this set to tell an override key that is ALREADY a
    binding id (a post-cut write, which must be left exactly as it is so the
    migration stays idempotent) from one that is neither a known relation id nor
    a known binding id (an orphan, which must be refused rather than dropped).
    """
    return frozenset(bundled_relation_binding_join().values())


__all__ = [
    "RelationBindingJoinError",
    "bundled_relation_binding_join",
    "bundled_relation_binding_join_targets",
]
