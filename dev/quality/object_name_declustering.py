"""Safe command-line orchestration for reviewed object-name declustering."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, Final, cast

from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.link_safety import is_link_like

from ..audit.object_names import exit_code, scan, to_json
from .object_name_graph import (
    InventoryLike,
    ObjectNameGraphError,
    RenameManifestLike,
    build_manifest_components,
    collect_import_edges,
    operation_locators,
)
from .object_name_manifest import ObjectNameManifestError, load_validated_object_name_manifest
from .object_name_rehearsal import (
    ObjectNameFindingDelta,
    ObjectNameGateOutcome,
    ObjectNameRehearsalError,
    ObjectNameRehearsalReceipt,
    rehearse_object_name_component,
)
from .object_name_replay import ObjectNameReplayError, replay_object_name_component

_DEFAULT_MANIFEST: Final[str] = "dev/quality/object_name_rename_manifest.toml"
_MODES: Final[tuple[str, ...]] = ("inventory", "plan", "rehearse", "apply", "verify")


class ObjectNameDeclusteringCliError(RuntimeError):
    """Expected operator-facing command refusal."""


def _repo_root(start: Path) -> Path:
    raw = start.absolute()
    for candidate in (raw, *raw.parents):
        if (candidate / ".git").is_dir() and (candidate / "src").is_dir() and (candidate / "dev").is_dir():
            current = candidate
            while current != current.parent:
                if is_link_like(current):
                    raise ObjectNameDeclusteringCliError(f"repository invocation path is link-like: {current}")
                current = current.parent
            return candidate
    raise ObjectNameDeclusteringCliError("cannot discover a repository worktree root")


def _receipt(path: Path) -> ObjectNameRehearsalReceipt:
    try:
        raw = cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))
        raw["finding_delta"] = ObjectNameFindingDelta(**raw["finding_delta"])
        raw["generator_outcomes"] = tuple(ObjectNameGateOutcome(**item) for item in raw["generator_outcomes"])
        raw["gate_outcomes"] = tuple(ObjectNameGateOutcome(**item) for item in raw["gate_outcomes"])
        for key in (
            "operation_ids", "baseline_files", "input_file_digests", "proposed_file_digests",
            "changed_paths", "tool_versions",
        ):
            values = cast("list[Any]", raw[key])
            raw[key] = tuple(tuple(cast("list[Any]", item)) if isinstance(item, list) else item for item in values)
        return ObjectNameRehearsalReceipt(**raw)
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ObjectNameDeclusteringCliError(f"receipt file is invalid: {path}") from exc


def _context(root: Path, manifest_path: Path):
    inventory = scan((root / "src", root / "dev"), root)
    manifest = load_validated_object_name_manifest(manifest_path, inventory=inventory, repo_root=root)
    graph_manifest = cast("RenameManifestLike", manifest)
    edges = collect_import_edges(operation_locators(graph_manifest), repo_root=root)
    components = build_manifest_components(
        graph_manifest, inventory=cast("InventoryLike", inventory), hard_edges=edges
    )
    if len(components) != 1:
        raise ObjectNameDeclusteringCliError(
            f"manifest must select exactly one complete component; found {len(components)}"
        )
    return inventory, manifest, components[0]


def _emit(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        sys.stdout.buffer.write(canonical_json_bytes(payload) + b"\n")
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=_MODES, default="rehearse")
    parser.add_argument("--manifest", type=Path, default=Path(_DEFAULT_MANIFEST))
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--receipt-id")
    parser.add_argument("--json", action="store_true", help="emit deterministic JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested safe mode and return one stable process exit code."""
    args = _parser().parse_args(argv)
    try:
        root = _repo_root(Path.cwd())
        if args.mode == "apply" and (args.receipt is None or not args.receipt_id):
            raise ObjectNameDeclusteringCliError("apply requires both --receipt and --receipt-id")
        if args.mode != "apply" and (args.receipt is not None or args.receipt_id is not None):
            raise ObjectNameDeclusteringCliError("receipt arguments are valid only in apply mode")
        apply_receipt = None
        if args.mode == "apply":
            if args.receipt is None or args.receipt_id is None:
                raise ObjectNameDeclusteringCliError("apply receipt arguments became unavailable")
            apply_receipt = _receipt(args.receipt)
            if apply_receipt.receipt_id != args.receipt_id:
                raise ObjectNameDeclusteringCliError("explicit receipt identity does not match the receipt file")
        if args.mode == "inventory":
            _emit(to_json(scan((root / "src", root / "dev"), root)), as_json=args.json)
            return 0
        manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
        inventory, manifest, component = _context(root, manifest_path)
        if args.mode == "plan":
            _emit({"component": asdict(component), "mode": "plan"}, as_json=args.json)
            return 0
        if args.mode == "verify":
            _emit({"inventory": to_json(inventory), "mode": "verify"}, as_json=args.json)
            return exit_code(inventory)
        if args.mode == "apply":
            if apply_receipt is None:
                raise ObjectNameDeclusteringCliError("apply receipt was not validated")
            result = replay_object_name_component(
                manifest, inventory=inventory, component=component, receipt=apply_receipt, repo_root=root
            )
            _emit({"mode": "apply", "result": asdict(result)}, as_json=args.json)
            return 0
        receipt = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=root)
        _emit({"mode": "rehearse", "receipt": asdict(receipt)}, as_json=args.json)
        return 0
    except (
        ObjectNameDeclusteringCliError,
        ObjectNameGraphError,
        ObjectNameManifestError,
        ObjectNameRehearsalError,
        ObjectNameReplayError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"object-name declustering refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
