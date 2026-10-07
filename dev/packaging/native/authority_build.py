"""Run the canonical authority publisher with compiler-aware content currency."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from dev._paths import REPO_ROOT

from ...registry.compiler.compiler_source_tree import compiler_source_tree_digest
from ..command_execution import run_command
from .action_cache import action_lock, fingerprint
from .build_paths import build_paths


def publish(build: Path) -> None:
    """Reuse a current publication only after the same compiler succeeded."""
    marker = build_paths(build)["generated"] / "authority-compiler.txt"
    # This development cache key includes the compiler's imported domain/core schema
    # owners and dependency versions. It never changes the published legal identity.
    identity = hashlib.sha256(
        (
            compiler_source_tree_digest()
            + fingerprint(build / "inputs-authority-compiler.txt", (Path(sys.executable),))
        ).encode("utf-8")
    ).hexdigest()
    with action_lock(build, "authority-publication"):
        command = [sys.executable, "-B", "-m", "dev.registry.pipeline", "publish-authority"]
        if marker.is_file() and marker.read_text(encoding="utf-8") == identity:
            command.append("--if-stale")
        result = run_command(command, cwd=REPO_ROOT)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        if result.returncode:
            raise SystemExit(result.returncode)
        if not marker.is_file() or marker.read_text(encoding="utf-8") != identity:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(identity, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    publish(parser.parse_args().build)
