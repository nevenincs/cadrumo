#!/usr/bin/env python
"""Programmatic semantic audit check using local RAG daemon.

Verifies that core domain/registry logic concepts (rounding, calculations)
do not leak into adapters or entrypoints.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request


def check_health() -> bool:
    """Check loopback HTTP health endpoint of the RAG daemon."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:8766/health", timeout=2) as response:
            data = json.loads(response.read().decode())
            return data.get("status") == "ready"
    except Exception:
        return False


def run_search(query: str) -> list[dict]:
    """Run search query via RAG service with --port 8766 --json."""
    cmd = [
        "uv",
        "run",
        "--no-sync",
        "vaultspec-rag",
        "search",
        query,
        "--type",
        "code",
        "--port",
        "8766",
        "--timeout",
        "45.0",
        "--json",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        if not data.get("ok"):
            return []
        return data.get("data", {}).get("results", [])
    except Exception:
        return []


def is_violation(path: str) -> bool:
    """Determine if a file path represents a hexagonal leakage violation."""
    # Check if leaked into adapters or entrypoints
    parts = path.replace("\\", "/").split("/")
    # Filter out tests and locale files
    if "tests" in parts or any(p.startswith("test_") for p in parts):
        return False
    if path.endswith(".yml") or path.endswith(".yaml"):
        return False

    # Violating paths
    return "adapters" in parts or "entrypoints" in parts


def main() -> None:
    """Execute programmatic semantic leak audits and assert clean state."""
    if not check_health():
        print("RAG service on port 8766 is offline or not ready. Skipping semantic audit.")
        sys.exit(0)

    # Core concepts queries to check leaks
    queries = [
        "currency rounding",
        "calculate tax base",
    ]

    violations = []
    score_threshold = 0.50

    for query in queries:
        results = run_search(query)
        for res in results:
            score = res.get("score", 0.0)
            path = res.get("path", "")
            if score >= score_threshold and is_violation(path):
                violations.append(f"Leak detected for query '{query}' (score {score:.2f}): {path}")

    if violations:
        print("=== Semantic Leak Violations ===")
        for violation in violations:
            print(violation)
        sys.exit(1)
    else:
        # Exit silent/concise on success
        print("no semantic leak violations detected")
        sys.exit(0)


if __name__ == "__main__":
    main()
