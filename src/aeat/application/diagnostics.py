"""Application-owned diagnostics and version reporting."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from aeat import __version__

from ..core.config import PROJECT_ROOT
from ..domain.calculations.registry._authority import ValidatedRegistryAuthority


class RegistryVersionSummary(BaseModel):
    """Stable registry summary suitable for version and doctor surfaces."""

    model_config = ConfigDict(frozen=True)

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

    model_config = ConfigDict(frozen=True)

    package_name: str
    package_version: str
    registry: RegistryVersionSummary


def build_cli_version_report(registry_root: Path | None = None) -> CliVersionReport:
    """Return the package and registry summary for CLI version surfaces."""

    root = registry_root or PROJECT_ROOT / "registry" / "aeat"
    return CliVersionReport(
        package_name="aeat",
        package_version=__version__,
        registry=_build_registry_version_summary(root),
    )


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


__all__ = [
    "CliVersionReport",
    "RegistryVersionSummary",
    "build_cli_version_report",
    "render_cli_version_text",
]
