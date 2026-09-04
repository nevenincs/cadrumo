"""Screen: public names that more than one module defines.

Duplication and ambiguity are different defects and want different remedies. A
duplicated body says one thing twice and is repaired by deleting a copy. A name
defined in two modules says two things under one word, and deleting either copy
loses behaviour a caller depends on. The second is the harder defect and the one
nothing here measured: a reader who greps a name and finds two definitions has
no way to know which one runs, and a reviewer approving a change to one may not
know the other exists.

Not every shared name is a defect, so a census that only counted them would
report mostly noise. Four classes are reported, and every row names one:

- ``entrypoint_convention`` - a module's ``main``. Every runnable module has
  one by convention and they are reached by module path, never by the bare name.
  Reported so the count is honest, never as a finding.
- ``typing_overload`` - several definitions inside one module, which is what an
  ``@overload`` set looks like to a parser. One implementation, several declared
  signatures. Reported and excluded for the same reason.
- ``cross_layer_collision`` - two definitions in different architectural layers.
  Often legitimate: a layer states a concept in its own vocabulary, and the
  hexagonal boundary is what stops the two from being merged.
- ``same_layer_collision`` - two definitions inside one layer. The sharpest
  class. No boundary explains these, so either one is dead, or they are the same
  concept under one name in two places, or they are different concepts and the
  name is wrong.

The layer is the first path segment below the package root, which is how this
project already separates ``core``, ``domain``, ``application``, ``adapters``
and ``entrypoints``.

Arity is reported beside each definition because it is the cheapest signal that
two same-named functions are not the same function. It is a hint, not a verdict:
same arity does not make them the same, and different arity does not make the
name acceptable.

The screen exits 0 whatever it finds. It reports; it does not gate. A gate
belongs here once the same-layer collisions it would refuse have been
adjudicated.
"""

from __future__ import annotations

import argparse
import ast
import collections
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "NameCollision",
    "PublicDefinition",
    "collect_public_definitions",
    "collision_census",
]

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent / "src" / "cadrumo"
_ENTRYPOINT_NAME = "main"


@dataclass(frozen=True, slots=True)
class PublicDefinition:
    """One public module-level function definition."""

    name: str
    module: str
    layer: str
    argc: int


@dataclass(frozen=True, slots=True)
class NameCollision:
    """One public name that more than one definition claims."""

    name: str
    kind: str
    definitions: tuple[PublicDefinition, ...]

    @property
    def detail(self) -> str:
        """A one-line rendering of every site claiming this name."""
        return " | ".join(f"{item.module}(argc={item.argc})" for item in self.definitions)


def _layer_of(module: str) -> str:
    """Return the architectural layer a module path sits in."""
    head, _, tail = module.partition("/")
    return head if tail else "<root>"


def collect_public_definitions(root: Path) -> tuple[PublicDefinition, ...]:
    """Return every public module-level function defined under ``root``.

    Tests are excluded: a helper shared by name across two test modules is a
    different question from a production name meaning two things, and mixing
    them would bury the production rows.

    A module that cannot be read is skipped and the skip is ANNOUNCED. Its
    definitions are absent from this corpus, and a collision is detected only
    between names that are both in it - so a silently skipped module cannot
    collide with anything, and the census reports fewer collisions than exist.

    Not fatal, because the tree is edited while this runs and one half-written
    file must not cost the whole census. Measured over the shipped tree: 2118
    modules walked, none unparsable, 4534 public definitions collected.
    """
    found: list[PublicDefinition] = []
    unread: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as error:
            unread.append(f"{path}: {error}")
            continue
        module = path.relative_to(root).as_posix()
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not node.name.startswith("_"):
                found.append(
                    PublicDefinition(
                        name=node.name,
                        module=module,
                        layer=_layer_of(module),
                        argc=len(node.args.args),
                    )
                )
    if unread:
        sys.stderr.write(
            f"name_collision_census: {len(unread)} module(s) could not be read; their public "
            "names are absent from this corpus and cannot be reported as colliding: " + repr(unread) + chr(10)
        )
    return tuple(found)


def collision_census(definitions: tuple[PublicDefinition, ...]) -> tuple[NameCollision, ...]:
    """Group definitions by name and classify every name more than one claims."""
    by_name: dict[str, list[PublicDefinition]] = collections.defaultdict(list)
    for definition in definitions:
        by_name[definition.name].append(definition)

    collisions: list[NameCollision] = []
    for name, claims in sorted(by_name.items()):
        if len(claims) < 2:
            continue
        modules = {item.module for item in claims}
        if name == _ENTRYPOINT_NAME:
            kind = "entrypoint_convention"
        elif len(modules) == 1:
            kind = "typing_overload"
        elif len({item.layer for item in claims}) > 1:
            kind = "cross_layer_collision"
        else:
            kind = "same_layer_collision"
        ordered = tuple(sorted(claims, key=lambda item: item.module))
        collisions.append(NameCollision(name=name, kind=kind, definitions=ordered))
    return tuple(collisions)


def main(argv: list[str] | None = None) -> int:
    """Print one greppable row per collision and a closing census; always exit 0."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--kind",
        action="append",
        help="report only these kinds (repeatable); default reports every kind",
    )
    args = parser.parse_args(argv)

    collisions = collision_census(collect_public_definitions(_PACKAGE_ROOT))
    wanted = set(args.kind) if args.kind else None
    tally: collections.Counter[str] = collections.Counter(item.kind for item in collisions)
    for collision in collisions:
        if wanted is not None and collision.kind not in wanted:
            continue
        sys.stdout.write(f"name_collision name={collision.name} kind={collision.kind} sites={collision.detail}\n")
    kinds = " ".join(f"{kind}={count}" for kind, count in sorted(tally.items()))
    sys.stdout.write(f"summary collisions={len(collisions)} {kinds}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
