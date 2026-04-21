"""Fail the commit when staged paths look like vaultspec install state.

Project-local replacement for `vaultspec-core check-providers`. Upstream
blocklists `.mcp.json`, but this project's fresh-clone test
`test_mcp_json_points_google_workspace_to_launcher` enforces that
.mcp.json IS committed. This hook keeps the rest of upstream's allowlist
but treats `.mcp.json` as a legitimately tracked project invariant.
"""

from __future__ import annotations

import subprocess
import sys

BLOCKED_NAMES: frozenset[str] = frozenset(
    {
        "providers.lock",
        "providers.json",
        "providers.json.lock",
        "providers.lock.lock",
        "CLAUDE.md",
        "GEMINI.md",
        "AGENTS.md",
    }
)
BLOCKED_DIRS: frozenset[str] = frozenset({".claude", ".gemini", ".codex", ".antigravity", ".agents"})
BLOCKED_PREFIXES: tuple[str, ...] = (".vaultspec/_snapshots/",)


def staged_paths() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--diff-filter=ACMR", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [p for p in result.stdout.splitlines() if p]


def find_violations(paths: list[str]) -> list[str]:
    bad: list[str] = []
    for p in paths:
        norm = p.replace("\\", "/")
        parts = norm.split("/")
        if parts[-1] in BLOCKED_NAMES:
            bad.append(p)
            continue
        if any(seg in BLOCKED_DIRS for seg in parts):
            bad.append(p)
            continue
        if any(norm.startswith(prefix) for prefix in BLOCKED_PREFIXES):
            bad.append(p)
            continue
    return bad


def main() -> int:
    violations = find_violations(staged_paths())
    if not violations:
        return 0
    print("error: provider artifacts must not be committed:", file=sys.stderr)
    for v in violations:
        print(f"  {v}", file=sys.stderr)
    print(
        "\nRun 'git reset HEAD <file>' to unstage, or 'git rm --cached <file>' to untrack.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
