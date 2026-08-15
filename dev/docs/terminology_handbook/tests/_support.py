"""Shared test-only support for the Terminology Handbook loader/scaffold/validator suites."""

from __future__ import annotations

from pathlib import Path


def write_concept_fragment(tmp_path: Path, name: str, content: str) -> Path:
    """Write ``content`` to ``concepts/<name>`` under ``tmp_path`` and return the ``concepts`` dir."""
    concepts = tmp_path / "concepts"
    concepts.mkdir(exist_ok=True)
    (concepts / name).write_text(content, encoding="utf-8")
    return concepts
