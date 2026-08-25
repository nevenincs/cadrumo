"""Validation gates for the compiled Terminology Handbook.

These gates are :data:`~dev.docs.terminology_handbook._loader.HandbookValidator`
callables bolted onto the loader's validation seam -- the loader body is
untouched. Each gate is a factory returning a closure over the assembled,
narrower-derived :class:`~dev.docs.terminology_handbook._loader.TerminologyHandbook`;
:func:`default_handbook_validators` assembles the full inventory in the
order the loader runs them.

The legal-ref gate resolves against the SAME legal catalogue the
registry calculation engine uses -- the authority's
:class:`~cadrumo.domain.calculations.registry.RegistryCatalogues` ``legal``
mapping, keyed by legal-ref id. It accepts an injected id
set so a unit test can resolve against a small synthetic catalogue,
defaulting to the bundled authority's catalogue for production and the
bundled-handbook gate.
"""

from __future__ import annotations

from collections.abc import Container

from cadrumo.core import ConceptLifecycle

from ._loader import HandbookValidator, TerminologyHandbook
from .errors import TerminologyValidationError

__all__ = [
    "approved_completeness_validator",
    "default_handbook_validators",
    "id_uniqueness_validator",
    "legal_refs_resolve_validator",
    "lifecycle_replaced_by_validator",
    "relation_integrity_validator",
]


def id_uniqueness_validator() -> HandbookValidator:
    """Gate: every ``concept_id`` is unique across the assembled handbook.

    The loader raises on a duplicate id while compiling fragments; this
    gate makes the invariant an explicit, independently testable member
    of the inventory and also enforces the never-reuse contract: a
    retired concept persists as a tombstone, so its id remains occupied
    and a re-minted live concept under the same id is caught here.
    """

    def _validate(handbook: TerminologyHandbook) -> None:
        seen: dict[str, int] = {}
        for concept in handbook.concepts:
            seen[concept.concept_id] = seen.get(concept.concept_id, 0) + 1
        duplicates = sorted(concept_id for concept_id, count in seen.items() if count > 1)
        if duplicates:
            raise TerminologyValidationError(f"duplicate concept_id(s): {duplicates!r}")

    return _validate


def legal_refs_resolve_validator(legal_ref_ids: Container[str] | None = None) -> HandbookValidator:
    """Gate: every ``legal_ref`` resolves in the legal catalogue.

    Args:
        legal_ref_ids: The set of legal-ref ids that resolve. Defaults to
            the bundled registry authority's legal catalogue keys
            (``bundled_authority().catalogues.legal``) -- the same
            catalogue the calculation engine grounds against. Passing an
            explicit container lets a unit test resolve against a small
            synthetic catalogue without loading the full registry.
    """
    resolved: Container[str] = _bundled_legal_ref_ids() if legal_ref_ids is None else legal_ref_ids

    def _validate(handbook: TerminologyHandbook) -> None:
        failures: list[str] = []
        for concept in handbook.concepts:
            for ref in concept.legal_refs:
                if ref not in resolved:
                    failures.append(f"concept {concept.concept_id!r}: legal_ref {ref!r} not in legal catalogue")
        if failures:
            raise TerminologyValidationError("unresolved legal_refs:\n" + "\n".join(f" - {f}" for f in failures))

    return _validate


def relation_integrity_validator() -> HandbookValidator:
    """Gate: every ``broader`` / ``related`` / ``replaced_by`` target exists.

    A relation pointing at a ``concept_id`` absent from the handbook is a
    dangling reference. ``replaced_by`` is checked here for existence;
    its non-retired-target and acyclicity contract is the
    :func:`lifecycle_replaced_by_validator`'s concern.
    """

    def _validate(handbook: TerminologyHandbook) -> None:
        known = set(handbook.by_id)
        failures: list[str] = []
        for concept in handbook.concepts:
            for axis_name, targets in (
                ("broader", concept.broader),
                ("related", concept.related),
            ):
                for target in targets:
                    if target not in known:
                        failures.append(f"concept {concept.concept_id!r}: {axis_name} target {target!r} does not exist")
            if concept.replaced_by is not None and concept.replaced_by not in known:
                failures.append(
                    f"concept {concept.concept_id!r}: replaced_by target {concept.replaced_by!r} does not exist",
                )
        if failures:
            raise TerminologyValidationError("dangling relation targets:\n" + "\n".join(f" - {f}" for f in failures))

    return _validate


def lifecycle_replaced_by_validator() -> HandbookValidator:
    """Gate: lifecycle / ``replaced_by`` integrity.

    Enforces, beyond the per-record biconditional the schema already
    holds (``replaced_by`` set exactly when ``retired``):

    * a ``retired`` concept's ``replaced_by`` points at a NON-retired
      concept -- a tombstone must redirect to a live successor, never to
      another tombstone;
    * a ``deprecated`` concept, when it declares ``replaced_by``, also
      points at a non-retired concept (deprecated carries an optional
      successor; if declared it must be live);
    * the ``replaced_by`` graph is acyclic -- no concept reaches itself by
      following successors.
    """

    def _validate(handbook: TerminologyHandbook) -> None:
        by_id = handbook.by_id
        failures: list[str] = []
        for concept in handbook.concepts:
            successor_id = concept.replaced_by
            if successor_id is None:
                continue
            successor = by_id.get(successor_id)
            if successor is None:
                # Existence is the relation_integrity gate's report; skip here.
                continue
            if successor.lifecycle is ConceptLifecycle.RETIRED:
                failures.append(f"concept {concept.concept_id!r}: replaced_by {successor_id!r} is itself retired")
        cycle = _first_replaced_by_cycle(handbook)
        if cycle is not None:
            failures.append("replaced_by cycle: " + " -> ".join(cycle))
        if failures:
            raise TerminologyValidationError(
                "lifecycle/replaced_by integrity:\n" + "\n".join(f" - {f}" for f in failures),
            )

    return _validate


def approved_completeness_validator() -> HandbookValidator:
    """Gate: an ``approved`` concept is curation-complete.

    An ``approved`` concept MUST carry, in its ``es`` section, a non-empty
    ``definition`` AND a ``source`` citation, and EVERY authored language
    section MUST carry a non-empty ``short_description``. ``draft`` (and
    ``deprecated`` / ``retired``) concepts are exempt: a draft with an
    empty definition is the curation-backlog signal the standing ratchet
    measures, not a hard failure here.
    """

    def _validate(handbook: TerminologyHandbook) -> None:
        from cadrumo.core.external_constants import OutputLanguage

        failures: list[str] = []
        for concept in handbook.concepts:
            if concept.lifecycle is not ConceptLifecycle.APPROVED:
                continue
            es = next(
                (section for section in concept.languages if section.language is OutputLanguage.ES),
                None,
            )
            if es is None:
                failures.append(f"concept {concept.concept_id!r}: approved concept has no es language section")
            else:
                if not (es.definition and es.definition.strip()):
                    failures.append(f"concept {concept.concept_id!r}: approved es section has no definition")
                if es.source is None or not es.source.citation.strip():
                    failures.append(f"concept {concept.concept_id!r}: approved es section has no source citation")
            for section in concept.languages:
                if not section.short_description.strip():
                    lang = section.language.value
                    failures.append(f"concept {concept.concept_id!r}: {lang!r} section has empty short_description")
        if failures:
            raise TerminologyValidationError(
                "approved-concept completeness:\n" + "\n".join(f" - {f}" for f in failures),
            )

    return _validate


def default_handbook_validators(legal_ref_ids: Container[str] | None = None) -> tuple[HandbookValidator, ...]:
    """Return the full validation gate inventory in loader-run order.

    Args:
        legal_ref_ids: Forwarded to :func:`legal_refs_resolve_validator`;
            defaults to the bundled authority catalogue.
    """
    return (
        id_uniqueness_validator(),
        relation_integrity_validator(),
        lifecycle_replaced_by_validator(),
        legal_refs_resolve_validator(legal_ref_ids),
        approved_completeness_validator(),
    )


def _bundled_legal_ref_ids() -> frozenset[str]:
    """Return every legal-reference id the bundled catalogue carries.

    Deliberately routed through the validated authority, and NOT through the
    raw compiler, even though that makes this refuse whenever the registry
    refuses. The compiler returns only the hand-authored legal entries; the
    authority additionally folds in the annual-Orden compiler's synthesised
    refs, which are more than half the catalogue. Reading the compiler here
    would return a legal-ref set missing those, and this set is used to decide
    whether a handbook concept's citation RESOLVES -- so the narrower set does
    not fail loudly, it rejects valid citations.

    A restored instrument returning a different population is worse than a
    blocked one. This one stays blocked until the registry validates.
    """
    from cadrumo.domain.calculations.registry import bundled_authority

    return frozenset(bundled_authority().catalogues.legal)


def _first_replaced_by_cycle(handbook: TerminologyHandbook) -> list[str] | None:
    by_id = handbook.by_id
    visited: set[str] = set()
    for start in by_id:
        if start in visited:
            continue
        path: list[str] = []
        seen_on_path: set[str] = set()
        current: str | None = start
        while current is not None and current in by_id:
            if current in seen_on_path:
                index = path.index(current)
                return [*path[index:], current]
            if current in visited:
                break
            seen_on_path.add(current)
            path.append(current)
            current = by_id[current].replaced_by
        visited.update(seen_on_path)
    return None
