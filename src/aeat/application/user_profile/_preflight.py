"""Preflight service: which schema fields a given modelo/revision needs.

:class:`ProfilePreflightService` inspects the schema's ``model_selectors``
against a :class:`UserProfileRecord` and returns a
:class:`ProfilePreflightReport` listing every required field that the
record does not yet carry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core import Period
from ...domain.calculations.registry import CasillaFieldKind
from ...domain.user_profile import ProfileSchemaDefinition, UserProfileRecord
from . import (
    ProfilePreflightReport,
    ProfilePreflightRequirement,
)
from ._completeness import conditional_profile_missing_required
from ._projections import record_to_path_values

if TYPE_CHECKING:
    from ...domain.calculations.registry import ModeloRevision

_LEGAL_ENTITY_TYPE = "legal_entity"
_PROFILE_ENTITY_TYPE_PATH = "taxpayer_type.entity_type"
_PROFILE_LEGAL_NAME_PATH = "identity.legal_name"
_PROFILE_NAME_PATH = "identity.name"
_PROFILE_SURNAMES_PATH = "identity.surnames"


class ProfilePreflightService:
    """Resolve required profile selectors for a given ``(modelo, revision, year, period)``.

    The service inspects the loaded schema's ``model_selectors`` and
    ``schedule_predicates`` declarations. Today every required field whose
    ``model_selectors`` reference the target modelo is considered required;
    revision-specific filtering will land alongside the registry-time
    selector inventory work.
    """

    def __init__(self, *, schema: ProfileSchemaDefinition) -> None:
        self._schema = schema

    def report(
        self,
        *,
        record: UserProfileRecord,
        modelo: str,
        revision_id: str,
        period: Period,
        revision: ModeloRevision | None = None,
    ) -> ProfilePreflightReport:
        """Compute missing required profile fields for the given filing context.

        Walks every section and field in the schema.  A field is considered
        required for this filing when ``field.required`` is true and at
        least one of its ``model_selectors`` has the prefix
        ``modelo_<modelo>``.  Facts already present on ``record`` are
        excluded from the missing list.

        Args:
            record: The caller's current :class:`UserProfileRecord`.
            modelo: Numeric modelo identifier (e.g. ``"303"``).
            revision_id: Revision tag from the registry (e.g. ``"2024-0A"``).
            period: Typed filing period.
            revision: Optional :class:`ModeloRevision` whose export layouts
                contribute filing-grade declarant identity requirements.

        Returns:
            A :class:`ProfilePreflightReport` with ``ready=True`` when all
            required fields are present, or ``ready=False`` with the
            ``missing`` list populated.
        """
        values = record_to_path_values(record)
        missing: list[ProfilePreflightRequirement] = []
        target = self._selector_prefix(modelo)
        for section in self._schema.sections:
            for field in section.fields:
                if not field.required:
                    continue
                if not self._selectors_match_modelo(field.model_selectors, target):
                    continue
                candidate_path = f"{section.key}.{field.key}"
                if self._has_value(values, candidate_path):
                    continue
                missing.append(
                    ProfilePreflightRequirement(
                        selector=field.model_selectors[0] if field.model_selectors else candidate_path,
                        section_key=section.key,
                        field_key=field.key,
                    ),
                )
        missing.extend(self._missing_export_identity_requirements(values, revision))
        missing.extend(self._missing_conditional_profile_requirements(values, missing))
        return ProfilePreflightReport(
            profile_id=record.profile_id,
            modelo=modelo,
            revision_id=revision_id,
            filing_year=period.filing_year,
            period=period,
            missing=tuple(missing),
            ready=not missing,
        )

    @staticmethod
    def _selector_prefix(modelo: str) -> str:
        return f"modelo_{modelo.strip()}"

    @staticmethod
    def _selectors_match_modelo(selectors: tuple[str, ...], target_prefix: str) -> bool:
        if not selectors:
            return False
        return any(selector.startswith(target_prefix) for selector in selectors)

    @staticmethod
    def _has_value(values: dict[str, str], path: str) -> bool:
        return bool((values.get(path) or "").strip())

    def _missing_export_identity_requirements(
        self,
        values: dict[str, str],
        revision: ModeloRevision | None,
    ) -> list[ProfilePreflightRequirement]:
        if revision is None:
            return []
        required_headers = {
            field.header_key.lower()
            for layout in revision.export_layouts
            for record in layout.records
            for field in record.fields
            if field.kind is CasillaFieldKind.HEADER and field.required and field.header_key is not None
        }
        legal_name_headers = {"full_name", "legal_name", "name", "first_name", "surnames"}
        if required_headers.isdisjoint(legal_name_headers):
            return []
        if (values.get(_PROFILE_ENTITY_TYPE_PATH) or "").strip() == _LEGAL_ENTITY_TYPE:
            if self._has_value(values, _PROFILE_LEGAL_NAME_PATH):
                return []
            return [
                ProfilePreflightRequirement(
                    selector="export.header.legal_name",
                    section_key="identity",
                    field_key="legal_name",
                ),
            ]
        # Natural-person export service composes declarant identity as the complete
        # name pair, so any required legal-name header makes both facts required
        # before filing-grade work starts.
        required_identity_fields = {"name", "surnames"}
        missing: list[ProfilePreflightRequirement] = []
        for section in self._schema.sections:
            if section.key != "identity":
                continue
            for field in section.fields:
                if field.key not in required_identity_fields:
                    continue
                candidate_path = f"{section.key}.{field.key}"
                if self._has_value(values, candidate_path):
                    continue
                missing.append(
                    ProfilePreflightRequirement(
                        selector="export.header.full_name",
                        section_key=section.key,
                        field_key=field.key,
                    ),
                )
        return missing

    def _missing_conditional_profile_requirements(
        self,
        values: dict[str, str],
        existing: list[ProfilePreflightRequirement],
    ) -> list[ProfilePreflightRequirement]:
        already_missing = {(item.section_key, item.field_key) for item in existing}
        missing: list[ProfilePreflightRequirement] = []
        for path in conditional_profile_missing_required(values):
            section_key, field_key = self._split_path(path)
            if (section_key, field_key) in already_missing:
                continue
            missing.append(
                ProfilePreflightRequirement(
                    selector=self._selector_for_path(path),
                    section_key=section_key,
                    field_key=field_key,
                ),
            )
        return missing

    def _selector_for_path(self, path: str) -> str:
        section_key, field_key = self._split_path(path)
        for section in self._schema.sections:
            if section.key != section_key:
                continue
            for field in section.fields:
                if field.key == field_key:
                    return field.model_selectors[0] if field.model_selectors else path
        return path

    @staticmethod
    def _split_path(path: str) -> tuple[str, str]:
        section_key, _, field_key = path.partition(".")
        return section_key, field_key


__all__ = ["ProfilePreflightService"]
