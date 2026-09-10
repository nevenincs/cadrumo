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

What "identical" compares. Two rows are compared as loaded ``CasillaDefinition``
values, never as authored text, after removing the tokens whose only content is
the edition the row sits in:

- ``source_refs`` are dropped, top level and inside ``constraints``: source
  references are declared per edition and an inheriting row takes the
  successor's, so they differ between editions by construction.
- ``export_refs`` are dropped: the slot identifier carries the edition and its
  ordinal moves on insertion, so the field is derived per edition rather than
  inherited.
- ``continuidad_origin`` and ``continuidad_evidence`` are dropped: they state the
  row's relationship to its predecessor, which differs between a row and the row
  it continues by construction. ``continuidad_id`` is the match key and is equal.
- ``legal_refs`` are compared as a set after removing the edition's own
  ``orden_aplicabilidad`` entries, top level and inside ``constraints``: an orden
  reissued with the edition re-cites the same content, and array order is not
  meaningful to any consumer.
- ``formula``, ``binding`` and ``alternate_bindings`` are compared with the
  edition's own revision identifier replaced by a placeholder wherever it sits as
  a hyphen-bounded segment, because those identifiers embed the edition key.

Every other field is compared exactly, including ``id``, ``number``,
``section``, ``semantic_role``, ``data_type`` and ``input_kind``, where the
corpus's genuine differences sit. A field the schema gains later is compared by
default, which errs toward reporting a difference: a new edition-local field
would hide restatement rather than invent it.

Where it stops:

- Casilla rows only. The completeness manifest does not inherit - a migrated
  edition restates its whole manifest by design - so it is never read here, and
  neither are formulas, bindings, layouts or any other family.
- The stated rows are read as ``revision.casillas``. That holds while the loader
  materialises no inheritance; a loader that does would present inherited rows
  as stated ones, and this screen would then need a statement-origin marker it
  does not have today.
- An edition declaring no predecessor is measured against the adjacent earlier
  edition by validity order - the pairing a declared predecessor must agree with
  wherever the two editions do not overlap. A declared predecessor is always
  used as declared.
- Labels are not compared. Locale keys are edition-scoped and label text
  inherits through the locale catalogue, not through the row.
- A formula or binding reference is compared by normalised identifier, not by
  resolving it to the successor edition's declaration of the same lineage.

The screen exits 0 whatever it finds. It reports; it does not gate.
"""

from __future__ import annotations

import collections
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions, revisions_overlap
from cadrumo.domain.calculations.registry.schema import (
    DeclaredPredecessor,
    ModeloDefinition,
    ModeloRevision,
    NoPredecessor,
)
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .corpus import bundled_modelo_ids

__all__ = [
    "EDITION_LOCAL_FIELDS",
    "KINDS",
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
    "restating_modelos",
    "screen_authority",
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

#: Casilla fields removed before comparison because they carry the edition, or
#: the row's relationship to its predecessor, rather than the row's meaning.
EDITION_LOCAL_FIELDS: Final[frozenset[str]] = frozenset(
    {"source_refs", "export_refs", "continuidad_origin", "continuidad_evidence"}
)


class PredecessorBasis(StrEnum):
    """How an edition's predecessor was established."""

    DECLARED = "declared"
    ROOT_DECLARED = "declared_none"
    ROOT_FIRST_IN_ORDER = "first_in_order"
    ADJACENT = "adjacent_in_order"
    UNDECIDABLE = "undecidable"


_EDITION_PLACEHOLDER: Final = "<edition>"
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


def _without_edition(identifier: str, revision_id: str) -> str:
    pattern = rf"(?<![^-]){re.escape(revision_id)}(?![^-])"
    return re.sub(pattern, _EDITION_PLACEHOLDER, identifier)


def _legal_refs(values: object, own_ordenes: frozenset[str]) -> frozenset[str]:
    if not isinstance(values, tuple | list):
        return frozenset[str]()
    return frozenset(str(value) for value in values) - own_ordenes


def inheritable_value(casilla: CasillaDefinition, revision: ModeloRevision) -> dict[str, object]:
    """Return the part of a casilla row an inheriting edition would carry unchanged.

    The row's typed dump with every token repeating its own edition removed, as
    the module docstring lists. Two rows are identical for this screen exactly
    when these values are equal.
    """
    revision_id = str(revision.id)
    own_ordenes = frozenset(str(ref) for ref in revision.orden_aplicabilidad)
    value: dict[str, object] = dict(casilla.model_dump(mode="python", exclude=set(EDITION_LOCAL_FIELDS)))
    value["legal_refs"] = _legal_refs(value.get("legal_refs"), own_ordenes)
    constraints = value.get("constraints")
    if isinstance(constraints, dict):
        constraints.pop("source_refs", None)
        constraints["legal_refs"] = _legal_refs(constraints.get("legal_refs"), own_ordenes)
    for name in _IDENTIFIER_FIELDS:
        current = value.get(name)
        if isinstance(current, str):
            value[name] = _without_edition(current, revision_id)
        elif isinstance(current, tuple):
            value[name] = tuple(_without_edition(str(item), revision_id) for item in current)
    return value


def _differing_fields(left: Mapping[str, object], right: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(sorted(name for name in set(left) | set(right) if left.get(name) != right.get(name)))


def judge_definition(definition: ModeloDefinition, *, modelo_id: str) -> tuple[RowJudgement, ...]:
    """Return a verdict for every stated casilla row of every non-root edition.

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

        if edition.basis == PredecessorBasis.UNDECIDABLE:
            for casilla in revision.casillas:
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
        for casilla in revision.casillas:
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
                differing = _differing_fields(
                    inheritable_value(casilla, revision), inheritable_value(inherited[0], predecessor)
                )
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
    editions = roots = declared = root_rows = 0
    verdicts: collections.Counter[MinimalityVerdict] = collections.Counter()
    for modelo_id in modelo_ids:
        definition = authority.modelo(modelo_id)
        for edition in edition_predecessors(definition):
            editions += 1
            if edition.basis == PredecessorBasis.DECLARED:
                declared += 1
            if edition.predecessor is None:
                roots += 1
                root_rows += len(definition.revisions[edition.revision].casillas)
        verdicts.update(item.kind for item in judge_definition(definition, modelo_id=modelo_id))
    return MinimalityCensus(
        editions=editions,
        root_editions=roots,
        declared_predecessor_editions=declared,
        rows_judged=sum(verdicts.values()),
        rows_in_root_editions=root_rows,
        verdicts=dict(sorted(verdicts.items())),
    )


def main() -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    authority = bundled_authority()
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
        f"rows_in_root_editions={census.rows_in_root_editions} restating_modelos={len(restating_modelos(findings))} "
        f"{verdicts}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
