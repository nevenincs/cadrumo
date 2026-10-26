"""Validate authored revision shape before measuring registry families."""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.keyed_families import CANONICAL_FAMILY_SPECS
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from .edition_delta_source import _members

_OPERATION_SECTIONS = {
    "casilla_overrides",
    "casilla_removals",
    "casilla_positions",
    "family_overrides",
    "family_removals",
    "family_positions",
    "cleared_families",
    "scoped_families",
}
_FAMILY_SECTIONS = {spec.section for spec in CANONICAL_FAMILY_SPECS}


def authored_shape_findings(raw_revisions: Mapping[str, object]) -> list[Mapping[str, object]]:
    """Report revisions, families, operations and scope fields whose authored shape the assessor cannot measure."""
    findings: list[Mapping[str, object]] = []
    for revision_id, raw_revision in raw_revisions.items():
        findings.extend(_revision_findings(str(revision_id), raw_revision))
    return findings


def _revision_findings(revision_id: str, raw_revision: object) -> list[Mapping[str, object]]:
    if not isinstance(raw_revision, Mapping):
        return [{"revision": revision_id, "family": "*", "reason": "revision_shape_unsupported"}]
    findings = _family_shape_findings(revision_id, raw_revision)
    findings.extend(_operation_shape_findings(revision_id, raw_revision))
    findings.extend(_scope_shape_findings(revision_id, raw_revision))
    return findings


def _family_shape_findings(revision_id: str, raw_revision: Mapping[str, object]) -> list[Mapping[str, object]]:
    return [
        {"revision": revision_id, "family": spec.section, "reason": "authored_shape_unsupported"}
        for spec in CANONICAL_FAMILY_SPECS
        if _members(raw_revision, spec.section, singleton=spec.singleton) is None
    ]


def _operation_shape_findings(revision_id: str, raw_revision: Mapping[str, object]) -> list[Mapping[str, object]]:
    return [
        {"revision": revision_id, "family": section, "reason": "operation_shape_unsupported"}
        for section in _OPERATION_SECTIONS
        if raw_revision.get(section) is not None and not isinstance(raw_revision.get(section), list | tuple)
    ]


def _scope_shape_findings(revision_id: str, raw_revision: Mapping[str, object]) -> list[Mapping[str, object]]:
    return [
        {"revision": revision_id, "family": str(section), "reason": "scope_field_unsupported"}
        for section in raw_revision
        if section not in _FAMILY_SECTIONS | _OPERATION_SECTIONS and section not in ModeloRevision.model_fields
    ]


__all__ = ("authored_shape_findings",)
