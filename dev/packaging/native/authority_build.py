"""Validate the published authority without changing authoring inputs during a build.

A validation is not repeated while nothing it read has changed. The ``app-authority``
build record names the fingerprint of every file the check reads: the bundled data tree
(registry sources, source evidence and the profile schema), the selected descriptor and
database, and the interpreter and module files that ran it. The record settles only when
the data held still across the check.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

from dev._paths import REPO_ROOT

from ..authority_staging import selected_published_authority
from .build_directory import require_enrolled_build
from .build_fingerprint import inventory_fingerprint
from .build_log import BuildLog, display_path
from .build_paths import build_paths
from .build_stamp import ACTION_COMPONENTS, action_identity, begin_record, read_inputs, settle_record
from .hashing import digest, digest_cache
from .stage_reuse import record_reuse, walk_files

COMPONENT = ACTION_COMPONENTS["authority"]
"""The build record of the last passing validation."""


def data_inputs(descriptor: Path, database: Path, data: Path) -> dict[str, str]:
    """Hash the selected authority pair and every file of the bundled data tree the check reads from."""
    # Resolve the root once: members walked below a resolved root are named by resolved paths.
    entries = {path.as_posix(): digest(path) for path in walk_files(data.resolve())}
    for path in (descriptor, database):
        entries[path.resolve().as_posix()] = digest(path)
    return entries


def loaded_code() -> list[Path]:
    """Return the files of every module this process has loaded, which is the code the check ran."""
    files: set[Path] = set()
    for module in list(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if isinstance(name, str) and Path(name).is_file():
            files.add(Path(name).resolve())
    return sorted(files)


def check_inventory(data: Mapping[str, str], code: Iterable[Path]) -> dict[str, str]:
    """Return the check's whole input inventory: its data, its code and the interpreter."""
    entries = dict(data)
    for path in code:
        entries[path.as_posix()] = digest(path) if path.is_file() else "missing"
    entries["@python"] = hashlib.sha256(f"{sys.version}\n{digest(Path(sys.executable))}".encode()).hexdigest()
    return entries


def publish(build: Path) -> None:
    """Admit a current authority as a read-only build input; refuse implicit authoring."""
    build_paths(build)
    instruction = "Run just registry-publish-authority outside the native build, then retry."
    log = BuildLog("registry_authority")
    try:
        descriptor, database = selected_published_authority(REPO_ROOT)
    except FileNotFoundError as error:
        raise SystemExit(f"{error} {instruction}") from error
    source = REPO_ROOT / "src/cadrumo/_data"
    with digest_cache(build):
        before = data_inputs(descriptor, database, source)
        recorded = read_inputs(build, COMPONENT)
        if recorded is not None:
            # The recorded code files are re-hashed; a module the check never loaded cannot change it.
            code = [Path(key) for key in recorded if not key.startswith("@") and key not in before]
            if record_reuse(build, COMPONENT, inventory_fingerprint(check_inventory(before, code))) is None:
                log.status(f"up to date, {display_path(descriptor)} was validated against these sources")
                return
        # Loaded only when the check runs: importing the registry pipeline costs more than a skip.
        from dev.registry.pipeline.authority_publication import authority_database_currency

        currency = authority_database_currency(
            descriptor,
            registry_root=source / "registry/aeat",
            source_root=source,
            profile_schema_path=source / "registry/cadrumo/user_profile/schema.toml",
        )
        if not currency.is_current:
            raise SystemExit(f"Registry authority is unavailable or stale: {currency.detail}. {instruction}")
        entries = check_inventory(before, loaded_code())
        fingerprint = inventory_fingerprint(entries)
        begin_record(build, action_identity(build, "authority", fingerprint), entries)
        settle_record(build, COMPONENT, settled=data_inputs(descriptor, database, source) == before)
    log.status(f"validated {display_path(descriptor)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=require_enrolled_build, required=True)
    args = parser.parse_args()
    publish(args.build)
