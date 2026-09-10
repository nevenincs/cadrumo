"""The reviewed semantics of a record design's slots, and the loader that compiles them.

The parser-read record design owns coordinates; this module owns the reviewed
registry meaning that is joined to them in a later generator step, and the
authored-fragment contract that meaning arrives in. Semantic-map fragments are
meaning-only authored inputs: the loader here owns their on-disk TOML shape and
compiles them, in filename order, into the canonical :class:`SemanticMap`. It
never reads an export layout, resolves catalogue references, matches an entry to
parser output, or uses a neighbouring generated tree as an oracle.

The compiled map and the loader that produces it are one contract, because the
callers that hold a map are the callers that ask for one: the generator, the
filing-export proof, the provenance manifest and the analysis screens each load
a map and then address its entries and anchors. Keeping the loader in a separate
private module left every one of them reaching past this boundary for the only
entry point that can build the thing this module describes.

Assembly detail stays private below: fragment discovery, per-fragment parsing and
collision refusal are this module's own, and nothing outside calls them.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Annotated, Final, Literal, cast

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.core.filing_projection_ref import (
    FilingProjectionRef,
    compile_filing_projection_ref,
    hydrate_filing_projection_ref,
)
from cadrumo.core.link_safety import is_link_like
from cadrumo.core.toml import freeze_toml, read_toml
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKindValue
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_semantics import (
    ExportComputedKey,
    ExportDraftAttribute,
    ExportSemanticPayloadAxis,
    export_semantic_payload_axis,
)
from cadrumo.domain.calculations.registry.ids import (
    BindingId,
    ExportFieldId,
    ModeloId,
    RecordId,
    SourceRefId,
)
from cadrumo.domain.calculations.registry.schema_base import LegalRefs, SourceRefs
from cadrumo.domain.calculations.registry.schema_exports import FilingEnvelopePrefixRole, RecordDiscriminator

from ._pydantic_error_detail import validation_error_detail
from .record_design_intermediate import AnchorKey, RecordKey

__all__ = [
    "SEMANTIC_MAP_FRAGMENT_SCHEMA_VERSION",
    "EnvelopePrefixField",
    "EnvelopeTotalAnchor",
    "FilingEnvelopePrefixRole",
    "SemanticMap",
    "SemanticMapAnchor",
    "SemanticMapEntry",
    "SemanticMapFragment",
    "SemanticMapPart",
    "SemanticMapRecord",
    "VariableEnvelopeSemantic",
    "load_semantic_map",
    "semantic_anchor_key",
    "semantic_record_key",
]


SEMANTIC_MAP_FRAGMENT_SCHEMA_VERSION: Final[int] = 1
_FRAGMENT_FILENAME = re.compile(r"^[0-9]{4}-(?P<fragment_id>[a-z0-9][a-z0-9-]*)$")
_RAW_ENTRIES_ADAPTER = TypeAdapter(tuple[dict[str, object], ...], config=ConfigDict(strict=True))


class _StrictModel(BaseModel):
    """Frozen development-tool boundary model with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _coerce_ordinal(value: object) -> object:
    """Accept a legacy authored int literal alongside the parser's printed str label.

    Committed semantic-map authoring data predates the parser's widened
    ``str | None`` ordinal and still writes bare integers (``ordinal = 14``).
    Coercing here lets that authored data hydrate unchanged while the anchor's
    stored value matches the parser type exactly, so ``semantic_anchor_key``
    and ``intermediate_anchor_key`` compare like-for-like without re-keying
    committed TOML/JSON.
    """
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    raise ValueError("ordinal must be a printed str label, a legacy int literal, or None")


type _AnchorOrdinal = Annotated[str | None, BeforeValidator(_coerce_ordinal)]


class SemanticMapAnchor(_StrictModel):
    """The complete parser-owned identity of one official design slot.

    ``record_identity`` is the parsed slot identity carried by
    :class:`RecordDesignIntermediateField`.  The optional cell intentionally
    mirrors the intermediate representation: workbook designs have a stable
    parser-column cell anchor, while a PDF design has no such cell.
    """

    sheet: str = Field(min_length=1)
    source_row: int = Field(gt=0)
    source_cell: str | None = Field(default=None, pattern=r"^[A-Z]+[1-9][0-9]*$")
    #: The ordinal AEAT printed, verbatim -- a str because it is a printed LABEL,
    #: never an arithmetic value. Mirrors
    #: :attr:`domain.calculations.registry.RecordDesignField.ordinal`, which
    #: :class:`RecordDesignIntermediateField.ordinal` is a straight 1:1
    #: projection of; this anchor field is the same value one join step later.
    #: The type permits ``None`` to match the parser exactly, but stays
    #: REQUIRED (no default): every anchor naming a printed field names a real
    #: printed ordinal, and TOML has no way to author an explicit null, so an
    #: omitted key refuses at load rather than silently defaulting into an
    #: anchor no parser field can ever match. The ONE field that legitimately
    #: has no ordinal declares :attr:`ordinal_absent` instead -- see there.
    ordinal: _AnchorOrdinal | None = Field(default=None, min_length=1)
    #: Declares that AEAT printed this row with NO ordinal, so the anchor's
    #: ``ordinal`` is genuinely ``None`` rather than merely unauthored.
    #:
    #: Required because the parser can now produce such a field and could not
    #: before. A row AEAT prints without a naturaleza is staged as an unnamed
    #: position candidate and admitted only by a gap fill, which cannot invent
    #: the ordinal AEAT never printed: Modelo 184's ``151-155 PORCENTAJE DE
    #: RENTA ATRIBUIBLE A MIEMBROS RESIDENTES`` is the worked case. Giving it a
    #: synthetic ordinal would fabricate a printed LABEL, which is exactly what
    #: the ``ordinal`` field's own contract forbids.
    #:
    #: This stays an EXPLICIT opt-in rather than a default so the safety the
    #: required key bought is kept: omitting both keys still refuses, and only
    #: an author stating "this row has no printed ordinal" reaches ``None``.
    ordinal_absent: bool = False
    record_identity: str = Field(min_length=1)

    @model_validator(mode="after")
    def _require_ordinal_or_declared_absence(self) -> SemanticMapAnchor:
        if self.ordinal_absent and self.ordinal is not None:
            msg = "anchor declares ordinal_absent but also names an ordinal"
            raise ValueError(msg)
        if not self.ordinal_absent and self.ordinal is None:
            msg = (
                "anchor names no ordinal; author the ordinal AEAT printed, or declare "
                "ordinal_absent = true when the design printed the row without one"
            )
            raise ValueError(msg)
        return self


def _coerce_envelope_prefix_role(value: object) -> object:
    """Hydrate the authored TOML token into its one closed envelope role."""
    if isinstance(value, FilingEnvelopePrefixRole):
        return value
    if isinstance(value, str):
        try:
            return FilingEnvelopePrefixRole(value)
        except ValueError as exc:
            raise ValueError(f"unknown envelope prefix role {value!r}") from exc
    raise ValueError("envelope prefix role must be a string")


type FilingEnvelopePrefixRoleValue = Annotated[
    FilingEnvelopePrefixRole,
    BeforeValidator(_coerce_envelope_prefix_role),
]


_PREFIX_ROLE_ORDER: tuple[FilingEnvelopePrefixRole, ...] = tuple(FilingEnvelopePrefixRole)


class EnvelopePrefixField(_StrictModel):
    """One exact source anchor and its non-inferable envelope prefix role."""

    role: FilingEnvelopePrefixRoleValue
    anchor: SemanticMapAnchor


class EnvelopeTotalAnchor(_StrictModel):
    """The parser-owned ``Total: Variable`` marker addressed without a field slot."""

    source_row: int = Field(gt=0)
    source_cell: str | None = Field(default=None, pattern=r"^[A-Z]+[1-9][0-9]*$")
    label: Literal["total"]
    length: Literal["Variable"]


class VariableEnvelopeSemantic(_StrictModel):
    """Hash-pinned semantic and composition authority for one variable envelope.

    The ordinary semantic map deliberately excludes variable-envelope fields.
    This separate contract retains the exact prefix anchors, ordered references
    to the already-owned fixed body records, the relative closer, and the
    parser's variable total marker without turning the wrapper into one more
    fixed-width record.
    """

    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    #: The parser record this wrapper composes. Declared by the map rather than
    #: pinned to one modelo: Modelos 151, 202, 322 and 353 carry the identical
    #: thirteen-anchor 328-byte prefix under their own record identities, so a
    #: literal here made one modelo's envelope the only composable one by
    #: accident rather than by contract.
    record_identity: str = Field(min_length=1)
    #: Which roles this design PRINTS, in source order. Not a fixed count: the
    #: shared ``<AUX>`` grammar is spelled in thirteen rows by Modelo 303 and in
    #: eight by Modelo 200, which fuses the first six into one composed opening
    #: tag. A fixed width here made the thirteen-row spelling the only
    #: expressible one, so a design differing only in how it PRINTS the same
    #: grammar was indistinguishable from one that violates it.
    prefix_fields: tuple[EnvelopePrefixField, ...] = Field(min_length=1)
    body_anchor: SemanticMapAnchor
    body_record_ids: tuple[RecordId, ...] = Field(min_length=1)
    closer_anchor: SemanticMapAnchor
    total_anchor: EnvelopeTotalAnchor

    @model_validator(mode="after")
    def _require_complete_ordered_semantics(self) -> VariableEnvelopeSemantic:
        roles = tuple(field.role for field in self.prefix_fields)
        if len(set(roles)) != len(roles):
            raise ValueError(f"variable envelope {self.record_identity!r} prefix roles must be unique")
        remaining = iter(_PREFIX_ROLE_ORDER)
        if not all(role in remaining for role in roles):
            raise ValueError(
                f"variable envelope {self.record_identity!r} prefix roles must appear in canonical source order",
            )
        anchors = tuple(field.anchor for field in self.prefix_fields)
        if len(set(anchors)) != len(anchors):
            raise ValueError(f"variable envelope {self.record_identity!r} prefix anchors must be unique")
        if self.body_anchor.record_identity != self.record_identity:
            raise ValueError(f"variable envelope body anchor must belong to {self.record_identity!r}")
        if self.closer_anchor.record_identity != self.record_identity:
            raise ValueError(f"variable envelope closer anchor must belong to {self.record_identity!r}")
        if len(set(self.body_record_ids)) != len(self.body_record_ids):
            raise ValueError("variable envelope body record identities must be unique and ordered")
        return self


class SemanticMapPart(_StrictModel):
    """A sub-slot that one design cell's own text declares inside itself.

    Modelo 347 prints one four-byte cell at offset 77 whose text divides it:
    "77-78 CODIGO PROVINCIA: Campo numerico de dos posiciones ..." and
    "79-80 CODIGO PAIS Campo alfabetico de 2 posiciones ...". The two halves
    carry different concepts and different AEAT types, so each is its own
    export field. A part is never inferred: the author copies the part's text
    from the cell verbatim, and validation holds it to the cell, so the split
    rests on what AEAT printed and nothing else.
    """

    offset: int = Field(gt=0)
    """The part's absolute one-based offset, inside its cell."""
    length: int = Field(gt=0)
    aeat_type: str = Field(min_length=1)
    """The type the part's own text states, e.g. "Numerico" for "Campo numerico"."""
    statement: str = Field(min_length=1)
    """The part's text, copied verbatim from the cell's content."""

    @property
    def printed_range(self) -> str:
        """The range the design prints for this part, e.g. ``"79-80"``."""
        return f"{self.offset}-{self.offset + self.length - 1}"


class SemanticMapEntry(_StrictModel):
    """Reviewed registry meaning for one exact parser anchor.

    Coordinates, field shape, and renderer formatting are intentionally absent:
    they belong to the hash-verified official design.  The following generator
    steps may use this entry only after they have established an exact bijection
    to parser output and resolved all canonical references through the registry.
    """

    anchor: SemanticMapAnchor
    export_field_id: ExportFieldId
    kind: CasillaFieldKindValue
    casilla_id: CasillaId | None = None
    binding: BindingId | None = None
    literal: str | None = None
    producer_key: FilingProducerKey | None = None
    projection_ref: FilingProjectionRef | None = None
    draft_attribute: ExportDraftAttribute | None = None
    computed_key: ExportComputedKey | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs
    part: SemanticMapPart | None = None
    """The sub-slot of its anchor's cell this entry fills, when the cell's text divides it."""

    @field_validator("projection_ref", mode="before")
    @classmethod
    def _compile_projection_ref_through_the_canonical_compiler(cls, value: object) -> object:
        """Compile a still-raw reference, so every persisted boundary round-trips.

        This entry is embedded in the export provenance manifest, which is
        written as JSON and read back by design.  Demanding an already-typed
        reference made that impossible: from JSON a reference can only arrive as
        a mapping.  Delegating to the one canonical compiler keeps the real
        invariant -- every reference was compiled by it -- while giving TOML and
        JSON the same single path.  A malformed payload still refuses there.
        """
        return value if value is None else hydrate_filing_projection_ref(value)

    @model_validator(mode="after")
    def _validate_exact_kind_semantics(self) -> SemanticMapEntry:
        """Require exactly the one semantic payload applicable to ``kind``."""
        payloads = {
            ExportSemanticPayloadAxis.CASILLA_ID: self.casilla_id,
            ExportSemanticPayloadAxis.BINDING: self.binding,
            ExportSemanticPayloadAxis.LITERAL: self.literal,
            ExportSemanticPayloadAxis.PRODUCER_KEY: self.producer_key,
            ExportSemanticPayloadAxis.PROJECTION_REF: self.projection_ref,
            ExportSemanticPayloadAxis.DRAFT_ATTRIBUTE: self.draft_attribute,
            ExportSemanticPayloadAxis.COMPUTED_KEY: self.computed_key,
        }
        required = export_semantic_payload_axis(self.kind)
        declared = tuple(axis for axis, value in payloads.items() if value is not None)
        if required is None:
            if declared:
                raise ValueError(
                    f"semantic-map {self.kind.value} field {self.export_field_id!r} "
                    f"must not declare semantic payloads: {', '.join(axis.value for axis in declared)}",
                )
            return self
        if declared != (required,):
            declared_description = ", ".join(axis.value for axis in declared) if declared else "none"
            raise ValueError(
                f"semantic-map {self.kind.value} field {self.export_field_id!r} must declare "
                f"only {required.value}; declared {declared_description}",
            )
        return self


def _coerce_row_field_casilla_ids(value: object) -> object:
    """Carry an authored casilla mapping as sorted pairs.

    The record is frozen and hashed -- ``_export_tree`` proves the join is total
    by comparing a ``frozenset`` of records -- so a ``Mapping`` member would make
    it unhashable. Sorted pairs are hashable and make equality and hash
    independent of the order the mapping was authored in.
    """
    if isinstance(value, Mapping):
        entries = cast(Mapping[object, object], value)
        return tuple(sorted((str(key), item) for key, item in entries.items()))
    return value


class SemanticMapRecord(_StrictModel):
    """Reviewed semantic identity for one exact parser record.

    The source design still owns record order, length, fields, and every wire
    characteristic.  This map supplies only the canonical registry identifier
    and business record type that cannot be inferred from a workbook tab name.
    """

    sheet: str = Field(min_length=1)
    record_identity: str = Field(min_length=1)
    export_record_id: RecordId
    record_type: str = Field(min_length=1)
    required: bool = True
    repeat: Literal["binding_rows", "projection_rows"] | None = None
    binding_record: str | None = None
    """The record whose binding rows this record repeats over, when ``repeat`` is
    ``binding_rows``. Carried unchanged into generated output; the generator does
    not derive or interpret it."""
    row_field_casilla_ids: Annotated[
        tuple[tuple[str, CasillaId], ...],
        BeforeValidator(_coerce_row_field_casilla_ids),
    ] = ()
    """Reviewed per-row casilla identities for a ``binding_rows`` record, authored
    as a mapping and carried as sorted pairs so the frozen record stays hashable."""
    discriminator: RecordDiscriminator | None = None
    """Reviewed runtime record-shape fact, carried unchanged into generated output.

    This is deliberately the existing registry discriminator model rather than
    a second mapping-only vocabulary: the generator neither interprets nor
    derives it.  An authored rule must therefore already satisfy the strict
    production schema that consumes it while parsing filed records.
    """


class SemanticMap(_StrictModel):
    """One authored semantic map for one exact official source design.

    Entries and records are exact parser keys only at this stage.  Exact parser
    joining, uniqueness, catalogue resolution, source applicability, and anomaly
    handling remain later explicit generator contracts.
    """

    modelo: ModeloId
    design_epoch: str = Field(min_length=1)
    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: tuple[SemanticMapRecord, ...] = Field(min_length=1)
    entries: tuple[SemanticMapEntry, ...] = Field(min_length=1)
    variable_envelopes: tuple[VariableEnvelopeSemantic, ...] = ()

    @model_validator(mode="after")
    def _require_unique_record_semantics(self) -> SemanticMap:
        mismatched_envelopes = tuple(
            envelope.record_identity
            for envelope in self.variable_envelopes
            if (envelope.source_ref != self.source_ref or envelope.source_sha256 != self.source_sha256)
        )
        if mismatched_envelopes:
            raise ValueError(
                "semantic map variable-envelope identities must match the exact semantic-map source: "
                f"{mismatched_envelopes!r}",
            )
        record_keys = tuple((record.sheet, record.record_identity) for record in self.records)
        duplicate_keys = sorted({key for key in record_keys if record_keys.count(key) > 1})
        if duplicate_keys:
            raise ValueError(f"semantic map contains duplicate exact record anchors: {duplicate_keys!r}")
        record_ids = tuple(str(record.export_record_id) for record in self.records)
        duplicate_ids = sorted({record_id for record_id in record_ids if record_ids.count(record_id) > 1})
        if duplicate_ids:
            raise ValueError(f"semantic map contains duplicate canonical export record ids: {duplicate_ids!r}")
        envelope_identities = tuple(envelope.record_identity for envelope in self.variable_envelopes)
        duplicate_envelopes = sorted(
            {identity for identity in envelope_identities if envelope_identities.count(identity) > 1},
        )
        if duplicate_envelopes:
            raise ValueError(f"semantic map contains duplicate variable-envelope identities: {duplicate_envelopes!r}")
        return self


def semantic_anchor_key(anchor: SemanticMapAnchor) -> AnchorKey:
    """Return the identity one anchor is matched and de-duplicated by.

    The join and the validation both key anchors, and they must key them the
    SAME way: the join looks an entry up by this tuple while the validation
    decides whether two anchors collide. Two spellings that drift make a pair
    the validation calls distinct unreachable to the join, which then reports
    a missing anchor rather than the collision that caused it.
    """
    return anchor.sheet, anchor.source_row, anchor.source_cell, anchor.ordinal, anchor.record_identity


def semantic_record_key(record: SemanticMapRecord) -> RecordKey:
    """Return the identity one record is matched and de-duplicated by."""
    return record.sheet, record.record_identity


class SemanticMapFragment(_StrictModel):
    """One reviewable fragment of one exact source-pinned semantic map."""

    schema_version: Literal[1]
    fragment_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    modelo: ModeloId
    design_epoch: str = Field(min_length=1)
    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: tuple[SemanticMapRecord, ...] = ()
    entries: tuple[SemanticMapEntry, ...] = ()
    variable_envelopes: tuple[VariableEnvelopeSemantic, ...] = ()

    @model_validator(mode="after")
    def _require_authored_meaning(self) -> SemanticMapFragment:
        if not self.records and not self.entries and not self.variable_envelopes:
            raise ValueError("semantic-map fragments must contain records, entries, or variable envelopes")
        return self


def load_semantic_map(fragment_directory: Path) -> SemanticMap:
    """Compile one strict semantic map from regular TOML fragments.

    Fragment order is the lexical filename order.  Filesystem enumeration
    order therefore cannot affect the compiled map, while every duplicate
    semantic identity is refused instead of merged or overwritten.
    """
    paths = _semantic_map_fragment_paths(fragment_directory)
    fragments = tuple(_load_fragment(path) for path in paths)
    return _compile_fragments(fragments)


def _semantic_map_fragment_paths(fragment_directory: Path) -> tuple[Path, ...]:
    if not fragment_directory.is_dir() or is_link_like(fragment_directory):
        raise RegistryValidationError(
            f"semantic-map path must be a real directory: {fragment_directory}",
        )
    try:
        paths = tuple(sorted(iter_directory(fragment_directory, require_root=True), key=lambda path: path.name))
    except OSError as exc:
        raise RegistryValidationError(
            f"cannot inspect semantic-map directory: {fragment_directory}",
        ) from exc
    if not paths:
        raise RegistryValidationError(
            f"semantic-map directory contains no TOML fragments: {fragment_directory}",
        )
    invalid = tuple(
        path.name for path in paths if path.suffix.casefold() != ".toml" or is_link_like(path) or not path.is_file()
    )
    if invalid:
        raise RegistryValidationError(
            f"semantic-map directory accepts only regular TOML fragments; refusing entries: {invalid!r}",
        )
    return paths


def _load_fragment(path: Path) -> SemanticMapFragment:
    frozen = freeze_toml(
        read_toml(
            path,
            error_factory=lambda message: RegistryValidationError(message),
        ),
    )
    data: dict[str, object] = dict(frozen)
    try:
        raw_entries = _RAW_ENTRIES_ADAPTER.validate_python(data.get("entries", ()))
    except ValidationError as exc:
        raise RegistryValidationError(
            f"invalid semantic-map fragment {path.name!r}: entries must be an array of tables",
        ) from exc
    compiled_entries: list[object] = []
    for raw_entry in raw_entries:
        entry = dict(raw_entry)
        if "header_key" in entry:
            raise RegistryValidationError(
                f"invalid semantic-map fragment {path.name!r}: legacy header_key is not accepted; use producer_key",
            )
        raw_producer_key = entry.get("producer_key")
        if isinstance(raw_producer_key, str):
            try:
                entry["producer_key"] = FilingProducerKey(raw_producer_key)
            except ValueError as exc:
                raise RegistryValidationError(
                    f"invalid semantic-map fragment {path.name!r}: "
                    f"{raw_producer_key!r} is not a canonical producer_key",
                ) from exc
        raw_projection_ref = entry.get("projection_ref")
        if raw_projection_ref is not None:
            try:
                entry["projection_ref"] = compile_filing_projection_ref(raw_projection_ref)
            except ValidationError as exc:
                raise RegistryValidationError(
                    f"invalid semantic-map fragment {path.name!r}: "
                    f"projection_ref is not canonical: {validation_error_detail(exc)}",
                ) from exc
            except ValueError as exc:
                raise RegistryValidationError(
                    f"invalid semantic-map fragment {path.name!r}: projection_ref is not canonical: {exc}",
                ) from exc
        for field_name, enum_type in (
            ("draft_attribute", ExportDraftAttribute),
            ("computed_key", ExportComputedKey),
        ):
            raw_value = entry.get(field_name)
            if isinstance(raw_value, str):
                try:
                    entry[field_name] = enum_type(raw_value)
                except ValueError as exc:
                    raise RegistryValidationError(
                        f"invalid semantic-map fragment {path.name!r}: {raw_value!r} is not a canonical {field_name}",
                    ) from exc
        compiled_entries.append(entry)
    data["entries"] = tuple(compiled_entries)
    try:
        fragment = SemanticMapFragment.model_validate(data)
    except ValidationError as exc:
        raise RegistryValidationError(
            f"invalid semantic-map fragment {path.name!r}: {validation_error_detail(exc)}",
        ) from exc
    filename_match = _FRAGMENT_FILENAME.fullmatch(path.stem)
    if filename_match is None or filename_match.group("fragment_id") != fragment.fragment_id:
        raise RegistryValidationError(
            f"semantic-map fragment filename {path.name!r} must be NNNN-<fragment_id>.toml",
        )
    return fragment


def _compile_fragments(fragments: Iterable[SemanticMapFragment]) -> SemanticMap:
    ordered = tuple(fragments)
    if not ordered:
        raise RegistryValidationError("semantic map requires at least one fragment")

    duplicate_fragment_ids = _duplicates(fragment.fragment_id for fragment in ordered)
    if duplicate_fragment_ids:
        raise RegistryValidationError(
            f"semantic map contains duplicate fragment ids: {duplicate_fragment_ids!r}",
        )

    identity = (
        ordered[0].modelo,
        ordered[0].design_epoch,
        ordered[0].source_ref,
        ordered[0].source_sha256,
    )
    mismatched_fragments = tuple(
        fragment.fragment_id
        for fragment in ordered
        if (
            fragment.modelo,
            fragment.design_epoch,
            fragment.source_ref,
            fragment.source_sha256,
        )
        != identity
    )
    if mismatched_fragments:
        raise RegistryValidationError(
            f"semantic-map fragments have conflicting modelo/design/source identities: {mismatched_fragments!r}",
        )

    records = tuple(record for fragment in ordered for record in fragment.records)
    entries = tuple(entry for fragment in ordered for entry in fragment.entries)
    variable_envelopes = tuple(envelope for fragment in ordered for envelope in fragment.variable_envelopes)
    if not records or not entries:
        raise RegistryValidationError(
            "compiled semantic map requires at least one record and one entry",
        )
    _require_no_collisions(records, entries)
    return SemanticMap(
        modelo=ordered[0].modelo,
        design_epoch=ordered[0].design_epoch,
        source_ref=ordered[0].source_ref,
        source_sha256=ordered[0].source_sha256,
        records=tuple(
            sorted(
                records,
                key=lambda record: (
                    record.sheet,
                    record.record_identity,
                    str(record.export_record_id),
                ),
            ),
        ),
        entries=tuple(sorted(entries, key=_entry_key)),
        variable_envelopes=tuple(sorted(variable_envelopes, key=lambda envelope: envelope.record_identity)),
    )


def _require_no_collisions(
    records: tuple[SemanticMapRecord, ...],
    entries: tuple[SemanticMapEntry, ...],
) -> None:
    collisions = (
        (
            "exact record anchors",
            _duplicates((record.sheet, record.record_identity) for record in records),
        ),
        (
            "export record ids",
            _duplicates(str(record.export_record_id) for record in records),
        ),
        (
            "exact field anchors",
            _duplicates(
                (
                    entry.anchor.sheet,
                    entry.anchor.source_row,
                    entry.anchor.source_cell,
                    entry.anchor.ordinal,
                    entry.anchor.record_identity,
                    # Parts of one cell share its anchor and differ by where
                    # they sit in it; validation holds them to the cell.
                    None if entry.part is None else entry.part.offset,
                )
                for entry in entries
            ),
        ),
        (
            "export field ids",
            _duplicates(str(entry.export_field_id) for entry in entries),
        ),
    )
    for subject, duplicates in collisions:
        if duplicates:
            raise RegistryValidationError(
                f"semantic-map fragments collide on {subject}: {duplicates!r}",
            )


def _duplicates[T](values: Iterable[T]) -> tuple[T, ...]:
    seen: set[T] = set()
    duplicates: set[T] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return tuple(sorted(duplicates, key=repr))


def _entry_key(entry: SemanticMapEntry) -> tuple[str, int, str, str, str, str]:
    return (
        entry.anchor.sheet,
        entry.anchor.source_row,
        entry.anchor.source_cell or "",
        entry.anchor.ordinal or "",
        entry.anchor.record_identity,
        str(entry.export_field_id),
    )
