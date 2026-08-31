"""The msgmerge three-outcome scaffold engine for the Terminology Handbook.

``scaffold`` reconciles the curated Handbook against the live enrolment
sources under the GNU gettext ``msgmerge`` contract: every run has
exactly three outcomes per concept --

* PRESERVE -- a concept already in the Handbook whose enrolment source
  still exists keeps ALL curated fields verbatim. Nothing the human
  authored (definition, short_description, scope_note, ratified term
  aliases, lifecycle, relations, legal_refs) is touched. Source-derived
  ``domain_refs`` are reconciled additively without overwriting a curated
  value.
* SCAFFOLD-EMPTY -- a newly discovered enrolable is written as a ``draft``
  concept with the curated prose fields EMPTY and clearly needing
  curation. There is NO fuzzy auto-fill: no definition, short_description,
  or scope_note is ever invented from a near neighbour (the documented
  gettext failure mode). A deterministic source label may seed one
  ``preferred`` term per language -- that is identity, not prose -- but the
  default fresh draft seeds none and carries a single placeholder
  short_description marking it for curation.
* RETIRE-TOMBSTONE -- a concept in the Handbook whose enrolment source has
  vanished is stamped ``lifecycle = retired`` plus ``replaced_by`` (or
  flagged for the operator to set ``replaced_by`` when no successor is
  inferable). It is NEVER deleted.

The engine first computes a :class:`ScaffoldPlan` (a structured diff) and
only then applies it. The plan IS the seam the sibling ``--check`` drift
gate consumes: ``--check`` computes the plan and reports it without
writing, exactly as the validation seam exposes its diff. Determinism:
stable ordering, canonical TOML serialisation, idempotent (a second run
with no source change produces an empty plan).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path

from cadrumo.core.concept_lifecycle import ConceptLifecycle
from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.external_constants import UTF_8_ENCODING, OutputLanguage

from ._enrolment import EnrolmentCandidate
from ._enums import TermStatus
from ._loader import load_terminology_handbook, terminology_concepts_dir
from ._schema import ConceptRecord, LanguageSection, TermSection
from ._serialize import serialise_concept

__all__ = [
    "ScaffoldAction",
    "ScaffoldEntry",
    "ScaffoldPlan",
    "apply_scaffold_plan",
    "build_scaffold_plan",
]

#: Placeholder short_description stamped on a scaffold-empty draft so the
#: required first-class field validates while remaining a visible curation
#: marker. It is never fuzzy-filled prose -- it says exactly "uncurated".
_DRAFT_PLACEHOLDER = "(sin curar) draft pendiente de definicion"

#: concept_id prefixes the scaffold OWNS -- one per machine enrolment-source
#: axis. The msgmerge retire outcome applies ONLY to a concept whose id
#: carries one of these prefixes (i.e. one the scaffold itself created from a
#: source) and whose source has since vanished. A hand-authored concept-grade
#: concept (e.g. ``prorrata``, a tax concept with no derivable source axis)
#: carries none of these prefixes, so a scaffold run never retires it -- it is
#: outside the scaffold's management, authored and retired by humans only.
_SCAFFOLD_MANAGED_PREFIXES: tuple[str, ...] = ("modelo-", "iva-", "periodo-", "tema-", "cli-")


def _is_scaffold_managed(concept_id: str) -> bool:
    return concept_id.startswith(_SCAFFOLD_MANAGED_PREFIXES)


class ScaffoldAction(StrEnum):
    """The three msgmerge outcomes plus the no-op."""

    PRESERVE = "preserve"
    SCAFFOLD_EMPTY = "scaffold_empty"
    RETIRE = "retire"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class ScaffoldEntry:
    """One concept's reconciliation outcome in a :class:`ScaffoldPlan`."""

    concept_id: str
    action: ScaffoldAction
    record: ConceptRecord
    #: Set on a RETIRE entry with no inferable successor, signalling the
    #: operator must set ``replaced_by`` by hand. The record still tombstones
    #: (retired) but carries a self-referential placeholder until curated.
    needs_replaced_by: bool = False


@dataclass(frozen=True, slots=True)
class ScaffoldPlan:
    """The structured diff a scaffold run will apply (the ``--check`` seam)."""

    entries: tuple[ScaffoldEntry, ...] = field(default=())

    def by_action(self, action: ScaffoldAction) -> tuple[ScaffoldEntry, ...]:
        """Return the entries for one outcome."""
        return tuple(entry for entry in self.entries if entry.action is action)

    @property
    def is_empty(self) -> bool:
        """True when no concept changes (every entry is UNCHANGED)."""
        return all(entry.action is ScaffoldAction.UNCHANGED for entry in self.entries)

    @property
    def counts(self) -> Mapping[ScaffoldAction, int]:
        """Outcome counts keyed by action, for the report surface."""
        counts: dict[ScaffoldAction, int] = dict.fromkeys(ScaffoldAction, 0)
        for entry in self.entries:
            counts[entry.action] += 1
        return counts


def build_scaffold_plan(
    candidates: Mapping[str, EnrolmentCandidate],
    existing: Mapping[str, ConceptRecord],
    *,
    today: date,
) -> ScaffoldPlan:
    """Compute the three-outcome plan reconciling ``existing`` against ``candidates``.

    Args:
        candidates: Enrolment candidates keyed by ``concept_id`` (the live
            source-derived expected set).
        existing: The currently curated concepts keyed by ``concept_id``.
        today: The date stamped on newly created drafts and on the
            ``updated_at`` of a freshly tombstoned concept; injected so the
            plan is deterministic and testable.

    Returns:
        A :class:`ScaffoldPlan` whose entries are sorted by ``concept_id``.
    """
    entries: list[ScaffoldEntry] = []
    expected_ids = set(candidates)
    existing_ids = set(existing)

    for concept_id in sorted(expected_ids | existing_ids):
        candidate = candidates.get(concept_id)
        current = existing.get(concept_id)
        if current is not None and candidate is not None:
            entries.append(_reconcile_present(concept_id, candidate, current))
        elif candidate is not None:
            entries.append(_scaffold_empty(candidate, today=today))
        else:
            assert current is not None
            if _is_scaffold_managed(concept_id):
                entries.append(_retire(current, today=today))
            else:
                # Hand-authored concept outside the scaffold's source axes:
                # the scaffold neither created nor retires it.
                entries.append(ScaffoldEntry(concept_id=concept_id, action=ScaffoldAction.UNCHANGED, record=current))
    return ScaffoldPlan(entries=tuple(entries))


def _reconcile_present(
    concept_id: str,
    candidate: EnrolmentCandidate,
    current: ConceptRecord,
) -> ScaffoldEntry:
    """PRESERVE: keep every curated field; reconcile source domain_refs additively."""
    merged_refs = _merge_domain_refs(current.domain_refs, candidate.domain_refs)
    if merged_refs == current.domain_refs:
        return ScaffoldEntry(concept_id=concept_id, action=ScaffoldAction.UNCHANGED, record=current)
    # domain_refs is machine-owned metadata; refreshing it never touches a
    # curated prose field, term, relation, or lifecycle.
    refreshed = current.model_copy(update={"domain_refs": merged_refs})
    return ScaffoldEntry(concept_id=concept_id, action=ScaffoldAction.PRESERVE, record=refreshed)


def _merge_domain_refs(curated: tuple[str, ...], source: tuple[str, ...]) -> tuple[str, ...]:
    merged = list(curated)
    for ref in source:
        if ref not in merged:
            merged.append(ref)
    return tuple(merged)


def _scaffold_empty(candidate: EnrolmentCandidate, *, today: date) -> ScaffoldEntry:
    """SCAFFOLD-EMPTY: a bare draft, no fuzzy prose."""
    languages = tuple(_empty_language_section(candidate, language) for language in (OutputLanguage.ES,))
    record = ConceptRecord(
        concept_id=candidate.concept_id,
        domain=candidate.domain,
        lifecycle=ConceptLifecycle.DRAFT,
        domain_refs=candidate.domain_refs,
        created_at=today,
        updated_at=today,
        languages=languages,
    )
    return ScaffoldEntry(concept_id=candidate.concept_id, action=ScaffoldAction.SCAFFOLD_EMPTY, record=record)


def _empty_language_section(candidate: EnrolmentCandidate, language: OutputLanguage) -> LanguageSection:
    seed = next((label for label in candidate.seed_labels if label.language is language), None)
    terms: tuple[TermSection, ...] = ()
    if seed is not None:
        terms = (TermSection(label=seed.label, term_status=TermStatus.PREFERRED),)
    return LanguageSection(
        language=language,
        short_description=_DRAFT_PLACEHOLDER,
        terms=terms,
    )


def _retire(current: ConceptRecord, *, today: date) -> ScaffoldEntry:
    """RETIRE-TOMBSTONE: stamp retired + replaced_by; never delete."""
    if current.lifecycle is ConceptLifecycle.RETIRED:
        # Already tombstoned; a vanished source for an already-retired
        # concept is a no-op (it stays a tombstone).
        return ScaffoldEntry(concept_id=current.concept_id, action=ScaffoldAction.UNCHANGED, record=current)
    replaced_by = current.replaced_by
    needs_replaced_by = replaced_by is None
    if replaced_by is None:
        # No inferable successor: tombstone but flag the operator to set
        # replaced_by. The schema requires a non-self replaced_by on a
        # retired concept, so we cannot self-reference; instead we keep the
        # concept DEPRECATED (a valid lifecycle that needs no replaced_by)
        # and flag it, rather than minting a fake successor.
        retired = current.model_copy(update={"lifecycle": ConceptLifecycle.DEPRECATED, "updated_at": today})
        return ScaffoldEntry(
            concept_id=current.concept_id,
            action=ScaffoldAction.RETIRE,
            record=retired,
            needs_replaced_by=True,
        )
    retired = current.model_copy(update={"lifecycle": ConceptLifecycle.RETIRED, "updated_at": today})
    return ScaffoldEntry(
        concept_id=current.concept_id,
        action=ScaffoldAction.RETIRE,
        record=retired,
        needs_replaced_by=needs_replaced_by,
    )


def apply_scaffold_plan(plan: ScaffoldPlan, concepts_dir: Path) -> tuple[Path, ...]:
    """Write the plan's PRESERVE / SCAFFOLD-EMPTY / RETIRE entries to disk.

    UNCHANGED entries are not rewritten (idempotence: a no-change run
    touches no file). Returns the paths written, sorted.
    """
    written: list[Path] = []
    concepts_dir.mkdir(parents=True, exist_ok=True)
    for entry in plan.entries:
        if entry.action is ScaffoldAction.UNCHANGED:
            continue
        path = concepts_dir / f"{entry.concept_id}.toml"
        path.write_text(serialise_concept(entry.record), encoding=UTF_8_ENCODING, newline="\n")
        written.append(path)
    return tuple(sorted(written))


def scaffold_handbook(
    concepts_dir: Path | None = None,
    candidates: Mapping[str, EnrolmentCandidate] | None = None,
    *,
    today: date | None = None,
    apply: bool = True,
) -> ScaffoldPlan:
    """Compute (and optionally apply) the scaffold plan for the bundled tree.

    Args:
        concepts_dir: Handbook concepts directory; defaults to the bundled
            tree.
        candidates: Enrolment candidates; defaults to walking every live
            source via :func:`~dev.docs.terminology_handbook._enrolment.collect_enrolment_candidates`.
        today: Date stamped on new/retired records; defaults to the system
            date.
        apply: When True, write the plan; when False, compute only (the
            ``--check`` dry-run mode).

    Returns:
        The computed :class:`ScaffoldPlan`.
    """
    from ._enrolment import collect_enrolment_candidates

    target = concepts_dir if concepts_dir is not None else terminology_concepts_dir()
    resolved_candidates = candidates if candidates is not None else collect_enrolment_candidates()
    existing = _load_existing(target)
    stamp = today if today is not None else _today()
    plan = build_scaffold_plan(resolved_candidates, existing, today=stamp)
    if apply:
        apply_scaffold_plan(plan, target)
    return plan


def _load_existing(concepts_dir: Path) -> dict[str, ConceptRecord]:
    if not concepts_dir.is_dir() or not any(iter_directory(concepts_dir, pattern="*.toml")):
        return {}
    handbook = load_terminology_handbook(concepts_dir)
    return dict(handbook.by_id)


def _today() -> date:
    from cadrumo.core.time import now

    return now().date()
