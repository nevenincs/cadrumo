"""Elide explicit schema defaults only after complete typed equality is proved."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from collections.abc import Mapping
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Literal, cast, get_origin

import rtoml
from pydantic import BaseModel

from .compact import canonical, field_count, fingerprint, publish_staged_tree
from .compiler.loader import load_modelo_directory, modelo_fact_scope


def complete_value(value: object) -> object:
    """Read every model field, including fields excluded from JSON serialization."""
    if isinstance(value, BaseModel):
        return {name: complete_value(getattr(value, name)) for name in type(value).model_fields}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return {"$python_type": "Decimal", "value": str(value)}
    if isinstance(value, Mapping):
        return {key: complete_value(item) for key, item in cast(Mapping[str, object], value).items()}
    if isinstance(value, tuple | list):
        return [complete_value(item) for item in cast(list[object], value)]
    return value


def prune_defaults(raw: object, typed: object, removed: set[tuple[str, str]]) -> object:
    """Suggest scalar omissions from actual schema defaults, never from truthiness."""
    if isinstance(raw, dict):
        result: dict[str, object] = {}
        for name, value in cast(dict[str, object], raw).items():
            field = type(typed).model_fields.get(name) if isinstance(typed, BaseModel) else None
            current = (
                getattr(typed, name, None)
                if isinstance(typed, BaseModel)
                else (cast(Mapping[str, object], typed).get(name) if isinstance(typed, Mapping) else None)
            )
            if (
                field is not None
                and not field.is_required()
                and get_origin(field.annotation) is not Literal
                and isinstance(value, str | bool | int | float)
                and isinstance(field.default, str | bool | int | float)
                and canonical(value) == canonical(complete_value(field.default))
            ):
                removed.add((name, canonical(value)))
                continue
            result[name] = prune_defaults(value, current, removed)
        return result
    if isinstance(raw, list):
        items = cast(list[object], raw)
        typed_items = cast(list[object], typed) if isinstance(typed, tuple | list) else []
        by_id = {str(getattr(item, "id", None)): item for item in typed_items if hasattr(item, "id")}
        values: list[object] = []
        for index, item in enumerate(items):
            match = typed_items[index] if len(items) == len(typed_items) else None
            raw_item = item
            if isinstance(item, dict) and "id" in item:
                match = by_id.get(str(cast(dict[str, object], item)["id"]))
            values.append(prune_defaults(raw_item, match, removed))
        return values
    return raw


def elide_text(text: str, typed: Mapping[str, object]) -> tuple[str, int]:
    """Delete whole scalar lines only; refuse ambiguous inline or mixed occurrences."""
    raw = rtoml.loads(text)
    removed: set[tuple[str, str]] = set()
    expected = prune_defaults(raw, typed, removed)
    if not removed:
        return text, 0
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        assignment = re.match(r"^\s*([A-Za-z_][\w-]*)\s*=\s*(.*)", line)
        if assignment:
            name, expression = assignment.groups()
            try:
                value = rtoml.loads("value = " + expression)["value"]
            except rtoml.TomlParsingError:
                value = None
            if (name, canonical(value)) in removed:
                if "#" in expression:
                    lines.append("# Implicit schema default: " + line.lstrip())
                continue
        lines.append(line)
    candidate = "".join(lines)
    try:
        after = rtoml.loads(candidate)
    except rtoml.TomlParsingError:
        return text, 0
    if canonical(after) != canonical(expected):
        return text, 0
    return candidate, field_count(raw) - field_count(after)


def minimize_modelo(directory: Path, work: Path, *, apply: bool = False) -> dict[str, object]:
    """Stage default elision, compare all typed fields, and publish guarded changes."""
    directory = directory.resolve(strict=True)
    work = work.resolve()
    if work.exists() or work.is_relative_to(directory) or directory.is_relative_to(work):
        raise ValueError("work must be new and outside the modelo")
    before_files = fingerprint(directory)
    before = load_modelo_directory(directory)
    originals, staged = work / "original", work / "staged"
    shutil.copytree(directory, originals)
    shutil.copytree(directory, staged)
    if fingerprint(originals) != before_files or fingerprint(staged) != before_files:
        raise ValueError("source changed while staging defaults")
    changed: dict[str, int] = {}
    for path in sorted(staged.rglob("*.toml")):
        if "export" in path.relative_to(staged).parts or "locales" in path.relative_to(staged).parts:
            continue
        original = path.read_text(encoding="utf-8-sig")
        text, removed = elide_text(original, {"modelo": before, "revisions": before.revisions})
        if removed:
            path.write_text(text, encoding="utf-8", newline="\n")
            changed[path.relative_to(staged).as_posix()] = removed
    with modelo_fact_scope(directory):
        after = load_modelo_directory(staged)
    baseline = canonical(complete_value(before))
    if baseline != canonical(complete_value(after)):
        raise ValueError("default elision changed a typed field; nothing published")
    result: dict[str, object] = {
        "modelo": directory.name,
        "removed_fields": sum(changed.values()),
        "changed": changed,
        "complete_typed_equality": True,
        "applied": False,
        "before_fingerprint": before_files,
        "after_fingerprint": fingerprint(staged),
        "backup": str(originals),
    }
    if apply:
        publish_staged_tree(directory, staged, originals, before_files)
        if canonical(complete_value(load_modelo_directory(directory))) != baseline:
            raise ValueError("live source changed after typed proof; backup retained")
        result["applied"] = True
    (work / "proof.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    """Rehearse or apply exact default removal across the corpus."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--modelo", action="append")
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="cadrumo-registry-defaults-"))
    print(work, flush=True)
    results: list[dict[str, object]] = []
    for directory in sorted(Path("src/cadrumo/_data/registry/aeat/modelos").iterdir()):
        if not directory.is_dir() or (args.modelo and directory.name not in args.modelo):
            continue
        result = minimize_modelo(directory, work / directory.name, apply=args.apply)
        results.append(result)
        print(directory.name, result["removed_fields"], flush=True)
        (work / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
