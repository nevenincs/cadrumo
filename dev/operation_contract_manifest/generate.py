"""Generate the operation contract manifest from the eager production registry.

Every registered operation's public contract is a pure function of its
definition. This generator composes every operation through the eager
production registry, the validation authority, and writes the result to
``src/cadrumo/_data/operations/contract_manifest.json``: each operation's
contract, ephemeral-secret lifetime, composition group and handler module,
plus the digest of the whole contract set.

``--check`` exits 1 when the committed manifest differs from fresh output, so
a contract change cannot ship without regenerating the manifest. A stale
manifest is also refused at runtime when its group is composed; this gate
names the drift first.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cadrumo.entrypoints.operation_composition import build_production_operation_contract_manifest
from dev._paths import REPO_ROOT, UTF_8


def target_path(repo_root: Path | None = None) -> Path:
    """Return the generated manifest's path."""
    return (repo_root or REPO_ROOT) / "src" / "cadrumo" / "_data" / "operations" / "contract_manifest.json"


def render_manifest() -> str:
    """Compose every production operation and render the canonical manifest."""
    return build_production_operation_contract_manifest().render()


def manifest_drifts(path: Path, fresh: str) -> bool:
    """Whether the manifest at ``path`` is absent or differs from ``fresh``."""
    on_disk = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return on_disk != fresh.encode(UTF_8)


def main(argv: list[str] | None = None) -> int:
    """Write the manifest, or verify it with ``--check``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit 1 when the committed manifest drifts.")
    parser.add_argument("--target", type=Path, default=None, help="Manifest path (default: the shipped manifest).")
    args = parser.parse_args(argv)
    path = args.target or target_path()
    fresh = render_manifest()
    if args.check:
        if manifest_drifts(path, fresh):
            print(
                f"DRIFT: {path} differs from the registered operations; run just generate-operation-contract-manifest",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {path} matches the registered operations.")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fresh, encoding=UTF_8, newline="\n")
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
