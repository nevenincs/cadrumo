"""Schema-lineage policy: version ceilings and the upgrade-chain gate.

The completeness gate here is the anti-stranding tripwire: every registered
secure-object namespace must carry a complete upgrade chain from the floor its
regime imposes to its current declared ``schema_version``, so a version bump
that strands years-old rows reds here rather than going silently unreadable.

What that floor IS depends on the regime, and the two must not be conflated.
Namespaces version independently -- most sit at 1, several at 2, one at 3 --
so the format-wide scalar floor is emphatically not the highest of them.
Pre-release each namespace's floor chases its own current version, which makes
the chain leg vacuous by design; post-flip every floor freezes at one released
value and the leg acquires real teeth. :func:`~core.lineage_obligations` is the
authority on which obligations bind, and these tests defer to it rather than
restating a policy that changes at the checkpoint.
"""

from __future__ import annotations

import pytest

from .....core.compatibility_lifecycle import (
    COMPATIBILITY_REGIME,
    RELEASED_FORMAT_FLOORS,
    expected_floor,
    lineage_obligations,
)
from ..errors import EnvelopeVersionError, StorageValidationError
from ..namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ..schema_lineage import (
    SECURE_OBJECT_DURABILITY_FLOOR,
    deregister_secure_object_schema_upgrader,
    ensure_schema_version_readable,
    missing_upgrade_hops,
    register_secure_object_schema_upgrader,
    upgrade_secure_object_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = "cadrumo-test.lineage.policy"


def _namespaces_missing_hops() -> dict[str, tuple[int, ...]]:
    """Return each namespace's unregistered hops from its own regime floor.

    The floor is taken per namespace rather than from the format-wide scalar,
    because that is what the regime actually says: pre-release a format's floor
    chases its current version, and each namespace carries its own current
    version. Post-flip every namespace's floor becomes the one frozen value and
    the gap it must bridge becomes real.
    """
    missing: dict[str, tuple[int, ...]] = {}
    for definition in STORAGE_NAMESPACE_REGISTRY.namespaces:
        hops = missing_upgrade_hops(
            namespace=definition.namespace,
            from_version=expected_floor(
                COMPATIBILITY_REGIME,
                "secure_object",
                definition.schema_version,
                RELEASED_FORMAT_FLOORS,
            ),
            to_version=definition.schema_version,
        )
        if hops:
            missing[definition.namespace] = hops
    return missing


def _has_cross_version_fixture_coverage() -> bool:
    """Report whether committed pre-bump payload fixtures cover the floor-to-current gap.

    None exist, and reporting that truthfully is the point. Pre-release the
    regime deletes old shapes instead of migrating them, and authoring a
    fixture for a shape nothing ever wrote is forbidden -- so the honest answer
    today is ``False``, which the pre-release branch ignores. It stops being
    ignored at the checkpoint flip, and this gate then reds until the fixtures
    are real. A placeholder ``True`` here would instead let the flip land
    silently unproven.
    """
    return False


def test_floor_satisfies_the_regime_lineage_obligations() -> None:
    """The declared floor satisfies whatever the active regime obliges of it.

    Secure-object namespaces version INDEPENDENTLY -- most sit at 1, a few at
    2, one at 3 -- while the durability floor is one scalar for the whole
    format. So the floor cannot simply equal the highest declared version: a
    floor above a namespace's version claims rows nothing can read, and it
    would also have to drag the envelope's own lower bound up with it, making
    every version-1 payload unrepresentable.

    :func:`~core.lineage_obligations` is the authority on what the floor owes.
    Pre-release it owes only coherence -- the floor may not exceed the current
    version, because older shapes are deleted rather than migrated. Post-flip
    it owes the frozen released value, and this same call starts demanding it.
    """
    current = max(
        (definition.schema_version for definition in STORAGE_NAMESPACE_REGISTRY.namespaces),
        default=SECURE_OBJECT_DURABILITY_FLOOR,
    )
    violations = lineage_obligations(
        COMPATIBILITY_REGIME,
        "secure_object",
        current,
        SECURE_OBJECT_DURABILITY_FLOOR,
        RELEASED_FORMAT_FLOORS,
        has_registered_upgraders_for_gap=not _namespaces_missing_hops(),
        has_fixture_coverage=_has_cross_version_fixture_coverage(),
    )
    assert violations == (), f"the secure-object durability floor violates its regime obligations: {violations}"


def test_no_namespace_declares_a_version_below_the_floor() -> None:
    """The floor may not claim readability for a version no namespace reaches.

    This is the pre-release obligation applied per namespace: the shared floor
    must sit at or below every declared version, or it asserts a readable
    shape that does not exist.
    """
    below = {
        definition.namespace: definition.schema_version
        for definition in STORAGE_NAMESPACE_REGISTRY.namespaces
        if definition.schema_version < SECURE_OBJECT_DURABILITY_FLOOR
    }
    assert below == {}, f"namespaces declare a schema_version below the durability floor: {below}"


def test_every_registered_namespace_upgrade_chain_is_complete() -> None:
    """A namespace version bump without its registered upgrader fails here -- post-flip.

    The chain each namespace owes runs from ITS OWN regime floor, not from the
    format-wide scalar. Pre-release that floor chases the namespace's current
    version, so the chain is vacuously complete and this leg is DORMANT by the
    regime's design: shapes an older build wrote are deleted, never migrated,
    and the governing rule forbids fabricating an upgrader before a real
    post-checkpoint bump needs one. Two namespaces nonetheless ship genuine
    one-hop upgraders today; they are early rather than required, and they are
    what this leg will demand of every bumped namespace once the regime flips.

    The dormancy is stated rather than hidden because a gate that cannot fail
    must never read as a gate that is passing.
    """
    broken = _namespaces_missing_hops()
    assert broken == {}, (
        "secure-object namespaces declare a schema_version without a complete "
        f"durability-floor upgrade chain: {broken}; register the missing one-hop "
        "upgrader(s) in the same change as the version bump"
    )


def test_future_schema_version_is_refused_as_from_future() -> None:
    with pytest.raises(EnvelopeVersionError) as raised:
        ensure_schema_version_readable(
            namespace=_NAMESPACE,
            schema_version=2,
            current_version=1,
        )
    assert raised.value.translated_message == "errors.storage.namespace.schema_version_from_future"
    assert raised.value.context == {
        "namespace": _NAMESPACE,
        "schema_version": 2,
        "expected": 1,
    }


def test_older_version_with_incomplete_chain_names_the_first_missing_hop() -> None:
    upgraders = {(_NAMESPACE, 2): lambda payload: payload}
    with pytest.raises(EnvelopeVersionError) as raised:
        ensure_schema_version_readable(
            namespace=_NAMESPACE,
            schema_version=1,
            current_version=3,
            upgraders=upgraders,
        )
    assert raised.value.translated_message == "errors.storage.namespace.schema_upgrade_path_missing"
    assert raised.value.context == {
        "namespace": _NAMESPACE,
        "schema_version": 1,
        "expected": 3,
        "missing_from_version": 1,
    }


def test_chain_upgrade_applies_registered_hops_in_order() -> None:
    upgraders = {
        (_NAMESPACE, 1): lambda payload: payload + b"|1to2",
        (_NAMESPACE, 2): lambda payload: payload + b"|2to3",
    }
    upgraded = upgrade_secure_object_payload(
        b"written-at-v1",
        namespace=_NAMESPACE,
        from_version=1,
        to_version=3,
        upgraders=upgraders,
    )
    assert upgraded == b"written-at-v1|1to2|2to3"


def test_equal_versions_return_the_payload_unchanged() -> None:
    payload = b"already-current"
    assert (
        upgrade_secure_object_payload(
            payload,
            namespace=_NAMESPACE,
            from_version=1,
            to_version=1,
        )
        is payload
    )


def test_registration_is_single_writer_per_hop_and_reversible() -> None:
    register_secure_object_schema_upgrader(_NAMESPACE, 1, lambda payload: payload)
    try:
        assert (
            missing_upgrade_hops(
                namespace=_NAMESPACE,
                from_version=1,
                to_version=2,
            )
            == ()
        )
        with pytest.raises(StorageValidationError):
            register_secure_object_schema_upgrader(_NAMESPACE, 1, lambda payload: payload)
    finally:
        deregister_secure_object_schema_upgrader(_NAMESPACE, 1)
    assert missing_upgrade_hops(
        namespace=_NAMESPACE,
        from_version=1,
        to_version=2,
    ) == (1,)
