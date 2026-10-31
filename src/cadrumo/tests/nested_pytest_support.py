"""Run a real nested pytest over a generated one-module package."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .audited_process import ensure_text_completed_process, run_audited_process


def nested_pytest_over_generated_module(package: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a real nested pytest over ``package/test_generated.py`` with the shared hook installed."""
    return ensure_text_completed_process(
        run_audited_process(
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "-c",
                str(package / "pytest.ini"),
                "-v",
                *args,
                str(package / "test_generated.py"),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=None,
            check=False,
        )
    )
