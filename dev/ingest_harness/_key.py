"""The corpus key, pinned by content hash, with every denominator re-derived.

The measurement corpus is external, read-only, and not a git repository, so the
only thing that can identify which key a figure was scored against is the key's
own content hash. This module computes that hash before anything else happens
and refuses a key that is not the pinned one.

**Never cite the key's internal ``schema_version``.** That field reads ``"1.0"``
and has never tracked the key through v1 to v5, so it identifies nothing. It is
loaded here only so the header can print it *labelled as stale*, which is
strictly better than leaving it out and letting a reader go find it.

**Every denominator is derived from the key, never inherited from prose.** Stale
counts (34 transcriptions, 8 twins, 26 vision-path, 36 category-scorable) reached
a decided record before anyone re-derived them. The figures this module computes
are therefore computed, and the accompanying test asserts them against the values
measured directly from the key -- so a corpus change makes a test fail rather
than silently moving a denominator underneath a published figure.

Two derivations that a naive filter gets wrong, both encoded here:

``category_scorable`` is ABSENT on the generated documents, not ``True``.
    Their category is intrinsic -- the key's own ``document_provenance`` says the
    taxpayer's position is known because the document was rendered from the
    spec -- so they carry no scorability flag at all. A filter written as
    ``hints["category_scorable"] is True`` yields 29 where the scorable set is
    59, and 29 is not a number anyone would notice as wrong.

``ground_truth == {}`` means there is NO denominator, not a denominator of zero.
    81 documents carry no authored truth. An accuracy over them is not a low
    score; it is undefined, and the field-count a reader would naturally quote is
    an emitted count wearing an accuracy's clothes.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "CORPUS_ROOT",
    "EXPECTED_KEY_BYTES",
    "EXPECTED_KEY_SHA256",
    "CorpusDocument",
    "CorpusKey",
    "CorpusKeyError",
    "Denominators",
    "ProvenanceClass",
    "TwinPair",
    "load_corpus_key",
]

_STRICT = ConfigDict(frozen=True, strict=True, extra="forbid")

CORPUS_ROOT: Final = Path(r"Y:\code\llm-invoice-smoke\corpus")
"""The external corpus tree. Read-only: it is not a git repository, so a delete
there is unrecoverable and nothing in this package ever opens it for writing."""

EXPECTED_KEY_SHA256: Final = "e2db6a499f6f0ffafa4cf44084f433962dd3f8a0f6f0a65facaf7df07bb38593"
"""The v5 key's content hash. The only identifier a figure may be quoted with."""

EXPECTED_KEY_BYTES: Final = 890_052
"""Byte length of the pinned key, checked alongside the hash purely so a
truncated read fails with a length mismatch rather than an opaque hash mismatch."""

#: The twin link is PROSE, not a structured field: the corpus records a vision
#: twin's original in free text. Resolving it therefore means matching a sentence,
#: and the harness declares that dependency in its output rather than presenting
#: the resolved pairs as though they came from a typed relation.
_TWIN_NOTE = re.compile(r"VISION-PATH TWIN of\s+(?P<original>[A-Za-z0-9_.-]+)")

TWIN_LINK_IS_PROSE: Final = (
    "Twin pairs are resolved by matching the phrase 'VISION-PATH TWIN of <ID>' in each "
    "document's free-text notes field. The corpus carries no structured twin relation, so "
    "this link breaks SILENTLY if the corpus rewords that sentence: the pair count simply "
    "drops. Any twin-delta figure must be read together with the pair count it was computed "
    "over, and the harness prints both."
)

#: Vision-path file formats: the document reaches the pipeline as pixels, so a
#: reading model must transcribe it rather than parse it.
_VISION_PATH_FORMATS: Final = frozenset({"image_photo", "pdf_scan"})


class CorpusKeyError(RuntimeError):
    """The key is not the pinned one, or contradicts itself."""


class ProvenanceClass(StrEnum):
    """How a corpus document came to exist.

    Derived from markers that are exclusive to each class rather than from the
    path, and then cross-checked against the path, because two independent
    derivations that agree are evidence and one derivation is an assumption.
    """

    GENERATED = "generated"
    """Rendered from the corpus's own spec. Category is intrinsic."""

    ACQUIRED_REAL = "acquired_real"
    """A real third-party document acquired under a verified free licence."""

    OPERATOR = "operator"
    """Operator-authored entries and standards-body sample records."""


class CorpusDocument(BaseModel):
    """One corpus document as the harness needs to see it.

    A narrow projection of the key's document entry: enough to select, score and
    caveat a document, deliberately not the whole record, so that a field the
    harness does not understand cannot be silently carried into a figure.
    """

    model_config = _STRICT

    doc_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    provenance_class: ProvenanceClass
    language: str = Field(min_length=1)
    file_format: str = Field(min_length=1)
    tolerance_cents: int = Field(ge=0)
    ground_truth: Mapping[str, Any]
    notes: str = ""

    @property
    def has_authored_truth(self) -> bool:
        """Whether ANY truth was authored for this document.

        False means an accuracy over it is undefined rather than zero. This is
        the structural guard behind the emitted-versus-scored distinction.
        """
        return bool(self.ground_truth)

    @property
    def scorable_fields(self) -> tuple[str, ...]:
        """Field names carrying non-null truth, in key order.

        A ``null`` truth value means the document LACKS the field, so it is not
        a scorable slot -- it is a fabrication trap, and a value emitted there is
        a hard error rather than a miss.
        """
        return tuple(name for name, value in self.ground_truth.items() if value is not None)

    @property
    def fabrication_trap_fields(self) -> tuple[str, ...]:
        """Field names whose truth is explicitly ``null``."""
        return tuple(name for name, value in self.ground_truth.items() if value is None)

    @property
    def is_vision_path(self) -> bool:
        """Whether the document reaches the pipeline as pixels."""
        return self.file_format in _VISION_PATH_FORMATS

    @property
    def is_spanish(self) -> bool:
        """Whether the document's language is Spanish, including the mixed tag.

        Drives the automatic optimism-bias caveat. Deliberately a prefix test:
        the corpus carries ``es`` and ``es-en``, and a mixed-language document
        rendered by the same synthetic renderer carries the same bias.
        """
        return self.language == "es" or self.language.startswith("es-")


class TwinPair(BaseModel):
    """A vision twin and the original it was rendered from.

    The pair isolates reading error: both carry identical figures, so a field the
    original recovers and the twin does not is a reading failure rather than a
    reasoning one.
    """

    model_config = _STRICT

    twin_doc_id: str = Field(min_length=1)
    original_doc_id: str = Field(min_length=1)


class Denominators(BaseModel):
    """Every count a figure in this campaign is quoted over.

    Held as one record so a report cannot print a numerator whose denominator
    was derived at a different moment or from a different key.
    """

    model_config = _STRICT

    documents: int
    generated: int
    acquired_real: int
    operator: int
    stage1_reference_text: int
    twin_pairs: int
    vision_path: int
    category_scorable: int
    documents_without_authored_truth: int
    fabrication_trap_slots: int


class CorpusKey(BaseModel):
    """The pinned key plus the derivations the harness quotes figures over."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    sha256: str = Field(min_length=64, max_length=64)
    byte_length: int = Field(gt=0)
    stale_schema_version: str
    documents: tuple[CorpusDocument, ...]
    twin_pairs: tuple[TwinPair, ...]
    category_scorable_ids: frozenset[str]
    stage1_reference_text_ids: frozenset[str]

    def document(self, doc_id: str) -> CorpusDocument:
        """Return one document by id, refusing an unknown id rather than ``None``.

        A silent ``None`` here becomes a skipped row, and a skipped row shrinks a
        denominator without anything saying so.
        """
        for row in self.documents:
            if row.doc_id == doc_id:
                return row
        raise CorpusKeyError(f"no corpus document with doc_id {doc_id!r} in key {self.sha256[:12]}")

    @property
    def denominators(self) -> Denominators:
        """Re-derive every denominator from this key's own contents."""
        by_class = {member: 0 for member in ProvenanceClass}
        for row in self.documents:
            by_class[row.provenance_class] += 1
        return Denominators(
            documents=len(self.documents),
            generated=by_class[ProvenanceClass.GENERATED],
            acquired_real=by_class[ProvenanceClass.ACQUIRED_REAL],
            operator=by_class[ProvenanceClass.OPERATOR],
            stage1_reference_text=len(self.stage1_reference_text_ids),
            twin_pairs=len(self.twin_pairs),
            vision_path=sum(1 for row in self.documents if row.is_vision_path),
            category_scorable=len(self.category_scorable_ids),
            documents_without_authored_truth=sum(1 for row in self.documents if not row.has_authored_truth),
            fabrication_trap_slots=sum(len(row.fabrication_trap_fields) for row in self.documents),
        )

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any], *, sha256: str, byte_length: int) -> Self:
        """Build the projection from a decoded key payload."""
        entries = payload["documents"]
        documents = tuple(_project_document(entry) for entry in entries)
        return cls(
            sha256=sha256,
            byte_length=byte_length,
            stale_schema_version=str(payload.get("schema_version", "")),
            documents=documents,
            twin_pairs=_resolve_twin_pairs(documents),
            category_scorable_ids=_category_scorable_ids(entries),
            stage1_reference_text_ids=frozenset(
                entry["doc_id"] for entry in entries if entry.get("stage1_reference_text")
            ),
        )


def _provenance_class(entry: Mapping[str, Any]) -> ProvenanceClass:
    """Classify one entry, cross-checking two independent signals.

    The marker keys inside ``provenance`` are exclusive per class, and the path's
    top-level directory agrees with them. Deriving from one and asserting the
    other means a corpus reshuffle raises here instead of quietly reclassifying
    documents underneath a published breakdown.
    """
    provenance = entry["provenance"]
    if "generator" in provenance:
        derived = ProvenanceClass.GENERATED
    elif "licence_evidence_url" in provenance:
        derived = ProvenanceClass.ACQUIRED_REAL
    elif "origin" in provenance:
        derived = ProvenanceClass.OPERATOR
    else:
        raise CorpusKeyError(f"{entry['doc_id']}: provenance carries no class marker")

    prefix = entry["path"].split("/")[0]
    expected_operator_prefix = prefix == "operator"
    expected_real_prefix = prefix == "real"
    agrees = {
        ProvenanceClass.OPERATOR: expected_operator_prefix,
        ProvenanceClass.ACQUIRED_REAL: expected_real_prefix,
        ProvenanceClass.GENERATED: not expected_operator_prefix and not expected_real_prefix,
    }[derived]
    if not agrees:
        raise CorpusKeyError(
            f"{entry['doc_id']}: provenance markers say {derived.value} but the path prefix is {prefix!r}",
        )
    return derived


def _project_document(entry: Mapping[str, Any]) -> CorpusDocument:
    hints = entry["scoring_hints"]
    return CorpusDocument(
        doc_id=entry["doc_id"],
        path=entry["path"],
        provenance_class=_provenance_class(entry),
        language=entry["axes"]["language"],
        file_format=entry["axes"]["file_format"],
        tolerance_cents=int(hints["tolerance_cents"]),
        ground_truth=dict(entry["ground_truth"]),
        notes=str(entry.get("notes") or ""),
    )


def _category_scorable_ids(entries: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]]) -> frozenset[str]:
    """Ids whose category may be scored.

    The rule is a union, not a flag lookup: an entry is scorable when it declares
    ``category_scorable`` true, OR when it is generated and therefore carries no
    flag because its category is intrinsic. Reading the flag alone silently drops
    the entire generated set.
    """
    scorable: set[str] = set()
    for entry in entries:
        declared = entry["scoring_hints"].get("category_scorable")
        if declared is True or (declared is None and _provenance_class(entry) is ProvenanceClass.GENERATED):
            scorable.add(entry["doc_id"])
    return frozenset(scorable)


def _resolve_twin_pairs(documents: tuple[CorpusDocument, ...]) -> tuple[TwinPair, ...]:
    """Resolve vision twins from the prose notes field.

    See :data:`TWIN_LINK_IS_PROSE`. The original id is verified to exist, so a
    reworded or mistyped reference raises rather than yielding a pair pointing at
    nothing.
    """
    known = {row.doc_id for row in documents}
    pairs: list[TwinPair] = []
    for row in documents:
        match = _TWIN_NOTE.search(row.notes)
        if match is None:
            continue
        original = match.group("original")
        if original not in known:
            raise CorpusKeyError(
                f"{row.doc_id}: notes name twin original {original!r}, which is not a document in this key",
            )
        pairs.append(TwinPair(twin_doc_id=row.doc_id, original_doc_id=original))
    return tuple(pairs)


def load_corpus_key(path: Path | None = None) -> CorpusKey:
    """Read the corpus key, refusing anything but the pinned content.

    The hash is computed before the payload is parsed, so an unpinned key cannot
    reach any downstream derivation at all.

    Raises:
        CorpusKeyError: When the file's hash or length is not the pinned one.
    """
    key_path = path if path is not None else CORPUS_ROOT / "GROUND_TRUTH.json"
    raw = key_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_KEY_SHA256 or len(raw) != EXPECTED_KEY_BYTES:
        raise CorpusKeyError(
            "corpus key is not the pinned v5 key; every figure in this campaign is quoted "
            f"against sha256 {EXPECTED_KEY_SHA256} ({EXPECTED_KEY_BYTES} bytes), but "
            f"{key_path} has sha256 {digest} ({len(raw)} bytes)",
        )
    return CorpusKey.from_payload(json.loads(raw.decode("utf-8")), sha256=digest, byte_length=len(raw))
