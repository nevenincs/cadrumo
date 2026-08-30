"""Enrolment-source walkers for the Terminology Handbook scaffold.

The scaffold enrols CONCEPT-GRADE vocabulary only -- the bounded set of
enrolables (modelos, IVA categories, period codes, registry topics, CLI
leaf verbs), each consumed through its existing authority, never
re-parsed. The 18,885 casillas and the 262 legal provisions
are PROJECTED at compile time by a separate compiler, never
scaffolded as Handbook concepts: turning a per-casilla or per-provision
row into a curated concept recreates the bulk-enrolment disease the
scale-control rule forbids. Legal provisions surface through concept
``legal_refs`` links, not as 262 curated concepts.

Each walker yields :class:`EnrolmentCandidate` records carrying the
machine-known identity (a deterministic Spanish-stem ``concept_id``, the
``domain``, source-derived ``domain_refs`` and a canonical preferred
label). These are the source-derived facts the scaffold's three-outcome
engine diffs against the existing curated handbook; the curated prose
(definition, short_description, scope_note, ratified aliases) is never
emitted here -- that is the human's to author, and the gettext failure
mode (fuzzy carry-forward of near-neighbour prose) is structurally
impossible because no walker produces prose.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from cadrumo.core.external_constants import OutputLanguage

from ._enums import ConceptDomain

__all__ = [
    "EnrolmentCandidate",
    "SeedLabel",
    "collect_enrolment_candidates",
]


@dataclass(frozen=True, slots=True)
class SeedLabel:
    """A deterministic source-provided canonical label for a language.

    The scaffold may seed exactly one ``preferred`` term per language
    section from a source label (e.g. the modelo official name, the enum
    member). This is deterministic identity, not fuzzy prose: it never
    seeds a ``definition`` or ``short_description``.
    """

    language: OutputLanguage
    label: str


@dataclass(frozen=True, slots=True)
class EnrolmentCandidate:
    """One concept-grade enrolable discovered from an authority.

    ``concept_id`` is the deterministic Spanish-stem identifier the
    scaffold uses as the merge key; ``domain`` is the closed axis;
    ``domain_refs`` are typed back-references into the source entity;
    ``seed_labels`` are the deterministic canonical labels a fresh draft
    may seed as ``preferred`` terms.
    """

    concept_id: str
    domain: ConceptDomain
    domain_refs: tuple[str, ...] = ()
    seed_labels: tuple[SeedLabel, ...] = field(default=())


def collect_enrolment_candidates(
    *,
    modelos: bool = True,
    iva_categories: bool = True,
    periods: bool = True,
    topics: bool = True,
    cli_verbs: bool = False,
) -> dict[str, EnrolmentCandidate]:
    """Walk every enrolment source and return candidates keyed by ``concept_id``.

    Each axis is consumed through its authority (registry via the
    validated authority, enums by import, topics via the catalogue
    repository, and the CLI via its public immutable graph projection). The boolean toggles let
    tests drive a controlled subset deterministically without standing up
    every authority.

    ``cli_verbs`` defaults to False: CLI verbs are a searchable namespace
    PROJECTED at compile time, not scaffolded as curated
    concepts. The walker is retained behind the toggle so a
    future decision can revisit, but the default concept-grade set is the
    bounded modelo / IVA / period / topic axes.

    Raises:
        ValueError: Two sources mint the same ``concept_id`` -- a
            namespace collision the deterministic prefixes are designed to
            prevent; surfaced loudly rather than silently dropped.
    """
    candidates: dict[str, EnrolmentCandidate] = {}
    walkers: list[Iterator[EnrolmentCandidate]] = []
    if modelos:
        walkers.append(_walk_modelos())
    if iva_categories:
        walkers.append(_walk_iva_categories())
    if periods:
        walkers.append(_walk_periods())
    if topics:
        walkers.append(_walk_topics())
    if cli_verbs:
        walkers.append(_walk_cli_verbs())
    for walker in walkers:
        for candidate in walker:
            existing = candidates.get(candidate.concept_id)
            if existing is not None and existing != candidate:
                raise ValueError(f"enrolment concept_id collision: {candidate.concept_id!r} minted by two sources")
            candidates[candidate.concept_id] = candidate
    return candidates


def _kebab(value: str) -> str:
    return value.replace("_", "-").replace(".", "-").lower()


def _walk_modelos() -> Iterator[EnrolmentCandidate]:
    """Yield a candidate per REGISTRY-BACKED modelo.

    ``Modelo`` is a typing device, not a glossary. It exists so production code
    references a modelo through an enum member rather than a bare three-digit
    literal, so it necessarily carries every code the codebase mentions --
    including the retired and code-referenced-only forms the codebase itself
    declares in ``NON_REGISTRY_MODELOS`` as having no registry definition.

    Walking the whole enum conflated "identifier the code references" with
    "concept a taxpayer looks up". The cost was measurable and invisible: 76 of
    the enum's 149 members are non-registry, and enrolling them made the
    Handbook report 118 unenrolled concepts against a committed 117 -- a backlog
    that would have tripled the curation ratchet, produced entirely by a change
    made in a different subsystem for unrelated reasons. Nobody saw it because
    the gate that reports it lived in a directory no test lane collected.

    Excluding them creates and deletes nothing. It narrows the candidate set to
    the forms this product actually models, which is what
    ``aeat-documentation`` asks of an approved concept.
    """
    from cadrumo.core import NON_REGISTRY_MODELOS, Modelo

    for modelo in sorted(Modelo, key=lambda member: member.value):
        if modelo in NON_REGISTRY_MODELOS:
            continue
        yield EnrolmentCandidate(
            concept_id=f"modelo-{modelo.value}",
            domain=ConceptDomain.MODELO,
            domain_refs=(f"modelo:{modelo.value}",),
        )


def _walk_iva_categories() -> Iterator[EnrolmentCandidate]:
    from cadrumo.domain.iva.schema import IvaCategory

    for category in sorted(IvaCategory, key=lambda member: member.value):
        yield EnrolmentCandidate(
            concept_id=f"iva-{_kebab(category.value)}",
            domain=ConceptDomain.REGIMEN,
            domain_refs=(f"iva-category:{category.value}",),
        )


def _walk_periods() -> Iterator[EnrolmentCandidate]:
    from cadrumo.core.period import StandardPeriodCode

    for period in sorted(StandardPeriodCode, key=lambda member: member.value):
        yield EnrolmentCandidate(
            concept_id=f"periodo-{_kebab(period.value)}",
            domain=ConceptDomain.PERIODO,
            domain_refs=(f"period:{period.value}",),
        )


def _walk_topics() -> Iterator[EnrolmentCandidate]:
    from cadrumo.core.topics import load_topic_catalogue

    catalogue = load_topic_catalogue()
    for topic in sorted(catalogue.topics, key=lambda item: item.slug):
        yield EnrolmentCandidate(
            concept_id=f"tema-{topic.slug}",
            domain=ConceptDomain.CONCEPTO,
            domain_refs=(f"topic:{topic.slug}",),
        )


def _walk_cli_verbs() -> Iterator[EnrolmentCandidate]:
    leaf_paths = _cli_leaf_command_paths()
    for path in sorted(leaf_paths):
        # Drop the root program name; the verb identity is the command path.
        verb_path = path[1:] if len(path) > 1 else path
        slug = "-".join(_kebab(token) for token in verb_path)
        if not slug:
            continue
        # The domain_ref keeps the command path colon-joined so it matches the
        # typed domain-ref pattern (no spaces); the human command form is
        # recoverable by splitting on the colon.
        ref_path = ":".join(verb_path)
        yield EnrolmentCandidate(
            concept_id=f"cli-{slug}",
            domain=ConceptDomain.CLI_VERB,
            domain_refs=(f"cli:{ref_path}",),
        )


def _cli_leaf_command_paths() -> tuple[tuple[str, ...], ...]:
    """Return every operator leaf path from the immutable command authority."""
    from cadrumo.entrypoints.cli.command_api import command_spec_nodes

    return tuple(node.path for node in command_spec_nodes() if node.spec.kind == "leaf")
