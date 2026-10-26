"""Select canonical authority-owned periodic and annual export layouts."""

from __future__ import annotations

from pathlib import Path

from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.authority_store import AUTHORITY_DESCRIPTOR_FILENAME
from cadrumo.domain.calculations.registry.export import resolve_export_layout
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition

from .cli_contracts import RetencionesInstalledCliError
from .scenario import (
    InstalledAnnualCliSlice,
    InstalledPeriodicCliSlice,
)


def _selected_layouts(
    *, authority_root: Path, slices: tuple[InstalledPeriodicCliSlice, ...], year: int
) -> tuple[str, dict[str, ExportLayoutDefinition]]:
    """Load the same descriptor-selected layouts used by the installed CLI."""
    descriptor = authority_root.resolve(strict=True) / AUTHORITY_DESCRIPTOR_FILENAME
    if not descriptor.is_file():
        raise RetencionesInstalledCliError(stage="authority_preflight", diagnostic_code="authority_descriptor_missing")
    try:
        authority = IndexedRegistryAuthority(descriptor)
        with authority.operation() as operation:
            generation = operation.generation.logical_generation
            layouts = {
                slice_.slice_id: resolve_export_layout(
                    operation.snapshot(
                        slice_.modelo,
                        filing_year=year,
                        period=slice_.period,
                        revision_id=slice_.revision,
                    ),
                    slice_.layout_id,
                ).layout
                for slice_ in slices
            }
    except Exception as exc:
        raise RetencionesInstalledCliError(
            stage="authority_preflight",
            diagnostic_code=f"authority_layout_{type(exc).__name__}",
        ) from exc
    return generation, layouts


def _selected_annual_layouts(
    *, authority_root: Path, slices: tuple[InstalledAnnualCliSlice, ...], year: int
) -> tuple[str, dict[str, ExportLayoutDefinition]]:
    """Load the selected annual layouts through the same local authority descriptor."""
    descriptor = authority_root.resolve(strict=True) / AUTHORITY_DESCRIPTOR_FILENAME
    if not descriptor.is_file():
        raise RetencionesInstalledCliError(
            stage="annual_authority_preflight",
            diagnostic_code="authority_descriptor_missing",
        )
    try:
        authority = IndexedRegistryAuthority(descriptor)
        with authority.operation() as operation:
            generation = operation.generation.logical_generation
            layouts = {
                slice_.slice_id: resolve_export_layout(
                    operation.snapshot(
                        slice_.modelo,
                        filing_year=year,
                        period=slice_.period,
                        revision_id=slice_.revision,
                    ),
                    slice_.layout_id,
                ).layout
                for slice_ in slices
            }
    except Exception as exc:
        raise RetencionesInstalledCliError(
            stage="annual_authority_preflight",
            diagnostic_code=f"authority_layout_{type(exc).__name__}",
        ) from exc
    return generation, layouts
