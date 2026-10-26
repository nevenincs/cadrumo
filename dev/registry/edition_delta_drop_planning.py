"""Decide which declared registry family members exactly restate inherited storage."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from cadrumo.domain.calculations.registry.keyed_families import family_identity_value
from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from . import edition_delta_chain_materialisation as _edition_delta_chain_materialisation
from . import edition_delta_drop_scope as _edition_delta_drop_scope
from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_fields as _edition_delta_fields
from . import edition_delta_lineage_attestation as _edition_delta_lineage_attestation
from . import edition_delta_source as _edition_delta_source
from .compiler.casilla_identity import LINEAGE_CLAIM_FIELDS
from .compiler.casilla_inheritance import without_lineage_claims
from .edition_delta_drop_types import DropPlan, EditionDrop, FamilyDrop, _FamilyDropState, _MemberFragment

__all__ = ("plan_drop",)


def _family_header(section: str) -> re.Pattern[str]:
    return re.compile(rf"^\[\[revisions\.{_edition_delta_fields._REVISION_SEGMENT}\.{re.escape(section)}\]\]\s*$")


def _read_family_fragments(edition_dir: Path, section: str) -> tuple[_MemberFragment, ...]:
    """Read one family's fragment directory, which is laid out exactly as ``casillas`` is."""
    header = _family_header(section)
    fragments: list[_MemberFragment] = []
    for path in sorted((edition_dir / section).glob("*.toml")):
        preamble, texts = _edition_delta_source._split_blocks(path.read_text(encoding="utf-8"), header)
        blocks = tuple(
            _edition_delta_source._Block(text, _edition_delta_source._block_row(text, section)) for text in texts
        )
        fragments.append(_MemberFragment(path, preamble, blocks))
    return tuple(fragments)


def _identity_of(member: Mapping[str, object], family: _edition_delta_drop_scope._DroppableFamily) -> str | None:
    value = member.get(family.identity)
    return value if isinstance(value, str) else None


def _materialised_members(table: Mapping[str, object], section: str) -> tuple[_edition_delta_source._Row, ...]:
    raw = table.get(section, ())
    return tuple(_edition_delta_source._as_row(member) for member in (raw if isinstance(raw, list | tuple) else ()))


def _stated_identity(
    member: Mapping[str, object],
    family: _edition_delta_drop_scope._DroppableFamily,
    revision_id: str,
    seen: set[str],
    state: _FamilyDropState,
) -> str | None:
    identity = _identity_of(member, family)
    if identity is None:
        if family.section == _edition_delta_fields._CASILLAS:
            state.kept_no_identity += 1
            return None
        raise _edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r}: states a {family.section} member carrying no {family.identity!r}, so it "
            "cannot be matched to an inherited member",
        )
    if identity in seen:
        raise _edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r}: states more than one {family.section} member under {family.identity} "
            f"{identity!r}, so neither can be said to restate the inherited member",
        )
    seen.add(identity)
    return identity


def _identity_fields_match(
    member: Mapping[str, object],
    candidate: Mapping[str, object],
    family: _edition_delta_drop_scope._DroppableFamily,
) -> bool:
    return all(
        family_identity_value(member, name) == family_identity_value(candidate, name) for name in family.identity_fields
    )


def _comparable_member(
    member: Mapping[str, object], family: _edition_delta_drop_scope._DroppableFamily, revision_id: str, identity: str
) -> object:
    compared = (
        _edition_delta_source._as_row(without_lineage_claims(member))
        if family.section == _edition_delta_fields._CASILLAS
        else member
    )
    return _edition_delta_chain_materialisation.comparable(
        compared, revision_id=revision_id, path=f"{family.section}.{identity}"
    )


def _drop_attestation(
    member: Mapping[str, object],
    family: _edition_delta_drop_scope._DroppableFamily,
    revision_id: str,
    predecessor_revision_id: str,
    manifest: Mapping[str, object],
) -> LineageAttestation | bool | None:
    needs_attestation = family.section == _edition_delta_fields._CASILLAS and any(
        claim in member for claim in LINEAGE_CLAIM_FIELDS
    )
    if not needs_attestation:
        return None
    attestation = _edition_delta_lineage_attestation._lineage_attestation(
        member=member,
        manifest=manifest,
        predecessor_revision_id=predecessor_revision_id,
        revision_id=revision_id,
    )
    return attestation if attestation is not None else False


def _record_candidate_match(
    member: Mapping[str, object],
    candidate: Mapping[str, object],
    family: _edition_delta_drop_scope._DroppableFamily,
    revision_id: str,
    predecessor_revision_id: str,
    manifest: Mapping[str, object],
    identity: str,
    state: _FamilyDropState,
) -> None:
    if not _identity_fields_match(member, candidate, family):
        state.kept_differs.append(identity)
        return
    left = _comparable_member(member, family, revision_id, identity)
    right = _comparable_member(candidate, family, revision_id, identity)
    if left != right:
        state.kept_differs.append(identity)
        return
    attestation = _drop_attestation(member, family, revision_id, predecessor_revision_id, manifest)
    if attestation is False:
        state.kept_pinned.append(identity)
        return
    if isinstance(attestation, LineageAttestation):
        state.lineage_attestations.append(attestation)
    state.dropped.append(identity)


def _plan_family_drop(
    *,
    family: _edition_delta_drop_scope._DroppableFamily,
    revision_id: str,
    predecessor_revision_id: str,
    manifest: Mapping[str, object],
    stated: Sequence[_edition_delta_source._Block],
    inherited: Sequence[_edition_delta_source._Row],
) -> FamilyDrop:
    """Decide which of one family's stated members restate exactly what the edition would inherit.

    The equality is exact over the member's whole table, with nothing set aside.
    A census counts a member restated with ``source_refs`` and ``legal_refs``
    held apart, because it is measuring what the union could eventually absorb;
    that is a larger population than this one. References are part of what
    materialises, so a member whose references differ is not a restatement here
    however alike the rest of it reads.

    Raises:
        MigrationRefusedError: When a stated member carries no identity, or the
            edition states two members under one identity, either of which would
            make the member that supersedes the inherited one a guess.
    """
    by_identity: dict[str, list[_edition_delta_source._Row]] = {}
    for member in inherited:
        identity = _identity_of(member, family)
        if identity is not None:
            by_identity.setdefault(identity, []).append(member)
    state = _FamilyDropState()
    seen: set[str] = set()
    for block in stated:
        member = block.row
        identity = _stated_identity(member, family, revision_id, seen, state)
        if identity is None:
            continue
        candidates = by_identity.get(identity, [])
        if len(candidates) != 1:
            state.kept_new.append(identity)
            continue
        _record_candidate_match(
            member,
            candidates[0],
            family,
            revision_id,
            predecessor_revision_id,
            manifest,
            identity,
            state,
        )
    return FamilyDrop(
        section=family.section,
        dropped=tuple(state.dropped),
        kept_new=tuple(state.kept_new),
        kept_differs=tuple(state.kept_differs),
        kept_pinned=tuple(state.kept_pinned),
        lineage_attestations=tuple(state.lineage_attestations),
        kept_no_identity=state.kept_no_identity,
    )


def _plan_edition_drop(
    modelo_dir: Path,
    revision_id: str,
    *,
    families: Sequence[_edition_delta_drop_scope._DroppableFamily],
) -> EditionDrop:
    """Decide what one edition would stop stating, reading the tree and writing nothing."""
    edition_dir = modelo_dir / "revisions" / revision_id
    source = _edition_delta_source._read_edition(modelo_dir, revision_id)
    predecessor = _edition_delta_drop_scope._declared_predecessor(source.manifest)
    baselines = {
        family.section: _edition_delta_drop_scope._family_storage_baseline(source.manifest, family.section)
        for family in families
    }
    if not any(baselines.values()):
        return EditionDrop(
            revision_id=revision_id,
            predecessor=None,
            skipped="root edition: inherits nothing, so it states no restatement",
            families=(),
        )
    inherited_tables: dict[str, Mapping[str, object]] = {}
    drops: list[FamilyDrop] = []
    for family in families:
        baseline = baselines[family.section]
        if baseline is None:
            continue
        stated = [
            block for fragment in _read_family_fragments(edition_dir, family.section) for block in fragment.blocks
        ]
        if not stated:
            continue
        if baseline not in inherited_tables:
            inherited_tables[baseline] = _edition_delta_source._read_edition(modelo_dir, baseline).table
        drop = _plan_family_drop(
            family=family,
            revision_id=revision_id,
            predecessor_revision_id=baseline,
            manifest=source.manifest,
            stated=stated,
            inherited=_materialised_members(inherited_tables[baseline], family.section),
        )
        if drop.stated:
            drops.append(drop)
    return EditionDrop(revision_id=revision_id, predecessor=predecessor, skipped=None, families=tuple(drops))


def plan_drop(
    modelo_dir: Path,
    definition: ModeloDefinition,
    *,
    families: Sequence[_edition_delta_drop_scope._DroppableFamily] = _edition_delta_drop_scope._DROPPABLE_FAMILIES,
) -> DropPlan:
    """Decide every edition's droppable restatement for one modelo, writing nothing."""
    return DropPlan(
        modelo_id=str(definition.id),
        editions=tuple(
            _plan_edition_drop(modelo_dir, str(revision.id), families=families)
            for revision in ordered_revisions(definition)
        ),
    )
