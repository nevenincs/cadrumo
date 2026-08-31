"""Application-owned diagnostics, version reports, and repair probes.

:func:`build_cli_version_report` and :func:`render_cli_version_text` back the
root ``aeat --version`` surface. They keep the fast path import-light unless the
caller requests registry detail.

:func:`build_config_repair_report` composes environment checks,
:class:`~application.workflow.WorkflowState` loading,
:class:`~application.workflow.ActiveProfileHealth` profile storage
verdicts, :class:`~application.wizard.status.WizardStatusReport`
readiness, registry summaries, and secure-object decryptability into a
:class:`ConfigRepairReport` of :class:`DiagnosticCheck` rows. The full registry
integrity probe is intentionally opt-in through :class:`RegistryIntegrityReport`;
it loads the registry authority only for repair commands that ask for that
validation.

Every warn/fail :class:`DiagnosticCheck` carries an application-owned
``precondition_verdict`` whose outcome is either a canonical action reference
or an explicit no-recovery classification. The validator raises
:class:`~application.errors.DiagnosticModelError` if a row is silent or
ambiguous. Renderers and CLI payloads can therefore treat the repair report as
a typed contract, not a best-effort text scan.

Secure-object repair helpers return :class:`SecureObjectIntegrityReport`
instances shared with :mod:`application.repair_integrity`. Dry-run preview
and quarantine use the same decryptability probe so the committed mutation has
the same namespace counts the operator saw before confirming it. Registry
validation routes through
:class:`~domain.calculations.registry.ValidatedRegistryAuthority` and the
core :class:`~core.Modelo` identifier enum only on the explicit
repair-integrity path.

See Also:
    :mod:`application.repair_integrity` owns metadata-only repair
    decisions and active-bucket repair sessions.
    :mod:`application.workflow.profile_health` supplies the redacted
    active-profile health verdict when secure workflow state is readable or
    degraded.
    :mod:`application.wizard.status` supplies semantic profile/auth
    readiness once the workflow state has loaded.
    :mod:`entrypoints.cli._config._repair_cli` wires these reports into
    ``aeat config repair`` commands.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from pydantic import AnyHttpUrl, TypeAdapter

from .. import __version__
from ..core.async_cleanup import close_async_resources
from ..core.config import Settings
from ..core.errors.hierarchy import SiteHealthError, SiteHealthState
from ..core.i18n._render import tr
from ..core.logging import default_log_file_path, get_logger
from ..core.modelo import Modelo
from ..core.operator_action_enums import NoRecoveryOutcome
from ..core.redaction.rules import CLI_PROFILE_ID_PLACEHOLDER
from ..core.resources._boundary import bundled_path
from ..core.time.clock import now
from .diagnostic_models import (
    CliVersionReport as _CliVersionReport,
)
from .diagnostic_models import (
    ConfigRepairReport as _ConfigRepairReport,
)
from .diagnostic_models import (
    DiagnosticCheck as _DiagnosticCheck,
)
from .diagnostic_models import (
    DiagnosticFinding as _DiagnosticFinding,
)
from .diagnostic_models import (
    DiagnosticStatus as _DiagnosticStatus,
)
from .diagnostic_models import (
    RegistryIntegrityReport as _RegistryIntegrityReport,
)
from .diagnostic_models import (
    RegistryVersionSummary as _RegistryVersionSummary,
)
from .diagnostic_models import (
    SecureObjectIntegrityReport as _SecureObjectIntegrityReport,
)
from .diagnostic_models import (
    _diagnostic_action_verdict,
    _diagnostic_no_recovery_verdict,
    _missing_verdict_binding,
    _resolved_verdict_binding,
)
from .diagnostic_models import (
    ensure_models_rebuilt as _ensure_models_rebuilt,
)
from .errors import DiagnosticModelError
from .operator_actions.models import PreconditionVerdict

# The browser adapter, the registry authority, the secure-object
# repository, the workflow store, and the wizard-status projection are
# all heavy import subtrees (the browser adapter and the registry parse
# alone add ~3.5s of cold-start import time). The ``aeat --version``
# fast path imports this module only for ``build_cli_version_report`` /
# ``render_cli_version_text``, neither of which needs any of them.
# Importing them lazily inside the functions that actually run keeps the
# version surface off the heavy import graph.
if TYPE_CHECKING:
    from ..adapters.outbound.aeat.browser._site_health import SiteHealthStatus
    from .wizard.status import WizardStatusReport
    from .workflow.profile_health import ActiveProfileHealth
    from .workflow.state_models import WorkflowState

_log = get_logger(__name__)

_REGISTRY_INTEGRITY_PROBE_YEAR: Final[int] = 2025
_REGISTRY_INTEGRITY_PROBE_DATE: Final[date] = date(2025, 12, 31)
_SITE_HEALTH_URL_ADAPTER: Final[TypeAdapter[AnyHttpUrl]] = TypeAdapter(AnyHttpUrl)


def build_cli_version_report(
    registry_root: Path | None = None,
    *,
    with_registry: bool = True,
) -> _CliVersionReport:
    """Return the package and registry summary for CLI version surfaces.

    The ``with_registry`` flag controls whether the full registry
    TOML load fires. The CLI root callback passes
    ``with_registry=False`` for bare ``aeat --version`` invocations
    (the operator must see name + version in under a second on cold
    start). When
    ``--detail`` is on, the caller re-invokes with
    ``with_registry=True`` to populate the registry summary.

    Returns a :class:`CliVersionReport` whose registry field is either the
    fast-path empty :class:`RegistryVersionSummary` or the detailed summary from
    :class:`~domain.calculations.registry.ValidatedRegistryAuthority`.
    """
    if with_registry:
        root = registry_root or bundled_path("registry", "aeat")
        summary = _build_registry_version_summary(root)
    else:
        summary = _RegistryVersionSummary(available=False, registry_root="")
    return _CliVersionReport(
        package_name="cadrumo",
        package_version=__version__,
        registry=summary,
    )


def build_config_repair_report(registry_root: Path | None = None) -> _ConfigRepairReport:
    """Return local diagnostics for the ``aeat config repair`` surface.

    Returns a :class:`ConfigRepairReport` enumerating every diagnostic
    check and any suggested repairs. Expensive registry validation beyond the
    rollup check remains in :func:`build_registry_integrity_report`, so the bare
    repair command stays focused on actionable local health.

    The secure-state branch reads
    :class:`~application.workflow.WorkflowState`, derives
    :class:`~application.workflow.ActiveProfileHealth`, and builds a
    :class:`~application.wizard.status.WizardStatusReport`. If that load
    fails, the report still emits profile and auth rows from the redacted health
    verdict so repair remains usable on a cold or degraded storage root.
    Each emitted warning/failure row is validated by :class:`DiagnosticCheck` so
    the caller never receives a silent repair finding.
    """
    _ensure_models_rebuilt()
    root = registry_root or bundled_path("registry", "aeat")
    registry = _build_registry_version_summary(root)
    log_parent_exists = default_log_file_path().parent.exists()
    checks: list[_DiagnosticCheck] = [
        _DiagnosticCheck(
            name="environment.python",
            status="ok",
            summary=sys.version.split()[0],
        ),
        _DiagnosticCheck(
            name="package.version",
            status="ok",
            summary=__version__,
        ),
        _DiagnosticCheck(
            name="logging.file",
            status="ok" if log_parent_exists else "warn",
            summary=str(default_log_file_path()),
            precondition_verdict=(
                None
                if log_parent_exists
                else _diagnostic_no_recovery_verdict(
                    condition_id="diagnostics.logging.file_parent.available",
                    evidence_id="diagnostics.logging.file_parent.observation",
                    values={
                        "log_file": str(default_log_file_path()),
                        "parent_exists": False,
                    },
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                )
            ),
        ),
        _DiagnosticCheck(
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
            precondition_verdict=(
                None
                if registry.available
                else _diagnostic_no_recovery_verdict(
                    condition_id="diagnostics.registry.load.available",
                    evidence_id="diagnostics.registry.load.observation",
                    values={"available": False, "registry_root": registry.registry_root},
                    outcome=NoRecoveryOutcome.TERMINAL,
                )
            ),
            audience="operator" if registry.available else "internal",
        ),
    ]

    setup_report: WizardStatusReport | None = None
    try:
        from .wizard.status import build_wizard_status
        from .workflow.persistence import workflow_state_repository
        from .workflow.profile_health import assess_active_profile_health

        # Read the secure state through whatever session the operator already
        # holds. This probe deliberately opens none of its own: it used to enter
        # the shared-master provider whenever no per-profile session served the
        # active bucket, which unlocked a taxpayer's bucket with no password so
        # a health report could be printed. The locked case is a diagnostic
        # verdict, not an obstacle -- the handler below already renders it as a
        # warn with the profile-health verdict that tells the operator to log in.
        state = workflow_state_repository().load()
        checks.append(
            _DiagnosticCheck(
                name="secure_state.load",
                status="ok",
                summary=tr("cli.diagnostics.summary.state_backend_readable"),
            ),
        )
        profile_health = assess_active_profile_health(state)
        checks.append(_active_profile_storage_check(profile_health))
        setup_report = _repair_safe_wizard_status(
            build_wizard_status(state),
            active_profile_label=profile_health.active_profile_label,
        )
        checks.append(_profile_check(setup_report, profile_health=profile_health, state=state))
        checks.append(_auth_check(setup_report))
    except Exception as exc:  # pragma: no cover - concrete failure mode depends on local secure backend.
        from .workflow.profile_health import assess_active_profile_health

        _log.debug("config repair secure state probe failed", exc_info=True)
        profile_health = assess_active_profile_health()
        missing_active_bucket_session = _is_missing_active_bucket_session(exc)
        checks.append(
            _DiagnosticCheck(
                name="secure_state.load",
                status="warn" if missing_active_bucket_session else "fail",
                summary=tr("cli.diagnostics.summary.state_backend_unreadable"),
                # A missing bucket session on a cold start is an
                # expected diagnostic verdict, not a fault to report
                # verbatim. Surfacing the raw NoActiveBucketSession
                # exception text leaks internal plumbing; the
                # summary + typed profile verdict already guide the operator.
                detail=None if missing_active_bucket_session else _compact_exception(exc),
                precondition_verdict=(
                    _required_profile_health_verdict(profile_health)
                    if missing_active_bucket_session
                    else _diagnostic_action_verdict(
                        condition_id="diagnostics.secure_state.load.readable",
                        evidence_id="diagnostics.secure_state.load.observation",
                        values={"readable": False},
                        action_id="operator.diagnostics.workflow.reset_progress",
                        argument_bindings=(_resolved_verdict_binding("yes", True),),
                    )
                ),
            ),
        )
        checks.append(_active_profile_storage_check(profile_health))
        checks.append(_profile_unavailable_check(profile_health))
        checks.append(_auth_unavailable_check(profile_health))

    secure_objects = _probe_secure_objects_integrity()
    checks.append(_secure_objects_integrity_check(secure_objects))
    checks.append(_registry_cross_domain_integrity_check(root))

    return _ConfigRepairReport(
        overall=_overall_status(tuple(checks)),
        package_name="cadrumo",
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
    from ..adapters.outbound.aeat.browser._factory import default_browser_session_factory

    url = settings.site_health_probe_url
    session = await default_browser_session_factory(settings)
    context = None
    try:
        context = await session.create_context()
        page = await context.new_page()
        try:
            await session.navigate(page, url)
        except SiteHealthError as exc:
            from ..adapters.outbound.aeat.browser._site_health import SiteHealthStatus

            status = exc.status
            if not isinstance(status, SiteHealthStatus):
                raise DiagnosticModelError("SiteHealthError carried a non-SiteHealthStatus payload") from exc
            return status
        return _ok_site_health_status(url)
    finally:
        await close_async_resources(
            context,
            session,
            task_name="cadrumo-diagnostics-browser-connectivity-close",
        )


def _ok_site_health_status(url: str) -> SiteHealthStatus:
    from ..adapters.outbound.aeat.browser._site_health import SiteHealthEvidence, SiteHealthStatus

    return SiteHealthStatus(
        state=SiteHealthState.OK,
        evidence=SiteHealthEvidence(
            url=_SITE_HEALTH_URL_ADAPTER.validate_python(url),
            http_status=200,
            html_fragment="",
            detected_markers=("healthy",),
        ),
        observed_at=now(),
    )


def render_config_repair_text(report: _ConfigRepairReport) -> str:
    """Render a compact human-readable repair report.

    Preserves :attr:`DiagnosticCheck.audience` and never reconstructs command
    prose from an application-owned :attr:`DiagnosticCheck.precondition_verdict`.
    Typed actions are resolved by the entrypoint projection; this application
    renderer remains a diagnosis-only view.
    """
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
    return "\n".join(lines) + "\n"


def _repair_safe_wizard_status(
    report: WizardStatusReport,
    *,
    active_profile_label: str | None,
) -> WizardStatusReport:
    """Return a repair status with a label, never an internal bucket UUID."""
    if report.active_profile is None:
        return report
    return report.model_copy(
        update={"active_profile": active_profile_label or CLI_PROFILE_ID_PLACEHOLDER},
    )


def _finding_tag(finding: _DiagnosticFinding) -> str:
    """Return the requirement prefix rendered ahead of a finding summary."""
    if finding.requirement == "required":
        return f"{tr('cli.diagnostics.repair.finding_required', default='required')}: "
    if finding.requirement == "optional":
        return f"{tr('cli.diagnostics.repair.finding_optional', default='optional')}: "
    return ""


def _build_registry_version_summary(registry_root: Path) -> _RegistryVersionSummary:
    from ..domain.calculations.registry.authority import ValidatedRegistryAuthority

    try:
        authority = ValidatedRegistryAuthority.load(registry_root, source_root=bundled_path())
    except Exception as exc:  # pragma: no cover - covered by later repair diagnostics.
        _log.debug("registry version summary load failed for %s", registry_root, exc_info=True)
        return _RegistryVersionSummary(
            available=False,
            registry_root=str(registry_root),
            error=f"{type(exc).__name__}: {exc}",
        )

    modelos = tuple(authority.modelos)
    revisions = tuple(revision for modelo in modelos for revision in modelo.revisions.values())
    return _RegistryVersionSummary(
        available=True,
        registry_root=str(registry_root),
        modelo_count=len(modelos),
        revision_count=len(revisions),
        casilla_count=sum(len(revision.casillas) for revision in revisions),
        formula_count=sum(len(revision.formulas) for revision in revisions),
        revision_ids=tuple(sorted({str(revision.id) for revision in revisions})),
    )


def _probe_secure_objects_integrity() -> _SecureObjectIntegrityReport:
    """Iterate every populated secure-objects namespace and aggregate counts.

    Returns an empty report when the table is empty or the engine cannot
    be reached. Non-empty results expose per-namespace counts so the
    operator can locate which application surface holds rows from a
    rotated master-key generation.
    The per-namespace rows come from
    :meth:`~adapters.persistence.storage.SecureObjectRepository.probe_namespace_integrity`.
    """
    _ensure_models_rebuilt()
    from ..adapters.persistence.storage.runtime_repository import (
        secure_object_repository_for_active_bucket_or_default_route,
    )
    from ..adapters.persistence.storage.sql.secure_objects import SecureObjectNamespaceIntegrity

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
        return _SecureObjectIntegrityReport()
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
    return _SecureObjectIntegrityReport(
        namespaces=integrity,
        readable_total=readable_total,
        unreadable_total=unreadable_total,
    )


def _secure_objects_integrity_check(report: _SecureObjectIntegrityReport) -> _DiagnosticCheck:
    """Render the ``secure_objects.integrity`` repair row.

    A non-zero unreadable total becomes a warn :class:`DiagnosticCheck` whose
    typed verdict resolves to the guarded quarantine path.
    """
    if report.unreadable_total == 0:
        if report.readable_total == 0:
            return _DiagnosticCheck(
                name="secure_objects.integrity",
                status="ok",
                summary=tr("cli.diagnostics.summary.secure_objects_empty"),
            )
        return _DiagnosticCheck(
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
    return _DiagnosticCheck(
        name="secure_objects.integrity",
        status="warn",
        summary=tr(
            "cli.diagnostics.summary.secure_objects_unreadable",
            default="%{unreadable} unreadable row(s), %{readable} readable row(s)",
            unreadable=report.unreadable_total,
            readable=report.readable_total,
        ),
        detail=affected,
        precondition_verdict=_diagnostic_action_verdict(
            condition_id="diagnostics.secure_objects.integrity.readable",
            evidence_id="diagnostics.secure_objects.integrity.observation",
            values={
                "readable_total": report.readable_total,
                "unreadable_total": report.unreadable_total,
            },
            action_id="operator.diagnostics.secure_objects.quarantine",
            argument_bindings=(_resolved_verdict_binding("yes", True),),
        ),
    )


def _registry_cross_domain_integrity_check(registry_root: Path) -> _DiagnosticCheck:
    """Cross-domain integrity check by exercising the snapshot-build gate.

    Loads :class:`~domain.calculations.registry.ValidatedRegistryAuthority`
    (which runs ``validate_registry`` at construction time) and attempts to
    build a representative snapshot for :class:`~core.Modelo` member
    ``M100``. The snapshot-build path wires
    :func:`_check_all_id_references` (typed-ID existence checks +
    renta first-slice routing target check + per-binding selector-
    shape gate); any divergence between code-side typed contracts
    and registry data surfaces here as a typed failure.

    A failure routes the operator to a structured diagnostic rather
    than a runtime KeyError mid-calculation.
    """
    from ..domain.calculations.registry.authority import ValidatedRegistryAuthority
    from ..domain.calculations.registry.errors import RegistryValidationError

    try:
        authority = ValidatedRegistryAuthority.load(registry_root, source_root=bundled_path())
        authority.snapshot(
            Modelo.M100.value,
            filing_year=_REGISTRY_INTEGRITY_PROBE_YEAR,
            period="0A",
            on=_REGISTRY_INTEGRITY_PROBE_DATE,
        )
    except RegistryValidationError as exc:
        return _DiagnosticCheck(
            name="registry.integrity",
            status="fail",
            summary=tr("cli.diagnostics.summary.registry_integrity_failed"),
            detail=str(exc),
            precondition_verdict=_diagnostic_no_recovery_verdict(
                condition_id="diagnostics.registry.integrity.valid",
                evidence_id="diagnostics.registry.integrity.validation",
                values={"registry_root": str(registry_root), "valid": False},
                outcome=NoRecoveryOutcome.TERMINAL,
            ),
            audience="internal",
        )
    except Exception as exc:  # pragma: no cover - defensive: registry not loadable
        return _DiagnosticCheck(
            name="registry.integrity",
            status="warn",
            summary=tr("cli.diagnostics.summary.registry_integrity_skipped"),
            detail=f"{type(exc).__name__}: {exc}",
            precondition_verdict=_diagnostic_no_recovery_verdict(
                condition_id="diagnostics.registry.integrity.observable",
                evidence_id="diagnostics.registry.integrity.observation",
                values={"observable": False, "registry_root": str(registry_root)},
                outcome=NoRecoveryOutcome.TERMINAL,
            ),
            audience="internal",
        )
    return _DiagnosticCheck(
        name="registry.integrity",
        status="ok",
        summary=tr("cli.diagnostics.summary.registry_integrity_ok"),
    )


def build_registry_integrity_report(registry_root: Path | None = None) -> _RegistryIntegrityReport:
    """Run the full registry validation as a standalone :class:`RegistryIntegrityReport` probe.

    Backs the ``aeat config repair integrity registry`` verb. Bundles
    the registry version summary with the cross-domain
    referential-integrity check so the engineer-facing verb can render
    both the registry's identity and its validation verdict. This stays
    off every fast-path surface.
    """
    root = registry_root or bundled_path("registry", "aeat")
    return _RegistryIntegrityReport(
        registry=_build_registry_version_summary(root),
        check=_registry_cross_domain_integrity_check(root),
    )


def _active_profile_storage_check(health: ActiveProfileHealth) -> _DiagnosticCheck:
    """Render :class:`ActiveProfileHealth` storage status before semantic readiness."""
    active_profile = health.active_profile_label or (
        CLI_PROFILE_ID_PLACEHOLDER if health.active_profile is not None else "-"
    )
    summary = tr(
        "cli.diagnostics.summary.profile_storage",
        active_profile=active_profile,
        source=health.source,
        status=health.status,
    )
    if health.status in {"none", "incomplete", "ready"}:
        return _DiagnosticCheck(
            name="profile.storage",
            status="ok",
            summary=summary,
        )
    detail = health.profile_record_error or None
    return _DiagnosticCheck(
        name="profile.storage",
        status="warn",
        summary=summary,
        detail=detail,
        precondition_verdict=_required_profile_health_verdict(health),
    )


def _profile_unavailable_check(health: ActiveProfileHealth) -> _DiagnosticCheck:
    """Render a profile-readiness row when only :class:`ActiveProfileHealth` is available."""
    if health.status == "profile_locked":
        # A locked profile is neither absent nor broken: the capsule is
        # committed and the record is intact, merely not knowable until
        # someone logs in. Falling through to either sibling branch below
        # would tell the operator something untrue -- "unreadable" implies
        # damage, "no profile configured" implies nothing was ever set up.
        return _DiagnosticCheck(
            name="profile.readiness",
            status="warn",
            summary=tr("cli.diagnostics.summary.profile_locked"),
            precondition_verdict=_required_profile_health_verdict(health),
        )
    if health.status in {"dangling_pointer", "missing_profile_record", "profile_record_unreadable"}:
        return _DiagnosticCheck(
            name="profile.readiness",
            status="warn",
            summary=tr("cli.diagnostics.summary.profile_unreadable", status=health.status),
            detail=health.profile_record_error or None,
            precondition_verdict=_required_profile_health_verdict(health),
        )
    return _DiagnosticCheck(
        name="profile.readiness",
        status="warn",
        summary=tr("cli.diagnostics.summary.profile_none", default="No profile configured"),
        precondition_verdict=_required_profile_health_verdict(health),
    )


def _unset_profile_key_findings(state: WorkflowState | None) -> tuple[_DiagnosticFinding, ...]:
    """Return one finding per profile key the active profile leaves unset.

    Each finding names the canonical key path, its operator-facing label,
    whether the key is required or optional. The parent readiness row owns the
    single typed profile-editor action, avoiding per-finding transport prose.
    """
    from .user_profile.keys_validation import list_profile_key_records

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

    from .user_profile.projections import record_to_path_values

    values = record_to_path_values(record)
    findings: list[_DiagnosticFinding] = []
    for entry in list_profile_key_records():
        raw = values.get(entry.key)
        if raw is not None and raw.strip() != "":
            continue
        requirement: Literal["required", "optional"] = (
            "required" if entry.requirement.value == "required" else "optional"
        )
        label = tr(str(entry.description))
        findings.append(
            _DiagnosticFinding(
                summary=f"{entry.key} — {label}",
                requirement=requirement,
            ),
        )
    return tuple(findings)


def _profile_check(
    report: WizardStatusReport,
    *,
    profile_health: ActiveProfileHealth | None = None,
    state: WorkflowState | None = None,
) -> _DiagnosticCheck:
    """Render semantic profile readiness from wizard status plus workflow state.

    ``report`` supplies the
    :class:`~application.wizard.status.WizardStatusReport` counters and
    next action. ``profile_health`` can override the row when
    :class:`~application.workflow.ActiveProfileHealth` says the active
    profile bucket is unavailable. ``state`` lets the check expand missing
    profile keys from :class:`~application.workflow.WorkflowState` into
    per-key :class:`DiagnosticFinding` rows.
    """
    if profile_health is not None and profile_health.status == "profile_locked":
        # Same distinction as `_profile_unavailable_check`: a locked profile
        # is benign, so it gets its own sentence rather than falling through
        # to `report.active_profile is None` below, which reports the
        # "no profile configured" summary that is untrue of a locked one.
        return _DiagnosticCheck(
            name="profile.readiness",
            status="warn",
            summary=tr("cli.diagnostics.summary.profile_locked"),
            precondition_verdict=_required_profile_health_verdict(profile_health),
        )
    if profile_health is not None and profile_health.status in {
        "dangling_pointer",
        "missing_profile_record",
        "profile_record_unreadable",
    }:
        return _DiagnosticCheck(
            name="profile.readiness",
            status="warn",
            summary=tr("cli.diagnostics.summary.profile_unreadable", status=profile_health.status),
            detail=profile_health.profile_record_error or None,
            precondition_verdict=_required_profile_health_verdict(profile_health),
        )
    if report.active_profile is None:
        return _DiagnosticCheck(
            name="profile.readiness",
            status="warn",
            summary=tr("cli.diagnostics.summary.profile_none"),
            precondition_verdict=(
                _required_profile_health_verdict(profile_health)
                if profile_health is not None
                else _diagnostic_action_verdict(
                    condition_id="diagnostics.profile.active.available",
                    evidence_id="diagnostics.profile.active.observation",
                    values={"active_profile_present": False},
                    action_id="operator.profile.create",
                    argument_bindings=(_missing_verdict_binding("profile_name"),),
                    missing_argument_names=("profile_name",),
                )
            ),
        )
    unset_findings = _unset_profile_key_findings(state)
    if not report.profile_ready:
        return _profile_not_ready_check(report, unset_findings=unset_findings)
    return _DiagnosticCheck(
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


def _profile_not_ready_check(
    report: WizardStatusReport,
    *,
    unset_findings: tuple[_DiagnosticFinding, ...],
) -> _DiagnosticCheck:
    """Render the readiness row for a profile still missing required keys.

    Prefers the record probe's own findings; when it is unavailable the row
    falls back to the wizard report's missing-required tuple so it still
    names what is wrong rather than reporting an empty warning. Enrolment
    keys already named by a required finding are not repeated.
    """
    findings = _profile_not_ready_findings(report, unset_findings)
    return _DiagnosticCheck(
        name="profile.readiness",
        status="warn",
        summary=tr(
            "cli.diagnostics.summary.profile_missing_fields",
            default="Profile is missing %{count} required field(s): %{fields}",
            count=len(findings),
            fields=", ".join(finding.summary for finding in findings),
        ),
        precondition_verdict=_profile_not_ready_verdict(report, finding_count=len(findings)),
        findings=findings,
    )


def _profile_not_ready_findings(
    report: WizardStatusReport,
    unset_findings: tuple[_DiagnosticFinding, ...],
) -> tuple[_DiagnosticFinding, ...]:
    missing_required = tuple(f for f in unset_findings if f.requirement == "required")
    if not missing_required:
        missing_required = tuple(
            _DiagnosticFinding(summary=_grounded_profile_key_summary(key), requirement="required")
            for key in report.missing_required
        )
    already_named = {finding.summary.split(" — ", 1)[0] for finding in missing_required}
    enrolment_findings = tuple(
        _DiagnosticFinding(summary=_grounded_profile_key_summary(key), requirement="required")
        for key in report.missing_enrolment
        if key not in already_named
    )
    return missing_required + enrolment_findings


def _profile_not_ready_verdict(
    report: WizardStatusReport,
    *,
    finding_count: int,
) -> PreconditionVerdict:
    return _diagnostic_action_verdict(
        condition_id="diagnostics.profile.required_fields.complete",
        evidence_id="diagnostics.profile.required_fields.observation",
        values={
            "missing_required_count": finding_count,
            "profile_name": report.active_profile or CLI_PROFILE_ID_PLACEHOLDER,
        },
        action_id="operator.profile.edit",
        argument_bindings=(
            _resolved_verdict_binding(
                "profile_name",
                report.active_profile or CLI_PROFILE_ID_PLACEHOLDER,
            ),
        ),
    )


def _grounded_profile_key_summary(key: str) -> str:
    """Render a bare profile key path as "path - label", or unchanged.

    The fallback branch above reads keys straight off the wizard report, which
    carries canonical paths and no labels, while the primary branch already
    emits the labelled form. Without this the operator's diagnostics would
    name the same field two different ways depending on which branch produced
    it, and the fallback way would be a raw dotted path.

    The path is retained ahead of the label because the enrolment de-duplication
    above splits on the separator to compare paths, and because the path is what
    an operator types at the profile editor.

    A key the schema does not resolve is returned unchanged rather than
    guessed at.
    """
    from ..domain.user_profile.loader import load_user_profile_schema
    from .user_profile.preflight import build_profile_preflight_requirement

    schema = load_user_profile_schema()
    requirement = build_profile_preflight_requirement(key, schema=schema)
    if requirement.label == key:
        return key
    return f"{key} — {requirement.label}"


def _auth_unavailable_check(health: ActiveProfileHealth) -> _DiagnosticCheck:
    """Render auth readiness when workflow state cannot expose wizard status."""
    return _DiagnosticCheck(
        name="auth.readiness",
        status="warn",
        summary=tr("cli.diagnostics.summary.auth_state_unreadable"),
        precondition_verdict=_required_profile_health_verdict(health),
    )


def _required_profile_health_verdict(health: ActiveProfileHealth) -> PreconditionVerdict:
    """Return the health assessment's required typed refusal outcome.

    ``ActiveProfileHealth`` owns the applicability decision. A diagnostics
    consumer may preserve that verdict, but cannot infer a second recovery from
    the health status or from an error message.
    """
    verdict = health.precondition_verdict
    if verdict is None:
        raise DiagnosticModelError(
            f"non-ready active-profile health {health.status!r} has no precondition verdict",
        )
    return verdict


def _auth_check(report: WizardStatusReport) -> _DiagnosticCheck:
    """Render auth readiness from :class:`WizardStatusReport`."""
    if not report.auth_provider:
        return _DiagnosticCheck(
            name="auth.readiness",
            status="warn",
            summary=tr("cli.diagnostics.summary.auth_none"),
            precondition_verdict=_diagnostic_action_verdict(
                condition_id="diagnostics.auth.provider.configured",
                evidence_id="diagnostics.auth.provider.observation",
                values={"configured": False},
                action_id="operator.auth.configure",
                argument_bindings=(
                    _missing_verdict_binding("file"),
                    _resolved_verdict_binding("provider", "certificate"),
                ),
                missing_argument_names=("file",),
            ),
        )
    if not report.login_ready:
        return _DiagnosticCheck(
            name="auth.readiness",
            status="warn",
            summary=tr(
                "cli.diagnostics.summary.auth_no_session",
                default="Authentication provider %{provider} has no ready session",
                provider=report.auth_provider,
            ),
            precondition_verdict=_diagnostic_action_verdict(
                condition_id="diagnostics.auth.session.ready",
                evidence_id="diagnostics.auth.session.observation",
                values={"login_ready": False, "provider": report.auth_provider},
                action_id="operator.auth.login",
                argument_bindings=(_resolved_verdict_binding("provider", report.auth_provider),),
            ),
        )
    return _DiagnosticCheck(
        name="auth.readiness",
        status="ok",
        summary=tr(
            "cli.diagnostics.summary.auth_session_ready",
            default="Authentication provider %{provider} has a ready session",
            provider=report.auth_provider,
        ),
    )


def _is_missing_active_bucket_session(exc: BaseException) -> bool:
    """Classify a secure-state probe failure as a missing active bucket session.

    This verdict decides whether ``secure_state.load`` warns (an expected cold
    start) or fails (a real fault), and whether the raw exception text reaches
    the operator, so it reads the typed exception chain rather than rendered
    text.

    Scanning the rendered text for the class name could not survive this
    module's own contract: a producer that stops passing an authored sentence
    positionally leaves ``str(exc)`` degraded to a locale key which no longer
    contains the class name, so the scan would quietly stop matching and every
    cold start would report as a hard fault. It also matched in the wrong
    direction, classifying any unrelated failure whose message merely mentioned
    the class as an expected cold start, which downgrades a genuine fault to a
    warning and suppresses its detail.

    Both the ``__cause__`` and ``__context__`` edges are followed. An explicit
    ``raise ... from`` sets only the former and an incidental re-raise inside an
    ``except`` block sets only the latter, so a chain can fork across the two;
    the previous single-edge walk silently abandoned the ``__context__`` branch
    whenever a ``__cause__`` was present. Identity marking keeps a self- or
    mutually-referential chain from looping.
    """
    from ..adapters.persistence.storage.master_key.active_session import NoActiveBucketSessionError

    seen: set[int] = set()
    pending: list[BaseException] = [exc]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, NoActiveBucketSessionError):
            return True
        pending.extend(link for link in (current.__cause__, current.__context__) if link is not None)
    return False


def _compact_exception(exc: BaseException) -> str:
    root = getattr(exc, "orig", None)
    if isinstance(root, BaseException):
        exc = root
    message = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
    return f"{type(exc).__name__}: {message}"


def _overall_status(checks: tuple[_DiagnosticCheck, ...]) -> _DiagnosticStatus:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "ok"


def render_cli_version_text(report: _CliVersionReport) -> str:
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
    themselves. The full breakdown remains the authority of
    :class:`ConfigRepairReport`.
    """
    return _probe_secure_objects_integrity().unreadable_total


def preview_quarantine_unreadable_secure_objects() -> _SecureObjectIntegrityReport:
    """Report the rows ``repair quarantine`` would move, mutating nothing.

    Backs the ``aeat config repair quarantine --dry-run`` preview. Runs
    the same per-namespace decryptability probe that
    :func:`quarantine_unreadable_secure_objects` uses to decide which
    rows to archive, but performs no copy and no delete: the
    ``secure_objects`` table is left exactly as found. The returned
    :class:`SecureObjectIntegrityReport` carries, per namespace, the
    ``unreadable`` count (= rows the non-dry-run verb would quarantine)
    and the ``readable`` count (= rows it would retain), so the
    operator can confirm the blast radius before committing - the same
    preview shape ``reset-progress --dry-run`` already offers.
    """
    from .repair_integrity import active_bucket_repair_session

    with active_bucket_repair_session():
        return _probe_secure_objects_integrity()


def quarantine_unreadable_secure_objects() -> _SecureObjectIntegrityReport:
    """Move every undecryptable secure-object row into the quarantine table.

    Delegates to
    :meth:`~adapters.persistence.storage.SecureObjectRepository.quarantine_unreadable_rows`,
    which creates the ``secure_objects_quarantine`` archive table on first use,
    copies each undecryptable row's metadata and (still encrypted) payload into
    the archive, then deletes the row from the active ``secure_objects`` table.
    Decryptable rows are not touched.

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
    return _SecureObjectIntegrityReport(
        namespaces=namespaces,
        readable_total=retained_total,
        unreadable_total=quarantined_total,
    )


__all__ = [
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
