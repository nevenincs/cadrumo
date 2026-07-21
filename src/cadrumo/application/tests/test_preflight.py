"""Real-behavior tests for the workstation-preflight health probes.

Each probe answers one health question — per-provider certificate / Cl@ve Móvil
configuration, secure-storage / bundled-corpus / configuration preflight,
and registry referential integrity — and MUST return a typed
:class:`~cadrumo.application.preflight.PreflightCheck` for both a healthy and an
unhealthy workstation, never raising. These tests drive the real probes against
real settings overrides, a real on-disk storage/corpus layout, and the real
registry referential-integrity gate over the bundled production authority.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import SecretStr

from ...core.config import override_settings
from ..preflight import (
    HealthSeverity,
    PreflightCheck,
    probe_auth_providers,
    probe_portal_registry_health,
    probe_registry_referential_integrity,
    probe_storage_corpus_env,
    run_preflight_checks,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _row(rows: tuple[PreflightCheck, ...], check_id: str) -> PreflightCheck:
    matches = [row for row in rows if row.check == check_id]
    assert matches, f"no preflight row for {check_id!r} in {[r.check for r in rows]}"
    return matches[0]


# ── #286 — per-auth-provider certificate / Cl@ve Móvil health ────────────────


def test_auth_provider_rows_are_ok_when_no_provider_configured() -> None:
    """An unconfigured optional provider is OK — not-configured is not a fault."""
    with override_settings(cadrumo_certificate_path=None, cadrumo_clave_movil_dni_nie=None):
        rows = probe_auth_providers()
    cert = _row(rows, "auth-provider:certificate")
    assert cert.healthy is True
    assert cert.severity is HealthSeverity.OK
    assert cert.remediation == ""


def test_auth_provider_certificate_missing_file_is_error_with_remediation(tmp_path: Path) -> None:
    """A configured certificate path pointing at a missing file is a red row."""
    missing = tmp_path / "does-not-exist.p12"
    with override_settings(cadrumo_certificate_path=missing):
        rows = probe_auth_providers()
    cert = _row(rows, "auth-provider:certificate")
    assert cert.healthy is False
    assert cert.severity is HealthSeverity.ERROR
    assert cert.remediation, "a red certificate row must name a concrete remediation"


def test_auth_provider_clave_invalid_identity_is_error() -> None:
    """A malformed Cl@ve Móvil DNI/NIE is classified as an error row."""
    with override_settings(cadrumo_clave_movil_dni_nie=SecretStr("NOT-A-VALID-ID")):
        rows = probe_auth_providers()
    clave = _row(rows, "auth-provider:clave_movil")
    assert clave.healthy is False
    assert clave.severity is HealthSeverity.ERROR
    assert clave.remediation


# ── #102 — secure-storage, bundled-corpus, and configuration preflight ───────


def test_storage_root_healthy_when_ancestor_writable(tmp_path: Path) -> None:
    """A storage root under a writable directory is reachable and OK."""
    with override_settings(cadrumo_local_storage_root=tmp_path / "storage" / "nested"):
        rows = probe_storage_corpus_env()
    storage = _row(rows, "storage:local-root")
    assert storage.healthy is True
    assert storage.severity is HealthSeverity.OK


def test_storage_root_error_when_ancestor_is_a_file(tmp_path: Path) -> None:
    """A storage root whose nearest existing ancestor is a file is a red row."""
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    with override_settings(cadrumo_local_storage_root=blocker / "sub"):
        rows = probe_storage_corpus_env()
    storage = _row(rows, "storage:local-root")
    assert storage.healthy is False
    assert storage.severity is HealthSeverity.ERROR
    assert storage.remediation


def test_corpus_row_healthy_for_bundled_normatives() -> None:
    """The bundled legal-normatives corpus ships with the package and is present."""
    rows = probe_storage_corpus_env()
    normatives = _row(rows, "corpus:normatives")
    assert normatives.healthy is True
    assert normatives.severity is HealthSeverity.OK


def test_corpus_row_error_when_corpus_root_missing(tmp_path: Path) -> None:
    """A missing corpus root surfaces an error row with a reinstall remediation."""
    with override_settings(aeat_normatives_root=tmp_path / "absent-corpus"):
        rows = probe_storage_corpus_env()
    normatives = _row(rows, "corpus:normatives")
    assert normatives.healthy is False
    assert normatives.severity is HealthSeverity.ERROR
    assert "reinstall" in normatives.remediation


def test_env_configuration_warns_without_passphrase() -> None:
    """An absent master-key passphrase is a non-blocking advisory (locked store)."""
    with override_settings(cadrumo_secret_passphrase=None):
        rows = probe_storage_corpus_env()
    env = _row(rows, "env:configuration")
    assert env.healthy is True
    assert env.severity is HealthSeverity.WARN


def test_env_configuration_ok_with_passphrase() -> None:
    """A configured master-key passphrase reports an OK configuration row."""
    with override_settings(cadrumo_secret_passphrase=SecretStr("workstation-secret")):
        rows = probe_storage_corpus_env()
    env = _row(rows, "env:configuration")
    assert env.healthy is True
    assert env.severity is HealthSeverity.OK


def test_registry_row_healthy_when_all_references_resolve() -> None:
    """The bundled registry passes the real ID gate and reports a healthy row."""
    row = probe_registry_referential_integrity()
    assert row.check == "registry:referential-integrity"
    assert row.healthy is True
    assert row.severity is HealthSeverity.OK


# ── Aggregate ────────────────────────────────────────────────────────────────


def test_run_preflight_checks_never_raises_and_covers_every_dimension() -> None:
    """The aggregate returns typed rows for every dimension and never raises."""
    rows = run_preflight_checks()
    ids = {row.check for row in rows}
    assert {
        "auth-provider:certificate",
        "auth-provider:clave_movil",
        "storage:local-root",
        "corpus:normatives",
        "corpus:manuals",
        "env:configuration",
        "storage:windows-long-path",
        "registry:referential-integrity",
        "portal-registry:health",
    } <= ids
    assert all(isinstance(row, PreflightCheck) for row in rows)


# ── WIN-003 — Windows MAX_PATH (long-path) headroom ───────────────────────────


def test_windows_long_path_row_ok_when_root_has_ample_headroom(tmp_path: Path) -> None:
    """A short, shallow storage root leaves ample MAX_PATH headroom (or is OK off-Windows)."""
    with override_settings(cadrumo_local_storage_root=tmp_path / "s"):
        rows = probe_storage_corpus_env()
    row = _row(rows, "storage:windows-long-path")
    assert row.healthy is True


def test_windows_long_path_row_flags_a_deep_root(tmp_path: Path) -> None:
    """A storage root already close to MAX_PATH surfaces the ceiling detail on Windows.

    Builds a genuinely deep on-disk path (not a mock) so
    ``windows_storage_root_long_path_margin`` computes a real, small-or-negative
    margin. The row's disposition legitimately depends on the workstation's own
    ``LongPathsEnabled`` opt-in (a real, machine-wide OS setting this test must
    not mutate): with the opt-in on, the row reports OK because the ceiling does
    not apply; with it off, the deep root's real margin drives an ERROR or WARN
    row naming the resolved root. Both are asserted as legitimate outcomes so the
    test is honest about depending on real, unmutated machine state rather than
    asserting a single hardcoded disposition.
    """
    from ...core.paths import windows_long_paths_enabled

    deep_root = tmp_path
    for segment in range(6):
        deep_root = deep_root / f"segment-{segment}-{'x' * 30}"
    with override_settings(cadrumo_local_storage_root=deep_root):
        rows = probe_storage_corpus_env()
    row = _row(rows, "storage:windows-long-path")

    if sys.platform != "win32" or windows_long_paths_enabled():
        assert row.healthy is True
        assert "not applicable" in row.detail or "LongPathsEnabled is set" in row.detail
    else:
        assert str(deep_root) in row.detail
        assert row.severity in (HealthSeverity.ERROR, HealthSeverity.WARN)
        assert row.remediation


# ── #413 — portal-registry health / recorded portal drift ────────────────────


def test_portal_health_ok_offline_when_no_drift_recorded() -> None:
    """With no recorded drift (the offline default) the row is healthy and names the count."""
    row = probe_portal_registry_health()
    assert row.check == "portal-registry:health"
    assert row.healthy is True
    assert row.severity is HealthSeverity.OK
    assert "no portal drift recorded" in row.detail


def test_portal_health_warns_on_recorded_volatile_url_drift() -> None:
    """A recorded drift on a rotatable app-path URL is a non-blocking advisory."""
    from datetime import UTC, datetime

    from ...domain.portals import PORTAL_REGISTRY, UrlStability, evaluate_portal_drift

    entry = next(m for m in PORTAL_REGISTRY.values() if m.url_stability is UrlStability.VOLATILE_APP_PATH)
    drift = evaluate_portal_drift(
        entry,
        observed_url=str(entry.url).rstrip("/") + "/rotated-shell",
        detected_at=datetime(2026, 6, 30, tzinfo=UTC),
    )
    assert drift is not None
    row = probe_portal_registry_health(drift_events=(drift,))
    assert row.healthy is True
    assert row.severity is HealthSeverity.WARN
    assert entry.portal.value in row.detail
    assert row.remediation


def test_portal_health_errors_on_recorded_stable_url_drift() -> None:
    """A recorded drift on a BOE-referenced stable URL is a red integrity row."""
    from datetime import UTC, datetime

    from ...domain.portals import PORTAL_REGISTRY, UrlStability, evaluate_portal_drift

    entry = next(m for m in PORTAL_REGISTRY.values() if m.url_stability is UrlStability.STABLE_PROTOCOL_GRADE)
    drift = evaluate_portal_drift(
        entry,
        observed_url="https://impostor.example.org/moved",
        detected_at=datetime(2026, 6, 30, tzinfo=UTC),
    )
    assert drift is not None
    row = probe_portal_registry_health(drift_events=(drift,))
    assert row.healthy is False
    assert row.severity is HealthSeverity.ERROR
    assert row.remediation
