"""Preflight service: which schema fields a given modelo/revision needs.

:class:`ProfilePreflightService` inspects the schema's ``model_selectors``
against a :class:`UserProfileRecord` and returns a
:class:`ProfilePreflightReport` listing every required field that the
record does not yet carry.
"""

from __future__ import annotations

from ...domain.user_profile import ProfileSchemaDefinition, UserProfileRecord
from . import (
    ProfilePreflightReport,
    ProfilePreflightRequirement,
)


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
        filing_year: int,
        period: str,
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
            filing_year: Four-digit filing year.
            period: Period code (e.g. ``"1T"``, ``"1P"``).

        Returns:
            A :class:`ProfilePreflightReport` with ``ready=True`` when all
            required fields are present, or ``ready=False`` with the
            ``missing`` list populated.
        """
        present_paths = {fact.path for fact in record.facts}
        missing: list[ProfilePreflightRequirement] = []
        target = self._selector_prefix(modelo)
        for section in self._schema.sections:
            for field in section.fields:
                if not field.required:
                    continue
                if not self._selectors_match_modelo(field.model_selectors, target):
                    continue
                candidate_path = f"{section.key}.{field.key}"
                if candidate_path in present_paths:
                    continue
                missing.append(
                    ProfilePreflightRequirement(
                        selector=field.model_selectors[0] if field.model_selectors else candidate_path,
                        section_key=section.key,
                        field_key=field.key,
                    ),
                )
        return ProfilePreflightReport(
            profile_id=record.profile_id,
            modelo=modelo,
            revision_id=revision_id,
            filing_year=filing_year,
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


__all__ = ["ProfilePreflightService"]
