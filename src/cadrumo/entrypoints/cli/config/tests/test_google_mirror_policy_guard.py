"""The remote-mirror policy is consulted on the path that leaves the machine.

``SecureObjectNamespaceDefinition.remote_mirror_policy`` declares whether a
namespace's rows may be pushed to a remote provider. The mirror reads every
row through
:meth:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository.iter_all_records_raw`,
which deliberately bypasses the decrypting read path and with it the funnel
that resolves a row's namespace definition, so the declaration reaches the
mirror only if the mirror asks for it. These tests pin that it does.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from .....adapters.outbound.storage.protocol import StorageProvider
from .....adapters.outbound.storage.records import ProviderObjectMetadata, ProviderProbeReport
from .....adapters.persistence.storage.namespace_registry import STORAGE_NAMESPACE_REGISTRY
from .....adapters.persistence.storage.namespace_taxonomy import (
    StorageCustodyDisposition,
    StorageNamespaceScope,
    StorageRemoteMirrorPolicy,
)
from .....adapters.persistence.storage.secure_object_namespaces import SecureObjectNamespaceDefinition
from .....core.classification.policies import SensitivityClass
from ..google import (
    _mirror_refusal_for_definition,
    _preflight_mirror_namespaces,
    _unmirrorable_namespace_reason,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _definition(policy: StorageRemoteMirrorPolicy) -> SecureObjectNamespaceDefinition:
    """Build a namespace definition carrying ``policy``.

    Built rather than borrowed from the shipped registry on purpose. No
    namespace ships as ``LOCAL_ONLY``, so reaching that branch by re-labelling
    a real one would pin the proof to a production declaration somebody may
    legitimately change. The ciphertext policy additionally requires the two
    metadata flags, which the definition's own coherence validator enforces.
    """
    requires_metadata = policy is StorageRemoteMirrorPolicy.CIPHERTEXT_WITH_METADATA
    return SecureObjectNamespaceDefinition(
        key=f"guard_fixture_{policy.value}",
        namespace=f"guard-fixture-{policy.value}",
        owner="mirror-policy-guard-test",
        sensitivity=SensitivityClass.FINANCIAL,
        schema_version=1,
        object_key_grammar="<fixture_key>",
        scope=StorageNamespaceScope.BUCKET_LOCAL,
        custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
        remote_mirror_policy=policy,
        remote_mirror_requires_revision=requires_metadata,
        remote_mirror_requires_integrity_manifest=requires_metadata,
    )


class _ProviderNeverReached:
    """A provider whose every operation is a failure.

    Not a stand-in for a provider: the property under test is that a withheld
    namespace never reaches the remote at all, so the useful provider here is
    one that cannot be used without saying so. A test double that returned
    plausible values would let a regression push a withheld namespace and
    still pass.
    """

    def _refuse(self, operation: str) -> None:
        message = f"withheld namespace reached the remote provider via {operation}"
        raise AssertionError(message)

    def put(self, *args: object, **kwargs: object) -> ProviderObjectMetadata:
        self._refuse("put")
        raise AssertionError

    def get(self, namespace: str, object_key_hmac: str) -> tuple[bytes, ProviderObjectMetadata]:
        self._refuse("get")
        raise AssertionError

    def delete(self, namespace: str, object_key_hmac: str) -> bool:
        self._refuse("delete")
        raise AssertionError

    def iter_namespaces(self) -> Iterator[str]:
        self._refuse("iter_namespaces")
        raise AssertionError

    def iter_objects(self, namespace: str) -> Iterator[ProviderObjectMetadata]:
        self._refuse("iter_objects")
        raise AssertionError

    def probe(self, *, read_only: bool = False) -> ProviderProbeReport:
        self._refuse("probe")
        raise AssertionError


def test_local_only_namespace_is_refused() -> None:
    """A namespace declaring ``LOCAL_ONLY`` must not be mirrored."""
    refusal = _mirror_refusal_for_definition(_definition(StorageRemoteMirrorPolicy.LOCAL_ONLY))

    assert refusal is not None
    assert StorageRemoteMirrorPolicy.LOCAL_ONLY.value in refusal


def test_ciphertext_namespace_is_permitted() -> None:
    """The same fixture shape carrying the ciphertext policy is mirrorable.

    The discriminating half of the pair: identical definition in every
    respect except the declared policy, so a refusal can only be coming from
    the policy rather than from anything incidental to the fixture.
    """
    refusal = _mirror_refusal_for_definition(_definition(StorageRemoteMirrorPolicy.CIPHERTEXT_WITH_METADATA))

    assert refusal is None


def test_test_only_namespace_is_refused() -> None:
    """``TEST_ONLY`` is withheld too, and the refusal names which policy withheld it."""
    refusal = _mirror_refusal_for_definition(_definition(StorageRemoteMirrorPolicy.TEST_ONLY))

    assert refusal is not None
    assert StorageRemoteMirrorPolicy.TEST_ONLY.value in refusal


def test_unregistered_namespace_is_refused_rather_than_waved_through() -> None:
    """A namespace absent from the registry is blocked, not mirrored by default.

    The rows most likely to carry an unregistered namespace are the newest,
    which is exactly the case a declared-disposition policy exists to cover.
    """
    refusal = _unmirrorable_namespace_reason("namespace-that-is-not-registered")

    assert refusal is not None
    assert "unregistered" in refusal


def test_every_shipped_namespace_decision_follows_its_own_declaration() -> None:
    """Total over the shipped registry, expectations read from each declaration.

    Derived rather than hardcoded so that re-declaring a namespace's policy
    moves this test's expectation with it instead of rotting it.
    """
    mismatches: list[str] = []
    for definition in STORAGE_NAMESPACE_REGISTRY.namespaces:
        refusal = _unmirrorable_namespace_reason(definition.namespace)
        mirrorable = definition.remote_mirror_policy is StorageRemoteMirrorPolicy.CIPHERTEXT_WITH_METADATA
        if mirrorable and refusal is not None:
            mismatches.append(f"{definition.namespace}: mirrorable by declaration but refused ({refusal})")
        if not mirrorable and refusal is None:
            mismatches.append(f"{definition.namespace}: declares {definition.remote_mirror_policy.value} but permitted")

    assert not mismatches, "\n".join(mismatches)


def test_withheld_namespace_never_reaches_the_provider() -> None:
    """The preflight blocks a withheld namespace before any remote call.

    Exercises the wiring rather than the decision: the guard has to run ahead
    of the manifest build and the remote inspection, or the withheld rows'
    metadata seeds a manifest and reaches the provider regardless of the
    verdict.
    """
    withheld = _definition(StorageRemoteMirrorPolicy.LOCAL_ONLY).namespace
    provider: StorageProvider = _ProviderNeverReached()

    outcome = _preflight_mirror_namespaces(provider=provider, planned_rows_by_namespace={withheld: []})

    assert outcome.blocked_namespaces == {withheld}
    assert outcome.manifests_by_namespace == {}
    assert [namespace for namespace, _reason in outcome.failed] == [withheld]
