"""Schema-driven validation service for user-profile lifecycle commands."""

from __future__ import annotations

from ...core.errors import BaseSeverity
from collections.abc import Iterable

from ...domain.user_profile import (
    ProfileFieldDefinition,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    UserProfileFact,
    UserProfileRecord,
)
from . import (
    ProfileValidationIssue,
    ProfileValidationReport,
)


class ProfileValidationService:
    """Validate a profile record against a loaded schema.

    Stateless. Constructed with a loaded :class:`ProfileSchemaDefinition`
    so the same instance can validate many records or commands.
    """

    def __init__(self, *, schema: ProfileSchemaDefinition) -> None:
        self._schema = schema
        self._field_index: dict[str, tuple[ProfileSectionDefinition, ProfileFieldDefinition]] = {}
        for section in schema.sections:
            for field in section.fields:
                self._field_index[f"{section.key}.{field.key}"] = (section, field)

    @property
    def schema(self) -> ProfileSchemaDefinition:
        return self._schema

    def validate_record(self, record: UserProfileRecord) -> ProfileValidationReport:
        """Validate every fact on a profile against the schema."""

        return self._build_report(record.profile_id, record.facts)

    def validate_facts(self, profile_id: str, facts: Iterable[UserProfileFact]) -> ProfileValidationReport:
        """Validate a free-standing collection of facts (e.g. a registration command)."""

        return self._build_report(profile_id, tuple(facts))

    def _build_report(
        self,
        profile_id: str,
        facts: tuple[UserProfileFact, ...],
    ) -> ProfileValidationReport:
        issues: list[ProfileValidationIssue] = []
        for fact in facts:
            issues.extend(self._validate_one_fact(fact))
        issues.extend(self._required_field_issues(facts))
        return ProfileValidationReport(
            profile_id=profile_id,
            schema_version=self._schema.version,
            issues=tuple(issues),
        )

    def _validate_one_fact(self, fact: UserProfileFact) -> tuple[ProfileValidationIssue, ...]:
        binding = self._field_index.get(self._section_field_key(fact.path))
        if binding is None:
            return (
                ProfileValidationIssue(
                    severity=BaseSeverity.ERROR,
                    code="unknown_field",
                    path=fact.path,
                    message=f"path {fact.path!r} does not match any schema field",
                ),
            )
        section, field = binding
        section_or_field_issue = self._validate_effective_window(section, field, fact)
        return section_or_field_issue

    def _validate_effective_window(
        self,
        section: ProfileSectionDefinition,
        field: ProfileFieldDefinition,
        fact: UserProfileFact,
    ) -> tuple[ProfileValidationIssue, ...]:
        if (fact.valid_from is not None or fact.valid_to is not None) and not (
            section.effective_dated or field.effective_dated
        ):
            return (
                ProfileValidationIssue(
                    severity=BaseSeverity.WARNING,
                    code="effective_window_unused",
                    path=fact.path,
                    message=(
                        f"path {fact.path!r} carries an effective window but neither "
                        f"section {section.key!r} nor field {field.key!r} is effective-dated"
                    ),
                ),
            )
        return ()

    def _required_field_issues(
        self,
        facts: tuple[UserProfileFact, ...],
    ) -> tuple[ProfileValidationIssue, ...]:
        present = {self._section_field_key(fact.path) for fact in facts}
        issues: list[ProfileValidationIssue] = []
        for section in self._schema.sections:
            if section.repeatable:
                continue
            for field in section.fields:
                if not field.required:
                    continue
                if f"{section.key}.{field.key}" not in present:
                    issues.append(
                        ProfileValidationIssue(
                            severity=BaseSeverity.ERROR,
                            code="required_field_missing",
                            path=f"{section.key}.{field.key}",
                            message=f"required field {section.key}.{field.key} is missing",
                        )
                    )
        return tuple(issues)

    @staticmethod
    def _section_field_key(path: str) -> str:
        head, _, tail = path.partition(".")
        if not tail:
            return path
        if tail and "." in tail and tail.split(".", 1)[0].isdigit():
            tail = tail.split(".", 1)[1]
        return f"{head}.{tail.split('.', 1)[0]}"


__all__ = ["ProfileValidationService"]