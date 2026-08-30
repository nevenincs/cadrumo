"""Product-side reader and search over the bundled Terminology Handbook.

The Handbook concept fragments under ``_data/terminology/concepts/*.toml`` are
authored/compiled by the terminology-handbook authoring tooling, which is
NOT shipped in the wheel. This module is the shipped, product-side consumer: a
lean strict loader that projects each concept for a requested locale and a
simple in-memory search over the small concept set.

Per the ``aeat-documentation`` rule the shipped search
surfaces only ``approved``-lifecycle concepts — the ratified taxpayer/operator
vocabulary — excluding ``draft`` (unreviewed) and ``deprecated`` (internal
machinery) concepts, which the taxpayer glossary also excludes. The lifecycle
axis itself is the core-owned :class:`~core.ConceptLifecycle` closed set, the
one home reachable from both this shipped reader and the unshipped authoring
tooling; a stored token that names no member is refused here rather than
silently filtered out of every result.

See Also:
    :func:`~application.corpus_search.search_terminology`
        Public facade for approved-concept terminology search.
    :func:`~application.corpus_search.lookup_terminology`
        Public facade for exact concept-id lookup.

Notes:
    External adapters may project ranked terminology hits into their own
    transport payloads without changing this product-side authority.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from ...core import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER, ConceptLifecycle
from ...core.text_fold import fold_diacritics
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.directory_scan import (
    scan_directory,
)
from ...core.external_constants import UTF_8_ENCODING
from ...core.resources import bundled_path
from .errors import CorpusSearchInputError

_Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

#: Canonical kebab-case shape for a Terminology Handbook ``concept_id``:
#: an immutable Spanish stem, lowercase, hyphen-separated. Shared with the
#: unshipped authoring schema (the authoring tooling's schema module,
#: which imports these three constants from this package) so a malformed
#: id is refused identically on both sides of the shipping boundary rather
#: than passing this lean product reader while failing strict authoring
#: validation.
CONCEPT_ID_PATTERN = r"^[a-z][a-z0-9-]*[a-z0-9]$"
CONCEPT_ID_MIN_LENGTH = 2
CONCEPT_ID_MAX_LENGTH = 64
_CONCEPT_ID_RE = re.compile(CONCEPT_ID_PATTERN)

_TERMINOLOGY_PARTS = ("terminology", "concepts")
_FALLBACK_LOCALE = "es"
_DEFAULT_LIFECYCLES = (ConceptLifecycle.APPROVED,)
_DEFAULT_LIMIT = 8

_WHITESPACE_RE = re.compile(r"\s+")


class TerminologyConcept(BaseModel):
    """One Handbook concept projected for a single locale."""

    model_config = _STRICT_FROZEN

    concept_id: _Text
    domain: _Text
    lifecycle: ConceptLifecycle
    locale: _Text
    preferred_label: _Text
    terms: tuple[str, ...] = ()
    short_description: str = ""
    definition: str = ""
    scope_note: str | None = None
    legal_refs: tuple[str, ...] = ()


class TerminologyHit(BaseModel):
    """One ranked terminology search result."""

    model_config = _STRICT_FROZEN

    concept_id: _Text
    preferred_label: _Text
    short_description: str = ""
    score: int = Field(ge=1)
    matched_on: _Text


def _fold(text: str) -> str:
    stripped = fold_diacritics(text)
    return _WHITESPACE_RE.sub(" ", stripped).strip().casefold()


def _terminology_root() -> Path:
    return bundled_path(*_TERMINOLOGY_PARTS)


def _as_str_object_dict(value: object) -> dict[str, object] | None:
    """Coerce a TOML-decoded value to a str-keyed dict, or ``None`` if it isn't one.

    TOML tables always decode to string-keyed dicts already; the comprehension
    reconstructs the mapping under a precise ``dict[str, object]`` type instead
    of the bare ``dict`` a plain ``isinstance`` narrows to.
    """
    if not isinstance(value, dict):
        return None
    return STR_KEYED_MAPPING_ADAPTER.validate_python(value)


def _validated_concept_id(token: str) -> str:
    """Refuse a ``concept_id`` outside the canonical kebab-case shape.

    Mirrors the authoring tooling's ``_ConceptId`` schema, which
    imports :data:`CONCEPT_ID_PATTERN` from this module: a malformed id
    (too short, uppercase, non-kebab-case) is refused here rather than
    silently producing a searchable concept with a garbage identifier.

    Raises:
        CorpusSearchInputError: If ``token`` does not match the canonical
            shape.
    """
    if not (CONCEPT_ID_MIN_LENGTH <= len(token) <= CONCEPT_ID_MAX_LENGTH) or _CONCEPT_ID_RE.fullmatch(token) is None:
        raise CorpusSearchInputError(
            reason="concept_id_malformed",
            context={"concept_id": token, "pattern": CONCEPT_ID_PATTERN},
        )
    return token


def _resolve_language(concept: dict[str, object], locale: str, *, concept_id: str) -> tuple[str, dict[str, object]]:
    """Resolve the ``(locale, language_block)`` a concept renders under.

    Raises:
        CorpusSearchInputError: If the fragment declares no ``[language.*]``
            section at all -- a structurally incomplete concept, never
            silently projected as an empty-text hit carrying its own
            ``concept_id`` as a fallback label.
    """
    languages = _as_str_object_dict(concept.get("language"))
    if not languages:
        raise CorpusSearchInputError(
            reason="concept_declares_no_language_sections",
            context={"concept_id": concept_id},
        )
    for candidate in (locale, _FALLBACK_LOCALE):
        block = _as_str_object_dict(languages.get(candidate))
        if block is not None:
            return candidate, block
    return _FALLBACK_LOCALE, {}


def _terms_and_preferred(language_block: dict[str, object]) -> tuple[str, tuple[str, ...]]:
    raw_terms = language_block.get("term")
    entries = OBJECT_TUPLE_ADAPTER.validate_python(raw_terms) if isinstance(raw_terms, list) else ()
    labels: list[str] = []
    preferred: str | None = None
    for entry in entries:
        entry_data = _as_str_object_dict(entry)
        if entry_data is None:
            continue
        label = entry_data.get("label")
        if not isinstance(label, str) or not label.strip():
            continue
        labels.append(label.strip())
        if entry_data.get("term_status") == "preferred" and preferred is None:
            preferred = label.strip()
        hidden = entry_data.get("hidden_search_forms")
        if isinstance(hidden, list):
            labels.extend(
                form.strip()
                for form in OBJECT_TUPLE_ADAPTER.validate_python(hidden)
                if isinstance(form, str) and form.strip()
            )
    resolved_preferred = preferred or (labels[0] if labels else "")
    return resolved_preferred, tuple(dict.fromkeys(labels))


def _hydrated_lifecycle(token: str, *, concept_id: str) -> ConceptLifecycle:
    """Hydrate a stored ``lifecycle`` token to its member, refusing an unknown one.

    A token outside the closed set is drift between the authoring tooling and
    the shipped reader, not a concept to skip: silently dropping it would erase
    the concept from every search result with no operator-visible signal.

    Raises:
        CorpusSearchInputError: If ``token`` names no
            :class:`~core.ConceptLifecycle` member.

    Returns:
        A :class:`~core.ConceptLifecycle`.
    """
    try:
        return ConceptLifecycle(token)
    except ValueError as exc:
        raise CorpusSearchInputError(
            reason="concept_lifecycle_unknown",
            context={
                "concept_id": concept_id,
                "lifecycle": token,
                "accepted": tuple(member.value for member in ConceptLifecycle),
            },
        ) from exc


def _project_concept(payload: dict[str, object], *, locale: str) -> TerminologyConcept | None:
    concept = _as_str_object_dict(payload.get("concept"))
    if concept is None:
        return None
    concept_id = concept.get("concept_id")
    domain = concept.get("domain")
    lifecycle = concept.get("lifecycle")
    if not (isinstance(concept_id, str) and isinstance(domain, str) and isinstance(lifecycle, str)):
        return None
    concept_id = _validated_concept_id(concept_id)
    resolved_lifecycle = _hydrated_lifecycle(lifecycle, concept_id=concept_id)
    resolved_locale, language_block = _resolve_language(payload, locale, concept_id=concept_id)
    preferred_label, terms = _terms_and_preferred(language_block)
    if not preferred_label:
        preferred_label = concept_id
    legal_refs = concept.get("legal_refs")
    return TerminologyConcept(
        concept_id=concept_id,
        domain=domain,
        lifecycle=resolved_lifecycle,
        locale=resolved_locale,
        preferred_label=preferred_label,
        terms=terms,
        short_description=_as_text(language_block.get("short_description")),
        definition=_as_text(language_block.get("definition")),
        scope_note=_as_optional_text(language_block.get("scope_note")),
        legal_refs=(
            tuple(ref for ref in OBJECT_TUPLE_ADAPTER.validate_python(legal_refs) if isinstance(ref, str))
            if isinstance(legal_refs, list)
            else ()
        ),
    )


def _as_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


@lru_cache(maxsize=8)
def load_terminology_concepts(locale: str = _FALLBACK_LOCALE) -> tuple[TerminologyConcept, ...]:
    """Load every Handbook concept projected for ``locale`` (fallback ``es``).

    Returns:
        A :class:`TerminologyConcept`.
    """
    root = _terminology_root()
    concepts: list[TerminologyConcept] = []
    for path in scan_directory(root, pattern="*.toml"):
        payload = tomllib.loads(path.read_text(encoding=UTF_8_ENCODING))
        projected = _project_concept(payload, locale=locale)
        if projected is not None:
            concepts.append(projected)
    return tuple(concepts)


def _match_score(concept: TerminologyConcept, needle: str) -> tuple[int, str]:
    folded_id = _fold(concept.concept_id)
    folded_labels = [(label, _fold(label)) for label in (concept.preferred_label, *concept.terms)]
    if needle == folded_id or any(needle == folded for _label, folded in folded_labels):
        return 100, concept.preferred_label
    for label, folded in folded_labels:
        if folded.startswith(needle):
            return 70, label
    for label, folded in folded_labels:
        if needle in folded:
            return 50, label
    if needle in _fold(concept.short_description):
        return 30, concept.preferred_label
    if needle in _fold(concept.definition):
        return 10, concept.preferred_label
    return 0, ""


def search_terminology(
    query: str,
    *,
    locale: str = _FALLBACK_LOCALE,
    limit: int = _DEFAULT_LIMIT,
    lifecycles: Iterable[ConceptLifecycle] = _DEFAULT_LIFECYCLES,
) -> tuple[TerminologyHit, ...]:
    """Search the Handbook for ``query``, returning ranked hits.

    Only concepts whose lifecycle is in ``lifecycles``
    (:attr:`~core.ConceptLifecycle.APPROVED` by default, the taxpayer-facing
    set) are considered.

    Raises:
        CorpusSearchInputError: If ``query`` is blank or ``limit`` is not
            positive.

    Returns:
        A :class:`TerminologyHit`.
    """
    needle = _fold(query)
    if not needle:
        raise CorpusSearchInputError(
            reason="query_empty",
            context={"query": query},
        )
    if limit <= 0:
        raise CorpusSearchInputError(
            reason="limit_not_positive",
            context={"limit": limit},
        )
    allowed = frozenset(lifecycles)
    scored: list[tuple[int, TerminologyHit]] = []
    for concept in load_terminology_concepts(locale):
        if concept.lifecycle not in allowed:
            continue
        score, matched = _match_score(concept, needle)
        if score <= 0:
            continue
        scored.append(
            (
                score,
                TerminologyHit(
                    concept_id=concept.concept_id,
                    preferred_label=concept.preferred_label,
                    short_description=concept.short_description,
                    score=score,
                    matched_on=matched,
                ),
            )
        )
    scored.sort(key=lambda item: (-item[0], item[1].concept_id))
    return tuple(hit for _score, hit in scored[:limit])


def lookup_terminology(concept_id: str, *, locale: str = _FALLBACK_LOCALE) -> TerminologyConcept:
    """Return one concept by id.

    Raises:
        CorpusSearchInputError: If ``concept_id`` is unknown.

    Returns:
        A :class:`TerminologyConcept`.
    """
    key = concept_id.strip()
    for concept in load_terminology_concepts(locale):
        if concept.concept_id == key:
            return concept
    raise CorpusSearchInputError(
        reason="concept_unknown",
        context={"concept_id": concept_id},
    )


__all__ = [
    "CONCEPT_ID_MAX_LENGTH",
    "CONCEPT_ID_MIN_LENGTH",
    "CONCEPT_ID_PATTERN",
    "TerminologyConcept",
    "TerminologyHit",
    "load_terminology_concepts",
    "lookup_terminology",
    "search_terminology",
]
