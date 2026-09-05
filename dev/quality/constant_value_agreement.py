"""Screen: constants whose name carries more than one value.

The name-collision census asks whether one word names two behaviours. This asks
the same question of data, where the failure is quieter. A reader who greps a
constant and finds two definitions with the same value learns nothing alarming.
A reader who finds two definitions with *different* values has to work out
which one the code in front of them reached, and nothing in the name helps.

Two conditions are reported and the distinction between them is the whole point:

- ``value_conflict`` - one name, more than one value. A grep for this name
  returns two different truths.
- ``value_agreement`` - one name, one value, several modules. Repetition rather
  than ambiguity. Sometimes worth collapsing and sometimes deliberate, so it is
  reported without judgement.
- ``stem_restatement`` - one value under two DIFFERENT names whose stems are
  related, one being a tail of the other once leading underscores are stripped.
  Keying on the name alone cannot see this, and it is the quieter half of the
  same defect: a canonical constant restated as a local literal under a
  decorated name drifts the moment the canonical value moves, and no grep for
  either name returns the other.

Visibility is carried on every row because it decides how far the damage
reaches. A module-private constant is scoped by the underscore that names it:
it cannot be imported, so two modules holding different values under one
private name are two local facts that never meet. A *public* name carrying two
values is a different matter, because a consumer choosing an import has no
signal that the choice changes the value.

Only literals are COMPARED. A constant built by a call or a comprehension has
no value this screen can compare, and guessing at one would be worse than
declining. Booleans are skipped: ``True`` under one name in two modules is not
evidence of anything.

But declining to compare a value is not a reason to ignore the name. A third
condition covers the constants whose values are unevaluable:

- ``derived_name_collision`` - the same, but every site builds the value from
  an imported authority rather than from literals. ``SEDE_BASE =
  EXTERNAL.aeat.domains.www6`` in four sede modules is four local bindings of
  one canonical value: they read the same source, so they cannot drift, and
  that is the pattern working rather than failing. Reported separately so it
  does not crowd out the kind that can.
- ``unevaluated_name_collision`` - one name defined in several modules, at
  least one of them by a call or comprehension. The screen reports the
  collision and says nothing about agreement, because it cannot know. This is
  where the quiet duplicates live: three registry modules each defined
  ``_NUMERIC_TUPLE_ADAPTER`` as a ``TypeAdapter(...)`` call, two of those
  copies were dead, and no literal-only census could see any of them.

The screen exits 0 whatever it finds. The public-visibility invariant it
protects is gated separately.
"""

from __future__ import annotations

import argparse
import ast
import collections
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "ConstantFinding",
    "collect_constants",
    "collect_unevaluated_constants",
    "constant_census",
    "stem_restatements",
    "unevaluated_collisions",
]

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent / "src" / "cadrumo"
_COMPARABLE = (str, int, float, tuple, frozenset)


@dataclass(frozen=True, slots=True)
class ConstantFinding:
    """One constant name defined in more than one module."""

    name: str
    kind: str
    public: bool
    sites: tuple[tuple[str, str], ...]

    @property
    def detail(self) -> str:
        """A one-line rendering of every module claiming this name and its value."""
        return " | ".join(f"{module}={value}" for module, value in self.sites)


def _assigned_name(node: ast.stmt) -> str | None:
    """Return the constant name a module-level statement binds, if it binds one."""
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
        return node.target.id
    return None


def collect_constants(root: Path) -> dict[str, dict[str, str]]:
    """Return every module-level literal constant, keyed by name then by module."""
    found: dict[str, dict[str, str]] = collections.defaultdict(dict)
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        module = path.relative_to(root).as_posix()
        for node in tree.body:
            name = _assigned_name(node)
            if name is None or not name.lstrip("_").isupper():
                continue
            try:
                value = ast.literal_eval(node.value)  # type: ignore[arg-type]
            except (ValueError, TypeError, SyntaxError):
                continue
            if isinstance(value, bool) or not isinstance(value, _COMPARABLE):
                continue
            found[name][module] = repr(value)
    return dict(found)


def collect_unevaluated_constants(root: Path) -> dict[str, dict[str, str]]:
    """Return module-level constants whose value the screen cannot evaluate.

    Keyed by name then module, with the unparsed source expression as the
    value. The expression is recorded for the reader, never compared: two
    ``TypeAdapter(...)`` calls that differ textually may still mean the same
    thing, and two that match textually may resolve differently.
    """
    found: dict[str, dict[str, str]] = collections.defaultdict(dict)
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        module = path.relative_to(root).as_posix()
        for node in tree.body:
            name = _assigned_name(node)
            if name is None or (not name.lstrip("_").isupper() and not name.startswith("_")):
                continue
            if not name.lstrip("_")[:1].isalpha():
                continue
            value = getattr(node, "value", None)
            if value is None:
                continue
            try:
                ast.literal_eval(value)
            except (ValueError, TypeError, SyntaxError):
                found[name][module] = ast.unparse(value).splitlines()[0][:60]
    return dict(found)


def _is_literal_construction(expression: str) -> bool:
    """Report whether an expression builds its value rather than reading one.

    This is the whole difference between a duplicate that can drift and one
    that cannot, and the test is simply whether any literal appears.

    An expression made only of names and attributes reads a value that lives
    somewhere else -- ``EXTERNAL.aeat.domains.www6``,
    ``storage_location(StorageCategory.BUCKETS).subpath`` -- so every copy
    resolves to whatever that source says and no edit can leave one stale.

    The moment a literal appears, the value is written down here:
    ``frozenset('0123456789abcdef')``, ``re.compile('[^a-z0-9]+')``,
    ``TypeAdapter(tuple[int | float, ...])``. A second copy is then a second
    source of truth, and changing one leaves the other behind. That holds for
    a bare ``...`` or ``True`` as much as for a string, which is why the rule
    is stated over literals rather than over a list of known constructors -- a
    list would have to be maintained, and mistaking a constructor for an
    authority hides real drift.
    """
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError:
        return False
    return any(isinstance(node, ast.Constant) for node in ast.walk(parsed))


def unevaluated_collisions(constants: dict[str, dict[str, str]]) -> tuple[ConstantFinding, ...]:
    """Report unevaluable constant names several modules bind IDENTICALLY.

    Two filters keep this honest rather than loud. An expression mentioning
    ``__name__`` is per-module by construction -- a module logger is the
    correct idiom, and eighty of these were exactly that -- so it is not a
    collision however many modules hold it. And the surviving expressions must
    match textually: ``build_playwright_stage_runner('GROI')`` beside
    ``build_playwright_stage_runner('NIF-IVA')`` is two configured instances of
    one helper, which is reuse working, not a redeclaration.
    """
    findings: list[ConstantFinding] = []
    for name, sites in sorted(constants.items()):
        sites = {module: text for module, text in sites.items() if "__name__" not in text}
        if len(sites) < 2 or len(set(sites.values())) != 1:
            continue
        kind = (
            "unevaluated_name_collision"
            if _is_literal_construction(next(iter(sites.values())))
            else "derived_name_collision"
        )
        findings.append(
            ConstantFinding(
                name=name,
                kind=kind,
                public=not name.startswith("_"),
                sites=tuple(sorted(sites.items())),
            )
        )
    return tuple(findings)


def constant_census(constants: dict[str, dict[str, str]]) -> tuple[ConstantFinding, ...]:
    """Classify every constant name that more than one module defines."""
    findings: list[ConstantFinding] = []
    for name, sites in sorted(constants.items()):
        if len(sites) < 2:
            continue
        kind = "value_conflict" if len(set(sites.values())) > 1 else "value_agreement"
        findings.append(
            ConstantFinding(
                name=name,
                kind=kind,
                public=not name.startswith("_"),
                sites=tuple(sorted(sites.items())),
            )
        )
    return tuple(findings)


def _stem(name: str) -> str:
    """Return a constant name without the underscores that only scope it."""
    return name.lstrip("_")


def _is_restatement_of(longer: str, shorter: str) -> bool:
    """Report whether ``longer`` reads as a decorated spelling of ``shorter``.

    The shorter stem must carry at least two segments. A single segment such as
    ``BYTES`` or ``SIZE`` is a unit, not a concept, and pairing on one would
    report every length in the tree against every other.
    """
    if shorter.count("_") < 1:
        return False
    if shorter.endswith("_VERSION"):
        # A version is a sequence number each schema owns independently, so two
        # of them agreeing at 1 is where they both started, not one restating
        # the other. Pairing on it reported fifteen rows and none was a defect.
        return False
    return longer.endswith(f"_{shorter}")


def stem_restatements(constants: dict[str, dict[str, str]]) -> tuple[ConstantFinding, ...]:
    """Group constants that share a value and whose names share a stem.

    Candidates are grouped by VALUE first, so the name comparison only ever runs
    within a set already known to agree. Comparing every name against every
    other would be quadratic in the whole census for no added detection.
    """
    by_value: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    for name, sites in constants.items():
        for module, value in sites.items():
            by_value[value].append((name, module))

    findings: list[ConstantFinding] = []
    for value, entries in sorted(by_value.items()):
        for index, (name, module) in enumerate(sorted(entries)):
            for other_name, other_module in sorted(entries)[index + 1 :]:
                if name == other_name or module == other_module:
                    continue
                left, right = _stem(name), _stem(other_name)
                if not (_is_restatement_of(left, right) or _is_restatement_of(right, left)):
                    continue
                findings.append(
                    ConstantFinding(
                        name=f"{name}~{other_name}",
                        kind="stem_restatement",
                        public=not (name.startswith("_") or other_name.startswith("_")),
                        sites=((module, value), (other_module, value)),
                    )
                )
    return tuple(findings)


def main(argv: list[str] | None = None) -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--kind", action="append", help="report only these kinds (repeatable)")
    parser.add_argument("--public-only", action="store_true", help="report only public names")
    args = parser.parse_args(argv)

    constants = collect_constants(_PACKAGE_ROOT)
    findings = (
        constant_census(constants)
        + stem_restatements(constants)
        + unevaluated_collisions(collect_unevaluated_constants(_PACKAGE_ROOT))
    )
    wanted = set(args.kind) if args.kind else None
    tally: collections.Counter[str] = collections.Counter(item.kind for item in findings)
    public_conflicts = sum(1 for item in findings if item.kind == "value_conflict" and item.public)
    for finding in findings:
        if wanted is not None and finding.kind not in wanted:
            continue
        if args.public_only and not finding.public:
            continue
        visibility = "public" if finding.public else "private"
        sys.stdout.write(
            f"constant name={finding.name} kind={finding.kind} visibility={visibility} sites={finding.detail}\n"
        )
    kinds = " ".join(f"{kind}={count}" for kind, count in sorted(tally.items()))
    sys.stdout.write(f"summary constants={len(findings)} {kinds} public_value_conflicts={public_conflicts}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
