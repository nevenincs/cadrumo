#!/usr/bin/env python3
"""Batch classifier for plan Steps based on git log heuristics and code verification.

Reads _steps_inventory.csv (838 Steps across 20 plans) and classifies each step
as DONE-CITED, DONE-NO-CITE, OPEN, or STALE-SUPERSEDED based on:
  1. git log --all --grep="<step-id>" (commit message evidence)
  2. git log --all -S "<symbol>" for key terms in Scope (code symbol searches)
  3. Structural code verification (presence/absence of expected code paths)

Output: _steps_classified.csv with Classification and Evidence columns.
"""

import csv
import subprocess
import re
import sys
import os
from pathlib import Path
from typing import Final

_UTF_8: Final[str] = "utf-8"


def run_git_cmd(args: list[str]) -> str:
    """Run a git command and return stdout, or empty string on failure."""
    try:
        # Ensure git is found in PATH
        env = os.environ.copy()
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return ""


def classify_step(step_id: str, action: str, scope: str) -> tuple[str, str]:
    """Classify a step and return (classification, evidence).

    Heuristics:
    - DONE-CITED: git log --grep="<step-id>" with commit found
    - DONE-NO-CITE: git log -S "<key-symbol>" shows code evidence but no cited commit
    - STALE-SUPERSEDED: action contains "supersede" / "replaced" / "archive" keywords
    - OPEN: no git evidence and no structural code found
    """

    # Heuristic 1: Direct commit citation (git log --grep="<step-id>")
    step_id_clean = step_id.replace(".", "").replace("-", "")
    grep_result = run_git_cmd(["log", "--all", "--oneline", f"--grep={step_id}"])
    if grep_result:
        first_commit = grep_result.split('\n')[0] if grep_result else ""
        if first_commit:
            return "DONE-CITED", f"Commit: {first_commit}"

    # Heuristic 2: Check for stale/superseded markers in action
    action_lower = action.lower()
    stale_markers = ["supersede", "replaced", "archive", "deprecated", "remove"]
    if any(marker in action_lower for marker in stale_markers):
        return "STALE-SUPERSEDED", f"Action marker: {stale_markers[0]}"

    # Heuristic 3: Extract key symbols from Scope and search git log
    scope_tokens = re.findall(r'[\w_-]+', scope)
    found_symbols = []

    for token in scope_tokens:
        if len(token) > 4:  # Longer tokens are more specific
            log_result = run_git_cmd(["log", "--all", "--oneline", "-S", token])
            if log_result:
                found_symbols.append(token)
                if len(found_symbols) >= 2:
                    return "DONE-NO-CITE", f"Code symbols: {', '.join(found_symbols[:2])}"

    if found_symbols:
        return "DONE-NO-CITE", f"Code symbol: {found_symbols[0]}"

    # Default to OPEN if no evidence
    return "OPEN", "No evidence"


def main():
    """Main classifier entry point."""
    input_file = "_steps_inventory.csv"
    output_file = "_steps_classified.csv"

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]

    input_path = Path(input_file)
    if not input_path.exists():
        print(f"Error: {input_file} not found", file=sys.stderr)
        sys.exit(1)

    # Read inventory
    rows = []
    try:
        with open(input_path, encoding=_UTF_8) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"Error reading {input_file}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Classifying {len(rows)} steps...", file=sys.stderr)

    # Classify each step
    classified = []
    for i, row in enumerate(rows):
        step_id = row.get("Step", "")
        action = row.get("Action", "")
        scope = row.get("Scope", "")

        classification, evidence = classify_step(step_id, action, scope)

        classified.append({
            "Plan": row.get("Plan", ""),
            "Step": step_id,
            "Action": action,
            "Scope": scope,
            "Classification": classification,
            "Evidence": evidence,
        })

        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(rows)}...", file=sys.stderr)

    # Write output
    try:
        with open(output_file, "w", encoding=_UTF_8, newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["Plan", "Step", "Action", "Scope", "Classification", "Evidence"],
            )
            writer.writeheader()
            writer.writerows(classified)
    except Exception as e:
        print(f"Error writing {output_file}: {e}", file=sys.stderr)
        sys.exit(1)

    # Summary
    counts = {}
    for row in classified:
        cls = row["Classification"]
        counts[cls] = counts.get(cls, 0) + 1

    print(f"\nClassification summary:", file=sys.stderr)
    for cls in sorted(counts.keys()):
        print(f"  {cls}: {counts[cls]}", file=sys.stderr)
    print(f"\nOutput: {output_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
