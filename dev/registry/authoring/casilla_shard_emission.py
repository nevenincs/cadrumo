"""Per-record casilla candidate emission and outcome assembly."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from dev.registry.compiler.record_design_schema import RecordDesignField, RecordDesignSheet

from .casilla_shard_design import audit_sheet, comment_line, derive_number, is_structural, normalise_for_drift
from .casilla_shard_prior import load_prior_attributes
from .casilla_shard_rows import _filename_stem, _render_row
from .casilla_shard_types import (
    GenerationRefusedError,
    GenerationReport,
    RecordOutcome,
    WaveSpec,
)


@dataclass(frozen=True, slots=True)
class _DesignRowGroup:
    number: str
    caption: str
    members: tuple[RecordDesignField, ...]


@dataclass(frozen=True, slots=True)
class _RowAttributes:
    section: str
    data_type: str
    casilla_id: str
    segmento: str | None
    legal_refs: str
    carried: bool


@dataclass(frozen=True, slots=True)
class _RowEmission:
    text: str | None = None
    carried: bool = False
    adjudicated: bool = False
    out_of_scope: bool = False


@dataclass(slots=True)
class _RecordCounts:
    carried: int = 0
    adjudicated: int = 0
    out_of_scope: int = 0


def _emit_record(
    spec: WaveSpec,
    sheets: Mapping[str, RecordDesignSheet],
    segmento: str,
    report: GenerationReport,
) -> None:
    sheet = sheets.get(segmento)
    if sheet is None:
        raise GenerationRefusedError(f"{segmento}: no such sheet in the design")
    problems = audit_sheet(sheet, spec.declared_desglose_parents.get(segmento), spec.number_grammar)
    if problems:
        raise GenerationRefusedError("; ".join(problems))

    prior = load_prior_attributes(spec.prior_casillas_dir, segmento, spec.prior_glob)
    groups, hoisted = _group_design_rows(spec, segmento, sheet)
    emitted, counts = _emit_design_groups(spec, segmento, groups, prior, report)
    if report.refusals:
        return
    if not emitted:
        raise GenerationRefusedError(f"{segmento}: nothing emitted")
    report.outcomes.append(_record_outcome(spec, segmento, sheet, emitted, counts, hoisted))


def _group_design_rows(
    spec: WaveSpec,
    segmento: str,
    sheet: RecordDesignSheet,
) -> tuple[tuple[_DesignRowGroup, ...], frozenset[int]]:
    declared = cast(
        Mapping[int, tuple[int, ...]],
        spec.declared_desglose_parents.get(segmento, {}),
    )
    hoisted: frozenset[int] = frozenset(child for children in declared.values() for child in children)
    stem = spec.record_stems.get(segmento, segmento.lower())
    grouped: dict[str, list[RecordDesignField]] = {}
    captions: dict[str, str] = {}
    for candidate in sorted(sheet.fields, key=lambda item: item.offset):
        if candidate.offset in hoisted or is_structural(candidate.description):
            continue
        derived, caption = derive_number(
            candidate.description,
            candidate.offset,
            candidate.length,
            segmento,
            stem,
            spec.number_grammar,
        )
        number = spec.number_aliases.get(segmento, {}).get(derived, derived)
        if spec.collapse_rows_by_number:
            grouped.setdefault(number, []).append(candidate)
            captions.setdefault(number, caption)
        else:
            key = f"{number}@{candidate.offset}"
            grouped[key] = [candidate]
            captions[key] = caption
    groups = tuple(
        _DesignRowGroup(
            number=key if spec.collapse_rows_by_number else key.split("@")[0],
            caption=captions[key],
            members=tuple(members),
        )
        for key, members in grouped.items()
    )
    return groups, hoisted


def _emit_design_groups(
    spec: WaveSpec,
    segmento: str,
    groups: Sequence[_DesignRowGroup],
    prior: Mapping[str, Mapping[str, str]],
    report: GenerationReport,
) -> tuple[list[str], _RecordCounts]:
    emitted: list[str] = []
    counts = _RecordCounts()
    stem = spec.record_stems.get(segmento, segmento.lower())
    for group in groups:
        outcome = _emit_design_group(spec, segmento, stem, group, prior, report)
        if outcome.text is not None:
            emitted.append(outcome.text)
        counts.carried += outcome.carried
        counts.adjudicated += outcome.adjudicated
        counts.out_of_scope += outcome.out_of_scope
    return emitted, counts


def _emit_design_group(
    spec: WaveSpec,
    segmento: str,
    stem: str,
    group: _DesignRowGroup,
    prior: Mapping[str, Mapping[str, str]],
    report: GenerationReport,
) -> _RowEmission:
    row = group.members[0]
    disposition = _candidate_disposition(spec, segmento, stem, row, group.number)
    if disposition == "out_of_scope":
        return _RowEmission(out_of_scope=True)
    if disposition == "deferred":
        report.deferred.append(
            f"{segmento}:{group.number} @{row.offset}+{row.length} "
            f"({len(group.members)} printed row(s)) {group.caption[:64]}"
        )
        return _RowEmission()
    attributes = _row_attributes(spec, segmento, group, prior, report)
    if attributes is None:
        return _RowEmission()
    return _render_group(spec, segmento, group, attributes)


def _candidate_disposition(
    spec: WaveSpec,
    segmento: str,
    stem: str,
    row: RecordDesignField,
    number: str,
) -> str | None:
    if row.offset in spec.scope_skip_positions.get(segmento, frozenset()):
        return "out_of_scope"
    if number.startswith(f"{stem}.") and segmento in spec.scope_skip_unnumbered:
        return "out_of_scope"
    if number in spec.scope_declined_numbers.get(segmento, frozenset()):
        return "out_of_scope"
    if number in spec.deferred_numbers.get(segmento, frozenset()):
        return "deferred"
    return None


def _row_attributes(
    spec: WaveSpec,
    segmento: str,
    group: _DesignRowGroup,
    prior: Mapping[str, Mapping[str, str]],
    report: GenerationReport,
) -> _RowAttributes | None:
    number = group.number
    carry_key = spec.carry_number_aliases.get(segmento, {}).get(number, number)
    if carry_key in prior:
        return _carried_attributes(spec, segmento, group, prior[carry_key], report)
    if segmento in spec.adjudicated_sections and spec.id_scheme == "segmento_number":
        return _adjudicated_attributes(spec, segmento, group)
    row = group.members[0]
    report.refusals.append(f"{segmento}:{number} @{row.offset}+{row.length} {group.caption[:70]}")
    return None


def _carried_attributes(
    spec: WaveSpec,
    segmento: str,
    group: _DesignRowGroup,
    attributes: Mapping[str, str],
    report: GenerationReport,
) -> _RowAttributes:
    row = group.members[0]
    section = attributes["section"]
    data_type = attributes["data_type"]
    casilla_id = attributes.get("id") or f"{segmento}:{group.number}"
    row_segmento = attributes.get("segmento") or None
    legal_refs = spec.legal_refs
    if spec.carry_legal_refs and attributes.get("legal_refs"):
        legal_refs = attributes["legal_refs"]
    _record_drift(segmento, group.number, row, group.caption, attributes.get("_caption", ""), report)
    return _RowAttributes(
        section=section,
        data_type=data_type,
        casilla_id=casilla_id,
        segmento=row_segmento,
        legal_refs=legal_refs,
        carried=True,
    )


def _adjudicated_attributes(spec: WaveSpec, segmento: str, group: _DesignRowGroup) -> _RowAttributes:
    row = group.members[0]
    tokens = spec.adjudicated_sections[segmento]
    section = "[" + ", ".join(f'"{token}"' for token in tokens) + "]"
    data_type = '"ratio"' if row.length in spec.ratio_lengths else '"money"'
    return _RowAttributes(
        section=section,
        data_type=data_type,
        casilla_id=f"{segmento}:{group.number}",
        segmento=segmento,
        legal_refs=spec.legal_refs,
        carried=False,
    )


def _record_drift(
    segmento: str,
    number: str,
    row: RecordDesignField,
    caption: str,
    prior_comment: str,
    report: GenerationReport,
) -> None:
    if not prior_comment:
        return
    prior_caption, _, prior_content = prior_comment.partition(" | ")
    current_caption, _, current_content = comment_line(row, caption).partition(" | ")
    if normalise_for_drift(prior_caption) != normalise_for_drift(current_caption):
        report.drift.append(
            f"{segmento}:{number} @{row.offset}+{row.length}\n"
            f"    prior: {prior_caption[2:].strip()[:96]}\n"
            f"    now:   {caption[:96]}"
        )
    elif prior_content and normalise_for_drift(prior_content) != normalise_for_drift(current_content):
        report.content_drift.append(
            f"{segmento}:{number} @{row.offset}+{row.length}\n"
            f"    prior contenido: {prior_content.strip()[:96]}\n"
            f"    now contenido:   {current_content.strip()[:96]}"
        )


def _render_group(
    spec: WaveSpec,
    segmento: str,
    group: _DesignRowGroup,
    attributes: _RowAttributes,
) -> _RowEmission:
    row = group.members[0]
    text = _render_row(
        members=group.members,
        revision_id=spec.revision_id,
        segmento=attributes.segmento,
        casilla_id=attributes.casilla_id,
        number=group.number,
        row=row,
        caption=group.caption,
        section=attributes.section,
        data_type=attributes.data_type,
        legal_refs=attributes.legal_refs,
    )
    return _RowEmission(text=text, carried=attributes.carried, adjudicated=not attributes.carried)


def _record_outcome(
    spec: WaveSpec,
    segmento: str,
    sheet: RecordDesignSheet,
    emitted: Sequence[str],
    counts: _RecordCounts,
    hoisted: frozenset[int],
) -> RecordOutcome:
    first = _filename_stem(emitted[0])
    last = _filename_stem(emitted[-1])
    filename = (
        f"c{segmento}+{first}__c{segmento}+{last}.toml"
        if spec.id_scheme == "segmento_number"
        else f"c{first}__c{last}.toml"
    )
    body = spec.headers[segmento] + "\n\n" + "\n".join(emitted)
    tiled = sum(row.length for row in sheet.fields if row.offset not in hoisted)
    return RecordOutcome(
        segmento=segmento,
        filename=filename,
        emitted=len(emitted),
        carried=counts.carried,
        adjudicated=counts.adjudicated,
        out_of_scope=counts.out_of_scope,
        tiled=tiled,
        declared_total=sheet.total_positions or tiled,
        body=body,
    )
