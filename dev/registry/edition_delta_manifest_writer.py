"""Write proven edition-level delta declarations into authored TOML."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation

from . import edition_delta_errors as _edition_delta_errors
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
    storage_operations = bool(plan.casilla_overrides or plan.casilla_removals or plan.casilla_positions)
    if not additions and not plan.lineage_attestations and not storage_operations:
        return
    text = path.read_text(encoding="utf-8")
    text = _replace_technical_root(text, path, additions, work)
    text = _insert_additions(text, path, additions, work)
    text = _append_lineage_attestations(text, plan.lineage_attestations)
    text = _append_casilla_storage_operations(text, plan)
    path.write_text(text, encoding="utf-8", newline="\n")


__all__ = ("_append_lineage_attestations", "write_manifest")
