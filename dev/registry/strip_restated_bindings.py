"""Remove a successor edition's binding members that restate what it would inherit.

The union rule says a successor edition states only the members that are new in
it or that differ from the member it would inherit. Bindings participate in the
canonical keyed-family merge by their edition-free ``id``. This tool proves a
prospective strip exact before anything is written.

What "restated" means here, and why it is stricter than the census signal.
The edition-delta status screen counts a member restated when its table equals
the predecessor's table with ``source_refs`` and ``legal_refs`` set aside. That
is the right question for a census -- it measures how much of the corpus the
union could eventually absorb -- but it is not a licence to delete a row,
because a deleted row must materialise back identically, and references are
part of what materialises. Two equalities are therefore computed and reported
apart:

- ``materialised`` (the default, and the only one ``--apply`` will act on). A
  member may be deleted when the member the merge would put in its place -- the
  predecessor's RAW member, carried forward by the keyed merge and then filled
  from THIS edition's ``binding_source_refs`` default -- equals the member as
  authored, filled from the same default. This is byte-identity by construction:
  the compared values are exactly what the loader hands to typed construction.
- ``lifted``. The same comparison after each side's ``source_refs`` are lifted
  against its own edition's declared ``binding_source_refs``. This is the
  census signal's population. A member counted here and not above is blocked on
  one thing only: its PREDECESSOR still states per-edition ``source_refs`` on
  the member inline instead of lifting them to the manifest default. Once the
  predecessor is lifted, the inherited raw member carries no ``source_refs``,
  the successor's own default fills it, and the member becomes deletable under
  the strict equality without anything else changing.

Reference defaults are applied to the MATERIALISED edition, after inheritance,
so an inherited member is grounded by the edition it now sits in rather than by
the edition that stated it. That ordering is what makes the lift the whole
precondition, and it is the loader's, not this tool's.

Refusals. A successor whose manifest declares an explicit no-predecessor root
(``[revisions.<id>.predecessor.none]``) inherits nothing and is refused, as is
one naming a predecessor the modelo does not carry, one declaring bindings
outside its ``bindings/`` directory (this tool rewrites those fragments and
nothing else), and one carrying two binding members under one id. A member
differing in any field is kept, with the differing keys named.

Carried grounding. Byte-identical payload is not identical meaning. A member
whose payload matches may still be kept, because what it would INHERIT carries
``source_refs`` the successor's own grounding does not supply: the predecessor
states its design ref inline, the successor declares a different default, and a
strip would move the row onto the predecessor's grounding in an edition whose
constructs and dependency classifications do not cite it. A member is therefore
strippable only when the refs it materialises after inheritance are what the
successor's own ``binding_source_refs`` default supplies -- no refs of its own,
exactly that default, or a tail every successor declaration claiming the member
already grounds. Otherwise it is kept and reported under ``carried_grounding``
with its id, the refs it would inherit, and the successor default they failed
against. The rule is decided in the plan, never at write time.

Proof. The proof runs against the loader's supported keyed-merge boundary with
the canonical ``bindings`` family policy. It compares the typed
``BindingDefinition`` set before and after the prospective strip, so a dropped
member must materialise byte-identically under the enrolled family.

Scoping. ``--all`` and ``--modelo`` sweep whole modelos. ``--edge
<modelo>/<successor-edition>`` and ``--edges-file`` name individual
predecessor->successor edges instead, which is what an enrolment landing on a
named set of edges needs: the strip must run on exactly the edges whose bindings
now inherit and on no others. A named edge whose successor is not declared,
declares an explicit no-predecessor root, or states no binding members is
refused before anything is planned, and every named edge appears in the report.

Writes nothing without ``--apply``. Materialised equality is the only equality
that ``--apply`` accepts; ``lifted`` remains a census/advisory comparison.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from cadrumo.domain.calculations.registry.errors import RegistryError, RegistryLoadError
from cadrumo.domain.calculations.registry.keyed_families import FamilyInheritanceMode, family_spec
from cadrumo.domain.calculations.registry.reference_sections import FAMILY_SOURCE_DEFAULT_FIELDS
from cadrumo.domain.calculations.registry.schema import BindingDefinition

# `inherit_keyed_family` is the loader's supported keyed merge boundary.
from .compiler.loader import inherit_keyed_family, modelo_fact_scope
from .corpus_write import verify_written, write_preserving_newlines
from .run_exclusions import (
    DEFAULT_EXCLUSION_REASON,
    ExclusionSet,
    collect_exclusions,
)

__all__ = [
    "CarriedGrounding",
    "EditionOutcome",
    "Equality",
    "ModeloOutcome",
    "StripReport",
    "main",
    "parse_edge",
    "parse_edges_file",
    "plan_modelo",
    "render_report",
    "strip_registry",
]

_MODELOS: Final = "modelos"
_REVISIONS: Final = "revisions"
_MANIFEST: Final = "revision.toml"
_BINDINGS: Final = "bindings"
_SOURCE_REFS: Final = "source_refs"
_SOURCE_ADDITIONS: Final = "additional_source_refs"
_PREDECESSOR: Final = "predecessor"
#: Set aside by the census signal's equality, which measures how much the union
#: could eventually absorb rather than what is deletable today.
_REFERENCE_KEYS: Final = frozenset({"source_refs", "legal_refs", "additional_source_refs"})
_SOURCE_DEFAULT_FIELDS: Final = dict(FAMILY_SOURCE_DEFAULT_FIELDS)
_BINDING_DEFAULT_FIELD: Final = _SOURCE_DEFAULT_FIELDS[_BINDINGS]

#: The successor declarations that claim a binding member and must therefore
#: carry its grounding: a construct lists its members under ``bindings``, a
#: dependency classification under ``binding_refs``.
_CONSTRUCTS: Final = "constructs"
_CLASSIFICATIONS: Final = "dependency_classifications"
_CLAIMANT_FAMILIES: Final = ((_CONSTRUCTS, "bindings"), (_CLASSIFICATIONS, "binding_refs"))


def _family_policy(family: str):
    """Return the canonical enrolled policy for one keyed family or refuse the strip."""
    policy = family_spec(family)
    if policy is None or policy.inheritance is not FamilyInheritanceMode.KEYED:
        raise RegistryLoadError(f"{family} are not enrolled in the canonical keyed-family merge")
    return policy


def _binding_family_policy():
    """Return the canonical enrolled binding policy or refuse the strip."""
    return _family_policy(_BINDINGS)


_REVISION_SEGMENT: Final = r'(?:"[^"\n]+"|[^".\]\n]+)'
_MEMBER_HEADER: Final = re.compile(rf"^\[\[revisions\.{_REVISION_SEGMENT}\.bindings\]\]\s*$")

#: The two equalities this tool can be asked for. ``materialised`` is provable
#: today; ``lifted`` is the census population and waits on the predecessor lift.
type Equality = str
MATERIALISED: Final[Equality] = "materialised"
LIFTED: Final[Equality] = "lifted"


# ── edge selection ──────────────────────────────────────────────────────────


def parse_edge(text: str) -> tuple[str, str]:
    """Parse one ``<modelo>/<successor-edition>`` edge.

    The successor names the edge because the predecessor is the successor's own
    declaration: naming it again would let an operator assert a chain the
    registry does not carry.
    """
    modelo, separator, edition = text.strip().partition("/")
    if not separator or not modelo.strip() or not edition.strip():
        raise RegistryError(f"malformed edge {text!r}: expected '<modelo>/<successor-edition>'")
    return modelo.strip(), edition.strip()


def parse_edges_file(path: Path) -> tuple[tuple[str, str], ...]:
    """Parse an edges file: one ``<modelo>/<edition>`` per line, ``#`` comments and blank lines ignored.

    Duplicates collapse in first-seen order, so a list assembled from several
    sources plans each edge once.
    """
    edges: dict[tuple[str, str], None] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.partition("#")[0].strip()
        if not line:
            continue
        try:
            edges[parse_edge(line)] = None
        except RegistryError as exc:
            raise RegistryError(f"{path}:{number}: {exc}") from exc
    if not edges:
        raise RegistryError(f"{path}: names no edge")
    return tuple(edges)


# ── raw tree reading ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _Block:
    """One binding member as authored: its text, including the comment run above its header."""

    text: str
    member: dict[str, Any]

    @property
    def identity(self) -> str:
        value = self.member.get("id")
        return value if isinstance(value, str) else ""


@dataclass(frozen=True, slots=True)
class _Fragment:
    path: Path
    preamble: str
    blocks: tuple[_Block, ...]


def _split_blocks(text: str) -> tuple[str, list[str]]:
    """Split a fragment into its preamble and one text block per binding header.

    A comment run directly above a header belongs to the member below it, so a
    deleted member takes its own commentary with it and leaves its neighbour's
    intact.
    """
    lines = text.splitlines(keepends=True)
    starts: list[int] = []
    for index, line in enumerate(lines):
        if _MEMBER_HEADER.match(line.rstrip("\r\n")):
            start = index
            while start > 0 and lines[start - 1].lstrip().startswith("#") and (not starts or start - 1 > starts[-1]):
                start -= 1
            starts.append(start)
    if not starts:
        return text, []
    bounds = [*starts, len(lines)]
    blocks = ["".join(lines[bounds[index] : bounds[index + 1]]) for index in range(len(starts))]
    return "".join(lines[: starts[0]]), blocks


def _block_member(block: str) -> dict[str, Any]:
    revisions = tomllib.loads(block).get(_REVISIONS)
    if not isinstance(revisions, dict) or len(revisions) != 1:
        raise RegistryError(f"binding block does not declare exactly one revision:\n{block}")
    (revision,) = revisions.values()
    members = revision.get(_BINDINGS) if isinstance(revision, dict) else None
    if not isinstance(members, list) or len(members) != 1:
        raise RegistryError(f"binding block does not declare exactly one member:\n{block}")
    member = members[0]
    if not isinstance(member, dict):
        raise RegistryError(f"binding block does not declare a table:\n{block}")
    return dict(member)


def _read_fragments(edition_dir: Path) -> tuple[_Fragment, ...]:
    fragments: list[_Fragment] = []
    for path in sorted((edition_dir / _BINDINGS).glob("*.toml")):
        preamble, texts = _split_blocks(path.read_text(encoding="utf-8"))
        fragments.append(_Fragment(path, preamble, tuple(_Block(text, _block_member(text)) for text in texts)))
    return tuple(fragments)


def _merged_revision_table(edition_dir: Path, revision_id: str) -> dict[str, Any]:
    """Merge every fragment below the edition into one raw revision table, as the loader does."""
    merged: dict[str, Any] = {}
    for path in sorted(edition_dir.rglob("*.toml")):
        table = tomllib.loads(path.read_text(encoding="utf-8")).get(_REVISIONS, {}).get(revision_id)
        if not isinstance(table, dict):
            continue
        for key, value in table.items():
            # Arrays are frozen to tuples because the loader's own helpers narrow
            # a TOML array by that type: a list reaches the merge as "not an
            # array" and the merge refuses it.
            if isinstance(value, list):
                existing = merged.get(key)
                merged[key] = (*existing, *value) if isinstance(existing, tuple) else tuple(value)
            else:
                merged.setdefault(key, value)
    return merged


def _declared_predecessor(table: Mapping[str, Any]) -> str | None:
    value = table.get(_PREDECESSOR)
    return value if isinstance(value, str) else None


def _declares_none_root(table: Mapping[str, Any]) -> bool:
    return isinstance(table.get(_PREDECESSOR), dict)


# ── the loader's semantics, for a delta that is not written yet ─────────────


def _binding_default(table: Mapping[str, Any]) -> tuple[str, ...]:
    value = table.get(_BINDING_DEFAULT_FIELD)
    return tuple(str(item) for item in value) if isinstance(value, list | tuple) else ()


def _defaulted(member: Mapping[str, Any], default: Sequence[str]) -> dict[str, Any]:
    """Fill a binding member's ``source_refs`` from the edition default, as the loader does.

    A stated value is kept whole and a default is never merged into one; only
    ``additional_source_refs`` extends the default, duplicates removed and the
    default first, and the additions key is consumed.
    """
    filled = dict(member)
    additions = filled.pop(_SOURCE_ADDITIONS, None)
    if additions is not None:
        if _SOURCE_REFS in filled or not isinstance(additions, list) or not additions or not default:
            raise RegistryError(f"binding {member.get('id')!r} states additions the loader would refuse")
        filled[_SOURCE_REFS] = list(dict.fromkeys((*default, *(str(item) for item in additions))))
    elif default and _SOURCE_REFS not in filled:
        filled[_SOURCE_REFS] = list(default)
    return filled


def _lifted(member: Mapping[str, Any], default: Sequence[str]) -> dict[str, Any]:
    """The member with a ``source_refs`` that restates its own edition's default removed.

    A value that opens with the default keeps only its tail, as additions; a
    value the default cannot reproduce is irreducible and is kept whole. This is
    the normalisation the ``lifted`` equality compares under, and it is exactly
    what a predecessor lift would leave behind.
    """
    refs = member.get(_SOURCE_REFS)
    if not default or not isinstance(refs, list):
        return dict(member)
    stated = tuple(str(item) for item in refs)
    if tuple(default) != stated[: len(default)]:
        return dict(member)
    rest = stated[len(default) :]
    if tuple(dict.fromkeys((*default, *rest))) != stated:
        return dict(member)
    lifted = {key: value for key, value in member.items() if key != _SOURCE_REFS}
    if rest:
        lifted[_SOURCE_ADDITIONS] = list(rest)
    return lifted


def _keyed_members(table: Mapping[str, Any], family: str = _BINDINGS) -> tuple[object, ...]:
    members = table.get(family, ())
    return tuple(members) if isinstance(members, list | tuple) else ()


def _materialised_bindings(
    modelo_id: str,
    revision_id: str,
    tables: Mapping[str, Mapping[str, Any]],
    seen: frozenset[str] = frozenset(),
) -> tuple[object, ...]:
    """The raw binding members an edition holds once its declared chain is merged."""
    return _materialised_family(modelo_id, revision_id, tables, _BINDINGS, seen)


def _materialised_family(
    modelo_id: str,
    revision_id: str,
    tables: Mapping[str, Mapping[str, Any]],
    family: str,
    seen: frozenset[str] = frozenset(),
) -> tuple[object, ...]:
    """The raw members of one keyed family an edition holds once its declared chain is merged.

    The merge is the loader's :func:`inherit_keyed_family` boundary, configured
    from the canonical policy of the named family. Defaults are NOT applied
    here: the loader applies them to the materialised edition, and applying them
    earlier is precisely the mistake that would make an inherited member carry
    its origin edition's grounding.
    """
    table = tables.get(revision_id)
    if table is None:
        raise RegistryError(f"modelo {modelo_id}: revision {revision_id!r} is not declared")
    predecessor_id = _declared_predecessor(table)
    if predecessor_id is None:
        return _keyed_members(table, family)
    if predecessor_id in seen:
        raise RegistryError(f"modelo {modelo_id}: revision {revision_id!r} loops through {predecessor_id!r}")
    inherited = _materialised_family(modelo_id, predecessor_id, tables, family, seen | {revision_id})
    policy = _family_policy(family)
    return inherit_keyed_family(
        f"{modelo_id}: revision {revision_id!r} inheriting from {predecessor_id!r}",
        revision_id=revision_id,
        section=policy.section,
        identity=policy.identity or "id",
        identity_fields=policy.identity_fields,
        period_scoped=policy.period_scoped,
        inherited=inherited,
        successor=table,
    )


def _frozen(value: object) -> object:
    """Freeze parsed TOML arrays into tuples, which is the shape typed construction accepts."""
    if isinstance(value, Mapping):
        return {str(key): _frozen(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return tuple(_frozen(item) for item in value)
    return value


def _typed(members: Iterable[object], default: Sequence[str]) -> dict[str, Any]:
    """Every member's typed ``BindingDefinition`` dump, keyed by id.

    The proof compares typed meaning rather than raw tables: two tables that
    differ only in key order or in a value the model normalises mean the same
    thing to every consumer, and a proof that reported them different would
    refuse a strip that changes nothing.
    """
    dumped: dict[str, Any] = {}
    for member in members:
        if not isinstance(member, dict):
            raise RegistryError(f"binding member is not a table: {member!r}")
        filled = _defaulted(member, default)
        definition = BindingDefinition.model_validate(_frozen(filled))
        dumped[str(filled["id"])] = definition.model_dump(mode="json")
    return dumped


# ── planning ────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class EditionOutcome:
    """One successor edition's strip: what it would remove, keep, and why."""

    modelo: str
    edition: str
    predecessor: str | None = None
    refusal: str = ""
    stated: int = 0
    removed: tuple[str, ...] = ()
    kept_new: int = 0
    kept_differs: tuple[tuple[str, tuple[str, ...]], ...] = ()
    #: Members equal under the run's equality but kept because the grounding
    #: they would inherit is not what this edition's own default supplies.
    carried_grounding: tuple[CarriedGrounding, ...] = ()
    successor_default: tuple[str, ...] = ()
    restated_after_lifting: tuple[str, ...] = ()
    restated_ignoring_refs: tuple[str, ...] = ()
    blocking_fields: tuple[tuple[str, int], ...] = ()
    fragments_rewritten: tuple[str, ...] = ()
    fragments_deleted: tuple[str, ...] = ()
    comment_only_removed: tuple[tuple[str, str], ...] = ()
    directories_removed: tuple[str, ...] = ()
    proof: str = "not run"

    def as_json(self) -> dict[str, Any]:
        """Return the outcome as report JSON."""
        return {
            "edition": self.edition,
            "predecessor": self.predecessor,
            "refusal": self.refusal,
            "stated": self.stated,
            "removed": list(self.removed),
            "removed_count": len(self.removed),
            "kept_new": self.kept_new,
            "kept_differs_count": len(self.kept_differs),
            "kept_differs": [{"id": identity, "fields": list(fields)} for identity, fields in self.kept_differs[:20]],
            "successor_default": list(self.successor_default),
            "carried_grounding_count": len(self.carried_grounding),
            "carried_grounding": [kept.as_json(self.successor_default) for kept in self.carried_grounding],
            "restated_after_lifting_count": len(self.restated_after_lifting),
            "restated_ignoring_refs_count": len(self.restated_ignoring_refs),
            "blocking_fields": dict(self.blocking_fields),
            "fragments_rewritten": list(self.fragments_rewritten),
            "fragments_deleted": list(self.fragments_deleted),
            "comment_only_removed": [{"fragment": name, "text": text} for name, text in self.comment_only_removed],
            "directories_removed": list(self.directories_removed),
            "proof": self.proof,
        }


@dataclass(slots=True)
class ModeloOutcome:
    """Every successor edition of one modelo."""

    modelo: str
    editions: list[EditionOutcome] = field(default_factory=list)

    @property
    def removed(self) -> int:
        """The number of members this modelo would stop stating."""
        return sum(len(edition.removed) for edition in self.editions)

    @property
    def kept_differs(self) -> int:
        """The number of stated members kept because they differ from the inherited member."""
        return sum(len(edition.kept_differs) for edition in self.editions)

    @property
    def carried_grounding(self) -> int:
        """The number of restated members kept because their inherited grounding is not this edition's."""
        return sum(len(edition.carried_grounding) for edition in self.editions)

    @property
    def restated_after_lifting(self) -> int:
        """The census population: members restated once each side's references are lifted."""
        return sum(len(edition.restated_after_lifting) for edition in self.editions)

    @property
    def restated_ignoring_refs(self) -> int:
        """The census signal's population: members equal once every reference field is set aside."""
        return sum(len(edition.restated_ignoring_refs) for edition in self.editions)

    @property
    def refusals(self) -> int:
        """The number of editions refused."""
        return sum(1 for edition in self.editions if edition.refusal)


@dataclass(slots=True)
class StripReport:
    """The whole run: every modelo's outcome and the proof's standing."""

    equality: Equality
    applied: bool
    enrolment: str
    modelos: list[ModeloOutcome] = field(default_factory=list)
    #: The ``(modelo, successor-edition)`` pairs the run was restricted to, empty for a modelo sweep.
    edges: tuple[tuple[str, str], ...] = ()
    #: The modelos and editions withheld from the run, each with its reason. An
    #: excluded target is never examined, so it plans nothing and refuses nothing;
    #: it is reported so the run states what it declined to look at.
    exclusions: ExclusionSet = field(default_factory=lambda: ExclusionSet(exclusions=()))

    def as_json(self) -> dict[str, Any]:
        """Return the run as report JSON."""
        return {
            "equality": self.equality,
            "applied": self.applied,
            "enrolment": self.enrolment,
            "edges": [f"{modelo}/{edition}" for modelo, edition in self.edges],
            "exclusions": self.exclusions.as_json(),
            "proof_note": (
                "bindings are enrolled in the loader's _KEYED_FAMILIES; the byte-identity proof ran against the "
                "loader's supported keyed-merge boundary with the canonical bindings family policy"
            ),
            "totals": {
                "removed": sum(modelo.removed for modelo in self.modelos),
                "kept_differs": sum(modelo.kept_differs for modelo in self.modelos),
                "carried_grounding": sum(modelo.carried_grounding for modelo in self.modelos),
                "restated_after_lifting": sum(modelo.restated_after_lifting for modelo in self.modelos),
                "restated_ignoring_refs": sum(modelo.restated_ignoring_refs for modelo in self.modelos),
                "refusals": sum(modelo.refusals for modelo in self.modelos),
            },
            "modelos": [
                {
                    "modelo": modelo.modelo,
                    "removed": modelo.removed,
                    "kept_differs": modelo.kept_differs,
                    "carried_grounding": modelo.carried_grounding,
                    "restated_after_lifting": modelo.restated_after_lifting,
                    "restated_ignoring_refs": modelo.restated_ignoring_refs,
                    "refusals": modelo.refusals,
                    "editions": [edition.as_json() for edition in modelo.editions],
                }
                for modelo in self.modelos
            ],
        }


def _without_references(member: Mapping[str, Any]) -> dict[str, Any]:
    """The member with every reference field set aside, which is the census signal's comparison.

    Reported alongside the provable equalities and never acted on: a member equal
    only here still materialises different references, and deleting it would
    change what the edition cites.
    """
    return {key: value for key, value in member.items() if key not in _REFERENCE_KEYS}


def _differing_fields(left: Mapping[str, Any], right: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(key for key in set(left) | set(right) if left.get(key) != right.get(key)))


# ── carried grounding ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CarriedGrounding:
    """A member kept because the grounding it would inherit is not the successor's own.

    ``inherited_refs`` is what the member materialises once the successor stops
    stating it -- the inherited raw member filled from the successor's own
    ``binding_source_refs`` default. ``uncovered_refs`` are the refs in it that
    neither that default supplies nor a successor declaration claiming the
    member grounds, named by ``owners``.
    """

    identity: str
    inherited_refs: tuple[str, ...]
    uncovered_refs: tuple[str, ...]
    owners: tuple[str, ...]

    def as_json(self, default: Sequence[str]) -> dict[str, Any]:
        """Return the kept member as report JSON, beside the successor default it failed against."""
        return {
            "id": self.identity,
            "inherited_source_refs": list(self.inherited_refs),
            "uncovered_source_refs": list(self.uncovered_refs),
            "successor_default": list(default),
            "claimed_by": list(self.owners),
        }


def _family_source_default(table: Mapping[str, Any], family: str) -> tuple[str, ...]:
    value = table.get(_SOURCE_DEFAULT_FIELDS[family])
    return tuple(str(item) for item in value) if isinstance(value, list | tuple) else ()


def _stated_refs(member: Mapping[str, Any], default: Sequence[str]) -> frozenset[str]:
    refs = member.get(_SOURCE_REFS)
    if isinstance(refs, list | tuple):
        return frozenset(str(item) for item in refs)
    return frozenset(default)


def _grounding_cover(
    modelo_id: str,
    revision_id: str,
    tables: Mapping[str, Mapping[str, Any]],
) -> dict[str, tuple[tuple[str, frozenset[str]], ...]]:
    """The refs each successor declaration claiming a binding member can ground it with.

    Construct closure requires the claiming declaration's ``source_refs`` to
    include every ref its member carries, so a ref no claimant states is a ref
    the member cannot legally materialise in this edition. Both claimant
    families are materialised through the same keyed merge as the bindings and
    filled from THIS edition's own family default, which is what the loader
    hands the validator.
    """
    cover: dict[str, list[tuple[str, frozenset[str]]]] = {}
    table = tables[revision_id]
    for family, field_name in _CLAIMANT_FAMILIES:
        default = _family_source_default(table, family)
        for member in _materialised_family(modelo_id, revision_id, tables, family):
            if not isinstance(member, dict):
                continue
            claimed = member.get(field_name, ())
            if not isinstance(claimed, list | tuple):
                continue
            owner = f"{family}:{member.get('id')}"
            grounds = _stated_refs(member, default)
            for identity in claimed:
                cover.setdefault(str(identity), []).append((owner, grounds))
    return {identity: tuple(owners) for identity, owners in cover.items()}


def _carried_grounding(
    identity: str,
    inherited_materialised: Mapping[str, Any],
    default: Sequence[str],
    owners: Sequence[tuple[str, frozenset[str]]],
) -> CarriedGrounding | None:
    """Return why the member must be kept, or ``None`` when it is safe to stop stating it.

    Byte-identical payload is not identical meaning. A member is strippable only
    when the ``source_refs`` it materialises after inheritance are what the
    successor's OWN declared default would supply -- the inherited member states
    no refs of its own, or states exactly that default, or a tail every
    successor declaration claiming the member already grounds. Anything else is
    the predecessor's grounding carried into an edition that does not cite it,
    which is a construct-closure failure the tool must refuse rather than write.
    """
    materialised = inherited_materialised.get(_SOURCE_REFS, ())
    refs = tuple(str(item) for item in materialised) if isinstance(materialised, list | tuple) else ()
    beyond = tuple(ref for ref in dict.fromkeys(refs) if ref not in default)
    if not beyond:
        return None
    uncovered = tuple(ref for ref in beyond if not owners or any(ref not in grounds for _owner, grounds in owners))
    if not uncovered:
        return None
    return CarriedGrounding(identity, refs, uncovered, tuple(owner for owner, _grounds in owners))


def plan_modelo(
    modelo_dir: Path,
    *,
    equality: Equality = MATERIALISED,
    edition_ids: Sequence[str] = (),
    excluded_edition_ids: Sequence[str] = (),
) -> ModeloOutcome:
    """Decide, for every successor edition of one modelo, which binding members restate the inherited one.

    ``edition_ids``, when given, restricts the plan to those successor editions;
    every other edition of the modelo is left unexamined and unreported.

    ``excluded_edition_ids`` names editions to withhold. An excluded edition is
    left unexamined and unreported here even when ``edition_ids`` selects it:
    the exclusion is the later and narrower decision. It is still read when
    materialising another edition's inheritance chain, because an edge names the
    edition to strip, never the editions the merge must walk.

    Writes nothing.
    """
    modelo_id = modelo_dir.name
    outcome = ModeloOutcome(modelo=modelo_id)
    editions_root = modelo_dir / _REVISIONS
    if not editions_root.is_dir():
        return outcome
    edition_dirs = {path.name: path for path in sorted(editions_root.iterdir()) if path.is_dir()}
    # The chain a selected successor inherits along is read from the whole
    # modelo: an edge names the edition to strip, never the editions the merge
    # must walk to materialise it.
    tables = {name: _merged_revision_table(path, name) for name, path in edition_dirs.items()}
    if edition_ids:
        edition_dirs = {name: path for name, path in edition_dirs.items() if name in edition_ids}
    if excluded_edition_ids:
        edition_dirs = {name: path for name, path in edition_dirs.items() if name not in excluded_edition_ids}
    for edition_id, edition_dir in edition_dirs.items():
        table = tables[edition_id]
        if not _keyed_members(table):
            continue
        result = EditionOutcome(modelo=modelo_id, edition=edition_id)
        outcome.editions.append(result)
        if _declares_none_root(table):
            result.refusal = "predecessor_none_root: the edition inherits nothing and states itself in full"
            continue
        predecessor_id = _declared_predecessor(table)
        if predecessor_id is None:
            result.refusal = "no_predecessor_declared"
            continue
        result.predecessor = predecessor_id
        try:
            _plan_edition(modelo_id, edition_id, edition_dir, tables, result, equality=equality)
        except (RegistryError, RegistryLoadError) as exc:
            # A merge refusal is this edition's answer, not the run's: enrolling
            # bindings would refuse it too, and the operator needs to see which
            # editions those are rather than a stopped sweep.
            result.refusal = f"{type(exc).__name__}: {exc}"
    return outcome


def _plan_edition(
    modelo_id: str,
    edition_id: str,
    edition_dir: Path,
    tables: Mapping[str, Mapping[str, Any]],
    result: EditionOutcome,
    *,
    equality: Equality,
) -> None:
    table = tables[edition_id]
    predecessor_id = str(result.predecessor)
    fragments = _read_fragments(edition_dir)
    stated_blocks = [block for fragment in fragments for block in fragment.blocks]
    if len(stated_blocks) != len(_keyed_members(table)):
        raise RegistryError(
            "bindings_declared_outside_fragments: the edition declares binding members outside its bindings/ "
            "directory, which this tool does not rewrite"
        )
    identities = [block.identity for block in stated_blocks]
    duplicated = sorted({identity for identity in identities if identities.count(identity) > 1})
    if duplicated or "" in identities:
        raise RegistryError(f"ambiguous_identity: {duplicated or ['<member stating no id>']}")
    result.stated = len(stated_blocks)

    default = _binding_default(table)
    predecessor_default = _binding_default(tables.get(predecessor_id, {}))
    inherited_raw = _materialised_bindings(modelo_id, predecessor_id, tables)
    inherited = {
        str(member["id"]): dict(member) for member in inherited_raw if isinstance(member, dict) and "id" in member
    }

    result.successor_default = default
    cover = _grounding_cover(modelo_id, edition_id, tables)

    removable: list[str] = []
    carried: list[CarriedGrounding] = []
    restated_lifted: list[str] = []
    restated_ignoring_refs: list[str] = []
    blocking: Counter[str] = Counter()
    differs: list[tuple[str, tuple[str, ...]]] = []
    for block in stated_blocks:
        before = inherited.get(block.identity)
        if before is None:
            result.kept_new += 1
            continue
        strict_left = _defaulted(before, default)
        strict_right = _defaulted(block.member, default)
        lifted_left = _defaulted(_lifted(before, predecessor_default), default)
        lifted_right = _defaulted(_lifted(block.member, default), default)
        if _without_references(strict_left) == _without_references(strict_right):
            restated_ignoring_refs.append(block.identity)
        if lifted_left == lifted_right:
            restated_lifted.append(block.identity)
        if strict_left == strict_right or (equality == LIFTED and lifted_left == lifted_right):
            withheld = _carried_grounding(block.identity, strict_left, default, cover.get(block.identity, ()))
            if withheld is None:
                removable.append(block.identity)
            else:
                carried.append(withheld)
        else:
            fields = _differing_fields(lifted_left, lifted_right)
            blocking[", ".join(fields)] += 1
            differs.append((block.identity, fields))
    result.removed = tuple(removable)
    result.carried_grounding = tuple(carried)
    result.restated_after_lifting = tuple(restated_lifted)
    result.restated_ignoring_refs = tuple(restated_ignoring_refs)
    result.blocking_fields = tuple(sorted(blocking.items(), key=lambda item: (-item[1], item[0]))[:10])
    result.kept_differs = tuple(differs)


# ── writing and proof ───────────────────────────────────────────────────────


def _preview(edition_dir: Path, removed: frozenset[str], result: EditionOutcome) -> dict[Path, str | None]:
    """The text each fragment would hold after the strip, ``None`` meaning the file is deleted.

    A fragment keeping rows is rewritten from its surviving blocks, so every
    sibling row and every comment run that belongs to one survives byte-for-byte.
    A fragment left with no row is deleted, never written back blank or as the
    remnant of its own leading comment run: the loader requires every fragment
    to declare a ``[revisions.<id>]`` table, so a file holding only whitespace
    or commentary stops the edition loading. A leading comment run above the
    first member states nothing the loader reads, so a fragment reduced to one
    counts as having nothing left; its text is preserved in the report under
    ``comment_only_removed`` rather than on disk.
    """
    planned: dict[Path, str | None] = {}
    rewritten: list[str] = []
    deleted: list[str] = []
    comment_only: list[tuple[str, str]] = []
    for fragment in _read_fragments(edition_dir):
        kept = [block for block in fragment.blocks if block.identity not in removed]
        if len(kept) == len(fragment.blocks):
            continue
        if kept:
            rewritten.append(fragment.path.name)
            planned[fragment.path] = fragment.preamble + "".join(block.text for block in kept)
            continue
        deleted.append(fragment.path.name)
        if fragment.preamble.strip():
            comment_only.append((fragment.path.name, fragment.preamble))
        planned[fragment.path] = None
    result.fragments_rewritten = tuple(rewritten)
    result.fragments_deleted = tuple(deleted)
    result.comment_only_removed = tuple(comment_only)
    return planned


def _write(planned: Mapping[Path, str | None], result: EditionOutcome) -> None:
    """Write the previewed strip, keeping each file's own line endings, and read every write back.

    The read-back is on the raw bytes: a write that doubled a carriage return or
    flipped the file's style raises rather than being accepted, because a
    fragment corrupted here is otherwise only discovered by the next load.

    A section directory left holding no fragment is removed in the same pass.
    The loader refuses an empty section directory, so deleting the last fragment
    below one and leaving the directory standing would stop the modelo loading
    just as surely as an empty fragment would. The sweep is version-control
    free, and it removes only a directory it finds genuinely empty.
    """
    emptied: set[Path] = set()
    for path, text in sorted(planned.items()):
        if text is None:
            path.unlink()
            emptied.add(path.parent)
        else:
            style = write_preserving_newlines(path, text)
            verify_written(path, style)
    removed: list[str] = []
    for directory in sorted(emptied):
        if any(directory.glob("*.toml")) or any(directory.iterdir()):
            continue
        directory.rmdir()
        removed.append(directory.name)
    result.directories_removed = tuple(removed)


def _members_from_texts(edition_dir: Path, planned: Mapping[Path, str | None]) -> tuple[object, ...]:
    """The edition's stated binding members after the previewed strip, read back from the rewritten text.

    Read back rather than taken from the plan, so what the proof compares is the
    text that would be on disk: a rewrite that lost or mangled a sibling row
    shows up here rather than surviving into a run.
    """
    members: list[object] = []
    for path in sorted((edition_dir / _BINDINGS).glob("*.toml")):
        text = planned[path] if path in planned else path.read_text(encoding="utf-8")
        if text is None:
            continue
        _preamble, blocks = _split_blocks(text)
        members.extend(_block_member(block) for block in blocks)
    return tuple(members)


def _edition_tables(modelo_dir: Path) -> dict[str, dict[str, Any]]:
    editions_root = modelo_dir / _REVISIONS
    return {
        path.name: _merged_revision_table(path, path.name) for path in sorted(editions_root.iterdir()) if path.is_dir()
    }


def _binding_state(
    modelo_dir: Path,
    edition_id: str,
    tables: Mapping[str, dict[str, Any]],
    stated: tuple[object, ...] | None = None,
) -> dict[str, Any]:
    """The typed binding set the successor materialises under canonical enrollment.

    ``stated`` replaces the edition's own members with the ones the strip would
    leave, which is how the after side is computed without writing anything.
    """
    resolved = dict(tables)
    if stated is not None:
        resolved[edition_id] = {**tables[edition_id], _BINDINGS: stated}
    members = _materialised_bindings(modelo_dir.name, edition_id, resolved)
    return _typed(members, _binding_default(resolved[edition_id]))


def _edge_refusal(modelo_dir: Path, edition_id: str) -> str:
    """Why this edge cannot be planned, or the empty string when it can.

    Checked before anything is planned, so an operator naming a set of edges
    learns about every bad one at once rather than one run at a time.
    """
    if not modelo_dir.is_dir():
        return "modelo is not in the registry"
    edition_dir = modelo_dir / _REVISIONS / edition_id
    if not edition_dir.is_dir():
        return "successor edition is not declared"
    table = _merged_revision_table(edition_dir, edition_id)
    if not table:
        return "successor edition is not declared"
    if _declares_none_root(table):
        return "successor declares [predecessor.none]: it inherits nothing and states itself in full"
    if _declared_predecessor(table) is None:
        return "successor declares no predecessor"
    if not _keyed_members(table):
        return "successor states no binding members"
    return ""


def _validate_edges(registry_root: Path, edges: Sequence[tuple[str, str]]) -> None:
    refused = [
        f"{modelo}/{edition}: {reason}"
        for modelo, edition in edges
        if (reason := _edge_refusal(registry_root / _MODELOS / modelo, edition))
    ]
    if refused:
        raise RegistryError("unplannable edge(s): " + "; ".join(refused))


def strip_registry(
    registry_root: Path,
    *,
    modelo_ids: Sequence[str] = (),
    edges: Sequence[tuple[str, str]] = (),
    exclusions: ExclusionSet | None = None,
    equality: Equality = MATERIALISED,
    apply: bool = False,
) -> StripReport:
    """Plan, prove and optionally write the strip for every requested modelo or edge.

    ``edges`` names individual ``(modelo, successor-edition)`` pairs and, when
    given, is the whole selection: no other edition of a named modelo is
    examined. Every named edge is validated first and the run refuses as a whole
    if any is unplannable.

    ``exclusions`` names the modelos and editions to withhold, each with its
    reason, and defaults to the frozen modelos alone. An exclusion outranks a
    selection: an excluded edge is dropped before validation, so naming it is
    not a refusal, and an excluded target is never planned, proved or written.
    """
    report = StripReport(
        equality=equality,
        applied=apply,
        enrolment="canonical: bindings are in the loader's _KEYED_FAMILIES",
        edges=tuple(edges),
        exclusions=exclusions if exclusions is not None else collect_exclusions(),
    )
    withheld = report.exclusions
    selected: dict[str, tuple[str, ...]] = {}
    if edges:
        remaining = [(modelo, edition) for modelo, edition in edges if not withheld.excludes(modelo, edition)]
        if not remaining:
            # Every named edge was excluded. An empty selection must not read as
            # "no selection": that would widen an edge run into a corpus sweep.
            return report
        _validate_edges(registry_root, remaining)
        for modelo, edition in remaining:
            selected[modelo] = (*selected.get(modelo, ()), edition)
        modelo_ids = tuple(selected)
    modelos_root = registry_root / _MODELOS
    for modelo_dir in sorted(path for path in modelos_root.iterdir() if path.is_dir()):
        if modelo_ids and modelo_dir.name not in modelo_ids:
            continue
        if withheld.excludes_modelo(modelo_dir.name):
            continue
        with modelo_fact_scope(modelo_dir):
            outcome = plan_modelo(
                modelo_dir,
                equality=equality,
                edition_ids=selected.get(modelo_dir.name, ()),
                excluded_edition_ids=withheld.editions_of(modelo_dir.name),
            )
            tables = _edition_tables(modelo_dir) if any(edition.removed for edition in outcome.editions) else {}
            for edition in outcome.editions:
                if edition.refusal or not edition.removed:
                    continue
                edition_dir = modelo_dir / _REVISIONS / edition.edition
                try:
                    before = _binding_state(modelo_dir, edition.edition, tables)
                    planned = _preview(edition_dir, frozenset(edition.removed), edition)
                    after = _binding_state(
                        modelo_dir, edition.edition, tables, _members_from_texts(edition_dir, planned)
                    )
                except (RegistryError, RegistryLoadError) as exc:
                    # The merge refuses this edition as it stands -- an undeclared
                    # repurpose is the usual cause -- so the strip is unprovable and
                    # the edition is reported refused rather than written.
                    edition.refusal = f"{type(exc).__name__}: {exc}"
                    edition.removed = ()
                    continue
                if after != before:
                    edition.proof = _proof_failure(before, after)
                    raise RegistryError(
                        f"modelo {modelo_dir.name} edition {edition.edition!r}: the strip would change the "
                        f"materialised binding set: {edition.proof}"
                    )
                edition.proof = "byte-identical (canonical enrolment)"
                if apply:
                    _write(planned, edition)
        report.modelos.append(outcome)
    return report


def _proof_failure(before: Mapping[str, Any], after: Mapping[str, Any]) -> str:
    lost = sorted(set(before) - set(after))
    gained = sorted(set(after) - set(before))
    changed = sorted(key for key in set(before) & set(after) if before[key] != after[key])
    return f"DIFFERS lost={lost[:5]} gained={gained[:5]} changed={changed[:5]}"


def render_report(report: StripReport) -> str:
    """Render the run for a terminal reader."""
    lines = [
        f"strip-restated-bindings equality={report.equality} applied={report.applied}",
        f"enrolment: {report.enrolment}",
    ]
    if report.edges:
        lines.append(f"edges: {len(report.edges)} selected: " + " ".join(f"{m}/{e}" for m, e in report.edges))
    lines.extend(report.exclusions.render_lines())
    for modelo in report.modelos:
        if not modelo.editions:
            continue
        lines.append(
            f"  {modelo.modelo}: removable={modelo.removed} kept_differs={modelo.kept_differs} "
            f"carried_grounding={modelo.carried_grounding} "
            f"restated_after_lifting={modelo.restated_after_lifting} "
            f"restated_ignoring_refs={modelo.restated_ignoring_refs} refusals={modelo.refusals}"
        )
        for edition in modelo.editions:
            if edition.refusal:
                lines.append(f"    {edition.edition}: refused: {edition.refusal}")
            else:
                lines.append(
                    f"    {edition.edition} <- {edition.predecessor}: stated={edition.stated} "
                    f"removable={len(edition.removed)} kept_new={edition.kept_new} "
                    f"kept_differs={len(edition.kept_differs)} "
                    f"carried_grounding={len(edition.carried_grounding)} "
                    f"restated_after_lifting={len(edition.restated_after_lifting)} proof={edition.proof}"
                )
    payload = report.as_json()["totals"]
    lines.append(
        f"corpus: removable={payload['removed']} kept_differs={payload['kept_differs']} "
        f"carried_grounding={payload['carried_grounding']} "
        f"restated_after_lifting={payload['restated_after_lifting']} "
        f"restated_ignoring_refs={payload['restated_ignoring_refs']} refusals={payload['refusals']}"
    )
    return "\n".join(lines)


def _default_registry_root() -> Path:
    from cadrumo.core.resources.bundled_data import bundled_path

    return Path(bundled_path("registry", "aeat")).resolve()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the strip over the requested modelos. Returns 0 unless a refusal blocks the run."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modelo", action="append", default=[], help="a modelo id; repeatable")
    parser.add_argument("--all", action="store_true", help="every modelo in the registry")
    parser.add_argument(
        "--edge",
        action="append",
        default=[],
        metavar="MODELO/EDITION",
        help="one predecessor->successor edge, named by its successor; repeatable",
    )
    parser.add_argument(
        "--edges-file",
        type=Path,
        default=None,
        help="a file of 'modelo/edition' edges, one per line, '#' comments and blank lines ignored",
    )
    parser.add_argument("--dry-run", action="store_true", default=True, help="plan and prove only (the default)")
    parser.add_argument("--apply", action="store_true", help="write the strip after the proof passes")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="MODELO",
        help="withhold a whole modelo from the run; repeatable",
    )
    parser.add_argument(
        "--exclusions-file",
        type=Path,
        default=None,
        help=(
            "a file of exclusions, one '<modelo>' or '<modelo>/<edition>' per line; a '#' "
            "comment states the reason for the entries that follow it"
        ),
    )
    parser.add_argument(
        "--exclude-edition",
        action="append",
        default=[],
        metavar="MODELO/EDITION",
        help=(
            "withhold one edition from the run; repeatable. An excluded edition is never "
            "planned, proved or written, and is listed in the report with its reason"
        ),
    )
    parser.add_argument(
        "--exclude-reason",
        default=DEFAULT_EXCLUSION_REASON,
        metavar="TEXT",
        help="the reason reported for every exclusion of this run",
    )
    parser.add_argument("--report", type=Path, default=None, help="write the run as JSON to this path")
    parser.add_argument("--registry-root", type=Path, default=None, help="a registry tree other than the shipped one")
    parser.add_argument(
        "--equality",
        choices=(MATERIALISED, LIFTED),
        default=MATERIALISED,
        help="which restatement equality to remove under; only 'materialised' may be applied",
    )
    args = parser.parse_args(argv)
    edge_mode = bool(args.edge or args.edges_file is not None)
    if edge_mode and (args.modelo or args.all):
        parser.error("--edge/--edges-file select edges; do not combine them with --modelo or --all")
    if not edge_mode and not args.modelo and not args.all:
        parser.error("name at least one --modelo or --edge, pass --edges-file, or pass --all")
    if args.apply and args.equality != MATERIALISED:
        parser.error("--apply removes only members provable under the 'materialised' equality")
    root = args.registry_root.resolve() if args.registry_root is not None else _default_registry_root()
    try:
        edges = dict.fromkeys(
            (
                *(parse_edge(text) for text in args.edge),
                *(parse_edges_file(args.edges_file) if args.edges_file is not None else ()),
            )
        )
        report = strip_registry(
            root,
            modelo_ids=tuple(args.modelo),
            edges=tuple(edges),
            exclusions=collect_exclusions(
                modelos=args.exclude,
                editions=args.exclude_edition,
                reason=args.exclude_reason,
                path=args.exclusions_file,
            ),
            equality=args.equality,
            apply=bool(args.apply),
        )
    except RegistryError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(render_report(report))
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report.as_json(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
