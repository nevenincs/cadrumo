"""Write proven edition-level delta declarations into authored TOML."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation

from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_row_delta_common as _edition_delta_row_delta_common
from . import edition_delta_source as _edition_delta_source
from . import edition_delta_toml_writer as _edition_delta_toml_writer
from . import edition_delta_types as _edition_delta_types


def _additions(work: _edition_delta_source._EditionWork) -> dict[str, object]:
    additions = _revision_additions(work)
    additions.update(_family_default_additions(work))
    return additions


def _revision_additions(work: _edition_delta_source._EditionWork) -> dict[str, object]:
    plan, manifest = work.plan, work.source.manifest
    additions: dict[str, object] = {}
    if plan.predecessor is not None and plan.basis is _edition_delta_types.PredecessorBasis.ADJACENT:
        additions["predecessor"] = plan.predecessor
    if (
        plan.predecessor is not None
        and plan.basis is _edition_delta_types.PredecessorBasis.STORAGE
        and "casilla_storage_baseline" not in manifest
    ):
        additions["casilla_storage_baseline"] = plan.predecessor
    if work.root_declaration is not None:
        additions["predecessor"] = work.root_declaration
    if plan.source_default is not None and "casilla_source_refs" not in manifest:
        additions["casilla_source_refs"] = list(plan.source_default)
    return additions


def _family_default_additions(work: _edition_delta_source._EditionWork) -> dict[str, object]:
    additions: dict[str, object] = {}
    manifest = work.source.manifest
    for key, default in sorted(work.source.family_defaults.items()):
        if key not in manifest:
            additions[key] = list(default)
    return additions


def _replace_technical_root(
    text: str, path: Path, additions: Mapping[str, object], work: _edition_delta_source._EditionWork
) -> str:
    if "predecessor" not in additions or not isinstance(work.source.manifest.get("predecessor"), Mapping):
        return text
    text, removed = re.subn(r"(?m)^predecessor\s*=.*(?:\r?\n|$)", "", text, count=1)
    if removed != 1:
        raise _edition_delta_errors.MigrationRefusedError(f"{path}: cannot replace the technical predecessor root")
    return text


def _insert_additions(
    text: str, path: Path, additions: Mapping[str, object], work: _edition_delta_source._EditionWork
) -> str:
    header = re.compile(
        rf'^\[revisions\.(?:"{re.escape(work.plan.revision_id)}"|{re.escape(work.plan.revision_id)})\][ \t]*\r?\n',
        re.MULTILINE,
    )
    match = header.search(text)
    if match is None:
        raise _edition_delta_errors.MigrationRefusedError(
            f"{path}: no [revisions.{work.plan.revision_id!r}] header to declare under"
        )
    inserted = "".join(f"{key} = {_edition_delta_toml_writer.toml_value(value)}\n" for key, value in additions.items())
    rewritten = text[: match.end()] + inserted + text[match.end() :]
    expected = {**work.source.manifest, **additions}
    if _edition_delta_source._manifest_table(rewritten, work.plan.revision_id) != expected:
        raise _edition_delta_errors.MigrationRefusedError(
            f"{path}: declaring {sorted(additions)!r} would change other manifest keys"
        )
    return rewritten


def _append_casilla_storage_operations(text: str, plan: _edition_delta_types.EditionPlan) -> str:
    """Append generated storage operations without reformatting authored TOML."""
    operation_groups = (
        ("casilla_overrides", plan.casilla_overrides),
        ("casilla_removals", plan.casilla_removals),
        ("casilla_positions", plan.casilla_positions),
    )
    for name, operations in operation_groups:
        text = _append_operation_group(text, plan.revision_id, name, operations)
    return text


def _append_operation_group(text: str, revision_id: str, name: str, operations: Sequence[Mapping[str, object]]) -> str:
    for operation in operations:
        block = [f'[[revisions."{revision_id}".{name}]]']
        block.extend(f"{key} = {_edition_delta_toml_writer.toml_value(value)}" for key, value in operation.items())
        text = text.rstrip() + "\n\n" + "\n".join(block) + "\n"
    return text


def _operation_header(revision_id: str, name: str) -> re.Pattern[str]:
    quoted = f'"{re.escape(revision_id)}"'
    bare = re.escape(revision_id)
    return re.compile(rf"^\[\[revisions\.(?:{quoted}|{bare})\.{re.escape(name)}\]\][ \t]*(?:#.*)?$")


def _operation_spans(lines: Sequence[str], header: re.Pattern[str]) -> list[tuple[int, int]]:
    starts = [index for index, line in enumerate(lines) if header.match(line.rstrip("\r\n"))]
    spans: list[tuple[int, int]] = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        for index in range(start + 1, end):
            if re.match(r"^[ \t]*\[\[?[^\]]+\]\]?[ \t]*(?:#.*)?(?:\r?\n)?$", lines[index]):
                end = index
                break
        spans.append((start, end))
    return spans


def _line_comment_suffix(value: str) -> str:
    in_string = False
    escaped = False
    for index, character in enumerate(value):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character == "#":
            return value[index:]
    return ""


def _rewrite_operation_fields(lines: list[str], span: tuple[int, int], replacement: Mapping[str, object]) -> None:
    start, end = span
    updates = {
        "fields": replacement.get("fields", {}),
        "removed_fields": replacement.get("removed_fields", ()),
    }
    found: set[str] = set()
    assignment = re.compile(r"^([ \t]*)(fields|removed_fields)([ \t]*=[ \t]*)(.*?)(\r?\n)?$")
    for index in range(start + 1, end):
        match = assignment.match(lines[index])
        if match is None or match.group(2) not in updates:
            continue
        key = match.group(2)
        original_value = match.group(4)
        comment = _line_comment_suffix(original_value)
        newline = match.group(5) or ""
        lines[index] = (
            f"{match.group(1)}{key}{match.group(3)}"
            f"{_edition_delta_toml_writer.toml_value(updates[key])}"
            f"{(' ' if comment and not comment.startswith(' ') else '')}{comment}{newline}"
        )
        found.add(key)
    missing = [key for key in updates if key not in found]
    if missing:
        insertion = end
        while insertion > start + 1 and not lines[insertion - 1].strip():
            insertion -= 1
        new_lines = [f"{key} = {_edition_delta_toml_writer.toml_value(updates[key])}\n" for key in missing]
        lines[insertion:insertion] = new_lines


def _replace_authored_overrides(text: str, work: _edition_delta_source._EditionWork) -> str:
    replacements = work.casilla_override_replacements
    if not replacements:
        return text
    revision_id = work.plan.revision_id
    authored = _edition_delta_row_delta_common.manifest_operations(work.source.manifest, "casilla_overrides")
    lines = text.splitlines(keepends=True)
    spans = _operation_spans(lines, _operation_header(revision_id, "casilla_overrides"))
    if len(spans) != len(authored):
        raise _edition_delta_errors.MigrationRefusedError(
            f"{work.source.revision_id}: expected {len(authored)} authored casilla override blocks, found {len(spans)}"
        )
    indexed: list[tuple[int, Mapping[str, object]]] = []
    for replacement in replacements:
        selector = replacement.get("selector")
        matching = [index for index, operation in enumerate(authored) if operation.get("selector") == selector]
        if len(matching) != 1:
            raise _edition_delta_errors.MigrationRefusedError(
                f"{work.source.revision_id}: cannot locate exactly one authored override for selector {selector!r}"
            )
        indexed.append((matching[0], replacement))
    for operation_index, replacement in sorted(indexed, key=lambda item: spans[item[0]][0], reverse=True):
        _rewrite_operation_fields(
            lines,
            _operation_spans(lines, _operation_header(revision_id, "casilla_overrides"))[operation_index],
            replacement,
        )
    rewritten = "".join(lines)
    actual = _edition_delta_row_delta_common.manifest_operations(
        _edition_delta_source._manifest_table(rewritten, revision_id), "casilla_overrides"
    )
    for replacement in replacements:
        selector = replacement.get("selector")
        matches = [operation for operation in actual if operation.get("selector") == selector]
        if len(matches) != 1 or dict(matches[0]) != dict(replacement):
            raise _edition_delta_errors.MigrationRefusedError(
                f"{work.source.revision_id}: rewriting authored override {selector!r} changed its parsed operation"
            )
    return rewritten


def _append_lineage_attestations(text: str, attestations: Sequence[LineageAttestation]) -> str:
    """Append canonical TOML for claims that moved out of complete rows."""
    for attestation in attestations:
        block = _attestation_lines(attestation)
        text = text.rstrip() + "\n\n" + "\n".join(block) + "\n"
    return text


def _attestation_lines(attestation: LineageAttestation) -> list[str]:
    block = [
        f'[[revisions."{attestation.to_revision}".lineage_attestations]]',
        f"family = {json.dumps(attestation.family, ensure_ascii=False)}",
        f"continuidad_id = {json.dumps(attestation.identity, ensure_ascii=False)}",
        f"from_revision = {json.dumps(str(attestation.from_revision), ensure_ascii=False)}",
        f"to_revision = {json.dumps(str(attestation.to_revision), ensure_ascii=False)}",
        f"origin = {json.dumps(attestation.origin.value, ensure_ascii=False)}",
    ]
    if attestation.evidence is not None:
        block.append(f"evidence = {json.dumps(attestation.evidence, ensure_ascii=False)}")
    block.extend(
        (
            f"legal_refs = {json.dumps(list(attestation.legal_refs), ensure_ascii=False)}",
            f"source_refs = {json.dumps(list(attestation.source_refs), ensure_ascii=False)}",
        )
    )
    return block


def write_manifest(path: Path, work: _edition_delta_source._EditionWork) -> None:
    """Add only declarations whose whole-chain proof succeeded."""
    plan = work.plan
    additions = _additions(work)
    storage_operations = bool(
        plan.casilla_overrides or plan.casilla_removals or plan.casilla_positions or work.casilla_override_replacements
    )
    if not additions and not plan.lineage_attestations and not storage_operations:
        return
    text = path.read_text(encoding="utf-8")
    text = _replace_technical_root(text, path, additions, work)
    text = _insert_additions(text, path, additions, work)
    text = _replace_authored_overrides(text, work)
    text = _append_lineage_attestations(text, plan.lineage_attestations)
    text = _append_casilla_storage_operations(text, plan)
    path.write_text(text, encoding="utf-8", newline="\n")


__all__ = ("_append_lineage_attestations", "write_manifest")
