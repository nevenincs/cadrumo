"""Pack registry declarations without changing their canonical authored value.

Each non-generated section is one TOML document. The compiler's own fragment
merge proves packing, including nested construct arrays and their order. Every
apply retains the original files in an exclusive backup and refuses concurrent
changes. Packing requires no legal inference and grants no filing capability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Mapping
from datetime import date, datetime, time
from pathlib import Path
from typing import cast

import rtoml

from .compiler.loader import load_modelo_declarations
from .transformation_proof import fingerprint_source_tree, prove_transformation, snapshot_definition


def plain(value: object) -> object:
    """Thaw compiler values without coercing TOML scalars."""
    if isinstance(value, Mapping):

        def is_table(item: object) -> bool:
            return isinstance(item, Mapping) or (
                isinstance(item, tuple | list) and any(isinstance(child, Mapping) for child in cast(list[object], item))
            )

        mapping = cast(Mapping[str, object], value)
        return {key: plain(item) for key, item in sorted(mapping.items(), key=lambda pair: is_table(pair[1]))}
    if isinstance(value, tuple | list):
        return [plain(item) for item in cast(list[object], value)]
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
    return {item.relative_path: item.sha256 for item in fingerprint_source_tree(directory).files}


def toml_comments(text: str) -> list[str]:
    """Retain full-line and trailing comments, but never hashes inside strings."""
    comments: list[str] = []
    quote = ""
    index = 0
    while index < len(text):
        if quote:
            if quote.startswith('"') and text[index] == "\\":
                index += 2
                continue
            if text.startswith(quote, index):
                index += len(quote)
                quote = ""
                continue
        elif text[index] in {"'", '"'}:
            quote = text[index] * (3 if text.startswith(text[index] * 3, index) else 1)
            index += len(quote)
            continue
        elif text[index] == "#":
            end = text.find("\n", index)
            if end < 0:
                end = len(text)
            comments.append(text[index:end].rstrip("\r"))
            index = end
        index += 1
    return comments


def retire_source_default_tables(text: str) -> str:
    """Remove only the retired manifest tables, retaining other text in place."""
    kept: list[str] = []
    dropping = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("["):
            dropping = bool(
                re.match(r'^\s*\[\[?revisions\.(?:"[^"]+"|[\w-]+)\.source_default_dispositions(?:[.\]])', line)
            )
        if not dropping:
            kept.append(line)
    return "".join(kept)


def field_count(value: object) -> int:
    """Count authored key occurrences, including nested member fields."""
    if isinstance(value, Mapping):
        return sum(1 + field_count(item) for item in cast(Mapping[str, object], value).values())
    if isinstance(value, tuple | list):
        return sum(field_count(item) for item in cast(list[object], value))
    return 0


def replace_if_unchanged(target: Path, replacement: Path | None, expected: str | None) -> None:
    """Capture the actual destination before comparison; never overwrite a racer.

    Hard-link installation is atomic and fails if a concurrent writer creates
    the destination during the capture/install gap. Displaced conflicting bytes
    remain recoverable, including when restoring their original name is unsafe.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".packing-", delete=False) as stream:
        pending = Path(stream.name)
    displaced: Path | None = None
    try:
        if replacement is not None:
            shutil.copy2(replacement, pending)
        if expected is not None:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".packing-displaced-", delete=False) as stream:
                displaced = Path(stream.name)
            displaced.unlink()
            target.rename(displaced)
            if hashlib.sha256(displaced.read_bytes()).hexdigest() != expected:
                raise ValueError(f"concurrent edit captured at {displaced}")
        if replacement is not None:
            os.link(pending, target)
        elif target.exists():
            raise ValueError(f"concurrent file appeared at {target}")
    except BaseException:
        if displaced is not None and displaced.exists():
            try:
                os.link(displaced, target)
            except FileExistsError as exc:
                raise ValueError(
                    f"concurrent target preserved at {target}; displaced bytes retained at {displaced}"
                ) from exc
            displaced.unlink()
        raise
    else:
        if displaced is not None:
            # Open handles can still edit the captured inode. Never discard
            # those bytes merely because the installed target is correct.
            if hashlib.sha256(displaced.read_bytes()).hexdigest() != expected:
                raise ValueError(f"captured source changed during installation; retained at {displaced}")
            displaced.unlink()
    finally:
        pending.unlink(missing_ok=True)


def publish_staged_tree(directory: Path, staged: Path, originals: Path, before: dict[str, str]) -> None:
    """Publish exact file changes, rolling back our own writes on any late refusal.

    Recovery never overwrites a concurrent writer's bytes. An interruption or an
    overlapping edit is recoverable from ``originals``; no claim of filesystem
    atomicity is made across multiple files.
    """
    after = fingerprint(staged)
    if fingerprint(directory) != before:
        raise ValueError("source changed before publication; nothing published")
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    completed: list[str] = []
    try:
        for name in changed:
            target = directory / name
            actual = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
            if actual != before.get(name):
                raise ValueError(f"concurrent edit at {target}")
            completed.append(name)
            replace_if_unchanged(target, staged / name if name in after else None, before.get(name))
        if fingerprint(directory) != after:
            raise ValueError("source changed during publication")
    except BaseException as exc:
        conflicts: list[str] = []
        for name in reversed(completed):
            target = directory / name
            actual = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
            if actual != after.get(name):
                conflicts.append(name)
                continue
            try:
                replace_if_unchanged(target, originals / name if name in before else None, after.get(name))
            except (OSError, ValueError) as recovery_error:
                conflicts.append(f"{name}: {recovery_error}")
        raise ValueError(
            f"publication refused: {exc}; prior writes rolled back except concurrent edits {conflicts}; "
            f"original backup retained at {originals}"
        ) from exc


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
    expected = cast(dict[str, object], plain(before))
    work.mkdir(parents=True)
    staged = work / "staged"
    shutil.copytree(directory, staged)
    originals = work / "original"
    shutil.copytree(directory, originals)
    if fingerprint(originals) != before_files or fingerprint(directory) != before_files:
        raise ValueError("source changed while copying; nothing published")
    changed_sections: list[str] = []
    removed_fields: list[str] = []
    revisions = cast(Mapping[str, Mapping[str, object]], before["revisions"])
    expected_revisions = cast(dict[str, dict[str, object]], expected["revisions"])
    for revision_id, revision in revisions.items():
        edition = staged / "revisions" / revision_id
        manifest_path = edition / "revision.toml"
        if "source_default_dispositions" in revision:
            manifest = rtoml.load(manifest_path)
            del manifest["revisions"][revision_id]["source_default_dispositions"]
            del expected_revisions[revision_id]["source_default_dispositions"]
            text = retire_source_default_tables(manifest_path.read_text(encoding="utf-8-sig"))
            if canonical(rtoml.loads(text)) != canonical(manifest):
                raise ValueError("source-default table retirement changed another declaration")
            manifest_path.write_text(text, encoding="utf-8", newline="\n")
            removed_fields.append(f"{revision_id}.source_default_dispositions")
        for section in sorted(edition.iterdir()):
            if not section.is_dir() or section.name in {"locales", "export"}:
                continue
            paths = sorted(section.glob("*.toml"), key=lambda path: path.as_posix())
            if not paths:
                continue
            value = revision[section.name]
            target = section / "0001-declarations.toml"
            # Comments can contain evidence locations not yet enrolled as fields.
            # Preserve them until their owning adjudication decides their fate.
            text = "\n".join(path.read_text(encoding="utf-8-sig").rstrip() for path in paths) + "\n"
            try:
                parsed = rtoml.loads(text)["revisions"][revision_id][section.name]
                needs_merge = canonical(parsed) != canonical(value)
            except rtoml.TomlParsingError:
                needs_merge = True
            if needs_merge:
                # Singleton-table fragments repeat headers. Keep comment context
                # alongside the canonical merged declaration instead of losing it.
                context: list[str] = []
                for path in paths:
                    original = path.read_text(encoding="utf-8-sig")
                    if toml_comments(original):
                        context.extend(
                            [f"# Original commentary: {path.name}", *[f"# {line}" for line in original.splitlines()]]
                        )
                text = rtoml.dumps(plain({"revisions": {revision_id: {section.name: value}}}))
                if context:
                    text = "\n".join(context) + "\n\n" + text
            if len(paths) == 1 and paths[0] == target and target.read_text(encoding="utf-8") == text:
                continue
            target.write_text(text, encoding="utf-8", newline="\n")
            for path in paths:
                if path != target:
                    path.unlink()
            changed_sections.append(f"{revision_id}/{section.name}")
    after = load_modelo_declarations(staged)
    before_value, after_value = canonical(expected), canonical(after)
    proof = prove_transformation(
        snapshot_definition(expected, locale_fields={}),
        snapshot_definition(after, locale_fields={}),
    )
    if not proof.is_equivalent or before_value != after_value:
        raise ValueError(f"canonical authored declarations changed at {proof.first_mismatch}; nothing published")
    after_files = fingerprint(staged)
    if fingerprint(directory) != before_files:
        raise ValueError("source changed during proof; nothing published")
    writes = {name for name, digest in after_files.items() if before_files.get(name) != digest}
    deletes = before_files.keys() - after_files.keys()
    result: dict[str, object] = {
        "modelo": directory.name,
        "before_files": sum(name.endswith(".toml") for name in before_files),
        "after_files": sum(name.endswith(".toml") for name in after_files),
        "authored_fields": field_count(before),
        "after_authored_fields": field_count(after),
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
        publish_staged_tree(directory, staged, originals, before_files)
        if fingerprint(directory) != after_files or canonical(load_modelo_declarations(directory)) != before_value:
            raise ValueError("published tree changed during final proof; original backup retained")
        result["applied"] = True
        (work / "proof.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    """Rehearse or apply proven packing and retain every per-modelo receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-root", type=Path, default=Path("src/cadrumo/_data/registry/aeat"))
    parser.add_argument("--modelo", action="append")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = args.registry_root.resolve()
    work = Path(tempfile.mkdtemp(prefix="cadrumo-registry-pack-"))
    print(json.dumps({"work": str(work)}), flush=True)
    results: list[dict[str, object]] = []
    for directory in sorted((root / "modelos").iterdir()):
        if not directory.is_dir() or (args.modelo and directory.name not in args.modelo):
            continue
        try:
            result = pack_modelo(directory, work / directory.name, apply=args.apply)
            results.append(result)
            print(
                json.dumps(
                    {
                        key: value
                        for key, value in result.items()
                        if key
                        not in {"before_fingerprint", "after_fingerprint", "writes", "deletes", "changed_sections"}
                    }
                ),
                flush=True,
            )
        except Exception as exc:
            failure: dict[str, object] = {"modelo": directory.name, "error": f"{type(exc).__name__}: {exc}"}
            results.append(failure)
            print(json.dumps(failure), flush=True)
            if args.apply:
                break
    (work / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return int(any("error" in result for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
