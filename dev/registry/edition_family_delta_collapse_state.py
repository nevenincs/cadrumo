"""Mutable working state for the keyed-family representation conversion."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path

from cadrumo.domain.calculations.registry.keyed_families import KeyedFamilySpec
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision


@dataclass(slots=True)
class CollapseInput:
    """One modelo's source digest, typed definition, authored, resolved and candidate revision tables."""

    source_digest: str
    before: ModeloDefinition
    source_raw: Mapping[str, object]
    resolved: Mapping[str, object]
    candidate_raw: Mapping[str, object]


@dataclass(slots=True)
class RevisionState:
    """One candidate revision's parsed manifest, family operations and pending writes during collapse."""

    before: ModeloDefinition
    typed_revision: ModeloRevision
    revision_id: str
    predecessor_id: str
    current: Mapping[str, object]
    predecessor: Mapping[str, object]
    revision_dir: Path
    manifest_path: Path
    manifest: MutableMapping[str, object]
    revision: MutableMapping[str, object]
    overrides: list[object]
    removals: list[object]
    positions: list[object]
    restated_sections: set[str]
    scoped_families: list[str]
    period_selector: object
    counts: list[dict[str, object]]
    revision_changed: bool = False


@dataclass(slots=True)
class FamilyState:
    """Predecessor and successor members of one keyed family, matched by its declared identity field."""

    spec: KeyedFamilySpec
    identity: str
    old_members: tuple[Mapping[str, object], ...]
    new_members: tuple[Mapping[str, object], ...]
    old: dict[str, Mapping[str, object]]
    new: dict[str, Mapping[str, object]]
    authored_order: list[str]
    authored_ids: set[str]
    replacements: dict[str, str]
    additions: set[str]
    keep: set[str]
    common: dict[str, str]
    existing_override_ids: set[str]
    existing_removal_ids: set[str]
    overrides_before: int
    removals_before: int


@dataclass(slots=True)
class FamilyCounts:
    """Override, payload and sequence-operation tallies accumulated while collapsing one family."""

    overrides: int = 0
    payload: int = 0
    sequence_additions: int = 0
    sequence_removals: int = 0
    sequence_order: int = 0


@dataclass(slots=True)
class FamilyChange:
    """The authored-payload and structural measurements of one family's collapse."""

    family_overrides: int
    additions: int
    removals: int
    sequence_additions: int
    sequence_removals: int
    sequence_order_positions: int
    structural_overhead: int
    authored_payload_fields_before: int
    authored_payload_fields_after: int

    def report(self, revision_id: str, family: str) -> dict[str, object]:
        """Render this change as the per-revision, per-family report row."""
        return {
            "revision": revision_id,
            "family": family,
            "authored_payload_fields_before": self.authored_payload_fields_before,
            "authored_payload_fields_after": self.authored_payload_fields_after,
            "overrides": self.family_overrides,
            "additions": self.additions,
            "removals": self.removals,
            "sequence_additions": self.sequence_additions,
            "sequence_removals": self.sequence_removals,
            "sequence_order_positions": self.sequence_order_positions,
            "structural_overhead": self.structural_overhead,
        }


__all__ = ("CollapseInput", "FamilyChange", "FamilyCounts", "FamilyState", "RevisionState")
