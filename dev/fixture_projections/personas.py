"""The persona catalogue check that runs before any producer is trusted.

Every persona is read through the catalogue reader, ``cadrumo.tests.personas``,
under the published authority's supported filing-year envelope, so the check
holds each persona to the contract every consumer reads it by: the catalogue
format, identity roles, ledger rows and year tokens. Its wizard answers then go
through the profile patch judge the materialiser submits them to, so an unknown
question id or a value the wizard refuses is found here, and its schema fields
and activity columns are looked up in the pinned profile schema.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Final

from cadrumo.application.user_profile.section_rows import section_row_facts
from cadrumo.application.wizard.catalogue import build_setup_flow
from cadrumo.application.wizard.patch_edit import validate_profile_patch
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.user_profile.values import ProfileSetupState
from cadrumo.entrypoints.tests.persona_materialisation import (
    PersonaMaterialisationError,
    patch_answers,
    year_envelope,
)
from cadrumo.tests.personas import (
    IdentityCatalogue,
    Persona,
    PersonaCatalogueError,
    YearEnvelope,
    parse_identity_catalogue,
    parse_persona,
)

IDENTITIES_FILE: Final[str] = "identities.toml"
ACTIVITY_SECTION: Final[str] = "activities"


def _toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _read(directory: Path, identities: IdentityCatalogue, envelope: YearEnvelope) -> Persona:
    return parse_persona(
        directory.name,
        persona_document=_toml(directory / "persona.toml"),
        ledger_text=(directory / "ledger.csv").read_text(encoding="utf-8"),
        documents_document=_toml(directory / "documents.toml"),
        expectations_document=_toml(directory / "expectations.toml"),
        catalogue=identities,
        envelope=envelope,
    )


def _profile_findings(persona: Persona, envelope: YearEnvelope, operation: PinnedAuthorityOperation) -> list[str]:
    findings: list[str] = []
    try:
        validate_profile_patch(
            flow=build_setup_flow(operation),
            current_values={},
            setup_state=ProfileSetupState.INCOMPLETE,
            supplied=dict(patch_answers(persona, envelope)),
            colegio_concertado=None,
            operation=operation,
        )
    except (CadrumoError, PersonaMaterialisationError, ValueError) as exc:
        findings.append(f"{persona.id}: the wizard refuses its answers: {exc}")
    schema = operation.profile_decode_context().schema
    known_paths = set(schema.field_paths)
    findings.extend(
        f"{persona.id}: [fields] names {field.path!r}, which the profile schema does not declare"
        for field in persona.fields
        if field.path not in known_paths
    )
    section = schema.section(ACTIVITY_SECTION)
    columns = {field.key for field in section.fields}
    for index, activity in enumerate(persona.activities):
        unknown = sorted(key for key, _ in activity.values if key not in columns)
        if unknown:
            findings.append(f"{persona.id}: activities[{index}] names unknown columns {unknown}")
            continue
        try:
            section_row_facts(section, row_index=index, values=dict(activity.values))
        except (CadrumoError, ValueError) as exc:
            findings.append(f"{persona.id}: activities[{index}] is refused: {exc}")
    return findings


def persona_findings(catalogue: Path, operation: PinnedAuthorityOperation) -> tuple[str, ...]:
    """Every reason a persona under ``catalogue`` departs from the contract, read under ``operation``."""
    if not catalogue.is_dir():
        return (f"no persona catalogue at {catalogue}",)
    try:
        identities = parse_identity_catalogue(_toml(catalogue / IDENTITIES_FILE))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, PersonaCatalogueError) as exc:
        return (f"{IDENTITIES_FILE}: {exc}",)
    envelope = year_envelope(operation)
    directories = sorted(path for path in catalogue.iterdir() if path.is_dir())
    if not directories:
        return ("no personas",)
    findings: list[str] = []
    for directory in directories:
        try:
            persona = _read(directory, identities, envelope)
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, PersonaCatalogueError) as exc:
            findings.append(f"{directory.name}: {exc}")
            continue
        findings.extend(_profile_findings(persona, envelope, operation))
    return tuple(findings)


def persona_catalogue_findings(catalogue: Path) -> tuple[str, ...]:
    """Every reason the catalogue at ``catalogue`` cannot be read, under the published authority."""
    with bundled_indexed_authority().operation() as operation:
        return persona_findings(catalogue, operation)
