"""Schema-driven validation service for user-profile lifecycle commands.

:class:`ProfileValidationService` validates a :class:`UserProfileRecord`
against a loaded schema definition and returns structured
:class:`ProfileValidationIssue` entries for every constraint violation.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date

from ...core.errors import BaseSeverity
from ...core.parsing._dates import _parse_iso8601_date
from ...domain.user_profile import (
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    UserProfileFact,
    UserProfileRecord,
)
from . import (
    ProfileValidationIssue,
    ProfileValidationReport,
)
from ._completeness import conditional_profile_missing_required

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
"""The single accepted date layout: zero-padded ``YYYY-MM-DD``.

``datetime.date.fromisoformat`` alone would also accept the compact
basic form (``19780315``), which the rest of the profile stack does
not canonicalise back to a :class:`datetime.date`. Anchoring the
extended hyphenated layout keeps every persisted date fact in one
shape."""


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
        """Validate every fact on a profile against the schema.

        Args:
            record: The :class:`UserProfileRecord` whose facts are validated.

        Returns a :class:`ProfileValidationReport`.
        """
        return self._build_report(record.profile_id, record.facts)

    def validate_facts(self, profile_id: str, facts: Iterable[UserProfileFact]) -> ProfileValidationReport:
        """Validate a free-standing collection of facts.

        Returns a :class:`ProfileValidationReport`.
        """
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
        issues.extend(self._conditional_completeness_issues(facts))
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
        return (
            *self._validate_value_type(field, fact),
            *self._validate_effective_window(section, field, fact),
        )

    def _validate_value_type(
        self,
        field: ProfileFieldDefinition,
        fact: UserProfileFact,
    ) -> tuple[ProfileValidationIssue, ...]:
        """Reject a fact whose value does not satisfy its declared field type.

        Currently enforces :attr:`ProfileFieldType.DATE`: a date field
        must carry a real ISO-8601 calendar day in the zero-padded
        ``YYYY-MM-DD`` layout. A :class:`datetime.date` is already
        valid; a string is accepted only when it matches that layout
        and :meth:`datetime.date.fromisoformat` parses it — together
        that rejects a non-ISO layout (``15/03/1978``), the compact
        basic form (``19780315``), an impossible month or day
        (``1978-13-45``), a non-calendar day (``1978-02-30``), and
        plain garbage (``not-a-date``) without any hand-rolled
        calendar maths.
        """
        if field.type is not ProfileFieldType.DATE or fact.value is None:
            return ()
        if isinstance(fact.value, date):
            return ()
        if isinstance(fact.value, str) and _ISO_DATE_RE.match(fact.value):
            try:
                _parse_iso8601_date(fact.value)
            except ValueError:
                return (self._invalid_date_issue(field, fact),)
            return ()
        return (self._invalid_date_issue(field, fact),)

    @staticmethod
    def _invalid_date_issue(
        field: ProfileFieldDefinition,
        fact: UserProfileFact,
    ) -> ProfileValidationIssue:
        """Build the ERROR issue for a date field carrying a non-date value."""
        return ProfileValidationIssue(
            severity=BaseSeverity.ERROR,
            code="invalid_date_value",
            path=fact.path,
            message=(f"field {fact.path!r} must be a valid ISO-8601 calendar date (YYYY-MM-DD); got {fact.value!r}"),
        )

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
                        ),
                    )
        return tuple(issues)

    def _conditional_completeness_issues(
        self,
        facts: tuple[UserProfileFact, ...],
    ) -> tuple[ProfileValidationIssue, ...]:
        values = {fact.path: self._render_fact_value(fact.value) for fact in facts if fact.value is not None}
        return tuple(
            ProfileValidationIssue(
                severity=BaseSeverity.ERROR,
                code="conditional_required_field_missing",
                path=path,
                message=f"conditionally required field {path} is missing",
            )
            for path in conditional_profile_missing_required(values)
        )

    @staticmethod
    def _section_field_key(path: str) -> str:
        head, _, tail = path.partition(".")
        if not tail:
            return path
        if tail and "." in tail and tail.split(".", 1)[0].isdigit():
            tail = tail.split(".", 1)[1]
        return f"{head}.{tail.split('.', 1)[0]}"

    @staticmethod
    def _render_fact_value(value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)


__all__ = ["ProfileValidationService"]
