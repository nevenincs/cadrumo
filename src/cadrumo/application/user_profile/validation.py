"""Schema-driven validation service for user-profile lifecycle commands.

:class:`ProfileValidationService` validates a :class:`UserProfileRecord`
against a loaded schema definition and returns structured
:class:`ProfileValidationIssue` entries for every constraint violation.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from ...core.errors import BaseSeverity
from ...domain.user_profile.schema import (
    ProfileFieldDefinition,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    ProfileValueRefusalKind,
    derived_selector_for_path,
    profile_value_refusal,
)
from ...domain.user_profile.values import UserProfileFact, UserProfileRecord, section_field_key
from .commands import (
    ProfileValidationIssue,
    ProfileValidationReport,
)
from .completeness import (
    IVA_REGIME_PATH,
    atribucion_socio_forbidden_country_paths,
    atribucion_socio_missing_country_paths,
    conditional_profile_missing_required,
    iva_regime_required,
    missing_required_field_paths,
)
from .projections import in_window_order

REQUIRED_FIELD_MISSING_CODE: Final[str] = "required_field_missing"
"""Issue code for a schema-required field absent from the fact set."""

CONDITIONAL_REQUIRED_FIELD_MISSING_CODE: Final[str] = "conditional_required_field_missing"
"""Issue code for a field required only under some other fact's value."""

CONDITIONALLY_FORBIDDEN_FIELD_CODE: Final[str] = "conditionally_forbidden_field"
"""Issue code for a field carrying a value some other fact's value prohibits.

The mirror of the code above, and deliberately NOT a completeness code. A
missing conditional field is an unfinished profile and may be deferred to the
ACTIVE promotion; a field the record layout forbids is a value that must never
reach an export, so it refuses at registration like any other malformed value.

The distinction is the whole reason this is its own code. Reporting a
prohibited value as a missing one would send the operator to supply MORE of
exactly the thing the form does not allow.
"""

NUMERIC_VALUE_ISSUE_CODE: Final[str] = "numeric_field_invalid"
"""Issue code for a numeric field carrying a non-number or an out-of-range value.

Deliberately NOT a completeness code: a malformed or out-of-range value is a
bad answer rather than a missing one, so it refuses even while a profile is
still ``SETUP_INCOMPLETE``, exactly as a bad date or an unknown enum token
already does. Deferring it would let a wrong number sit in a profile until
the ACTIVE promotion and then refuse the promotion instead of the write that
caused it.
"""

BOOLEAN_VALUE_ISSUE_CODE: Final[str] = "boolean_field_invalid"
"""Issue code for a boolean field carrying something that is not a yes/no answer.

Not a completeness code, for the same reason as its numeric sibling: an
unreadable answer is a bad one rather than a missing one. A blank is refused
here rather than deferred, because a boolean field's readers resolve an
unreadable value to ``False`` -- so a value admitted unread does not stay
undecided, it silently becomes "no".
"""

ENUM_VALUE_ISSUE_CODE: Final[str] = "invalid_enum_value"
"""Issue code for an enum field carrying a token outside its declared set."""

DATE_VALUE_ISSUE_CODE: Final[str] = "invalid_date_value"
"""Issue code for a date field carrying something that is not a calendar day."""

EMAIL_VALUE_ISSUE_CODE: Final[str] = "invalid_email_value"
"""Issue code for an email field carrying something that is not an address.

Not a completeness code, for the same reason as its siblings: an entry that
is not an address is a bad answer rather than a missing one. The declaration
was previously the only content-format type in the schema that nothing
checked, so ``banana`` stored and stayed.
"""

DERIVED_FIELD_ISSUE_CODE: Final[str] = "derived_field_not_editable"
"""Issue code for a write aimed at a path the engine computes.

Path legitimacy, not value admissibility, which is why it is judged here beside
``unknown_field`` rather than through the value-refusal authority. That is now
the only thing keeping the rule answerable: the schema declares the derived
namespaces as ``[[derived_selectors]]`` patterns and nothing else, so the
field index does NOT hold them and there is no declaration left to judge
against.

Evaluated BEFORE the ``unknown_field`` refusal, and that ordering is what makes
the refusal instructive rather than merely correct. Both codes would block the
write, but only this one names the entry surface that edits the source facts;
reaching ``unknown_field`` first would tell an operator the engine's own path
does not exist.
"""

UNKNOWN_FIELD_ISSUE_CODE: Final[str] = "unknown_field"
"""Issue code for a write aimed at a path the schema does not declare."""

_ISSUE_CODE_BY_REFUSAL_KIND: Final[dict[ProfileValueRefusalKind, str]] = {
    ProfileValueRefusalKind.ENUM: ENUM_VALUE_ISSUE_CODE,
    ProfileValueRefusalKind.DATE: DATE_VALUE_ISSUE_CODE,
    ProfileValueRefusalKind.NUMERIC: NUMERIC_VALUE_ISSUE_CODE,
    ProfileValueRefusalKind.BOOLEAN: BOOLEAN_VALUE_ISSUE_CODE,
    ProfileValueRefusalKind.EMAIL: EMAIL_VALUE_ISSUE_CODE,
}
"""How a refusal kind is reported as an issue.

Exhaustive over :class:`ProfileValueRefusalKind` by construction, and pinned
as such by a test: a new kind added to the domain rule with no entry here
would otherwise raise a :exc:`KeyError` at the moment a taxpayer's value
tripped it, turning a refusal that should have been reported into a crash.
"""

COMPLETENESS_ISSUE_CODES: Final[frozenset[str]] = frozenset(
    {REQUIRED_FIELD_MISSING_CODE, CONDITIONAL_REQUIRED_FIELD_MISSING_CODE},
)
"""The issue codes that mean "not finished yet" rather than "malformed".

A profile born ``SETUP_INCOMPLETE`` defers exactly these; every other
blocking issue (bad shape, bad value, unknown path) still refuses at
registration. They come due in full at the promotion out of setup — see
:meth:`~cadrumo.application.user_profile.ProfileRecordRepository.complete_setup`,
which judges with ``require_complete=True`` precisely because COMPLETE is the
claim that nothing required is missing.
"""


class ProfileValidationService:
    """Validate a profile record against a loaded schema.

    Stateless. Constructed with a loaded :class:`ProfileSchemaDefinition`
    so the same instance can validate many records or commands.
    """

    def __init__(self, *, schema: ProfileSchemaDefinition) -> None:
        """Bind the validator to a loaded schema and index its section fields."""
        self._schema = schema
        self._field_index: dict[str, tuple[ProfileSectionDefinition, ProfileFieldDefinition]] = {}
        for section in schema.sections:
            for field in section.fields:
                self._field_index[f"{section.key}.{field.key}"] = (section, field)

    @property
    def schema(self) -> ProfileSchemaDefinition:
        """Return the loaded schema this validator was constructed with."""
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
        issues.extend(self._atribucion_socio_country_issues(facts))
        issues.extend(self._unenforced_expiry_issues(facts))
        return ProfileValidationReport(
            profile_id=profile_id,
            schema_version=self._schema.version,
            issues=tuple(issues),
        )

    def _validate_one_fact(self, fact: UserProfileFact) -> tuple[ProfileValidationIssue, ...]:
        """Judge one fact's path and value, or admit it.

        A CLEAR is admissible at EVERY path, declared or not, and that is the
        load-bearing remedy for both path rules rather than a softening of
        either. This service judges the whole MERGED fact set on every edit
        rather than the incoming change, so a fact the schema no longer accepts
        is re-judged on every later edit to every other field. Were the clear
        refused too, that fact could not be removed by any door: the profile
        could not be edited, cleared or promoted through the lifecycle API at
        all, with no in-band remedy.

        Two rules produce such a fact and the generalisation covers both,
        because the trap is the same shape.

        A DERIVED path was measured in that state, not reasoned about. The
        exemption was once written as a ``value is not None`` guard on the
        derived branch alone, which stopped working the moment the per-year
        field declarations were removed: the clear fell through to a field
        lookup that now misses, and was refused as ``unknown_field`` -- an
        ERROR outside :data:`COMPLETENESS_ISSUE_CODES`, so blocking in both
        ``require_complete`` modes.

        A RETIRED path reaches the same place with no rule needed to put it
        there. Retired declarations are deleted here rather than tolerated, so
        the first field removal against a live profile still holding a fact at
        that path bricks it.

        Admitting the clear gives nothing back to either rule. Both exist to
        stop a value being WRITTEN and a clear writes none: the injectors
        compute always and overwrite whatever the fact index holds, and every
        projection drops a ``None``-valued fact before a reader sees it, so a
        cleared fact is inert wherever it sits. What it costs is refusing a
        clear aimed at a path that does not exist -- and that refusal could
        never name the right fact anyway, because this door judges the merged
        set and cannot tell an operator's typo from a fact already stored.

        The effective-window check still runs on a clear where a declaration
        exists to run it against: a window recorded on a cleared fact is as
        inert as one recorded on a valued fact, and the operator is owed the
        same warning either way.
        """
        binding = self._field_index.get(section_field_key(fact.path))
        if fact.value is None:
            if binding is None:
                return ()
            cleared_section, cleared_field = binding
            return self._validate_effective_window(cleared_section, cleared_field, fact)
        derived = derived_selector_for_path(fact.path, self._schema.derived_selectors)
        if derived is not None:
            return (
                ProfileValidationIssue(
                    severity=BaseSeverity.ERROR,
                    code=DERIVED_FIELD_ISSUE_CODE,
                    path=fact.path,
                    message=(
                        f"path {fact.path!r} is computed by the engine and cannot be written; "
                        f"edit the facts it derives from with {derived.entry_surface!r}"
                    ),
                ),
            )
        if binding is None:
            return (
                ProfileValidationIssue(
                    severity=BaseSeverity.ERROR,
                    code=UNKNOWN_FIELD_ISSUE_CODE,
                    path=fact.path,
                    message=f"path {fact.path!r} does not match any schema field",
                ),
            )
        section, field = binding
        return (
            *self._validate_value_type(field, fact),
            *self._validate_effective_window(section, field, fact),
        )

    @staticmethod
    def _validate_value_type(
        field: ProfileFieldDefinition,
        fact: UserProfileFact,
    ) -> tuple[ProfileValidationIssue, ...]:
        """Reject a fact whose value does not satisfy its declared field type.

        The verdict comes from
        :func:`~cadrumo.domain.user_profile.schema.profile_value_refusal` rather
        than being formed here, so this door admits a value under exactly the
        rule the readers judge it by and the rule an operator surface refuses
        it by. The per-type rules -- enum token, numeric range, yes/no
        readability, ISO calendar day, address shape -- used to be split between that domain
        authority and this method, which is how a screen wanting to refuse a
        bad date where it was typed had nothing to ask and would have had to
        restate the layout itself.

        What stays here is the ISSUE VOCABULARY: a refusal kind is turned
        into the code an issue report carries. That is this layer's, because
        the codes are the report's contract rather than a property of the
        value.

        The schema arrives by injection, so a caller validating against a
        synthetic schema is checked against ITS declarations rather than the
        shipped ones -- which is why the declaration, not the fact carrier,
        is what enforcement reads.
        """
        refusal = profile_value_refusal(field, fact.value)
        if refusal is None:
            return ()
        return (
            ProfileValidationIssue(
                severity=BaseSeverity.ERROR,
                code=_ISSUE_CODE_BY_REFUSAL_KIND[refusal.kind],
                path=fact.path,
                message=refusal.message,
            ),
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

    def _atribucion_socio_country_issues(
        self,
        facts: tuple[UserProfileFact, ...],
    ) -> tuple[ProfileValidationIssue, ...]:
        """Enforce the Modelo 184 clave/country coupling, in both directions.

        Positions 79-80 of the declarado record carry the socio's country only
        under clave 2; claves 1 and 3 require BLANCOS. So the country is owed
        on one clave and PROHIBITED on the other two, and a rule enforcing only
        the first half would leave the prohibited case to whatever was typed --
        which is how a Spanish default came to write a value the layout forbids
        on the majority case.

        Enforced here, at the door, rather than left to a reader. A conditional
        that two surfaces could apply and neither does is the shape that
        produced the double-defaulted country elsewhere in this tree: a green
        suite is then consistent with nothing being enforced at all.
        """
        values = {fact.path: self._render_fact_value(fact.value) for fact in facts if fact.value is not None}
        return (
            *(
                ProfileValidationIssue(
                    severity=BaseSeverity.ERROR,
                    code=CONDITIONAL_REQUIRED_FIELD_MISSING_CODE,
                    path=path,
                    message=(
                        f"conditionally required field {path} is missing; a socio declared under clave 2 "
                        f"(no residente sin establecimiento permanente) states its country of residence"
                    ),
                )
                for path in atribucion_socio_missing_country_paths(values)
            ),
            *(
                ProfileValidationIssue(
                    severity=BaseSeverity.ERROR,
                    code=CONDITIONALLY_FORBIDDEN_FIELD_CODE,
                    path=path,
                    message=(
                        f"field {path} must be empty; Modelo 184 fills the country only under clave 2, and "
                        f"a socio declared residente or no residente con establecimiento permanente "
                        f"requires BLANCOS there"
                    ),
                )
                for path in atribucion_socio_forbidden_country_paths(values)
            ),
        )

    @staticmethod
    def _render_fact_value(value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)


_PROFILE_SCHEMA_VALIDATION_MESSAGE: Final[str] = "profile facts failed schema validation"

_REPORTED_ISSUE_LIMIT: Final[int] = 3
"""How many refused facts the message names before it summarises the rest.

The operator needs the first few named to act; an unbounded list on a badly
wrong batch turns a refusal into a wall of text nobody reads.
"""


def reject_invalid_profile_facts(
    profile_id: str,
    facts: Iterable[UserProfileFact],
    *,
    require_complete: bool,
    schema: ProfileSchemaDefinition | None = None,
) -> None:
    """Refuse a fact set on blocking schema issues, or return silently.

    Every door that writes profile facts -- registration's initial record, the
    wizard's fact patch, and the cotejo censal's adoption of certificate
    values alike -- judges through here, so an engine-derived path, an unknown
    path or a mis-shaped value is refused at the write rather than at
    whichever surface happened to collect it. A check
    living only in an edit dialog binds nobody who writes through another
    surface, and a stored value at a derived path silently displaces the
    computation that owns it.

    The whole resulting fact sequence is judged rather than the incoming
    change alone, so a patch is never left half-applied by a later field's
    refusal.

    ``require_complete`` selects which issues block. A profile that is still
    :attr:`~cadrumo.domain.user_profile.values.ProfileSetupState.INCOMPLETE` is by
    definition allowed to be missing the fields filing depends on -- demanding
    them in order to build an incomplete profile is a contradiction. Shape and
    value are judged in both modes; only the missing-required-field issues are
    deferred, to the moment the profile is completed.

    Raises:
        ProfileSchemaValidationError: When any blocking issue remains, naming
            the refused paths and why.
    """
    from ...domain.user_profile.errors import ProfileSchemaValidationError
    from ...domain.user_profile.loader import load_user_profile_schema

    service = ProfileValidationService(schema=schema or load_user_profile_schema())
    report = service.validate_facts(profile_id, facts)
    blocking = [
        issue
        for issue in report.issues
        if issue.severity is BaseSeverity.ERROR and (require_complete or issue.code not in COMPLETENESS_ISSUE_CODES)
    ]
    if not blocking:
        return
    named = "; ".join(issue.message for issue in blocking[:_REPORTED_ISSUE_LIMIT])
    remaining = len(blocking) - _REPORTED_ISSUE_LIMIT
    detail = f"{named}; and {remaining} more" if remaining > 0 else named
    raise ProfileSchemaValidationError(
        f"{_PROFILE_SCHEMA_VALIDATION_MESSAGE}: {detail}",
        context={
            "profile_id": profile_id,
            "issue_count": len(blocking),
            "issue_codes": tuple(issue.code for issue in blocking),
            "issue_paths": tuple(issue.path for issue in blocking),
        },
        translated_message="application.user_profile.errors.lifecycle_schema_validation_failed",
    )


__all__ = [
    "BOOLEAN_VALUE_ISSUE_CODE",
    "COMPLETENESS_ISSUE_CODES",
    "CONDITIONALLY_FORBIDDEN_FIELD_CODE",
    "CONDITIONAL_REQUIRED_FIELD_MISSING_CODE",
    "DATE_VALUE_ISSUE_CODE",
    "EMAIL_VALUE_ISSUE_CODE",
    "ENUM_VALUE_ISSUE_CODE",
    "NUMERIC_VALUE_ISSUE_CODE",
    "REQUIRED_FIELD_MISSING_CODE",
    "UNKNOWN_FIELD_ISSUE_CODE",
    "ProfileValidationService",
    "reject_invalid_profile_facts",
]
