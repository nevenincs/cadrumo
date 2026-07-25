"""Schema-lineage policy: version ceilings and the upgrade-chain gate.

The completeness gate here is the anti-stranding tripwire: every registered secure-object
namespace must carry a complete upgrade chain from the durability floor to
its current declared ``schema_version``. Today every namespace sits at
version 1 and the chain is vacuously complete; the moment a namespace bumps
its version without landing the one-hop upgrader in the same change, this
gate goes red instead of years-old rows going silently unreadable.
"""

from __future__ import annotations

import pytest

from .....core import COMPATIBILITY_REGIME, RELEASED_FORMAT_FLOORS, expected_floor
from .._namespace_registry import STORAGE_NAMESPACE_REGISTRY
from .._schema_lineage import (
    SECURE_OBJECT_DURABILITY_FLOOR,
    deregister_secure_object_schema_upgrader,
    ensure_schema_version_readable,
    missing_upgrade_hops,
    register_secure_object_schema_upgrader,
    upgrade_secure_object_payload,
)
from ..errors import EnvelopeVersionError, StorageValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = "cadrumo-test.lineage.policy"


def test_floor_matches_the_regime_expected_floor() -> None:
    """The secure-object floor tracks the regime-switched compatibility policy.

    The current secure-object version is the highest declared namespace
    ``schema_version``. While ``PRE_RELEASE`` (today) the expected floor IS
    that current version — the floors-chase-current pre-release posture — so
    every stored row sits at or above the floor with no pre-current shape to
    tolerate. Post-flip the expected floor becomes the frozen released value
    and this assertion demands the floor stay pinned there.
    """
    current = max(
        (definition.schema_version for definition in STORAGE_NAMESPACE_REGISTRY.namespaces),
        default=SECURE_OBJECT_DURABILITY_FLOOR,
    )
    assert (
        expected_floor(
            COMPATIBILITY_REGIME,
            "secure_object",
            current,
            RELEASED_FORMAT_FLOORS,
        )
        == SECURE_OBJECT_DURABILITY_FLOOR
    )


def test_every_registered_namespace_upgrade_chain_is_complete() -> None:
    """A namespace version bump without its registered upgrader fails here."""
    incomplete = {
        definition.namespace: missing_upgrade_hops(
            namespace=definition.namespace,
            from_version=SECURE_OBJECT_DURABILITY_FLOOR,
            to_version=definition.schema_version,
        )
        for definition in STORAGE_NAMESPACE_REGISTRY.namespaces
    }
    broken = {namespace: hops for namespace, hops in incomplete.items() if hops}
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
