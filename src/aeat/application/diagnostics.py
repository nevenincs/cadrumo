"""Application-owned diagnostics and version reporting.

Registry diagnostics are produced by loading a :class:`ValidatedRegistryAuthority`
from the configured registry root and inspecting the available modelos and revisions.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from .. import __version__
from ..core import Modelo
from ..core.config import PROJECT_ROOT, Settings
from ..core.errors import SiteHealthError
from ..core.i18n import tr
from ..core.logging import default_log_file_path, get_logger
from ..core.redaction import CLI_PROFILE_ID_PLACEHOLDER
from ..core.resources import bundled_path
from ..core.time import now
from ._errors import DiagnosticModelError

# The browser adapter, the registry authority, the secure-object
# repository, the workflow store, and the wizard-status projection are
# all heavy import subtrees (the browser adapter and the registry parse
# alone add ~3.5s of cold-start import time). The ``aeat --version``
# fast path imports this module only for ``build_cli_version_report`` /
# ``render_cli_version_text``, neither of which needs any of them.
# Importing them lazily inside the functions that actually run keeps the
# version surface off the heavy graph (disaster ADR Ruling 4 fast-path).
if TYPE_CHECKING:
    from ..adapters.outbound.aeat.browser import SiteHealthStatus
    from ..adapters.persistence.storage.sql.secure_objects import SecureObjectNamespaceIntegrity
    from .wizard._status import WizardStatusReport
    from .workflow._models import WorkflowState
    from .workflow._profile_health import ActiveProfileHealth

_log = get_logger(__name__)

_REGISTRY_INTEGRITY_PROBE_YEAR: Final[int] = 2025
_REGISTRY_INTEGRITY_PROBE_DATE: Final[date] = date(2025, 12, 31)

DiagnosticStatus = Literal["ok", "warn", "fail"]


class RegistryVersionSummary(BaseModel):
    """Stable registry summary suitable for version and repair surfaces."""

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


DiagnosticAudience = Literal["operator", "internal"]
"""Who can act on a check.

``operator`` rows describe a state the taxpayer can themselves resolve
(an incomplete profile, a missing certificate). ``internal`` rows
describe an application-side defect the taxpayer cannot fix (a
registry-integrity regression). The renderer words the two distinctly
so a taxpayer is never alarmed into thinking an internal bug is a field
they forgot to fill in.
"""


class DiagnosticFinding(BaseModel):
    """One concrete, named sub-finding inside a :class:`DiagnosticCheck`.

    A bare counter (``31/40``) or a one-word verdict (``warn``) tells the
    operator *that* something is wrong but never *what*. Each finding
    names one specific cause in operator language and, where an
    automated route exists, the exact ``aeat ...`` command that resolves
    it. The profile-keys check emits one finding per unset key; a
    failing check emits one finding per concrete cause.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    summary: str
    detail: str | None = None
    next_action: str | None = None
    requirement: Literal["required", "optional"] | None = None


class DiagnosticCheck(BaseModel):
    """One concrete config repair check.

    A failing or warning row MUST carry exactly one of ``next_action`` (an
    exact ``aeat ...`` command string the operator can run) or ``dead_end``
    (a short explanation of why no automated route exists). A row that
    supplies neither, or both, is a :class:`pydantic.ValidationError` at
    construction time. ``ok`` rows MUST carry neither.

    ``findings`` carries the per-cause breakdown: the specific keys that
    are unset, the specific reasons a check failed. ``audience`` records
    whether the operator can act on the row or whether it reports an
    internal application defect.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: str
    status: DiagnosticStatus
    summary: str
    detail: str | None = None
    next_action: str | None = None
    dead_end: str | None = None
    audience: DiagnosticAudience = "operator"
    findings: tuple[DiagnosticFinding, ...] = ()

    @model_validator(mode="after")
    def _enforce_actionable_contract(self) -> DiagnosticCheck:
        next_action = self.next_action if self.next_action else None
        dead_end = self.dead_end if self.dead_end else None
        if next_action is not None and dead_end is not None:
            raise DiagnosticModelError("DiagnosticCheck may set at most one of `next_action` or `dead_end`, not both")
        if self.status in {"fail", "warn"}:
            if next_action is None and dead_end is None:
                raise DiagnosticModelError(
                    f"DiagnosticCheck(status={self.status!r}) must populate one of "
                    "`next_action` or `dead_end`; silent failing rows are forbidden",
                )
        else:  # status == "ok"
            if next_action is not None or dead_end is not None:
                raise DiagnosticModelError("DiagnosticCheck(status='ok') must not carry `next_action` or `dead_end`")
        return self


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


class ConfigRepairReport(BaseModel):
    """Local environment and configuration diagnostics for ``aeat config repair``."""

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


_models_rebuilt = False


def _ensure_models_rebuilt() -> None:
    """Resolve the deferred forward references on the heavy report models.

    ``SecureObjectIntegrityReport`` and ``ConfigRepairReport`` carry
    fields typed by ``SecureObjectNamespaceIntegrity`` and
    ``WizardStatusReport``. Those names are imported lazily so the
    ``aeat --version`` fast path never pulls the heavy secure-object and
    wizard-status import subtrees. The two models are only ever
    *constructed* by the diagnostics functions below — never by the
    version path — so their forward references are resolved here, on
    first use of a heavy function, when the real types are imported
    anyway. Idempotent: the rebuild runs once per process.
    """
    global _models_rebuilt
    if _models_rebuilt:
        return
    from ..adapters.persistence.storage.sql.secure_objects import (
        SecureObjectNamespaceIntegrity,  # noqa: F401  # model_rebuild local namespace
    )
    from .wizard._status import WizardStatusReport  # noqa: F401  # model_rebuild local namespace

    SecureObjectIntegrityReport.model_rebuild(_types_namespace=locals())
    ConfigRepairReport.model_rebuild(_types_namespace={**globals(), **locals()})
    _models_rebuilt = True


class RegistryIntegrityReport(BaseModel):
    """Result of the opt-in full registry-validation probe.

    Disaster ADR Ruling 4 moves the full registry TOML parse +
    cross-domain referential-integrity gate off the ``--version`` and
    bare-invocation surfaces into the explicit
    ``aeat config repair integrity registry`` verb. This typed
    report is what that verb renders.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    registry: RegistryVersionSummary
    check: DiagnosticCheck


def build_cli_version_report(
    registry_root: Path | None = None,
    *,
    with_registry: bool = True,
) -> CliVersionReport:
    """Return the package and registry summary for CLI version surfaces.

    The ``with_registry`` flag controls whether the full registry
    TOML load fires. The CLI root callback passes
    ``with_registry=False`` for bare ``aeat --version`` invocations
    (the fast-path mandated by disaster ADR Ruling 4 — the operator
    must see name + version in under a second on cold start). When
    ``--detail`` is on, the caller re-invokes with
    ``with_registry=True`` to populate the registry summary.

    Returns a :class:`CliVersionReport`.
    """
    if with_registry:
        root = registry_root or bundled_path("registry", "aeat")
        summary = _build_registry_version_summary(root)
    else:
        summary = RegistryVersionSummary(available=False, registry_root="")
    return CliVersionReport(
        package_name="aeat",
        package_version=__version__,
        registry=summary,
    )


def build_config_repair_report(registry_root: Path | None = None) -> ConfigRepairReport:
    """Return local diagnostics for the ``aeat config repair`` surface.

    Returns a :class:`ConfigRepairReport` enumerating every diagnostic
    check and any suggested repairs.
    """
    _ensure_models_rebuilt()
    root = registry_root or bundled_path("registry", "aeat")
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
            next_action=None if default_log_file_path().parent.exists() else "aeat config repair logs",
        ),
        DiagnosticCheck(
            name="registry.load",
            status="ok" if registry.available else "fail",
            summary=(
                tr(
                    "cli.diagnostics.summary.registry_counts",
                    modelos=registry.modelo_count,
                    casillas=registry.casilla_count,
                )
                if registry.available
                else tr("cli.diagnostics.summary.registry_unavailable")
            ),
            detail=registry.error,
            dead_end=(None if registry.available else tr("cli.diagnostics.dead_end.registry_bundled")),
            audience="operator" if registry.available else "internal",
        ),
    ]

    setup_report: WizardStatusReport | None = None
    provider_context: object | None = None
    try:
        try:
            from ..adapters.persistence.storage import get_master_key_provider, has_active_bucket_session
            from ..core import resolve_active_bucket_id
            from .wizard._status import build_wizard_status
            from .workflow import workflow_state_repository
            from .workflow._profile_health import assess_active_profile_health

            if not has_active_bucket_session() and resolve_active_bucket_id() is not None:
                provider_context = get_master_key_provider()
                # TYPE-IGNORE-RATIONALE-RUNTIME-CM-PROTOCOL:
                # get_master_key_provider returns a runtime context object;
                # __enter__/__exit__ are not statically visible here.
                provider_context.__enter__()  # type: ignore[attr-defined]
            state = workflow_state_repository().load()
            checks.append(
                DiagnosticCheck(
                    name="secure_state.load",
                    status="ok",
                    summary=tr("cli.diagnostics.summary.state_backend_readable"),
                ),
            )
            profile_health = assess_active_profile_health(state)
            checks.append(_active_profile_storage_check(profile_health))
            setup_report = _repair_safe_wizard_status(build_wizard_status(state))
            checks.append(_profile_check(setup_report, profile_health=profile_health, state=state))
            checks.append(_auth_check(setup_report))
        except Exception as exc:  # pragma: no cover - concrete failure mode depends on local secure backend.
            from .workflow._profile_health import assess_active_profile_health

            _log.debug("config repair secure state probe failed", exc_info=True)
            profile_health = assess_active_profile_health()
            missing_active_bucket_session = _is_missing_active_bucket_session(exc)
            checks.append(
                DiagnosticCheck(
                    name="secure_state.load",
                    status="warn" if missing_active_bucket_session else "fail",
                    summary=tr("cli.diagnostics.summary.state_backend_unreadable"),
                    # A missing bucket session on a cold start is an
                    # expected diagnostic verdict, not a fault to report
                    # verbatim. Surfacing the raw NoActiveBucketSession
                    # exception text leaks internal plumbing; the
                    # summary + next_action already guide the operator.
                    detail=None if missing_active_bucket_session else _compact_exception(exc),
                    next_action=(
                        profile_health.next_action or "aeat config switch NAME"
                        if missing_active_bucket_session
                        else "aeat config repair reset-progress --yes"
                    ),
                ),
            )
            checks.append(_active_profile_storage_check(profile_health))
            checks.append(_profile_unavailable_check(profile_health))
            checks.append(_auth_unavailable_check(profile_health))

        secure_objects = _probe_secure_objects_integrity()
        checks.append(_secure_objects_integrity_check(secure_objects))
    finally:
        if provider_context is not None:
            # TYPE-IGNORE-RATIONALE-RUNTIME-CM-PROTOCOL:
            # get_master_key_provider returns a runtime context object;
            # __enter__/__exit__ are not statically visible here.
            provider_context.__exit__(None, None, None)  # type: ignore[attr-defined]

    checks.append(_registry_cross_domain_integrity_check(root))

    stale_sync = _windows_stale_sync_check()
    if stale_sync is not None:
        checks.append(stale_sync)

    return ConfigRepairReport(
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


def probe_browser_connectivity(settings: Settings | None = None) -> SiteHealthStatus:
    """Probe the configured AEAT browser target through the browser adapter.

    Returns a :class:`SiteHealthStatus`.
    """
    # `load_settings()` honours `override_settings`; bare `Settings()`
    # bypasses the context-var.
    from ..core.config import load_settings as _load_settings

    resolved = settings or _load_settings()
    return asyncio.run(_probe_browser_connectivity(resolved))


def render_browser_connectivity_text(status: SiteHealthStatus) -> str:
    """Render one site-health status as compact repair output."""
    markers = ", ".join(status.evidence.detected_markers) or tr("cli.diagnostics.browser.markers_none")
    lines = [
        f"{tr('cli.diagnostics.browser.target_label')}\t{tr('cli.diagnostics.browser.target_browser')}",
        f"{tr('cli.diagnostics.browser.state_label')}\t{status.state.value}",
        f"{tr('cli.diagnostics.browser.http_status_label')}\t{status.evidence.http_status}",
        f"{tr('cli.diagnostics.browser.markers_label')}\t{markers}",
        f"{tr('cli.diagnostics.browser.observed_at_label')}\t{status.observed_at.isoformat()}",
    ]
    if status.retry_after_seconds is not None:
        lines.append(f"{tr('cli.diagnostics.browser.retry_after_label')}\t{status.retry_after_seconds}")
    return "\n".join(lines) + "\n"


async def _probe_browser_connectivity(settings: Settings) -> SiteHealthStatus:
    from ..adapters.outbound.aeat.browser import default_browser_session_factory

    url = settings.site_health_probe_url
    session = await default_browser_session_factory(settings)
    context = None
    try:
        context = await session.create_context()
        page = await context.new_page()
        try:
            await session.navigate(page, url)
        except SiteHealthError as exc:
            from ..adapters.outbound.aeat.browser import SiteHealthStatus

            status = exc.status
            if not isinstance(status, SiteHealthStatus):
                raise DiagnosticModelError("SiteHealthError carried a non-SiteHealthStatus payload") from exc
            return status
        return _ok_site_health_status(url)
    finally:
        if context is not None:
            try:
                await context.close()
            # BROAD-EXCEPT-RATIONALE-DIAGNOSTICS-TEARDOWN:
            # close raises heterogeneous async exceptions; teardown must continue.
            except Exception:
                _log.warning("config repair connectivity context close failed", exc_info=True)
        try:
            await session.close()
        # BROAD-EXCEPT-RATIONALE-DIAGNOSTICS-TEARDOWN:
        # close raises heterogeneous async exceptions; teardown must continue.
        except Exception:
            _log.warning("config repair connectivity browser close failed", exc_info=True)


def _ok_site_health_status(url: str) -> SiteHealthStatus:
    from ..adapters.outbound.aeat.browser import SiteHealthEvidence, SiteHealthState, SiteHealthStatus
    from ..adapters.outbound.aeat.browser._site_health import _URL_ADAPTER

    return SiteHealthStatus(
        state=SiteHealthState.OK,
        evidence=SiteHealthEvidence(
            url=_URL_ADAPTER.validate_python(url),
            http_status=200,
            html_fragment="",
            detected_markers=("healthy",),
        ),
        observed_at=now(),
    )


def render_config_repair_text(report: ConfigRepairReport) -> str:
    """Render a compact human-readable repair report."""
    lines = [
        f"{tr('cli.diagnostics.repair.overall_label', default='Overall')}\t{report.overall}",
        (
            f"{tr('cli.diagnostics.repair.version_label', default='Version')}\t"
            f"{report.package_name} {report.package_version}"
        ),
        f"{tr('cli.diagnostics.repair.python_label', default='Python')}\t{report.python_version}",
        f"{tr('cli.diagnostics.repair.logs_label', default='Logs')}\t{report.log_file}",
    ]
    if report.setup is not None:
        lines.append(
            f"{tr('cli.diagnostics.repair.profile_label', default='Profile')}\t{report.setup.active_profile or '-'} "
            f"({report.setup.profile_present_keys}/{report.setup.profile_total_keys})",
        )
        lines.append(f"{tr('cli.diagnostics.repair.auth_label', default='Auth')}\t{report.setup.auth_provider or '-'}")
    lines.append(tr("cli.diagnostics.repair.checks_heading", default="Checks"))
    for check in report.checks:
        scope = (
            ""
            if check.status == "ok" or check.audience == "operator"
            else f" [{tr('cli.diagnostics.repair.audience_internal', default='internal application issue')}]"
        )
        lines.append(f"{check.status}\t{check.name}\t{check.summary}{scope}")
        if check.detail:
            lines.append(f"{tr('cli.diagnostics.repair.detail_label', default='Detail')}\t{check.detail}")
        for finding in check.findings:
            tag = _finding_tag(finding)
            lines.append(f"{tr('cli.diagnostics.repair.finding_label', default='-')}\t{tag}{finding.summary}")
            if finding.detail:
                lines.append(f"  {tr('cli.diagnostics.repair.detail_label', default='Detail')}\t{finding.detail}")
            if finding.next_action:
                lines.append(f"  {tr('cli.diagnostics.repair.next_label', default='Next')}\t{finding.next_action}")
        if check.next_action:
            lines.append(f"{tr('cli.diagnostics.repair.next_label', default='Next')}\t{check.next_action}")
        if check.dead_end:
            lines.append(f"{tr('cli.diagnostics.repair.note_label', default='Note')}\t{check.dead_end}")
    return "\n".join(lines) + "\n"


def _repair_safe_wizard_status(report: WizardStatusReport) -> WizardStatusReport:
    """Return a repair-surface copy that does not expose the bucket UUID."""
    if report.active_profile is None:
        return report
    return report.model_copy(update={"active_profile": CLI_PROFILE_ID_PLACEHOLDER})


def _finding_tag(finding: DiagnosticFinding) -> str:
    """Return the requirement prefix rendered ahead of a finding summary."""
    if finding.requirement == "required":
        return f"{tr('cli.diagnostics.repair.finding_required', default='required')}: "
    if finding.requirement == "optional":
        return f"{tr('cli.diagnostics.repair.finding_optional', default='optional')}: "
    return ""


def _build_registry_version_summary(registry_root: Path) -> RegistryVersionSummary:
    from ..domain.calculations.registry import ValidatedRegistryAuthority

    try:
        authority = ValidatedRegistryAuthority.load(registry_root, source_root=bundled_path())
    except Exception as exc:  # pragma: no cover - covered by later repair diagnostics.
        _log.debug("registry version summary load failed for %s", registry_root, exc_info=True)
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
    _ensure_models_rebuilt()
    from ..adapters.persistence.storage.runtime_repository import (
        secure_object_repository_for_active_bucket_or_default_route,
    )
    from ..adapters.persistence.storage.sql.secure_objects import (
        SecureObjectNamespaceIntegrity,
    )

    try:
        repo = secure_object_repository_for_active_bucket_or_default_route()
        namespaces = repo.list_namespaces()
    except Exception as exc:  # pragma: no cover - engine resolution depends on local backend.
        _log.debug(
            "secure objects engine unreachable for repair probe: %s: %s",
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        return SecureObjectIntegrityReport()
    integrity_items: list[SecureObjectNamespaceIntegrity] = []
    for ns in namespaces:
        try:
            integrity_items.append(repo.probe_namespace_integrity(ns))
        # BROAD-EXCEPT-RATIONALE-DIAGNOSTICS-INTEGRITY-PROBE:
        # storage probes raise heterogeneous backend errors; continue per namespace.
        except Exception:
            _log.debug("secure objects integrity probe failed for namespace=%s", ns, exc_info=True)
            integrity_items.append(
                SecureObjectNamespaceIntegrity(
                    namespace=ns,
                    readable=0,
                    unreadable=1,
                ),
            )
    integrity = tuple(integrity_items)
    readable_total = sum(item.readable for item in integrity)
    unreadable_total = sum(item.unreadable for item in integrity)
    return SecureObjectIntegrityReport(
        namespaces=integrity,
        readable_total=readable_total,
        unreadable_total=unreadable_total,
    )


def _secure_objects_integrity_check(report: SecureObjectIntegrityReport) -> DiagnosticCheck:
    """Render the ``secure_objects.integrity`` repair row."""
    if report.unreadable_total == 0:
        if report.readable_total == 0:
            return DiagnosticCheck(
                name="secure_objects.integrity",
                status="ok",
                summary=tr("cli.diagnostics.summary.secure_objects_empty"),
            )
        return DiagnosticCheck(
            name="secure_objects.integrity",
            status="ok",
            summary=tr(
                "cli.diagnostics.summary.secure_objects_readable",
                readable=report.readable_total,
                namespaces=len(report.namespaces),
            ),
        )
    affected = ", ".join(
        f"{item.namespace} ({item.unreadable}/{item.readable + item.unreadable})"
        for item in report.namespaces
        if item.unreadable > 0
    )
    return DiagnosticCheck(
        name="secure_objects.integrity",
        status="warn",
        summary=tr(
            "cli.diagnostics.summary.secure_objects_unreadable",
            default="%{unreadable} unreadable row(s), %{readable} readable row(s)",
            unreadable=report.unreadable_total,
            readable=report.readable_total,
        ),
        detail=affected,
        next_action="aeat config repair quarantine --yes",
    )


def _registry_cross_domain_integrity_check(registry_root: Path) -> DiagnosticCheck:
    """Cross-domain integrity check by exercising the snapshot-build gate.

    Loads the registry authority (which runs ``validate_registry``
    at construction time) and attempts to build a representative
    snapshot for modelo 100. The snapshot-build path wires
    :func:`_check_all_id_references` (typed-ID existence checks +
    renta first-slice routing target check + per-binding selector-
    shape gate); any divergence between code-side typed contracts
    and registry data surfaces here as a typed failure.

    A failure routes the operator to a structured diagnostic rather
    than a runtime KeyError mid-calculation.
    """
    from ..domain.calculations.registry import RegistryValidationError, ValidatedRegistryAuthority

    try:
        authority = ValidatedRegistryAuthority.load(registry_root, source_root=bundled_path())
        authority.snapshot(
            Modelo.M100.value,
            filing_year=_REGISTRY_INTEGRITY_PROBE_YEAR,
            period="0A",
            on=_REGISTRY_INTEGRITY_PROBE_DATE,
        )
    except RegistryValidationError as exc:
        return DiagnosticCheck(
            name="registry.integrity",
            status="fail",
            summary=tr("cli.diagnostics.summary.registry_integrity_failed"),
            detail=str(exc),
            next_action=tr("cli.diagnostics.next_action.inspect_registry_toml"),
            audience="internal",
        )
    except Exception as exc:  # pragma: no cover - defensive: registry not loadable
        return DiagnosticCheck(
            name="registry.integrity",
            status="warn",
            summary=tr("cli.diagnostics.summary.registry_integrity_skipped"),
            detail=f"{type(exc).__name__}: {exc}",
            dead_end=tr("cli.diagnostics.dead_end.registry_integrity_internal"),
            audience="internal",
        )
    return DiagnosticCheck(
        name="registry.integrity",
        status="ok",
        summary=tr("cli.diagnostics.summary.registry_integrity_ok"),
    )


def build_registry_integrity_report(registry_root: Path | None = None) -> RegistryIntegrityReport:
    """Run the full registry validation as a standalone, opt-in probe and return a :class:`RegistryIntegrityReport`.

    Backs the ``aeat config repair integrity registry`` verb. Bundles
    the registry version summary with the cross-domain
    referential-integrity check so the engineer-facing verb can render
    both the registry's identity and its validation verdict. Disaster
    ADR Ruling 4 keeps this off every fast-path surface.
    """
    root = registry_root or bundled_path("registry", "aeat")
    return RegistryIntegrityReport(
        registry=_build_registry_version_summary(root),
        check=_registry_cross_domain_integrity_check(root),
    )


def _active_profile_storage_check(health: ActiveProfileHealth) -> DiagnosticCheck:
    """Render pointer/manifest/profile-record health before semantic readiness."""
    active_profile = CLI_PROFILE_ID_PLACEHOLDER if health.active_profile is not None else "-"
    summary = tr(
        "cli.diagnostics.summary.profile_storage",
        active_profile=active_profile,
        source=health.source,
        status=health.status,
    )
    if health.status in {"none", "incomplete", "ready"}:
        return DiagnosticCheck(
            name="profile.storage",
            status="ok",
            summary=summary,
        )
    detail = health.profile_record_error or None
    return DiagnosticCheck(
        name="profile.storage",
        status="warn",
        summary=summary,
        detail=detail,
        next_action=health.next_action,
    )


def _profile_unavailable_check(health: ActiveProfileHealth) -> DiagnosticCheck:
    if health.status in {"dangling_pointer", "missing_profile_record", "profile_record_unreadable"}:
        return DiagnosticCheck(
            name="profile.readiness",
            status="warn",
            summary=tr("cli.diagnostics.summary.profile_unreadable", status=health.status),
            detail=health.profile_record_error or None,
            next_action=health.next_action,
        )
    return DiagnosticCheck(
        name="profile.readiness",
        status="warn",
        summary=tr("cli.diagnostics.summary.profile_none", default="No profile configured"),
        next_action="aeat config profile create NAME --tax-id <TAX_ID> --activity <ACTIVITY>",
    )


_PROFILE_EDIT_COMMAND = "aeat config profile edit NAME"
"""The operator command that walks the profile wizard over an existing
profile. There is deliberately no per-key setter on the ``aeat config``
surface, so every unset-key finding routes to this single guided
editor; the finding's ``summary`` names the specific key to fill."""


def _unset_profile_key_findings(state: WorkflowState | None) -> tuple[DiagnosticFinding, ...]:
    """Return one finding per profile key the active profile leaves unset.

    Each finding names the canonical key path, its operator-facing label,
    whether the key is required or optional, and the guided-editor
    command that fills it. This is what turns a bare ``31/40`` counter
    into an actionable list: the operator sees precisely which fields
    are unset and the one command that walks them through filling each.
    """
    from .user_profile._keys_validation import list_profile_key_records

    if state is None:
        return ()
    try:
        record = state.active_profile_record()
    except Exception:  # pragma: no cover
        # BROAD-EXCEPT-RATIONALE-DIAGNOSTICS-RECORD-READ:
        # record unreadability is handled by upstream storage checks.
        _log.debug("config repair profile-key finding probe could not read record", exc_info=True)
        return ()
    if record is None:
        return ()

    from .user_profile._projections import record_to_path_values

    values = record_to_path_values(record)
    findings: list[DiagnosticFinding] = []
    for entry in list_profile_key_records():
        raw = values.get(entry.key)
        if raw is not None and raw.strip() != "":
            continue
        requirement: Literal["required", "optional"] = (
            "required" if entry.requirement.value == "required" else "optional"
        )
        label = tr(str(entry.description))
        findings.append(
            DiagnosticFinding(
                summary=f"{entry.key} — {label}",
                requirement=requirement,
                next_action=_PROFILE_EDIT_COMMAND,
            ),
        )
    return tuple(findings)


def _profile_check(
    report: WizardStatusReport,
    *,
    profile_health: ActiveProfileHealth | None = None,
    state: WorkflowState | None = None,
) -> DiagnosticCheck:
    if profile_health is not None and profile_health.status in {
        "dangling_pointer",
        "missing_profile_record",
        "profile_record_unreadable",
    }:
        return DiagnosticCheck(
            name="profile.readiness",
            status="warn",
            summary=tr("cli.diagnostics.summary.profile_unreadable", status=profile_health.status),
            detail=profile_health.profile_record_error or None,
            next_action=profile_health.next_action,
        )
    if report.active_profile is None:
        return DiagnosticCheck(
            name="profile.readiness",
            status="warn",
            summary=tr("cli.diagnostics.summary.profile_none"),
            next_action="aeat config profile create NAME --tax-id <TAX_ID> --activity <ACTIVITY>",
        )
    unset_findings = _unset_profile_key_findings(state)
    if not report.profile_ready:
        missing_required = tuple(f for f in unset_findings if f.requirement == "required")
        # Fall back to the wizard report's missing-required tuple when the
        # record probe is unavailable, so the row still names what is wrong.
        if not missing_required:
            missing_required = tuple(
                DiagnosticFinding(summary=key, requirement="required") for key in report.missing_required
            )
        enrolment_findings = tuple(
            DiagnosticFinding(summary=key, requirement="required")
            for key in report.missing_enrolment
            if key not in {f.summary.split(" — ", 1)[0] for f in missing_required}
        )
        return DiagnosticCheck(
            name="profile.readiness",
            status="warn",
            summary=tr(
                "cli.diagnostics.summary.profile_missing_keys",
                default="Profile is missing %{count} required key(s)",
                count=len(missing_required) + len(enrolment_findings),
            ),
            next_action=_PROFILE_EDIT_COMMAND,
            findings=missing_required + enrolment_findings,
        )
    return DiagnosticCheck(
        name="profile.readiness",
        status="ok",
        summary=tr(
            "cli.diagnostics.summary.profile_keys_set",
            default="Profile keys set: %{present}/%{total}",
            present=report.profile_present_keys,
            total=report.profile_total_keys,
        ),
        findings=unset_findings,
    )


def _auth_unavailable_check(health: ActiveProfileHealth) -> DiagnosticCheck:
    return DiagnosticCheck(
        name="auth.readiness",
        status="warn",
        summary=tr("cli.diagnostics.summary.auth_state_unreadable"),
        next_action=health.next_action or "aeat config switch NAME",
    )


def _auth_check(report: WizardStatusReport) -> DiagnosticCheck:
    if not report.auth_provider:
        return DiagnosticCheck(
            name="auth.readiness",
            status="warn",
            summary=tr("cli.diagnostics.summary.auth_none"),
            next_action="aeat config auth configure --provider certificate --file PATH",
        )
    if not report.login_ready:
        return DiagnosticCheck(
            name="auth.readiness",
            status="warn",
            summary=tr(
                "cli.diagnostics.summary.auth_no_session",
                default="Authentication provider %{provider} has no ready session",
                provider=report.auth_provider,
            ),
            next_action=f"aeat config auth test --provider {report.auth_provider}",
        )
    return DiagnosticCheck(
        name="auth.readiness",
        status="ok",
        summary=tr(
            "cli.diagnostics.summary.auth_session_ready",
            default="Authentication provider %{provider} has a ready session",
            provider=report.auth_provider,
        ),
    )


def _is_missing_active_bucket_session(exc: BaseException) -> bool:
    from ..adapters.persistence.storage.master_key import NoActiveBucketSessionError

    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, NoActiveBucketSessionError):
            return True
        current = current.__cause__ or current.__context__
    return "NoActiveBucketSessionError" in f"{type(exc).__name__}: {exc}"


def _compact_exception(exc: BaseException) -> str:
    root = getattr(exc, "orig", None)
    if isinstance(root, BaseException):
        exc = root
    message = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
    return f"{type(exc).__name__}: {message}"


def _windows_stale_sync_check() -> DiagnosticCheck | None:
    """Report when the Windows venv is older than ``pyproject.toml``.

    Plain ``uv run aeat`` re-syncs the venv on each invocation, which
    races the OS handle on ``Scripts/aeat.exe`` and intermittently raises
    ``os error 32``. The canonical workaround is to invoke the CLI via
    ``uv run --no-sync aeat`` (or the ``tools/aeat.cmd`` launcher).
    That workaround skips sync, so a stale venv must be detected
    explicitly. This row fires when the host is Windows and
    ``pyproject.toml`` is newer than the venv marker.
    """
    if sys.platform != "win32":
        return None
    pyproject = PROJECT_ROOT / "pyproject.toml"
    venv_marker = PROJECT_ROOT / ".venv" / "pyvenv.cfg"
    if not pyproject.is_file() or not venv_marker.is_file():
        return None
    if pyproject.stat().st_mtime <= venv_marker.stat().st_mtime:
        return DiagnosticCheck(
            name="runtime.dependency_sync",
            status="ok",
            summary=tr("cli.diagnostics.summary.venv_in_sync"),
        )
    return DiagnosticCheck(
        name="runtime.dependency_sync",
        status="warn",
        summary=tr("cli.diagnostics.summary.venv_stale"),
        next_action="uv sync",
    )


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
        return tr(
            "cli.diagnostics.version.registry_unavailable",
            package=report.package_name,
            version=report.package_version,
            error=registry.error or "",
        )
    revision_label = (
        ", ".join(registry.revision_ids) if registry.revision_ids else tr("cli.diagnostics.version.no_revisions")
    )
    return tr(
        "cli.diagnostics.version.registry_summary",
        default=(
            "{package} {version}\n"
            "Registry: {modelos} modelos, {casillas} casillas, "
            "{formulas} formulas\n"
            "Revisions: {revisions}"
        ),
        package=report.package_name,
        version=report.package_version,
        revisions=revision_label,
        modelos=registry.modelo_count,
        casillas=registry.casilla_count,
        formulas=registry.formula_count,
    )


def secure_object_unreadable_total() -> int:
    """Return the count of rows the current master key cannot decrypt.

    Lightweight wrapper over :func:`_probe_secure_objects_integrity` for
    consumers (notably ``aeat app overview status``) that want to surface
    a concise "N rows unreadable" pointer towards
    ``aeat config repair`` without rendering the per-namespace breakdown
    themselves. The full breakdown remains the authority of repair.
    """
    return _probe_secure_objects_integrity().unreadable_total


def preview_quarantine_unreadable_secure_objects() -> SecureObjectIntegrityReport:
    """Report the rows ``repair quarantine`` would move, mutating nothing.

    Backs the ``aeat config repair quarantine --dry-run`` preview. Runs
    the same per-namespace decryptability probe that
    :func:`quarantine_unreadable_secure_objects` uses to decide which
    rows to archive, but performs no copy and no delete: the
    ``secure_objects`` table is left exactly as found. The returned
    :class:`SecureObjectIntegrityReport` carries, per namespace, the
    ``unreadable`` count (= rows the non-dry-run verb would quarantine)
    and the ``readable`` count (= rows it would retain), so the
    operator can confirm the blast radius before committing — the same
    preview shape ``reset-progress --dry-run`` already offers.
    """
    from .repair_integrity import active_bucket_repair_session

    with active_bucket_repair_session():
        return _probe_secure_objects_integrity()


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
    _ensure_models_rebuilt()
    from ..adapters.persistence.storage.runtime_repository import (
        secure_object_repository_for_active_bucket_or_default_route,
    )
    from .repair_integrity import active_bucket_repair_session

    with active_bucket_repair_session():
        repo = secure_object_repository_for_active_bucket_or_default_route()
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
    "ConfigRepairReport",
    "DiagnosticCheck",
    "DiagnosticFinding",
    "RegistryIntegrityReport",
    "RegistryVersionSummary",
    "SecureObjectIntegrityReport",
    "build_cli_version_report",
    "build_config_repair_report",
    "build_registry_integrity_report",
    "preview_quarantine_unreadable_secure_objects",
    "probe_browser_connectivity",
    "quarantine_unreadable_secure_objects",
    "render_browser_connectivity_text",
    "render_cli_version_text",
    "render_config_repair_text",
    "secure_object_unreadable_total",
]
