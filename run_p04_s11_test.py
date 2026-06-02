#!/usr/bin/env python
"""Run P04.S11 formula parity test and capture output."""
import subprocess
import sys

result = subprocess.run(
    [
        sys.executable, "-m", "pytest",
        "src/aeat",
        "-k", "test_formula_revisions_are_owned_by_constructs_with_snapshot_workflow_surfaces",
        "-n", "2",
        "-q",
        "--tb=short",
    ],
    capture_output=True,
    text=True,
)

print(result.stdout)
print(result.stderr)
sys.exit(result.returncode)
