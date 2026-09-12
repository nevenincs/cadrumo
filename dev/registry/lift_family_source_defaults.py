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
- a member states ``source_refs`` the textual pass cannot reproduce exactly. The
  rewrite is textual, so a multi-line array or a spelling this module's line
  pattern does not match is refused for the WHOLE edition rather than partially
  applied. Four such members ship today, all in modelo 347's bindings.

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
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, cast

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
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from cadrumo.domain.calculations.registry.reference_sections import FAMILY_SOURCE_DEFAULT_FIELDS

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


def _write(path: Path, text: str) -> None:
    r"""Write a corpus file, keeping its line endings.

    ``newline`` is explicit rather than defaulted because the default
    translates every ``\\n`` to the platform separator, which on Windows
    rewrites a whole LF-authored fragment to CRLF and reports a change on every
    line of a file the run meant to touch on one. The corpus is LF throughout,
    and the rollback path below restores through this same function, so a
    translated write would make even a rolled-back run dirty the tree.
    """
    path.write_text(text, encoding="utf-8", newline="\n")


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

    @property
    def liftable(self) -> bool:
        """Whether this decision writes anything."""
        return bool(self.default) and not self.refusal


@dataclass
class ModeloPlan:
    """One modelo's lift decisions across every edition and family."""

    modelo: str
    lifts: list[EditionLift] = field(default_factory=list)

    @property
    def liftable(self) -> list[EditionLift]:
        """Every decision this plan would write."""
        return [lift for lift in self.lifts if lift.liftable]

    @property
    def refusals(self) -> list[EditionLift]:
        """Every decision this plan declines, with the reason."""
        return [lift for lift in self.lifts if lift.refusal]

    @property
    def manifests(self) -> dict[str, tuple[str, ...]]:
        """The manifest fields this plan would write, keyed by edition."""
        written: dict[str, list[str]] = {}
        for lift in self.liftable:
            if lift.manifest_declared:
                continue
            written.setdefault(lift.edition, []).append(FAMILY_DEFAULT_KEY[lift.family])
        return {edition: tuple(sorted(keys)) for edition, keys in sorted(written.items())}


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
        for line in path.read_text(encoding="utf-8").splitlines():
            header = _ARRAY_TABLE_HEADER.match(line)
            if line.startswith("["):
                in_member = header is not None and header.group("family") == family and _header_id(header) == edition_id
                continue
            if in_member and _SOURCE_REFS_OPENING.match(line) and not _SOURCE_REFS_LINE.match(line):
                found.append(f"{path.name}: {line.strip()}")
    return tuple(found)


def _header_id(header: re.Match[str]) -> str:
    return str(header.group("dq") or header.group("sq") or header.group("bare") or "")


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


def plan_modelo(modelo_dir: Path, families: Sequence[str] = FAMILIES) -> ModeloPlan:
    """Decide every edition and family of one modelo."""
    plan = ModeloPlan(modelo=modelo_dir.name)
    for edition_dir in _edition_dirs(modelo_dir):
        for family in families:
            decision = plan_edition(modelo_dir.name, edition_dir, family)
            if decision is not None:
                plan.lifts.append(decision)
    return plan


def lifted_fragment_text(text: str, edition_id: str, family: str, default: tuple[str, ...]) -> str:
    """Return one fragment's text with ``default`` lifted out of this family's member statements.

    Only a member's OWN top-level ``source_refs`` is touched: the rewrite starts
    at an ``[[revisions.<edition>.<family>]]`` header and stops at the next
    table header, so a nested provider table stating its own references, and
    every other family sharing the file, are left exactly as authored.
    """
    if not default:
        return text
    rendered: list[str] = []
    in_member = False
    for line in text.splitlines():
        header = _ARRAY_TABLE_HEADER.match(line)
        if line.startswith("["):
            in_member = header is not None and header.group("family") == family and _header_id(header) == edition_id
            rendered.append(line)
            continue
        match = _SOURCE_REFS_LINE.match(line) if in_member else None
        if match is None:
            rendered.append(line)
            continue
        items = _quoted_items(match.group("items"))
        if items == default:
            continue
        if items[: len(default)] == default:
            indent = match.group("indent")
            rendered.append(indent + _render_refs("additional_source_refs", items[len(default) :]))
            continue
        rendered.append(line)
    return "\n".join(rendered) + ("\n" if text.endswith("\n") else "")


def _manifest_with_default(text: str, edition_id: str, key: str, refs: tuple[str, ...]) -> str:
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
    lines.insert((anchor if anchor is not None else table) + 1, _render_refs(key, refs))
    return "\n".join(lines) + "\n"


class ModeloLiftFailedError(Exception):
    """A modelo's lift did not survive its own validation and was rolled back."""

    def __init__(self, modelo: str, reason: str) -> None:
        """Record the modelo and the validation failure that rejected its lift."""
        super().__init__(f"modelo {modelo}: lift rolled back, {reason}")
        self.modelo = modelo
        self.reason = reason


def apply_plan(plan: ModeloPlan, modelos_root: Path = REGISTRY_MODELOS_ROOT) -> list[Path]:
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
    liftable = plan.liftable
    if not liftable:
        return []
    modelo_dir = modelos_root / plan.modelo
    baseline = load_outcome(modelo_dir)
    original: dict[Path, str] = {}
    touched: list[Path] = []

    def remember(path: Path) -> str:
        text = path.read_text(encoding="utf-8")
        original.setdefault(path, text)
        return text

    try:
        for lift in liftable:
            edition_dir = modelo_dir / _REVISIONS / lift.edition
            if lift.family in _MEMBER_REWRITE_FAMILIES:
                for fragment in lift.fragments:
                    text = remember(fragment)
                    rewritten = lifted_fragment_text(text, lift.edition, lift.family, lift.default)
                    if rewritten != text:
                        _write(fragment, rewritten)
                        touched.append(fragment)
            if lift.manifest_declared:
                continue
            manifest = edition_dir / _MANIFEST
            declared = _manifest_with_default(
                remember(manifest), lift.edition, FAMILY_DEFAULT_KEY[lift.family], lift.default
            )
            _write(manifest, declared)
            if manifest not in touched:
                touched.append(manifest)
        for path in touched:
            tomllib.loads(path.read_text(encoding="utf-8"))
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
    per_family: dict[str, int] = {}
    for plan in plans:
        for lift in plan.lifts:
            if lift.liftable:
                liftable += 1
                per_family[lift.family] = per_family.get(lift.family, 0) + 1
                manifest = "declared" if lift.manifest_declared else "write"
                lines.append(
                    f"lift modelo={plan.modelo} edition={lift.edition} family={lift.family} "
                    f"members={lift.members} default={list(lift.default)} manifest={manifest}"
                )
            else:
                lines.append(
                    f"refuse modelo={plan.modelo} edition={lift.edition} family={lift.family} "
                    f"members={lift.members} reason={lift.refusal}"
                )
        for edition, keys in plan.manifests.items():
            lines.append(f"manifest {plan.modelo}/{edition} fields={','.join(keys)}")
        if written is not None:
            for edition, count in _written_editions(written.get(plan.modelo, ())).items():
                lines.append(f"wrote modelo={plan.modelo} edition={edition} files={count}")
    refusals = sum(len(plan.refusals) for plan in plans)
    breakdown = " ".join(f"{family}={per_family[family]}" for family in FAMILIES if per_family.get(family))
    if written is not None:
        total = sum(len(paths) for paths in written.values())
        lines.append(f"total applied={total} {breakdown} refusals={refusals}".replace("  ", " "))
        return "\n".join(lines)
    lines.append(
        f"total {'applied' if applied else 'planned'}={liftable} {breakdown} refusals={refusals}".replace("  ", " ")
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

    plans = [plan_modelo(directory, families) for directory in directories]
    failures: list[str] = []
    written: dict[str, Sequence[Path]] = {}
    if args.apply:
        for plan in plans:
            try:
                written[plan.modelo] = apply_plan(plan, root)
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
    rendered = render_plan(plans, applied=args.apply, written=written if args.apply else None)
    print(rendered)
    for failure in failures:
        print(failure, file=sys.stderr)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
