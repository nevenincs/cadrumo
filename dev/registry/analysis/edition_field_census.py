"""Screen: which fields actually exist on disk, per declaration family, across the corpus.

An existence audit, not a value or correctness check. Every registry fragment
under every edition is read and, for every declaration family the revision
model declares, the set of field paths its members carry is gathered. The
result says what the corpus is made of before anyone decides what a union of
editions should converge on: a field cannot be lifted, inherited, or made a
manifest default until it is known where it is present, where it is absent,
and whether the schema even knows it.

Sanitisation, because raw key paths are noise:

- **Depth cap.** A path is recorded to two levels: ``field`` and
  ``field.sub`` for a nested table, ``field[].sub`` for an array of tables.
  Anything deeper folds into its parent. Formula expressions are recursive
  trees whose depth is a property of the formula, not of the schema, and
  recording them raw produces dozens of paths that mean one thing.
- **Discriminated nests.** A nested table carrying ``kind`` is a union member,
  and its fields legitimately differ by kind. Its sub-fields are recorded as
  ``field[kind=<value>].sub`` and measured against the members of that kind
  only, so a field every ``previous_filing`` provider carries is converged
  rather than sparse across the whole family.
- **Classification against the schema.** Each top-level key is ``typed`` when
  the family's element model declares it, ``authoring`` when it is a known
  authoring-layer key the loader resolves before typing
  (``additional_source_refs``), and ``unknown`` otherwise. A nested path takes
  its top-level key's class; resolving nested typing generically through
  unions and annotations would be brittle, and the top-level answer is the
  one that decides whether a key is legal at all. A typed field no member
  carries is reported ``unused``.
- **Status by presence ratio** within the field's own denominator (the
  family's members, or the kind's members for a discriminated nest):
  ``converged`` at or above 98%, ``common`` at or above 50%, ``sparse``
  below 5%, ``outlier`` when carried by at most two modelos or below 0.5% of
  members, ``mixed`` otherwise.
- **Intra-modelo divergence.** Within one modelo, a field that some editions'
  members carry and other editions' members never do. The manifest's chain
  keys (``predecessor``, ``reviewed_against``) are excluded: a first edition
  lacks them by definition. Divergence is the
  question this lane exists to answer for the union: a field stated in one
  edition and absent from the next is either a real change or a restatement
  gap, and either way it is where inheritance will be decided.

Read from the authored TOML rather than the compiled authority, because the
question is what is written, and the authority normalises exactly the
differences this screen exists to see. The manifest's own scalar keys are
reported as the family ``manifest``.

The screen exits 0 whatever it finds. It reports; it does not gate.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any, Final

__all__ = [
    "CLASSES",
    "STATUSES",
    "FamilyCensus",
    "FieldCensus",
    "FieldDivergence",
    "Report",
    "build_report",
    "field_paths",
    "scan_registry",
    "signal_lines",
]

_MODELOS: Final = "modelos"
_REVISIONS: Final = "revisions"
_MANIFEST: Final = "revision.toml"
_MANIFEST_FAMILY: Final = "manifest"
_DISCRIMINATOR: Final = "kind"
_AUTHORING_ONLY_KEYS: Final = frozenset({"additional_source_refs"})
_DEPTH: Final = 2
#: Manifest keys whose presence is defined by position in the chain, not by authoring drift.
_CHAIN_POSITION_KEYS: Final = frozenset({"predecessor", "reviewed_against"})

CLASSES: Final[tuple[str, ...]] = ("typed", "authoring", "unknown")
STATUSES: Final[tuple[str, ...]] = ("converged", "common", "mixed", "sparse", "outlier")

#: Recorded when the schema could not be imported and classification degraded.
_LIMITATIONS: list[str] = []

_CONVERGED: Final = 0.98
_COMMON: Final = 0.50
_SPARSE: Final = 0.05
_OUTLIER_RATIO: Final = 0.005
_OUTLIER_MODELOS: Final = 2


@cache
def _schema_families() -> dict[str, frozenset[str]]:
    """Every collection family on the revision model with its element model's typed keys.

    Read off the shipped model so a family or field added to the schema is
    measured without editing this screen. A family whose element type is a
    union of models takes the union of their keys.
    """
    import typing

    try:
        from cadrumo.domain.calculations.registry.schema import ModeloRevision
    except Exception as exc:
        _LIMITATIONS.append(f"schema_unavailable: {type(exc).__name__}; every observed key classified typed")
        return {}

    families: dict[str, frozenset[str]] = {}
    manifest_keys: set[str] = set()
    for name, info in ModeloRevision.model_fields.items():
        args = typing.get_args(info.annotation)
        element = args[0] if args else None
        if element is None or typing.get_origin(info.annotation) is not tuple:
            manifest_keys.add(name)
            continue
        candidates = [element] if hasattr(element, "model_fields") else list(typing.get_args(element))
        keys = {key for candidate in candidates for key in getattr(candidate, "model_fields", {})}
        if keys:
            families[name] = frozenset(keys)
        else:
            manifest_keys.add(name)
    families[_MANIFEST_FAMILY] = frozenset(manifest_keys)
    return families


def _bundled_registry_root() -> Path:
    from cadrumo.core.resources.bundled_data import bundled_path

    return Path(bundled_path("registry", "aeat")).resolve()


def field_paths(member: dict[str, Any]) -> frozenset[str]:
    """Return the sanitised field paths one member carries.

    Two levels deep, arrays of tables as ``field[]``, and the sub-fields of a
    nested table carrying ``kind`` recorded under ``field[kind=<value>]``.
    """
    paths: set[str] = set()
    for key, value in member.items():
        paths.add(key)
        if isinstance(value, dict):
            prefix = f"{key}[kind={value[_DISCRIMINATOR]}]" if isinstance(value.get(_DISCRIMINATOR), str) else key
            if prefix != key:
                paths.add(prefix)
            paths.update(f"{prefix}.{sub}" for sub in value if sub != _DISCRIMINATOR or prefix == key)
        elif isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            paths.add(f"{key}[]")
            paths.update(f"{key}[].{sub}" for item in value for sub in item)
    return frozenset(paths)


@dataclass
class _Presence:
    members: int = 0
    editions: set[str] = field(default_factory=set)
    modelos: set[str] = field(default_factory=set)


@dataclass
class _FamilyAccumulator:
    members: int = 0
    editions: set[str] = field(default_factory=set)
    modelos: set[str] = field(default_factory=set)
    fields: dict[str, _Presence] = field(default_factory=lambda: defaultdict(_Presence))
    #: members per discriminated-nest prefix, the denominator for its sub-fields
    kinds: Counter[str] = field(default_factory=Counter)
    #: per modelo, per edition, per field: members carrying it and members total
    per_edition: dict[tuple[str, str], Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    per_edition_members: Counter[tuple[str, str]] = field(default_factory=Counter)


def _is_section(value: object) -> bool:
    """Whether a revision key holds declaration members (an array of tables) rather than a manifest value."""
    return isinstance(value, list) and any(isinstance(item, dict) for item in value)


def _read_sections(edition_dir: Path, edition_id: str) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    sections: dict[str, list[dict[str, Any]]] = defaultdict(list)
    manifest: dict[str, Any] = {}
    for path in sorted(edition_dir.rglob("*.toml")):
        table = tomllib.loads(path.read_text(encoding="utf-8")).get(_REVISIONS, {}).get(edition_id, {})
        if not isinstance(table, dict):
            continue
        if path.name == _MANIFEST and path.parent == edition_dir:
            manifest = {key: value for key, value in table.items() if not _is_section(value)}
        for key, value in table.items():
            if _is_section(value):
                sections[key].extend(item for item in value if isinstance(item, dict))
    return sections, manifest


def scan_registry(registry_root: Path, *, modelo_ids: tuple[str, ...] = ()) -> dict[str, _FamilyAccumulator]:
    """Walk every edition and accumulate field presence per family."""
    known = _schema_families()
    accumulators: dict[str, _FamilyAccumulator] = defaultdict(_FamilyAccumulator)
    modelos_root = registry_root / _MODELOS
    for modelo_dir in sorted(path for path in modelos_root.iterdir() if path.is_dir()):
        modelo = modelo_dir.name
        if modelo_ids and modelo not in modelo_ids:
            continue
        revisions = modelo_dir / _REVISIONS
        if not revisions.is_dir():
            continue
        for edition_dir in sorted(path for path in revisions.iterdir() if path.is_dir()):
            edition = edition_dir.name
            sections, manifest = _read_sections(edition_dir, edition)
            members_by_family: dict[str, list[dict[str, Any]]] = dict(sections)
            members_by_family[_MANIFEST_FAMILY] = [manifest] if manifest else []
            for family, members in members_by_family.items():
                if family not in known and family != _MANIFEST_FAMILY:
                    # An undeclared section is itself the finding: report it as a
                    # family whose every key is unknown.
                    pass
                acc = accumulators[family]
                acc.members += len(members)
                acc.editions.add(f"{modelo}/{edition}")
                acc.modelos.add(modelo)
                acc.per_edition_members[(modelo, edition)] += len(members)
                for member in members:
                    paths = field_paths(member)
                    for path in paths:
                        presence = acc.fields[path]
                        presence.members += 1
                        presence.editions.add(f"{modelo}/{edition}")
                        presence.modelos.add(modelo)
                        acc.per_edition[(modelo, edition)][path] += 1
                        if path.endswith("]") and "[kind=" in path:
                            acc.kinds[path] += 1
    return accumulators


@dataclass(frozen=True, slots=True)
class FieldCensus:
    """One field path in one family: where it is present and what the schema says of it."""

    family: str
    path: str
    members: int
    denominator: int
    editions: int
    editions_total: int
    modelos: int
    modelos_total: int
    klass: str
    status: str

    @property
    def ratio(self) -> float:
        """Presence ratio within the field's own denominator."""
        return self.members / self.denominator if self.denominator else 0.0


@dataclass(frozen=True, slots=True)
class FieldDivergence:
    """One field present in some editions of a modelo's family and absent from others."""

    modelo: str
    family: str
    path: str
    present: tuple[str, ...]
    absent: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FamilyCensus:
    """One family's members, its field census, the typed fields nobody uses, and its divergences."""

    family: str
    members: int
    editions: int
    modelos: int
    fields: tuple[FieldCensus, ...]
    unused: tuple[str, ...]
    divergences: tuple[FieldDivergence, ...]

    def count(self, *, status: str | None = None, klass: str | None = None) -> int:
        """Number of fields matching a status and/or a class."""
        return sum(
            1
            for item in self.fields
            if (status is None or item.status == status) and (klass is None or item.klass == klass)
        )


@dataclass(frozen=True, slots=True)
class Report:
    """One census over a registry root."""

    families: tuple[FamilyCensus, ...]


def _classify(family: str, path: str, typed: frozenset[str]) -> str:
    top = path.split(".")[0].split("[")[0]
    if _LIMITATIONS:
        return "typed" if top not in _AUTHORING_ONLY_KEYS else "authoring"
    if top in typed:
        return "typed"
    if top in _AUTHORING_ONLY_KEYS:
        return "authoring"
    return "unknown"


def _status(ratio: float, modelos: int, *, kind_scoped: bool = False) -> str:
    if ratio < _OUTLIER_RATIO or (not kind_scoped and modelos <= _OUTLIER_MODELOS):
        return "outlier"
    if ratio >= _CONVERGED:
        return "converged"
    if ratio >= _COMMON:
        return "common"
    if ratio < _SPARSE:
        return "sparse"
    return "mixed"


def _denominator(acc: _FamilyAccumulator, path: str) -> int:
    if "[kind=" in path:
        prefix = path.split(".")[0]
        return acc.kinds.get(prefix, acc.members)
    return acc.members


def _divergences(family: str, acc: _FamilyAccumulator) -> tuple[FieldDivergence, ...]:
    by_modelo: dict[str, list[str]] = defaultdict(list)
    for modelo, edition in acc.per_edition_members:
        by_modelo[modelo].append(edition)
    found: list[FieldDivergence] = []
    for modelo, editions in sorted(by_modelo.items()):
        with_members = sorted(edition for edition in editions if acc.per_edition_members[(modelo, edition)])
        if len(with_members) < 2:
            continue
        paths = {path for edition in with_members for path in acc.per_edition[(modelo, edition)]}
        for path in sorted(paths):
            if "[kind=" in path or (family == _MANIFEST_FAMILY and path.split(".")[0] in _CHAIN_POSITION_KEYS):
                continue
            present = tuple(edition for edition in with_members if acc.per_edition[(modelo, edition)][path])
            absent = tuple(edition for edition in with_members if not acc.per_edition[(modelo, edition)][path])
            if present and absent:
                found.append(FieldDivergence(modelo, family, path, present, absent))
    return tuple(found)


def build_report(registry_root: Path, *, modelo_ids: tuple[str, ...] = ()) -> Report:
    """Scan a registry root and classify every observed field per family."""
    accumulators = scan_registry(registry_root, modelo_ids=modelo_ids)
    known = _schema_families()
    all_editions = {edition for acc in accumulators.values() for edition in acc.editions}
    all_modelos = {modelo for acc in accumulators.values() for modelo in acc.modelos}
    families: list[FamilyCensus] = []
    for family in sorted(set(accumulators) | set(known)):
        acc = accumulators.get(family, _FamilyAccumulator())
        typed = known.get(family, frozenset())
        fields = tuple(
            FieldCensus(
                family=family,
                path=path,
                members=presence.members,
                denominator=_denominator(acc, path),
                editions=len(presence.editions),
                editions_total=len(all_editions),
                modelos=len(presence.modelos),
                modelos_total=len(all_modelos),
                klass=_classify(family, path, typed),
                status=_status(
                    presence.members / _denominator(acc, path) if _denominator(acc, path) else 0.0,
                    len(presence.modelos),
                    kind_scoped="[kind=" in path,
                ),
            )
            for path, presence in sorted(acc.fields.items())
        )
        used_top = {item.path.split(".")[0].split("[")[0] for item in fields}
        families.append(
            FamilyCensus(
                family=family,
                members=acc.members,
                editions=len(acc.editions),
                modelos=len(acc.modelos),
                fields=fields,
                unused=tuple(sorted(typed - used_top)) if acc.members else (),
                divergences=_divergences(family, acc),
            )
        )
    return Report(tuple(families))


def signal_lines(report: Report, *, totals_only: bool = False) -> list[str]:
    """Sorted, path-free lines a later run diffs against."""
    families = [item for item in report.families if item.members]
    lines = [
        "# edition_field_census schema=1",
        *(f"limitation {text}" for text in _LIMITATIONS),
        "corpus "
        + " ".join(
            [
                f"families={len(families)}",
                f"fields={sum(len(item.fields) for item in families)}",
                f"typed={sum(item.count(klass='typed') for item in families)}",
                f"authoring={sum(item.count(klass='authoring') for item in families)}",
                f"unknown={sum(item.count(klass='unknown') for item in families)}",
                f"unused={sum(len(item.unused) for item in families)}",
                f"converged={sum(item.count(status='converged') for item in families)}",
                f"divergent={sum(len(item.divergences) for item in families)}",
                f"outlier={sum(item.count(status='outlier') for item in families)}",
            ]
        ),
    ]
    for item in families:
        divergent_modelos = len({div.modelo for div in item.divergences})
        lines.append(
            f"fields {item.family} members={item.members} editions={item.editions} modelos={item.modelos} "
            f"fields={len(item.fields)} converged={item.count(status='converged')} "
            f"common={item.count(status='common')} mixed={item.count(status='mixed')} "
            f"sparse={item.count(status='sparse')} outlier={item.count(status='outlier')} "
            f"unknown={item.count(klass='unknown')} unused={len(item.unused)} "
            f"divergent={len(item.divergences)} divergent_modelos={divergent_modelos}"
        )
    if totals_only:
        return lines
    for item in families:
        for census in item.fields:
            lines.append(
                f"field {item.family} {census.path} members={census.members}/{census.denominator} "
                f"ratio={census.ratio:.3f} editions={census.editions}/{census.editions_total} "
                f"modelos={census.modelos}/{census.modelos_total} class={census.klass} status={census.status}"
            )
        lines.extend(f"unused {item.family} {name}" for name in item.unused)
        lines.extend(
            f"divergent {div.modelo} {item.family} {div.path} "
            f"present={','.join(div.present)} absent={','.join(div.absent)}"
            for div in item.divergences
        )
    return lines


def _payload(report: Report) -> dict[str, Any]:
    return {
        "families": [
            {
                "family": item.family,
                "members": item.members,
                "editions": item.editions,
                "modelos": item.modelos,
                "unused": list(item.unused),
                "fields": [
                    {
                        "path": census.path,
                        "members": census.members,
                        "denominator": census.denominator,
                        "editions": census.editions,
                        "modelos": census.modelos,
                        "class": census.klass,
                        "status": census.status,
                    }
                    for census in item.fields
                ],
                "divergences": [
                    {"modelo": div.modelo, "path": div.path, "present": list(div.present), "absent": list(div.absent)}
                    for div in item.divergences
                ],
            }
            for item in report.families
            if item.members
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--registry-root", type=Path, default=None)
    parser.add_argument("--modelo", action="append", default=[], help="restrict to these modelo ids")
    parser.add_argument("--family", action="append", default=[], help="print only these families")
    parser.add_argument("--totals-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()
    root = (arguments.registry_root or _bundled_registry_root()).resolve()
    report = build_report(root, modelo_ids=tuple(arguments.modelo))
    if arguments.family:
        report = Report(tuple(item for item in report.families if item.family in set(arguments.family)))
    if arguments.json:
        sys.stdout.write(json.dumps(_payload(report), indent=2, sort_keys=True) + "\n")
        return 0
    for line in signal_lines(report, totals_only=arguments.totals_only):
        sys.stdout.write(line + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
