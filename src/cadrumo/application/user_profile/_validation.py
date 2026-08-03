"""Schema-driven validation service for user-profile lifecycle commands.

:class:`ProfileValidationService` validates a :class:`UserProfileRecord`
against a loaded schema definition and returns structured
:class:`ProfileValidationIssue` entries for every constraint violation.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from typing import Final

from ...core.errors import BaseSeverity
from ...core.parsing import parse_iso8601_date as _parse_iso8601_date
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
from ._completeness import (
    IVA_REGIME_PATH,
    conditional_profile_missing_required,
    iva_regime_required,
    missing_required_field_paths,
)
from ._projections import in_window_order

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
"""The single accepted date layout: zero-padded ``YYYY-MM-DD``.

``datetime.date.fromisoformat`` alone would also accept the compact
basic form (``19780315``), which the rest of the profile stack does
not canonicalise back to a :class:`datetime.date`. Anchoring the
extended hyphenated layout keeps every persisted date fact in one
shape."""

REQUIRED_FIELD_MISSING_CODE: Final[str] = "required_field_missing"
"""Issue code for a schema-required field absent from the fact set."""

CONDITIONAL_REQUIRED_FIELD_MISSING_CODE: Final[str] = "conditional_required_field_missing"
"""Issue code for a field required only under some other fact's value."""

COMPLETENESS_ISSUE_CODES: Final[frozenset[str]] = frozenset(
    {REQUIRED_FIELD_MISSING_CODE, CONDITIONAL_REQUIRED_FIELD_MISSING_CODE},
)
"""The issue codes that mean "not finished yet" rather than "malformed".

A profile born ``SETUP_INCOMPLETE`` defers exactly these; every other
blocking issue (bad shape, bad value, unknown path) still refuses at
registration. The lifecycle service re-applies them in full at the ACTIVE
promotion — see
:meth:`~cadrumo.application.user_profile.ProfileLifecycleService.complete_setup`.
"""


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
        issues.extend(self._unenforced_expiry_issues(facts))
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

        Enforces :attr:`ProfileFieldType.DATE`: a date field must carry a
        real ISO-8601 calendar day in the zero-padded ``YYYY-MM-DD``
        layout. A :class:`datetime.date` is already valid; a string is
        accepted only when it matches that layout and
        :meth:`datetime.date.fromisoformat` parses it — together that
        rejects a non-ISO layout (``15/03/1978``), the compact basic form
        (``19780315``), an impossible month or day (``1978-13-45``), a
        non-calendar day (``1978-02-30``), and plain garbage
        (``not-a-date``) without any hand-rolled calendar maths.

        Enforces :attr:`ProfileFieldType.ENUM` against the field's own
        declared ``enum_values``. Those declarations were previously
        advisory: an enum field accepted any token at all and stored it
        unchanged, so a closed set that every reader treated as
        authoritative constrained nothing, and a value carrying the wrong
        vocabulary could sit in a profile indefinitely without any check
        able to fail.

        The schema arrives here by injection, so a caller validating
        against a synthetic schema is checked against ITS declarations
        rather than the shipped ones — which is why enum enforcement
        belongs at this boundary and not on the fact carrier.
        """
        if fact.value is None:
            return ()
        if field.type is ProfileFieldType.ENUM:
            return self._validate_enum_value(field, fact)
        if field.type is not ProfileFieldType.DATE:
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
    def _validate_enum_value(
        field: ProfileFieldDefinition,
        fact: UserProfileFact,
    ) -> tuple[ProfileValidationIssue, ...]:
        """Reject an enum-typed value outside the field's declared set.

        Comparison is exact rather than case-folded. The declared sets are
        case-significant and inconsistent between fields by design — some
        carry AEAT's own uppercase tokens, others the profile's lowercase
        vocabulary — so folding would silently admit a spelling the
        declaring authority does not use.
        """
        if str(fact.value) in field.enum_values:
            return ()
        return (
            ProfileValidationIssue(
                severity=BaseSeverity.ERROR,
                code="invalid_enum_value",
                path=fact.path,
                message=(f"field {fact.path!r} must be one of {list(field.enum_values)}; got {fact.value!r}"),
            ),
        )

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

    @staticmethod
    def _unenforced_expiry_issues(
        facts: tuple[UserProfileFact, ...],
    ) -> tuple[ProfileValidationIssue, ...]:
        """Report a ``valid_to`` that ends nothing, because no reader consults it.

        The effective-window resolvers order on ``valid_from`` and take the
        last fact per path; ``valid_to`` is not consulted, since honouring
        expiry needs an ``as_of`` the caller supplies rather than the clock.
        An operator who records an end date is therefore describing a state
        the profile does not enter.

        The warning is scoped to the case where that is true. A closed
        window on a fact some LATER fact supersedes is accurate
        bookkeeping - the later ``valid_from`` already ends it, and warning
        there would report correct records as suspect. Only the effective
        fact's own ``valid_to`` is inert, because nothing after it takes
        over, so the path keeps projecting past the date the operator gave.

        Selection reuses the projection's own ordering rather than
        restating it. A second copy of the rule could drift from the one
        the readers use, and this check is only meaningful while it names
        exactly the fact they resolve to.

        Args:
            facts: Every fact on the record, in declaration order.

        Returns:
            One WARNING per path whose effective fact carries a ``valid_to``.
        """
        effective: dict[str, UserProfileFact] = {}
        for fact in in_window_order(facts):
            effective[fact.path] = fact
        return tuple(
            ProfileValidationIssue(
                severity=BaseSeverity.WARNING,
                code="effective_window_end_not_enforced",
                path=path,
                message=(
                    f"path {path!r} declares valid_to {fact.valid_to.isoformat()!r} but the value "
                    f"keeps resolving after it; record a later valid_from at {path!r} to supersede it"
                ),
            )
            for path, fact in effective.items()
            if fact.valid_to is not None
        )

    def _required_field_issues(
        self,
        facts: tuple[UserProfileFact, ...],
    ) -> tuple[ProfileValidationIssue, ...]:
        # Presence is VALUE-bearing, never fact-bearing. A cleared field is a
        # fact carrying ``value=None``, so keying on the fact existing let a
        # clear not merely evade this check but affirmatively SATISFY it:
        # clearing a required field silenced the very issue its absence
        # raises. The overview built from the same record already reads
        # presence this way, so the enforcing surface now agrees with the one
        # the operator is shown.
        # Repeatable sections were skipped wholesale here, so 13 of the 15
        # fields the schema declares required were never reached and the
        # declaration bound nothing. Removing that skip alone would have been
        # wrong in BOTH directions at once, because the presence set drops the
        # row index: an empty section would raise (demanding every taxpayer
        # hold an attribution entity) while a second, incomplete row would
        # pass. The shared row-aware helper is what makes "required" mean
        # per-row, and the overview reads the same one so the enforcing
        # surface and the displayed one cannot drift apart again.
        values = {fact.path: self._render_fact_value(fact.value) for fact in facts if fact.value is not None}
        return tuple(
            ProfileValidationIssue(
                severity=BaseSeverity.ERROR,
                code=REQUIRED_FIELD_MISSING_CODE,
                path=path,
                message=f"required field {path} is missing",
            )
            for path in missing_required_field_paths(self._schema, values)
            if not (path == IVA_REGIME_PATH and not iva_regime_required(values))
        )

    def _conditional_completeness_issues(
        self,
        facts: tuple[UserProfileFact, ...],
    ) -> tuple[ProfileValidationIssue, ...]:
        values = {fact.path: self._render_fact_value(fact.value) for fact in facts if fact.value is not None}
        return tuple(
            ProfileValidationIssue(
                severity=BaseSeverity.ERROR,
                code=CONDITIONAL_REQUIRED_FIELD_MISSING_CODE,
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


__all__ = [
    "COMPLETENESS_ISSUE_CODES",
    "CONDITIONAL_REQUIRED_FIELD_MISSING_CODE",
    "REQUIRED_FIELD_MISSING_CODE",
    "ProfileValidationService",
]
