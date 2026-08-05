"""Disposable pre-cutover extractor for revision construct titles."""

from __future__ import annotations

import base64
import json
import re
import sys
import tomllib
from pathlib import Path

_PLAIN_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")


def _segment(value: str) -> str:
    if _PLAIN_SEGMENT.fullmatch(value) and not value.startswith("x-"):
        return value
    encoded = base64.b32hexencode(value.encode("utf-8")).decode("ascii").rstrip("=").lower()
    return f"x-{encoded}"


def main() -> None:
    root = Path(__file__).parents[1] / "src/cadrumo/_data/registry/aeat/modelos"
    output = Path(sys.argv[1])
    values: dict[tuple[str, str, str], str] = {}
    conflicts: list[tuple[tuple[str, str, str], str, str, str]] = []

    for modelo_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        modelo_id = modelo_dir.name
        for source in sorted(modelo_dir.rglob("*.toml")):
            payload = tomllib.loads(source.read_text(encoding="utf-8"))
            revisions = payload.get("revisions")
            if not isinstance(revisions, dict):
                continue
            for revision_id, revision in revisions.items():
                if not isinstance(revision_id, str) or not isinstance(revision, dict):
                    continue
                constructs = revision.get("constructs")
                if not isinstance(constructs, list):
                    continue
                for construct in constructs:
                    if not isinstance(construct, dict):
                        continue
                    construct_id = construct.get("id")
                    title = construct.get("title")
                    if not isinstance(construct_id, str) or not isinstance(title, str):
                        continue
                    identity = (modelo_id, revision_id, construct_id)
                    previous = values.get(identity)
                    if previous is not None and previous != title:
                        conflicts.append((identity, previous, title, str(source)))
                    else:
                        values[identity] = title

    if conflicts:
        for identity, previous, current, source in conflicts:
            print(f"CONFLICT {identity!r}: {previous!r} vs {current!r} at {source}", file=sys.stderr)
        raise SystemExit(2)
    if not values:
        raise SystemExit("no construct titles found")

    manifest = {locale: {} for locale in ("ca", "en", "es", "hu")}
    for (modelo_id, revision_id, construct_id), title in sorted(values.items()):
        key = (
            f"modelo.schema.{_segment(modelo_id)}.revision.{_segment(revision_id)}.construct."
            f"{_segment(construct_id)}.field.title"
        )
        manifest["es"][key] = title
        for locale in ("ca", "en", "hu"):
            manifest[locale][key] = None
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"construct_values={len(values)} manifest={output}")


if __name__ == "__main__":
    main()
