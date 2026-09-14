"""Application-owned profile-value builders for inward user-profile tests.

These helpers ask the application completeness and validation services what a
profile still needs.  They therefore belong beside the application tests;
real capsule publication and credential setup remain in persistence-adapter
test support.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from cadrumo.application.user_profile.completeness import conditional_profile_missing_required
from cadrumo.application.user_profile.validation import COMPLETENESS_ISSUE_CODES, ProfileValidationService
from cadrumo.domain.user_profile.tests.schema_value_support import schema_valid_placeholder
from cadrumo.domain.user_profile.values import UserProfileFact

if TYPE_CHECKING:
    from cadrumo.domain.user_profile.schema import ProfileSchemaDefinition


_COMPLETENESS_PROBE_PROFILE_ID = "00000000-0000-4000-8000-000000000000"


def complete_conditional_facts(
    schema: ProfileSchemaDefinition,
    facts: Iterable[UserProfileFact],
) -> tuple[UserProfileFact, ...]:
    """Append schema-required conditional facts until the set is complete."""
    completed = list(facts)
    fields = {f"{section.key}.{field.key}": field for section in schema.sections for field in section.fields}
    for _ in range(len(fields) + 1):
        values = {fact.path: fact.value for fact in completed if fact.value is not None}
        missing = tuple(path for path in conditional_profile_missing_required(values) if path in fields)
        if not missing:
            break
        completed.extend(UserProfileFact(path=path, value=schema_valid_placeholder(fields[path])) for path in missing)
    return tuple(completed)


def complete_profile_facts(
    schema: ProfileSchemaDefinition,
    facts: Iterable[UserProfileFact] = (),
) -> tuple[UserProfileFact, ...]:
    """Return ``facts`` extended until the application reports no required fields."""
    service = ProfileValidationService(schema=schema)
    completed = list(facts)
    fields = {f"{section.key}.{field.key}": field for section in schema.sections for field in section.fields}
    for _ in range(len(fields) + 1):
        report = service.validate_facts(_COMPLETENESS_PROBE_PROFILE_ID, completed)
        missing = tuple(
            issue.path for issue in report.issues if issue.code in COMPLETENESS_ISSUE_CODES and issue.path in fields
        )
        if not missing:
            return tuple(completed)
        completed.extend(UserProfileFact(path=path, value=schema_valid_placeholder(fields[path])) for path in missing)
    raise RuntimeError("profile completeness did not converge; a required field is unfillable")


__all__ = ["complete_conditional_facts", "complete_profile_facts"]
