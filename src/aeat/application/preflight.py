"""Workstation preflight health probes for ``aeat config check``.

This module is the read-only doctor surface for the health dimensions that sit
*beside* the external-dependency probes in :mod:`aeat.application.provisioning`:
per-auth-provider certificate / Cl@ve Móvil configuration health, secure-storage
and bundled-corpus reachability, key configuration sanity, and registry
referential integrity. Each probe answers one health question and returns a
typed :class:`PreflightCheck` — it never raises; a broken dimension is report
data (an ``error`` severity row with a concrete remediation), not an exception
path, so the doctor reports status rather than crashing on a red row.

The certificate / Cl@ve Móvil rows reuse
:func:`~aeat.application.auth.probe_provider_configuration` (the pure-local
per-provider probe that opens the ``.p12`` and classifies expiry via
:func:`~aeat.adapters.outbound.aeat.auth.evaluate_loaded_certificate_health`, or
classifies the configured DNI/NIE). The registry row reuses the same
referential-integrity gate the registry runs at snapshot build
(``check_all_id_references``) by driving
:meth:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority.snapshot`
over every bundled revision. ``aeat config check`` renders these rows through
:class:`~aeat.entrypoints.cli._config._check_payloads.CheckPreflightPayload`
beside the capability posture and dependency probes.
"""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, Field

from ..core import STRICT_FROZEN_CONFIG
from ..core.config import Settings, load_settings
from ..core.errors import AeatError

if TYPE_CHECKING:
    from ..domain.calculations.registry import ModeloDefinition, RegistrySnapshot


class _RegistryAuthorityLike(Protocol):
    """Structural view of the registry authority the sweep consumes.

    Declared as a :class:`typing.Protocol` so
    :func:`probe_registry_referential_integrity` accepts an injected
    authority in tests without importing the concrete
    :class:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority`
    at module load and without a mock: any object exposing the real
    ``modelos`` iterable and ``snapshot`` builder satisfies it.
    """

    @property
    def modelos(self) -> tuple[ModeloDefinition, ...]: ...

    def snapshot(
        self,
        modelo_id: str,
        *,
        filing_year: int,
        period: str,
        revision_id: str | None = ...,
    ) -> RegistrySnapshot: ...


__all__ = [
    "HealthSeverity",
    "PreflightCheck",
    "probe_auth_providers",
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


class PreflightCheck(BaseModel):
    """One typed workstation-preflight health row.

    ``check`` is the stable row id shown by ``aeat config check`` (e.g.
    ``auth-provider:certificate``, ``storage:local-root``,
    ``corpus:normatives``, ``registry:referential-integrity``).
    ``healthy`` is the boolean verdict; ``severity`` grades it;
    ``detail`` explains the observed state; ``remediation`` names the
    concrete operator action when ``healthy`` is false.
    """

    model_config = STRICT_FROZEN_CONFIG

    check: str = Field(min_length=1)
    healthy: bool
    severity: HealthSeverity
    detail: str = ""
    remediation: str = ""


# ── #286 — per-auth-provider certificate / Cl@ve Móvil health ────────────────

# ProviderProbeResult values that mean the provider is simply not configured on
# this workstation — a legitimate, non-fault state for an optional provider.
_UNCONFIGURED_PROBE_RESULTS = frozenset({"no_provider", "no_path_set", "identity_unset"})
# ProviderProbeResult values that are a real, operator-fixable misconfiguration.
_ERROR_PROBE_RESULTS = frozenset({"expired", "corrupt", "unreadable", "invalid_identity", "file_missing"})
# ProviderProbeResult values that are a non-blocking advisory.
_WARN_PROBE_RESULTS = frozenset({"expiring"})


def probe_auth_providers(*, settings: Settings | None = None) -> tuple[PreflightCheck, ...]:
    """Probe each auth provider's local certificate / Cl@ve Móvil configuration.

    Runs the pure-local per-provider probe for every
    :class:`~aeat.application.auth.AuthProviderKind` (no network, no
    active-profile session) and maps its typed
    :class:`~aeat.application.auth.ProviderProbeResult` onto a
    :class:`PreflightCheck`. A not-configured optional provider is ``OK``
    (not a fault); an expired / corrupt / unreadable certificate or an
    invalid Cl@ve identity is ``ERROR``; a certificate inside its
    pre-expiry window is ``WARN``. The probe never raises.
    """
    from .auth import AuthProviderKind, probe_provider_configuration

    rows: list[PreflightCheck] = []
    for kind in AuthProviderKind:
        check_id = f"auth-provider:{kind.value}"
        try:
            probe = probe_provider_configuration(kind.value, settings=settings)
        except AeatError as exc:  # never crash the doctor on a probe failure
            rows.append(
                PreflightCheck(
                    check=check_id,
                    healthy=False,
                    severity=HealthSeverity.ERROR,
                    detail=f"provider probe failed: {type(exc).__name__}: {exc}",
                    remediation="review the provider configuration under `aeat config auth`",
                ),
            )
            continue
        result = str(probe.result)
        if result in _ERROR_PROBE_RESULTS:
            severity = HealthSeverity.ERROR
            healthy = False
            remediation = _auth_error_remediation(kind.value, result)
        elif result in _WARN_PROBE_RESULTS:
            severity = HealthSeverity.WARN
            healthy = True
            remediation = "renew the certificate before it expires (obtain a fresh FNMT bundle)"
        else:
            # OK or an unconfigured-optional state: both are non-faults.
            severity = HealthSeverity.OK
            healthy = True
            remediation = ""
        rows.append(
            PreflightCheck(
                check=check_id,
                healthy=healthy,
                severity=severity,
                detail=probe.summary or f"provider {kind.value}: {result or 'unknown'}",
                remediation=remediation,
            ),
        )
    return tuple(rows)


def _auth_error_remediation(provider: str, result: str) -> str:
    """Return the concrete operator action for a red auth-provider probe."""
    if provider == "certificate":
        if result == "file_missing":
            return "point `aeat config auth certificate --file` at an existing .p12 bundle"
        if result == "expired":
            return "obtain a fresh FNMT certificate and reconfigure `aeat config auth certificate`"
        if result == "unreadable":
            return "set the correct PKCS#12 passphrase (AEAT_CERTIFICATE_PASSWORD)"
        return "re-export a valid .p12 bundle and reconfigure `aeat config auth certificate`"
    return "set a valid DNI/NIE for Cl@ve Móvil via `aeat config auth clave-movil`"


# ── #102 — secure-storage, bundled-corpus, and configuration preflight ───────


def probe_storage_corpus_env(*, settings: Settings | None = None) -> tuple[PreflightCheck, ...]:
    """Probe secure-storage reachability, bundled-corpus presence, and config sanity.

    Returns one :class:`PreflightCheck` per dimension: the local
    secure-storage root is writable (an existing ancestor accepts
    writes), the bundled legal-normatives and Manual-práctico corpora are
    present, and the deployment :class:`~aeat.core.config.Settings`
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
    )


def _nearest_existing_ancestor(path: Path) -> Path | None:
    """Return the closest existing directory at or above ``path``."""
    for candidate in (path, *path.parents):
        if candidate.exists():
            return candidate
    return None


def _probe_storage_root(settings: Settings) -> PreflightCheck:
    """Report whether the local secure-storage root is reachable and writable."""
    root = settings.aeat_local_storage_root
    ancestor = _nearest_existing_ancestor(root)
    if ancestor is None:
        return PreflightCheck(
            check="storage:local-root",
            healthy=False,
            severity=HealthSeverity.ERROR,
            detail=f"no existing directory at or above the storage root {root}",
            remediation=f"create the storage root directory {root} or set AEAT_LOCAL_STORAGE_ROOT to a writable path",
        )
    if not ancestor.is_dir():
        return PreflightCheck(
            check="storage:local-root",
            healthy=False,
            severity=HealthSeverity.ERROR,
            detail=f"the storage root ancestor {ancestor} is not a directory",
            remediation=f"set AEAT_LOCAL_STORAGE_ROOT to a writable directory (currently {root})",
        )
    if not os.access(ancestor, os.W_OK):
        return PreflightCheck(
            check="storage:local-root",
            healthy=False,
            severity=HealthSeverity.ERROR,
            detail=f"the storage root ancestor {ancestor} is not writable",
            remediation=f"grant write access to {ancestor} or set AEAT_LOCAL_STORAGE_ROOT to a writable path",
        )
    existing = "present" if root.exists() else "created lazily on first write"
    return PreflightCheck(
        check="storage:local-root",
        healthy=True,
        severity=HealthSeverity.OK,
        detail=f"secure-storage root {root} is reachable and writable ({existing})",
    )


def _probe_corpus(check_id: str, root: Path, label: str) -> PreflightCheck:
    """Report whether a bundled corpus directory is present and non-empty."""
    try:
        present = root.is_dir() and any(root.iterdir())
    except OSError as exc:
        return PreflightCheck(
            check=check_id,
            healthy=False,
            severity=HealthSeverity.ERROR,
            detail=f"the bundled {label} corpus at {root} is unreadable: {type(exc).__name__}",
            remediation="reinstall the aeat package so the bundled corpus data is present",
        )
    if not present:
        return PreflightCheck(
            check=check_id,
            healthy=False,
            severity=HealthSeverity.ERROR,
            detail=f"the bundled {label} corpus is missing or empty at {root}",
            remediation="reinstall the aeat package so the bundled corpus data is present",
        )
    return PreflightCheck(
        check=check_id,
        healthy=True,
        severity=HealthSeverity.OK,
        detail=f"the bundled {label} corpus is present at {root}",
    )


def _probe_config_sanity(settings: Settings) -> PreflightCheck:
    """Report whether the deployment configuration loaded with a coherent key posture.

    Reaching this row means :func:`~aeat.core.config.load_settings`
    already produced a validated :class:`~aeat.core.config.Settings`, so
    the env-var / config parse is sane. The remaining signal is the
    master-key passphrase posture: an absent passphrase is a non-blocking
    advisory (the store is merely locked and prompts interactively), a
    configured one is ``OK``.
    """
    if settings.aeat_secret_passphrase is None:
        return PreflightCheck(
            check="env:configuration",
            healthy=True,
            severity=HealthSeverity.WARN,
            detail="configuration is valid but no master-key passphrase is configured (locked store)",
            remediation="set AEAT_SECRET_PASSPHRASE for non-interactive access, or unlock interactively when prompted",
        )
    return PreflightCheck(
        check="env:configuration",
        healthy=True,
        severity=HealthSeverity.OK,
        detail="deployment configuration loaded and a master-key passphrase is configured",
    )


# ── #98 — registry referential integrity ─────────────────────────────────────


def probe_registry_referential_integrity(
    *,
    authority: _RegistryAuthorityLike | None = None,
) -> PreflightCheck:
    """Run the registry referential-integrity gate over every bundled revision.

    Drives the same ``check_all_id_references`` existence gate the
    registry runs at snapshot build (casilla / formula / binding / legal
    / source ID references) by building a snapshot for every revision of
    every bundled modelo through
    :meth:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority.snapshot`.
    A dangling reference surfaces as a
    :class:`~aeat.domain.calculations.registry.RegistryValidationError`,
    which is caught and reported as an ``error`` row naming the count of
    failing revisions — the probe never raises. ``authority`` overrides
    the default bundled authority so the sweep can be exercised against a
    controlled registry.
    """
    from ..domain.calculations.registry import (
        RegistrySnapshotError,
        RegistryValidationError,
        bundled_authority,
    )

    if authority is None:
        try:
            authority = bundled_authority()
        except (RegistryValidationError, RegistrySnapshotError, AeatError) as exc:
            return PreflightCheck(
                check="registry:referential-integrity",
                healthy=False,
                severity=HealthSeverity.ERROR,
                detail=f"the bundled registry failed to load: {type(exc).__name__}: {exc}",
                remediation=(
                    "inspect the registry TOML sources; run the registry validation suite for the failing modelo"
                ),
            )

    revisions_checked = 0
    failures: list[str] = []
    for modelo in authority.modelos:
        for revision in modelo.revisions.values():
            filing_year, period = _representative_filing_context(revision)
            if filing_year is None or period is None:
                continue
            revisions_checked += 1
            try:
                authority.snapshot(
                    modelo.id,
                    filing_year=filing_year,
                    period=period,
                    revision_id=revision.id,
                )
            except (RegistryValidationError, RegistrySnapshotError) as exc:
                failures.append(f"modelo {modelo.id} revision {revision.id}: {exc}")

    if failures:
        preview = "; ".join(failures[:3])
        return PreflightCheck(
            check="registry:referential-integrity",
            healthy=False,
            severity=HealthSeverity.ERROR,
            detail=(
                f"{len(failures)} of {revisions_checked} registry revisions have dangling "
                f"typed-ID references: {preview}"
            ),
            remediation="fix the dangling casilla/formula/binding/legal/source references in the named revision TOML",
        )
    return PreflightCheck(
        check="registry:referential-integrity",
        healthy=True,
        severity=HealthSeverity.OK,
        detail=f"all {revisions_checked} registry revisions pass the typed-ID referential-integrity gate",
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
    filing_year = years[0] if years else getattr(selector, "year_from", None)
    periods = getattr(selector, "periods", ()) or ()
    period = periods[0] if periods else None
    return filing_year, period


def run_preflight_checks(*, settings: Settings | None = None) -> tuple[PreflightCheck, ...]:
    """Run every workstation-preflight probe and return the typed rows.

    Concatenates the per-auth-provider certificate / Cl@ve Móvil health
    rows (#286), the secure-storage / bundled-corpus / configuration rows
    (#102), and the registry referential-integrity row (#98). Every probe
    catches its own failures and reports them as ``error`` rows, so the
    aggregate never raises.
    """
    resolved = settings if settings is not None else load_settings()
    return (
        *probe_auth_providers(settings=resolved),
        *probe_storage_corpus_env(settings=resolved),
        probe_registry_referential_integrity(),
    )
