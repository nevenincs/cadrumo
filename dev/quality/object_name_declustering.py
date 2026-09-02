"""Safe command-line orchestration for reviewed object-name declustering."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, Final, cast

from pydantic import TypeAdapter, ValidationError

from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.link_safety import is_link_like

from ..audit.object_names import exit_code, scan, to_json
from .object_name_graph import ObjectNameGraphError
from .object_name_manifest import ObjectNameManifestError, load_validated_object_name_manifest
from .object_name_rehearsal import (
    ObjectNameRehearsalError,
    ObjectNameRehearsalReceipt,
    canonical_object_name_component_set,
    rehearse_object_name_component,
)
from .object_name_replay import (
    ObjectNameReplayError,
    _validate_receipt_integrity,  # pyright: ignore[reportPrivateUsage]
    replay_object_name_component,
)

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
        if is_link_like(path) or not path.is_file():
            raise ObjectNameDeclusteringCliError(f"receipt must be a regular file: {path}")
        payload = path.read_bytes()
        decoded = cast("object", json.loads(payload))
        if not isinstance(decoded, dict):
            raise ObjectNameDeclusteringCliError("receipt schema must be an object")
        fields = cast("dict[str, object]", decoded)
        if set(fields) != set(ObjectNameRehearsalReceipt.__dataclass_fields__):
            raise ObjectNameDeclusteringCliError("receipt schema fields are not exact")
        receipt = TypeAdapter(ObjectNameRehearsalReceipt).validate_json(payload, strict=True)
        _validate_receipt_integrity(receipt)
        return receipt
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ValidationError,
        KeyError,
        TypeError,
        ObjectNameReplayError,
    ) as exc:
        raise ObjectNameDeclusteringCliError(f"receipt file is invalid: {path}") from exc


def _manifest_path(root: Path, supplied: Path) -> Path:
    if supplied.is_absolute() or any(part in {"", ".", "..", ".git"} for part in supplied.parts):
        raise ObjectNameDeclusteringCliError("manifest path must be safe and repository-relative")
    candidate = root
    for part in supplied.parts:
        candidate /= part
        if is_link_like(candidate):
            raise ObjectNameDeclusteringCliError(f"manifest path traverses a link-like component: {supplied}")
    if not candidate.is_file():
        raise ObjectNameDeclusteringCliError(f"manifest path is not a regular file: {supplied}")
    return candidate


def _context(root: Path, manifest_path: Path):
    inventory = scan((root / "src", root / "dev"), root)
    manifest = load_validated_object_name_manifest(manifest_path, inventory=inventory, repo_root=root)
    components = canonical_object_name_component_set(manifest, inventory=inventory, repo_root=root)
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
        if args.mode == "verify":
            inventory = scan((root / "src", root / "dev"), root)
            _emit({"inventory": to_json(inventory), "mode": "verify"}, as_json=args.json)
            return exit_code(inventory)
        inventory, manifest, component = _context(root, _manifest_path(root, args.manifest))
        if args.mode == "plan":
            _emit({"component": asdict(component), "mode": "plan"}, as_json=args.json)
            return 0
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
