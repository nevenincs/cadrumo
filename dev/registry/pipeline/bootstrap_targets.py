"""Read reviewed generated-export bootstrap target declarations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, cast

from cadrumo.core.toml import parse_toml

__all__ = ["GeneratedExportBootstrapTarget", "generated_export_bootstrap_target"]

_BOOTSTRAP_TARGETS_PATH: Final[Path] = Path(__file__).with_name("generated_export_bootstrap_targets.toml")


@dataclass(frozen=True, slots=True)
class GeneratedExportBootstrapTarget:
    """One reviewed transport and supersession declaration for an unpublished tree."""

    modelo: str
    revision: str
    source_ref: str
    source_sha256: str
    layout_id: str
    line_ending: Literal["crlf", "lf", "none"]
    supersedes_layout_id: str | None
    superseded_construct_references: int
    manual_origin_revision: str | None = None


def generated_export_bootstrap_target(
    *,
    modelo: str,
    revision: str,
    source_ref: str,
    source_sha256: str,
) -> GeneratedExportBootstrapTarget | None:
    """Return the uniquely matching reviewed bootstrap declaration, if one exists."""
    payload = parse_toml(_BOOTSTRAP_TARGETS_PATH.read_text("utf-8"))
    matches = _matching_bootstrap_targets(
        payload,
        modelo=modelo,
        revision=revision,
        source_ref=source_ref,
        source_sha256=source_sha256,
    )
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError(f"multiple generated-export bootstrap targets match {modelo}/{revision}/{source_ref}")
    return _bootstrap_target_from_row(matches[0])


def _matching_bootstrap_targets(
    payload: Mapping[str, object],
    *,
    modelo: str,
    revision: str,
    source_ref: str,
    source_sha256: str,
) -> list[Mapping[str, object]]:
    targets = cast(list[Mapping[str, object]], payload.get("targets", []))
    return [
        row
        for row in targets
        if row.get("modelo") == modelo
        and row.get("revision") == revision
        and row.get("source_ref") == source_ref
        and row.get("source_sha256") == source_sha256
    ]


def _bootstrap_target_from_row(row: Mapping[str, object]) -> GeneratedExportBootstrapTarget:
    accepted_line_ending = _accepted_bootstrap_line_ending(row)
    supersedes_layout_id = _validated_superseded_layout_id(row)
    superseded_construct_references = _validated_superseded_construct_references(row, supersedes_layout_id)
    manual_origin_revision = _validated_manual_origin_revision(row, supersedes_layout_id)
    return GeneratedExportBootstrapTarget(
        modelo=str(row["modelo"]),
        revision=str(row["revision"]),
        source_ref=str(row["source_ref"]),
        source_sha256=str(row["source_sha256"]),
        layout_id=str(row["layout_id"]),
        line_ending=accepted_line_ending,
        supersedes_layout_id=supersedes_layout_id,
        superseded_construct_references=superseded_construct_references,
        manual_origin_revision=manual_origin_revision,
    )


def _accepted_bootstrap_line_ending(row: Mapping[str, object]) -> Literal["crlf", "lf", "none"]:
    line_ending = row.get("line_ending")
    if line_ending not in {"crlf", "lf", "none"}:
        raise ValueError("reviewed generated-export bootstrap target has invalid line ending")
    return cast(Literal["crlf", "lf", "none"], line_ending)


def _validated_superseded_layout_id(row: Mapping[str, object]) -> str | None:
    supersedes_layout_id = row.get("supersedes_layout_id")
    if supersedes_layout_id is not None and (not isinstance(supersedes_layout_id, str) or not supersedes_layout_id):
        raise ValueError("reviewed generated-export bootstrap target has invalid superseded layout id")
    return supersedes_layout_id


def _validated_superseded_construct_references(row: Mapping[str, object], supersedes_layout_id: str | None) -> int:
    references = row.get("superseded_construct_references", 0)
    if not isinstance(references, int) or references < 0:
        raise ValueError("reviewed generated-export bootstrap target has invalid superseded construct-reference count")
    if supersedes_layout_id is None and references != 0:
        raise ValueError("reviewed generated-export bootstrap target must pair its superseded layout and references")
    return references


def _validated_manual_origin_revision(row: Mapping[str, object], supersedes_layout_id: str | None) -> str | None:
    manual_origin_revision = row.get("manual_origin_revision")
    if manual_origin_revision is not None and (
        not isinstance(manual_origin_revision, str) or not manual_origin_revision or supersedes_layout_id is None
    ):
        raise ValueError("reviewed generated-export bootstrap target has invalid manual origin revision")
    return manual_origin_revision
