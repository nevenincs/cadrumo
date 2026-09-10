"""Screen: whether a successor edition states a casilla row it would inherit unchanged.

A successor edition only needs to state the casilla rows that are new in it or
that differ from the row carrying the same lineage in its predecessor edition.
A stated row identical to that inherited row adds nothing but maintenance: it is
the copy delta authoring exists to remove. This screen names those rows.

Four conditions are reported:

- ``restated_unchanged`` - a stated row equals, once edition restatement is
  removed, the row carrying the same ``continuidad_id`` in the predecessor
  edition. It is the only condition that says an edition is non-minimal.
- ``unchecked_no_lineage`` - the row carries no ``continuidad_id``, so no
  inherited row can be identified and minimality cannot be judged. Reported so
  that an unjudged row is never counted as a minimal one.
- ``unchecked_ambiguous_lineage`` - the predecessor edition carries the row's
  chain on more than one row, so which row would be inherited is undecided.
- ``unchecked_predecessor_undecidable`` - the edition declares no predecessor
  and its adjacent earlier edition overlaps it in period, so the pair may be
  parallel variants rather than a sequence and there is no predecessor to
  measure against. Every row of such an edition is reported.

A row that differs from its inherited row, and a row whose chain the predecessor
does not carry, is a legitimate statement and is not a finding. A root edition -
one declaring an explicit no-predecessor, or the first of an undeclaring modelo
by validity order - inherits nothing, so its rows are not applicable rather than
clean, and the census counts them apart.

Which rows are judged. Only the rows an edition states. A delta edition's loaded
casillas also hold the rows it inherits, each marked by the loader with
``inherited_from``; those are counted apart and never judged, since an inherited
row is the minimal form by definition.

What "identical" compares. A stated row is compared with what inheriting the
predecessor's row would give, both as loaded ``CasillaDefinition`` values, never
as authored text, after removing the tokens whose only content is the edition
the row sits in:

- ``source_refs`` are compared as a set after removing each edition's own
  ``casilla_source_refs`` default, top level and inside ``constraints``, when
  both editions declare one: what is left is the row's own additions, which
  travel with an inherited row. Where either edition declares no default they
  are dropped, since nothing then separates the edition's grounding from the
  row's.
- ``export_refs`` are dropped: the slot identifier carries the edition and its
  ordinal moves on insertion, so the field is derived per edition rather than
  inherited.
- ``continuidad_origin`` and ``continuidad_evidence`` are unset on the inherited
  side only: they state a row's relationship to its predecessor and are never
  inherited, so a stated row carrying either is a statement inheritance cannot
  reproduce. ``continuidad_id`` is the match key and is equal.
- ``legal_refs`` are compared as a set after removing the edition's own
  ``orden_aplicabilidad`` entries, top level and inside ``constraints``: an orden
  reissued with the edition re-cites the same content, and array order is not
  meaningful to any consumer.
- ``formula``, ``binding`` and ``alternate_bindings`` are compared by lineage,
  the edition's own revision identifier replaced by a placeholder wherever it
  sits as a whole segment, because those identifiers embed the edition key.

Every other field is compared exactly, including ``id``, ``number``,
``section``, ``semantic_role``, ``data_type`` and ``input_kind``, where the
corpus's genuine differences sit. A field the schema gains later is compared by
default, which errs toward reporting a difference: a new edition-local field
would hide restatement rather than invent it.

Where it stops:

- Casilla rows only. The completeness manifest does not inherit - a migrated
  edition restates its whole manifest by design - so it is never read here, and
  neither are formulas, bindings, layouts or any other family.
- Stated rows are the loaded rows whose ``inherited_from`` is unset. The marker
  is the loader's; a definition built outside the loader carries whatever
  markers it was given, and a row wrongly marked inherited escapes judgement.
- The comparison is of loaded values, which do not show whether the
  predecessor's row states its ``source_refs`` in full or as additions. Where it
  states them in full, inheriting would carry the predecessor's design citation
  forward, yet the row reads as a restatement once both defaults are removed.
- An edition declaring no predecessor is measured against the adjacent earlier
  edition by validity order - the pairing a declared predecessor must agree with
  wherever the two editions do not overlap. A declared predecessor is always
  used as declared.
- Labels are not compared. Locale keys are edition-scoped and label text
  inherits through the locale catalogue, not through the row.
- A formula or binding reference is compared by lineage, not by resolving it to
  the successor edition's declaration of that lineage.

The screen exits 0 whatever it finds. It reports; it does not gate.
"""

from __future__ import annotations

import collections
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.identifier_lineage import identifier_lineage
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions, revisions_overlap
from cadrumo.domain.calculations.registry.schema import (
    DeclaredPredecessor,
    ModeloDefinition,
    ModeloRevision,
    NoPredecessor,
)
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from dev.registry.compiler.authority import compiled_bundled_authority

from .corpus import bundled_modelo_ids

__all__ = [
    "EDITION_LOCAL_FIELDS",
    "KINDS",
    "LINEAGE_CLAIM_FIELDS",
    "EditionPredecessor",
    "MinimalityCensus",
    "MinimalityVerdict",
    "PredecessorBasis",
    "RowJudgement",
    "definition_findings",
    "edition_predecessors",
    "inheritable_value",
    "judge_definition",
    "minimality_census",
    "restatement_differences",
    "restating_modelos",
    "screen_authority",
    "stated_casillas",
    "stated_value",
]


class MinimalityVerdict(StrEnum):
    """Why a stated casilla row's minimality could or could not be judged.

    ``RESTATED_UNCHANGED`` is the only member that says an edition is
    non-minimal. The ``UNCHECKED_*`` members report that judgement could not
    be reached at all, so an unjudged row is never counted as a minimal one.
    ``STATED_DIFFERENCE`` and ``NEW_IN_EDITION`` are legitimate statements, not
    findings; see :data:`KINDS` for the subset that is.
    """

    RESTATED_UNCHANGED = "restated_unchanged"
    UNCHECKED_NO_LINEAGE = "unchecked_no_lineage"
    UNCHECKED_AMBIGUOUS_LINEAGE = "unchecked_ambiguous_lineage"
    UNCHECKED_PREDECESSOR_UNDECIDABLE = "unchecked_predecessor_undecidable"
    STATED_DIFFERENCE = "stated_difference"
    NEW_IN_EDITION = "new_in_edition"


KINDS: Final[tuple[MinimalityVerdict, ...]] = (
    MinimalityVerdict.RESTATED_UNCHANGED,
    MinimalityVerdict.UNCHECKED_NO_LINEAGE,
    MinimalityVerdict.UNCHECKED_AMBIGUOUS_LINEAGE,
    MinimalityVerdict.UNCHECKED_PREDECESSOR_UNDECIDABLE,
)

#: Casilla fields compared net of, or not at all beside, the edition they sit in:
#: ``source_refs`` net of the edition default, ``export_refs`` never.
EDITION_LOCAL_FIELDS: Final[frozenset[str]] = frozenset({"source_refs", "export_refs"})

#: Casilla fields stating a row's relationship to its predecessor, which an
#: inherited row never carries.
LINEAGE_CLAIM_FIELDS: Final[frozenset[str]] = frozenset({"continuidad_origin", "continuidad_evidence"})


class PredecessorBasis(StrEnum):
    """How an edition's predecessor was established."""

    DECLARED = "declared"
    ROOT_DECLARED = "declared_none"
    ROOT_FIRST_IN_ORDER = "first_in_order"
    ADJACENT = "adjacent_in_order"
    UNDECIDABLE = "undecidable"


_IDENTIFIER_FIELDS: Final[tuple[str, ...]] = ("formula", "binding", "alternate_bindings")


@dataclass(frozen=True, slots=True)
class EditionPredecessor:
    """The edition a revision would inherit from, and how that was established."""

    revision: str
    predecessor: str | None
    basis: PredecessorBasis


@dataclass(frozen=True, slots=True)
class RowJudgement:
    """One stated casilla row of a non-root edition and its minimality verdict.

    The screen's findings are the judgements whose kind is in :data:`KINDS`; the
    other two verdicts are legitimate statements and are counted in the census.
    """

    modelo: str
    revision: str
    predecessor: str | None
    casilla: str
    kind: MinimalityVerdict
    detail: str


@dataclass(frozen=True, slots=True)
class MinimalityCensus:
    """Corpus-wide counts reported beside the findings, so no denominator is implied."""

    editions: int
    root_editions: int
    declared_predecessor_editions: int
    rows_judged: int
    rows_inherited: int
    rows_in_root_editions: int
    verdicts: Mapping[MinimalityVerdict, int]


def edition_predecessors(definition: ModeloDefinition) -> tuple[EditionPredecessor, ...]:
    """Return, per revision in validity order, the edition it would inherit from."""
    ordered = ordered_revisions(definition)
    resolved: list[EditionPredecessor] = []
    for position, revision in enumerate(ordered):
        declared = revision.predecessor
        if isinstance(declared, DeclaredPredecessor):
            resolved.append(EditionPredecessor(str(revision.id), str(declared.revision_id), PredecessorBasis.DECLARED))
        elif isinstance(declared, NoPredecessor):
            resolved.append(EditionPredecessor(str(revision.id), None, PredecessorBasis.ROOT_DECLARED))
        elif position == 0:
            resolved.append(EditionPredecessor(str(revision.id), None, PredecessorBasis.ROOT_FIRST_IN_ORDER))
        else:
            earlier = ordered[position - 1]
            if revisions_overlap(earlier, revision):
                resolved.append(EditionPredecessor(str(revision.id), str(earlier.id), PredecessorBasis.UNDECIDABLE))
            else:
                resolved.append(EditionPredecessor(str(revision.id), str(earlier.id), PredecessorBasis.ADJACENT))
    return tuple(resolved)


def _refs_net_of(values: object, own: frozenset[str]) -> frozenset[str]:
    if not isinstance(values, tuple | list):
        return frozenset[str]()
    return frozenset(str(value) for value in values) - own


def _source_default(revision: ModeloRevision) -> frozenset[str] | None:
    default = revision.casilla_source_refs
    return None if not default else frozenset(str(ref) for ref in default)


def stated_value(
    casilla: CasillaDefinition,
    revision: ModeloRevision,
    *,
    source_default: frozenset[str] | None = None,
) -> dict[str, object]:
    """Return a casilla row with every token repeating its own edition removed.

    The row's typed dump normalised as the module docstring lists. Its
    ``source_refs`` are kept net of ``source_default`` when one is given and
    dropped otherwise; the caller passes the edition's default only when both
    editions of a comparison declare one.
    """
    revision_id = str(revision.id)
    own_ordenes = frozenset(str(ref) for ref in revision.orden_aplicabilidad)
    value: dict[str, object] = dict(casilla.model_dump(mode="python", exclude=set(EDITION_LOCAL_FIELDS)))
    value["legal_refs"] = _refs_net_of(value.get("legal_refs"), own_ordenes)
    if source_default is not None:
        value["source_refs"] = _refs_net_of(casilla.source_refs, source_default)
    constraints = value.get("constraints")
    if isinstance(constraints, dict):
        constraint_sources = constraints.pop("source_refs", None)
        if source_default is not None:
            constraints["source_refs"] = _refs_net_of(constraint_sources, source_default)
        constraints["legal_refs"] = _refs_net_of(constraints.get("legal_refs"), own_ordenes)
    for name in _IDENTIFIER_FIELDS:
        current = value.get(name)
        if isinstance(current, str):
            value[name] = identifier_lineage(current, revision_id)
        elif isinstance(current, tuple):
            value[name] = tuple(identifier_lineage(str(item), revision_id) for item in current)
    return value


def inheritable_value(
    casilla: CasillaDefinition,
    revision: ModeloRevision,
    *,
    source_default: frozenset[str] | None = None,
) -> dict[str, object]:
    """Return the part of a casilla row an inheriting edition would carry.

    :func:`stated_value` with the row's lineage claims unset, as an inherited
    row materialises. A stated row restates its inherited row exactly when its
    stated value equals the inherited row's inheritable value.
    """
    value = stated_value(casilla, revision, source_default=source_default)
    value.update(dict.fromkeys(LINEAGE_CLAIM_FIELDS))
    return value


def restatement_differences(
    stated: CasillaDefinition,
    revision: ModeloRevision,
    inherited: CasillaDefinition,
    predecessor: ModeloRevision,
) -> tuple[str, ...]:
    """Return the fields in which a stated row differs from inheriting ``inherited``; empty means restated."""
    own_default, predecessor_default = _source_default(revision), _source_default(predecessor)
    compare_sources = own_default is not None and predecessor_default is not None
    left = stated_value(stated, revision, source_default=own_default if compare_sources else None)
    right = inheritable_value(inherited, predecessor, source_default=predecessor_default if compare_sources else None)
    return tuple(sorted(name for name in set(left) | set(right) if left.get(name) != right.get(name)))


def stated_casillas(revision: ModeloRevision) -> tuple[CasillaDefinition, ...]:
    """Return the casilla rows the edition states itself, in order: every row the loader did not mark inherited."""
    return tuple(casilla for casilla in revision.casillas if casilla.inherited_from is None)


def judge_definition(definition: ModeloDefinition, *, modelo_id: str) -> tuple[RowJudgement, ...]:
    """Return a verdict for every stated casilla row of every non-root edition; inherited rows get none.

    Takes the definition rather than the authority, as the sibling screens do,
    so a test can hand it a copy of a real definition carrying a constructed
    edition and assert the verdict the screen would reach.
    """
    judgements: list[RowJudgement] = []
    for edition in edition_predecessors(definition):
        if edition.predecessor is None:
            continue
        revision = definition.revisions[edition.revision]

        def judged(
            casilla: CasillaDefinition,
            kind: MinimalityVerdict,
            detail: str,
            edition: EditionPredecessor = edition,
        ) -> None:
            judgements.append(
                RowJudgement(modelo_id, edition.revision, edition.predecessor, str(casilla.id), kind, detail)
            )

        stated = stated_casillas(revision)
        if edition.basis == PredecessorBasis.UNDECIDABLE:
            for casilla in stated:
                judged(
                    casilla,
                    MinimalityVerdict.UNCHECKED_PREDECESSOR_UNDECIDABLE,
                    f"no declared predecessor and adjacent edition {edition.predecessor} overlaps in period",
                )
            continue
        predecessor = definition.revisions[edition.predecessor]
        by_chain: dict[str, list[CasillaDefinition]] = collections.defaultdict(list)
        for candidate in predecessor.casillas:
            if candidate.continuidad_id:
                by_chain[str(candidate.continuidad_id)].append(candidate)
        for casilla in stated:
            chain = str(casilla.continuidad_id) if casilla.continuidad_id else None
            if chain is None:
                judged(casilla, MinimalityVerdict.UNCHECKED_NO_LINEAGE, "row carries no continuidad_id")
                continue
            inherited = by_chain.get(chain, [])
            if not inherited:
                judged(casilla, MinimalityVerdict.NEW_IN_EDITION, f"chain {chain} absent from {edition.predecessor}")
            elif len(inherited) > 1:
                judged(
                    casilla,
                    MinimalityVerdict.UNCHECKED_AMBIGUOUS_LINEAGE,
                    f"chain {chain} sits on {len(inherited)} rows of {edition.predecessor}",
                )
            else:
                differing = restatement_differences(casilla, revision, inherited[0], predecessor)
                if differing:
                    judged(casilla, MinimalityVerdict.STATED_DIFFERENCE, f"differs in {', '.join(differing)}")
                else:
                    judged(
                        casilla,
                        MinimalityVerdict.RESTATED_UNCHANGED,
                        f"identical to {inherited[0].id} of {edition.predecessor} on chain {chain}",
                    )
    return tuple(judgements)


def definition_findings(definition: ModeloDefinition, *, modelo_id: str) -> tuple[RowJudgement, ...]:
    """Return one modelo definition's findings: restated rows and unjudged rows."""
    return tuple(item for item in judge_definition(definition, modelo_id=modelo_id) if item.kind in KINDS)


def screen_authority(authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]) -> tuple[RowJudgement, ...]:
    """Screen every modelo's successor editions through the validated authority."""
    findings: list[RowJudgement] = []
    for modelo_id in modelo_ids:
        findings.extend(definition_findings(authority.modelo(modelo_id), modelo_id=modelo_id))
    return tuple(findings)


def restating_modelos(findings: tuple[RowJudgement, ...]) -> tuple[str, ...]:
    """Return the modelos with at least one row restating its inherited row unchanged."""
    return tuple(sorted({item.modelo for item in findings if item.kind == MinimalityVerdict.RESTATED_UNCHANGED}))


def minimality_census(authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]) -> MinimalityCensus:
    """Return corpus-wide edition and row counts, every verdict counted apart."""
    editions = roots = declared = root_rows = inherited_rows = 0
    verdicts: collections.Counter[MinimalityVerdict] = collections.Counter()
    for modelo_id in modelo_ids:
        definition = authority.modelo(modelo_id)
        for edition in edition_predecessors(definition):
            editions += 1
            revision = definition.revisions[edition.revision]
            inherited_rows += len(revision.casillas) - len(stated_casillas(revision))
            if edition.basis == PredecessorBasis.DECLARED:
                declared += 1
            if edition.predecessor is None:
                roots += 1
                root_rows += len(revision.casillas)
        verdicts.update(item.kind for item in judge_definition(definition, modelo_id=modelo_id))
    return MinimalityCensus(
        editions=editions,
        root_editions=roots,
        declared_predecessor_editions=declared,
        rows_judged=sum(verdicts.values()),
        rows_inherited=inherited_rows,
        rows_in_root_editions=root_rows,
        verdicts=dict(sorted(verdicts.items())),
    )


def main() -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    authority = compiled_bundled_authority()
    modelo_ids = bundled_modelo_ids()
    findings = screen_authority(authority, modelo_ids)
    census = minimality_census(authority, modelo_ids)
    for item in findings:
        sys.stdout.write(
            f"minimality modelo={item.modelo} revision={item.revision} predecessor={item.predecessor} "
            f"casilla={item.casilla} kind={item.kind} detail={item.detail!r}\n"
        )
    verdicts = " ".join(f"{kind}={count}" for kind, count in census.verdicts.items())
    sys.stdout.write(
        f"summary findings={len(findings)} editions={census.editions} root_editions={census.root_editions} "
        f"declared_predecessor_editions={census.declared_predecessor_editions} rows_judged={census.rows_judged} "
        f"rows_inherited={census.rows_inherited} "
        f"rows_in_root_editions={census.rows_in_root_editions} restating_modelos={len(restating_modelos(findings))} "
        f"{verdicts}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
