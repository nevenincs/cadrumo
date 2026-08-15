"""Shared helpers for parsing the CLI's plain tab-separated text output."""

from __future__ import annotations


def _line_value(output: str, key: str) -> str:
    for line in output.splitlines():
        head, sep, tail = line.partition("\t")
        if sep and head.strip() == key:
            return tail.strip()
    raise AssertionError(f"no {key!r} line in CLI output:\n{output}")
