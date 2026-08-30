"""Structured ``applies_when`` selection predicate for operator harness skills.

Each shipped skill's ``SKILL.md`` frontmatter carries a machine-queryable
``applies_when`` predicate that a router, an MCP guided prompt, or a live-eval
scenario can evaluate deterministically, instead of parsing the selection rule
out of the human ``description`` prose. This module defines that predicate schema
and the frontmatter parser that produces it.

The predicate is expressed over three orthogonal axes:

- ``profile_facts`` - conjunctive predicates over :class:`TaxpayerProfile` fact
  names. A fact name that is not a real field of the model fails validation, so a
  typo cannot ship; enum-valued facts additionally validate their expected values
  against the enum member set.
- ``workflow_phase`` - the point in the operator lifecycle spine a cross-cutting
  helper skill serves (ledger upkeep, classification, export, reconciliation, ...).
- ``temporal_trigger`` - a life-situation (WHEN) overlay keyed off deadline or
  lifecycle state (backlog overdue, quarter boundary, annual window, activity
  start/end).

A skill that is a cross-cutting helper invoked by other skills, with no profile,
phase, or temporal gate, declares ``always: true``.

The fact-name and enum-value registries are derived from the live
:class:`TaxpayerProfile` model at import, never hand-maintained, so the predicate
vocabulary tracks the profile model automatically.
"""

from __future__ import annotations

import enum
import re
import types
import typing
from collections.abc import Mapping
from typing import ClassVar

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from cadrumo.domain.deadlines.models import TaxpayerProfile


class SkillMetadataError(ValueError):
    """Raised when a skill's frontmatter or ``applies_when`` predicate is invalid."""

    __bare_base_rationale__: ClassVar[str] = (
        "agent-harness skill-frontmatter/applies_when validation error; intentionally a plain "
        "ValueError (a malformed-input signal at the harness boundary), not an operator-facing "
        "registry-bound filing/calculation error"
    )


class ProfileFactMatch(enum.StrEnum):
    """How a single :class:`TaxpayerProfile` fact is matched by a predicate."""

    PRESENT = "present"
    """The fact is declared (not ``None`` and, for a collection, non-empty)."""
    ABSENT = "absent"
    """The fact is undeclared (``None`` or an empty collection)."""
    EQUALS = "equals"
    """A scalar fact equals one of the predicate's ``values`` (in-set membership)."""
    CONTAINS = "contains"
    """A collection fact intersects the predicate's ``values`` (non-empty overlap)."""
    IS_TRUE = "is_true"
    """A boolean fact is ``True``."""
    IS_FALSE = "is_false"
    """A boolean fact is ``False``."""


class WorkflowPhase(enum.StrEnum):
    """The operator-lifecycle point a cross-cutting helper skill serves."""

    ONBOARDING = "onboarding"
    LEDGER_UPKEEP = "ledger_upkeep"
    CLASSIFICATION = "classification"
    MODELO_PREPARATION = "modelo_preparation"
    EXPORT = "export"
    RECONCILIATION = "reconciliation"


class TemporalTrigger(enum.StrEnum):
    """A life-situation (WHEN) overlay keyed off deadline or lifecycle state."""

    BACKLOG_OVERDUE = "backlog_overdue"
    QUARTER_BOUNDARY = "quarter_boundary"
    ANNUAL_WINDOW = "annual_window"
    AMENDMENT_REQUESTED = "amendment_requested"
    ACTIVITY_START = "activity_start"
    ACTIVITY_END = "activity_end"


class MatchMode(enum.StrEnum):
    """How the ``profile_facts`` conjuncts combine into one profile predicate."""

    ALL = "all"
    """Every ``profile_facts`` predicate must hold (logical AND)."""
    ANY = "any"
    """At least one ``profile_facts`` predicate must hold (logical OR)."""


class _FactKind(enum.Enum):
    """The structural shape of a :class:`TaxpayerProfile` fact for match validation."""

    BOOL = enum.auto()
    ENUM_SCALAR = enum.auto()
    COLLECTION = enum.auto()
    SCALAR = enum.auto()


def _strip_optional(annotation: object) -> object:
    """Return ``annotation`` with a single ``| None`` union arm removed."""
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        arms = [arm for arm in typing.get_args(annotation) if arm is not type(None)]
        if len(arms) == 1:
            return arms[0]
    return annotation


def _enum_values(candidate: object) -> frozenset[str] | None:
    """Return the string member values of ``candidate`` when it is an enum type."""
    if isinstance(candidate, type) and issubclass(candidate, enum.Enum):
        return frozenset(str(member.value) for member in candidate)
    return None


def _classify_fact(annotation: object) -> tuple[_FactKind, frozenset[str] | None]:
    """Classify a profile field annotation into its match kind and enum-value set."""
    resolved = _strip_optional(annotation)
    origin = typing.get_origin(resolved)
    if origin in (frozenset, set, list, tuple):
        args = typing.get_args(resolved)
        element = args[0] if args else None
        return _FactKind.COLLECTION, _enum_values(element)
    if isinstance(resolved, type) and issubclass(resolved, bool):
        return _FactKind.BOOL, None
    enum_values = _enum_values(resolved)
    if enum_values is not None:
        return _FactKind.ENUM_SCALAR, enum_values
    return _FactKind.SCALAR, None


def _build_fact_registry() -> tuple[dict[str, _FactKind], dict[str, frozenset[str]]]:
    kinds: dict[str, _FactKind] = {}
    enum_values: dict[str, frozenset[str]] = {}

    def register(prefix: str, model: type[BaseModel]) -> None:
        for name, field in model.model_fields.items():
            resolved = _strip_optional(field.annotation)
            full = f"{prefix}{name}"
            # Descend exactly one level into a nested profile sub-model
            # (``iva`` -> ``ModeloIVAProfile``, ``enrollment`` -> ``ModeloEnrollment``)
            # so a predicate can name ``iva.oss_enrolled`` and the sub-field is
            # still validated against the live model rather than a literal list.
            if not prefix and isinstance(resolved, type) and issubclass(resolved, BaseModel):
                register(f"{full}.", resolved)
                continue
            kind, values = _classify_fact(field.annotation)
            kinds[full] = kind
            if values is not None:
                enum_values[full] = values

    register("", TaxpayerProfile)
    return kinds, enum_values


_FACT_KINDS, _FACT_ENUM_VALUES = _build_fact_registry()


def profile_fact_names() -> frozenset[str]:
    """Return every valid :class:`TaxpayerProfile` fact name a predicate may cite."""
    return frozenset(_FACT_KINDS)


class ProfileFactPredicate(BaseModel):
    """A single conjunct: a :class:`TaxpayerProfile` fact matched a stated way."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fact: str
    match: ProfileFactMatch
    values: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_against_profile(self) -> ProfileFactPredicate:
        if self.fact not in _FACT_KINDS:
            raise ValueError(
                f"unknown TaxpayerProfile fact '{self.fact}'; a fact name must be a real field of the profile model",
            )
        kind = _FACT_KINDS[self.fact]
        allowed_values = _FACT_ENUM_VALUES.get(self.fact)
        match self.match:
            case ProfileFactMatch.PRESENT | ProfileFactMatch.ABSENT:
                self._forbid_values()
            case ProfileFactMatch.IS_TRUE | ProfileFactMatch.IS_FALSE:
                self._forbid_values()
                if kind is not _FactKind.BOOL:
                    raise ValueError(
                        f"match '{self.match.value}' requires a boolean fact; '{self.fact}' is not boolean",
                    )
            case ProfileFactMatch.EQUALS:
                self._require_values()
                if kind is _FactKind.COLLECTION:
                    raise ValueError(f"'{self.fact}' is a collection; use match 'contains'")
                if kind is _FactKind.BOOL:
                    raise ValueError(f"'{self.fact}' is boolean; use match 'is_true'/'is_false'")
                self._check_enum_values(allowed_values)
            case ProfileFactMatch.CONTAINS:
                self._require_values()
                if kind is not _FactKind.COLLECTION:
                    raise ValueError(
                        f"match 'contains' requires a collection fact; '{self.fact}' is a scalar - use match 'equals'",
                    )
                self._check_enum_values(allowed_values)
        return self

    def _forbid_values(self) -> None:
        if self.values:
            raise ValueError(f"match '{self.match.value}' takes no values")

    def _require_values(self) -> None:
        if not self.values:
            raise ValueError(f"match '{self.match.value}' requires at least one value")

    def _check_enum_values(self, allowed_values: frozenset[str] | None) -> None:
        if allowed_values is None:
            return
        invalid = sorted(value for value in self.values if value not in allowed_values)
        if invalid:
            raise ValueError(
                f"invalid value(s) {invalid} for enum fact '{self.fact}'; allowed: {sorted(allowed_values)}",
            )


class SkillAppliesWhen(BaseModel):
    """The structured selection predicate lifted from a skill's prose description."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_facts: tuple[ProfileFactPredicate, ...] = ()
    profile_match: MatchMode = MatchMode.ALL
    workflow_phase: WorkflowPhase | None = None
    temporal_trigger: TemporalTrigger | None = None
    always: bool = False

    @model_validator(mode="after")
    def _validate_axes(self) -> SkillAppliesWhen:
        if self.profile_match is MatchMode.ANY and not self.profile_facts:
            raise ValueError("profile_match 'any' requires at least one profile_facts predicate")
        gated = bool(self.profile_facts) or self.workflow_phase is not None or self.temporal_trigger is not None
        if self.always:
            if gated:
                raise ValueError(
                    "always=true is exclusive; do not combine it with profile_facts, "
                    "workflow_phase, or temporal_trigger",
                )
            return self
        if not gated:
            raise ValueError(
                "applies_when must declare at least one of: profile_facts, workflow_phase, temporal_trigger, always",
            )
        return self


class SkillMetadata(BaseModel):
    """The validated frontmatter of a shipped ``SKILL.md``.

    ``applies_when`` is optional at the load boundary: a skill whose predicate has
    not yet been lifted from prose still loads (with ``applies_when`` ``None``),
    and a predicate that IS present is fully validated. Strict presence - the
    requirement that every shipped skill declare the field - is enforced by the
    coverage gate, not the load path, so the tree stays loadable while the lifts
    land.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str
    applies_when: SkillAppliesWhen | None = None


_FRONTMATTER = re.compile(r"\A---\r?\n(?P<body>.*?)\r?\n---\r?\n", re.DOTALL)


def parse_skill_frontmatter(text: str) -> Mapping[str, object]:
    """Extract and YAML-parse the leading frontmatter block of a ``SKILL.md``."""
    matched = _FRONTMATTER.match(text)
    if matched is None:
        raise SkillMetadataError("SKILL.md has no leading YAML frontmatter block")
    loaded = yaml.safe_load(matched.group("body"))
    if not isinstance(loaded, Mapping):
        raise SkillMetadataError("SKILL.md frontmatter is not a YAML mapping")
    frontmatter: dict[str, object] = {}
    for key, value in loaded.items():
        if not isinstance(key, str):
            raise SkillMetadataError("SKILL.md frontmatter mapping keys must be strings")
        frontmatter[key] = value
    return frontmatter


def parse_skill_metadata(text: str) -> SkillMetadata:
    """Parse and validate the full frontmatter of a ``SKILL.md`` document.

    Returns:
        A :class:`SkillMetadata`.
    """
    data = parse_skill_frontmatter(text)
    try:
        return SkillMetadata.model_validate(dict(data))
    except ValidationError as exc:
        raise SkillMetadataError(f"invalid skill frontmatter: {exc}") from exc


__all__ = [
    "MatchMode",
    "ProfileFactMatch",
    "ProfileFactPredicate",
    "SkillAppliesWhen",
    "SkillMetadata",
    "SkillMetadataError",
    "TemporalTrigger",
    "WorkflowPhase",
    "parse_skill_frontmatter",
    "parse_skill_metadata",
    "profile_fact_names",
]
