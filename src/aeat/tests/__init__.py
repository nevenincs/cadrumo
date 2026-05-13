"""Project-bundled test plumbing, meta tests, and fixtures.

This subpackage ships with ``aeat`` so the wheel is self-testable. It
hosts the pytest collection hook (``_marker_hook``), the dotenv loader
the hook uses (``_env_loader``), repo-meta tests (release config,
``.env`` alignment, marker-taxonomy integrity), and the on-disk
``fixtures/`` tree consumed by colocated tests across the package.

Colocated unit tests live next to the modules they exercise (rust-style
``src/aeat/<subpkg>/test_*.py``); only repo-meta and fixture-bearing
content lives here.
"""

from __future__ import annotations

from pathlib import Path

FIXTURES_DIR: Path = Path(__file__).resolve().parent / "fixtures"
"""Root of the on-disk fixture tree bundled with the package."""

__all__ = ["FIXTURES_DIR"]
