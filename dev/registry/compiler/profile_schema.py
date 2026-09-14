"""Strict development parsing for captured user-profile schema bytes."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.user_profile.schema import ProfileSchemaDefinition

_ENVELOPE_MEMBERS = frozenset({"schema", "sections", "derived_selectors"})


def parse_captured_profile_schema(
    payload: bytes,
    *,
    source_path: Path,
    legal_reference_ids: frozenset[str] | None = None,
) -> ProfileSchemaDefinition:
    """Parse one exact captured TOML payload without consulting ambient files."""
    try:
        document = tomllib.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise RegistryValidationError(f"profile schema source {source_path} is not valid UTF-8 TOML") from exc
    unexpected = sorted(set(document) - _ENVELOPE_MEMBERS)
    missing = sorted({"schema", "sections"} - set(document))
    if unexpected or missing:
        raise RegistryValidationError(
            f"profile schema source {source_path} has invalid envelope; unexpected={unexpected!r}, missing={missing!r}"
        )
    schema = document["schema"]
    sections = document["sections"]
    derived = document.get("derived_selectors", [])
    if not isinstance(schema, Mapping) or not isinstance(sections, list) or not sections:
        raise RegistryValidationError(f"profile schema source {source_path} has invalid schema or sections members")
    if not isinstance(derived, list):
        raise RegistryValidationError(f"profile schema source {source_path} has invalid derived_selectors member")
    try:
        parsed = ProfileSchemaDefinition.model_validate(
            {**schema, "sections": sections, "derived_selectors": derived},
            strict=False,
        )
    except ValidationError as exc:
        raise RegistryValidationError(
            f"profile schema source {source_path} failed typed validation with {len(exc.errors())} violations"
        ) from exc
    if legal_reference_ids is not None:
        _validate_declared_legal_references(parsed, legal_reference_ids)
    return parsed


def capture_profile_schema(
    path: Path,
    *,
    legal_reference_ids: frozenset[str] | None = None,
) -> tuple[bytes, ProfileSchemaDefinition]:
    """Read a required source once and parse only the captured bytes."""
    try:
        resolved = path.resolve(strict=True)
        payload = resolved.read_bytes()
    except OSError as exc:
        raise RegistryValidationError(f"profile schema source is unavailable at {path}") from exc
    return payload, parse_captured_profile_schema(
        payload,
        source_path=resolved,
        legal_reference_ids=legal_reference_ids,
    )


def _validate_declared_legal_references(
    schema: ProfileSchemaDefinition,
    legal_reference_ids: frozenset[str],
) -> None:
    declared = {reference for section in schema.sections for field in section.fields for reference in field.legal_refs}
    declared.update(reference for selector in schema.derived_selectors for reference in selector.legal_refs)
    unknown = sorted(declared - legal_reference_ids)
    if unknown:
        raise RegistryValidationError(f"profile schema declares unknown legal references {unknown!r}")
