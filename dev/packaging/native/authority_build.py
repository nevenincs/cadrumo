"""Validate the published authority without changing authoring inputs during a build."""

from __future__ import annotations

import argparse
from pathlib import Path

from dev._paths import REPO_ROOT
from dev.registry.pipeline.authority_publication import authority_database_currency

from ..authority_staging import selected_published_authority
from .build_directory import require_enrolled_build
from .build_log import BuildLog, display_path
from .build_paths import build_paths


def publish(build: Path) -> None:
    """Admit a current authority as a read-only build input; refuse implicit authoring."""
    build_paths(build)
    instruction = "Run just registry-publish-authority outside the native build, then retry."
    log = BuildLog("registry_authority")
    try:
        descriptor, _database = selected_published_authority(REPO_ROOT)
    except FileNotFoundError as error:
        raise SystemExit(f"{error} {instruction}") from error
    source = REPO_ROOT / "src/cadrumo/_data"
    currency = authority_database_currency(
        descriptor,
        registry_root=source / "registry/aeat",
        source_root=source,
        profile_schema_path=source / "registry/cadrumo/user_profile/schema.toml",
    )
    if not currency.is_current:
        raise SystemExit(f"Registry authority is unavailable or stale: {currency.detail}. {instruction}")
    log.status(f"validated {display_path(descriptor)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=require_enrolled_build, required=True)
    args = parser.parse_args()
    publish(args.build)
