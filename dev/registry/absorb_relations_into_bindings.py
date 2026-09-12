"""Fold the authored relation family into the binding rows it targets.

A cross-filing fold used to be declared twice: a ``relation_prefill`` binding
named the slot, and a relation in ``relations/*.toml`` named the source modelo,
the source casilla, the source periods, the year alignment, and the
aggregation. Every axis except ``kind`` and ``dependency_role`` was declared on
both sides, and nothing made the two agree.
:class:`~cadrumo.domain.calculations.registry.relation_prefill_bindings.RelationPrefillProvider`
now carries all of them, so this tool rewrites the corpus onto the single
declaration and removes the relation family.

What it does, per revision directory:

* joins each relation to its ``target_binding`` and refuses -- leaving every
  file of that revision untouched -- when a relation names no binding, or when
  a group of relations sharing one binding disagrees on an axis the single
  provider cannot carry;
* derives the provider's ``temporal`` member from the relation's runtime-
  effective axes (the revision selector's filing-year delta, the source-period
  list, and the period offset) through
  :func:`~cadrumo.domain.calculations.registry.binding_temporal.temporal_selector_from_relation_fields`;
  an ABSOLUTE ``year`` maps to delta zero only when it equals the year its own
  revision directory is named for, and is refused otherwise rather than
  reinterpreted;
* moves ``target_periods`` onto the binding's ``applicability``, and unions the
  relation's ``legal_refs``/``source_refs`` into the binding's;
* rewrites formula ``relation`` operands, ``dependency_classifications``
  ``relation_refs``, and construct ``relations`` members onto the binding ids
  they now name;
* deletes ``relations/*.toml`` and the ``family_dispositions.relations`` table
  of each revision.

Three merge shapes are recognised where one binding is targeted by several
relations, each derived from what the relations actually declare rather than
from the binding's identity:

* every relation declares the ``prior_pagos_cumulative`` alignment -- the
  expanding span named the old way, so the group becomes one
  ``prior_quarter_expanding_span``;
* the relations share a filing-year delta and differ only in their source
  periods -- the group becomes one member over the union of those periods;
* the relations carry DIFFERENT filing-year deltas per target period -- the
  group becomes ``filing_year_offset_by_target_period``, whose offsets map is
  total over the target periods the relations covered and produces no anchor
  for any other, which is the scope-out the old per-target relation split
  expressed by simply not applying.

A relation whose target binding is a ``previous_filing`` provider is absorbed
by DELETION: that provider already states the same source coordinate and
window. The tool asserts the agreement before deleting and refuses on any
disagreement.

The rewrite is textual so comments, ordering, and hand formatting survive; the
structured parse decides what each row becomes. Every rewritten binding row is
constructed as a
:class:`~cadrumo.domain.calculations.registry.schema.BindingDefinition` before
anything is written, and a single failure leaves the whole revision untouched.

``--dry-run`` also emits the frozen relation-id to binding-id join table, which
is derived from the pre-cut corpus and is the only surviving record of the
mapping once the relation family is gone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_MODELOS_ROOT = REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"
GENERATED_ROOT = REPO_ROOT / "dev" / "registry" / "generated"
JOIN_TABLE_PATH = GENERATED_ROOT / "relation_binding_join.json"

sys.path.insert(0, str(REPO_ROOT / "src"))

from cadrumo.domain.calculations.registry.binding_temporal import (  # noqa: E402
    FilingYearOffsetByTargetPeriod,
    temporal_selector_from_relation_fields,
)
from cadrumo.domain.calculations.registry.schema import BindingDefinition  # noqa: E402

__all__ = ["AbsorptionReport", "absorb_modelo", "main"]

#: Modelo/revision pairs another contributor is editing concurrently. Their
#: files are read, planned, and then re-read immediately before the write; a
#: content change in that window means the plan was built against a stale file,
#: so the write is skipped and reported rather than applied over the edit.
CONCURRENTLY_EDITED_REVISIONS: frozenset[tuple[str, str]] = frozenset({("100", "2024"), ("100", "2025")})

_KEY_LINE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=")
_BINDINGS_HEADER = re.compile(r'^\[\[revisions\.(?:"(?P<quoted>[^"]+)"|(?P<bare>[^.\]]+))\.bindings\]\]\s*$')
_ARRAY_OPEN = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*\[\s*$")
_ARRAY_INLINE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<body>\[.*\])$")
_NEWLINE_CHARS = "".join((chr(13), chr(10)))
_RELATION_OPERAND = re.compile(r'\brelation\s*=\s*"(?P<id>[^"]+)"')
_DISPOSITION_HEADER = re.compile(r'^\[revisions\.(?:"[^"]+"|[^.\]]+)\.family_dispositions\.relations\]\s*$')


class AbsorptionRefusalError(Exception):
    """One relation group could not be absorbed without guessing."""

    def __init__(self, target: str, reason: str) -> None:
        """Record the refused target binding and why it was refused."""
        super().__init__(f"{target}: {reason}")
        self.target = target
        self.reason = reason


@dataclass
class AbsorptionReport:
    """Per-run counts, the join table, and the refusals."""

    modelos: list[str] = field(default_factory=list)
    revisions_absorbed: list[str] = field(default_factory=list)
    relations_absorbed_by_modelo: Counter[str] = field(default_factory=Counter)
    merge_shape_counts: Counter[str] = field(default_factory=Counter)
    previous_filing_deletions: int = 0
    files_rewritten: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    files_skipped_concurrent: list[str] = field(default_factory=list)
    dispositions_removed: list[str] = field(default_factory=list)
    formula_operands_rewritten: int = 0
    dependency_refs_rewritten: int = 0
    construct_members_rewritten: int = 0
    join_table: dict[str, str] = field(default_factory=dict)
    refusals: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Return the JSON-serialisable form of this report."""
        return {
            "modelos": sorted(self.modelos),
            "revisions_absorbed": sorted(self.revisions_absorbed),
            "relations_absorbed_by_modelo": dict(sorted(self.relations_absorbed_by_modelo.items())),
            "relations_absorbed_total": sum(self.relations_absorbed_by_modelo.values()),
            "merge_shape_counts": dict(sorted(self.merge_shape_counts.items())),
            "previous_filing_deletions": self.previous_filing_deletions,
            "formula_operands_rewritten": self.formula_operands_rewritten,
            "dependency_refs_rewritten": self.dependency_refs_rewritten,
            "construct_members_rewritten": self.construct_members_rewritten,
            "dispositions_removed": sorted(self.dispositions_removed),
            "files_rewritten": sorted(self.files_rewritten),
            "files_deleted": sorted(self.files_deleted),
            "files_skipped_concurrent": sorted(self.files_skipped_concurrent),
            "refusals": self.refusals,
        }


def _toml_value(value: object) -> str:
    """Render one Python value as its TOML literal."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        body = ", ".join(f"{_toml_key(key)} = {_toml_value(item)}" for key, item in value.items())
        return "{ " + body + " }"
    raise TypeError(f"no TOML rendering for {type(value).__name__}")


def _toml_key(key: object) -> str:
    """Render a mapping key as a bare or quoted TOML key."""
    text = str(key)
    return text if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", text) else json.dumps(text, ensure_ascii=False)


def _prune_none(table: dict[str, Any]) -> dict[str, Any]:
    """Drop keys whose value is absent, so an omitted axis stays omitted in TOML."""
    return {key: value for key, value in table.items() if value is not None}


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _display_path(path: Path) -> str:
    """Return the repo-relative path, or the absolute one for an out-of-tree root."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _content_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _iter_family_rows(revision_dir: Path, family: str) -> list[tuple[Path, dict[str, Any]]]:
    """Return every declared row of one family directory with its fragment path."""
    family_dir = revision_dir / family
    if not family_dir.is_dir():
        return []
    rows: list[tuple[Path, dict[str, Any]]] = []
    for toml_path in sorted(family_dir.glob("*.toml")):
        for revision_table in _load_toml(toml_path).get("revisions", {}).values():
            if not isinstance(revision_table, dict):
                continue
            entries = revision_table.get(family)
            if isinstance(entries, list):
                rows.extend((toml_path, entry) for entry in entries if isinstance(entry, dict))
    return rows


def _as_tuples(value: object) -> object:
    """Return ``value`` with every list turned into a tuple, recursively."""
    if isinstance(value, list):
        return tuple(_as_tuples(item) for item in value)
    if isinstance(value, dict):
        return {key: _as_tuples(item) for key, item in value.items()}
    return value


def _relation_filing_year_delta(relation: dict[str, Any], *, revision_name: str, target: str) -> int:
    """Return the relation's effective filing-year delta, refusing an unanchored year.

    The selector's ``year_from``/``year_to`` bounds pick a source REVISION and
    never moved the source filing year at runtime, so they carry delta zero. An
    absolute ``year`` did move it, and is accepted only when it names the year
    its own revision directory is named for -- which makes it delta zero too.
    Any other absolute year states a coordinate the relative union cannot hold
    and that the edition rules would carry wrongly into a successor.
    """
    selector = relation.get("source_revision_selector") or {}
    year = selector.get("year")
    delta = selector.get("filing_year_delta")
    if year is not None:
        if str(year) != revision_name:
            raise AbsorptionRefusalError(
                target,
                f"relation {relation.get('id')!r} selects absolute source year {year} "
                f"in revision {revision_name!r}; no relative member can express it",
            )
        return 0
    return int(delta or 0)


def _relation_temporal(relation: dict[str, Any], *, revision_name: str, target: str) -> dict[str, Any]:
    """Return the temporal member one relation's runtime-effective axes name."""
    alignment = relation.get("period_alignment") or {}
    delta = _relation_filing_year_delta(relation, revision_name=revision_name, target=target)
    try:
        member = temporal_selector_from_relation_fields(
            filing_year_delta=delta,
            source_periods=tuple(relation.get("source_periods") or ()),
            source_period_offset_from_target=relation.get("source_period_offset_from_target"),
            alignment_mode=alignment.get("mode"),
        )
    except Exception as exc:
        raise AbsorptionRefusalError(target, f"relation {relation.get('id')!r} temporal: {exc}") from exc
    return _prune_none(member.model_dump(mode="json"))


def _merged_temporal(
    relations: list[dict[str, Any]],
    *,
    revision_name: str,
    target: str,
    report: AbsorptionReport,
) -> dict[str, Any]:
    """Return the one temporal member a group of relations on one binding states."""
    if len(relations) == 1:
        report.merge_shape_counts["single"] += 1
        return _relation_temporal(relations[0], revision_name=revision_name, target=target)

    modes = {(relation.get("period_alignment") or {}).get("mode") for relation in relations}
    if modes == {"prior_pagos_cumulative"}:
        report.merge_shape_counts["expanding_span"] += 1
        return _relation_temporal(relations[0], revision_name=revision_name, target=target)

    deltas = {
        relation["id"]: _relation_filing_year_delta(relation, revision_name=revision_name, target=target)
        for relation in relations
    }
    source_period_sets = {tuple(relation.get("source_periods") or ()) for relation in relations}
    if len(set(deltas.values())) == 1:
        merged_periods: list[str] = []
        for relation in relations:
            merged_periods.extend(
                period for period in (relation.get("source_periods") or ()) if period not in merged_periods
            )
        report.merge_shape_counts["period_union"] += 1
        return _merged_period_union(
            relations[0], delta=next(iter(deltas.values())), periods=merged_periods, target=target
        )

    if len(source_period_sets) != 1:
        raise AbsorptionRefusalError(
            target,
            "relations differ in BOTH filing-year delta and source periods; no single member expresses that",
        )
    offsets: dict[str, int] = {}
    for relation in relations:
        target_periods = tuple(relation.get("target_periods") or ())
        if not target_periods:
            raise AbsorptionRefusalError(
                target,
                f"relation {relation['id']!r} carries a distinct filing-year delta but names no target_periods",
            )
        for period in target_periods:
            existing = offsets.get(period)
            if existing is not None and existing != deltas[relation["id"]]:
                raise AbsorptionRefusalError(
                    target,
                    f"target period {period!r} is claimed with two different filing-year deltas",
                )
            offsets[period] = deltas[relation["id"]]
    report.merge_shape_counts["offset_by_target_period"] += 1
    member = FilingYearOffsetByTargetPeriod(offsets=offsets, source_periods=next(iter(source_period_sets)))
    return _prune_none(member.model_dump(mode="json"))


def _merged_period_union(
    exemplar: dict[str, Any],
    *,
    delta: int,
    periods: list[str],
    target: str,
) -> dict[str, Any]:
    """Return the member covering the union of several relations' source periods."""
    merged = dict(exemplar)
    merged["source_periods"] = periods
    merged["source_revision_selector"] = {"filing_year_delta": delta}
    merged["period_alignment"] = {}
    try:
        member = temporal_selector_from_relation_fields(
            filing_year_delta=delta,
            source_periods=tuple(periods),
            source_period_offset_from_target=exemplar.get("source_period_offset_from_target"),
        )
    except Exception as exc:
        raise AbsorptionRefusalError(target, f"merged period union: {exc}") from exc
    return _prune_none(member.model_dump(mode="json"))


@dataclass
class _BindingPlan:
    """The rewrite one binding row receives."""

    binding_id: str
    path: Path
    provider: dict[str, Any] | None
    applicability: dict[str, Any] | None
    legal_refs: list[str]
    source_refs: list[str]


def _agreeing(relations: list[dict[str, Any]], key: str, target: str) -> Any:
    """Return the one value a group of relations declares for ``key``."""
    values = {json.dumps(relation.get(key), sort_keys=True, default=str) for relation in relations}
    if len(values) != 1:
        raise AbsorptionRefusalError(target, f"relations disagree on {key!r}: {sorted(values)}")
    return relations[0].get(key)


def _plan_relation_prefill(
    binding: dict[str, Any],
    relations: list[dict[str, Any]],
    *,
    revision_name: str,
    report: AbsorptionReport,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Return the absorbed provider and applicability for one relation-prefill binding."""
    target = str(binding["id"])
    provider = dict(binding.get("provider") or {})
    source_modelo = _agreeing(relations, "source_modelo", target)
    source_casilla = _agreeing(relations, "source_casilla_id", target)
    if str(provider.get("source_modelo")) != str(source_modelo):
        raise AbsorptionRefusalError(
            target,
            f"binding source_modelo {provider.get('source_modelo')!r} disagrees with relation {source_modelo!r}",
        )
    declared_casillas = provider.get("source_casilla_ids") or (
        [provider["source_casilla_id"]] if provider.get("source_casilla_id") else []
    )
    if list(declared_casillas) != [source_casilla]:
        raise AbsorptionRefusalError(
            target,
            f"binding source casillas {list(declared_casillas)!r} disagree with relation {source_casilla!r}",
        )
    relation_agg = {(relation.get("aggregation") or {}).get("op", "copy") for relation in relations}
    binding_agg = (binding.get("aggregation") or {}).get("op", "copy")
    if relation_agg != {binding_agg}:
        raise AbsorptionRefusalError(
            target,
            f"binding aggregation {binding_agg!r} disagrees with relation {sorted(relation_agg)!r}",
        )

    absorbed = {
        "kind": "relation_prefill",
        "relation_kind": _agreeing(relations, "kind", target),
        "dependency_role": _agreeing(relations, "dependency_role", target),
        "source_modelo": str(source_modelo),
        "source_casilla_id": str(source_casilla),
        "temporal": _merged_temporal(relations, revision_name=revision_name, target=target, report=report),
    }

    target_periods: list[str] = []
    for relation in relations:
        target_periods.extend(
            period for period in (relation.get("target_periods") or ()) if period not in target_periods
        )
    applicability = binding.get("applicability")
    if target_periods:
        declared = {"kind": "target_periods", "periods": target_periods}
        if applicability is not None and applicability != declared:
            raise AbsorptionRefusalError(
                target,
                f"binding already declares applicability {applicability!r}, which the relation target periods "
                f"{target_periods!r} contradict",
            )
        return absorbed, declared
    return absorbed, None


def _assert_previous_filing_agreement(binding: dict[str, Any], relations: list[dict[str, Any]]) -> None:
    """Refuse unless the previous-filing provider already states the relation's fold."""
    target = str(binding["id"])
    provider = dict(binding.get("provider") or {})
    source_modelo = _agreeing(relations, "source_modelo", target)
    source_casilla = _agreeing(relations, "source_casilla_id", target)
    if str(provider.get("source_modelo")) != str(source_modelo):
        raise AbsorptionRefusalError(target, "previous-filing provider names a different source modelo")
    declared = provider.get("source_casilla_ids") or (
        [provider["source_casilla_id"]] if provider.get("source_casilla_id") else []
    )
    if list(declared) != [source_casilla]:
        raise AbsorptionRefusalError(target, "previous-filing provider names a different source casilla")
    temporal = provider.get("temporal") or {}
    for relation in relations:
        offset = relation.get("source_period_offset_from_target")
        if offset is None:
            raise AbsorptionRefusalError(
                target,
                f"relation {relation['id']!r} targets a previous_filing provider but names no period offset to match",
            )
        if temporal.get("kind") != "target_period_offset" or temporal.get("periods") != offset:
            raise AbsorptionRefusalError(
                target,
                f"previous-filing temporal {temporal!r} does not state relation offset {offset!r}",
            )


def _union_refs(binding: dict[str, Any], relations: list[dict[str, Any]], key: str) -> list[str]:
    """Return the binding's refs unioned with every relation's, in stable order."""
    merged = list(binding.get(key) or [])
    for relation in relations:
        merged.extend(ref for ref in (relation.get(key) or []) if ref not in merged)
    return merged


def _validated_binding(row: dict[str, Any], plan: _BindingPlan) -> None:
    """Construct the rewritten row as a ``BindingDefinition``, raising on any refusal."""
    candidate = dict(row)
    if plan.provider is not None:
        candidate["provider"] = plan.provider
    if plan.applicability is not None:
        candidate["applicability"] = plan.applicability
    candidate["legal_refs"] = plan.legal_refs
    candidate["source_refs"] = plan.source_refs
    try:
        BindingDefinition.model_validate({key: _as_tuples(item) for key, item in candidate.items()})
    except Exception as exc:
        raise AbsorptionRefusalError(plan.binding_id, f"rewritten row does not validate: {exc}") from exc


def _rewrite_binding_file(path: Path, plans: dict[str, _BindingPlan]) -> str:
    """Return the fragment text with each planned binding row rewritten in place."""
    original = path.read_text(encoding="utf-8", newline="")
    ending = "\r\n" if "\r\n" in original else "\n"
    lines = original.splitlines(keepends=True)
    out: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        out.append(line)
        if _BINDINGS_HEADER.match(line.rstrip("\r\n") + "\n") is None:
            index += 1
            continue
        cursor = index + 1
        region: list[str] = []
        while cursor < len(lines) and not lines[cursor].lstrip().startswith("["):
            region.append(lines[cursor])
            cursor += 1
        row_id = _region_id(region)
        plan = plans.get(row_id) if row_id else None
        out.extend(region if plan is None else _rewritten_region(region, plan, ending))
        index = cursor
    return "".join(out)


def _region_id(region: list[str]) -> str | None:
    for line in region:
        match = re.match(r'^id\s*=\s*"([^"]+)"', line)
        if match:
            return match.group(1)
    return None


def _rewritten_region(region: list[str], plan: _BindingPlan, ending: str) -> list[str]:
    """Return one binding row's key region with the absorbed keys substituted."""
    rewritten: list[str] = []
    seen_applicability = False
    for line in region:
        match = _KEY_LINE.match(line)
        key = match.group("key") if match else None
        if key == "provider" and plan.provider is not None:
            rewritten.append(f"provider = {_toml_value(plan.provider)}{ending}")
            if plan.applicability is not None:
                rewritten.append(f"applicability = {_toml_value(plan.applicability)}{ending}")
                seen_applicability = True
            continue
        if key == "applicability":
            if plan.applicability is not None and not seen_applicability:
                rewritten.append(f"applicability = {_toml_value(plan.applicability)}{ending}")
                seen_applicability = True
                continue
            rewritten.append(line)
            continue
        if key == "legal_refs":
            rewritten.append(f"legal_refs = {_toml_value(plan.legal_refs)}{ending}")
            continue
        if key == "source_refs":
            rewritten.append(f"source_refs = {_toml_value(plan.source_refs)}{ending}")
            continue
        rewritten.append(line)
    return rewritten


def _rewrite_relation_operands(path: Path, join: dict[str, str], report: AbsorptionReport) -> str | None:
    """Return the formula fragment with ``relation`` operands rekeyed onto bindings."""
    original = path.read_text(encoding="utf-8", newline="")
    if not _RELATION_OPERAND.search(original):
        return None

    def _swap(match: re.Match[str]) -> str:
        relation_id = match.group("id")
        binding_id = join.get(relation_id)
        if binding_id is None:
            raise AbsorptionRefusalError(relation_id, f"formula operand in {path.name} names an unjoined relation")
        report.formula_operands_rewritten += 1
        return f'binding = "{binding_id}"'

    rewritten = _RELATION_OPERAND.sub(_swap, original)
    _refuse_folded_operand_collision(path, rewritten)
    return rewritten


def _refuse_folded_operand_collision(path: Path, text: str) -> None:
    """Refuse if two operands of one expression now name the same binding.

    Two relations that merged into one binding were two DISTINCT source
    windows; a formula that summed both would, after the fold, sum the same
    materialised value twice. The merged provider already covers the union of
    the windows, so the correct rewrite is one operand -- which is an authoring
    decision, not something this tool may make silently.
    """
    for revision_table in tomllib.loads(text).get("revisions", {}).values():
        if not isinstance(revision_table, dict):
            continue
        for formula in revision_table.get("formulas", []) or []:
            if isinstance(formula, dict):
                _walk_expression_for_collision(str(formula.get("id")), formula.get("expression"), path)


def _walk_expression_for_collision(formula_id: str, node: object, path: Path) -> None:
    """Refuse a duplicate binding operand at any one ``args`` level."""
    if not isinstance(node, dict):
        return
    args = node.get("args")
    if isinstance(args, list):
        bindings = [arg["binding"] for arg in args if isinstance(arg, dict) and isinstance(arg.get("binding"), str)]
        duplicates = sorted({item for item in bindings if bindings.count(item) > 1})
        if duplicates:
            raise AbsorptionRefusalError(
                formula_id,
                f"formula in {path.name} folds operands onto the same binding twice: {duplicates}",
            )
        for arg in args:
            _walk_expression_for_collision(formula_id, arg, path)


def _rewrite_dependency_refs(path: Path, join: dict[str, str], report: AbsorptionReport) -> str | None:
    """Return the dependency-classification fragment with ``relation_refs`` rekeyed."""
    original = path.read_text(encoding="utf-8", newline="")
    if "relation_refs" not in original:
        return None
    lines = original.splitlines(keepends=True)
    spans = [span for span in _array_spans(lines) if span.key == "relation_refs"]
    if not spans:
        return None
    rewritten = list(lines)
    for span in sorted(spans, key=lambda item: item.start, reverse=True):
        members = _array_members(lines, span)
        mapped = _mapped_members(members, join, path, subject="dependency classification")
        report.dependency_refs_rewritten += len(members)
        rewritten[span.start : span.end] = _array_block("binding_refs", mapped, span)
    return "".join(rewritten)


def _mapped_members(members: list[str], join: dict[str, str], path: Path, *, subject: str) -> list[str]:
    """Return the joined binding ids for a list of relation ids, deduplicated in order."""
    mapped: list[str] = []
    for member in members:
        binding_id = join.get(member)
        if binding_id is None:
            raise AbsorptionRefusalError(member, f"{subject} in {path.name} names an unjoined relation")
        if binding_id not in mapped:
            mapped.append(binding_id)
    return mapped


def _rewrite_construct_members(path: Path, join: dict[str, str], report: AbsorptionReport) -> str | None:
    """Return the construct fragment with its ``relations`` members folded into ``bindings``.

    A construct that joins relations almost always joins the target bindings
    too, so the members are merged into the existing ``bindings`` array rather
    than emitted as a second one; the relation array is then removed. Order is
    preserved -- the construct's own bindings first, then any target binding
    only the relation side named. The authored layout of the array that
    survives is preserved, inline or one member per line.
    """
    original = path.read_text(encoding="utf-8", newline="")
    lines = original.splitlines(keepends=True)
    spans = _array_spans(lines)
    relation_spans = [span for span in spans if span.key == "relations"]
    if not relation_spans:
        return None
    binding_spans = [span for span in spans if span.key == "bindings"]
    edits: list[tuple[int, int, list[str]]] = []
    for span in relation_spans:
        members = _array_members(lines, span)
        mapped = _mapped_members(members, join, path, subject="construct")
        report.construct_members_rewritten += len(members)
        host = _enclosing_binding_span(binding_spans, _block_bounds(lines, span.start))
        if host is None:
            edits.append((span.start, span.end, _array_block("bindings", mapped, span)))
            continue
        merged = _array_members(lines, host)
        merged.extend(binding_id for binding_id in mapped if binding_id not in merged)
        edits.append((host.start, host.end, _array_block("bindings", merged, host)))
        edits.append((span.start, span.end, []))
    rewritten = list(lines)
    for span_start, span_end, replacement in sorted(edits, key=lambda edit: edit[0], reverse=True):
        rewritten[span_start:span_end] = replacement
    return "".join(rewritten)


@dataclass(frozen=True)
class _ArraySpan:
    """One authored TOML array of strings located in a fragment's line list."""

    key: str
    start: int
    end: int
    inline: bool
    ending: str


def _is_string_array(body: str) -> bool:
    """Return whether an inline array literal holds only strings."""
    try:
        parsed = json.loads(body)
    except ValueError:
        return False
    return isinstance(parsed, list) and all(isinstance(item, str) for item in parsed)


def _array_spans(lines: list[str]) -> list[_ArraySpan]:
    """Return every authored ``key = [...]`` array of strings, inline or multi-line."""
    spans: list[_ArraySpan] = []
    for index, line in enumerate(lines):
        body = line.rstrip(_NEWLINE_CHARS)
        ending = line[len(body) :]
        inline = _ARRAY_INLINE.match(body)
        if inline is not None:
            if _is_string_array(inline.group("body")):
                spans.append(_ArraySpan(inline.group("key"), index, index + 1, inline=True, ending=ending))
            continue
        opened = _ARRAY_OPEN.match(body)
        if opened is None:
            continue
        cursor = index + 1
        while cursor < len(lines) and lines[cursor].strip() != "]":
            cursor += 1
        spans.append(_ArraySpan(opened.group("key"), index, cursor + 1, inline=False, ending=ending))
    return spans


def _array_members(lines: list[str], span: _ArraySpan) -> list[str]:
    """Return the string members of one array span."""
    if span.inline:
        body = lines[span.start].rstrip(_NEWLINE_CHARS)
        return list(json.loads(body[body.index("[") :]))
    members: list[str] = []
    for line in lines[span.start + 1 : span.end - 1]:
        entry = line.strip().rstrip(",")
        if entry:
            members.append(json.loads(entry))
    return members


def _array_block(key: str, members: list[str], span: _ArraySpan) -> list[str]:
    """Render one array under ``key`` in the layout the replaced span used."""
    if span.inline:
        return [f"{key} = {_toml_value(members)}{span.ending}"]
    return [
        f"{key} = [{span.ending}",
        *(f'    "{member}",{span.ending}' for member in members),
        f"]{span.ending}",
    ]


def _enclosing_binding_span(binding_spans: list[_ArraySpan], block_bounds: tuple[int, int]) -> _ArraySpan | None:
    """Return the ``bindings`` array declared by the same array-of-tables element."""
    block_start, block_end = block_bounds
    inside = [span for span in binding_spans if block_start <= span.start < block_end]
    return inside[0] if inside else None


def _block_bounds(lines: list[str], index: int) -> tuple[int, int]:
    """Return the line span of the array-of-tables element containing ``index``."""
    start = 0
    for cursor in range(index, -1, -1):
        if lines[cursor].lstrip().startswith("[["):
            start = cursor
            break
    end = len(lines)
    for cursor in range(index + 1, len(lines)):
        if lines[cursor].lstrip().startswith("[["):
            end = cursor
            break
    return start, end


def _strip_relations_disposition(path: Path) -> str | None:
    """Return the revision manifest with its ``family_dispositions.relations`` table removed."""
    original = path.read_text(encoding="utf-8", newline="")
    lines = original.splitlines(keepends=True)
    out: list[str] = []
    index = 0
    removed = False
    while index < len(lines):
        if _DISPOSITION_HEADER.match(lines[index].rstrip("\r\n") + "\n"):
            removed = True
            index += 1
            while index < len(lines) and not lines[index].lstrip().startswith("["):
                index += 1
            while out and out[-1].strip() == "":
                out.pop()
            continue
        out.append(lines[index])
        index += 1
    return "".join(out) if removed else None


@dataclass
class _RevisionPlan:
    """Every file edit one revision receives, applied all-or-nothing."""

    writes: dict[Path, str] = field(default_factory=dict)
    deletes: list[Path] = field(default_factory=list)
    digests: dict[Path, str] = field(default_factory=dict)


def absorb_revision(
    modelo: str,
    revision_dir: Path,
    report: AbsorptionReport,
    *,
    apply: bool,
) -> None:
    """Absorb every relation of one revision, or leave the revision untouched."""
    relation_rows = _iter_family_rows(revision_dir, "relations")
    if not relation_rows:
        return
    binding_rows = {
        str(row["id"]): (path, row) for path, row in _iter_family_rows(revision_dir, "bindings") if row.get("id")
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _, relation in relation_rows:
        grouped[str(relation.get("target_binding"))].append(relation)

    plan = _RevisionPlan()
    try:
        join = _plan_revision(modelo, revision_dir, grouped, binding_rows, plan, report)
    except AbsorptionRefusalError as exc:
        report.refusals.append(
            {"modelo": modelo, "revision": revision_dir.name, "target": exc.target, "reason": exc.reason},
        )
        return

    for relation_id, target in join.items():
        existing = report.join_table.get(relation_id)
        if existing is not None and existing != target:
            report.refusals.append(
                {
                    "modelo": modelo,
                    "revision": revision_dir.name,
                    "target": relation_id,
                    "reason": f"relation id joins to {existing!r} in one revision and {target!r} in another",
                },
            )
            return
    report.join_table.update(join)
    report.revisions_absorbed.append(f"{modelo}/{revision_dir.name}")
    report.relations_absorbed_by_modelo[modelo] += len(relation_rows)
    report.files_rewritten.extend(_display_path(path) for path in plan.writes)
    report.files_deleted.extend(_display_path(path) for path in plan.deletes)
    if not apply:
        return
    if (modelo, revision_dir.name) in CONCURRENTLY_EDITED_REVISIONS:
        changed = [path for path, digest in plan.digests.items() if _content_digest(path) != digest]
        if changed:
            report.files_skipped_concurrent.extend(_display_path(path) for path in changed)
            return
    for path, text in plan.writes.items():
        path.write_text(text, encoding="utf-8", newline="")
    for path in plan.deletes:
        path.unlink()
        parent = path.parent
        if not any(parent.iterdir()):
            parent.rmdir()


def _plan_revision(
    modelo: str,
    revision_dir: Path,
    grouped: dict[str, list[dict[str, Any]]],
    binding_rows: dict[str, tuple[Path, dict[str, Any]]],
    plan: _RevisionPlan,
    report: AbsorptionReport,
) -> dict[str, str]:
    """Build every file edit one revision needs, refusing before any is applied."""
    join: dict[str, str] = {}
    plans_by_file: dict[Path, dict[str, _BindingPlan]] = defaultdict(dict)
    for target, relations in sorted(grouped.items()):
        entry = binding_rows.get(target)
        if entry is None:
            raise AbsorptionRefusalError(target, "relation names a target_binding this revision does not declare")
        path, binding = entry
        provider_kind = str((binding.get("provider") or {}).get("kind"))
        if provider_kind == "previous_filing":
            _assert_previous_filing_agreement(binding, relations)
            absorbed, applicability = None, None
            report.previous_filing_deletions += len(relations)
        elif provider_kind == "relation_prefill":
            absorbed, applicability = _plan_relation_prefill(
                binding,
                relations,
                revision_name=revision_dir.name,
                report=report,
            )
        else:
            raise AbsorptionRefusalError(target, f"target binding declares provider kind {provider_kind!r}")
        binding_plan = _BindingPlan(
            binding_id=target,
            path=path,
            provider=absorbed,
            applicability=applicability,
            legal_refs=_union_refs(binding, relations, "legal_refs"),
            source_refs=_union_refs(binding, relations, "source_refs"),
        )
        _validated_binding(binding, binding_plan)
        plans_by_file[path][target] = binding_plan
        for relation in relations:
            join[str(relation["id"])] = target

    for path, plans in plans_by_file.items():
        plan.digests[path] = _content_digest(path)
        plan.writes[path] = _rewrite_binding_file(path, plans)

    for family, rewriter in (
        ("formulas", _rewrite_relation_operands),
        ("dependency_classifications", _rewrite_dependency_refs),
        ("constructs", _rewrite_construct_members),
    ):
        family_dir = revision_dir / family
        if not family_dir.is_dir():
            continue
        for toml_path in sorted(family_dir.glob("*.toml")):
            text = rewriter(toml_path, join, report)
            if text is not None:
                plan.digests[toml_path] = _content_digest(toml_path)
                plan.writes[toml_path] = text

    plan.deletes.extend(sorted((revision_dir / "relations").glob("*.toml")))
    return join


def absorb_modelo(
    modelo: str, report: AbsorptionReport, *, apply: bool, modelos_root: Path = REGISTRY_MODELOS_ROOT
) -> None:
    """Absorb every relation-bearing revision of one modelo."""
    revisions = modelos_root / modelo / "revisions"
    if not revisions.is_dir():
        report.refusals.append({"modelo": modelo, "revision": "*", "target": "*", "reason": "modelo has no revisions"})
        return
    report.modelos.append(modelo)
    for revision_dir in sorted(p for p in revisions.iterdir() if p.is_dir()):
        absorb_revision(modelo, revision_dir, report, apply=apply)
        _retire_relations_disposition(modelo, revision_dir, report, apply=apply)


def _retire_relations_disposition(
    modelo: str,
    revision_dir: Path,
    report: AbsorptionReport,
    *,
    apply: bool,
) -> None:
    """Remove one revision's ``family_dispositions.relations`` table.

    The disposition states why a family this revision declares nothing for is
    empty on purpose. A family that no longer exists has no absence to explain,
    so the entry goes with it -- including on the many revisions that never
    declared a relation at all, which is where most of them live.
    """
    manifest = revision_dir / "revision.toml"
    if not manifest.is_file():
        return
    stripped = _strip_relations_disposition(manifest)
    if stripped is None:
        return
    report.dispositions_removed.append(f"{modelo}/{revision_dir.name}")
    report.files_rewritten.append(_display_path(manifest))
    if not apply:
        return
    if (modelo, revision_dir.name) in CONCURRENTLY_EDITED_REVISIONS and _strip_relations_disposition(
        manifest
    ) != stripped:
        report.files_skipped_concurrent.append(_display_path(manifest))
        return
    manifest.write_text(stripped, encoding="utf-8", newline="")


def _all_modelos(modelos_root: Path) -> list[str]:
    return sorted(p.name for p in modelos_root.iterdir() if p.is_dir() and (p / "revisions").is_dir())


def main(argv: list[str] | None = None) -> int:
    """Run the absorption and return the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelo", action="append", default=[], help="Modelo to absorb; repeatable.")
    parser.add_argument("--all", action="store_true", help="Absorb every modelo carrying a revisions tree.")
    parser.add_argument("--dry-run", action="store_true", help="Report the rewrite without writing any corpus file.")
    parser.add_argument("--report", type=Path, default=None, help="Write the JSON summary to this path.")
    args = parser.parse_args(argv)

    if not args.modelo and not args.all:
        parser.error("pass --modelo <id> at least once, or --all")
    modelos = _all_modelos(REGISTRY_MODELOS_ROOT) if args.all else list(dict.fromkeys(args.modelo))

    report = AbsorptionReport()
    for modelo in modelos:
        absorb_modelo(modelo, report, apply=not args.dry_run)

    summary = report.as_dict()
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.dry_run and args.all and not summary["refusals"]:
        GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
        JOIN_TABLE_PATH.write_text(
            json.dumps({"relation_binding_join": dict(sorted(report.join_table.items()))}, indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        print(f"Join table written: {JOIN_TABLE_PATH.relative_to(REPO_ROOT)} ({len(report.join_table)} relations)")

    mode = "dry-run" if args.dry_run else "applied"
    print(f"Modelos: {', '.join(summary['modelos']) or '(none)'} [{mode}]")
    print(
        f"Relations absorbed: {summary['relations_absorbed_total']} across {len(summary['revisions_absorbed'])} revisions"
    )
    for shape, count in summary["merge_shape_counts"].items():
        print(f"  merge shape {shape}: {count}")
    print(f"  previous_filing deletions: {summary['previous_filing_deletions']}")
    print(f"  formula operands: {summary['formula_operands_rewritten']}")
    print(f"  dependency refs: {summary['dependency_refs_rewritten']}")
    print(f"  construct members: {summary['construct_members_rewritten']}")
    print(f"  dispositions removed: {len(summary['dispositions_removed'])}")
    if summary["files_skipped_concurrent"]:
        print(f"Skipped (changed under a concurrent editor): {', '.join(summary['files_skipped_concurrent'])}")
    if summary["refusals"]:
        print(f"Refused groups ({len(summary['refusals'])}); their revisions were left untouched:")
        for refusal in summary["refusals"]:
            print(f"  {refusal['modelo']}/{refusal['revision']} {refusal['target']}: {refusal['reason']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
