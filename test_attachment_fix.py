#!/usr/bin/env python
"""Quick test of attachment plaintext-leak fix."""
import sys
import subprocess

result = subprocess.run(
    [sys.executable, "-m", "pytest", "-xvs",
     "src/aeat/domain/attachments/test_repository.py::test_blob_and_manifest_round_trip_without_plaintext_files"],
    cwd="Y:\\code\\aeat-worktrees\\chore-476-restructure-execution",
)
sys.exit(result.returncode)
