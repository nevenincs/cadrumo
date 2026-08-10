"""Fail-closed authority for absent record-design numeric wire facts.

Render profiles are reviewed inputs, not inference recipes.  A profile may name
only fixed-record numeric fields whose exact official ``Contenido`` cell is
blank.  It must enumerate that eligible set exactly and is rejected before a
renderer can observe it when any authority, anchor, or representation drifts.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Final, Literal

import rtoml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.domain.calculations.registry import ModeloId, RegistryValidationError, SourceRefId

from ._record_design_ir import RecordDesignIntermediateField
from ._semantic_map_join import JoinedRecordDesign

__all__ = [
    "RENDER_PROFILE_SCHEMA_VERSION",
    "RenderProfile",
    "RenderProfileAnchor",
    "RenderProfileDesignIdentity",
    "RenderProfileFragment",
    "ReviewedEvidence",
    "SingletonNumericRule",
    "Width17MembershipRule",
    "load_and_validate_render_profile",
    "validate_render_profile",
]


RENDER_PROFILE_SCHEMA_VERSION: Final[int] = 1


class _StrictModel(BaseModel):
    """Frozen authored boundary with unknown keys forbidden."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RenderProfileDesignIdentity(_StrictModel):
    """Identity of the exact official design to which rules apply."""

    modelo: ModeloId
    design_epoch: str = Field(min_length=1)
    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RenderProfileAnchor(_StrictModel):
    """Complete parser-owned field identity; no selector or wildcard exists."""

    sheet: str = Field(min_length=1)
    source_row: int = Field(gt=0)
    source_cell: str | None = Field(pattern=r"^[A-Z]+[1-9][0-9]*$")
    ordinal: int = Field(gt=0)
    record_identity: str = Field(min_length=1)


class ReviewedEvidence(_StrictModel):
    """Non-empty, anchor-specific review evidence for one authored rule."""

    source_sheet: str = Field(min_length=1)
    source_cell: str = Field(pattern=r"^[A-Z]+[1-9][0-9]*$")
    statement: str = Field(min_length=1)
    justification: str = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_whitespace_only_review_text(self) -> ReviewedEvidence:
        if not self.statement.strip() or not self.justification.strip():
            raise ValueError("reviewed evidence and justification must contain non-whitespace text")
        return self


class Width17MembershipRule(_StrictModel):
    """Reviewed enumeration of width-17 amount anchors of one AEAT type."""

    rule_kind: Literal["width_17_membership"]
    aeat_type: Literal["Num", "N"]
    integer_digits: Literal[15, 14]
    decimal_digits: Literal[2]
    sign_policy: Literal["unsigned", "n-prefix-negative-blank-nonnegative"]
    anchors: tuple[RenderProfileAnchor, ...] = Field(min_length=1)
    evidence: ReviewedEvidence

    @model_validator(mode="after")
    def _require_explicit_type_specific_representation(self) -> Width17MembershipRule:
        expected = (15, "unsigned") if self.aeat_type == "Num" else (14, "n-prefix-negative-blank-nonnegative")
        if (self.integer_digits, self.sign_policy) != expected:
            raise ValueError(f"{self.aeat_type} width-17 representation conflicts with its explicit sign policy")
        return self


class SingletonNumericRule(_StrictModel):
    """One reviewed smaller numeric field; grouping is deliberately impossible."""

    rule_kind: Literal["singleton_numeric"]
    aeat_type: Literal["Num"]
    semantic_kind: Literal[
        "integer",
        "decimal",
        "date_yyyymmdd",
        "enumeration",
        "percentage_decimal",
        "digit_string",
        "identifier_digits",
    ]
    integer_digits: int = Field(ge=0)
    decimal_digits: int = Field(ge=0)
    sign_policy: Literal["unsigned"]
    allowed_values: tuple[str, ...]
    anchor: RenderProfileAnchor
    evidence: ReviewedEvidence

    @model_validator(mode="after")
    def _require_kind_specific_declaration(self) -> SingletonNumericRule:
        if self.semantic_kind == "enumeration":
            if not self.allowed_values or any(
                not item or not item.isascii() or not item.isdigit() for item in self.allowed_values
            ):
                raise ValueError("enumeration rules require explicit non-empty ASCII-digit allowed_values")
            if len(set(self.allowed_values)) != len(self.allowed_values):
                raise ValueError("enumeration allowed_values must be unique")
        elif self.allowed_values:
            raise ValueError("allowed_values must be explicitly empty outside an enumeration rule")
        if self.semantic_kind == "date_yyyymmdd" and (self.integer_digits, self.decimal_digits) != (8, 0):
            raise ValueError("date_yyyymmdd requires exactly 8 integer digits and 0 decimal digits")
        if self.semantic_kind == "integer" and (self.integer_digits <= 0 or self.decimal_digits != 0):
            raise ValueError("integer requires positive integer digits and 0 decimal digits")
        if self.semantic_kind in {"decimal", "percentage_decimal"} and (
            self.integer_digits <= 0 or self.decimal_digits <= 0
        ):
            raise ValueError(f"{self.semantic_kind} requires positive integer and decimal digits")
        if self.semantic_kind in {"digit_string", "identifier_digits"} and (
            self.integer_digits <= 0 or self.decimal_digits != 0
        ):
            raise ValueError(f"{self.semantic_kind} requires positive integer digits and 0 decimal digits")
        if self.semantic_kind == "enumeration" and self.decimal_digits != 0:
            raise ValueError("enumeration requires 0 decimal digits")
        if self.evidence.source_sheet != self.anchor.sheet or self.evidence.source_cell != self.anchor.source_cell:
            raise ValueError("smaller-field evidence must be anchored to the exact governed field")
        return self


class RenderProfileFragment(_StrictModel):
    """One deterministic, independently reviewable profile fragment."""

    schema_version: Literal[1]
    fragment_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    design_identity: RenderProfileDesignIdentity
    width_17_rules: tuple[Width17MembershipRule, ...]
    singleton_rules: tuple[SingletonNumericRule, ...]

    @model_validator(mode="after")
    def _require_authored_rules(self) -> RenderProfileFragment:
        if not self.width_17_rules and not self.singleton_rules:
            raise ValueError("render profile fragments must contain at least one authored rule")
        return self


class RenderProfile(_StrictModel):
    """Deterministically compiled complete profile for one official design."""

    schema_version: Literal[1]
    design_identity: RenderProfileDesignIdentity
    fragment_ids: tuple[str, ...] = Field(min_length=1)
    width_17_rules: tuple[Width17MembershipRule, ...]
    singleton_rules: tuple[SingletonNumericRule, ...]

    @model_validator(mode="after")
    def _require_unique_fragment_ids(self) -> RenderProfile:
        duplicate_ids = _duplicates(self.fragment_ids)
        if duplicate_ids:
            raise ValueError(f"render profile contains duplicate fragment ids: {duplicate_ids!r}")
        return self


def load_and_validate_render_profile(
    profile_directory: Path,
    joined: JoinedRecordDesign,
) -> RenderProfile:
    """Load sorted TOML fragments and validate exact coverage against parser IR."""
    if not profile_directory.is_dir() or profile_directory.is_symlink() or profile_directory.is_junction():
        raise RegistryValidationError(f"render profile path must be a real directory: {profile_directory}")
    paths = tuple(sorted(profile_directory.glob("*.toml"), key=lambda path: path.name))
    if not paths:
        raise RegistryValidationError(f"render profile directory contains no TOML fragments: {profile_directory}")
    fragments: list[RenderProfileFragment] = []
    for path in paths:
        if path.is_symlink() or path.is_junction() or not path.is_file():
            raise RegistryValidationError(f"render profile fragment must be a regular file: {path}")
        try:
            fragments.append(RenderProfileFragment.model_validate_json(json.dumps(rtoml.load(path))))
        except (OSError, ValueError, TypeError) as exc:
            raise RegistryValidationError(f"invalid render profile fragment {path.name!r}: {exc}") from exc
    profile = _compile_fragments(fragments)
    validate_render_profile(profile, joined)
    return profile


def validate_render_profile(
    profile: RenderProfile,
    joined: JoinedRecordDesign,
) -> None:
    """Refuse every identity, membership, coverage, and representation conflict."""
    expected_identity = RenderProfileDesignIdentity(
        modelo=joined.modelo,
        design_epoch=joined.source.design_epoch,
        source_ref=joined.source.source_ref,
        source_sha256=joined.source.source_sha256,
    )
    if profile.design_identity != expected_identity:
        raise RegistryValidationError(
            f"render profile identity {profile.design_identity!r} does not match exact official design "
            f"{expected_identity!r}",
        )

    fields_by_anchor = {
        _field_anchor(joined_field.parser_field): joined_field.parser_field for joined_field in joined.fields
    }
    eligible = {
        anchor: field
        for anchor, field in fields_by_anchor.items()
        if field.aeat_type in {"Num", "N"} and (field.content is None or not field.content.strip())
    }
    governed = tuple(anchor for rule in profile.width_17_rules for anchor in rule.anchors) + tuple(
        rule.anchor for rule in profile.singleton_rules
    )
    duplicates = _duplicates(governed)
    if duplicates:
        raise RegistryValidationError(f"render profile contains duplicate or overlapping exact anchors: {duplicates!r}")
    governed_set = set(governed)
    eligible_set = set(eligible)
    if governed_set != eligible_set:
        missing = sorted(eligible_set - governed_set, key=_anchor_key)
        unknown = sorted(governed_set - eligible_set, key=_anchor_key)
        raise RegistryValidationError(
            "render profile must cover exactly the eligible blank numeric fields; "
            f"missing={missing!r}, unknown={unknown!r}",
        )

    width_17_types = tuple(rule.aeat_type for rule in profile.width_17_rules)
    duplicate_width_17_types = _duplicates(width_17_types)
    if duplicate_width_17_types:
        raise RegistryValidationError(
            "render profile splits one width-17 AEAT type across multiple membership rules: "
            f"{duplicate_width_17_types!r}",
        )
    eligible_width_17_types = {field.aeat_type for field in eligible.values() if field.length == 17}
    if set(width_17_types) != eligible_width_17_types:
        raise RegistryValidationError(
            "render profile must declare one explicit width-17 membership rule for each eligible AEAT type",
        )

    known_sheets = {record.parser_sheet.sheet for record in joined.records}
    for rule in profile.width_17_rules:
        if rule.evidence.source_sheet not in known_sheets:
            raise RegistryValidationError(
                "width-17 membership evidence must resolve to a fixed-record source sheet in the bound design; "
                f"got {rule.evidence.source_sheet!r}",
            )
        for anchor in rule.anchors:
            field = eligible[anchor]
            if field.length != 17 or field.aeat_type != rule.aeat_type:
                raise RegistryValidationError(
                    f"width-17 {rule.aeat_type} membership conflicts with official field at {anchor!r}",
                )
    for rule in profile.singleton_rules:
        field = eligible[rule.anchor]
        if field.length == 17 or field.aeat_type != rule.aeat_type:
            raise RegistryValidationError(f"smaller singleton rule conflicts with official field at {rule.anchor!r}")
        if rule.integer_digits + rule.decimal_digits != field.length:
            raise RegistryValidationError(
                f"smaller singleton representation width conflicts with official length at {rule.anchor!r}",
            )
        if any(len(item) != field.length for item in rule.allowed_values):
            raise RegistryValidationError(
                f"enumeration value width conflicts with official length at {rule.anchor!r}",
            )


def _compile_fragments(fragments: Iterable[RenderProfileFragment]) -> RenderProfile:
    ordered = tuple(fragments)
    if not ordered:
        raise RegistryValidationError("render profile requires at least one fragment")
    ids = tuple(fragment.fragment_id for fragment in ordered)
    duplicate_ids = _duplicates(ids)
    if duplicate_ids:
        raise RegistryValidationError(f"render profile contains duplicate fragment ids: {duplicate_ids!r}")
    design_identity = ordered[0].design_identity
    mismatched = tuple(fragment.fragment_id for fragment in ordered if fragment.design_identity != design_identity)
    if mismatched:
        raise RegistryValidationError(f"render profile fragments have inapplicable design identities: {mismatched!r}")
    width_rules = _compile_width_17_rules(rule for fragment in ordered for rule in fragment.width_17_rules)
    return RenderProfile(
        schema_version=RENDER_PROFILE_SCHEMA_VERSION,
        design_identity=design_identity,
        fragment_ids=ids,
        width_17_rules=width_rules,
        singleton_rules=tuple(rule for fragment in ordered for rule in fragment.singleton_rules),
    )


def _compile_width_17_rules(rules: Iterable[Width17MembershipRule]) -> tuple[Width17MembershipRule, ...]:
    by_type: dict[str, list[Width17MembershipRule]] = {}
    for rule in rules:
        by_type.setdefault(rule.aeat_type, []).append(rule)
    compiled: list[Width17MembershipRule] = []
    for aeat_type in ("Num", "N"):
        type_rules = by_type.get(aeat_type, [])
        if not type_rules:
            continue
        authority = type_rules[0]
        if any(
            (
                rule.integer_digits,
                rule.decimal_digits,
                rule.sign_policy,
                rule.evidence,
            )
            != (
                authority.integer_digits,
                authority.decimal_digits,
                authority.sign_policy,
                authority.evidence,
            )
            for rule in type_rules[1:]
        ):
            raise RegistryValidationError(
                f"render profile fragments conflict on width-17 {aeat_type} authority",
            )
        compiled.append(
            authority.model_copy(
                update={"anchors": tuple(anchor for rule in type_rules for anchor in rule.anchors)},
            ),
        )
    return tuple(compiled)


def _field_anchor(field: RecordDesignIntermediateField) -> RenderProfileAnchor:
    return RenderProfileAnchor(
        sheet=field.sheet,
        source_row=field.source_row,
        source_cell=field.source_cell,
        ordinal=field.ordinal,
        record_identity=field.record_identity,
    )


def _duplicates[T](values: Iterable[T]) -> tuple[T, ...]:
    seen: set[T] = set()
    duplicates: set[T] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return tuple(sorted(duplicates, key=repr))


def _anchor_key(anchor: RenderProfileAnchor) -> tuple[str, int, int, str, str]:
    return (
        anchor.sheet,
        anchor.source_row,
        anchor.ordinal,
        anchor.source_cell or "",
        anchor.record_identity,
    )
