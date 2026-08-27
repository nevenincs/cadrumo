"""Cross-reference user-profile schema metadata against modelo registry use.

Validates every :class:`ModeloDefinition` in the registry against the
user-profile schema, checking that each :class:`ModeloRevision` binding
selector, filing schedule predicate, and deadline applicability condition
maps to a declared profile fact path.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Literal, cast

from pydantic import BaseModel, Field

from .schema import (
    ProfileDerivedSelectorDefinition,
    ProfileSchemaDefinition,
    derived_selector_for_path,
)

if TYPE_CHECKING:
    from ..calculations.registry.schema import ModeloDefinition, ModeloRevision

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import BindingSourceKind
from ...core.errors import BaseSeverity
from ..calculations.registry.bindings import ProfileSelector
from ..calculations.registry.ids import RevisionId


class UserProfileRegistryContractIssue(BaseModel):
    """One unresolved cross-reference between user-profile schema and modelos."""

    model_config = _STRICT_FROZEN

    severity: Literal[BaseSeverity.ERROR, BaseSeverity.WARNING]
    modelo_id: str
    revision_id: RevisionId
    surface: Literal[
        "binding",
        "filing_schedule",
        "deadline_window",
        "export_layout",
        "cross_reference_applicability",
    ]
    construct_id: str
    selector: str
    message: str = Field(min_length=1)


class UserProfileSelectorIndex(BaseModel):
    """Schema-owned selector namespaces consumed by modelo registry surfaces."""

    model_config = _STRICT_FROZEN

    profile_selectors: frozenset[str]
    schedule_predicates: frozenset[str]
    field_paths: frozenset[str]
    #: Namespaces the engine owns and computes. Kept as typed models rather
    #: than folded into ``profile_selectors`` because a pattern carrying a
    #: placeholder is not a literal set member -- set membership could never
    #: see it -- and because a caller resolving a selector this way needs to
    #: know WHICH pattern matched, not merely that one did.
    derived_selectors: tuple[ProfileDerivedSelectorDefinition, ...] = ()


class UserProfileRegistryContractReport(BaseModel):
    """Typed result for profile schema coverage against modelo registry usage."""

    model_config = _STRICT_FROZEN

    schema_id: str
    schema_version: int
    checked_modelos: tuple[str, ...]
    issues: tuple[UserProfileRegistryContractIssue, ...] = ()

    @property
    def errors(self) -> tuple[UserProfileRegistryContractIssue, ...]:
        """Return blocking :class:`UserProfileRegistryContractIssue` failures."""
        return tuple(issue for issue in self.issues if issue.severity is BaseSeverity.ERROR)

    @property
    def warnings(self) -> tuple[UserProfileRegistryContractIssue, ...]:
        """Return non-blocking :class:`UserProfileRegistryContractIssue` coverage gaps."""
        return tuple(issue for issue in self.issues if issue.severity is BaseSeverity.WARNING)

    @property
    def valid(self) -> bool:
        """Return whether all blocking selector references resolve."""
        return not self.errors


def build_user_profile_selector_index(schema: ProfileSchemaDefinition) -> UserProfileSelectorIndex:
    """Build the profile selector namespaces declared by the TOML schema.

    Returns:
        A :class:`UserProfileSelectorIndex` with all declared selector namespaces.
    """
    profile_selectors: set[str] = set(schema.field_paths)
    schedule_predicates: set[str] = set()
    for section in schema.sections:
        for field in section.fields:
            profile_selectors.update(field.model_selectors)
            schedule_predicates.update(field.schedule_predicates)
    return UserProfileSelectorIndex(
        profile_selectors=frozenset(profile_selectors),
        schedule_predicates=frozenset(schedule_predicates),
        field_paths=frozenset(schema.field_paths),
        derived_selectors=schema.derived_selectors,
    )


def validate_user_profile_registry_contract(
    modelos: Iterable[ModeloDefinition],
    schema: ProfileSchemaDefinition,
) -> UserProfileRegistryContractReport:
    """Validate all profile-facing modelo registry references against the schema.

    Blocking errors are reserved for model calculation and schedule selectors
    that cannot be resolved from schema-declared profile facts. Export header
    gaps are warnings during the rollout because several committed layouts use
    non-profile operational headers that will move behind an export-context
    backend rather than a live taxpayer profile fact.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` instances to validate.
        schema: The user-profile schema to validate registry references against.

    Returns:
        A :class:`UserProfileRegistryContractReport` with all issues found.
    """
    index = build_user_profile_selector_index(schema)
    checked_modelos: list[str] = []
    issues: list[UserProfileRegistryContractIssue] = []
    for modelo in modelos:
        checked_modelos.append(modelo.id)
        for revision in modelo.revisions.values():
            issues.extend(_binding_issues(modelo.id, revision, index))
            issues.extend(_schedule_issues(modelo.id, revision, index))
            issues.extend(_deadline_issues(modelo.id, revision, index))
            issues.extend(_cross_reference_applicability_issues(modelo.id, revision, index))
            issues.extend(_export_issues(modelo.id, revision, index))
    return UserProfileRegistryContractReport(
        schema_id=schema.id,
        schema_version=schema.version,
        checked_modelos=tuple(sorted(checked_modelos)),
        issues=tuple(issues),
    )


def _binding_issues(
    modelo_id: str,
    revision: ModeloRevision,
    index: UserProfileSelectorIndex,
) -> tuple[UserProfileRegistryContractIssue, ...]:
    issues: list[UserProfileRegistryContractIssue] = []
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.PROFILE:
            continue
        selectors = tuple(profile_binding_selectors(binding.selector))
        if not selectors:
            issues.append(
                _issue(
                    severity=BaseSeverity.ERROR,
                    modelo_id=modelo_id,
                    revision_id=revision.id,
                    surface="binding",
                    construct_id=binding.id,
                    selector="<unresolved>",
                    message="profile binding does not declare a supported profile selector",
                ),
            )
            continue
        for selector in selectors:
            # A selector resolves either as a literal schema-declared path /
            # model alias, or as a member of a namespace the engine owns and
            # computes. The derived hop sits here, BELOW the empty-selector
            # arm above: that arm answers a malformed selector yielding no
            # path at all, which no pattern should ever excuse.
            #
            # Asked through the one canonical judgment rather than a method on
            # this index, so the write-door refusal and this validator cannot
            # develop separate opinions about what "derived" means. Scoped to
            # binding selectors only: the schedule, deadline, cross-reference
            # and export-header surfaces read disjoint namespaces that no
            # derived path declares, and routing them here would silently
            # retire real coverage warnings.
            derived = derived_selector_for_path(selector, index.derived_selectors)
            if selector not in index.profile_selectors and derived is None:
                issues.append(
                    _issue(
                        severity=BaseSeverity.ERROR,
                        modelo_id=modelo_id,
                        revision_id=revision.id,
                        surface="binding",
                        construct_id=binding.id,
                        selector=selector,
                        message="profile binding selector is not declared by user-profile schema",
                    ),
                )
    return tuple(issues)


def _schedule_issues(
    modelo_id: str,
    revision: ModeloRevision,
    index: UserProfileSelectorIndex,
) -> tuple[UserProfileRegistryContractIssue, ...]:
    issues: list[UserProfileRegistryContractIssue] = []
    for schedule in revision.filing_schedules:
        for condition in schedule.profile_conditions:
            if condition.field not in index.schedule_predicates:
                issues.append(
                    _issue(
                        severity=BaseSeverity.ERROR,
                        modelo_id=modelo_id,
                        revision_id=revision.id,
                        surface="filing_schedule",
                        construct_id=schedule.id,
                        selector=condition.field,
                        message="filing schedule predicate is not declared by user-profile schema",
                    ),
                )
    return tuple(issues)


def _deadline_issues(
    modelo_id: str,
    revision: ModeloRevision,
    index: UserProfileSelectorIndex,
) -> tuple[UserProfileRegistryContractIssue, ...]:
    issues: list[UserProfileRegistryContractIssue] = []
    for window in revision.deadline_windows:
        for condition in window.applicability_conditions:
            if condition.field not in index.schedule_predicates:
                issues.append(
                    _issue(
                        severity=BaseSeverity.ERROR,
                        modelo_id=modelo_id,
                        revision_id=revision.id,
                        surface="deadline_window",
                        construct_id=window.id,
                        selector=condition.field,
                        message="deadline applicability predicate is not declared by user-profile schema",
                    ),
                )
    return tuple(issues)


def _cross_reference_applicability_issues(
    modelo_id: str,
    revision: ModeloRevision,
    index: UserProfileSelectorIndex,
) -> tuple[UserProfileRegistryContractIssue, ...]:
    issues: list[UserProfileRegistryContractIssue] = []
    for cross_reference in revision.live_cross_references:
        for predicate in cross_reference.applicability_predicates:
            if predicate.field not in index.schedule_predicates:
                issues.append(
                    _issue(
                        severity=BaseSeverity.ERROR,
                        modelo_id=modelo_id,
                        revision_id=revision.id,
                        surface="cross_reference_applicability",
                        construct_id=cross_reference.id,
                        selector=predicate.field,
                        message="cross-reference applicability predicate is not declared by user-profile schema",
                    ),
                )
    return tuple(issues)


def _export_issues(
    modelo_id: str,
    revision: ModeloRevision,
    index: UserProfileSelectorIndex,
) -> tuple[UserProfileRegistryContractIssue, ...]:
    # Producer fields are resolved by the typed application snapshot, not by
    # profile-schema export declarations.  Keeping a second profile export
    # vocabulary would reintroduce the retired raw-header authority.
    del modelo_id, revision, index
    return ()


def profile_binding_selectors(selector: Mapping[str, object] | BaseModel) -> tuple[str, ...]:
    """Return the declared user-profile paths selected by one binding payload."""
    if isinstance(selector, ProfileSelector):
        # Every real caller passes the selector of an already-filtered
        # ``source == BindingSourceKind.PROFILE`` binding, which the
        # discriminated-union field validator on ``DataBindingDefinition``
        # (``_coerce_selector`` -> ``ProfileSelector.model_validate``) has
        # already hydrated into the typed model by construction time. Reading
        # the typed ATTRIBUTES here -- rather than round-tripping through
        # ``model_dump()`` into a plain dict and re-reading it with string
        # literals -- means a field rename on ``ProfileSelector`` (e.g.
        # ``required_when_profile_key``, declared at ``_bindings.py``) fails
        # loud (``AttributeError``, and at static analysis time) instead of
        # the dict-literal read silently and permanently returning ``None``.
        selectors: list[str] = []
        profile_key = selector.profile_key
        if isinstance(profile_key, str):
            selectors.append(profile_key)
        selectors.extend(selector.profile_keys)
        required_when_profile_key = selector.required_when_profile_key
        if isinstance(required_when_profile_key, str):
            selectors.append(required_when_profile_key)
        profile_model = selector.profile_model
        profile_field = selector.field
        if isinstance(profile_model, str) and isinstance(profile_field, str):
            collection = selector.collection
            if isinstance(collection, str):
                selectors.append(f"{profile_model}.{collection}.{profile_field}")
            else:
                selectors.append(f"{profile_model}.{profile_field}")
        return tuple(dict.fromkeys(selectors))
    if isinstance(selector, BaseModel):
        # A different binding-source family's typed selector; its shape never
        # carries a profile key, so no read is needed.
        return ()
    selectors = []
    profile_key = selector.get("profile_key")
    if isinstance(profile_key, str):
        selectors.append(profile_key)
    profile_keys = selector.get("profile_keys")
    if isinstance(profile_keys, tuple):
        selectors.extend(
            item
            # CAST-RATIONALE-PROFILE-KEYS-TUPLE: isinstance narrows to tuple but
            # not its element type; each item is filtered by isinstance below.
            # nosemgrep: no-cast-in-domain-application
            for item in cast(tuple[object, ...], profile_keys)
            if isinstance(item, str)
        )
    required_when_profile_key = selector.get("required_when_profile_key")
    if isinstance(required_when_profile_key, str):
        selectors.append(required_when_profile_key)
    profile_model = selector.get("profile_model")
    profile_field = selector.get("field")
    if isinstance(profile_model, str) and isinstance(profile_field, str):
        collection = selector.get("collection")
        if isinstance(collection, str):
            selectors.append(f"{profile_model}.{collection}.{profile_field}")
        else:
            selectors.append(f"{profile_model}.{profile_field}")
    return tuple(dict.fromkeys(selectors))


def _issue(
    *,
    severity: Literal[BaseSeverity.ERROR, BaseSeverity.WARNING],
    modelo_id: str,
    revision_id: RevisionId,
    surface: Literal[
        "binding",
        "filing_schedule",
        "deadline_window",
        "export_layout",
        "cross_reference_applicability",
    ],
    construct_id: str,
    selector: str,
    message: str,
) -> UserProfileRegistryContractIssue:
    return UserProfileRegistryContractIssue(
        severity=severity,
        modelo_id=modelo_id,
        revision_id=revision_id,
        surface=surface,
        construct_id=construct_id,
        selector=selector,
        message=message,
    )
