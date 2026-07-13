"""Materialise a fresh Claude plugin and validate it with ``claude plugin validate --strict``.

The plugin generation target emits the single authored
harness source as a one-click Claude plugin. This smoke lane materialises a fresh
plugin into a throwaway directory and runs the live ``claude plugin validate
--strict`` oracle over it, so a schema drift between the emitter and the Claude
plugin format fails the packaging lane loudly.

Unlike a pytest gate, this is a standalone smoke lane: when the ``claude`` CLI is
not on PATH it does not fail the build - it materialises the tree, prints an
explicit ``SKIPPED`` status naming the missing tool, and exits 0. The
materialisation itself always runs, so the lane still proves the emitter produces
a tree; only the strict-validation assertion is gated on the tool's presence.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TypedDict

from cadrumo.agent import materialise_plugin

_CLAUDE = "claude"
_VALIDATE_ARGS = ("plugin", "validate", "--strict")


class PluginValidateSummary(TypedDict):
    """Machine-readable plugin-validation smoke summary."""

    status: str
    plugin_root: str
    skills_written: int
    agents_written: int
    tool: str
    detail: str


def _validate(plugin_root: Path, *, skills: int, agents: int) -> PluginValidateSummary:
    """Run the strict validator over the materialised plugin tree.

    Returns a ``skipped`` summary when the ``claude`` CLI is absent; raises
    ``SystemExit`` when the validator reports a non-zero exit (a real drift).
    """
    claude = shutil.which(_CLAUDE)
    if claude is None:
        return {
            "status": "skipped",
            "plugin_root": str(plugin_root),
            "skills_written": skills,
            "agents_written": agents,
            "tool": _CLAUDE,
            "detail": f"{_CLAUDE} CLI not on PATH; plugin materialised but not strict-validated",
        }
    completed = subprocess.run(  # noqa: S603 - claude resolved from PATH, fixed args
        [claude, *_VALIDATE_ARGS, str(plugin_root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"claude plugin validate --strict failed for {plugin_root}:\n{completed.stdout}\n{completed.stderr}",
        )
    return {
        "status": "validated",
        "plugin_root": str(plugin_root),
        "skills_written": skills,
        "agents_written": agents,
        "tool": claude,
        "detail": "claude plugin validate --strict passed",
    }


def main(argv: list[str] | None = None) -> int:
    """Materialise a fresh plugin and strict-validate it where ``claude`` is present."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable summary.")
    parser.add_argument("--keep", action="store_true", help="Keep the materialised plugin tree on disk.")
    args = parser.parse_args(argv)

    work = Path(tempfile.mkdtemp(prefix="cadrumo-plugin-smoke-"))
    plugin_root = work / "cadrumo-plugin"
    try:
        manifest = materialise_plugin(plugin_root)
        summary = _validate(plugin_root, skills=manifest.skills_written, agents=manifest.agents_written)
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"{summary['status'].upper()}: {summary['detail']}")
        print(f"plugin root\t{summary['plugin_root']}")
        print(f"skills\t{summary['skills_written']}")
        print(f"agents\t{summary['agents_written']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
