"""Lineage attestations required by casilla row relocation."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation

from . import edition_delta_fields as _edition_delta_fields


def _source_refs(member: Mapping[str, object], manifest: Mapping[str, object]) -> object:
    source_refs = member.get(_edition_delta_fields._ROW_SOURCE)
    if isinstance(source_refs, list | tuple) and source_refs:
        return source_refs
    default_refs = manifest.get("casilla_source_refs")
    additions = member.get(_edition_delta_fields._ROW_SOURCE_ADDITIONS)
    return tuple(default_refs if isinstance(default_refs, list | tuple) else ()) + tuple(
        additions if isinstance(additions, list | tuple) else ()
    )


def _legal_refs(member: Mapping[str, object], manifest: Mapping[str, object]) -> object:
    legal_refs = member.get(_edition_delta_fields._ROW_LEGAL)
    if isinstance(legal_refs, list | tuple) and legal_refs:
        return legal_refs
    return manifest.get("orden_aplicabilidad")


def _lineage_attestation(
    *,
    member: Mapping[str, object],
    manifest: Mapping[str, object],
    predecessor_revision_id: str,
    revision_id: str,
) -> LineageAttestation | None:
    """Build the canonical carrier for one row-authored continuity claim.

    ``None`` means the claim cannot be represented without inventing missing
    grounding.  Callers keep that row stated in that case.
    """
    identity = member.get(_edition_delta_fields._LINEAGE)
    if not isinstance(identity, str):
        return None
    raw_attestation = {
        "family": _edition_delta_fields._CASILLAS,
        "continuidad_id": identity,
        "from_revision": predecessor_revision_id,
        "to_revision": revision_id,
        "origin": member.get("continuidad_origin"),
        "evidence": member.get("continuidad_evidence"),
        "legal_refs": _tuple_if_sequence(_legal_refs(member, manifest)),
        "source_refs": _tuple_if_sequence(_source_refs(member, manifest)),
    }
    try:
        return LineageAttestation.model_validate(raw_attestation)
    except ValidationError:
        return None


def _tuple_if_sequence(value: object) -> object:
    return tuple(value) if isinstance(value, list | tuple) else value
