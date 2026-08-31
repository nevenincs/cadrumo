"""Strict TOML loader compiling the Terminology Handbook authoring tree.

This is the terminology-scale sibling of the registry authoring-compiler
pipeline (``TOML authoring tree -> loader/compiler -> strict schema
objects``). Each fragment under ``src/cadrumo/_data/terminology/concepts/``
is one concept; the loader parses every fragment, reshapes the nested
``[language.<code>]`` / ``[[language.<code>.term]]`` authoring layout into
the :class:`~dev.docs.terminology_handbook._schema.ConceptRecord` shape, compiles each
into a strict frozen record, then DERIVES every concept's ``narrower`` as
the inverse of the parsed ``broader`` edges across the whole set.

Validation that requires the full set or external authorities -- id
uniqueness beyond a single load, legal-ref resolution against the legal
catalogue, relation-target existence, approved-concept completeness -- is
deliberately NOT performed here. The loader exposes a clean seam for it:
:func:`load_terminology_handbook` accepts a ``validators`` sequence of
:data:`HandbookValidator` callables run against the assembled
:class:`TerminologyHandbook` immediately before it is returned, and
:class:`TerminologyHandbook` exposes the parsed records (and the raw
``broader`` edge map) so a validator can reason over the graph. The
sibling validation step bolts its gates on through this seam without
touching the loader body.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.toml import freeze_toml, read_toml, to_str_keyed_dict

from ._schema import ConceptRecord
from .errors import TerminologyLoadError, TerminologyValidationError

__all__ = [
    "HandbookValidator",
    "TerminologyHandbook",
    "load_terminology_handbook",
    "terminology_concepts_dir",
]

#: A validation hook: receives the assembled, narrower-derived handbook and
#: raises :class:`~dev.docs.terminology_handbook.errors.TerminologyValidationError`
#: (or any :class:`~dev.docs.terminology_handbook.errors.TerminologyError`) on a
#: violation. The sibling validation step supplies these; the loader runs
#: them as the final compile stage. Returning normally means "passed".
HandbookValidator = Callable[["TerminologyHandbook"], None]

_LANGUAGE_TABLE = "language"
_TERM_ARRAY = "term"
_CONCEPT_TABLE = "concept"


class TerminologyHandbook(BaseModel):
    """The compiled Terminology Handbook: every concept, narrower-derived.

    ``concepts`` is ordered by ``concept_id``. ``by_id`` and
    ``broader_edges`` are derived projections the validation seam reasons
    over -- ``broader_edges`` maps each ``concept_id`` to the tuple of
    concepts it declares as ``broader`` (the authoring edges, before
    inversion), so a relation-integrity validator can confirm every
    target exists without re-deriving the graph.
    """

    model_config = _STRICT_FROZEN

    concepts: tuple[ConceptRecord, ...] = Field(default=())

    @property
    def by_id(self) -> Mapping[str, ConceptRecord]:
        """Concept records keyed by their immutable ``concept_id``."""
        return {concept.concept_id: concept for concept in self.concepts}

    @property
    def broader_edges(self) -> Mapping[str, tuple[str, ...]]:
        """Authoring ``broader`` edges per concept (pre-inversion)."""
        return {concept.concept_id: concept.broader for concept in self.concepts}

    def concept(self, concept_id: str) -> ConceptRecord:
        """Return the :class:`ConceptRecord` for ``concept_id``."""
        found = self.by_id.get(concept_id)
        if found is None:
            raise TerminologyValidationError(f"unknown concept {concept_id!r}")
        return found


def terminology_concepts_dir() -> Path:
    """Return the bundled Terminology Handbook concepts directory."""
    return bundled_path("terminology", "concepts")


def load_terminology_handbook(
    concepts_dir: Path | None = None,
    *,
    validators: Sequence[HandbookValidator] = (),
) -> TerminologyHandbook:
    """Compile the Terminology Handbook authoring tree into typed records.

    Args:
        concepts_dir: Directory of per-concept TOML fragments. Defaults
            to the bundled :func:`terminology_concepts_dir`.
        validators: Validation hooks run against the assembled,
            narrower-derived handbook immediately before it is returned.
            This is the seam the sibling validation step uses to add
            id-uniqueness, legal-ref-resolution, relation-integrity, and
            approved-concept-completeness gates without modifying the
            loader. The deterministic ``narrower`` derivation and the
            per-fragment schema compilation always run; the hooks run
            last, over the whole set.

    Returns:
        A frozen :class:`TerminologyHandbook` with ``narrower`` derived
        on every concept.

    Raises:
        TerminologyLoadError: A fragment cannot be read or parsed.
        TerminologyValidationError: A fragment violates the schema, a
            fragment authors ``narrower`` (a derived-only field), a
            ``concept_id`` collides across fragments, or a supplied
            validator rejects the assembled handbook.
    """
    target = concepts_dir.resolve() if concepts_dir is not None else terminology_concepts_dir().resolve()
    records = _compile_records(str(target))
    handbook = _derive_narrower(records)
    for validate in validators:
        validate(handbook)
    return handbook


def _compile_records(concepts_dir: str) -> tuple[ConceptRecord, ...]:
    source = Path(concepts_dir)
    if not source.is_dir():
        raise TerminologyLoadError(f"{source}: terminology concepts directory not found")
    fragments = scan_directory(source, pattern="*.toml")
    if not fragments:
        raise TerminologyLoadError(f"{source}: no concept fragments found")
    records: list[ConceptRecord] = []
    seen: dict[str, Path] = {}
    for fragment in fragments:
        record = _compile_fragment(fragment)
        prior = seen.get(record.concept_id)
        if prior is not None:
            raise TerminologyValidationError(
                f"duplicate concept_id {record.concept_id!r}: {prior.name} and {fragment.name}",
            )
        if fragment.stem != record.concept_id:
            raise TerminologyValidationError(
                f"concept fragment {fragment.name!r} declares concept_id {record.concept_id!r}; "
                f"the file must be named {record.concept_id}.toml -- the curation write path "
                f"resolves by concept_id, so a filename mismatch silently forks the concept into "
                f"a duplicate file on the next edit",
            )
        seen[record.concept_id] = fragment
        records.append(record)
    records.sort(key=lambda record: record.concept_id)
    return tuple(records)


def _compile_fragment(fragment: Path) -> ConceptRecord:
    data = freeze_toml(
        read_toml(fragment, error_factory=lambda message: TerminologyLoadError(f"{fragment}: {message}")),
    )
    raw_concept = data.get(_CONCEPT_TABLE)
    if not isinstance(raw_concept, dict):
        raise TerminologyValidationError(f"{fragment}: missing [concept] table")
    if "narrower" in raw_concept:
        raise TerminologyValidationError(f"{fragment}: 'narrower' is derived at load and must not be authored")
    raw_languages = data.get(_LANGUAGE_TABLE)
    if not isinstance(raw_languages, dict) or not raw_languages:
        raise TerminologyValidationError(f"{fragment}: missing [language.<code>] sections")
    sections = tuple(_reshape_language(fragment, code, body) for code, body in raw_languages.items())
    payload = {**raw_concept, "languages": sections}
    try:
        return ConceptRecord.model_validate(payload)
    except ValidationError as exc:
        raise TerminologyValidationError(f"{fragment}: invalid concept fragment: {exc}") from exc


def _reshape_language(fragment: Path, code: object, body: object) -> dict[str, object]:
    if not isinstance(body, Mapping):
        raise TerminologyValidationError(f"{fragment}: language section {code!r} is not a table")
    keyed = to_str_keyed_dict(
        dict(body.items()),
        error_factory=lambda message: TerminologyValidationError(f"{fragment}: language {code!r}: {message}"),
    )
    raw_terms = keyed.get(_TERM_ARRAY, ())
    if not isinstance(raw_terms, tuple):
        raise TerminologyValidationError(f"{fragment}: language {code!r} [[language.{code}.term]] must be an array")
    section: dict[str, object] = {key: value for key, value in keyed.items() if key != _TERM_ARRAY}
    section["language"] = code
    section["terms"] = raw_terms
    return section


def _derive_narrower(records: tuple[ConceptRecord, ...]) -> TerminologyHandbook:
    inverse: dict[str, list[str]] = {record.concept_id: [] for record in records}
    for record in records:
        for parent in record.broader:
            inverse.setdefault(parent, []).append(record.concept_id)
    derived = tuple(
        record.model_copy(update={"narrower": tuple(sorted(inverse.get(record.concept_id, ())))}) for record in records
    )
    return TerminologyHandbook(concepts=derived)


_CACHE_MAX = 8


@lru_cache(maxsize=_CACHE_MAX)
def _bundled_handbook_cached(fingerprint: str) -> TerminologyHandbook:
    del fingerprint
    return load_terminology_handbook()


def load_bundled_terminology_handbook() -> TerminologyHandbook:
    """Load the bundled Handbook, caching by the concepts-tree fingerprint.

    The cache key is the complete fragment-tree fingerprint (every
    fragment path, size, and mtime), mirroring the registry rule that
    caches above the loader invalidate on the full tree, so an edit to
    any fragment busts the cache. Callers that pass validators or a
    custom directory bypass the cache via
    :func:`load_terminology_handbook` directly.
    """
    fingerprint = _concepts_tree_fingerprint(terminology_concepts_dir())
    return _bundled_handbook_cached(fingerprint)


def _concepts_tree_fingerprint(concepts_dir: Path) -> str:
    parts: list[str] = []
    for fragment in scan_directory(concepts_dir, pattern="*.toml"):
        stat = fragment.stat()
        parts.append(f"{fragment.name}:{stat.st_size}:{stat.st_mtime_ns}")
    return "|".join(parts)
