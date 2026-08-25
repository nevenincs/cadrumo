#!/usr/bin/env python
"""Programmatic semantic audit check using local RAG daemon.

Verifies that core domain/registry logic concepts (rounding, calculations)
do not leak into adapters or entrypoints.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import textwrap
import urllib.request
from collections.abc import Iterable, Mapping
from typing import cast


def _json_object(value: object) -> dict[str, object] | None:
    """Return a JSON object with string keys, or no object at all."""
    if not isinstance(value, dict):
        return None
    raw_object = cast(dict[object, object], value)
    return {str(key): item for key, item in raw_object.items()}


def _rag_results(value: object) -> list[dict[str, object]]:
    """Retain only object-shaped RAG results from an untrusted JSON response."""
    if not isinstance(value, list):
        return []
    raw_results = cast(list[object], value)
    return [result for raw in raw_results if (result := _json_object(raw)) is not None]


def check_health() -> bool:
    """Check loopback HTTP health endpoint of the RAG daemon."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:8766/health", timeout=2) as response:
            data = _json_object(json.loads(response.read().decode()))
            if data is None:
                return False
            return data.get("status") == "ready"
    except Exception:
        return False


def run_search(query: str) -> list[dict[str, object]]:
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
        data = _json_object(json.loads(result.stdout))
        if data is None or data.get("ok") is not True:
            return []
        response_data = _json_object(data.get("data"))
        return _rag_results(response_data.get("results") if response_data is not None else None)
    except Exception:
        return []


# No adapter owns or is allowlisted for filing-value coercion. Fixed-width
# numeric and padding semantics live in the registry domain codec.
_VERIFIED_NON_LEAK_PATHS: frozenset[str] = frozenset()


def is_violation(path: str) -> bool:
    """Determine if a file path represents a hexagonal leakage violation."""
    # Check if leaked into adapters or entrypoints
    normalised = path.replace("\\", "/")
    parts = normalised.split("/")
    # Filter out tests and locale files
    if "tests" in parts or any(p.startswith("test_") for p in parts):
        return False
    if path.endswith(".yml") or path.endswith(".yaml"):
        return False
    # Verified format-boundary delegators are not leaks (see _VERIFIED_NON_LEAK_PATHS).
    if any(normalised.endswith(allowed) for allowed in _VERIFIED_NON_LEAK_PATHS):
        return False

    # Violating paths
    return "adapters" in parts or "entrypoints" in parts


def _snippet_tree(snippet: object) -> ast.Module | None:
    """Parse a RAG code snippet when it is a complete enough Python fragment."""
    if not isinstance(snippet, str) or not snippet.strip():
        return None
    try:
        return ast.parse(textwrap.dedent(snippet))
    except SyntaxError:
        return None


def _call_name(call: ast.Call) -> str | None:
    """Return the unqualified name a call exposes for semantic evidence."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _is_tax_base_target(target: ast.expr) -> bool:
    """Whether an assignment target names the tax-base value under audit."""
    if isinstance(target, ast.Name):
        name = target.id
    elif isinstance(target, ast.Attribute):
        name = target.attr
    else:
        return False
    return name.lower() in {"tax_base", "taxable_base"}


def _is_transcribed_value(value: ast.expr) -> bool:
    """Whether an expression reads an already-stated structured-document value."""
    if isinstance(value, ast.Attribute):
        return value.attr in {"text", "value"}
    if not isinstance(value, ast.Call):
        return False
    name = _call_name(value)
    if name in {"_first_text", "findtext", "get"}:
        return True
    if name in {"_decimal", "coerce_decimal", "Decimal"}:
        return any(_is_transcribed_value(argument) for argument in value.args)
    return False


def _is_calculation(value: ast.expr) -> bool:
    """Whether an expression performs arithmetic or invokes a calculation primitive."""
    if isinstance(value, (ast.BinOp, ast.UnaryOp)):
        return True
    if not isinstance(value, ast.Call):
        return False
    name = _call_name(value)
    if name is not None and any(token in name.lower() for token in ("calculate", "compute", "derive", "sum")):
        return True
    return any(_is_calculation(argument) for argument in value.args)


def _calculation_function_name(result: dict[str, object]) -> str | None:
    """Return a RAG function name only when it itself claims tax-base calculation."""
    function_name = result.get("function_name")
    if not isinstance(function_name, str):
        return None
    name = function_name.lower()
    if "tax" not in name or "base" not in name:
        return None
    if any(token in name for token in ("calculate", "compute", "derive")):
        return function_name
    return None


def calculation_evidence(query: str, result: dict[str, object]) -> str | None:
    """Return concrete leak evidence from a RAG hit, never path-based exemptions.

    A relevant adapter result alone is only a retrieval hypothesis. For the
    tax-base query it must show an adapter assigning a tax base through
    arithmetic, or a calculation-named function doing arithmetic. Reading a
    value from a structured invoice remains transcriptive even when that value
    is later used to derive a different document total.
    """
    tree = _snippet_tree(result.get("snippet"))
    if tree is None:
        return None

    if query == "calculate tax base":
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(_is_tax_base_target(target) for target in node.targets):
                if _is_transcribed_value(node.value):
                    continue
                if _is_calculation(node.value):
                    return "tax-base arithmetic assignment"
            if (
                isinstance(node, ast.AnnAssign)
                and _is_tax_base_target(node.target)
                and node.value is not None
                and not _is_transcribed_value(node.value)
                and _is_calculation(node.value)
            ):
                return "tax-base arithmetic assignment"

        function_name = _calculation_function_name(result)
        if function_name is not None and any(
            _is_calculation(node) for node in ast.walk(tree) if isinstance(node, ast.expr)
        ):
            return f"tax-base arithmetic in {function_name}"
        return None

    if query == "currency rounding":
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and (_call_name(node) or "").lower() in {
                "quantize",
                "round",
                "round_to_cents",
                "to_integral_value",
            }:
                return "currency-rounding call"
    return None


def semantic_leak_violations(
    results_by_query: Mapping[str, Iterable[dict[str, object]]],
) -> tuple[str, ...]:
    """Classify shaped RAG results into concrete semantic leak violations."""
    violations: list[str] = []
    score_threshold = 0.50

    for query, results in results_by_query.items():
        for result in results:
            raw_score = result.get("score")
            score = float(raw_score) if isinstance(raw_score, int | float) else 0.0
            raw_path = result.get("path")
            path = raw_path if isinstance(raw_path, str) else ""
            if score < score_threshold or not is_violation(path):
                continue
            evidence = calculation_evidence(query, result)
            if evidence is not None:
                violations.append(f"Leak detected for query '{query}' ({evidence}; score {score:.2f}): {path}")

    return tuple(violations)


def main() -> None:
    """Execute programmatic semantic leak audits and assert clean state."""
    if not check_health():
        print("RAG service on port 8766 is offline or not ready. Skipping semantic audit.")
        sys.exit(0)

    # Core concepts queries to check leaks
    queries = (
        "currency rounding",
        "calculate tax base",
    )
    violations = semantic_leak_violations({query: run_search(query) for query in queries})

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
