"""Prove every check-set guard in both directions with temporary mutations."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_TEST = "dev/ci/tests/test_check_set_contract.py"


@dataclass(frozen=True)
class Proof:
    """One reversible mutation and its expected guard assertion."""

    node: str
    path: Path
    old: str
    new: str
    assertion: str


def _run(node: str) -> subprocess.CompletedProcess[str]:
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required to prove the check-set guards")
    return subprocess.run(  # noqa: S603 - resolved executable and closed proof table
        [
            uv,
            "run",
            "--no-sync",
            "pytest",
            "-q",
            "-n0",
            "--timeout=900",
            "-m",
            "integration",
            f"{_TEST}::{node}",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _proofs() -> tuple[Proof, ...]:
    workflow = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    source = REPO_ROOT / "src" / "cadrumo" / "core" / "file_permissions.py"
    return (
        Proof(
            "test_no_command_runs_twice_in_one_workflow_run",
            workflow,
            "      - name: Import architecture\n        run: just check-import-boundaries\n",
            "      - name: Import architecture\n        run: just check-import-boundaries\n"
            "      - name: Import architecture again\n        run: just check-import-boundaries\n",
            "duplicate commands",
        ),
        Proof(
            "test_every_job_name_describes_coverage_with_the_shared_vocabulary",
            workflow,
            '    name: "Check: Workflow definitions (Linux)"',
            '    name: "actionlint"',
            "job naming contract violations",
        ),
        Proof(
            "test_every_self_hosted_job_has_a_timeout",
            workflow,
            "    timeout-minutes: 10\n",
            "",
            "self-hosted jobs without timeout-minutes",
        ),
        Proof(
            "test_every_default_branch_push_reaches_a_verdict",
            workflow,
            "${{ github.ref == 'refs/heads/main' && format('-{0}', github.sha) || '' }}",
            "",
            "main concurrency group has no SHA suffix",
        ),
        Proof(
            "test_shipped_packages_cannot_detect_the_test_runner",
            source,
            "from __future__ import annotations\n",
            "from __future__ import annotations\n\nimport pytest\n",
            "shipped test-runner awareness",
        ),
    )


def main() -> int:
    """Run every mutation/failure/restore/pass proof and publish the count."""
    proved = 0
    for proof in _proofs():
        original = proof.path.read_text(encoding="utf-8")
        if original.count(proof.old) != 1:
            raise RuntimeError(f"mutation anchor is not unique for {proof.node}: {proof.old!r}")
        try:
            proof.path.write_text(original.replace(proof.old, proof.new, 1), encoding="utf-8")
            failed = _run(proof.node)
            combined = failed.stdout + failed.stderr
            if failed.returncode == 0 or proof.assertion not in combined:
                sys.stderr.write(combined)
                raise RuntimeError(f"{proof.node} did not fail on {proof.assertion!r}")
        finally:
            proof.path.write_text(original, encoding="utf-8")
        passed = _run(proof.node)
        if passed.returncode != 0:
            sys.stderr.write(passed.stdout + passed.stderr)
            raise RuntimeError(f"{proof.node} did not pass after restoration")
        proved += 1
        print(f"PROVED {proved}: {proof.node} failed and passed on its named assertion")
    print(f"PROVED_GUARD_COUNT={proved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
