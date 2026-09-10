"""The predecessor forest rule over one modelo's editions.

An edition is authored relative to a sibling edition only when its manifest
names one. The declared edges must form trees: every named target is another
edition of the same modelo, no chain of edges returns to where it started, and
so every edition walks up its edges to a root. A root is an edition that
declares, with grounding, that no earlier sibling exists, or the one edition
that omits the key altogether.

The key-less edition is the dangerous root. A first edition and a successor
whose author forgot the key are shape-identical, so absence can identify a
first edition only while it is unique: a second edition omitting the key is a
second undeclared root and is refused naming every such edition. Editions that
each declare no predecessor are a legal parallel set, such as scheme variants
sharing one validity date; the rule accepts any number of them and invents no
order between them.

Reachability is not a separate check. Once every named target resolves and no
cycle exists, each edition's single upward chain ends at an edition that names
no sibling, which is a root by definition; an edition cut off from every root
can only sit on a cycle, and the cycle refusal names it.

Where it stops:

- The rule binds a modelo once any of its editions declares the key, in either
  form. A modelo none of whose editions declares it is in the full-copy format,
  where every edition states every row itself and inherits nothing; each such
  edition is its own key-less root and the modelo loads unchanged. A forgotten
  key there is invisible to this rule, because nothing distinguishes it from a
  full-copy edition until a sibling opts into declaring.
- The rule reads declarations only. It does not check that a declared
  predecessor agrees with the editions' validity dates, that the successor's
  authority grade permits inheriting, or that a no-predecessor claim's
  references resolve against the legal and source catalogues.
- A newly authored successor that declares its predecessor correctly but
  inherits a row its author meant to drop passes this rule; only an authored
  retirement or a comparison against the official form can say otherwise.

The input is the three declaration states projected to plain edition ids, so
the typed modelo validator and any caller holding raw, not yet typed manifests
apply the same rule.
"""

from __future__ import annotations

from collections.abc import Mapping

from .errors import RegistryValidationError

__all__ = ("validate_predecessor_forest",)


def validate_predecessor_forest(
    modelo_id: str,
    *,
    named: Mapping[str, str],
    declared_roots: frozenset[str],
    keyless: frozenset[str],
) -> None:
    """Refuse a modelo whose declared predecessor edges do not form a forest.

    ``named`` maps each edition that names a sibling to that sibling's id;
    ``declared_roots`` holds the editions declaring that no predecessor exists;
    ``keyless`` holds the editions omitting the key. Together they must cover
    each edition exactly once.

    Raises:
        RegistryValidationError: When an edition carries more than one
            declaration state, more than one edition omits the key in a modelo
            that declares it anywhere, a named target is the edition itself or
            no edition of the modelo, or the named edges form a cycle.
    """
    _require_one_state_per_edition(modelo_id, named=named, declared_roots=declared_roots, keyless=keyless)
    if not named and not declared_roots:
        return
    if len(keyless) > 1:
        omitting = " and ".join(repr(edition) for edition in sorted(keyless))
        raise RegistryValidationError(
            f"modelo {modelo_id!r} has {len(keyless)} editions omitting the predecessor key: {omitting}; "
            "absence identifies a first edition only while one edition omits it, so every other edition "
            "must name its predecessor or declare that none exists",
        )
    editions = frozenset(named) | declared_roots | keyless
    for edition, target in sorted(named.items()):
        if target == edition:
            raise RegistryValidationError(
                f"modelo {modelo_id!r} revision {edition!r} declares itself as its own predecessor",
            )
        if target not in editions:
            raise RegistryValidationError(
                f"modelo {modelo_id!r} revision {edition!r} declares predecessor {target!r}, "
                f"which is not a revision of this modelo; declared revisions are {sorted(editions)!r}",
            )
    _refuse_cycles(modelo_id, named)


def _require_one_state_per_edition(
    modelo_id: str,
    *,
    named: Mapping[str, str],
    declared_roots: frozenset[str],
    keyless: frozenset[str],
) -> None:
    overlap = (frozenset(named) & declared_roots) | (frozenset(named) & keyless) | (declared_roots & keyless)
    if overlap:
        raise RegistryValidationError(
            f"modelo {modelo_id!r} editions {sorted(overlap)!r} carry more than one predecessor declaration state",
        )


def _refuse_cycles(modelo_id: str, named: Mapping[str, str]) -> None:
    """Walk each edition up its named edges and refuse the first cycle met.

    ``settled`` holds editions already proven to reach a root, so every edition
    is walked once across the whole modelo.
    """
    settled: set[str] = set()
    for start in sorted(named):
        path: list[str] = []
        on_path: set[str] = set()
        current = start
        while current in named and current not in settled:
            if current in on_path:
                cycle = [*path[path.index(current) :], current]
                chain = " -> ".join(repr(edition) for edition in cycle)
                raise RegistryValidationError(
                    f"modelo {modelo_id!r} predecessor declarations form a cycle {chain}; "
                    "no edition on it is reachable from a root",
                )
            path.append(current)
            on_path.add(current)
            current = named[current]
        settled.update(path)
