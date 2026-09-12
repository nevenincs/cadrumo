"""Lift a family's shared ``source_refs`` from its members onto the edition manifest.

An edition's members each cite the document that grounds them, and in the
full-copy authoring shape every member of the family restates that citation.
The loader already knows how to supply it once: ``ModeloRevision`` carries a
source-default field for every family the domain pairs with one, beside
``casilla_source_refs``, and
:func:`dev.registry.compiler._loader_internals._apply_edition_reference_defaults`
fills them into the members that state none. What the corpus lacks is the
declaration, so the restatement stands unlifted and the edition-delta screen
reports it as ``family_default_undeclared``.

This tool declares it. Per edition and family it derives the candidate default
with :func:`dev.registry.source_default_rule.edition_source_default` -- the same
function the screen consults, imported rather than copied, so the tool and the
signal cannot disagree about what is liftable -- writes it onto the edition's
``revision.toml`` beside ``casilla_source_refs``, and rewrites each member's
statement by the loader's own member-side rule: a member whose ``source_refs``
EQUAL the default states none, a member whose references OPEN with the default
keeps only the tail as ``additional_source_refs``, and a member stating anything
else is irreducible and is kept whole.

Refusals, each one an edition the tool declines rather than guesses at:

- the rule derives no default (a member states no ``source_refs``, no leading
  run opens two members, or two runs tie) -- the rule's own reason is reported;
- the manifest already declares a different default for that family. The
  declaration is the higher authority and is never overwritten. A manifest
  declaring the SAME value is not a refusal and not overwritten either: it is
  already true, and only the members are rewritten under it. Declaring the
  default and lifting it out of the members are two halves of one lift, and an
  edition that took only the first half is not finished -- the restatement
  stands, and the member-side rule applies to it unchanged. An edition whose
  members all state something irreducible has nothing left to rewrite and is
  reported as done;
- a member states ``source_refs`` the textual pass cannot reproduce exactly. Both
  the one-line and the multi-line array spellings are read and rewritten, so what
  remains unreproducible is a statement carrying something the tool would have to
  drop to rewrite it -- an authored comment inside the array, a non-quoted value,
  or no closing bracket. Such a statement refuses the WHOLE edition rather than
  being partially applied.

Which families are liftable is read from the domain's own
``FAMILY_SOURCE_DEFAULT_FIELDS`` pairing rather than restated here, so the
``--family`` choices, the manifest-key mapping and the member-rewrite set
follow the loader that consumes them and cannot drift from it.

The casilla family is derived and reported like the rest, but only its manifest
declaration is written: casilla member statements are lifted by their own
owning pass, and rewriting them here would be two writers on one surface.

Writes are per modelo and are gated on the modelo still compiling: every edited
file is re-parsed, and the modelo is loaded through
:func:`dev.registry.compiler.loader.load_modelo_directory` before the change is
kept. A modelo that fails either check is rolled back to the bytes it had and
reported as a refusal, so a failed lift never leaves a half-written tree.

Modes. Without ``--apply`` the tool reports what it would do and writes nothing.
``--modelo`` scopes to one modelo, ``--all`` to every modelo in the corpus, and
``--report`` writes the findings to a file as well as to stdout.
``--exclude`` withholds a whole modelo, ``--exclude-edition <modelo>/<edition>``
withholds one edition, and ``--exclusions-file`` reads either from a campaign
file. The frozen modelos of :data:`dev.registry.run_exclusions.FROZEN_MODELOS`
are withheld from every run whether or not a flag names them.
``--exclude-reason`` states once why this run's flag-named exclusions were made.
An excluded target is never examined -- it plans nothing, refuses nothing and
carries no declaration forward -- and is listed in the report with its reason,
so a run states what it declined to look at as plainly as what it did.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, cast, get_args

from cadrumo.domain.calculations.registry.reference_sections import FAMILY_SOURCE_DEFAULT_FIELDS
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from .corpus_write import verify_written, write_preserving_newlines
from .run_exclusions import (
    DEFAULT_EXCLUSION_REASON,
    Exclusion,
    MalformedExclusionError,
    collect_exclusions,
    excluded_editions,
)
from .source_default_rule import edition_source_default

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
REGISTRY_MODELOS_ROOT: Final = REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"

__all__ = [
    "FAMILY_DEFAULT_KEY",
    "EditionLift",
    "ModeloPlan",
    "apply_plan",
    "lifted_fragment_text",
    "load_outcome",
    "main",
    "plan_modelo",
    "render_plan",
]

_REVISIONS: Final = "revisions"
_MANIFEST: Final = "revision.toml"

#: The manifest key each family lifts its shared ``source_refs`` into. Every
#: inheritable family comes from the domain's own pairing so this tool cannot
#: default one family from another's grounding; the casilla key is named here
#: because that family's member-side lift is owned elsewhere.
FAMILY_DEFAULT_KEY: Final[dict[str, str]] = {"casillas": "casilla_source_refs"}

#: Families whose members this tool rewrites: every family the domain pairs
#: with a manifest key. The casilla family is derived and declared but never
#: rewritten here, because its members belong to another pass.
_MEMBER_REWRITE_FAMILIES: Final[set[str]] = set()

#: Every family this tool acts on, in the domain's own order with the
#: declare-only casilla family last.
_ENROLLED_FAMILIES: Final[list[str]] = []


def _enroll_domain_family_keys() -> None:
    """Fill this module's family tables from the domain's own family/manifest pairing.

    The pairing is the single source of which families carry an edition-level
    source default, so the ``--family`` choices, the manifest-key mapping and
    the member-rewrite set are all read off it rather than restated here. A
    family the domain adds to the pairing is liftable the moment it lands, and
    one it removes stops being an option, without this tool being edited: a
    hardcoded list could only ever disagree with the loader that consumes it.
    """
    FAMILY_DEFAULT_KEY.update(dict(FAMILY_SOURCE_DEFAULT_FIELDS))
    paired = [family for family, _ in FAMILY_SOURCE_DEFAULT_FIELDS]
    _MEMBER_REWRITE_FAMILIES.update(paired)
    _ENROLLED_FAMILIES.extend(paired)
    _ENROLLED_FAMILIES.append("casillas")


_enroll_domain_family_keys()

FAMILIES: Final[tuple[str, ...]] = tuple(_ENROLLED_FAMILIES)

_ARRAY_TABLE_HEADER: Final = re.compile(
    r"""^\[\[revisions\.(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|(?P<bare>[^.\]]+))\.(?P<family>[A-Za-z_]+)\]\]\s*$"""
)
_SOURCE_REFS_LINE: Final = re.compile(r"""^(?P<indent>\s*)source_refs\s*=\s*\[(?P<items>[^\]]*)\]\s*$""")
_SOURCE_REFS_OPENING: Final = re.compile(r"""^\s*source_refs\s*=""")
_QUOTED_ITEM: Final = re.compile(r'"([^"]*)"')


def _quoted_items(text: str) -> tuple[str, ...]:
    """Return the double-quoted items of a one-line TOML array."""
    return tuple(str(item) for item in _QUOTED_ITEM.findall(text))


@dataclass(frozen=True, slots=True)
class _RefsSpan:
    """One member's own ``source_refs`` statement, however many lines it occupies.

    ``last`` is the index of the final line of the statement, equal to ``first``
    for the one-line spelling. ``items`` is what the statement says, read the
    same way from either spelling, so the member-side rule is applied once
    rather than once per layout.
    """

    first: int
    last: int
    indent: str
    items: tuple[str, ...]


def _refs_span(lines: Sequence[str], start: int) -> _RefsSpan | None:
    """Read the ``source_refs`` statement opening at ``lines[start]``, or ``None`` if it is unreproducible.

    A statement is reproducible when the tool can read every reference out of it
    and put the remainder back in its own one-line spelling without losing
    anything a reader authored. A span carrying a comment, a trailing key on the
    closing line, a non-quoted value, or no closing bracket at all is not
    reproducible, and is reported rather than guessed at: a rewrite that dropped
    an authored comment would be a silent edit to grounding nobody asked for.
    """
    single = _SOURCE_REFS_LINE.match(lines[start])
    if single is not None:
        return _RefsSpan(start, start, single.group("indent"), _quoted_items(single.group("items")))
    opening = lines[start]
    indent = opening[: len(opening) - len(opening.lstrip())]
    body = opening.partition("=")[2]
    if body.strip() != "[":
        return None
    collected = [body.strip()]
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if _ARRAY_TABLE_HEADER.match(line) or line.startswith("["):
            return None
        collected.append(line.strip())
        if line.strip().endswith("]"):
            joined = " ".join(collected)
            inner = joined[joined.index("[") + 1 : joined.rindex("]")]
            items = _quoted_items(inner)
            residue = _QUOTED_ITEM.sub("", inner).replace(",", "").strip()
            if residue:
                return None
            return _RefsSpan(start, index, indent, items)
    return None


def _write(path: Path, text: str) -> str:
    r"""Write a corpus file in the line-ending style it already had, and return that style.

    The style is detected from the file's own raw bytes rather than assumed,
    because the text layer's default
    translates every ``\\n`` to the platform separator, which on Windows
    rewrites a whole LF-authored fragment to CRLF and reports a change on every
    line of a file the run meant to touch on one. The corpus is LF throughout,
    and the rollback path below restores through this same function, so a
    translated write would make even a rolled-back run dirty the tree.
    """
    return write_preserving_newlines(path, text)


def _render_refs(key: str, refs: Sequence[str]) -> str:
    return f"{key} = [" + ", ".join(f'"{ref}"' for ref in refs) + "]"


@dataclass(frozen=True, slots=True)
class EditionLift:
    """One edition/family decision: a default to declare, or a reason not to."""

    modelo: str
    edition: str
    family: str
    default: tuple[str, ...] = ()
    refusal: str = ""
    members: int = 0
    fragments: tuple[Path, ...] = ()
    #: Whether the manifest already declares this default, so only the members
    #: are rewritten. The declaration is the higher authority either way: an
    #: equal one is not rewritten, it is simply already true.
    manifest_declared: bool = False
    #: The predecessor edition whose derived default this edition carries. Set
    #: only on a carried declaration: an edition owning no member of the family
    #: that inherits a lifted edition's rows, and so must state the same default
    #: for those rows to materialise unchanged. Empty on a normal lift.
    inherited_from: str = ""

    @property
    def liftable(self) -> bool:
        """Whether this decision writes anything."""
        return bool(self.default) and not self.refusal


@dataclass
class ModeloPlan:
    """One modelo's lift decisions across every edition and family."""

    modelo: str
    lifts: list[EditionLift] = field(default_factory=list)
    #: Lifts withheld because a file they would write is under a live edit,
    #: each with the paths that were too recent and their ages in minutes.
    skipped: list[tuple[EditionLift, tuple[tuple[Path, float], ...]]] = field(default_factory=list)
    #: Editions the operator excluded, each with the reason given for the exclusion.
    #: An excluded edition is never examined, so it plans nothing and refuses nothing;
    #: it is reported so the run states what it declined to look at and why.
    exclusions: list[tuple[str, str]] = field(default_factory=list)

    @property
    def liftable(self) -> list[EditionLift]:
        """Every decision this plan would write."""
        return [lift for lift in self.lifts if lift.liftable]

    @property
    def refusals(self) -> list[EditionLift]:
        """Every decision this plan declines, with the reason."""
        return [lift for lift in self.lifts if lift.refusal]

    @property
    def manifests(self) -> dict[str, tuple[tuple[str, ...], str]]:
        """The manifest fields this plan would write, and any carry, keyed by edition."""
        written: dict[str, list[str]] = {}
        carried: dict[str, str] = {}
        for lift in self.liftable:
            if lift.manifest_declared:
                continue
            written.setdefault(lift.edition, []).append(FAMILY_DEFAULT_KEY[lift.family])
            if lift.inherited_from:
                carried[lift.edition] = lift.inherited_from
        return {edition: (tuple(sorted(keys)), carried.get(edition, "")) for edition, keys in sorted(written.items())}


def iter_modelo_dirs(modelos_root: Path = REGISTRY_MODELOS_ROOT) -> list[Path]:
    """Return every modelo directory under the corpus root."""
    return sorted(path for path in modelos_root.iterdir() if path.is_dir())


def _edition_dirs(modelo_dir: Path) -> list[Path]:
    revisions = modelo_dir / _REVISIONS
    return sorted(path for path in revisions.iterdir() if path.is_dir()) if revisions.is_dir() else []


def _revision_table(edition_dir: Path) -> dict[str, Any]:
    manifest = edition_dir / _MANIFEST
    if not manifest.is_file():
        return {}
    table = tomllib.loads(manifest.read_text(encoding="utf-8")).get(_REVISIONS, {}).get(edition_dir.name, {})
    return table if isinstance(table, dict) else {}


def _members(edition_dir: Path, family: str) -> tuple[list[Mapping[str, Any]], tuple[Path, ...]]:
    """Every member of one family under an edition, merged across fragments as the loader merges them."""
    found: list[Mapping[str, Any]] = []
    fragments: list[Path] = []
    for path in sorted(edition_dir.rglob("*.toml")):
        table = tomllib.loads(path.read_text(encoding="utf-8")).get(_REVISIONS, {}).get(edition_dir.name, {})
        if not isinstance(table, dict):
            continue
        declared = table.get(family)
        rows = [row for row in declared if isinstance(row, dict)] if isinstance(declared, list) else []
        if rows:
            found.extend(rows)
            fragments.append(path)
    return found, tuple(fragments)


def _unreproducible_statements(fragments: Sequence[Path], edition_id: str, family: str) -> tuple[str, ...]:
    """Return every ``source_refs`` statement of this family the textual rewrite cannot reproduce."""
    found: list[str] = []
    for path in fragments:
        in_member = False
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            header = _ARRAY_TABLE_HEADER.match(line)
            if line.startswith("["):
                in_member = header is not None and header.group("family") == family and _header_id(header) == edition_id
                continue
            if in_member and _SOURCE_REFS_OPENING.match(line) and _refs_span(lines, index) is None:
                found.append(f"{path.name}: {line.strip()}")
    return tuple(found)


def _header_id(header: re.Match[str]) -> str:
    return str(header.group("dq") or header.group("sq") or header.group("bare") or "")


def _declared_predecessor(table: Mapping[str, Any]) -> str | None:
    """Return the sibling edition this one is authored against, if it declares one.

    ``predecessor`` is either the sibling's revision id or a single ``none``
    table grounding why no earlier sibling exists. Only the first is a link to
    walk; a ``none`` table ends the chain, as does an absent declaration.
    """
    value = table.get("predecessor")
    return value if isinstance(value, str) else None


def _successor_editions(modelo_dir: Path) -> dict[str, list[str]]:
    """Return each edition's declared successors, keyed by the predecessor's id."""
    successors: dict[str, list[str]] = {}
    for edition_dir in _edition_dirs(modelo_dir):
        predecessor = _declared_predecessor(_revision_table(edition_dir))
        if predecessor is not None:
            successors.setdefault(predecessor, []).append(edition_dir.name)
    return {edition: sorted(names) for edition, names in successors.items()}


def _member_ids(edition_dir: Path, family: str) -> frozenset[str]:
    """The ids an edition states itself for one family."""
    members, _fragments = _members(edition_dir, family)
    return frozenset(str(row["id"]) for row in members if "id" in row)


def _live_inherited_ids(
    modelo_dir: Path,
    edition: str,
    family: str,
    loaded: dict[str, Any] | None = None,
) -> frozenset[str] | None:
    """The ids that materialise in ``edition`` without that edition stating them.

    Read off the PUBLIC loader rather than reimplementing the keyed-family
    merge: a member the successor supersedes appears under the successor's own
    stated id, and one an evolution retires does not materialise at all, so
    what remains is exactly the set the successor inherits live. Reproducing
    that rule here would be a second copy of it, free to disagree with the
    loader it is predicting.

    Returns ``None`` when the modelo does not load, because then nothing about
    its materialisation is known and a caller must not read an empty set as
    proof that nothing is inherited.
    """
    cache = loaded if loaded is not None else {}
    if "modelo" not in cache:
        try:
            from .compiler.loader import load_modelo_directory

            cache["modelo"] = load_modelo_directory(modelo_dir)
        except Exception:
            cache["modelo"] = None
    modelo = cache["modelo"]
    if modelo is None or edition not in modelo.revisions:
        return None
    revision = modelo.revisions[edition]
    members = getattr(revision, family, ())
    materialised = frozenset(str(member.id) for member in members if getattr(member, "id", None) is not None)
    return materialised - _member_ids(modelo_dir / _REVISIONS / edition, family)


def _lift_write_targets(modelo_dir: Path, lift: EditionLift) -> tuple[Path, ...]:
    """Every file this lift would write: its family fragments and the edition manifest."""
    targets = list(lift.fragments) if lift.family in _MEMBER_REWRITE_FAMILIES else []
    if not lift.manifest_declared:
        targets.append(modelo_dir / _REVISIONS / lift.edition / _MANIFEST)
    return tuple(targets)


def _recently_modified(
    paths: Sequence[Path], minutes: float, now: float | None = None
) -> tuple[tuple[Path, float], ...]:
    """Return the paths modified within ``minutes``, with each one's age in minutes.

    A file another writer touched moments ago is that writer's in-flight work.
    Writing over it would destroy an edit this tool never saw, and the age is
    reported so a skip can be read as "too recent" rather than as a refusal.
    """
    if minutes <= 0:
        return ()
    moment = time.time() if now is None else now
    recent: list[tuple[Path, float]] = []
    for path in paths:
        if not path.is_file():
            continue
        age = (moment - path.stat().st_mtime) / 60
        if age < minutes:
            recent.append((path, age))
    return tuple(recent)


def _revision_model() -> Any:
    """The typed revision model whose fields declare the caps this tool must respect."""
    return ModeloRevision


def _materialised_refs(stated: object, default: tuple[str, ...]) -> tuple[str, ...] | None:
    """The references a member will carry once the lift has rewritten it.

    Mirrors what the loader fills in, so the value validated here is the value
    that will exist: a member stating the default exactly carries the default, a
    member opening with it carries the default followed by its tail, and an
    irreducible member is untouched and carries what it states.
    """
    if not isinstance(stated, list):
        return default
    refs = tuple(str(item) for item in stated)
    if refs[: len(default)] == default:
        return refs
    return None


def _cap_refusal(edition_dir: Path, lift: EditionLift) -> str:
    """Return a reason this lift's values fail the schema, or an empty string.

    Every value the lift writes is put through the typed field that owns it
    BEFORE anything is written: the manifest declaration through the
    ``ModeloRevision`` field it lands on, and each rewritten member's references
    through that family's own member-model field, carrying what it will
    materialise with. Each cap -- item count, id length, id pattern -- is
    therefore enforced by the schema that declares it, and no limit is restated
    here to drift from it.

    Only the fields this tool writes are checked. Validating a whole member
    standalone would refuse valid corpus rows, because the loader normalises
    parts of a row -- ``legal_refs`` among them -- before typed construction,
    and a gate that rejects what the corpus legitimately contains is worse than
    no gate.

    A write that produced an over-cap value would otherwise be caught only by
    the post-write load, after the tree had been touched and on the rollback
    path rather than the refusal path.
    """
    from pydantic import TypeAdapter, ValidationError

    revision = _revision_model()
    key = FAMILY_DEFAULT_KEY[lift.family]
    manifest_field = revision.model_fields.get(key)
    if manifest_field is not None:
        try:
            TypeAdapter(manifest_field.annotation).validate_python(list(lift.default))
        except ValidationError as error:
            return f"{key} would not validate against {revision.__name__}: {error.errors()[0]['msg']}"

    family_field = revision.model_fields.get(lift.family)
    member_models = get_args(family_field.annotation) if family_field is not None else ()
    if not member_models:
        return ""
    member_model = member_models[0]
    written_fields = {
        name: TypeAdapter(field.annotation)
        for name in ("source_refs", "additional_source_refs")
        if (field := member_model.model_fields.get(name)) is not None
    }
    try:
        members, _fragments = _members(edition_dir, lift.family)
    except tomllib.TOMLDecodeError:
        # An unparseable fragment is the re-parse gate's finding, not this
        # one's; reporting it here would relabel a malformed tree as a cap
        # violation and rob that gate of its own refusal.
        return ""
    for row in members:
        refs = _materialised_refs(row.get("source_refs"), lift.default)
        if refs is None:
            continue
        checked = {"source_refs": list(refs)}
        tail = refs[len(lift.default) :]
        if tail and "additional_source_refs" in written_fields:
            checked["additional_source_refs"] = list(tail)
        for name, adapter in written_fields.items():
            if name not in checked:
                continue
            try:
                adapter.validate_python(checked[name])
            except ValidationError as error:
                return (
                    f"member {row.get('id', '<no id>')!r} {name} would not validate against "
                    f"{member_model.__name__}: {error.errors()[0]['msg']}"
                )
    return ""


def _rewritable_members(members: Sequence[Mapping[str, Any]], default: tuple[str, ...]) -> int:
    """Count the members whose own ``source_refs`` the member-side rule would rewrite.

    A member states the default exactly, or opens with it and carries a tail;
    either is work. A member stating anything else is irreducible and is kept
    whole, so an edition holding only those has nothing left to lift and is
    reported as done rather than as a lift that rewrites nothing.
    """
    rewritable = 0
    for member in members:
        stated: object = member.get("source_refs")
        if not isinstance(stated, list):
            continue
        refs = tuple(str(item) for item in cast("list[object]", stated))
        rewritable += refs[: len(default)] == default
    return rewritable


def plan_edition(modelo: str, edition_dir: Path, family: str) -> EditionLift | None:
    """Decide one edition/family: the default to declare, a refusal, or nothing to do."""
    members, fragments = _members(edition_dir, family)
    if not members:
        return None
    edition = edition_dir.name
    key = FAMILY_DEFAULT_KEY[family]
    declared = _revision_table(edition_dir).get(key)
    derived, withheld = edition_source_default(members)

    def lift(*, default: tuple[str, ...] = (), refusal: str = "", manifest_declared: bool = False) -> EditionLift:
        return EditionLift(
            modelo=modelo,
            edition=edition,
            family=family,
            default=default,
            refusal=refusal,
            members=len(members),
            fragments=fragments,
            manifest_declared=manifest_declared,
        )

    def unrewritable(default: tuple[str, ...]) -> EditionLift | None:
        if family not in _MEMBER_REWRITE_FAMILIES:
            return None
        unreproducible = _unreproducible_statements(fragments, edition, family)
        if not unreproducible:
            return None
        return lift(
            default=default,
            refusal=f"{len(unreproducible)} source_refs statement(s) not textually rewritable: "
            + "; ".join(unreproducible),
        )

    if isinstance(declared, list):
        already = tuple(str(item) for item in declared)
        if derived is not None and already != derived:
            return lift(refusal=f"{key} already declares {list(already)}; the rule derives {list(derived)}")
        # A declaration equal to the derived default is already true, so the
        # manifest is left alone -- but the members it speaks for may still
        # restate it. Declaring the default and lifting it out of the members
        # are two halves of one lift, and an edition that took only the first
        # half is not finished: the restatement stands, and the member-side
        # rule applies to it unchanged.
        if family not in _MEMBER_REWRITE_FAMILIES or derived is None or not _rewritable_members(members, already):
            return None
        return unrewritable(already) or lift(default=already, manifest_declared=True)
    if derived is None:
        return lift(refusal=str(withheld))
    return unrewritable(derived) or lift(default=derived)


def _forward_closure(
    modelo_dir: Path,
    lift: EditionLift,
    successors: Mapping[str, Sequence[str]],
    loaded: dict[str, Any],
) -> tuple[list[EditionLift], str]:
    """Return the declarations this lift's successors must carry, or the reason it refuses.

    A member the lift strips still materialises into every edition that
    inherits it, and the loader grounds an inherited row stating no
    ``source_refs`` in the edition it now sits in. So each edition in the
    forward closure must resolve the same default, or those rows would move
    onto a different grounding without the edition ever failing to load.

    An edition owning no member of the family carries this default and is
    marked with the predecessor it came from. One owning members keeps its own
    plan, and the lift is refused only when that edition's effective default
    differs AND at least one of the lifted edition's members actually
    materialises live in it -- a member the successor supersedes or retires
    never reaches materialisation, so a differing default cannot reground it.
    An edition owning members that derive no default at all is always refused:
    the inherited rows would then materialise with no grounding whatever.
    """
    key = FAMILY_DEFAULT_KEY[lift.family]
    lifted_ids = _member_ids(modelo_dir / _REVISIONS / lift.edition, lift.family)
    carried: list[EditionLift] = []
    seen = {lift.edition}
    queue = list(successors.get(lift.edition, ()))
    while queue:
        edition = queue.pop(0)
        if edition in seen:
            continue
        seen.add(edition)
        edition_dir = modelo_dir / _REVISIONS / edition
        table = _revision_table(edition_dir)
        members, _fragments = _members(edition_dir, lift.family)
        declared = table.get(key)
        effective: tuple[str, ...] | None
        if isinstance(declared, list):
            effective, origin = tuple(str(item) for item in declared), "declares"
        elif members:
            effective, origin = edition_source_default(members)[0], "owns members and derives"
        else:
            carried.append(
                EditionLift(
                    modelo=lift.modelo,
                    edition=edition,
                    family=lift.family,
                    default=lift.default,
                    inherited_from=lift.edition,
                )
            )
            queue.extend(successors.get(edition, ()))
            continue
        if effective is None:
            return [], (
                f"no_derivable_default: successor edition {edition!r} owns {len(members)} member(s) of "
                f"{lift.family} and derives no default, so rows inherited from {lift.edition!r} would "
                f"materialise with no grounding at all instead of {list(lift.default)}"
            )
        if effective != lift.default:
            live = _live_inherited_ids(modelo_dir, edition, lift.family, loaded)
            if live is None:
                return [], (
                    f"live_regrounding: successor edition {edition!r} {origin} {list(effective)} against "
                    f"{list(lift.default)} on {lift.edition!r}, and the modelo does not load, so which "
                    "members it inherits live cannot be established"
                )
            regrounded = sorted(live & lifted_ids)
            if regrounded:
                return [], (
                    f"live_regrounding: successor edition {edition!r} {origin} {list(effective)}, but "
                    f"{len(regrounded)} member(s) of {lift.family} inherited live from {lift.edition!r} "
                    f"would be regrounded from {list(lift.default)} to {list(effective)}: " + ", ".join(regrounded)
                )
        queue.extend(successors.get(edition, ()))
    return carried, ""


def plan_modelo(
    modelo_dir: Path,
    families: Sequence[str] = FAMILIES,
    *,
    excluded: Mapping[str, str] = MappingProxyType({}),
) -> ModeloPlan:
    """Decide every edition and family of one modelo, and the declarations its successors carry.

    ``excluded`` maps an edition id of this modelo to the reason it is excluded.
    An excluded edition is not examined and carries no declaration forward: the
    exclusion is a decision about the edition itself, so a lift that would only
    have been reachable through it is not planned either.
    """
    plan = ModeloPlan(modelo=modelo_dir.name)
    for edition_dir in _edition_dirs(modelo_dir):
        if edition_dir.name in excluded:
            plan.exclusions.append((edition_dir.name, excluded[edition_dir.name]))
            continue
        for family in families:
            decision = plan_edition(modelo_dir.name, edition_dir, family)
            if decision is not None:
                plan.lifts.append(decision)

    successors = _successor_editions(modelo_dir)
    loaded: dict[str, Any] = {}
    carried: dict[tuple[str, str], EditionLift] = {}
    refused_families: set[str] = set()
    for index, lift in enumerate(list(plan.lifts)):
        if not lift.liftable or lift.family not in _MEMBER_REWRITE_FAMILIES:
            continue
        declarations, refusal = _forward_closure(modelo_dir, lift, successors, loaded)
        if refusal:
            refused_families.add(lift.family)
            plan.lifts[index] = EditionLift(
                modelo=lift.modelo,
                edition=lift.edition,
                family=lift.family,
                refusal=refusal,
                members=lift.members,
            )
            continue
        for declaration in declarations:
            carried.setdefault((declaration.edition, declaration.family), declaration)

    # A carried declaration only makes sense beside the lift that needs it, and
    # apply_plan is per modelo, so a family with any refusal contributes none.
    stated = {(lift.edition, lift.family) for lift in plan.lifts}
    plan.lifts.extend(
        declaration
        for identity, declaration in sorted(carried.items())
        if identity not in stated and declaration.family not in refused_families and declaration.edition not in excluded
    )
    return plan


def lifted_fragment_text(text: str, edition_id: str, family: str, default: tuple[str, ...]) -> str:
    """Return one fragment's text with ``default`` lifted out of this family's member statements.

    Both the one-line and the multi-line array spellings are read through the
    same span reader and rewritten by the same rule, and a rewritten statement is
    written back in this module's one-line spelling at the opening line's own
    indentation. Only a member's OWN top-level ``source_refs`` is touched: the rewrite starts
    at an ``[[revisions.<edition>.<family>]]`` header and stops at the next
    table header, so a nested provider table stating its own references, and
    every other family sharing the file, are left exactly as authored.
    """
    if not default:
        return text
    lines = text.splitlines()
    rendered: list[str] = []
    in_member = False
    index = 0
    while index < len(lines):
        line = lines[index]
        header = _ARRAY_TABLE_HEADER.match(line)
        if line.startswith("["):
            in_member = header is not None and header.group("family") == family and _header_id(header) == edition_id
            rendered.append(line)
            index += 1
            continue
        span = _refs_span(lines, index) if in_member and _SOURCE_REFS_OPENING.match(line) else None
        if span is None:
            rendered.append(line)
            index += 1
            continue
        index = span.last + 1
        if span.items == default:
            continue
        if span.items[: len(default)] == default:
            rendered.append(span.indent + _render_refs("additional_source_refs", span.items[len(default) :]))
            continue
        rendered.extend(lines[span.first : span.last + 1])
    return "\n".join(rendered) + ("\n" if text.endswith("\n") else "")


#: Written above a carried declaration so the manifest itself says the value is
#: the predecessor's rather than this edition's own grounding. A comment and not
#: a schema key: the fact is provenance for a reader and a prompt for a later
#: authoring pass, and a new field would oblige every consumer of
#: ``ModeloRevision`` to carry it.
_CARRIED_COMMENT: Final = (
    '# {key}: carried from predecessor edition "{predecessor}"; not re-grounded on this edition\'s own design'
)


def _manifest_with_default(
    text: str, edition_id: str, key: str, refs: tuple[str, ...], *, carried_from: str = ""
) -> str:
    """Return a manifest declaring ``key``, placed beside ``casilla_source_refs``.

    Beside rather than at the top of the table, because the three keys are one
    statement of the edition's grounding and a reader should find them together.
    An edition declaring no casilla default takes the line directly under its
    table header, which is the same place the first of the three would sit.
    """
    header = re.compile(rf"""^\[revisions\.(?:"{re.escape(edition_id)}"|{re.escape(edition_id)})\]\s*$""")
    casilla = re.compile(r"""^casilla_source_refs\s*=\s*\[[^\]]*\]\s*$""")
    lines = text.splitlines()
    anchor = table = None
    for index, line in enumerate(lines):
        if header.match(line):
            table = index
        elif table is not None and line.startswith("["):
            break
        elif table is not None and casilla.match(line):
            anchor = index
    if table is None:
        raise RuntimeError(f"no [revisions.{edition_id}] table to declare {key} on")
    declaration = [_render_refs(key, refs)]
    if carried_from:
        declaration.insert(0, _CARRIED_COMMENT.format(key=key, predecessor=carried_from))
    at = (anchor if anchor is not None else table) + 1
    lines[at:at] = declaration
    return "\n".join(lines) + "\n"


class CapViolationError(Exception):
    """A value the lift would write does not satisfy the schema's own cap."""

    def __init__(self, edition: str, family: str, reason: str) -> None:
        self.edition = edition
        self.family = family
        self.reason = reason
        super().__init__(f"{edition}/{family}: {reason}")


class ModeloLiftFailedError(Exception):
    """A modelo's lift did not survive its own validation and was rolled back."""

    def __init__(self, modelo: str, reason: str) -> None:
        """Record the modelo and the validation failure that rejected its lift."""
        super().__init__(f"modelo {modelo}: lift rolled back, {reason}")
        self.modelo = modelo
        self.reason = reason


def apply_plan(
    plan: ModeloPlan,
    modelos_root: Path = REGISTRY_MODELOS_ROOT,
    *,
    skip_recent_minutes: float = 0,
) -> list[Path]:
    """Write one modelo's lift, validating before the change is kept.

    Every edited file is re-parsed and the modelo is compiled through the
    loader; either failing restores the original bytes and raises, so a modelo
    is never left half-lifted.

    The compile check is a COMPARISON rather than an absolute gate, because a
    modelo can already be failing for a reason that is not this tool's: the
    corpus is edited by several hands, and a modelo carrying someone else's
    in-flight defect would otherwise be permanently unliftable. The load is
    therefore taken before the write as well, and the lift is kept when the
    modelo afterwards fails in exactly the way it already failed. A modelo that
    loaded before and does not load after is always rolled back, and a modelo
    whose failure CHANGES is rolled back too, since a changed failure is the
    tool's own.

    Raises:
        ModeloLiftFailedError: When the written tree does not re-parse, or the
            modelo's load outcome is worse than it was before the write. The
            tree is restored first.
    """
    modelo_dir = modelos_root / plan.modelo
    liftable = []
    for lift in plan.liftable:
        # A lift is withheld WHOLE when any file it would write is under a live
        # edit. Skipping one file of a lift and writing the rest is the one
        # outcome that must not happen: members stripped without their manifest
        # declaration materialise with no grounding at all.
        recent = _recently_modified(_lift_write_targets(modelo_dir, lift), skip_recent_minutes)
        if recent:
            plan.skipped.append((lift, recent))
            continue
        liftable.append(lift)
    if not liftable:
        return []
    baseline = load_outcome(modelo_dir)
    original: dict[Path, str] = {}
    touched: list[Path] = []

    def remember(path: Path) -> str:
        text = path.read_text(encoding="utf-8")
        original.setdefault(path, text)
        return text

    try:
        # Every capped value goes through its owning typed field before the
        # first byte is written, so an over-cap value refuses rather than
        # surviving a write and being undone by the rollback path. It sits
        # inside the guarded region so that it answers to the same error
        # contract as every other failure here: a caller sees
        # ModeloLiftFailedError and a tree restored to the bytes it had,
        # never a raw parse error escaping from a half-checked plan.
        styles: dict[Path, str] = {}
        for lift in liftable:
            refusal = _cap_refusal(modelo_dir / _REVISIONS / lift.edition, lift)
            if refusal:
                raise CapViolationError(lift.edition, lift.family, refusal)

        for lift in liftable:
            edition_dir = modelo_dir / _REVISIONS / lift.edition
            if lift.family in _MEMBER_REWRITE_FAMILIES:
                for fragment in lift.fragments:
                    text = remember(fragment)
                    rewritten = lifted_fragment_text(text, lift.edition, lift.family, lift.default)
                    if rewritten != text:
                        styles[fragment] = _write(fragment, rewritten)
                        touched.append(fragment)
            if lift.manifest_declared:
                continue
            manifest = edition_dir / _MANIFEST
            declared = _manifest_with_default(
                remember(manifest),
                lift.edition,
                FAMILY_DEFAULT_KEY[lift.family],
                lift.default,
                carried_from=lift.inherited_from,
            )
            styles[manifest] = _write(manifest, declared)
            if manifest not in touched:
                touched.append(manifest)
        for path in touched:
            verify_written(path, styles[path])
        after = load_outcome(modelo_dir)
        if after != baseline:
            raise RegistryLoadRegressionError(baseline, after)
    except Exception as exc:
        for path, text in original.items():
            _write(path, text)
        raise ModeloLiftFailedError(plan.modelo, f"{type(exc).__name__}: {exc}") from exc
    return touched


def load_outcome(modelo_dir: Path) -> str:
    """Compile the modelo through the owning loader and return its outcome as a comparable identity.

    ``"loads"`` when it compiles, and the failure's type and message otherwise.
    The message carries the failing revision and field, so two runs comparing
    equal really did fail the same way rather than merely both failing.
    """
    from .compiler.loader import load_modelo_directory

    try:
        load_modelo_directory(modelo_dir)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return "loads"


class RegistryLoadRegressionError(Exception):
    """The written tree loads worse than the tree the lift started from."""

    def __init__(self, baseline: str, after: str) -> None:
        """Record the load outcome before and after the write."""
        super().__init__(f"load outcome changed from {baseline!r} to {after!r}")
        self.baseline = baseline
        self.after = after


def _written_editions(paths: Sequence[Path]) -> dict[str, int]:
    """Count written files per edition, read off each path's own revisions segment."""
    counted: dict[str, int] = {}
    for path in paths:
        parts = path.parts
        if _REVISIONS not in parts:
            continue
        edition = parts[parts.index(_REVISIONS) + 1]
        counted[edition] = counted.get(edition, 0) + 1
    return dict(sorted(counted.items()))


def render_plan(
    plans: Sequence[ModeloPlan],
    *,
    applied: bool,
    written: Mapping[str, Sequence[Path]] | None = None,
    withheld_modelos: Sequence[Exclusion] = (),
) -> str:
    """Render every plan as diffable lines.

    ``written`` carries the paths ``apply_plan`` actually wrote, keyed by
    modelo. A planned lift and a written file are different facts -- a lift
    whose members already state the default rewrites nothing, and a lift the
    loader gate rolled back writes nothing at all -- so the applied total
    counts the files, and reports them per edition. Without it the total
    counts the plan, which is the only thing a dry run has.
    """
    lines: list[str] = []
    liftable = 0
    excluded = len(withheld_modelos)
    lines.extend(item.render() for item in withheld_modelos)
    per_family: dict[str, int] = {}
    for plan in plans:
        for edition, reason in plan.exclusions:
            excluded += 1
            lines.append(f"excluded: {plan.modelo}/{edition} reason={reason}")
        for lift in plan.lifts:
            if lift.liftable:
                liftable += 1
                per_family[lift.family] = per_family.get(lift.family, 0) + 1
                manifest = "declared" if lift.manifest_declared else "write"
                carried = f" inherited_from={lift.inherited_from}" if lift.inherited_from else ""
                lines.append(
                    f"lift modelo={plan.modelo} edition={lift.edition} family={lift.family} "
                    f"members={lift.members} default={list(lift.default)} manifest={manifest}{carried}"
                )
            else:
                lines.append(
                    f"refuse modelo={plan.modelo} edition={lift.edition} family={lift.family} "
                    f"members={lift.members} reason={lift.refusal}"
                )
        for edition, (keys, inherited_from) in plan.manifests.items():
            carried = f" inherited_from={inherited_from}" if inherited_from else ""
            lines.append(f"manifest {plan.modelo}/{edition} fields={','.join(keys)}{carried}")
        for lift, recent in plan.skipped:
            for path, age in recent:
                lines.append(
                    f"skip modelo={plan.modelo} edition={lift.edition} family={lift.family} "
                    f"path={path.as_posix()} age_minutes={age:.1f}"
                )
        if written is not None:
            for edition, count in _written_editions(written.get(plan.modelo, ())).items():
                lines.append(f"wrote modelo={plan.modelo} edition={edition} files={count}")
    refusals = sum(len(plan.refusals) for plan in plans)
    breakdown = " ".join(f"{family}={per_family[family]}" for family in FAMILIES if per_family.get(family))
    excluded_total = f" excluded={excluded}" if excluded else ""
    if written is not None:
        total = sum(len(paths) for paths in written.values())
        lines.append(f"total applied={total} {breakdown} refusals={refusals}{excluded_total}".replace("  ", " "))
        return "\n".join(lines)
    lines.append(
        (
            f"total {'applied' if applied else 'planned'}={liftable} {breakdown} refusals={refusals}{excluded_total}"
        ).replace("  ", " ")
    )
    return "\n".join(lines)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--modelo", help="Lift one modelo by id.")
    scope.add_argument("--all", action="store_true", help="Lift every modelo in the corpus.")
    parser.add_argument(
        "--family",
        action="append",
        choices=FAMILIES,
        help="Restrict to one family; repeatable. Defaults to every family.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report the plan and write nothing (the default).")
    parser.add_argument("--apply", action="store_true", help="Write the lift.")
    parser.add_argument("--report", type=Path, help="Write the rendered report to this path as well as to stdout.")
    parser.add_argument(
        "--skip-recent-minutes",
        type=float,
        default=0,
        metavar="N",
        help=(
            "Withhold any lift whose files were modified within N minutes, so a live edit by "
            "another writer is never written over. 0, the default, is off."
        ),
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="MODELO",
        help="Withhold a whole modelo from the run; repeatable.",
    )
    parser.add_argument(
        "--exclusions-file",
        type=Path,
        default=None,
        help=(
            "A file of exclusions, one '<modelo>' or '<modelo>/<edition>' per line. A '#' "
            "comment states the reason for the entries that follow it."
        ),
    )
    parser.add_argument(
        "--exclude-edition",
        action="append",
        default=[],
        metavar="MODELO/EDITION",
        help=(
            "Withhold one edition from the run, named as '<modelo>/<edition>'; repeatable. "
            "An excluded edition is never examined: it plans nothing, refuses nothing and "
            "carries no declaration forward, and is listed in the report with its reason."
        ),
    )
    parser.add_argument(
        "--exclude-reason",
        default=DEFAULT_EXCLUSION_REASON,
        metavar="TEXT",
        help="The reason reported for every exclusion of this run.",
    )
    parser.add_argument(
        "--modelos-root", type=Path, default=REGISTRY_MODELOS_ROOT, help="The corpus root to read and write."
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Plan, and optionally apply, the family source-default lift."""
    args = _parse_args(argv)
    if args.apply and args.dry_run:
        print("--apply and --dry-run contradict each other", file=sys.stderr)
        return 2
    families = tuple(dict.fromkeys(args.family)) if args.family else FAMILIES
    root = args.modelos_root
    directories = iter_modelo_dirs(root) if args.all else [root / str(args.modelo)]
    if not all(directory.is_dir() for directory in directories):
        print(f"no such modelo directory: {directories[0]}", file=sys.stderr)
        return 2

    try:
        exclusions = collect_exclusions(
            modelos=args.exclude,
            editions=args.exclude_edition,
            reason=args.exclude_reason,
            path=args.exclusions_file,
        )
    except MalformedExclusionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    plans = [
        plan_modelo(directory, families, excluded=excluded_editions(exclusions, directory.name))
        for directory in directories
        if not exclusions.excludes_modelo(directory.name)
    ]
    withheld = [item for item in exclusions.exclusions if not item.edition]
    failures: list[str] = []
    written: dict[str, Sequence[Path]] = {}
    if args.apply:
        for plan in plans:
            try:
                written[plan.modelo] = apply_plan(plan, root, skip_recent_minutes=args.skip_recent_minutes)
            except ModeloLiftFailedError as exc:
                written[plan.modelo] = ()
                failures.append(str(exc))
                plan.lifts = [
                    EditionLift(
                        modelo=lift.modelo,
                        edition=lift.edition,
                        family=lift.family,
                        refusal=exc.reason if lift.liftable else lift.refusal,
                        members=lift.members,
                    )
                    for lift in plan.lifts
                ]
    rendered = render_plan(
        plans, applied=args.apply, written=written if args.apply else None, withheld_modelos=tuple(withheld)
    )
    print(rendered)
    for failure in failures:
        print(failure, file=sys.stderr)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
