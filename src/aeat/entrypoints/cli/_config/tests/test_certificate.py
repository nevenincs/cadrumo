"""CLI integration tests for ``aeat config auth certificate ...``.

Exercises the real Typer command tree against a real profile bucket and
real encrypted secure-object storage — no mocks. See GitHub issue #591
(multi-cert source resolution and expiry/rotation awareness slices).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from .....adapters.persistence.storage import activate_master_key_provider, get_master_key_provider
from .....core.config import override_settings
from .....tests.cli_runner import invoke_typer_app
from .....tests.secure_sql import isolated_profile_storage_root
from ... import app as root_app
from ..._errors import CliRefusedBoundaryError
from ..__init__ import app as config_app

_CERT_SECRET = "correct-horse-battery-staple"  # noqa: S105 - synthetic test fixture, not a secret

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


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


def test_certificate_register_requires_active_profile(tmp_path: Path) -> None:
    # Invoked directly on the `config` sub-app (like the sibling apoderado
    # tests) so the root app's error boundary — which rewrites the
    # exception into a plain SystemExit — is absent and the typed
    # CliRefusedBoundaryError leaks as `result.exception` for pinning.
    with isolated_profile_storage_root(tmp_path=tmp_path):
        cert_path = tmp_path / "personal.p12"
        cert_path.write_bytes(b"placeholder cert")
        result = invoke_typer_app(
            config_app,
            ["auth", "certificate", "register", "--name", "personal", "--file", str(cert_path)],
        )
        assert result.exit_code != 0
        assert isinstance(result.exception, CliRefusedBoundaryError), (
            f"expected CliRefusedBoundaryError, got {type(result.exception).__name__}: {result.exception}"
        )


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
            # Invoked on the `config` sub-app directly; see the analogous
            # note on `test_certificate_register_requires_active_profile`.
            result = invoke_typer_app(
                config_app,
                ["auth", "certificate", "select", "--name", "does-not-exist"],
            )
        assert result.exit_code != 0
        assert isinstance(result.exception, CliRefusedBoundaryError), (
            f"expected CliRefusedBoundaryError, got {type(result.exception).__name__}: {result.exception}"
        )


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


# ── certificate check (expiry/rotation awareness, GitHub issue #591) ────────


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
            with override_settings(aeat_certificate_password_secret=_CERT_SECRET):
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
            with override_settings(aeat_certificate_password_secret=_CERT_SECRET):
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
