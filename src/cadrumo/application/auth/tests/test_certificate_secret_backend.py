"""Real-behavior tests for the certificate-secret backend abstraction.

Exercises :mod:`~application.auth._certificate_secret_backend` against a
real encrypted :class:`~adapters.persistence.storage.SecretStore` (an
:class:`~adapters.persistence.storage.master_key.EphemeralMasterKeyProvider`
under a real :class:`~adapters.persistence.storage.blob_store.EncryptedBlobStore`
— no mocks or fakes) and the operator verbs
(:func:`~application.auth.set_operator_certificate_source_secret`,
:func:`~application.auth.remove_operator_certificate_source_secret`,
:func:`~application.auth.resolve_certificate_source_secret`) against a
real workflow-state repository, mirroring the pattern already
established for the sibling certificate-source registry tests.

Also pins the post-cutover surface: named certificate secrets have exactly
one storage authority (encrypted secure storage), so the deleted keyring
backend, backend-kind selector, backend factory, and unavailable error must
be absent from both the module and the ``application.auth`` facade.

See Also:
    :mod:`~application.auth._certificate_secret_backend`
        Sole secure-storage certificate-secret backend contract under test.
    :class:`~application.auth.SecureStorageCertificateSecretBackend`
        Bucket-scoped backend exercised with a real encrypted store.
    :class:`~adapters.persistence.storage.SecretStore`
        Encrypted secret substrate used for certificate passphrase persistence.
    :class:`~adapters.persistence.storage.blob_store.EncryptedBlobStore`
        Blob encryption layer backing the isolated real-behavior store.
    :func:`~application.auth.set_operator_certificate_source_secret`
        Operator-facing mutation verb whose redaction and rotation behavior is
        covered by the integration cases.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import SecretStr

from ....adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_secret_store,
)
from ....tests.secure_sql import isolated_profile_storage_root
from ... import auth as _auth_facade
from ... import wizard as _wizard  # noqa: F401  (importing wizard seeds the ProfileKey registry)
from ...user_profile import profile_create_storage_span, register_minimal_profile
from ...workflow import workflow_state_repository
from .. import (
    SECURE_STORAGE_BACKEND_LABEL,
    CertificateSourceNotFoundError,
    register_operator_certificate_source,
    remove_operator_certificate_source_secret,
    resolve_certificate_source_secret,
    set_operator_certificate_source_secret,
)
from .. import _certificate_secret_backend as _backend_module
from .._certificate_secret_backend import SecureStorageCertificateSecretBackend

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RETIRED_KEYRING_SYMBOLS = (
    "KeyringCertificateSecretBackend",
    "CertificateSecretBackendKind",
    "CertificateSecretBackendUnavailableError",
    "CertificateSecretNotFoundError",
    "certificate_secret_backend",
)

_BUCKET_ID = "44444444-4444-4444-8444-444444444444"
_OTHER_BUCKET_ID = "55555555-5555-4555-8555-555555555555"
_PROFILE_LABEL = "gestor-cert-secret"


def _register_operator_profile():
    return lambda state: register_minimal_profile(
        state,
        profile_id=_BUCKET_ID,
        display_name=_PROFILE_LABEL,
    )


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    """Open an isolated storage root plus an active bucket session for the whole test.

    Mirrors the sibling ``test_certificate_sources_check.py`` fixture.
    """
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET_ID),
    ):
        yield


# ---------------------------------------------------------------------------
# Pure backend unit tests: SecureStorageCertificateSecretBackend against a
# real, isolated SecretStore (no active-bucket session required).
# ---------------------------------------------------------------------------


@pytest.fixture
def secret_store(tmp_path: Path) -> Iterator[SecretStore]:
    provider = EphemeralMasterKeyProvider()
    blob_store = EncryptedBlobStore(root_dir=tmp_path / "blobs", master_key_provider=provider)
    store = SecretStore(store_dir=tmp_path / "secrets", blob_store=blob_store, master_key_provider=provider)
    yield store


def test_secure_storage_backend_roundtrips_a_secret(secret_store: SecretStore) -> None:
    """A secret set through the backend is readable back through the same backend."""
    backend = SecureStorageCertificateSecretBackend(bucket_id=_BUCKET_ID, store=secret_store)

    backend.set("personal", SecretStr("correct-horse-battery-staple"))
    resolved = backend.get("personal")

    assert resolved is not None
    assert resolved.get_secret_value() == "correct-horse-battery-staple"


def test_secure_storage_backend_get_is_none_when_unset(secret_store: SecretStore) -> None:
    """A source with no registered secret resolves to ``None``, not an error."""
    backend = SecureStorageCertificateSecretBackend(bucket_id=_BUCKET_ID, store=secret_store)

    assert backend.get("never-registered") is None


def test_secure_storage_backend_set_rotates_an_existing_secret(secret_store: SecretStore) -> None:
    """Calling ``set`` again on the same name replaces the prior secret (rotation)."""
    backend = SecureStorageCertificateSecretBackend(bucket_id=_BUCKET_ID, store=secret_store)

    backend.set("personal", SecretStr("old-passphrase"))
    backend.set("personal", SecretStr("new-passphrase"))
    resolved = backend.get("personal")

    assert resolved is not None
    assert resolved.get_secret_value() == "new-passphrase"


def test_secure_storage_backend_remove_is_idempotent(secret_store: SecretStore) -> None:
    """Removing a secret returns ``True`` once, then ``False`` on a repeat call (no-op)."""
    backend = SecureStorageCertificateSecretBackend(bucket_id=_BUCKET_ID, store=secret_store)
    backend.set("personal", SecretStr("passphrase"))

    first = backend.remove("personal")
    second = backend.remove("personal")

    assert first is True
    assert second is False
    assert backend.get("personal") is None


def test_secure_storage_backend_scopes_secrets_by_bucket(secret_store: SecretStore) -> None:
    """Two profile buckets never see each other's certificate secrets."""
    backend_a = SecureStorageCertificateSecretBackend(bucket_id=_BUCKET_ID, store=secret_store)
    backend_b = SecureStorageCertificateSecretBackend(bucket_id=_OTHER_BUCKET_ID, store=secret_store)

    backend_a.set("personal", SecretStr("bucket-a-secret"))

    assert backend_b.get("personal") is None


def test_secure_storage_backend_never_leaks_secret_in_repr(secret_store: SecretStore) -> None:
    """The resolved :class:`~pydantic.SecretStr` never leaks its value via ``repr``."""
    backend = SecureStorageCertificateSecretBackend(bucket_id=_BUCKET_ID, store=secret_store)
    backend.set("personal", SecretStr("do-not-leak-me"))

    resolved = backend.get("personal")

    assert resolved is not None
    assert "do-not-leak-me" not in repr(resolved)
    assert "do-not-leak-me" not in str(resolved)


def test_secure_storage_backend_request_witness_is_stable_keyed_and_secret_free(
    secret_store: SecretStore,
) -> None:
    """Retry matching uses a stable master-keyed witness, never the secret value."""
    backend = SecureStorageCertificateSecretBackend(bucket_id=_BUCKET_ID, store=secret_store)

    first = backend.request_witness("personal", SecretStr("do-not-persist-in-workflow"))
    repeated = backend.request_witness("personal", SecretStr("do-not-persist-in-workflow"))
    different = backend.request_witness("personal", SecretStr("different-secret"))

    assert first == repeated
    assert first != different
    assert len(first) == 64
    assert "do-not-persist-in-workflow" not in first


# ---------------------------------------------------------------------------
# Operator-verb integration tests: the CLI-facing service functions, wired
# through a real workflow-state repository and an injected SecretStore.
# ---------------------------------------------------------------------------


@pytest.fixture
def _isolated_secret_store(tmp_path: Path) -> Iterator[SecretStore]:
    """Inject a deterministic :class:`SecretStore` for the operator-verb tests.

    ``get_secret_store()`` is a process-wide singleton; overriding it for
    the duration of each test keeps the operator verbs' secret writes
    isolated from any other test in the same pytest process.
    """
    provider = EphemeralMasterKeyProvider()
    blob_store = EncryptedBlobStore(root_dir=tmp_path / "op-blobs", master_key_provider=provider)
    store = SecretStore(store_dir=tmp_path / "op-secrets", blob_store=blob_store, master_key_provider=provider)
    override_secret_store(store)
    try:
        yield store
    finally:
        override_secret_store(None)


def test_set_operator_certificate_source_secret_requires_a_registered_source(
    _isolated_secret_store: SecretStore,
) -> None:
    """Binding a secret to an unregistered source name is refused, not silently created."""
    workflow_state_repository().update(_register_operator_profile())

    with pytest.raises(CertificateSourceNotFoundError):
        set_operator_certificate_source_secret(name="ghost", secret=SecretStr("passphrase"))


def test_set_then_resolve_roundtrips_the_secret(_isolated_secret_store: SecretStore, tmp_path: Path) -> None:
    """A secret set via the operator verb is resolvable via the operator resolver."""
    workflow_state_repository().update(_register_operator_profile())
    cert_path = tmp_path / "personal.p12"
    cert_path.write_bytes(b"placeholder cert")
    register_operator_certificate_source(name="personal", certificate_path=cert_path)

    result = set_operator_certificate_source_secret(name="personal", secret=SecretStr("correct-horse-battery-staple"))

    assert result.name == "personal"
    assert result.has_secret is True
    assert result.rotated is False
    assert result.backend == SECURE_STORAGE_BACKEND_LABEL

    resolved = resolve_certificate_source_secret(name="personal", bucket_id=_BUCKET_ID)
    assert resolved is not None
    assert resolved.get_secret_value() == "correct-horse-battery-staple"


def test_set_operator_certificate_source_secret_never_carries_secret_in_result(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """The mutation result never carries the secret value itself, only its presence."""
    workflow_state_repository().update(_register_operator_profile())
    cert_path = tmp_path / "personal.p12"
    cert_path.write_bytes(b"placeholder cert")
    register_operator_certificate_source(name="personal", certificate_path=cert_path)

    result = set_operator_certificate_source_secret(name="personal", secret=SecretStr("do-not-leak-me"))

    assert "do-not-leak-me" not in repr(result)
    assert "do-not-leak-me" not in result.model_dump_json()


def test_set_operator_certificate_source_secret_twice_reports_rotated(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """A second ``set`` call on the same source reports ``rotated=True``."""
    workflow_state_repository().update(_register_operator_profile())
    cert_path = tmp_path / "personal.p12"
    cert_path.write_bytes(b"placeholder cert")
    register_operator_certificate_source(name="personal", certificate_path=cert_path)

    first = set_operator_certificate_source_secret(name="personal", secret=SecretStr("old-passphrase"))
    second = set_operator_certificate_source_secret(name="personal", secret=SecretStr("new-passphrase"))

    assert first.rotated is False
    assert second.rotated is True
    resolved = resolve_certificate_source_secret(name="personal", bucket_id=_BUCKET_ID)
    assert resolved is not None
    assert resolved.get_secret_value() == "new-passphrase"


def test_remove_operator_certificate_source_secret_is_idempotent(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """Removing a certificate source's secret twice is a no-op the second time."""
    workflow_state_repository().update(_register_operator_profile())
    cert_path = tmp_path / "personal.p12"
    cert_path.write_bytes(b"placeholder cert")
    register_operator_certificate_source(name="personal", certificate_path=cert_path)
    set_operator_certificate_source_secret(name="personal", secret=SecretStr("passphrase"))

    first = remove_operator_certificate_source_secret(name="personal")
    second = remove_operator_certificate_source_secret(name="personal")

    assert first.removed is True
    assert second.removed is False
    assert resolve_certificate_source_secret(name="personal", bucket_id=_BUCKET_ID) is None


def test_resolve_certificate_source_secret_is_none_when_never_set(
    _isolated_secret_store: SecretStore,
    tmp_path: Path,
) -> None:
    """A registered source with no bound secret resolves to ``None``."""
    workflow_state_repository().update(_register_operator_profile())
    cert_path = tmp_path / "personal.p12"
    cert_path.write_bytes(b"placeholder cert")
    register_operator_certificate_source(name="personal", certificate_path=cert_path)

    assert resolve_certificate_source_secret(name="personal", bucket_id=_BUCKET_ID) is None


# ---------------------------------------------------------------------------
# Post-cutover surface: no certificate keyring backend, selector, factory,
# fallback, migration, probe, or cleanup path survives. Secure storage is the
# sole authority.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("symbol", _RETIRED_KEYRING_SYMBOLS)
def test_retired_keyring_symbol_absent_from_backend_module(symbol: str) -> None:
    """The keyring backend, backend-kind selector, factory, and errors are deleted."""
    assert not hasattr(_backend_module, symbol), f"{symbol} must be deleted from the certificate-secret backend module"


@pytest.mark.parametrize("symbol", _RETIRED_KEYRING_SYMBOLS)
def test_retired_keyring_symbol_absent_from_auth_facade(symbol: str) -> None:
    """The retired keyring surface is no longer exported from ``application.auth``."""
    assert not hasattr(_auth_facade, symbol), f"{symbol} must not be re-exported from the application.auth facade"
    assert symbol not in _auth_facade.__all__


def test_secure_storage_backend_is_the_only_public_backend() -> None:
    """The module exposes exactly the secure-storage backend, its protocol, and the label."""
    assert set(_backend_module.__all__) == {
        "SECURE_STORAGE_BACKEND_LABEL",
        "CertificateSecretBackend",
        "SecureStorageCertificateSecretBackend",
    }
    assert SECURE_STORAGE_BACKEND_LABEL == "secure_storage"
