"""CLI integration tests for ``aeat config auth certificate ...``.

Exercises the real Typer command tree against a real profile bucket and
real encrypted secure-object storage — no mocks. Covers multi-cert source
resolution and expiry/rotation awareness.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from .....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from .....adapters.persistence.storage import (
    EncryptedBlobStore,
    SecretStore,
    activate_master_key_provider,
    get_master_key_provider,
    override_secret_store,
    secure_object_repository_for_active_bucket,
)
from .....application.auth import resolve_certificate_source_secret
from .....application.user_profile import profile_storage_session
from .....application.workflow import workflow_state_repository
from .....core import resolve_active_bucket_id
from .....domain.buckets import BucketEvent, BucketEventType
from .....tests.cli_runner import invoke_typer_app
from .....tests.master_key import EphemeralMasterKeyProvider
from .....tests.secure_sql import isolated_profile_storage_root
from ... import app as root_app

# serial: these tests activate the process-global master-key-provider singleton
# (activate_master_key_provider / get_master_key_provider); under `-n auto` a
# concurrently-running file on the same worker can leave that global in a state
# they observe, so they must run in the serial (-n0) pass. Green standalone.
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_CERT_SECRET = "correct-horse-battery-staple"  # noqa: S105 - synthetic test fixture, not a secret
_ROTATED_CERT_SECRET = "rotated-horse-battery-staple"  # noqa: S105 - synthetic test fixture


def _create_profile() -> None:
    create = invoke_typer_app(
        root_app,
        [
            "config",
            "profile",
            "create",
            "gestor",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--entity-type",
            "natural_person",
            "--name",
            "Gestor",
            "--surnames",
            "Multi",
            "--activity",
            "gestoria",
            "--iva-regime",
            "GENERAL",
        ],
    )
    assert create.exit_code == 0, f"profile create failed: {create.output}"


@contextmanager
def _blocking_certificate_secret_event_commit(db_path: Path) -> Iterator[None]:
    trigger_name = "fail_cli_certificate_secret_event_finalize"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            f"""
            CREATE TRIGGER {trigger_name}
            BEFORE UPDATE ON secure_objects
            WHEN OLD.namespace = 'cadrumo.domain.buckets.event_history'
            BEGIN
                SELECT RAISE(ABORT, 'CLI certificate secret event finalize blocked');
            END
            """,
        )
        connection.commit()
    try:
        yield
    finally:
        with sqlite3.connect(db_path) as connection:
            connection.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
            connection.commit()


def _active_bucket_id() -> str:
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    return bucket_id


def _certificate_secret_events(
    *,
    bucket_id: str,
    event_type: BucketEventType,
) -> tuple[BucketEvent, ...]:
    with profile_storage_session(bucket_id):
        objects = secure_object_repository_for_active_bucket()
        return tuple(
            event
            for event in BucketEventHistoryRepository(objects=objects).load().events.values()
            if event.event_type is event_type
        )


def test_certificate_register_requires_active_profile(tmp_path: Path) -> None:
    # Invoke through the ROOT app (the production path). Invoking the config
    # sub-app directly is not production-faithful and breaks under test
    # ordering once the full app has lazily materialised the config subtree
    # (see #211). The root app's error boundary RENDERS the refusal, so assert
    # the rendered refusal (a clean refusal, not a crash).
    with isolated_profile_storage_root(tmp_path=tmp_path):
        cert_path = tmp_path / "personal.p12"
        cert_path.write_bytes(b"placeholder cert")
        result = invoke_typer_app(
            root_app,
            ["config", "auth", "certificate", "register", "--name", "personal", "--file", str(cert_path)],
        )
        assert result.exit_code != 0, result.output
        assert "Traceback" not in result.output, result.output
        assert "Refused" in result.output, result.output


def test_certificate_register_list_select_remove_happy_path(tmp_path: Path) -> None:
    """Register two named sources, enumerate both, select one, then remove it.

    This is the multi-cert slice's core contract: a gestor managing
    several entities registers one certificate per entity and selects
    the active one without re-running ``auth configure --file``.

    Every write invocation after profile creation shares one held-open
    master-key session (:func:`activate_master_key_provider`): the
    in-process ``invoke_typer_app`` runner does not re-open a bucket
    session per invocation the way a fresh CLI process does, matching
    the established pattern in ``test_config_auth_accepts_supported_provider_and_rejects_others``.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()

        personal = tmp_path / "personal.p12"
        personal.write_bytes(b"placeholder personal cert")
        apoderado = tmp_path / "apoderado-acme.p12"
        apoderado.write_bytes(b"placeholder apoderado cert")

        with activate_master_key_provider(get_master_key_provider()):
            register_personal = invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "register", "--name", "personal", "--file", str(personal)],
            )
            register_apoderado = invoke_typer_app(
                root_app,
                [
                    "config",
                    "auth",
                    "certificate",
                    "register",
                    "--name",
                    "apoderado-acme",
                    "--file",
                    str(apoderado),
                    "--friendly-name",
                    "ACME SL",
                ],
            )
            listed = invoke_typer_app(root_app, ["config", "auth", "certificate", "list"])
            selected = invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "select", "--name", "apoderado-acme"],
            )
            listed_after = invoke_typer_app(root_app, ["config", "auth", "certificate", "list"])
            removed = invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "remove", "--name", "personal"],
            )
            listed_final = invoke_typer_app(root_app, ["config", "auth", "certificate", "list"])

        assert register_personal.exit_code == 0, f"register personal failed: {register_personal.output}"
        assert "name\tpersonal" in register_personal.output
        assert register_apoderado.exit_code == 0, f"register apoderado failed: {register_apoderado.output}"

        assert listed.exit_code == 0, f"list failed: {listed.output}"
        assert "personal" in listed.output
        assert "apoderado-acme" in listed.output
        assert "active_source\t<none>" in listed.output

        assert selected.exit_code == 0, f"select failed: {selected.output}"
        assert "active\tTrue" in selected.output
        assert str(apoderado) in selected.output

        assert listed_after.exit_code == 0, f"list-after-select failed: {listed_after.output}"
        assert "active_source\tapoderado-acme" in listed_after.output

        assert removed.exit_code == 0, f"remove failed: {removed.output}"
        assert "removed\tTrue" in removed.output

        assert listed_final.exit_code == 0, f"final list failed: {listed_final.output}"
        assert "personal" not in listed_final.output
        assert "active_source\tapoderado-acme" in listed_final.output


def test_certificate_select_unregistered_name_refuses(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()

        with activate_master_key_provider(get_master_key_provider()):
            # Invoke through the ROOT app (production path); see the analogous
            # note on `test_certificate_register_requires_active_profile` and
            # #211.
            result = invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "select", "--name", "does-not-exist"],
            )
        assert result.exit_code != 0, result.output
        assert "Traceback" not in result.output, result.output
        assert "Refused" in result.output, result.output


def test_certificate_remove_unregistered_name_is_a_no_op(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()

        with activate_master_key_provider(get_master_key_provider()):
            result = invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "remove", "--name", "never-registered"],
            )
        assert result.exit_code == 0, f"remove of unregistered name must not error: {result.output}"
        assert "removed\tFalse" in result.output


# ── certificate check (expiry/rotation awareness) ───────────────────────────


def _build_pkcs12(
    tmp_path: Path,
    *,
    not_valid_before: datetime,
    not_valid_after: datetime,
    name: str,
) -> Path:
    """Generate a real self-signed PKCS#12 bundle with the given validity window."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, name),
        ],
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_valid_before)
        .not_valid_after(not_valid_after)
        .sign(key, hashes.SHA256())
    )
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=name.encode("utf-8"),
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(_CERT_SECRET.encode("utf-8")),
    )
    out = tmp_path / f"{name}.p12"
    out.write_bytes(pfx_bytes)
    return out


def test_certificate_check_reports_ok_and_expiring_per_source(tmp_path: Path) -> None:
    """``certificate check`` classifies each registered source independently.

    A gestor with one valid certificate and one certificate inside the
    renewal window must see both verdicts in one report, with a
    non-blocking warning naming the expiring source — never silently
    masked by the valid one.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        now = datetime.now(UTC)
        valid_cert = _build_pkcs12(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=300),
            name="personal",
        )
        expiring_cert = _build_pkcs12(
            tmp_path,
            not_valid_before=now - timedelta(days=1),
            not_valid_after=now + timedelta(days=10),
            name="apoderado-acme",
        )

        with activate_master_key_provider(get_master_key_provider()):
            invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "register", "--name", "personal", "--file", str(valid_cert)],
            )
            invoke_typer_app(
                root_app,
                [
                    "config",
                    "auth",
                    "certificate",
                    "register",
                    "--name",
                    "apoderado-acme",
                    "--file",
                    str(expiring_cert),
                ],
            )
            invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "secret", "set", "--name", "personal", "--secret", _CERT_SECRET],
            )
            invoke_typer_app(
                root_app,
                [
                    "config",
                    "auth",
                    "certificate",
                    "secret",
                    "set",
                    "--name",
                    "apoderado-acme",
                    "--secret",
                    _CERT_SECRET,
                ],
            )
            checked = invoke_typer_app(root_app, ["config", "auth", "certificate", "check"])

        assert checked.exit_code == 0, f"check failed: {checked.output}"
        assert "personal" in checked.output
        assert "\tok\t" in checked.output
        assert "apoderado-acme" in checked.output
        assert "\texpiring\t" in checked.output
        assert "WARNING\tapoderado-acme" in checked.output


def test_certificate_check_reports_expired_certificate(tmp_path: Path) -> None:
    """``certificate check`` classifies an already-lapsed certificate as expired, never corrupt."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        now = datetime.now(UTC)
        expired_cert = _build_pkcs12(
            tmp_path,
            not_valid_before=now - timedelta(days=400),
            not_valid_after=now - timedelta(days=5),
            name="expired-cert",
        )

        with activate_master_key_provider(get_master_key_provider()):
            invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "register", "--name", "expired-cert", "--file", str(expired_cert)],
            )
            invoke_typer_app(
                root_app,
                [
                    "config",
                    "auth",
                    "certificate",
                    "secret",
                    "set",
                    "--name",
                    "expired-cert",
                    "--secret",
                    _CERT_SECRET,
                ],
            )
            checked = invoke_typer_app(root_app, ["config", "auth", "certificate", "check"])

        assert checked.exit_code == 0, f"check failed: {checked.output}"
        assert "\texpired\t" in checked.output
        assert "WARNING\texpired-cert" in checked.output


def test_certificate_check_with_no_registered_sources_reports_none(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()

        with activate_master_key_provider(get_master_key_provider()):
            result = invoke_typer_app(root_app, ["config", "auth", "certificate", "check"])

        assert result.exit_code == 0, f"check failed: {result.output}"
        assert "sources\t<none>" in result.output


# ── certificate secret set/remove (per-source secret backend, #591 slice) ───


@pytest.fixture
def _isolated_secret_store(tmp_path: Path):
    """Inject a deterministic :class:`SecretStore` for the secret-verb CLI tests.

    ``override_secret_store`` installs an explicit process-wide test store for
    the duration of each test, keeping CLI secret writes isolated from any
    other test in the same pytest process.
    """
    provider = EphemeralMasterKeyProvider()
    blob_store = EncryptedBlobStore(root_dir=tmp_path / "cli-secret-blobs", master_key_provider=provider)
    store = SecretStore(store_dir=tmp_path / "cli-secrets", blob_store=blob_store, master_key_provider=provider)
    override_secret_store(store)
    try:
        yield store
    finally:
        override_secret_store(None)


def test_certificate_secret_set_requires_a_registered_source(tmp_path: Path, _isolated_secret_store) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()

        with activate_master_key_provider(get_master_key_provider()):
            # Invoke through the ROOT app (production path); see #211.
            result = invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "secret", "set", "--name", "ghost", "--secret", _CERT_SECRET],
            )

        assert result.exit_code != 0, result.output
        assert "Traceback" not in result.output, result.output
        assert "Refused" in result.output, result.output


def test_certificate_secret_set_then_remove_roundtrip(tmp_path: Path, _isolated_secret_store) -> None:
    """Setting a secret, rotating it, then removing it never leaks the secret value in output."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        cert_path = tmp_path / "personal.p12"
        cert_path.write_bytes(b"placeholder cert")

        with activate_master_key_provider(get_master_key_provider()):
            invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "register", "--name", "personal", "--file", str(cert_path)],
            )
            first_set = invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "secret", "set", "--name", "personal", "--secret", _CERT_SECRET],
            )
            second_set = invoke_typer_app(
                root_app,
                [
                    "config",
                    "auth",
                    "certificate",
                    "secret",
                    "set",
                    "--name",
                    "personal",
                    "--secret",
                    "a-rotated-passphrase",
                ],
            )
            removed = invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "secret", "remove", "--name", "personal"],
            )
            removed_again = invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "secret", "remove", "--name", "personal"],
            )

        assert first_set.exit_code == 0, f"secret set failed: {first_set.output}"
        assert "rotated\tFalse" in first_set.output
        assert _CERT_SECRET not in first_set.output

        assert second_set.exit_code == 0, f"secret rotate failed: {second_set.output}"
        assert "rotated\tTrue" in second_set.output
        assert "a-rotated-passphrase" not in second_set.output

        assert removed.exit_code == 0, f"secret remove failed: {removed.output}"
        assert "removed\tTrue" in removed.output

        assert removed_again.exit_code == 0, f"repeat secret remove must not error: {removed_again.output}"
        assert "removed\tFalse" in removed_again.output


def test_certificate_secret_set_cli_resumes_failed_event_commit_as_set_once(
    tmp_path: Path,
    _isolated_secret_store,
) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _create_profile()
        bucket_id = _active_bucket_id()
        cert_path = tmp_path / "personal.p12"
        cert_path.write_bytes(b"placeholder cert")
        db_path = storage_root / "buckets" / bucket_id / "db" / "cadrumo.db"

        with activate_master_key_provider(get_master_key_provider()):
            registered = invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "register", "--name", "personal", "--file", str(cert_path)],
            )
            assert registered.exit_code == 0, registered.output

            with _blocking_certificate_secret_event_commit(db_path):
                failed = invoke_typer_app(
                    root_app,
                    [
                        "config",
                        "auth",
                        "certificate",
                        "secret",
                        "set",
                        "--name",
                        "personal",
                        "--secret",
                        _CERT_SECRET,
                    ],
                )

            assert failed.exit_code != 0, failed.output
            assert "Traceback" not in failed.output
            assert _CERT_SECRET not in failed.output
            with profile_storage_session(bucket_id):
                pending = workflow_state_repository().load().auth.certificate_secret_mutation_intent
                resolved = resolve_certificate_source_secret(name="personal", bucket_id=bucket_id)
            assert pending is not None
            assert pending.event_kind.value == "set"
            assert pending.prior_present is False
            assert resolved is not None
            assert resolved.get_secret_value() == _CERT_SECRET
            assert (
                _certificate_secret_events(
                    bucket_id=bucket_id,
                    event_type=BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_SET,
                )
                == ()
            )

            mismatched = invoke_typer_app(
                root_app,
                [
                    "config",
                    "auth",
                    "certificate",
                    "secret",
                    "set",
                    "--name",
                    "personal",
                    "--secret",
                    _ROTATED_CERT_SECRET,
                ],
            )
            resumed = invoke_typer_app(
                root_app,
                [
                    "config",
                    "auth",
                    "certificate",
                    "secret",
                    "set",
                    "--name",
                    "personal",
                    "--secret",
                    _CERT_SECRET,
                ],
            )

            assert mismatched.exit_code != 0, mismatched.output
            assert "Traceback" not in mismatched.output
            assert _ROTATED_CERT_SECRET not in mismatched.output
            assert resumed.exit_code == 0, resumed.output
            assert "rotated\tFalse" in resumed.output
            with profile_storage_session(bucket_id):
                final = workflow_state_repository().load()
                resolved_after_retry = resolve_certificate_source_secret(
                    name="personal",
                    bucket_id=bucket_id,
                )
            events = _certificate_secret_events(
                bucket_id=bucket_id,
                event_type=BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_SET,
            )
            rotated_events = _certificate_secret_events(
                bucket_id=bucket_id,
                event_type=BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_ROTATED,
            )

        assert final.auth.certificate_secret_mutation_intent is None
        assert resolved_after_retry is not None
        assert resolved_after_retry.get_secret_value() == _CERT_SECRET
        assert len(events) == 1
        assert events[0].occurred_at == pending.started_at
        assert events[0].payload["operation_id"] == pending.operation_id
        assert rotated_events == ()


def test_certificate_secret_rotate_cli_resumes_failed_event_commit_as_rotation_once(
    tmp_path: Path,
    _isolated_secret_store,
) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _create_profile()
        bucket_id = _active_bucket_id()
        cert_path = tmp_path / "personal.p12"
        cert_path.write_bytes(b"placeholder cert")
        db_path = storage_root / "buckets" / bucket_id / "db" / "cadrumo.db"

        with activate_master_key_provider(get_master_key_provider()):
            registered = invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "register", "--name", "personal", "--file", str(cert_path)],
            )
            initial = invoke_typer_app(
                root_app,
                [
                    "config",
                    "auth",
                    "certificate",
                    "secret",
                    "set",
                    "--name",
                    "personal",
                    "--secret",
                    _CERT_SECRET,
                ],
            )
            assert registered.exit_code == 0, registered.output
            assert initial.exit_code == 0, initial.output

            with _blocking_certificate_secret_event_commit(db_path):
                failed = invoke_typer_app(
                    root_app,
                    [
                        "config",
                        "auth",
                        "certificate",
                        "secret",
                        "set",
                        "--name",
                        "personal",
                        "--secret",
                        _ROTATED_CERT_SECRET,
                    ],
                )

            assert failed.exit_code != 0, failed.output
            assert "Traceback" not in failed.output
            assert _ROTATED_CERT_SECRET not in failed.output
            with profile_storage_session(bucket_id):
                pending = workflow_state_repository().load().auth.certificate_secret_mutation_intent
            assert pending is not None
            assert pending.event_kind.value == "rotated"
            assert pending.prior_present is True

            resumed = invoke_typer_app(
                root_app,
                [
                    "config",
                    "auth",
                    "certificate",
                    "secret",
                    "set",
                    "--name",
                    "personal",
                    "--secret",
                    _ROTATED_CERT_SECRET,
                ],
            )
            assert resumed.exit_code == 0, resumed.output
            assert "rotated\tTrue" in resumed.output
            with profile_storage_session(bucket_id):
                resolved = resolve_certificate_source_secret(name="personal", bucket_id=bucket_id)
            rotated_events = _certificate_secret_events(
                bucket_id=bucket_id,
                event_type=BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_ROTATED,
            )
            set_events = _certificate_secret_events(
                bucket_id=bucket_id,
                event_type=BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_SET,
            )

        assert resolved is not None
        assert resolved.get_secret_value() == _ROTATED_CERT_SECRET
        assert len(set_events) == 1
        assert len(rotated_events) == 1
        assert rotated_events[0].occurred_at == pending.started_at
        assert rotated_events[0].payload["operation_id"] == pending.operation_id


def test_certificate_secret_remove_cli_resumes_failed_event_commit_truthfully_once(
    tmp_path: Path,
    _isolated_secret_store,
) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _create_profile()
        bucket_id = _active_bucket_id()
        cert_path = tmp_path / "personal.p12"
        cert_path.write_bytes(b"placeholder cert")
        db_path = storage_root / "buckets" / bucket_id / "db" / "cadrumo.db"

        with activate_master_key_provider(get_master_key_provider()):
            registered = invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "register", "--name", "personal", "--file", str(cert_path)],
            )
            initial = invoke_typer_app(
                root_app,
                [
                    "config",
                    "auth",
                    "certificate",
                    "secret",
                    "set",
                    "--name",
                    "personal",
                    "--secret",
                    _CERT_SECRET,
                ],
            )
            assert registered.exit_code == 0, registered.output
            assert initial.exit_code == 0, initial.output

            with _blocking_certificate_secret_event_commit(db_path):
                failed = invoke_typer_app(
                    root_app,
                    ["config", "auth", "certificate", "secret", "remove", "--name", "personal"],
                )

            assert failed.exit_code != 0, failed.output
            assert "Traceback" not in failed.output
            with profile_storage_session(bucket_id):
                pending = workflow_state_repository().load().auth.certificate_secret_mutation_intent
                removed_secret = resolve_certificate_source_secret(name="personal", bucket_id=bucket_id)
            assert pending is not None
            assert pending.event_kind.value == "removed"
            assert pending.prior_present is True
            assert removed_secret is None

            resumed = invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "secret", "remove", "--name", "personal"],
            )
            repeated = invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "secret", "remove", "--name", "personal"],
            )
            removed_events = _certificate_secret_events(
                bucket_id=bucket_id,
                event_type=BucketEventType.AUTH_CERTIFICATE_SOURCE_SECRET_REMOVED,
            )
            with profile_storage_session(bucket_id):
                final = workflow_state_repository().load()

        assert resumed.exit_code == 0, resumed.output
        assert "removed\tTrue" in resumed.output
        assert repeated.exit_code == 0, repeated.output
        assert "removed\tFalse" in repeated.output
        assert final.auth.certificate_secret_mutation_intent is None
        assert len(removed_events) == 1
        assert removed_events[0].occurred_at == pending.started_at
        assert removed_events[0].payload["operation_id"] == pending.operation_id


def test_certificate_secret_cli_exposes_no_backend_or_legacy_grammar(
    tmp_path: Path,
    _isolated_secret_store,
) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        cert_path = tmp_path / "personal.p12"
        cert_path.write_bytes(b"placeholder cert")

        with activate_master_key_provider(get_master_key_provider()):
            invoke_typer_app(
                root_app,
                ["config", "auth", "certificate", "register", "--name", "personal", "--file", str(cert_path)],
            )
            set_backend = invoke_typer_app(
                root_app,
                [
                    "config",
                    "auth",
                    "certificate",
                    "secret",
                    "set",
                    "--name",
                    "personal",
                    "--secret",
                    _CERT_SECRET,
                    "--backend",
                    "keyring",
                ],
            )
            remove_backend = invoke_typer_app(
                root_app,
                [
                    "config",
                    "auth",
                    "certificate",
                    "secret",
                    "remove",
                    "--name",
                    "personal",
                    "--backend",
                    "keyring",
                ],
            )
            retired_commands = tuple(
                invoke_typer_app(
                    root_app,
                    ["config", "auth", "certificate", "secret", retired],
                )
                for retired in ("keyring", "migrate", "fallback", "probe", "clear", "put", "delete")
            )

        for result in (set_backend, remove_backend):
            assert result.exit_code == 2, result.output
            assert "Traceback" not in result.output, result.output
            assert "No such option: --backend" in result.output, result.output
        for result in retired_commands:
            assert result.exit_code == 2, result.output
            assert "Traceback" not in result.output, result.output
            assert "No such command" in result.output, result.output
