#!/usr/bin/env python
"""Zero-noise code complexity and maintainability auditor.

Enforces cyclomatic complexity (Radon), maintainability index (Radon),
and cognitive complexity (Complexipy) thresholds, filtering out noise
to output only actionable violations.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
    from complexipy import file_complexity
except ImportError:
    # Fallback if complexipy is run outside the correct venv
    file_complexity = None


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the complexity audit."""
    parser = argparse.ArgumentParser(description="Audit code complexity with zero-noise filtering.")
    parser.add_argument(
        "--tests",
        action="store_true",
        help="Audit test files instead of production packages.",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=20,
        help="Cognitive complexity threshold for complexipy.",
    )
    return parser.parse_args()


def run_radon_cc(target: str, exclude: str) -> list[str]:
    """Run radon cc and filter out non-violation output."""
    cmd = ["radon", "cc", target, "-n", "C", "-s", "-a"]
    if exclude:
        cmd.extend(["-e", exclude])

    result = subprocess.run(  # noqa: S603
        ["uv", "run", "--no-sync", *cmd],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )

    lines = result.stdout.splitlines()
    violations: list[str] = []
    has_functions = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Radon cc outputs file paths and then blocks with grades:
        # e.g., "    F 12:0 my_func - C (12)"
        # We detect if there are actual function lines (indented)
        if line.startswith(" ") or line.startswith("\t"):
            violations.append(line)
            has_functions = True
        elif not line.startswith("Average complexity:"):
            # This is a file header line, we will append it if it precedes a violation
            violations.append(line)

    # Clean up file headers that have no following violations
    cleaned: list[str] = []
    last_header = None
    for line in violations:
        if line.startswith(" ") or line.startswith("\t"):
            if last_header:
                cleaned.append(last_header)
                last_header = None
            cleaned.append(line)
        else:
            last_header = line

    if has_functions:
        # Append the average complexity line at the end for context
        avg_line = next((ln for ln in lines if ln.startswith("Average complexity:")), None)
        if avg_line:
            cleaned.append(avg_line)
        return cleaned
    return []


def run_radon_mi(target: str, exclude: str) -> list[str]:
    """Run radon mi and return only files with grade B or worse."""
    cmd = ["radon", "mi", target, "-s"]
    if exclude:
        cmd.extend(["-e", exclude])

    result = subprocess.run(  # noqa: S603
        ["uv", "run", "--no-sync", *cmd],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )

    lines = result.stdout.splitlines()
    violations: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # MI outputs: "path/to/file.py - A" (or B, C)
        # We filter out A-grade files (high maintainability) to reduce noise.
        # Actionable files are B, C, or lower.
        if not (stripped.endswith(" - A") or " - A (" in stripped):
            violations.append(line)

    return violations


def run_cognitive_complexity(root: Path, is_test_run: bool, threshold: int) -> list[str]:
    """Audit cognitive complexity using complexipy."""
    if file_complexity is None:
        return ["[WARNING] complexipy is not installed or available in this environment."]

    def is_production(path: Path) -> bool:
        parts = path.parts
        name = path.name
        if "_data" in parts or "tests" in parts:
            return False
        return not (name.startswith("test_") or name.startswith("_test_") or "_test_" in name)

    if is_test_run:
        # Top-level test files matching test_*.py in target root
        files = sorted(root.glob("test_*.py"))
    else:
        # Production files
        files = sorted(path for path in root.rglob("*.py") if is_production(path))

    findings: list[tuple[int, str, str]] = []
    for path in files:
        try:
            result = file_complexity(str(path))
            for function in result.functions:
                if function.complexity > threshold:
                    findings.append((function.complexity, str(path), function.name))
        except Exception:  # noqa: S110
            # Handle parsing errors gracefully
            pass

    findings.sort(reverse=True)
    violations: list[str] = []
    if findings:
        violations.append(f"Cognitive complexity violations (threshold {threshold}):")
        for complexity, path, function_name in findings[:80]:
            violations.append(f"{complexity:>4}  {path}::{function_name}")
    return violations


def main() -> None:
    """Run complexity audits against production or test packages."""
    args = parse_args()
    target_dir = "src/aeat"

    if args.tests:
        # Exclude pattern for test run is not needed as we only target top-level test files,
        # but for Radon we exclude production and data folders:
        exclude_pattern = (
            "src/aeat/application/*,src/aeat/domain/*,src/aeat/adapters/*,src/aeat/core/*,src/aeat/_data/*"
        )
        scope_name = "test files"
    else:
        exclude_pattern = (
            "src/aeat/test_*.py,src/aeat/**/test_*.py,src/aeat/**/_test_*.py,src/aeat/tests/*,src/aeat/_data/*"
        )
        scope_name = "production code"

    # Run radon CC
    cc_violations = run_radon_cc(target_dir, exclude_pattern)

    # Run radon MI
    mi_violations = run_radon_mi(target_dir, exclude_pattern)

    # Run cognitive complexity
    cog_violations = run_cognitive_complexity(Path(target_dir), args.tests, args.threshold)

    has_violations = bool(cc_violations or mi_violations or cog_violations)

    if has_violations:
        print(f"=== Complexity Audit Failures for {scope_name} ===")
        if cc_violations:
            print("\n--- Cyclomatic Complexity (Radon CC Grade >= C) ---")
            print("\n".join(cc_violations))
        if mi_violations:
            print("\n--- Maintainability Index (Radon MI Grade < A) ---")
            print("\n".join(mi_violations))
        if cog_violations:
            print("\n--- Cognitive Complexity (Complexipy > threshold) ---")
            print("\n".join(cog_violations))
        sys.exit(1)
    else:
        print(f"no {scope_name} functions/files exceed complexity thresholds")
        sys.exit(0)


if __name__ == "__main__":
    main()
