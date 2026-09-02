"""Worst-case on-disk object-path length for the local provider layout.

This package owns the ``local_provider_object_sidecar`` grammar
(``<root>/buckets/<bucket_id>/blobs/<namespace>/<hmac_prefix>--<label>.meta.json``,
declared with ``owner="cadrumo.adapters.outbound.storage"`` in
:data:`~adapters.persistence.storage.STORAGE_NAMESPACE_REGISTRY`), so the
deepest suffix that grammar can produce is derived here and handed to
:func:`~core.paths.windows_storage_root_long_path_margin` rather than
duplicated as a literal beneath it.

The ``<namespace>`` segment is the load-bearing one, and it was previously
mis-sourced. ``LocalFileSystemProvider`` fans one directory out per namespace
(``self._root / namespace``), and the namespaces it is handed in production
are *registered secure-object namespaces*: the mirror push loop passes
``SecureObjectRawRow.namespace`` straight to
:meth:`~adapters.outbound.storage.StorageProvider.put`, and the mirror
preflight refuses any namespace absent from the registry. Those values are
dotted and long (the longest shipped is 72 characters). The prior constant
instead spelled a bucket-event object type into the arithmetic — a disjoint
vocabulary whose values are never registered storage namespaces at all — and
so understated the worst case by 54 characters, which could let the preflight
margin accept a storage root from which a real outbound write then exceeds
``MAX_PATH``.

Deriving from :data:`~adapters.persistence.storage.STORAGE_NAMESPACE_REGISTRY`
makes the ceiling structural over the whole shipped domain: a newly registered
namespace longer than today's longest raises the budget automatically instead
of silently re-opening the gap.

The registry field caps ``namespace`` at 128 characters, which is the only
hard structural bound available. Budgeting against that cap rather than the
shipped maximum would put the suffix alone at 265 characters — past
:data:`~core.paths.WINDOWS_MAX_PATH` (260) before any root is prepended — so
every margin would be negative and the preflight probe would refuse every
storage root on every Windows workstation. The shipped-longest derivation is
the honest budget: it measures the deepest path this build can actually write.
"""

from __future__ import annotations

from functools import lru_cache

__all__ = ["windows_worst_case_object_path_suffix_length"]

#: Canonical UUIDv4 string length, the ``<bucket_id>`` segment's fixed width.
_BUCKET_ID_LENGTH = 36

#: Windows path separator. The suffix is measured in the worst-case (longest)
#: spelling; POSIX separators are the same width, so the count is portable.
_SEPARATOR = "\\"


@lru_cache(maxsize=1)
def windows_worst_case_object_path_suffix_length() -> int:
    """Return the longest object-path suffix this build's layout can append.

    Measured from the leading separator through the sidecar extension, using
    the real grammar constants: the bucket/blob directory names, a
    36-character bucket id, the longest namespace registered in
    :data:`~adapters.persistence.storage.STORAGE_NAMESPACE_REGISTRY`, the
    HMAC prefix width, and the operator-label cap.

    The ``.meta.json`` sidecar is measured rather than the ``.bin`` payload
    because it is the longer of the two names the provider writes for one
    object, so a path that fits the sidecar fits the payload.

    Returns:
        The suffix length in characters, for
        :func:`~core.paths.windows_storage_root_long_path_margin`.
    """
    from ...persistence.storage.namespace_registry import STORAGE_NAMESPACE_REGISTRY
    from ...persistence.storage.storage_path_definitions import BUCKET_BLOBS_DIRNAME, BUCKETS_DIRNAME
    from ._object_name import HMAC_PREFIX_LENGTH, LABEL_MAX_LENGTH
    from .local import SIDECAR_EXTENSION

    longest_namespace = max(len(definition.namespace) for definition in STORAGE_NAMESPACE_REGISTRY.namespaces)
    return len(
        _SEPARATOR
        + BUCKETS_DIRNAME
        + _SEPARATOR
        + ("0" * _BUCKET_ID_LENGTH)
        + _SEPARATOR
        + BUCKET_BLOBS_DIRNAME
        + _SEPARATOR
        + ("n" * longest_namespace)
        + _SEPARATOR
        + ("a" * HMAC_PREFIX_LENGTH)
        + "--"
        + ("b" * LABEL_MAX_LENGTH)
        + SIDECAR_EXTENSION,
    )
