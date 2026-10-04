"""Capture and compare immutable execution inputs for the final portable cohorts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUFFIXES = {
    ".py",
    ".toml",
    ".json",
    ".yaml",
    ".yml",
    ".pdf",
    ".svg",
    ".html",
    ".txt",
    ".xlsx",
    ".csv",
    ".rs",
    ".cpp",
    ".h",
    ".cmake",
}


def digest(path: Path) -> str:
    """Hash the exact current file bytes without exposing their contents."""
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def capture(output: Path, head: str) -> None:
    """Record source/configuration and published authority inputs before or after execution."""
    listed = [
        path.relative_to(ROOT).as_posix()
        for directory in (ROOT / "src", ROOT / "dev", ROOT / ".codex/rules")
        for path in directory.rglob("*")
        if path.is_file()
    ]
    paths = {
        path.replace("\\", "/")
        for path in listed
        if Path(path).suffix in SUFFIXES or path.replace("\\", "/").startswith(".codex/rules")
    }
    paths.update(
        name
        for name in (
            "pyproject.toml",
            "uv.lock",
            "justfile",
            "conftest.py",
            "AGENTS.md",
            "CMakeLists.txt",
            "CMakePresets.json",
        )
        if (ROOT / name).is_file()
    )
    hashes = {name: digest(ROOT / name) for name in sorted(paths)}
    descriptor_path = ROOT / ".authority/authority.current.json"
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    database = descriptor_path.parent / descriptor["database"]
    database_hash = digest(database)
    if database_hash != descriptor["database_sha256"]:
        raise RuntimeError("published authority database hash does not match its descriptor")
    document = {
        "captured_at": datetime.now(UTC).isoformat(),
        "head": head,
        "source_sha256": hashes,
        "source_aggregate_sha256": hashlib.sha256(
            json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "authority_descriptor": descriptor,
        "authority_descriptor_sha256": digest(descriptor_path),
        "authority_database_sha256": database_hash,
        "controlled_environment": {
            "CADRUMO_AUTHORITY_ROOT": str(descriptor_path.parent),
            "CADRUMO_PLAYWRIGHT_BROWSERS_DIR": str(ROOT / "var/storage/components/playwright"),
        },
    }
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(
        f"Captured {len(hashes)} source/config/resource inputs; authority {descriptor['logical_generation']}\n"
    )


def compare(before: Path, after: Path, output: Path) -> bool:
    """Report exact source and authority drift instead of accepting stale execution evidence."""
    first = json.loads(before.read_text(encoding="utf-8"))
    last = json.loads(after.read_text(encoding="utf-8"))
    a, b = first["source_sha256"], last["source_sha256"]
    changed = [name for name in sorted(a.keys() | b.keys()) if a.get(name) != b.get(name)]
    authority_changed = first["authority_descriptor"] != last["authority_descriptor"]
    result = {
        "before": str(before),
        "after": str(after),
        "source_changed_paths": changed,
        "authority_changed": authority_changed,
        "head_changed": first["head"] != last["head"],
        "stable_execution_inputs": not changed and not authority_changed,
    }
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(f"Input stability: {result['stable_execution_inputs']}; {len(changed)} changed source paths\n")
    return result["stable_execution_inputs"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("capture", "compare"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--before", type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--head")
    args = parser.parse_args()
    if args.action == "capture":
        if args.head is None:
            parser.error("capture requires --head from the read-only Git observation")
        capture(args.output, args.head)
    else:
        if args.before is None or args.after is None:
            parser.error("compare requires --before and --after")
        raise SystemExit(0 if compare(args.before, args.after, args.output) else 2)
