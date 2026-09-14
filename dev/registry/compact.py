"""Pack registry declarations without changing their canonical authored value.

Each non-generated section is one TOML document. The compiler's own fragment
merge proves packing, including nested construct arrays and their order. Every
apply retains the original files in an exclusive backup and refuses concurrent
changes. Packing requires no legal inference and grants no filing capability.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import date, datetime, time
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import rtoml

from .compiler.loader import load_modelo_declarations


def plain(value: object) -> object:
    """Thaw compiler values without coercing TOML scalars."""
    if isinstance(value, Mapping):
        def is_table(item: object) -> bool:
            return isinstance(item, Mapping) or (
                isinstance(item, tuple | list) and any(isinstance(child, Mapping) for child in item)
            )
        return {key: plain(item) for key, item in sorted(value.items(), key=lambda pair: is_table(pair[1]))}
    if isinstance(value, tuple | list):
        return [plain(item) for item in value]
    return value


def canonical(value: object) -> str:
    """Encode exact scalar kinds and sequence order for equality."""
    def encode(item: object) -> object:
        if isinstance(item, datetime | date | time):
            return {"$toml_type": type(item).__name__, "value": item.isoformat()}
        raise TypeError(f"unsupported declaration scalar {type(item).__name__}")

    return json.dumps(plain(value), default=encode, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def fingerprint(directory: Path) -> dict[str, str]:
    """Identify the complete input set, including non-TOML provenance."""
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def field_count(value: object) -> int:
    if isinstance(value, Mapping):
        return sum(1 + field_count(item) for item in value.values())
    if isinstance(value, tuple | list):
        return sum(field_count(item) for item in value)
    return 0


def pack_modelo(directory: Path, work: Path, *, apply: bool = False) -> dict[str, object]:
    """Stage and prove one modelo; preserve originals before changing live files."""
    directory = directory.resolve(strict=True)
    work = work.resolve()
    if not (directory / "manifest.toml").is_file():
        raise ValueError(f"not a modelo directory: {directory}")
    if work.is_relative_to(directory) or directory.is_relative_to(work) or work.exists():
        raise ValueError("work must be a new directory outside the modelo and its ancestors")
    before_files = fingerprint(directory)
    before = load_modelo_declarations(directory)
    expected = plain(before)
    work.mkdir(parents=True)
    staged = work / "staged"
    shutil.copytree(directory, staged)
    originals = work / "original"
    shutil.copytree(directory, originals)
    if fingerprint(originals) != before_files or fingerprint(directory) != before_files:
        raise ValueError("source changed while copying; nothing published")
    changed_sections: list[str] = []
    removed_fields: list[str] = []
    for revision_id, revision in before["revisions"].items():
        edition = staged / "revisions" / revision_id
        manifest_path = edition / "revision.toml"
        if "source_default_dispositions" in revision:
            manifest = rtoml.load(manifest_path)
            del manifest["revisions"][revision_id]["source_default_dispositions"]
            del expected["revisions"][revision_id]["source_default_dispositions"]
            manifest_path.write_text(rtoml.dumps(plain(manifest)), encoding="utf-8", newline="\n")
            removed_fields.append(f"{revision_id}.source_default_dispositions")
        for section in sorted(edition.iterdir()):
            if not section.is_dir() or section.name in {"locales", "export"}:
                continue
            paths = sorted(section.glob("*.toml"))
            if not paths:
                continue
            value = revision[section.name]
            target = section / "0001-declarations.toml"
            # Comments can contain evidence locations not yet enrolled as fields.
            # Preserve them until their owning adjudication decides their fate.
            comments = [
                line for path in paths for line in path.read_text(encoding="utf-8-sig").splitlines()
                if line.lstrip().startswith("#")
            ]
            text = rtoml.dumps(plain({"revisions": {revision_id: {section.name: value}}}))
            if comments:
                text = "\n".join(comments) + "\n\n" + text
            if len(paths) == 1 and paths[0] == target and target.read_text(encoding="utf-8") == text:
                continue
            target.write_text(text, encoding="utf-8", newline="\n")
            for path in paths:
                if path != target:
                    path.unlink()
            changed_sections.append(f"{revision_id}/{section.name}")
    after = load_modelo_declarations(staged)
    before_value, after_value = canonical(expected), canonical(after)
    if before_value != after_value:
        raise ValueError("canonical authored declarations changed; nothing published")
    after_files = fingerprint(staged)
    if fingerprint(directory) != before_files:
        raise ValueError("source changed during proof; nothing published")
    writes = {name for name, digest in after_files.items() if before_files.get(name) != digest}
    deletes = before_files.keys() - after_files.keys()
    result = {
        "modelo": directory.name,
        "before_files": sum(name.endswith(".toml") for name in before_files),
        "after_files": sum(name.endswith(".toml") for name in after_files),
        "authored_fields": field_count(before),
        "declarations_sha256": hashlib.sha256(before_value.encode()).hexdigest(),
        "equivalent": True,
        "applied": False,
        "changed_sections": changed_sections,
        "removed_obsolete_fields": removed_fields,
        "backup": str(originals),
        "before_fingerprint": before_files,
        "after_fingerprint": after_files,
        "writes": sorted(writes),
        "deletes": sorted(deletes),
    }
    (work / "proof.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    if apply:
        # Only exact paths captured above are replaced/deleted. Backups are
        # complete before the first write; untouched and new files are preserved.
        for name in sorted(writes):
            target = directory / name
            expected = before_files.get(name)
            actual = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
            if actual != expected:
                raise ValueError(f"concurrent edit at {target}; original backup retained")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged / name, target)
        for name in sorted(deletes):
            target = directory / name
            if hashlib.sha256(target.read_bytes()).hexdigest() != before_files[name]:
                raise ValueError(f"concurrent edit at {target}; original backup retained")
            target.unlink()
        if fingerprint(directory) != after_files or canonical(load_modelo_declarations(directory)) != before_value:
            raise ValueError("published tree changed during final proof; original backup retained")
        result["applied"] = True
        (work / "proof.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-root", type=Path, default=Path("src/cadrumo/_data/registry/aeat"))
    parser.add_argument("--modelo", action="append")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = args.registry_root.resolve()
    work = Path(tempfile.mkdtemp(prefix="cadrumo-registry-pack-"))
    print(json.dumps({"work": str(work)}), flush=True)
    results = []
    for directory in sorted((root / "modelos").iterdir()):
        if not directory.is_dir() or (args.modelo and directory.name not in args.modelo):
            continue
        try:
            result = pack_modelo(directory, work / directory.name, apply=args.apply)
            results.append(result)
            print(json.dumps({key: value for key, value in result.items() if key not in {
                "before_fingerprint", "after_fingerprint", "writes", "deletes", "changed_sections"
            }}), flush=True)
        except Exception as exc:
            result = {"modelo": directory.name, "error": f"{type(exc).__name__}: {exc}"}
            results.append(result)
            print(json.dumps(result), flush=True)
    (work / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return int(any("error" in result for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
