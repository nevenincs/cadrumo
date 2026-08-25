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

import ast
import inspect
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import SecretStr

from ...adapters.outbound.storage import windows_worst_case_object_path_suffix_length
from ...core import AuthProviderKind, RegistryAuthorityGrade
from ...core.config import override_settings
from ..auth.probes import ProviderProbeResult
from ..preflight import (
    _ERROR_PROBE_RESULTS,
    _OK_PROBE_RESULTS,
    _UNCONFIGURED_PROBE_RESULTS,
    _WARN_PROBE_RESULTS,
    HealthSeverity,
    PreflightCheck,
    grade_provider_probe_result,
    probe_auth_providers,
    probe_portal_registry_health,
    probe_registry_referential_integrity,
    probe_storage_corpus_env,
    run_preflight_checks,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Measured from the storage adapter's real on-disk grammar, the same value the
#: composition root supplies in production. Reaching for it here keeps these
#: probes exercising the true margin rather than a hand-picked sample.
_SUFFIX_LENGTH = windows_worst_case_object_path_suffix_length()


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
    assert cert.precondition_verdict is None
    assert cert.facts["probe_result"] in {
        ProviderProbeResult.NO_PROVIDER.value,
        ProviderProbeResult.NO_PATH_SET.value,
    }


def test_auth_provider_certificate_missing_file_is_error_with_remediation(tmp_path: Path) -> None:
    """A configured certificate path pointing at a missing file is a red row."""
    missing = tmp_path / "does-not-exist.p12"
    with override_settings(cadrumo_certificate_path=missing):
        rows = probe_auth_providers()
    cert = _row(rows, "auth-provider:certificate")
    assert cert.healthy is False
    assert cert.severity is HealthSeverity.ERROR
    assert cert.precondition_verdict is not None
    assert cert.precondition_verdict.action is not None
    assert cert.precondition_verdict.action.action_id == "operator.auth.configure"
    assert cert.precondition_verdict.evidence[0].values == cert.facts


def test_auth_provider_clave_invalid_identity_is_error() -> None:
    """A malformed Cl@ve Móvil DNI/NIE is classified as an error row."""
    with override_settings(cadrumo_clave_movil_dni_nie=SecretStr("NOT-A-VALID-ID")):
        rows = probe_auth_providers()
    clave = _row(rows, "auth-provider:clave_movil")
    assert clave.healthy is False
    assert clave.severity is HealthSeverity.ERROR
    assert clave.precondition_verdict is not None
    assert clave.precondition_verdict.evidence[0].values == clave.facts


def test_every_probe_result_belongs_to_exactly_one_severity_band() -> None:
    """The four bands must partition ProviderProbeResult — no member ungraded, none double-graded.

    This is the structural guarantee behind the doctor's honesty: a probe
    result added without a band would otherwise be graded by the fall-through,
    and the fall-through is a defect report, not a verdict. Reds the moment a
    new member lands unclassified.
    """
    bands = {
        "error": _ERROR_PROBE_RESULTS,
        "warn": _WARN_PROBE_RESULTS,
        "unconfigured": _UNCONFIGURED_PROBE_RESULTS,
        "ok": _OK_PROBE_RESULTS,
    }
    declared = frozenset(ProviderProbeResult)
    banded: set[ProviderProbeResult] = set()
    for name, band in bands.items():
        overlap = banded & band
        assert not overlap, f"band {name} double-grades {sorted(overlap)}"
        unknown = band - declared
        assert not unknown, f"band {name} names non-members {sorted(unknown)}"
        banded |= band
    assert banded == declared, f"ungraded ProviderProbeResult members: {sorted(declared - banded)}"


def test_every_declared_probe_result_grades_without_the_defect_fall_through() -> None:
    """No real probe result reaches the fall-through, so the fall-through only reports defects."""
    for member in ProviderProbeResult:
        severity, healthy = grade_provider_probe_result(AuthProviderKind.CERTIFICATE, member)
        if member in _OK_PROBE_RESULTS | _UNCONFIGURED_PROBE_RESULTS:
            assert healthy is True and severity is HealthSeverity.OK, member.value


# ── #102 — secure-storage, bundled-corpus, and configuration preflight ───────


def test_storage_root_healthy_when_ancestor_writable(tmp_path: Path) -> None:
    """A storage root under a writable directory is reachable and OK."""
    with override_settings(cadrumo_local_storage_root=tmp_path / "storage" / "nested"):
        rows = probe_storage_corpus_env(object_path_suffix_length=_SUFFIX_LENGTH)
    storage = _row(rows, "storage:local-root")
    assert storage.healthy is True
    assert storage.severity is HealthSeverity.OK


def test_storage_root_error_when_ancestor_is_a_file(tmp_path: Path) -> None:
    """A storage root whose nearest existing ancestor is a file is a red row."""
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    with override_settings(cadrumo_local_storage_root=blocker / "sub"):
        rows = probe_storage_corpus_env(object_path_suffix_length=_SUFFIX_LENGTH)
    storage = _row(rows, "storage:local-root")
    assert storage.healthy is False
    assert storage.severity is HealthSeverity.ERROR
    assert storage.precondition_verdict is not None
    assert storage.precondition_verdict.evidence[0].values == storage.facts


def test_corpus_row_healthy_for_bundled_normatives() -> None:
    """The bundled legal-normatives corpus ships with the package and is present."""
    rows = probe_storage_corpus_env(object_path_suffix_length=_SUFFIX_LENGTH)
    normatives = _row(rows, "corpus:normatives")
    assert normatives.healthy is True
    assert normatives.severity is HealthSeverity.OK


def test_corpus_row_error_when_corpus_root_missing(tmp_path: Path) -> None:
    """A missing corpus root surfaces an error row with a reinstall remediation."""
    with override_settings(aeat_normatives_root=tmp_path / "absent-corpus"):
        rows = probe_storage_corpus_env(object_path_suffix_length=_SUFFIX_LENGTH)
    normatives = _row(rows, "corpus:normatives")
    assert normatives.healthy is False
    assert normatives.severity is HealthSeverity.ERROR
    assert normatives.facts["corpus_present"] is False
    assert normatives.precondition_verdict is not None
    assert normatives.precondition_verdict.action is None


def test_env_configuration_warns_without_passphrase() -> None:
    """An absent master-key passphrase is a non-blocking advisory (locked store)."""
    with override_settings(cadrumo_secret_passphrase=None):
        rows = probe_storage_corpus_env(object_path_suffix_length=_SUFFIX_LENGTH)
    env = _row(rows, "env:configuration")
    assert env.healthy is True
    assert env.severity is HealthSeverity.WARN


def test_env_configuration_ok_with_passphrase() -> None:
    """A configured master-key passphrase reports an OK configuration row."""
    with override_settings(cadrumo_secret_passphrase=SecretStr("workstation-secret")):
        rows = probe_storage_corpus_env(object_path_suffix_length=_SUFFIX_LENGTH)
    env = _row(rows, "env:configuration")
    assert env.healthy is True
    assert env.severity is HealthSeverity.OK


def test_registry_row_healthy_when_all_references_resolve() -> None:
    """The bundled registry passes the real ID gate and reports a healthy row."""
    row = probe_registry_referential_integrity()
    assert row.check == "registry:referential-integrity"
    assert row.healthy is True
    assert row.severity is HealthSeverity.OK


def test_registry_probe_snapshots_every_real_revision_at_its_declared_grade() -> None:
    """Bundled applicability, calculation, and filing revisions retain their exact grade."""
    from ...domain.calculations.registry import (
        bundled_authority,
    )
    from ..preflight import _probe_registry_authority

    authority = bundled_authority()
    expected = {
        (modelo.id, revision.id): revision.effective_authority_grade
        for modelo in authority.modelos
        for revision in modelo.revisions.values()
        if _representative_context_exists(revision)
    }
    row = _probe_registry_authority(authority)

    assert row.healthy is True
    assert set(expected.values()) == set(RegistryAuthorityGrade)
    assert {key: value for key, value in row.facts.items() if key.startswith("grade_")} == {
        f"grade_{grade.value}_count": sum(observed is grade for observed in expected.values())
        for grade in RegistryAuthorityGrade
    }


def test_registry_probe_binds_the_snapshot_grade_to_the_observed_revision_grade() -> None:
    """The reported grade and snapshot keyword share one production local."""
    from ..preflight import _probe_registry_authority

    tree = ast.parse(inspect.getsource(_probe_registry_authority))
    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "requested_grade" for target in node.targets)
    ]
    assert len(assignments) == 1
    assert ast.unparse(assignments[0].value) == "revision.effective_authority_grade"
    snapshot_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "snapshot"
    ]
    assert len(snapshot_calls) == 1
    grade_keyword = next(keyword for keyword in snapshot_calls[0].keywords if keyword.arg == "grade")
    assert isinstance(grade_keyword.value, ast.Name)
    assert grade_keyword.value.id == "requested_grade"


def test_registry_probe_still_reports_real_dangling_references() -> None:
    """Removing the real legal catalogue makes snapshot reference validation red."""
    from ...domain.calculations import registry as registry_module

    authority = registry_module.bundled_authority()
    broken = replace(
        authority,
        catalogues=authority.catalogues.model_copy(update={"legal": {}}),
        _snapshots={},
    )
    from ..preflight import _probe_registry_authority

    row = _probe_registry_authority(broken)

    assert row.healthy is False
    assert row.severity is HealthSeverity.ERROR
    assert int(row.facts["failure_count"]) > 0


def test_registry_probe_keeps_an_ungraded_revision_fail_closed() -> None:
    """Passing the effective floor never turns an absent grade into a declaration."""
    from ...domain.calculations import registry as registry_module
    from ..preflight import _probe_registry_authority

    authority = registry_module.bundled_authority()
    source_modelo = authority.modelos[0]
    source_revision = next(iter(source_modelo.revisions.values()))
    ungraded = source_revision.model_copy(update={"authority_grade": None})
    modelo = source_modelo.model_copy(update={"revisions": {ungraded.id: ungraded}})

    broken = replace(
        authority,
        modelos=(modelo,),
        _modelos_by_id={modelo.id: modelo},
        _snapshots={},
    )
    row = _probe_registry_authority(broken)

    assert row.healthy is False
    assert row.facts == {
        "revisions_checked": 1,
        "failure_count": 1,
        f"grade_{ungraded.effective_authority_grade.value}_count": 1,
    }


def _representative_context_exists(revision: object) -> bool:
    """Mirror only the probe's inclusion boundary, not its grade decision."""
    from ..preflight import _representative_filing_context

    year, period = _representative_filing_context(revision)
    return year is not None and period is not None


# ── Aggregate ────────────────────────────────────────────────────────────────


def test_run_preflight_checks_never_raises_and_covers_every_dimension() -> None:
    """The aggregate returns typed rows for every dimension and never raises."""
    rows = run_preflight_checks(object_path_suffix_length=_SUFFIX_LENGTH)
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
        rows = probe_storage_corpus_env(object_path_suffix_length=_SUFFIX_LENGTH)
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
        rows = probe_storage_corpus_env(object_path_suffix_length=_SUFFIX_LENGTH)
    row = _row(rows, "storage:windows-long-path")

    if sys.platform != "win32" or windows_long_paths_enabled():
        assert row.healthy is True
        assert row.facts["path_limit_applicable"] is False
    else:
        assert row.facts["storage_root"] == str(deep_root)
        assert row.severity in (HealthSeverity.ERROR, HealthSeverity.WARN)
        if row.healthy:
            assert row.precondition_verdict is None
        else:
            assert row.precondition_verdict is not None


# ── #413 — portal-registry health / recorded portal drift ────────────────────


def test_portal_health_ok_offline_when_no_drift_recorded() -> None:
    """With no recorded drift (the offline default) the row is healthy and names the count."""
    row = probe_portal_registry_health()
    assert row.check == "portal-registry:health"
    assert row.healthy is True
    assert row.severity is HealthSeverity.OK
    assert row.facts["drift_count"] == 0


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
    assert row.facts["drift_count"] == 1
    assert row.facts["stable_drift_present"] is False
    assert row.precondition_verdict is None


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
    assert row.facts["drift_count"] == 1
    assert row.facts["stable_drift_present"] is True
    assert row.precondition_verdict is not None
    assert row.precondition_verdict.evidence[0].values == row.facts
