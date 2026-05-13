"""Application-owned diagnostics and version reporting."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from aeat import __version__

from ..adapters.persistence.storage.sql.secure_objects import (
    SecureObjectNamespaceIntegrity,
    SecureObjectRepository,
)
from ..core.config import PROJECT_ROOT
from ..core.logging import default_log_file_path, get_logger
from ..domain.calculations.registry import ValidatedRegistryAuthority
from .wizard._status import WizardStatusReport, build_wizard_status
from .workflow import workflow_state_repository

_log = get_logger(__name__)

DiagnosticStatus = Literal["ok", "warn", "fail"]


class RegistryVersionSummary(BaseModel):
    """Stable registry summary suitable for version and doctor surfaces."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    available: bool
    registry_root: str
    modelo_count: int = 0
    revision_count: int = 0
    casilla_count: int = 0
    formula_count: int = 0
    revision_ids: tuple[str, ...] = ()
    error: str | None = None


class CliVersionReport(BaseModel):
    """Version payload rendered by root CLI version surfaces."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    package_name: str
    package_version: str
    registry: RegistryVersionSummary


class DiagnosticCheck(BaseModel):
    """One concrete config doctor check."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: str
    status: DiagnosticStatus
    summary: str
    detail: str | None = None
    next_action: str | None = None


class SecureObjectIntegrityReport(BaseModel):
    """Aggregated decryptability counts across every populated namespace.

    Surfaces how many rows of the local ``secure_objects`` table can be
    decrypted under the current master key. A non-zero ``unreadable`` total
    almost always means the keychain master-key entry was rotated or
    regenerated since the affected rows were written; the plaintexts are
    cryptographically unrecoverable from this process.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespaces: tuple[SecureObjectNamespaceIntegrity, ...] = ()
    readable_total: int = 0
    unreadable_total: int = 0


class ConfigDoctorReport(BaseModel):
    """Local environment and configuration diagnostics for ``aeat config doctor``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    overall: DiagnosticStatus
    package_name: str
    package_version: str
    python_version: str
    log_file: str
    registry: RegistryVersionSummary
    setup: WizardStatusReport | None
    secure_objects: SecureObjectIntegrityReport
    checks: tuple[DiagnosticCheck, ...]


def build_cli_version_report(registry_root: Path | None = None) -> CliVersionReport:
    """Return the package and registry summary for CLI version surfaces."""

    root = registry_root or PROJECT_ROOT / "registry" / "aeat"
    return CliVersionReport(
        package_name="aeat",
        package_version=__version__,
        registry=_build_registry_version_summary(root),
    )


def build_config_doctor_report(registry_root: Path | None = None) -> ConfigDoctorReport:
    """Return local diagnostics for the config-facing doctor surface."""

    root = registry_root or PROJECT_ROOT / "registry" / "aeat"
    registry = _build_registry_version_summary(root)
    checks: list[DiagnosticCheck] = [
        DiagnosticCheck(
            name="environment.python",
            status="ok",
            summary=sys.version.split()[0],
        ),
        DiagnosticCheck(
            name="package.version",
            status="ok",
            summary=__version__,
        ),
        DiagnosticCheck(
            name="logging.file",
            status="ok" if default_log_file_path().parent.exists() else "warn",
            summary=str(default_log_file_path()),
            next_action=None if default_log_file_path().parent.exists() else "aeat --help",
        ),
        DiagnosticCheck(
            name="registry.load",
            status="ok" if registry.available else "fail",
            summary=(
                f"{registry.modelo_count} modelos, {registry.casilla_count} casillas"
                if registry.available
                else "registry unavailable"
            ),
            detail=registry.error,
        ),
    ]

    setup_report: WizardStatusReport | None = None
    try:
        state = workflow_state_repository().load()
        checks.append(DiagnosticCheck(name="secure_state.load", status="ok", summary="state backend readable"))
        setup_report = build_wizard_status(state)
        checks.append(_profile_check(setup_report))
        checks.append(_auth_check(setup_report))
    except Exception as exc:  # pragma: no cover - concrete failure mode depends on local secure backend.
        checks.append(
            DiagnosticCheck(
                name="secure_state.load",
                status="fail",
                summary="state backend unreadable",
                detail=f"{type(exc).__name__}: {exc}",
            )
        )

    secure_objects = _probe_secure_objects_integrity()
    checks.append(_secure_objects_integrity_check(secure_objects))

    return ConfigDoctorReport(
        overall=_overall_status(tuple(checks)),
        package_name="aeat",
        package_version=__version__,
        python_version=sys.version.split()[0],
        log_file=str(default_log_file_path()),
        registry=registry,
        setup=setup_report,
        secure_objects=secure_objects,
        checks=tuple(checks),
    )


def render_config_doctor_text(report: ConfigDoctorReport) -> str:
    """Render a compact human-readable doctor report."""

    lines = [
        f"Overall\t{report.overall}",
        f"Version\t{report.package_name} {report.package_version}",
        f"Python\t{report.python_version}",
        f"Logs\t{report.log_file}",
    ]
    if report.setup is not None:
        lines.append(
            f"Profile\t{report.setup.active_profile or '-'} "
            f"({report.setup.profile_present_keys}/{report.setup.profile_total_keys})"
        )
        lines.append(f"Auth\t{report.setup.auth_provider or '-'}")
    lines.append("Checks")
    for check in report.checks:
        lines.append(f"{check.status}\t{check.name}\t{check.summary}")
        if check.detail:
            lines.append(f"detail\t{check.detail}")
        if check.next_action:
            lines.append(f"next\t{check.next_action}")
    return "\n".join(lines) + "\n"


def _build_registry_version_summary(registry_root: Path) -> RegistryVersionSummary:
    try:
        authority = ValidatedRegistryAuthority.load(registry_root, source_root=PROJECT_ROOT)
    except Exception as exc:  # pragma: no cover - covered by later doctor diagnostics.
        return RegistryVersionSummary(
            available=False,
            registry_root=str(registry_root),
            error=f"{type(exc).__name__}: {exc}",
        )

    modelos = tuple(authority.modelos)
    revisions = tuple(revision for modelo in modelos for revision in modelo.revisions.values())
    return RegistryVersionSummary(
        available=True,
        registry_root=str(registry_root),
        modelo_count=len(modelos),
        revision_count=len(revisions),
        casilla_count=sum(len(revision.casillas) for revision in revisions),
        formula_count=sum(len(revision.formulas) for revision in revisions),
        revision_ids=tuple(sorted({str(revision.id) for revision in revisions})),
    )


def _probe_secure_objects_integrity() -> SecureObjectIntegrityReport:
    """Iterate every populated secure-objects namespace and aggregate counts.

    Returns an empty report when the table is empty or the engine cannot
    be reached. Non-empty results expose per-namespace counts so the
    operator can locate which application surface holds rows from a
    rotated master-key generation.
    """
    try:
        repo = SecureObjectRepository()
        namespaces = repo.list_namespaces()
    except Exception as exc:  # pragma: no cover - engine resolution depends on local backend.
        _log.debug("secure objects engine unreachable for doctor probe: %s: %s", type(exc).__name__, exc)
        return SecureObjectIntegrityReport()
    integrity = tuple(repo.probe_namespace_integrity(ns) for ns in namespaces)
    readable_total = sum(item.readable for item in integrity)
    unreadable_total = sum(item.unreadable for item in integrity)
    return SecureObjectIntegrityReport(
        namespaces=integrity,
        readable_total=readable_total,
        unreadable_total=unreadable_total,
    )


def _secure_objects_integrity_check(report: SecureObjectIntegrityReport) -> DiagnosticCheck:
    """Render the ``secure_objects.integrity`` doctor row."""
    if report.unreadable_total == 0:
        if report.readable_total == 0:
            return DiagnosticCheck(
                name="secure_objects.integrity",
                status="ok",
                summary="no rows stored",
            )
        return DiagnosticCheck(
            name="secure_objects.integrity",
            status="ok",
            summary=f"{report.readable_total} row(s) decryptable across {len(report.namespaces)} namespace(s)",
        )
    affected = ", ".join(
        f"{item.namespace} ({item.unreadable}/{item.readable + item.unreadable})"
        for item in report.namespaces
        if item.unreadable > 0
    )
    return DiagnosticCheck(
        name="secure_objects.integrity",
        status="warn",
        summary=(
            f"{report.unreadable_total} unreadable row(s) sealed under a prior master key; "
            f"{report.readable_total} row(s) decryptable"
        ),
        detail=affected,
        next_action="aeat config doctor quarantine --yes",
    )


def _profile_check(report: WizardStatusReport) -> DiagnosticCheck:
    if report.active_profile is None:
        return DiagnosticCheck(
            name="profile.active",
            status="warn",
            summary="no active profile",
            next_action="aeat config init --profile NAME --tax-id NIF",
        )
    if not report.profile_ready:
        return DiagnosticCheck(
            name="profile.required_keys",
            status="warn",
            summary=f"missing required keys: {', '.join(report.missing_required)}",
            next_action=report.next_action,
        )
    return DiagnosticCheck(
        name="profile.required_keys",
        status="ok",
        summary=f"{report.profile_present_keys}/{report.profile_total_keys} keys set",
    )


def _auth_check(report: WizardStatusReport) -> DiagnosticCheck:
    if not report.auth_provider:
        return DiagnosticCheck(
            name="auth.provider",
            status="warn",
            summary="no authentication provider configured",
            next_action="aeat config auth --provider certificate --file PATH",
        )
    if not report.login_ready:
        return DiagnosticCheck(
            name="auth.session",
            status="warn",
            summary=f"{report.auth_provider} configured but no active session",
            next_action="aeat config auth --provider certificate",
        )
    return DiagnosticCheck(name="auth.session", status="ok", summary=f"{report.auth_provider} session ready")


def _overall_status(checks: tuple[DiagnosticCheck, ...]) -> DiagnosticStatus:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "ok"


def render_cli_version_text(report: CliVersionReport) -> str:
    """Render a compact text line for human-facing version output."""

    registry = report.registry
    if not registry.available:
        return f"{report.package_name} {report.package_version} (registry unavailable: {registry.error})"
    revision_label = ", ".join(registry.revision_ids) if registry.revision_ids else "no revisions"
    return (
        f"{report.package_name} {report.package_version} "
        f"(registry revisions {revision_label}; "
        f"{registry.modelo_count} modelos, "
        f"{registry.casilla_count} casillas, "
        f"{registry.formula_count} formulas)"
    )


def secure_object_unreadable_total() -> int:
    """Return the count of rows the current master key cannot decrypt.

    Lightweight wrapper over :func:`_probe_secure_objects_integrity` for
    consumers (notably ``aeat app overview status``) that want to surface
    a concise "N rows unreadable" pointer towards
    ``aeat config doctor`` without rendering the per-namespace breakdown
    themselves. The full breakdown remains the authority of doctor.
    """
    return _probe_secure_objects_integrity().unreadable_total


def quarantine_unreadable_secure_objects() -> SecureObjectIntegrityReport:
    """Move every undecryptable secure-object row into the quarantine table.

    Delegates to :meth:`SecureObjectRepository.quarantine_unreadable_rows`,
    which creates the ``secure_objects_quarantine`` archive table on
    first use, copies each undecryptable row's metadata and (still
    encrypted) payload into the archive, then deletes the row from the
    active ``secure_objects`` table. Decryptable rows are not touched.

    The user's ciphertext is preserved in the archive; nothing is
    auto-deleted. If a missing master key is later recovered (e.g.
    restored from a recovery-key backup), the operator can manually
    re-import rows from the quarantine table.

    Returns:
        A :class:`SecureObjectIntegrityReport` whose ``namespaces``
        report carries per-namespace ``unreadable`` counts (= rows
        moved to quarantine) and ``readable`` counts (= rows retained
        in ``secure_objects``).
    """
    repo = SecureObjectRepository()
    namespaces = repo.quarantine_unreadable_rows()
    quarantined_total = sum(item.unreadable for item in namespaces)
    retained_total = sum(item.readable for item in namespaces)
    return SecureObjectIntegrityReport(
        namespaces=namespaces,
        readable_total=retained_total,
        unreadable_total=quarantined_total,
    )


__all__ = [
    "CliVersionReport",
    "ConfigDoctorReport",
    "DiagnosticCheck",
    "RegistryVersionSummary",
    "SecureObjectIntegrityReport",
    "build_cli_version_report",
    "build_config_doctor_report",
    "quarantine_unreadable_secure_objects",
    "render_cli_version_text",
    "render_config_doctor_text",
    "secure_object_unreadable_total",
]
