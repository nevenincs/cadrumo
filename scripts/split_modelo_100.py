"""Migrate registry/aeat/modelos/100.toml to the directory layout.

This script is the official escape hatch for in-flight agents who
were working against the old single-file layout (commit 758fc637 and
earlier) when modelo 100 was migrated to directory mode. If their
git checkout still has ``registry/aeat/modelos/100.toml``, running
this script:

  1. Reads the in-flight 100.toml.
  2. Verifies it loads via the existing single-file loader (catches
     malformed TOML / schema-violating edits early).
  3. Splits it byte-preservingly into
     ``registry/aeat/modelos/100/manifest.toml`` plus
     ``registry/aeat/modelos/100/revisions/<revision-id>.toml``.
  4. Verifies the directory layout loads to a ModeloDefinition equal
     to the single-file load result (no information loss).
  5. Deletes ``registry/aeat/modelos/100.toml`` ONLY after all checks
     pass.

If the directory layout already exists with conflicting content,
the script ABORTS and asks for human review — auto-merging would
risk silent data loss when the same casilla / formula was edited in
both places.

Usage::

    .venv/Scripts/python.exe scripts/split_modelo_100.py

Exits with status 0 on success, non-zero on any check failure or
manual-review requirement. The script is idempotent when the source
file does not exist (it reports "nothing to do" and exits 0).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC = PROJECT_ROOT / "registry" / "aeat" / "modelos" / "100.toml"
DST_DIR = PROJECT_ROOT / "registry" / "aeat" / "modelos" / "100"
REVS_DIR = DST_DIR / "revisions"
HEADER_RE = re.compile(r'^\s*\[\[?revisions\."([^"]+)"')


def _split_text_into_files(text: str) -> tuple[str, dict[str, str]]:
    """Walk source text line by line, attributing each line to either
    the manifest or to the currently-active revision.

    Lines BEFORE the first revision header go to the manifest. Each
    revision header switches the active output target. Blank lines /
    comments stay with the currently-active target. The split is
    byte-preserving — concatenating manifest + all revision files
    reproduces the source byte-for-byte (modulo file boundaries).
    """
    lines = text.splitlines(keepends=True)
    manifest_lines: list[str] = []
    revision_lines: dict[str, list[str]] = {}
    active: str | None = None
    for line in lines:
        match = HEADER_RE.match(line)
        if match:
            active = match.group(1)
            revision_lines.setdefault(active, [])
        if active is None:
            manifest_lines.append(line)
        else:
            revision_lines[active].append(line)
    return ("".join(manifest_lines), {rev: "".join(rs) for rev, rs in revision_lines.items()})


def _abort(message: str) -> int:
    print(f"ABORT: {message}", file=sys.stderr)
    return 1


def main() -> int:
    if not SRC.is_file():
        if (DST_DIR / "manifest.toml").is_file():
            print(f"nothing to do — modelo 100 already in directory layout at {DST_DIR}")
            return 0
        return _abort(f"neither {SRC} nor {DST_DIR}/manifest.toml exists; cannot proceed")

    if (DST_DIR / "manifest.toml").is_file():
        return _abort(
            f"both {SRC} and {DST_DIR}/manifest.toml exist. Manual review required:\n"
            f"  - inspect {SRC} content for in-flight edits\n"
            f"  - merge those edits into the appropriate {REVS_DIR}/<rev>.toml files\n"
            f"  - delete {SRC} once merged\n"
            f"This script will not auto-merge to avoid silent data loss."
        )

    print(f"reading {SRC} ({SRC.stat().st_size:,} bytes)")
    text = SRC.read_text(encoding="utf-8")

    from aeat.domain.calculations.registry._loader import (
        load_modelo_directory,
        load_modelo_file,
    )

    print(f"validating {SRC} loads via single-file loader...")
    expected = load_modelo_file(SRC)
    print(f"  loaded: modelo {expected.id!r}, revisions={sorted(expected.revisions)!r}")

    manifest_text, revision_files = _split_text_into_files(text)
    print(f"split into manifest ({len(manifest_text.splitlines()):,} lines) "
          f"+ {len(revision_files)} revision file(s)")

    DST_DIR.mkdir(exist_ok=True)
    REVS_DIR.mkdir(exist_ok=True)
    (DST_DIR / "manifest.toml").write_text(manifest_text, encoding="utf-8")
    for rev_id, rev_text in revision_files.items():
        path = REVS_DIR / f"{rev_id}.toml"
        path.write_text(rev_text, encoding="utf-8")
        print(f"  wrote {path.name}: {len(rev_text.splitlines()):,} lines")

    print("verifying directory-mode load matches single-file load...")
    actual = load_modelo_directory(DST_DIR)
    if actual != expected:
        return _abort(
            "POST-SPLIT EQUIVALENCE CHECK FAILED. The directory layout produced a "
            "different ModeloDefinition than the single-file source. NOT deleting "
            f"{SRC}. Inspect {DST_DIR}/ for the partial split output."
        )
    print("  EQUIVALENCE OK")

    SRC.unlink()
    print(f"deleted {SRC}")
    print("\nMigration complete. Commit the result:")
    print(f"  git add {DST_DIR.relative_to(PROJECT_ROOT).as_posix()}/ "
          f"{SRC.relative_to(PROJECT_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
