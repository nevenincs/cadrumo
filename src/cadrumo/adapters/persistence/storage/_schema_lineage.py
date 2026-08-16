"""Schema-lineage policy for persisted secure-object payloads.

A persisted secure object passes **two** version gates on the way to a
consumer, and they hold deliberately different contracts.

*Layer one* guards the outer SQL row. :func:`ensure_schema_version_readable`
is a *ceiling* plus an upgrade-chain completeness test: a version above the
consumer's current version is refused as written-by-a-newer-application, and
a version below it is readable exactly when the per-hop upgrade chain up to
the current version is complete. Registered upgraders transform decrypted
plaintext payload bytes one version step at a time; ciphertext, AEAD
associated data, and revision-lineage metadata are never rewritten by a read.

*Layer two* guards the ``Envelope`` inside the decrypted payload, and its
contract is strict EQUALITY — :func:`inner_envelope_version_is_current`.
Equality is right there precisely because layer one has already refused or
chain-upgraded the row, so an inner deviation is drift or corruption rather
than a lineage gap. The two layers are not interchangeable: layer one is
deliberately absent from the storage package facade so a layer-two caller
cannot reach for the wrong gate.

Layer two carries a second equality alongside the version one:
:func:`inner_envelope_classification_is_expected` re-checks the inner
envelope's :class:`~adapters.persistence.storage.SensitivityClass` against
what the caller's own namespace declares, as defense-in-depth against a row
whose embedded payload metadata has drifted from the outer columns layer one
already gated. Twenty-nine call sites hand-rolled this same comparison
independently before this predicate existed — six of them under their own
domain-specific exception class rather than the shared
:class:`~adapters.persistence.storage.ClassificationError`, which is why an
inventory keyed on the raise could not find them; the AST gate in
``tests/test_classification_enrollment_inventory.py`` is keyed on the
comparison instead, for exactly that reason.

Namespaces version INDEPENDENTLY: most sit at schema version 1, several at 2,
and one at 3. The upgrader registry below is therefore not empty — two
namespaces landed a real one-hop upgrader alongside their bump. Those two are
ahead of the current obligation rather than meeting it: while the
compatibility regime is pre-release, each namespace's durability floor chases
its own current version, older shapes are deleted rather than migrated, and
the lineage gate (``tests/test_schema_lineage.py``) does not demand a chain.
At the checkpoint flip the floors freeze and that gate starts requiring the
one-hop upgrader for every namespace above the frozen floor, in the same
change as the bump. An upgrader MUST re-stamp the payload's inner envelope
version; see
:func:`register_secure_object_schema_upgrader` for the obligation and why
forgetting it is silent at layer one and loud only at layer two.
:data:`SECURE_OBJECT_DURABILITY_FLOOR` moves forward only deliberately, once
every version below it is no longer readable by any live consumer.

See Also:
    :func:`~adapters.persistence.storage.sql._secure_object_row_codec.secure_object_record_from_row`
        Row decode path that applies this policy before returning a record.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Final

from ....core.classification import SensitivityClass
from .errors import EnvelopeVersionError, StorageValidationError

#: Upgrades one decrypted plaintext payload from ``from_version`` to
#: ``from_version + 1`` for its namespace. Pure bytes-to-bytes; never touches
#: ciphertext or row metadata.
#:
#: The payload's OWN inner ``Envelope.schema_version`` is emphatically NOT row
#: metadata — it is payload content, and re-stamping it to ``from_version + 1``
#: is part of the hop's job. See
#: :func:`register_secure_object_schema_upgrader` for why forgetting it is
#: silent rather than loud.
SecureObjectSchemaUpgrader = Callable[[bytes], bytes]

#: Oldest secure-object schema version every read path keeps readable.
#: Starts at the from-birth version; moves forward only deliberately.
SECURE_OBJECT_DURABILITY_FLOOR: Final[int] = 1

_SCHEMA_UPGRADERS: dict[tuple[str, int], SecureObjectSchemaUpgrader] = {}


def register_secure_object_schema_upgrader(
    namespace: str,
    from_version: int,
    upgrader: SecureObjectSchemaUpgrader,
) -> None:
    """Register the one-hop payload upgrader for ``(namespace, from_version)``.

    A schema bump for a namespace lands its upgrader through this function in
    the same change that raises the namespace's declared ``schema_version``;
    the lineage gate fails until it does.

    **The upgrader MUST re-stamp the payload's inner envelope.** A hop that
    transforms payload shape but leaves ``Envelope.schema_version`` at
    ``from_version`` is only half-written, and its failure mode is asymmetric:
    the row codec re-stamps the OUTER record to the current version
    unconditionally, so the outer layer will already have declared such a row
    current by the time anything reads it. The inner stamp moves only if this
    upgrader moves it.

    That asymmetry is why the obligation is recorded here rather than left to
    review. The only read-time detector of a forgotten re-stamp is the inner
    equality contract,
    :func:`inner_envelope_version_is_current` — layer one cannot see it, because
    from layer one's perspective nothing is wrong. Every persisted read path
    applies that equality, so a forgotten re-stamp surfaces as a loud refusal on
    first read rather than an ambiguous payload reaching a tax calculation.

    The obligation is currently assertable only vacuously: no hop is registered
    while every namespace sits at its from-birth version, and fabricating an
    old-shape payload to prove it would invent a shape nothing ever wrote, which
    the pre-release compatibility regime forbids. The first real hop is
    therefore the first executable proof, and the change that lands it owes
    three things in the same commit: the upgrader, a committed pre-bump
    serialized fixture, and a restorability test that loads those bytes through
    the real production read path and asserts the inner version arrives at the
    bumped value.

    Raises:
        StorageValidationError: When an upgrader for the hop is already
            registered — two competing transformations for one hop is a
            wiring error, never a merge.
    """
    key = (namespace, from_version)
    if key in _SCHEMA_UPGRADERS:
        raise StorageValidationError(
            context={"namespace": namespace, "from_version": from_version},
            translated_message="errors.storage.namespace.schema_upgrader_already_registered",
        )
    _SCHEMA_UPGRADERS[key] = upgrader


def deregister_secure_object_schema_upgrader(namespace: str, from_version: int) -> None:
    """Remove a registered upgrader hop.

    Production wiring never removes a hop — dropping one would re-open the
    stranding gap the lineage gate closes. This exists so tests that
    register a real upgrader against a scratch namespace can restore the
    registry in their teardown.
    """
    _SCHEMA_UPGRADERS.pop((namespace, from_version), None)


def missing_upgrade_hops(
    *,
    namespace: str,
    from_version: int,
    to_version: int,
    upgraders: Mapping[tuple[str, int], SecureObjectSchemaUpgrader] | None = None,
) -> tuple[int, ...]:
    """Return the ``from_version`` of every unregistered hop in the chain.

    An empty tuple means every step from ``from_version`` to ``to_version``
    has a registered upgrader (vacuously so when the versions are equal).
    """
    source = _SCHEMA_UPGRADERS if upgraders is None else upgraders
    return tuple(version for version in range(from_version, to_version) if (namespace, version) not in source)


def ensure_schema_version_readable(
    *,
    namespace: str,
    schema_version: int,
    current_version: int,
    upgraders: Mapping[tuple[str, int], SecureObjectSchemaUpgrader] | None = None,
) -> None:
    """Refuse a stored version the current application cannot read.

    The gate is a ceiling, not an equality: a version above
    ``current_version`` was written by a newer application and is refused
    outright; a version below it is accepted exactly when the registered
    upgrade chain up to ``current_version`` is complete, and refused loudly
    — naming the first missing hop — when it is not.

    Raises:
        EnvelopeVersionError: When ``schema_version`` exceeds
            ``current_version`` (future shape) or the upgrade chain has a
            missing hop (readable only after the missing upgrader ships).
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
    missing = missing_upgrade_hops(
        namespace=namespace,
        from_version=schema_version,
        to_version=current_version,
        upgraders=upgraders,
    )
    if missing:
        raise EnvelopeVersionError(
            context={
                "namespace": namespace,
                "schema_version": schema_version,
                "expected": current_version,
                "missing_from_version": missing[0],
            },
            translated_message="errors.storage.namespace.schema_upgrade_path_missing",
        )


def upgrade_secure_object_payload(
    payload: bytes,
    *,
    namespace: str,
    from_version: int,
    to_version: int,
    upgraders: Mapping[tuple[str, int], SecureObjectSchemaUpgrader] | None = None,
) -> bytes:
    """Chain-upgrade a decrypted payload from ``from_version`` to ``to_version``.

    Validates the chain first (so a missing hop refuses before any
    transformation runs), then applies each registered one-hop upgrader in
    order. Equal versions return the payload unchanged.

    Raises:
        EnvelopeVersionError: When ``from_version`` exceeds ``to_version``
            or the chain has a missing hop.
    """
    ensure_schema_version_readable(
        namespace=namespace,
        schema_version=from_version,
        current_version=to_version,
        upgraders=upgraders,
    )
    source = _SCHEMA_UPGRADERS if upgraders is None else upgraders
    for version in range(from_version, to_version):
        payload = source[(namespace, version)](payload)
    return payload


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


# Keep durable-format upgrade ownership beside the lineage registry, rather
# than relying on an incidental import of a profile repository.  That makes
# every real secure-object reader see the same complete chain before it opens
# any taxpayer data.
from ._iva_deduction_schema import (  # noqa: E402
    upgrade_bienes_inversion_v1_payload,
    upgrade_transaction_catalogue_v1_payload,
)
from ._namespace_registry import (  # noqa: E402
    PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE,
    TRANSACTION_CATALOGUE_NAMESPACE,
)

register_secure_object_schema_upgrader(
    PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.namespace,
    1,
    upgrade_bienes_inversion_v1_payload,
)
register_secure_object_schema_upgrader(
    TRANSACTION_CATALOGUE_NAMESPACE.namespace,
    1,
    upgrade_transaction_catalogue_v1_payload,
)


__all__ = [
    "SECURE_OBJECT_DURABILITY_FLOOR",
    "SecureObjectSchemaUpgrader",
    "deregister_secure_object_schema_upgrader",
    "ensure_schema_version_readable",
    "inner_envelope_classification_is_expected",
    "inner_envelope_version_is_current",
    "missing_upgrade_hops",
    "register_secure_object_schema_upgrader",
    "upgrade_secure_object_payload",
]
