"""Canonical serialization and decoding for addressed authority components.

Core types: :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
"""

from __future__ import annotations

import json
from base64 import b64decode, b64encode
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import PurePath
from typing import Final, cast, get_args

from pydantic import BaseModel, TypeAdapter, ValidationError

from ....core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant
from ....core.identity.documents import TAX_ID_FORMAT_CONTEXT
from ....core.type_guards import (
    is_object_list_or_tuple,
    is_object_mapping,
    is_object_set_or_frozenset,
    is_str_keyed_dict,
)
from .authority_artifact import (
    AuthorityComponentCodecError,
    AuthorityComponentKind,
    AuthorityComponentQuery,
    EvidenceComponentQuery,
    ExportLayoutComponentQuery,
    FormLayoutComponentQuery,
    GovernedFactComponentQuery,
    ModeloDirectoryComponentQuery,
    ModeloRevisionComponentQuery,
    ProfileSchemaComponentQuery,
    PublishedLegalEvidence,
    PublishedSourceEvidence,
    ReferenceComponentQuery,
    RuntimeCatalogueComponentQuery,
    SnapshotGlobalsComponentQuery,
)
from .facts.atoms import TAGGED_FACT_ATOM_CONTEXT, FactAtomField, OptionalFactAtomField, tagged_fact_atom_json
from .facts.resolution import GovernedFactQuery, ResolvedGovernedFact
from .facts.schema import GovernedFact, GovernedFactCatalogue
from .governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from .provenance import NormativeCorpusProvenance
from .revision_contracts import DeclaredPredecessor, NoPredecessor
from .runtime_catalogues import RuntimeRegistryCatalogues
from .schema import ModeloRevision, SnapshotGlobalCatalogues, SupportedFilingYearsCatalogue
from .schema_exports import ExportLayoutDefinition
from .schema_form_layouts import FormLayoutDefinition
from .schema_references import TemporalSupportEnvelope
from .tax_id_format import tax_id_format_from_catalogue
from .temporal import ModeloRevisionDirectory

__all__ = ["decode_authority_component", "encode_authority_component"]

_FACT_ATOM_VALIDATORS: Final = frozenset(
    (get_args(FactAtomField)[1], get_args(OptionalFactAtomField)[1]),
)
_TAGGED_DECODE_CONTEXT: Final = {TAGGED_FACT_ATOM_CONTEXT: True}


def encode_authority_component(query: AuthorityComponentQuery, value: object) -> bytes:
    """Encode one typed component with the canonical authority value vocabulary."""
    try:
        payload: object
        if isinstance(value, PublishedLegalEvidence):
            payload = {
                "legal_reference_id": value.legal_reference_id,
                "anchored_text": value.anchored_text,
                "text_sha256": value.text_sha256,
                "provenance": value.provenance.value,
            }
        elif isinstance(value, PublishedSourceEvidence):
            payload = {
                "source_reference_id": value.source_reference_id,
                "payload_base64": b64encode(value.payload).decode("ascii"),
                "payload_sha256": value.payload_sha256,
            }
        else:
            payload = _json_value(value)
        return canonical_json_bytes(
            {"codec": "cadrumo-authority-component-v1", "kind": query.kind.value, "payload": payload}
        )
    except (TypeError, ValueError) as exc:
        raise AuthorityComponentCodecError(f"authority component {query!r} could not be encoded") from exc


def decode_authority_component(
    query: AuthorityComponentQuery,
    payload: bytes,
    *,
    dependencies: tuple[object, ...] = (),
    fact_query_observer: Callable[[GovernedFactQuery], None] | None = None,
) -> object:
    """Strictly decode one addressed component using only declared dependencies."""
    try:
        frame = _decode_json_object(payload, subject="authority component")
        _require_members(frame, {"codec", "kind", "payload"}, "component")
        if _required_string(frame, "codec") != "cadrumo-authority-component-v1":
            raise AuthorityComponentCodecError("authority component uses an unsupported codec")
        if _required_string(frame, "kind") != query.kind.value:
            raise AuthorityComponentCodecError("authority component kind does not match its query")
        document = frame["payload"]
        return _decode_typed_component(query, document, dependencies, fact_query_observer)
    except AuthorityComponentCodecError:
        raise
    except (ValidationError, TypeError, ValueError) as exc:
        raise AuthorityComponentCodecError(f"authority component {query!r} failed typed decoding") from exc


_FactQueryObserver = Callable[[GovernedFactQuery], None] | None
_ComponentDecoder = Callable[[AuthorityComponentQuery, object, tuple[object, ...], _FactQueryObserver], object]


def _decode_typed_component(
    query: AuthorityComponentQuery,
    document: object,
    dependencies: tuple[object, ...],
    fact_query_observer: _FactQueryObserver,
) -> object:
    decoder = _COMPONENT_DECODERS.get(type(query))
    if decoder is None:
        raise AuthorityComponentCodecError(f"unsupported authority component query {query!r}")
    return decoder(query, document, dependencies, fact_query_observer)


def _decode_profile_schema(
    _query: AuthorityComponentQuery,
    document: object,
    _dependencies: tuple[object, ...],
    _observer: _FactQueryObserver,
) -> object:
    from ...user_profile.schema import ProfileSchemaDefinition

    return ProfileSchemaDefinition.model_validate(document, strict=False)


def _decode_governed_fact(
    _query: AuthorityComponentQuery,
    document: object,
    _dependencies: tuple[object, ...],
    _observer: _FactQueryObserver,
) -> object:
    return GovernedFact.model_validate(document, strict=False, context=_TAGGED_DECODE_CONTEXT)


def _decode_modelo_revision(
    _query: AuthorityComponentQuery,
    document: object,
    dependencies: tuple[object, ...],
    fact_query_observer: _FactQueryObserver,
) -> object:
    facts = tuple(item for item in dependencies if isinstance(item, GovernedFact))
    fact_catalogue = GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts})
    tax_id_format = tax_id_format_from_catalogue(fact_catalogue)
    context = {**_TAGGED_DECODE_CONTEXT, TAX_ID_FORMAT_CONTEXT: tax_id_format}
    directories = tuple(item for item in dependencies if isinstance(item, ModeloRevisionDirectory))
    if len(directories) != 1 or directories[0].supported_filing_years is None:
        raise AuthorityComponentCodecError(
            "modelo revision component must depend on its directory's supported filing years"
        )
    candidate = CandidateFactAuthority(fact_catalogue, directories[0].supported_filing_years)
    source = _observed_authority(candidate, fact_query_observer)
    with validating_governed_facts(source):
        return ModeloRevision.model_validate(document, strict=False, context=context)


def _observed_authority(
    candidate: CandidateFactAuthority,
    fact_query_observer: _FactQueryObserver,
) -> CandidateFactAuthority | _ObservedFactAuthority:
    if fact_query_observer is None:
        return candidate
    return _ObservedFactAuthority(candidate, fact_query_observer)


def _decode_modelo_directory(
    _query: AuthorityComponentQuery,
    document: object,
    _dependencies: tuple[object, ...],
    _observer: _FactQueryObserver,
) -> object:
    return ModeloRevisionDirectory.model_validate(document, strict=False)


def _decode_runtime_catalogue(
    query: AuthorityComponentQuery,
    document: object,
    _dependencies: tuple[object, ...],
    _observer: _FactQueryObserver,
) -> object:
    runtime_query = cast(RuntimeCatalogueComponentQuery, query)
    field = RuntimeRegistryCatalogues.model_fields.get(runtime_query.family)
    if field is None or field.annotation is None:
        raise AuthorityComponentCodecError(f"unknown runtime catalogue family {runtime_query.family!r}")
    return TypeAdapter(field.annotation).validate_python(document, strict=False)


def _decode_snapshot_globals(
    _query: AuthorityComponentQuery,
    document: object,
    dependencies: tuple[object, ...],
    fact_query_observer: _FactQueryObserver,
) -> object:
    facts = tuple(item for item in dependencies if isinstance(item, GovernedFact))
    fact_catalogue = GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts})
    if not is_object_mapping(document):
        raise AuthorityComponentCodecError("snapshot globals component payload must be a mapping")
    support = SupportedFilingYearsCatalogue.model_validate(document.get("supported_filing_years"), strict=False)
    candidate = CandidateFactAuthority(fact_catalogue, support)
    source = _observed_authority(candidate, fact_query_observer)
    with validating_governed_facts(source):
        return SnapshotGlobalCatalogues.model_validate(document, strict=False)


def _decode_reference(
    query: AuthorityComponentQuery,
    document: object,
    _dependencies: tuple[object, ...],
    _observer: _FactQueryObserver,
) -> object:
    from .schema_references import LegalReference, SourceReference

    reference_query = cast(ReferenceComponentQuery, query)
    model = LegalReference if reference_query.kind is AuthorityComponentKind.LEGAL_REFERENCE else SourceReference
    return model.model_validate(document, strict=False)


def _decode_evidence(
    query: AuthorityComponentQuery,
    document: object,
    _dependencies: tuple[object, ...],
    _observer: _FactQueryObserver,
) -> object:
    evidence_query = cast(EvidenceComponentQuery, query)
    row = _mapping_item(document, "payload")
    if evidence_query.kind is AuthorityComponentKind.LEGAL_EVIDENCE:
        return _decode_legal_evidence(row)
    return _decode_source_evidence(row)


def _decode_legal_evidence(row: Mapping[str, object]) -> PublishedLegalEvidence:
    return PublishedLegalEvidence(
        legal_reference_id=_required_string(row, "legal_reference_id"),
        anchored_text=_required_string(row, "anchored_text"),
        text_sha256=_required_string(row, "text_sha256"),
        provenance=NormativeCorpusProvenance(_required_string(row, "provenance")),
    )


def _decode_source_evidence(row: Mapping[str, object]) -> PublishedSourceEvidence:
    return PublishedSourceEvidence(
        source_reference_id=_required_string(row, "source_reference_id"),
        payload=_decode_base64(_required_string(row, "payload_base64")),
        payload_sha256=_required_string(row, "payload_sha256"),
    )


def _decode_export_layout(
    _query: AuthorityComponentQuery,
    document: object,
    _dependencies: tuple[object, ...],
    _observer: _FactQueryObserver,
) -> object:
    return ExportLayoutDefinition.model_validate(document, strict=False)


def _decode_form_layout(
    _query: AuthorityComponentQuery,
    document: object,
    _dependencies: tuple[object, ...],
    _observer: _FactQueryObserver,
) -> object:
    return FormLayoutDefinition.model_validate(document, strict=False)


_COMPONENT_DECODERS: Final[dict[type[object], _ComponentDecoder]] = {
    ProfileSchemaComponentQuery: _decode_profile_schema,
    GovernedFactComponentQuery: _decode_governed_fact,
    ModeloRevisionComponentQuery: _decode_modelo_revision,
    ModeloDirectoryComponentQuery: _decode_modelo_directory,
    RuntimeCatalogueComponentQuery: _decode_runtime_catalogue,
    SnapshotGlobalsComponentQuery: _decode_snapshot_globals,
    ReferenceComponentQuery: _decode_reference,
    EvidenceComponentQuery: _decode_evidence,
    ExportLayoutComponentQuery: _decode_export_layout,
    FormLayoutComponentQuery: _decode_form_layout,
}


@dataclass(frozen=True, slots=True, weakref_slot=True)
class _ObservedFactAuthority:
    """Report the exact governed queries exercised by one component decode."""

    authority: CandidateFactAuthority
    observer: Callable[[GovernedFactQuery], None]

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        self.observer(query)
        return self.authority.resolve_governed_fact(query)

    def supported_filing_years(self) -> TemporalSupportEnvelope:
        return self.authority.supported_filing_years()


def _json_value(value: object) -> object:
    """Project registry values to JSON, omitting only schema-declared defaults."""
    if isinstance(value, DeclaredPredecessor | NoPredecessor):
        # The predecessor union intentionally owns a compact authored wire
        # dialect. Its serializer is a semantic projection, unlike ordinary
        # presentation serializers that may hide fields needed for authority
        # reconstruction.
        return _json_value(value.model_dump(mode="json"))
    if isinstance(value, BaseModel):
        return _json_model_value(value)
    return _json_non_model_value(value)


def _json_model_value(value: BaseModel) -> object:
    if type(value).__pydantic_decorators__.model_serializers:
        # A model that declares its own serialiser is authored in that shape,
        # and its parser accepts only that shape back.
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


def _json_non_model_value(value: object) -> object:
    if is_object_mapping(value):
        return {_json_key(key): _json_value(item) for key, item in value.items()}
    if is_object_set_or_frozenset(value):
        # Iteration order of a set follows per-process string hashing, so an
        # unordered collection is written in canonical-JSON order: the same
        # authority always publishes the same bytes.
        return sorted((_json_value(item) for item in value), key=canonical_json_bytes)
    if is_object_list_or_tuple(value):
        return [_json_value(item) for item in value]
    return _json_scalar_value(value)


def _json_scalar_value(value: object) -> object:
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
    raise TypeError(f"authority artifact cannot serialize {type(value).__name__}")


def _field_equals_declared_default(model: BaseModel, field_name: str) -> bool:
    """Return whether the schema explicitly permits this field to be omitted."""
    if field_name == "kind":
        # Registry discriminated unions use ``kind`` as their wire tag.  A
        # member commonly gives that Literal field a default so direct Python
        # construction stays ergonomic, but the parent union still requires
        # the tag when it rehydrates canonical JSON.
        return False
    field = type(model).model_fields[field_name]
    if field.is_required():
        return False
    try:
        comparison = getattr(model, field_name) == field.get_default(call_default_factory=True)
    except (TypeError, ValueError):
        # A context-sensitive default factory, or a value whose equality is not
        # scalar, is not sufficient authority to remove published information.
        return False
    return comparison if isinstance(comparison, bool) else False


def _json_key(key: object) -> str:
    """Project a mapping key through the JSON-safe value vocabulary."""
    value = _json_value(key)
    if not isinstance(value, (str, int, float, bool)):
        raise TypeError("authority artifact mapping keys must be JSON scalar values")
    return str(value)


def _decode_json_object(raw: bytes, *, subject: str) -> dict[str, object]:
    """Decode JSON while refusing duplicate names and non-finite values."""
    try:
        decoded = json.loads(raw, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant)
    except (TypeError, UnicodeDecodeError, ValueError) as exc:
        raise AuthorityComponentCodecError(f"{subject} is not valid canonical JSON") from exc
    if not is_str_keyed_dict(decoded):
        raise AuthorityComponentCodecError(f"{subject} must be a JSON object")
    return decoded


def _require_members(document: Mapping[str, object], expected: set[str], subject: str) -> None:
    """Refuse misspelled or unrecognized envelope fields before typed admission."""
    if set(document) != expected:
        raise AuthorityComponentCodecError(f"authority component {subject} has unexpected or missing members")


def _required_string(document: Mapping[str, object], field_name: str) -> str:
    """Return one non-empty string field or raise a format refusal."""
    value = document.get(field_name)
    if not isinstance(value, str) or not value:
        raise AuthorityComponentCodecError(f"authority component field {field_name!r} must be a non-empty string")
    return value


def _mapping_item(value: object, field_name: str) -> Mapping[str, object]:
    """Require one decoded JSON object."""
    if not is_str_keyed_dict(value):
        raise AuthorityComponentCodecError(f"authority component field {field_name!r} must be an object")
    return value


def _decode_base64(value: str) -> bytes:
    try:
        return b64decode(value.encode("ascii"), validate=True)
    except ValueError as exc:
        raise AuthorityComponentCodecError("authority component contains invalid base64 source evidence") from exc
