"""Storage-baseline eligibility and raw-overlap diagnostics for registry collapse verification."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from cadrumo.domain.calculations.registry.keyed_families import (
    CANONICAL_FAMILY_SPECS,
    KeyedFamilySpec,
    inline_family_source_default,
)
from cadrumo.domain.calculations.registry.revision_order import revisions_coexist
from cadrumo.domain.calculations.registry.schema import (
    ModeloRevision,
)
from cadrumo.domain.calculations.registry.temporal import (
    RevisionSelectionMetadata,
)
from dev.registry.compiler.loader import load_modelo_declarations
from dev.registry.edition_delta_assessment_lineage import technical_root

from .registry_collapse_models import _REPRESENTATION_ONLY, RootEligibility
from .registry_collapse_values import _same_typed_value


def _with_family_source_default(raw_revision: Mapping[str, object], section: str) -> object:
    """Return one family's raw members with the edition's ``source_refs`` default bound as the loader binds it.

    Selection metadata validates each member's grounding, so a member relying on
    its edition's family default must carry that default before validation, or
    the revision is reported unresolved for a reference the loader supplies. A
    malformed family is passed through for validation to refuse.
    """
    members = raw_revision.get(section, ())
    if not isinstance(members, list | tuple):
        return members
    spec = next(spec for spec in CANONICAL_FAMILY_SPECS if spec.section == section)
    return tuple(
        inline_family_source_default(member, raw_revision, spec.source_default_key)
        if isinstance(member, Mapping)
        else member
        for member in members
    )


def root_eligibility(modelo_dir: Path) -> tuple[Mapping[str, object], ...]:
    """Classify every revision/family edge without treating an explicit root as invisible."""
    try:
        declarations = load_modelo_declarations(modelo_dir).get("revisions", {})
    except Exception as exc:  # each modelo must still receive an outcome
        return ({"revision": "*", "family": "*", "status": RootEligibility.UNRESOLVED, "detail": str(exc)},)
    if not isinstance(declarations, Mapping):
        return (
            {
                "revision": "*",
                "family": "*",
                "status": RootEligibility.UNRESOLVED,
                "detail": "revisions is not a mapping",
            },
        )
    metadata, invalid = _revision_metadata(cast(Mapping[str, object], declarations))
    ordered = sorted(metadata, key=lambda item: (item.valid_from, str(item.id)))
    rows: list[Mapping[str, object]] = []
    previous = None
    for revision in ordered:
        revision_id = str(revision.id)
        raw = declarations.get(revision_id)
        rows.extend(_revision_family_eligibility(revision_id, revision, raw, previous))
        previous = revision
    rows.extend(_invalid_revision_eligibility(invalid))
    return tuple(rows)


def _revision_metadata(
    declarations: Mapping[str, object],
) -> tuple[list[RevisionSelectionMetadata], dict[str, str]]:
    metadata: list[RevisionSelectionMetadata] = []
    invalid: dict[str, str] = {}
    for revision_id, raw_revision in declarations.items():
        if not isinstance(raw_revision, Mapping):
            invalid[str(revision_id)] = "revision is not a mapping"
            continue
        try:
            metadata.append(_validated_revision_metadata(str(revision_id), raw_revision))
        except Exception as exc:
            invalid[str(revision_id)] = f"{type(exc).__name__}: {exc}"
    return metadata, invalid


def _validated_revision_metadata(
    revision_id: str,
    raw_revision: Mapping[str, object],
) -> RevisionSelectionMetadata:
    return RevisionSelectionMetadata.model_validate(
        {
            "id": revision_id,
            "valid_from": raw_revision.get("valid_from"),
            "valid_to": raw_revision.get("valid_to"),
            "period_selector": raw_revision.get("period_selector"),
            "deadline_windows": _with_family_source_default(raw_revision, "deadline_windows"),
            "filing_schedules": _with_family_source_default(raw_revision, "filing_schedules"),
        }
    )


def _family_root_eligibility(
    revision_id: str,
    revision: RevisionSelectionMetadata,
    raw: object,
    previous: RevisionSelectionMetadata | None,
    *,
    section: str,
    inherited: bool,
) -> Mapping[str, object]:
    family_baseline = "casilla_storage_baseline" if section == "casillas" else "family_storage_baseline"
    baseline = raw.get(family_baseline) if isinstance(raw, Mapping) else None
    predecessor = raw.get("predecessor") if isinstance(raw, Mapping) else None
    named = baseline if isinstance(baseline, str) else predecessor if isinstance(predecessor, str) else None
    explicit_root = isinstance(predecessor, Mapping)
    if previous is None:
        status, candidate = RootEligibility.FIRST_REVISION, None
    elif named is not None:
        status, candidate = RootEligibility.EXISTING_INHERITANCE, named
    elif _is_incompatible_root(previous, revision, raw, explicit_root, inherited):
        status, candidate = RootEligibility.INCOMPATIBLE, str(previous.id)
    elif not isinstance(raw, Mapping):
        status, candidate = RootEligibility.UNRESOLVED, str(previous.id)
    else:
        status, candidate = RootEligibility.CANDIDATE, str(previous.id)
    return {
        "revision": revision_id,
        "family": section,
        "status": status,
        "candidate": candidate,
        "explicit_root": explicit_root,
    }


def _is_incompatible_root(
    previous: RevisionSelectionMetadata,
    revision: RevisionSelectionMetadata,
    raw: object,
    explicit_root: bool,
    inherited: bool,
) -> bool:
    return (
        (explicit_root and not technical_root(cast(Mapping[str, object], raw)))
        or revisions_coexist(cast("ModeloRevision", previous), cast("ModeloRevision", revision))
        or not inherited
    )


def _revision_family_eligibility(
    revision_id: str,
    revision: RevisionSelectionMetadata,
    raw: object,
    previous: RevisionSelectionMetadata | None,
) -> tuple[Mapping[str, object], ...]:
    return tuple(
        _family_root_eligibility(
            revision_id,
            revision,
            raw,
            previous,
            section=spec.section,
            inherited=spec.inherited,
        )
        for spec in CANONICAL_FAMILY_SPECS
    )


def _invalid_revision_eligibility(invalid: Mapping[str, str]) -> tuple[Mapping[str, object], ...]:
    return tuple(
        {
            "revision": revision_id,
            "family": spec.section,
            "status": RootEligibility.UNRESOLVED,
            "candidate": None,
            "explicit_root": False,
            "detail": detail,
        }
        for revision_id, detail in sorted(invalid.items())
        for spec in CANONICAL_FAMILY_SPECS
    )


def _raw_members(value: object, *, singleton: bool) -> tuple[Mapping[str, object], ...]:
    if singleton:
        return (cast(Mapping[str, object], value),) if isinstance(value, Mapping) else ()
    if not isinstance(value, list | tuple):
        return ()
    return tuple(cast(Mapping[str, object], item) for item in value if isinstance(item, Mapping))


def _raw_leaves(value: object, prefix: tuple[str, ...] = ()) -> dict[tuple[str, ...], object]:
    if not isinstance(value, Mapping) or not value:
        return {prefix: value}
    leaves: dict[tuple[str, ...], object] = {}
    for key, child in value.items():
        leaves.update(_raw_leaves(child, (*prefix, str(key))))
    return leaves


def root_overlap_diagnostics(
    modelo_dir: Path,
    eligibility: Sequence[Mapping[str, object]] | None = None,
) -> tuple[Mapping[str, object], ...]:
    """Expose same-storage-id root overlap as diagnostic evidence, never accepted identity."""
    declarations = load_modelo_declarations(modelo_dir).get("revisions", {})
    if not isinstance(declarations, Mapping):
        return ()
    declarations = cast(Mapping[str, object], declarations)
    rows = root_eligibility(modelo_dir) if eligibility is None else eligibility
    specs = {spec.section: spec for spec in CANONICAL_FAMILY_SPECS}
    findings: list[Mapping[str, object]] = []
    for row in rows:
        target = _root_overlap_target(row, declarations, specs)
        if target is None:
            continue
        revision_id, family, spec, current, baseline = target
        old = _baseline_members(baseline.get(family), spec.storage_identity, spec.singleton)
        findings.extend(
            finding
            for member in _raw_members(current.get(family), singleton=spec.singleton)
            if (finding := _root_member_overlap(revision_id, family, spec.storage_identity, member, old)) is not None
        )
    return tuple(findings)


def _root_overlap_target(
    row: Mapping[str, object],
    declarations: Mapping[str, object],
    specs: Mapping[str, KeyedFamilySpec],
) -> tuple[str, str, KeyedFamilySpec, Mapping[str, object], Mapping[str, object]] | None:
    if row.get("status") is not RootEligibility.CANDIDATE:
        return None
    revision_id, baseline_id, family = row.get("revision"), row.get("candidate"), row.get("family")
    if not all(isinstance(value, str) for value in (revision_id, baseline_id, family)):
        return None
    spec = specs.get(cast(str, family))
    current, baseline = declarations.get(revision_id), declarations.get(baseline_id)
    if spec is None or not isinstance(current, Mapping) or not isinstance(baseline, Mapping):
        return None
    return (
        cast(str, revision_id),
        cast(str, family),
        spec,
        cast(Mapping[str, object], current),
        cast(Mapping[str, object], baseline),
    )


def _baseline_members(
    value: object,
    storage_identity: str,
    singleton: bool,
) -> Mapping[str, Mapping[str, object]]:
    return {
        str(item.get(storage_identity)): item
        for item in _raw_members(value, singleton=singleton)
        if item.get(storage_identity) is not None
    }


def _root_member_overlap(
    revision_id: str,
    family: str,
    storage_identity: str,
    member: Mapping[str, object],
    baseline: Mapping[str, Mapping[str, object]],
) -> Mapping[str, object] | None:
    identity = member.get(storage_identity)
    inherited = baseline.get(str(identity))
    if identity is None or inherited is None:
        return None
    fields = _equal_raw_overlap_fields(member, inherited, storage_identity)
    if not fields:
        return None
    return {
        "revision": revision_id,
        "family": family,
        "member": str(identity),
        "fields": fields,
        "reason": "raw same-storage-id overlap requires baseline conversion proof",
    }


def _equal_raw_overlap_fields(
    member: Mapping[str, object],
    inherited: Mapping[str, object],
    storage_identity: str,
) -> list[str]:
    left, right = _raw_leaves(member), _raw_leaves(inherited)
    return sorted(
        ".".join(path)
        for path, value in left.items()
        if path
        and path[0] not in _REPRESENTATION_ONLY | {storage_identity}
        and path in right
        and _same_typed_value(value, right[path])
    )


def _root_gaps(rows: Sequence[Mapping[str, object]]) -> tuple[Mapping[str, object], ...]:
    return tuple(row for row in rows if row.get("status") in {RootEligibility.CANDIDATE, RootEligibility.UNRESOLVED})
