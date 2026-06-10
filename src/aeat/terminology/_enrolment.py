"""Enrolment-source walkers for the Terminology Handbook scaffold.

The scaffold enrols CONCEPT-GRADE vocabulary only -- the bounded set of
enrolables (modelos, IVA categories, period codes, registry topics, CLI
leaf verbs), each consumed through its existing authority, never
re-parsed. Per ADR D4 the 18,885 casillas and the 262 legal provisions
are PROJECTED at compile time (a separate compiler, W03.P07), never
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

from ..core.external_constants import OutputLanguage
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
    cli_verbs: bool = True,
) -> dict[str, EnrolmentCandidate]:
    """Walk every enrolment source and return candidates keyed by ``concept_id``.

    Each axis is consumed through its authority (registry via the
    validated authority, enums by import, topics via the catalogue
    repository, the CLI via Typer introspection). The boolean toggles let
    tests drive a controlled subset deterministically without standing up
    every authority.

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
    from ..core import Modelo

    for modelo in sorted(Modelo, key=lambda member: member.value):
        yield EnrolmentCandidate(
            concept_id=f"modelo-{modelo.value}",
            domain=ConceptDomain.MODELO,
            domain_refs=(f"modelo:{modelo.value}",),
        )


def _walk_iva_categories() -> Iterator[EnrolmentCandidate]:
    from ..domain.iva import IvaCategory

    for category in sorted(IvaCategory, key=lambda member: member.value):
        yield EnrolmentCandidate(
            concept_id=f"iva-{_kebab(category.value)}",
            domain=ConceptDomain.REGIMEN,
            domain_refs=(f"iva-category:{category.value}",),
        )


def _walk_periods() -> Iterator[EnrolmentCandidate]:
    from ..core._period import StandardPeriodCode

    for period in sorted(StandardPeriodCode, key=lambda member: member.value):
        yield EnrolmentCandidate(
            concept_id=f"periodo-{_kebab(period.value)}",
            domain=ConceptDomain.PERIODO,
            domain_refs=(f"period:{period.value}",),
        )


def _walk_topics() -> Iterator[EnrolmentCandidate]:
    from ..core.topics import load_topic_catalogue

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
    """Return every operator CLI leaf-command path via Typer introspection.

    Mirrors the house tree-walk in ``dev/docs/cli_reference.py``
    (``typer.main.get_command`` then a recursive group walk) rather than
    re-inventing command discovery.
    """
    import click
    from typer.main import get_command

    from ..entrypoints.cli import app

    root = get_command(app)
    leaves: list[tuple[str, ...]] = []

    def _walk(cmd: object, path: tuple[str, ...]) -> None:
        if not isinstance(cmd, click.Group):
            leaves.append(path)
            return
        with click.Context(cmd, info_name=cmd.name or None) as ctx:
            for child_name in cmd.list_commands(ctx):
                child = cmd.get_command(ctx, child_name)
                if child is not None:
                    _walk(child, (*path, child_name))

    root_name = getattr(root, "name", None) or "aeat"
    _walk(root, (root_name,))
    return tuple(leaves)
