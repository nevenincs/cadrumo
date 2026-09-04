"""Curation operations and the audit health report for the Handbook.

The ``set`` / ``relate`` / ``retire`` operations mutate one concept
fragment through the strict schema and the canonical serialiser, then
RE-VALIDATE the whole tree with the relation-integrity and lifecycle
validation gates before writing: a mutation that would leave the tree
loader-invalid is REFUSED with an explanation, never written. Every
operation is deterministic and idempotent (re-running with the same
arguments is a no-op diff).

The audit report is read-only: it summarises curation-backlog health
(draft counts, empty short_descriptions, dangling relations,
retired-without-replaced_by, seed-provenance coverage) as a structured
:class:`AuditReport` so a curation-backlog ratchet can consume the
counts directly rather than re-parsing printed text.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from cadrumo.core.concept_lifecycle import ConceptLifecycle
from cadrumo.core.external_constants import UTF_8_ENCODING, OutputLanguage

from ._serialize import serialise_concept
from .enums import TermStatus
from .errors import TerminologyValidationError
from .loader import TerminologyHandbook, load_terminology_handbook, terminology_concepts_dir
from .schema import (
    ConceptRecord,
    LanguageSection,
    LanguageSource,
    TermSection,
)
from .validators import default_handbook_validators

__all__ = [
    "AuditReport",
    "CurationError",
    "audit_handbook",
    "relate_concepts",
    "retire_concept",
    "set_language_field",
    "set_term",
]

_CURATED_FIELDS = ("short_description", "definition", "scope_note")


class CurationError(TerminologyValidationError):
    """Raised when a curation operation is refused (would invalidate the tree)."""


@dataclass(frozen=True, slots=True)
class AuditReport:
    """Structured handbook-health snapshot for the curation-backlog ratchet."""

    total_concepts: int
    draft_count: int
    approved_count: int
    deprecated_count: int
    retired_count: int
    #: concept_id -> sorted language codes whose short_description is the
    #: scaffold placeholder or empty.
    empty_short_description: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: concept_id -> sorted dangling relation targets (broader/related/replaced_by).
    dangling_relations: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: concept_ids that are retired but carry no replaced_by.
    retired_without_replaced_by: tuple[str, ...] = field(default=())
    seeded_count: int = 0
    hand_authored_count: int = 0

    @property
    def is_clean(self) -> bool:
        """True when no structural-health issue is present.

        Draft counts and seed coverage are backlog signals, not failures,
        so they do not affect cleanliness; dangling relations and
        retired-without-replaced_by are structural defects that do.
        """
        return not self.dangling_relations and not self.retired_without_replaced_by


_PLACEHOLDER_MARKER = "(sin curar)"


def audit_handbook(concepts_dir: Path | None = None) -> AuditReport:
    """Compute the structured :class:`AuditReport` for the Handbook tree."""
    handbook = _load(concepts_dir)
    known = set(handbook.by_id)

    draft = approved = deprecated = retired = 0
    empty_short: dict[str, tuple[str, ...]] = {}
    dangling: dict[str, tuple[str, ...]] = {}
    retired_no_replacement: list[str] = []
    seeded = hand_authored = 0

    for concept in handbook.concepts:
        match concept.lifecycle:
            case ConceptLifecycle.DRAFT:
                draft += 1
            case ConceptLifecycle.APPROVED:
                approved += 1
            case ConceptLifecycle.DEPRECATED:
                deprecated += 1
            case ConceptLifecycle.RETIRED:
                retired += 1

        empty_langs = tuple(
            section.language.value
            for section in concept.languages
            if _is_uncurated_short_description(section.short_description)
        )
        if empty_langs:
            empty_short[concept.concept_id] = tuple(sorted(empty_langs))

        missing = _dangling_targets(concept, known)
        if missing:
            dangling[concept.concept_id] = missing

        if concept.lifecycle is ConceptLifecycle.RETIRED and concept.replaced_by is None:
            retired_no_replacement.append(concept.concept_id)

        if concept.seed_provenance is not None:
            seeded += 1
        else:
            hand_authored += 1

    return AuditReport(
        total_concepts=len(handbook.concepts),
        draft_count=draft,
        approved_count=approved,
        deprecated_count=deprecated,
        retired_count=retired,
        empty_short_description=empty_short,
        dangling_relations=dangling,
        retired_without_replaced_by=tuple(sorted(retired_no_replacement)),
        seeded_count=seeded,
        hand_authored_count=hand_authored,
    )


def _is_uncurated_short_description(value: str) -> bool:
    return not value.strip() or _PLACEHOLDER_MARKER in value


def _dangling_targets(concept: ConceptRecord, known: set[str]) -> tuple[str, ...]:
    targets: list[str] = []
    for target in (*concept.broader, *concept.related):
        if target not in known:
            targets.append(target)
    if concept.replaced_by is not None and concept.replaced_by not in known:
        targets.append(concept.replaced_by)
    return tuple(sorted(set(targets)))


def set_language_field(
    concept_id: str,
    language: OutputLanguage,
    field_name: str,
    value: str,
    *,
    concepts_dir: Path | None = None,
    today: date | None = None,
    source_citation: str | None = None,
    source_authority: str | None = None,
) -> Path:
    """Set a curated language-section field, refusing an invalid result.

    ``field_name`` is one of ``short_description`` / ``definition`` /
    ``scope_note`` / ``source`` (``source`` consumes ``value`` as the
    citation and the optional ``source_authority``). The language section
    is created if absent.
    """
    handbook, target_dir = _load_with_dir(concepts_dir)
    concept = _require_concept(handbook, concept_id)
    section = _section_or_new(concept, language)

    if field_name == "source":
        updated_section = section.model_copy(
            update={"source": LanguageSource(citation=value, authority=source_authority)},
        )
    elif field_name in _CURATED_FIELDS:
        updated_section = section.model_copy(update={field_name: value})
    else:
        raise CurationError(f"unknown language field {field_name!r}; expected one of {(*_CURATED_FIELDS, 'source')!r}")

    new_concept = _replace_section(concept, updated_section, today=today)
    return _commit_concept(handbook, new_concept, target_dir)


def set_term(
    concept_id: str,
    language: OutputLanguage,
    label: str,
    term_status: TermStatus,
    *,
    concepts_dir: Path | None = None,
    today: date | None = None,
) -> Path:
    """Add or update a term on a language section, refusing an invalid result.

    A term with the same label is replaced (idempotent); a new label is
    appended. The strict language-section validator (one preferred term,
    unique labels) is enforced by re-validation.
    """
    handbook, target_dir = _load_with_dir(concepts_dir)
    concept = _require_concept(handbook, concept_id)
    section = _section_or_new(concept, language)

    new_term = TermSection(label=label, term_status=term_status)
    kept = tuple(term for term in section.terms if term.label != label)
    updated_section = section.model_copy(update={"terms": (*kept, new_term)})
    new_concept = _replace_section(concept, updated_section, today=today)
    return _commit_concept(handbook, new_concept, target_dir)


def remove_term(
    concept_id: str,
    language: OutputLanguage,
    label: str,
    *,
    concepts_dir: Path | None = None,
    today: date | None = None,
) -> Path:
    """Remove a term by its exact label from a language section.

    The counterpart to :func:`set_term`, which could only add or replace a term
    with no way to drop a stale or duplicate one. The strict language-section
    validator (one preferred term, unique labels) runs on the result, so
    removing the sole preferred term is refused. Removing a label the section
    does not carry is an error, not a silent no-op.
    """
    handbook, target_dir = _load_with_dir(concepts_dir)
    concept = _require_concept(handbook, concept_id)
    section = _section_or_new(concept, language)
    kept = tuple(term for term in section.terms if term.label != label)
    if len(kept) == len(section.terms):
        raise CurationError(
            f"no term {label!r} on concept {concept_id!r} [{language.value}] to remove",
        )
    updated_section = section.model_copy(update={"terms": kept})
    new_concept = _replace_section(concept, updated_section, today=today)
    return _commit_concept(handbook, new_concept, target_dir)


def relate_concepts(
    concept_id: str,
    relation: str,
    target_id: str,
    *,
    remove: bool = False,
    concepts_dir: Path | None = None,
    today: date | None = None,
) -> Path:
    """Add or remove a ``broader`` / ``related`` edge, refusing an invalid result.

    Dangling targets, self-references, and cycles are rejected by the
    relation-integrity and lifecycle validators run before the write.
    """
    if relation not in ("broader", "related"):
        raise CurationError(f"unknown relation {relation!r}; expected 'broader' or 'related'")
    handbook, target_dir = _load_with_dir(concepts_dir)
    concept = _require_concept(handbook, concept_id)
    current = getattr(concept, relation)

    if remove:
        updated = tuple(item for item in current if item != target_id)
    else:
        updated = current if target_id in current else (*current, target_id)

    new_concept = concept.model_copy(update={relation: updated, "updated_at": _stamp(today)})
    return _commit_concept(handbook, new_concept, target_dir)


def retire_concept(
    concept_id: str,
    replaced_by: str,
    *,
    concepts_dir: Path | None = None,
    today: date | None = None,
) -> Path:
    """Retire a concept with a required ``replaced_by``, refusing an invalid result.

    Never deletes; stamps ``lifecycle = retired`` + ``replaced_by``. The
    lifecycle validator rejects a self-reference, a retired successor,
    or a cycle before the write.
    """
    handbook, target_dir = _load_with_dir(concepts_dir)
    concept = _require_concept(handbook, concept_id)
    new_concept = concept.model_copy(
        update={
            "lifecycle": ConceptLifecycle.RETIRED,
            "replaced_by": replaced_by,
            "updated_at": _stamp(today),
        },
    )
    return _commit_concept(handbook, new_concept, target_dir)


# --------------------------------------------------------------------------
# internal helpers
# --------------------------------------------------------------------------
def _load(concepts_dir: Path | None) -> TerminologyHandbook:
    target = concepts_dir if concepts_dir is not None else terminology_concepts_dir()
    return load_terminology_handbook(target)


def _load_with_dir(concepts_dir: Path | None) -> tuple[TerminologyHandbook, Path]:
    target = concepts_dir if concepts_dir is not None else terminology_concepts_dir()
    return load_terminology_handbook(target), target


def _require_concept(handbook: TerminologyHandbook, concept_id: str) -> ConceptRecord:
    concept = handbook.by_id.get(concept_id)
    if concept is None:
        raise CurationError(f"unknown concept {concept_id!r}")
    return concept


def _section_or_new(concept: ConceptRecord, language: OutputLanguage) -> LanguageSection:
    for section in concept.languages:
        if section.language is language:
            return section
    # A new section needs the required short_description; seed the uncurated
    # placeholder so it is a visible curation marker, never invented prose.
    return LanguageSection(language=language, short_description="(sin curar) seccion nueva")


def _replace_section(concept: ConceptRecord, updated: LanguageSection, *, today: date | None) -> ConceptRecord:
    others = tuple(section for section in concept.languages if section.language is not updated.language)
    # Preserve authoring order: keep existing sections, append a genuinely new one.
    had = any(section.language is updated.language for section in concept.languages)
    if had:
        languages = tuple(updated if section.language is updated.language else section for section in concept.languages)
    else:
        languages = (*others, updated)
    return concept.model_copy(update={"languages": languages, "updated_at": _stamp(today)})


def _commit_concept(handbook: TerminologyHandbook, new_concept: ConceptRecord, concepts_dir: Path) -> Path:
    # Re-validate the mutated record through the full schema so per-record
    # and per-section invariants (one preferred term, no self replaced_by,
    # unique labels) -- which model_copy bypasses -- fire and are reported as
    # a refusal rather than a raw ValidationError.
    revalidated = _revalidate_record(new_concept)
    by_id = dict(handbook.by_id)
    by_id[revalidated.concept_id] = revalidated
    candidate_handbook = TerminologyHandbook(concepts=tuple(by_id.values()))
    _validate_or_refuse(candidate_handbook)
    path = concepts_dir / f"{revalidated.concept_id}.toml"
    path.write_text(serialise_concept(revalidated), encoding=UTF_8_ENCODING, newline="\n")
    return path


def _revalidate_record(record: ConceptRecord) -> ConceptRecord:
    from pydantic import ValidationError

    try:
        return ConceptRecord.model_validate(record.model_dump(mode="python"))
    except (ValidationError, TerminologyValidationError) as exc:
        raise CurationError(f"refused: mutation would invalidate the concept: {exc}") from exc


def _validate_or_refuse(handbook: TerminologyHandbook) -> None:
    try:
        for validate in default_handbook_validators():
            validate(handbook)
    except TerminologyValidationError as exc:
        raise CurationError(f"refused: mutation would invalidate the handbook: {exc}") from exc


def _stamp(today: date | None) -> date:
    if today is not None:
        return today
    from cadrumo.core.time.clock import now

    return now().date()
