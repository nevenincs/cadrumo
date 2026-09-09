"""Schema identity checks for persisted secure-object payloads.

A persisted secure object passes **two** version gates on the way to a
consumer, and they hold deliberately different contracts.

*Layer one* guards the outer SQL row. :func:`ensure_schema_version_readable`
requires the exact version the consumer declares. A version above it is
refused as written by a newer application; a version below it has no reader in
this build and is refused before decryption.

*Layer two* guards the ``Envelope`` inside the decrypted payload, and its
contract is strict EQUALITY — :func:`inner_envelope_version_is_current`.
Equality is right there precisely because layer one has already established
the current row version, so an inner deviation is drift or corruption. The two layers are
deliberately absent from the storage package facade so a layer-two caller
cannot reach for the wrong gate.

Layer two carries a second equality alongside the version one:
:func:`inner_envelope_classification_is_expected` re-checks the inner
envelope's :class:`~adapters.persistence.storage.SensitivityClass` against
what the caller's own namespace declares, as defense-in-depth against a row
whose embedded payload metadata has drifted from the outer columns layer one
already gated. Callers use this predicate so the equality rule remains owned
by the schema-lineage boundary regardless of their domain-specific refusal
type or message.

See Also:
    :func:`~adapters.persistence.storage.sql._secure_object_row_codec.secure_object_record_from_row`
        Row decode path that applies this policy before returning a record.
"""

from __future__ import annotations

from ....core.classification.policies import SensitivityClass
from .errors import EnvelopeVersionError


def ensure_schema_version_readable(
    *,
    namespace: str,
    schema_version: int,
    current_version: int,
) -> None:
    """Refuse a stored version the current application cannot read.

    A version above ``current_version`` was written by a newer application. A
    version below it has no reader in this build. Both refuse before decrypting.

    Raises:
        EnvelopeVersionError: When ``schema_version`` exceeds
            ``current_version`` or falls below it.
    """
    if schema_version > current_version:
        raise EnvelopeVersionError(
            context={
                "namespace": namespace,
                "schema_version": schema_version,
                "expected": current_version,
            },
            translated_message="errors.storage.namespace.schema_version_from_future",
        )
    if schema_version < current_version:
        raise EnvelopeVersionError(
            context={
                "namespace": namespace,
                "schema_version": schema_version,
                "expected": current_version,
                "missing_from_version": schema_version,
            },
            translated_message="errors.storage.namespace.schema_upgrade_path_missing",
        )


def inner_envelope_version_is_current(stored_version: int, current_version: int) -> bool:
    """Return whether a decrypted payload's inner envelope sits at the current version.

    This is the *layer two* contract described in the module docstring, and it
    is an equality rather than a ceiling. By the time a consumer validates the
    inner :class:`~adapters.persistence.storage.Envelope`, layer one has
    already refused a future outer row or chain-upgraded an older one to
    ``current_version``, so the only remaining ways an inner stamp can differ
    are drift and corruption — neither of which a ceiling detects on the
    below-current side.

    The below-current side is what gives this predicate its teeth. The row
    codec re-stamps the OUTER record to the current version unconditionally,
    while the inner stamp lives in the payload bytes and moves only if a
    registered upgrader rewrites that field. An upgrader that transforms
    payload shape but forgets the inner version therefore yields exactly a
    below-current inner stamp on a row layer one has already declared current,
    and this equality is the ONLY place that is detectable at read time.

    The predicate **does not raise**, by contract. Callers own their refusal:
    each read path raises its own exception class carrying its own translated
    message key and the per-object diagnostics (object key, bucket id,
    amendment id, observation and snapshot labels) that identify *which* row is
    unreadable. At least one caller is additionally ordering-sensitive — its
    raise sits inside a ``try`` whose ``except`` clause names the exception
    types it expects — so a raising helper would silently re-route that path
    even though the comparison itself is unchanged.

    Args:
        stored_version: The ``schema_version`` read from the inner envelope.
        current_version: The namespace's declared current ``schema_version``,
            which every caller derives from its
            :class:`~adapters.persistence.storage.SecureObjectNamespaceDefinition`
            rather than restating as a literal.

    Returns:
        ``True`` when the stored version is exactly the current version.
    """
    return stored_version == current_version


def inner_envelope_classification_is_expected(
    stored: SensitivityClass,
    expected: SensitivityClass,
) -> bool:
    """Return whether a decrypted payload's inner envelope carries the expected class.

    The classification sibling of :func:`inner_envelope_version_is_current`: the
    same *layer two* defense-in-depth re-check, on the same equality contract,
    for the same reason. By the time a consumer validates the inner
    :class:`~adapters.persistence.storage.Envelope`, the outer SQL row's
    ``expected_class`` argument has already gated the row once; this predicate
    is the second, independent look at the payload's own embedded statement, so
    a row whose payload bytes drifted from its own columns is still caught.

    The predicate **does not raise**, by contract — the same contract as its
    version sibling, and for the same reason. Callers own their refusal: each
    read path raises its own exception class (``ClassificationError`` at most
    sites, but six catalogue repositories raise their own domain-specific
    ``*PersistenceError`` instead) carrying its own translated message key and
    per-object diagnostics. A raising helper would silently re-route every one
    of those differently-typed refusals even though the comparison itself is
    identical everywhere.

    Args:
        stored: The classification read from the inner envelope.
        expected: The classification the caller's namespace declares, which
            every caller derives from its own
            :class:`~adapters.persistence.storage.SensitivityClass` constant or
            :class:`~adapters.persistence.storage.SecureObjectNamespaceDefinition`
            rather than restating as a literal.

    Returns:
        ``True`` when the stored classification is exactly the expected one.
    """
    return stored is expected


__all__ = [
    "ensure_schema_version_readable",
    "inner_envelope_classification_is_expected",
    "inner_envelope_version_is_current",
]
