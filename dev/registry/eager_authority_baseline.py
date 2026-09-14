"""Development-only eager JSON baseline for indexed-authority measurements."""

from __future__ import annotations

import json
import os
from base64 import b64decode, b64encode
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path, PurePath
from typing import cast, get_args

from pydantic import BaseModel, ValidationError

from cadrumo.core.atomic_write import hardened_staged_publication
from cadrumo.core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant, sha256_hex
from cadrumo.core.identity.documents import TAX_ID_FORMAT_CONTEXT
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityBuildIdentity,
    AuthorityEvidenceProjection,
    PublishedLegalEvidence,
    PublishedSourceEvidence,
)
from cadrumo.domain.calculations.registry.facts.schema import (
    TAGGED_FACT_ATOM_CONTEXT,
    FactAtomField,
    GovernedFactCatalogue,
    OptionalFactAtomField,
    tagged_fact_atom_json,
)
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from cadrumo.domain.calculations.registry.provenance import NormativeCorpusProvenance
from cadrumo.domain.calculations.registry.revision_contracts import DeclaredPredecessor, NoPredecessor
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.tax_id_format import tax_id_format_from_catalogue

_FORMAT = "cadrumo-development-eager-authority-v1"
_TAGGED_CONTEXT = {TAGGED_FACT_ATOM_CONTEXT: True}
_FACT_ATOM_VALIDATORS = frozenset((get_args(FactAtomField)[1], get_args(OptionalFactAtomField)[1]))


class EagerAuthorityBaselineError(ValueError):
    """The explicit development comparison baseline is invalid or unavailable."""


def write_eager_authority_baseline(path: Path, artifact: AuthorityArtifact) -> None:
    """Write canonical eager bytes from the same validated artifact as SQLite."""
    artifact.catalogues.runtime.require_complete()
    artifact.require_evidence_closure()
    tax_id_format_from_catalogue(artifact.catalogues.facts)
    payload = _artifact_document(artifact)
    encoded = canonical_json_bytes(
        {"format": _FORMAT, "payload": payload, "payload_sha256": sha256_hex(canonical_json_bytes(payload))}
    )
    read_eager_authority_baseline_bytes(encoded)
    path.parent.mkdir(parents=True, exist_ok=True)
    with hardened_staged_publication(path) as publication:
        with publication.path.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        publication.publish()


def read_eager_authority_baseline(path: Path) -> AuthorityArtifact:
    """Read one explicit baseline; no bundled or runtime fallback exists."""
    try:
        return read_eager_authority_baseline_bytes(path.read_bytes())
    except OSError as exc:
        raise EagerAuthorityBaselineError(f"eager authority baseline is unavailable at {path}") from exc


def read_eager_authority_baseline_bytes(raw: bytes) -> AuthorityArtifact:
    """Strictly decode one canonical development-only baseline frame."""
    try:
        frame = json.loads(raw, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant)
        if not isinstance(frame, dict) or set(frame) != {"format", "payload", "payload_sha256"}:
            raise ValueError("unexpected eager baseline frame")
        if frame["format"] != _FORMAT or not isinstance(frame["payload"], dict):
            raise ValueError("unsupported eager baseline format")
        payload = cast(dict[str, object], frame["payload"])
        if frame["payload_sha256"] != sha256_hex(canonical_json_bytes(payload)):
            raise ValueError("eager baseline content digest mismatch")
        return _artifact_from_document(payload)
    except (ValidationError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise EagerAuthorityBaselineError("eager authority baseline failed strict decoding") from exc


def published_authority(path: Path) -> ValidatedRegistryAuthority:
    """Materialise the complete eager graph used only for paired measurement."""
    artifact = read_eager_authority_baseline(path)
    return ValidatedRegistryAuthority.from_validated_components(
        modelos=artifact.modelos,
        catalogues=artifact.catalogues,
        identity_digest=artifact.identity_digest,
        evidence=artifact.evidence,
        profile_schema=artifact.profile_schema,
    )


def _artifact_document(artifact: AuthorityArtifact) -> dict[str, object]:
    return {
        "modelos": [_json_value(modelo) for modelo in artifact.modelos],
        "catalogues": _json_value(artifact.catalogues),
        "identity_digest": artifact.identity_digest,
        "build_identity": {
            "source_identity_digest": artifact.build_identity.source_identity_digest,
            "compiler_identity_digest": artifact.build_identity.compiler_identity_digest,
            "component_dependency_digest": artifact.build_identity.component_dependency_digest,
        },
        "evidence": {
            "legal": [
                {
                    "legal_reference_id": item.legal_reference_id,
                    "anchored_text": item.anchored_text,
                    "text_sha256": item.text_sha256,
                    "provenance": item.provenance.value,
                }
                for item in artifact.evidence.legal
            ],
            "sources": [
                {
                    "source_reference_id": item.source_reference_id,
                    "payload_base64": b64encode(item.payload).decode("ascii"),
                    "payload_sha256": item.payload_sha256,
                }
                for item in artifact.evidence.sources
            ],
        },
        "profile_schema": _json_value(artifact.profile_schema),
    }


def _artifact_from_document(payload: Mapping[str, object]) -> AuthorityArtifact:
    required = {"modelos", "catalogues", "identity_digest", "build_identity", "evidence", "profile_schema"}
    if set(payload) != required:
        raise ValueError("unexpected eager baseline payload")
    modelos_document = _sequence(payload, "modelos")
    catalogues_document = _mapping(payload, "catalogues")
    identity_digest = _string(payload, "identity_digest")
    build_document = _mapping(payload, "build_identity")
    evidence_document = _mapping(payload, "evidence")
    facts = GovernedFactCatalogue.model_validate(_mapping(catalogues_document, "facts"), context=_TAGGED_CONTEXT)
    decode_context = {**_TAGGED_CONTEXT, TAX_ID_FORMAT_CONTEXT: tax_id_format_from_catalogue(facts)}
    with validating_governed_facts(CandidateFactAuthority(facts, authority_digest=identity_digest)):
        modelos = tuple(
            ModeloDefinition.model_validate(_mapping_item(item), context=decode_context) for item in modelos_document
        )
        catalogues = RegistryCatalogues.model_validate({**catalogues_document, "facts": facts}, context=decode_context)
    legal = tuple(
        PublishedLegalEvidence(
            legal_reference_id=_string(row := _mapping_item(item), "legal_reference_id"),
            anchored_text=_string(row, "anchored_text"),
            text_sha256=_string(row, "text_sha256"),
            provenance=NormativeCorpusProvenance(_string(row, "provenance")),
        )
        for item in _sequence(evidence_document, "legal")
    )
    sources = tuple(
        PublishedSourceEvidence(
            source_reference_id=_string(row := _mapping_item(item), "source_reference_id"),
            payload=b64decode(_string(row, "payload_base64").encode("ascii"), validate=True),
            payload_sha256=_string(row, "payload_sha256"),
        )
        for item in _sequence(evidence_document, "sources")
    )
    from cadrumo.domain.user_profile.schema import ProfileSchemaDefinition

    artifact = AuthorityArtifact(
        modelos=modelos,
        catalogues=catalogues,
        identity_digest=identity_digest,
        build_identity=AuthorityBuildIdentity(
            _string(build_document, "source_identity_digest"),
            _string(build_document, "compiler_identity_digest"),
            _string(build_document, "component_dependency_digest"),
        ),
        evidence=AuthorityEvidenceProjection(legal=legal, sources=sources),
        profile_schema=ProfileSchemaDefinition.model_validate(payload["profile_schema"]),
    )
    artifact.catalogues.runtime.require_complete()
    artifact.require_evidence_closure()
    return artifact


def _json_value(value: object) -> object:
    if isinstance(value, DeclaredPredecessor | NoPredecessor):
        return _json_value(value.model_dump(mode="json"))
    if isinstance(value, BaseModel):
        if type(value).__pydantic_decorators__.model_serializers:
            return _json_value(value.model_dump(mode="python"))
        return {
            field_name: (
                tagged_fact_atom_json(getattr(value, field_name))
                if _FACT_ATOM_VALIDATORS.intersection(field.metadata)
                else _json_value(getattr(value, field_name))
            )
            for field_name, field in type(value).model_fields.items()
            if not _field_equals_declared_default(value, field_name)
        }
    if isinstance(value, Mapping):
        return {_json_key(key): _json_value(item) for key, item in cast(Mapping[object, object], value).items()}
    if isinstance(value, (frozenset, set)):
        return sorted(
            (_json_value(item) for item in cast(set[object] | frozenset[object], value)),
            key=canonical_json_bytes,
        )
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in cast(Sequence[object], value)]
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, PurePath):
        return value.as_posix()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"eager authority baseline cannot serialize {type(value).__name__}")


def _field_equals_declared_default(model: BaseModel, field_name: str) -> bool:
    if field_name == "kind":
        return False
    field = type(model).model_fields[field_name]
    if field.is_required():
        return False
    try:
        comparison = getattr(model, field_name) == field.get_default(call_default_factory=True)
    except (TypeError, ValueError):
        return False
    return comparison if isinstance(comparison, bool) else False


def _json_key(key: object) -> str:
    value = _json_value(key)
    if not isinstance(value, (str, int, float, bool)):
        raise TypeError("eager authority baseline mapping keys must be JSON scalar values")
    return str(value)


def _mapping(document: Mapping[str, object], key: str) -> Mapping[str, object]:
    return _mapping_item(document[key])


def _mapping_item(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("expected JSON object")
    return cast(dict[str, object], value)


def _sequence(document: Mapping[str, object], key: str) -> Sequence[object]:
    value = document[key]
    if not isinstance(value, list):
        raise ValueError("expected JSON array")
    return cast(list[object], value)


def _string(document: Mapping[str, object], key: str) -> str:
    value = document[key]
    if not isinstance(value, str):
        raise ValueError("expected JSON string")
    return value


__all__ = [
    "EagerAuthorityBaselineError",
    "published_authority",
    "read_eager_authority_baseline",
    "write_eager_authority_baseline",
]
