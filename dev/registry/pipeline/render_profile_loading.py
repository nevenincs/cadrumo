"""Canonical strict fragment loading and compilation for reviewed render profiles."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Final, Literal

import rtoml
from pydantic import ValidationError

from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.link_safety import is_link_like
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import RevisionId, is_registry_id

from .pydantic_error_detail import validation_error_detail
from .render_profile_model import RenderProfile
from .render_profile_model_base import RenderProfileDesignIdentity
from .render_profile_rules import (
    RenderProfileFragment,
    Width17MembershipRule,
)
from .render_profile_validation import _duplicates

RENDER_PROFILE_SCHEMA_VERSION: Final[Literal[1]] = 1


def load_render_profile(profile_directory: Path) -> RenderProfile:
    """Load sorted TOML fragments without weakening their strict authored schema."""
    _require_render_profile_directory(profile_directory)
    paths = _render_profile_fragment_paths(profile_directory)
    fragments = tuple(_load_render_profile_fragment(path) for path in paths)
    return _compile_fragments(fragments)


def load_render_profile_for_revision(epoch_directory: Path, revision_id: RevisionId) -> RenderProfile:
    """Select a complete revision-scoped profile when one source epoch serves distinct revisions."""
    if not is_registry_id(revision_id) or "/" in revision_id or "\\" in revision_id:
        raise RegistryValidationError(f"render-profile revision id is not a safe registry identity: {revision_id!r}")
    _require_render_profile_directory(epoch_directory)
    try:
        members = tuple(iter_directory(epoch_directory, require_root=True))
    except OSError as exc:
        raise RegistryValidationError(f"cannot inspect render-profile epoch directory: {epoch_directory}") from exc
    fragments = tuple(path for path in members if path.suffix.casefold() == ".toml")
    editions = tuple(path for path in members if path.is_dir() and not is_link_like(path))
    if fragments and editions:
        raise RegistryValidationError("render-profile epoch mixes unscoped fragments with revision directories")
    if fragments:
        return load_render_profile(epoch_directory)
    invalid = tuple(path.name for path in members if path not in editions or not is_registry_id(path.name))
    if invalid:
        raise RegistryValidationError(f"render-profile epoch contains unsupported entries: {invalid!r}")
    selected = epoch_directory / revision_id
    if selected not in editions:
        raise RegistryValidationError(
            f"render-profile epoch has no reviewed profile for revision {revision_id!r}: {epoch_directory}"
        )
    return load_render_profile(selected)


def _require_render_profile_directory(profile_directory: Path) -> None:
    if not profile_directory.is_dir() or is_link_like(profile_directory):
        raise RegistryValidationError(f"render profile path must be a real directory: {profile_directory}")


def _render_profile_fragment_paths(profile_directory: Path) -> tuple[Path, ...]:
    try:
        paths = tuple(sorted(iter_directory(profile_directory, require_root=True), key=lambda path: path.name))
    except OSError as exc:
        raise RegistryValidationError(f"cannot inspect render profile directory: {profile_directory}") from exc
    if not paths:
        raise RegistryValidationError(f"render profile directory contains no TOML fragments: {profile_directory}")
    non_fragments = tuple(
        path.name for path in paths if path.suffix.casefold() != ".toml" or is_link_like(path) or not path.is_file()
    )
    if non_fragments:
        raise RegistryValidationError(
            "render profile directory accepts only regular TOML fragments; "
            f"refusing non-profile entries: {non_fragments!r}",
        )
    return paths


def _load_render_profile_fragment(path: Path) -> RenderProfileFragment:
    if is_link_like(path) or not path.is_file():
        raise RegistryValidationError(f"render profile fragment must be a regular file: {path}")
    try:
        return RenderProfileFragment.model_validate_json(json.dumps(rtoml.load(path)))
    except ValidationError as exc:
        raise RegistryValidationError(
            f"invalid render profile fragment {path.name!r}: {validation_error_detail(exc)}",
        ) from exc
    except (OSError, ValueError, TypeError) as exc:
        raise RegistryValidationError(f"invalid render profile fragment {path.name!r}: {exc}") from exc


def _compile_fragments(fragments: Iterable[RenderProfileFragment]) -> RenderProfile:
    ordered = _ordered_profile_fragments(fragments)
    ids = tuple(fragment.fragment_id for fragment in ordered)
    _require_unique_fragment_ids(ids)
    design_identity = _shared_fragment_identity(ordered)
    _require_fragment_identity(ordered, design_identity)
    empty_assertions = tuple(fragment.empty_rule_assertion for fragment in ordered if fragment.empty_rule_assertion)
    if empty_assertions and len(ordered) != 1:
        raise RegistryValidationError("an empty render profile must be one complete exact-design fragment")
    width_rules = _compile_width_17_rules(rule for fragment in ordered for rule in fragment.width_17_rules)
    return RenderProfile(
        schema_version=RENDER_PROFILE_SCHEMA_VERSION,
        design_identity=design_identity,
        fragment_ids=ids,
        width_17_rules=width_rules,
        singleton_rules=tuple(rule for fragment in ordered for rule in fragment.singleton_rules),
        signed_composite_rules=tuple(rule for fragment in ordered for rule in fragment.signed_composite_rules),
        literal_numeric_rules=tuple(rule for fragment in ordered for rule in fragment.literal_numeric_rules),
        telematic_transport_choice_rules=tuple(
            rule for fragment in ordered for rule in fragment.telematic_transport_choice_rules
        ),
        empty_rule_assertion=empty_assertions[0] if empty_assertions else None,
    )


def _ordered_profile_fragments(fragments: Iterable[RenderProfileFragment]) -> tuple[RenderProfileFragment, ...]:
    ordered = tuple(fragments)
    if not ordered:
        raise RegistryValidationError("render profile requires at least one fragment")
    return ordered


def _require_unique_fragment_ids(ids: tuple[str, ...]) -> None:
    duplicate_ids = _duplicates(ids)
    if duplicate_ids:
        raise RegistryValidationError(f"render profile contains duplicate fragment ids: {duplicate_ids!r}")


def _shared_fragment_identity(fragments: tuple[RenderProfileFragment, ...]) -> RenderProfileDesignIdentity:
    return fragments[0].design_identity


def _require_fragment_identity(
    fragments: tuple[RenderProfileFragment, ...],
    design_identity: RenderProfileDesignIdentity,
) -> None:
    mismatched = tuple(fragment.fragment_id for fragment in fragments if fragment.design_identity != design_identity)
    if mismatched:
        raise RegistryValidationError(f"render profile fragments have inapplicable design identities: {mismatched!r}")


#: Width-17 AEAT types in the order their compiled rules are emitted. Declared
#: explicitly rather than derived from ``Width17MembershipRule.aeat_type``,
#: because this order reaches the rendered bytes and reordering a type annotation
#: must not silently reorder generated output. It is held exhaustive against that
#: annotation by the owning test, so widening the type without extending this
#: tuple -- which would drop the new type's rules here in silence -- fails.
_WIDTH_17_TYPE_ORDER: Final[tuple[str, ...]] = ("Num", "N")


def _compile_width_17_rules(rules: Iterable[Width17MembershipRule]) -> tuple[Width17MembershipRule, ...]:
    by_type: dict[str, list[Width17MembershipRule]] = {}
    for rule in rules:
        by_type.setdefault(rule.aeat_type, []).append(rule)
    compiled: list[Width17MembershipRule] = []
    for aeat_type in _WIDTH_17_TYPE_ORDER:
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
