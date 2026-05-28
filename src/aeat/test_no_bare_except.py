"""Structural gate: no bare-except patterns in the test surface.

A bare ``except:`` (no exception class) silently swallows every
exception including ``KeyboardInterrupt``, ``SystemExit``, and
assertion errors themselves.  ``except Exception: pass`` is equally
opaque when the body is only a ``pass`` statement — it masks real
failures and defeats the quality-gate purpose of the test.

This test walks every ``test_*.py`` file under ``src/aeat/``,
parses the AST, and fails if it finds either shape.  Adding a bare
``except`` to a test file is blocked immediately by the CI gate;
the fix is always to replace it with a specific exception assertion.

The enumeration also covers
:mod:`aeat.entrypoints.cli.test_stdio` to confirm no workaround
for the S50 stream-reconfigure tests landed there.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


def _bare_except_locations(src_root: Path) -> list[tuple[str, int, str]]:
    """Return (file, lineno, shape) for every bare-except in test files."""

    findings: list[tuple[str, int, str]] = []
    for path in sorted(src_root.rglob("test_*.py")):
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for handler in node.handlers:
                if handler.type is None:
                    # bare ``except:``
                    findings.append((str(path), node.lineno, "bare except:"))
                elif (
                    isinstance(handler.type, ast.Name)
                    and handler.type.id == "Exception"
                    and len(handler.body) == 1
                    and isinstance(handler.body[0], ast.Pass)
                ):
                    # ``except Exception: pass`` — opaque swallow
                    findings.append((str(path), node.lineno, "except Exception: pass"))
    return findings


def test_no_bare_except_in_test_surface() -> None:
    """Zero bare-except or ``except Exception: pass`` shapes in test files.

    Every test file under ``src/aeat/`` is parsed with the standard AST
    module; no subprocess, no mock, no skip.  Failures name the exact
    file and line number so the author can replace the bare handler with
    a specific exception assertion.
    """
    src_root = Path(__file__).parent
    findings = _bare_except_locations(src_root)

    if findings:
        lines = "\n".join(f"  {path}:{lineno}  [{shape}]" for path, lineno, shape in findings)
        raise AssertionError(
            f"Found {len(findings)} bare-except pattern(s) in test surface:\n{lines}\n"
            "Replace each with a specific exception assertion or a documented "
            "controlled-failure helper."
        )
