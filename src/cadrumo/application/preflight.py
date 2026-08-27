"""Workstation preflight health probes for ``aeat config check``.

This module is the read-only doctor surface for the health dimensions that sit
*beside* the external-dependency probes in :mod:`application.provisioning`:
per-auth-provider certificate / Cl@ve Móvil configuration health, secure-storage
and bundled-corpus reachability, key configuration sanity, registry referential
integrity, and portal-registry assembly health with any recorded portal drift.
Each probe answers one health question and returns a
typed :class:`PreflightCheck` — it never raises; a broken dimension is report
data (an ``error`` severity row with typed facts and a precondition verdict), not an exception
path, so the doctor reports status rather than crashing on a red row.

The certificate / Cl@ve Móvil rows reuse
:func:`~application.auth.probe_provider_configuration` (the pure-local
per-provider probe that opens the ``.p12`` and classifies expiry via
:func:`~adapters.outbound.aeat.auth.evaluate_loaded_certificate_health`, or
classifies the configured DNI/NIE). The registry row reuses the same
referential-integrity gate the registry runs at snapshot build
(``check_all_id_references``) by driving
:meth:`~domain.calculations.registry.ValidatedRegistryAuthority.snapshot`
over every bundled revision. ``aeat config check`` renders these rows through
:class:`~entrypoints.cli._config._check_payloads.CheckPreflightPayload`
beside the capability posture and dependency probes.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field, model_validator

from ..core import (
    STRICT_FROZEN_CONFIG,
    ActionConditionality,
    ActionEvidenceProvenance,
    AuthProviderKind,
    NoRecoveryOutcome,
)
from ..core.config import Settings, load_settings
from ..core.directory_scan import (
    iter_directory,
)
from ..core.errors import CadrumoError
from ..core.paths import (
    WINDOWS_MAX_PATH,
    windows_long_paths_enabled,
    windows_storage_root_long_path_margin,
)
from .auth.probes import ProviderProbeResult
from .operator_actions import ActionReference, ConditionEvidence, PreconditionVerdict

if TYPE_CHECKING:
    from ..domain.portals import PortalDriftEvent


__all__ = [
    "HealthSeverity",
    "PreflightCheck",
    "grade_provider_probe_result",
    "probe_auth_providers",
    "probe_portal_registry_health",
    "probe_registry_referential_integrity",
    "probe_storage_corpus_env",
    "run_preflight_checks",
]


class HealthSeverity(StrEnum):
    """Closed severity catalogue for a :class:`PreflightCheck` row.

    ``OK`` — the dimension is healthy (or a not-configured optional
    provider, which is not a fault). ``WARN`` — a non-blocking advisory
    (a certificate inside its pre-expiry window; no master-key passphrase
    configured). ``ERROR`` — a real breakage the operator must fix (an
    expired / corrupt certificate, an unreachable storage root, a missing
    bundled corpus, a dangling registry reference).
    """

    OK = "ok"
    WARN = "warn"
    ERROR = "error"


class PreflightCondition(StrEnum):
    """Closed failed-condition identities for workstation health probes."""

    AUTH_PROVIDER_HEALTHY = "preflight.auth.provider_healthy"
    STORAGE_ROOT_WRITABLE = "preflight.storage.root_writable"
    CORPUS_PRESENT = "preflight.corpus.present"
    WINDOWS_PATH_FITS = "preflight.storage.windows_path_fits"
    REGISTRY_REFERENCES_VALID = "preflight.registry.references_valid"
    PORTAL_REGISTRY_HEALTHY = "preflight.portal.registry_healthy"


class PreflightCheck(BaseModel):
    """One typed workstation-preflight health row.

    ``check`` is the stable row id shown by ``aeat config check`` (e.g.
    ``auth-provider:certificate``, ``storage:local-root``,
    ``corpus:normatives``, ``registry:referential-integrity``).
    ``healthy`` is the boolean verdict and ``severity`` grades it. ``facts``
    carries only locale-neutral observations. An unhealthy row owns one typed
    precondition verdict; a healthy row owns none.
    """

    model_config = STRICT_FROZEN_CONFIG

    check: str = Field(min_length=1)
    healthy: bool
    severity: HealthSeverity
    facts: dict[str, str | int | bool] = Field(default_factory=dict)
    precondition_verdict: PreconditionVerdict | None = None

    @model_validator(mode="after")
    def _verdict_matches_health(self) -> PreflightCheck:
        if self.healthy and self.precondition_verdict is not None:
            raise ValueError("healthy preflight rows cannot carry a failed precondition")
        if not self.healthy and self.precondition_verdict is None:
            raise ValueError("unhealthy preflight rows require a typed precondition verdict")
        return self


def _preflight_verdict(
    condition: PreflightCondition,
    *,
    facts: Mapping[str, str | int | bool],
    action_id: str | None = None,
) -> PreconditionVerdict:
    condition_id = condition.value
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            ConditionEvidence(
                condition_id=condition_id,
                evidence_id=f"{condition_id}.observation",
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                values=facts,
            ),
        ),
        conditionality=ActionConditionality.IMMEDIATE if action_id else ActionConditionality.NOT_APPLICABLE,
        action=ActionReference(action_id=action_id) if action_id else None,
        no_recovery_outcome=None if action_id else NoRecoveryOutcome.OPERATOR_DECISION,
    )


def _failed_check(
    *,
    check: str,
    severity: HealthSeverity,
    condition: PreflightCondition,
    facts: Mapping[str, str | int | bool],
    action_id: str | None = None,
) -> PreflightCheck:
    return PreflightCheck(
        check=check,
        healthy=False,
        severity=severity,
        facts=dict(facts),
        precondition_verdict=_preflight_verdict(condition, facts=facts, action_id=action_id),
    )


def _healthy_check(*, check: str, severity: HealthSeverity, facts: Mapping[str, str | int | bool]) -> PreflightCheck:
    return PreflightCheck(check=check, healthy=True, severity=severity, facts=dict(facts))


# ── Per-auth-provider certificate / Cl@ve Móvil health ────────────────

# ProviderProbeResult members that mean the provider is simply not configured on
# this workstation — a legitimate, non-fault state for an optional provider.
_UNCONFIGURED_PROBE_RESULTS: Final[frozenset[ProviderProbeResult]] = frozenset(
    {
        ProviderProbeResult.NO_PROVIDER,
        ProviderProbeResult.NO_PATH_SET,
        ProviderProbeResult.IDENTITY_UNSET,
    },
)
# ProviderProbeResult members that are a real, operator-fixable misconfiguration.
_ERROR_PROBE_RESULTS: Final[frozenset[ProviderProbeResult]] = frozenset(
    {
        ProviderProbeResult.EXPIRED,
        ProviderProbeResult.CORRUPT,
        ProviderProbeResult.UNREADABLE,
        ProviderProbeResult.INVALID_IDENTITY,
        ProviderProbeResult.FILE_MISSING,
    },
)
# ProviderProbeResult members that are a non-blocking advisory.
_WARN_PROBE_RESULTS: Final[frozenset[ProviderProbeResult]] = frozenset({ProviderProbeResult.EXPIRING})
# The single ProviderProbeResult member that means the provider is configured and
# sound. Kept a set so the four bands partition the enum and a newly added
# member belongs to exactly one of them.
_OK_PROBE_RESULTS: Final[frozenset[ProviderProbeResult]] = frozenset({ProviderProbeResult.OK})


def grade_provider_probe_result(
    provider: AuthProviderKind,
    result: ProviderProbeResult,
) -> tuple[HealthSeverity, bool]:
    """Grade one ``ProviderProbeResult`` value into a doctor verdict.

    The four declared bands partition
    :class:`~application.auth.ProviderProbeResult`: a real misconfiguration is
    ``ERROR``, a pre-expiry certificate is ``WARN``, and a sound or
    not-configured-optional provider is ``OK``.

    A value in none of them is graded ``ERROR`` rather than passed. It reports
    a defect in this mapping — most likely a probe result added without a band
    — and not a verdict about the operator's workstation; a doctor that renders
    an ungraded state green gives the one answer an operator cannot act on.

    Args:
        provider: The :class:`~core.AuthProviderKind` member being graded.
        result: The probe's typed :class:`~application.auth.ProviderProbeResult`
            member.

    Returns:
        The severity and the healthy verdict.
    """
    del provider
    if result in _ERROR_PROBE_RESULTS:
        return HealthSeverity.ERROR, False
    if result in _WARN_PROBE_RESULTS:
        return HealthSeverity.WARN, True
    if result in _UNCONFIGURED_PROBE_RESULTS or result in _OK_PROBE_RESULTS:
        return HealthSeverity.OK, True
    return HealthSeverity.ERROR, False


def probe_auth_providers(*, settings: Settings | None = None) -> tuple[PreflightCheck, ...]:
    """Probe each auth provider's local certificate / Cl@ve Móvil configuration.

    Runs the pure-local per-provider probe for every
    :class:`~core.AuthProviderKind` (no network, no
    active-profile session) and maps its typed
    :class:`~application.auth.ProviderProbeResult` onto a
    :class:`PreflightCheck`. A not-configured optional provider is ``OK``
    (not a fault); an expired / corrupt / unreadable certificate or an
    invalid Cl@ve identity is ``ERROR``; a certificate inside its
    pre-expiry window is ``WARN``. A result belonging to none of the four
    declared bands is itself reported ``ERROR``, because an ungraded state
    rendered green is the one doctor answer an operator cannot act on. The
    probe never raises.
    """
    from .auth.operator_probes import probe_provider_configuration

    rows: list[PreflightCheck] = []
    for kind in AuthProviderKind:
        check_id = f"auth-provider:{kind.value}"
        try:
            probe = probe_provider_configuration(kind.value, settings=settings)
        except CadrumoError as exc:  # never crash the doctor on a probe failure
            facts = {"provider": kind.value, "probe_error_type": type(exc).__name__}
            rows.append(
                _failed_check(
                    check=check_id,
                    severity=HealthSeverity.ERROR,
                    condition=PreflightCondition.AUTH_PROVIDER_HEALTHY,
                    facts=facts,
                    action_id="operator.auth.configure",
                ),
            )
            continue
        severity, healthy = grade_provider_probe_result(kind, probe.result)
        facts = {"provider": kind.value, "probe_result": probe.result.value}
        if healthy:
            rows.append(_healthy_check(check=check_id, severity=severity, facts=facts))
        else:
            rows.append(
                _failed_check(
                    check=check_id,
                    severity=severity,
                    condition=PreflightCondition.AUTH_PROVIDER_HEALTHY,
                    facts=facts,
                    action_id="operator.auth.configure",
                )
            )
    return tuple(rows)


# ── Secure-storage, bundled-corpus, and configuration preflight ───────


def probe_storage_corpus_env(
    *,
    object_path_suffix_length: int,
    settings: Settings | None = None,
) -> tuple[PreflightCheck, ...]:
    """Probe secure-storage reachability, bundled-corpus presence, and config sanity.

    Returns one :class:`PreflightCheck` per dimension: the local
    secure-storage root is writable (an existing ancestor accepts
    writes), the bundled legal-normatives and Manual-práctico corpora are
    present, and the deployment :class:`~core.config.Settings`
    loaded with a coherent master-key posture. Each probe is a read-only
    filesystem / configuration inspection — it never writes into the
    operator's storage root and never raises.
    """
    resolved = settings if settings is not None else load_settings()
    return (
        _probe_storage_root(resolved),
        _probe_corpus("corpus:normatives", resolved.aeat_normatives_root, "legal normatives"),
        _probe_corpus("corpus:manuals", resolved.aeat_manuals_root, "Manual práctico"),
        _probe_config_sanity(resolved),
        _probe_windows_long_path_support(resolved, object_path_suffix_length=object_path_suffix_length),
    )


def _nearest_existing_ancestor(path: Path) -> Path | None:
    """Return the closest existing directory at or above ``path``."""
    for candidate in (path, *path.parents):
        if candidate.exists():
            return candidate
    return None


def _probe_storage_root(settings: Settings) -> PreflightCheck:
    """Report whether the local secure-storage root is reachable and writable."""
    root = settings.cadrumo_local_storage_root
    ancestor = _nearest_existing_ancestor(root)
    if ancestor is None:
        facts = {"storage_root": str(root), "existing_ancestor_present": False}
        return _failed_check(
            check="storage:local-root",
            severity=HealthSeverity.ERROR,
            condition=PreflightCondition.STORAGE_ROOT_WRITABLE,
            facts=facts,
            action_id="operator.storage.init",
        )
    if not ancestor.is_dir():
        facts = {"storage_root": str(root), "ancestor": str(ancestor), "ancestor_is_directory": False}
        return _failed_check(
            check="storage:local-root",
            severity=HealthSeverity.ERROR,
            condition=PreflightCondition.STORAGE_ROOT_WRITABLE,
            facts=facts,
        )
    if not os.access(ancestor, os.W_OK):
        facts = {"storage_root": str(root), "ancestor": str(ancestor), "ancestor_writable": False}
        return _failed_check(
            check="storage:local-root",
            severity=HealthSeverity.ERROR,
            condition=PreflightCondition.STORAGE_ROOT_WRITABLE,
            facts=facts,
        )
    return _healthy_check(
        check="storage:local-root",
        severity=HealthSeverity.OK,
        facts={"storage_root": str(root), "root_present": root.exists(), "ancestor_writable": True},
    )


def _probe_corpus(check_id: str, root: Path, label: str) -> PreflightCheck:
    """Report whether a bundled corpus directory is present and non-empty."""
    try:
        present = root.is_dir() and any(iter_directory(root, require_root=True))
    except OSError as exc:
        facts = {"corpus_root": str(root), "error_type": type(exc).__name__, "corpus_present": False}
        return _failed_check(
            check=check_id,
            severity=HealthSeverity.ERROR,
            condition=PreflightCondition.CORPUS_PRESENT,
            facts=facts,
        )
    if not present:
        facts = {"corpus_root": str(root), "corpus_present": False}
        return _failed_check(
            check=check_id,
            severity=HealthSeverity.ERROR,
            condition=PreflightCondition.CORPUS_PRESENT,
            facts=facts,
        )
    return _healthy_check(
        check=check_id,
        severity=HealthSeverity.OK,
        facts={"corpus_root": str(root), "corpus_present": True},
    )


def _probe_config_sanity(settings: Settings) -> PreflightCheck:
    """Report whether the deployment configuration loaded with a coherent key posture.

    Reaching this row means :func:`~core.config.load_settings`
    already produced a validated :class:`~core.config.Settings`, so
    the env-var / config parse is sane. The remaining signal is the
    master-key passphrase posture: an absent passphrase is a non-blocking
    advisory (the store is merely locked and prompts interactively), a
    configured one is ``OK``.
    """
    if settings.cadrumo_secret_passphrase is None:
        return _healthy_check(
            check="env:configuration",
            severity=HealthSeverity.WARN,
            facts={"configuration_valid": True, "secret_passphrase_configured": False},
        )
    return _healthy_check(
        check="env:configuration",
        severity=HealthSeverity.OK,
        facts={"configuration_valid": True, "secret_passphrase_configured": True},
    )


# ── Windows MAX_PATH (long-path) headroom ───────────────────────────

#: Headroom below which the long-path row advises rather than staying silent.
#:
#: The number expresses what the margin has to survive, not a taste for round
#: figures. The deepest object path is budgeted from the LONGEST NAMESPACE THIS
#: BUILD REGISTERS, so the margin shrinks whenever a longer one is added --
#: without anyone editing a constant, and without the operator doing anything at
#: all. Forty characters is roughly the room a further dotted module path needs,
#: so a root inside the threshold is one that a plausible future namespace could
#: push past ``WINDOWS_MAX_PATH``.
#:
#: It was calibrated against a budget understated by 54 characters, and the
#: honest budget (``d10519946f``) leaves a DEFAULT install inside it. That is
#: not a reason to raise the number: the advisory is true, and the gap is
#: genuinely small -- the longest registered namespace is 72 characters and a
#: default root survives only about 80, which an ordinary module path reaches.
#: Tuning this to restore silence would re-hide exactly what that fix surfaced.
_LONG_PATH_WARN_MARGIN = 40


def _probe_windows_long_path_support(settings: Settings, *, object_path_suffix_length: int) -> PreflightCheck:
    r"""Report whether the storage root has headroom below the Windows ``MAX_PATH`` ceiling.

    Not applicable outside Windows: every non-Windows platform (and every
    Windows workstation that already carries the ``LongPathsEnabled``
    opt-in) returns ``OK``. On a Windows workstation without the opt-in,
    the row grades on
    :func:`~core.paths.windows_storage_root_long_path_margin` — the
    character headroom left before the deepest object the bucket / blob
    layout can produce
    (``<root>\buckets\<uuid>\blobs\<namespace>\<hmac>--<label>.meta.json``)
    would meet or exceed :data:`~core.paths.WINDOWS_MAX_PATH`. The
    ``<namespace>`` budget comes from
    :func:`~adapters.outbound.storage.windows_worst_case_object_path_suffix_length`,
    which measures the longest namespace this build actually registers
    rather than a hand-picked sample. Zero or
    negative margin is an ``ERROR`` (a real object write can fail
    partway through); a thin positive margin is a ``WARN`` advisory so the
    operator can relocate the root before it runs out. This probe never
    writes to disk and never raises — a registry read failure degrades to
    the conservative "not enabled" assumption inside
    :func:`~core.paths.windows_long_paths_enabled`.
    """
    if sys.platform != "win32":
        return _healthy_check(
            check="storage:windows-long-path",
            severity=HealthSeverity.OK,
            facts={"platform_windows": False, "path_limit_applicable": False},
        )

    if windows_long_paths_enabled():
        return _healthy_check(
            check="storage:windows-long-path",
            severity=HealthSeverity.OK,
            facts={"platform_windows": True, "long_paths_enabled": True, "path_limit_applicable": False},
        )

    root = settings.cadrumo_local_storage_root
    margin = windows_storage_root_long_path_margin(
        root,
        object_path_suffix_length=object_path_suffix_length,
    )
    if margin <= 0:
        facts = {
            "storage_root": str(root),
            "long_paths_enabled": False,
            "path_margin": margin,
            "max_path": WINDOWS_MAX_PATH,
        }
        return _failed_check(
            check="storage:windows-long-path",
            severity=HealthSeverity.ERROR,
            condition=PreflightCondition.WINDOWS_PATH_FITS,
            facts=facts,
        )
    if margin < _LONG_PATH_WARN_MARGIN:
        return _healthy_check(
            check="storage:windows-long-path",
            severity=HealthSeverity.WARN,
            facts={
                "storage_root": str(root),
                "long_paths_enabled": False,
                "path_margin": margin,
                "max_path": WINDOWS_MAX_PATH,
            },
        )
    return _healthy_check(
        check="storage:windows-long-path",
        severity=HealthSeverity.OK,
        facts={
            "storage_root": str(root),
            "long_paths_enabled": False,
            "path_margin": margin,
            "max_path": WINDOWS_MAX_PATH,
        },
    )


# ── #98 — registry referential integrity ─────────────────────────────────────


def probe_registry_referential_integrity() -> PreflightCheck:
    """Run the registry referential-integrity gate over every bundled revision.

    Drives the same ``check_all_id_references`` existence gate the
    registry runs at snapshot build (casilla / formula / binding / legal
    / source ID references) by building a snapshot for every revision of
    every bundled modelo through
    :meth:`~domain.calculations.registry.ValidatedRegistryAuthority.snapshot`.
    A dangling reference surfaces as a
    :class:`~domain.calculations.registry.RegistryValidationError`,
    which is caught and reported as an ``error`` row naming the count of
    failing revisions — the probe never raises.

    Returns:
        A single :class:`PreflightCheck` row for the registry-integrity dimension.
    """
    from ..domain.calculations.registry.authority import bundled_authority
    from ..domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError

    try:
        authority = bundled_authority()
    except (RegistryValidationError, RegistrySnapshotError, CadrumoError) as exc:
        facts = {"registry_loaded": False, "error_type": type(exc).__name__}
        return _failed_check(
            check="registry:referential-integrity",
            severity=HealthSeverity.ERROR,
            condition=PreflightCondition.REGISTRY_REFERENCES_VALID,
            facts=facts,
        )

    return _probe_registry_authority(authority)


def _probe_registry_authority(authority: object) -> PreflightCheck:
    """Validate one loaded authority through the production snapshot path."""
    from collections import Counter

    from ..domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError

    revisions_checked = 0
    failure_count = 0
    grade_counts: Counter[str] = Counter()
    for modelo in authority.modelos:  # ty: ignore[unresolved-attribute]
        for revision in modelo.revisions.values():
            filing_year, period = _representative_filing_context(revision)
            if filing_year is None or period is None:
                continue
            revisions_checked += 1
            requested_grade = revision.effective_authority_grade
            grade_counts[requested_grade.value] += 1
            try:
                authority.snapshot(  # ty: ignore[unresolved-attribute]
                    modelo.id,
                    filing_year=filing_year,
                    period=period,
                    revision_id=revision.id,
                    grade=requested_grade,
                )
            except (RegistryValidationError, RegistrySnapshotError):
                failure_count += 1

    if failure_count:
        facts: dict[str, str | int | bool] = {
            "revisions_checked": revisions_checked,
            "failure_count": failure_count,
        }
        facts.update({f"grade_{grade}_count": count for grade, count in sorted(grade_counts.items())})
        return _failed_check(
            check="registry:referential-integrity",
            severity=HealthSeverity.ERROR,
            condition=PreflightCondition.REGISTRY_REFERENCES_VALID,
            facts=facts,
        )
    return _healthy_check(
        check="registry:referential-integrity",
        severity=HealthSeverity.OK,
        facts={
            "revisions_checked": revisions_checked,
            "failure_count": 0,
            **{f"grade_{grade}_count": count for grade, count in sorted(grade_counts.items())},
        },
    )


def _representative_filing_context(revision: object) -> tuple[int | None, str | None]:
    """Derive one buildable ``(filing_year, period)`` for ``revision``.

    Mirrors the registry test harness: the first declared year (or the
    open-ended ``year_from``) paired with the first declared period. A
    revision that declares no period is skipped (returns ``(None, None)``)
    rather than guessed.
    """
    selector = getattr(revision, "period_selector", None)
    if selector is None:
        return None, None
    years = getattr(selector, "years", ()) or ()
    raw_filing_year = years[0] if years else getattr(selector, "year_from", None)
    filing_year = raw_filing_year if isinstance(raw_filing_year, int) else None
    periods = getattr(selector, "periods", ()) or ()
    raw_period = periods[0] if periods else None
    period = raw_period if isinstance(raw_period, str) else None
    return filing_year, period


# ── Portal-registry health / recorded portal drift ────────────────────

# UrlStability tiers whose drift is a real integrity concern (the URL was
# promised to change only via explicit Orden / campaign-boundary publication).
# A drift on a volatile app-path shell is an expected rotation, not an error.
_PORTAL_DRIFT_ERROR_STABILITIES = frozenset({"stable_protocol_grade"})


def probe_portal_registry_health(
    *,
    drift_events: Sequence[PortalDriftEvent] = (),
) -> PreflightCheck:
    """Report portal-registry assembly health and any recorded portal drift.

    Read-only and offline: this probe never contacts AEAT. It confirms the
    bundled :data:`~domain.portals.PORTAL_REGISTRY` assembled (a
    :class:`~domain.portals.PortalIntegrityError` at import is caught and
    reported as an ``error`` row) and reports the count of any *recorded*
    :class:`~domain.portals.PortalDriftEvent` passed in. The events are
    produced elsewhere, under the live-read access gate, by
    :func:`~domain.portals.evaluate_portal_drift`; this row reports the
    registered / recorded state, it does not perform a live probe.

    With no recorded drift (the offline default) the row is ``OK``. A recorded
    drift on a ``stable_protocol_grade`` (BOE-referenced) URL is an ``ERROR``;
    a drift on a campaign-stable or volatile app-path URL is a ``WARN``
    advisory, since those tiers are expected to rotate.

    Args:
        drift_events: Recorded portal-drift events to surface. Defaults to
            empty — no live probe, nothing recorded.

    Returns:
        One :class:`PreflightCheck` row with id ``portal-registry:health``.
    """
    from ..domain.portals import PORTAL_REGISTRY
    from ..domain.portals import PortalRegistryError as _PortalRegistryError

    try:
        portal_count = len(PORTAL_REGISTRY)
    except _PortalRegistryError as exc:  # registry failed structural assembly
        facts = {"registry_assembled": False, "error_type": type(exc).__name__}
        return _failed_check(
            check="portal-registry:health",
            severity=HealthSeverity.ERROR,
            condition=PreflightCondition.PORTAL_REGISTRY_HEALTHY,
            facts=facts,
        )

    if not drift_events:
        return _healthy_check(
            check="portal-registry:health",
            severity=HealthSeverity.OK,
            facts={"portal_count": portal_count, "drift_count": 0, "stable_drift_present": False},
        )

    has_error = any(str(event.url_stability) in _PORTAL_DRIFT_ERROR_STABILITIES for event in drift_events)
    facts = {
        "portal_count": portal_count,
        "drift_count": len(drift_events),
        "stable_drift_present": has_error,
    }
    if has_error:
        return _failed_check(
            check="portal-registry:health",
            severity=HealthSeverity.ERROR,
            condition=PreflightCondition.PORTAL_REGISTRY_HEALTHY,
            facts=facts,
        )
    return _healthy_check(
        check="portal-registry:health",
        severity=HealthSeverity.WARN,
        facts=facts,
    )


def run_preflight_checks(
    *,
    object_path_suffix_length: int,
    settings: Settings | None = None,
) -> tuple[PreflightCheck, ...]:
    """Run every workstation-preflight probe and return the typed :class:`PreflightCheck` rows.

    Concatenates the per-auth-provider certificate / Cl@ve Móvil health
    rows, the secure-storage / bundled-corpus / configuration rows,
    the registry referential-integrity row, and the
    portal-registry health / recorded-drift row. Every probe catches
    its own failures and reports them as ``error`` rows, so the aggregate
    never raises. The portal-drift row runs with the offline default (no
    recorded drift), reporting registered state rather than a live probe.
    """
    resolved = settings if settings is not None else load_settings()
    return (
        *probe_auth_providers(settings=resolved),
        *probe_storage_corpus_env(settings=resolved, object_path_suffix_length=object_path_suffix_length),
        probe_registry_referential_integrity(),
        probe_portal_registry_health(),
    )
