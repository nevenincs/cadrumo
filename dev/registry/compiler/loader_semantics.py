"""Public TOML-to-schema semantic conversions used by the registry loader."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.core.filing_projection_ref import compile_filing_projection_ref
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.export_semantics import ExportComputedKey, ExportDraftAttribute

from ._toml_helpers import as_toml_table


def _passthrough_toml_row(raw: object) -> dict[str, object]:
    """Carry a non-table TOML row through to schema validation unchanged."""
    # CAST-RATIONALE-TOML-ROW: raw TOML value, shape confirmed by the isinstance
    # guard in the same expression. The malformed row must reach model validation.
    # nosemgrep: no-cast-in-domain-application
    return dict(cast(Mapping[str, object], raw)) if isinstance(raw, Mapping) else {"value": raw}


def compile_export_semantic_field(source_path: Path, raw_field: object) -> dict[str, object]:
    """Construct closed export selector enums at the TOML compiler boundary."""
    field = as_toml_table(raw_field)
    if field is None:
        return _passthrough_toml_row(raw_field)
    if "header_key" in field:
        raise RegistryLoadError(
            f"{source_path}: legacy export field header_key is not accepted; use producer_key with a canonical "
            "FilingProducerKey identity",
        )
    payload = dict(field)
    for name, enum_type in (
        ("producer_key", FilingProducerKey),
        ("draft_attribute", ExportDraftAttribute),
        ("computed_key", ExportComputedKey),
    ):
        raw_value = payload.get(name)
        if raw_value is None or isinstance(raw_value, enum_type):
            continue
        if not isinstance(raw_value, str):
            raise RegistryLoadError(
                f"{source_path}: export field {name} must be a canonical string token, got "
                f"{type(raw_value).__name__!r}",
            )
        try:
            payload[name] = enum_type(raw_value)
        except ValueError as exc:
            raise RegistryLoadError(
                f"{source_path}: export field {name} {raw_value!r} is not a canonical {enum_type.__name__}",
            ) from exc
    raw_projection_ref = payload.get("projection_ref")
    if raw_projection_ref is not None:
        try:
            payload["projection_ref"] = compile_filing_projection_ref(raw_projection_ref)
        except (ValidationError, ValueError) as exc:
            raise RegistryLoadError(
                f"{source_path}: export field projection_ref is not a canonical FilingProjectionRef: {exc}",
            ) from exc
    return payload


def compile_projection_endpoint_declaration(source_path: Path, raw_declaration: object) -> dict[str, object]:
    """Hydrate one revision-owned projection declaration at the TOML boundary."""
    declaration = as_toml_table(raw_declaration)
    if declaration is None:
        return _passthrough_toml_row(raw_declaration)
    payload = dict(declaration)
    if "projection_ref" in payload:
        try:
            payload["projection_ref"] = compile_filing_projection_ref(payload["projection_ref"])
        except (ValidationError, ValueError) as exc:
            raise RegistryLoadError(f"{source_path}: {exc}") from exc
    return payload


__all__ = ["compile_export_semantic_field", "compile_projection_endpoint_declaration"]
