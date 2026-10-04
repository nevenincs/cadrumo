"""Build the localized roots served by the canonical documentation preview."""

from __future__ import annotations

import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cadrumo.core.storage_environment import prepare_temporary_directory
from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command

from .build_paths import docs_build_root, docs_html_root
from .i18n import TARGET_LANGUAGES


def language_build_command(language: str, html_root: Path) -> list[str]:
    """Use the regular build driver to populate a dropdown destination."""
    return [
        sys.executable,
        "-m",
        "dev.docs.build",
        "--language",
        language,
        "--isolated-source",
        "--out-dir",
        str(html_root / language),
    ]


def main() -> int:
    """Refresh each translated site without rewriting the watched English sources."""
    build_root = docs_build_root(REPO_ROOT)
    html_root = docs_html_root(REPO_ROOT)
    logs = build_root / "locale-logs"
    logs.mkdir(parents=True, exist_ok=True)
    jobs = max(1, (os.cpu_count() or 1) // len(TARGET_LANGUAGES))
    with tempfile.TemporaryDirectory(prefix="cadrumo-docs-preview-", dir=prepare_temporary_directory()) as scratch:

        def build(language: str) -> int:
            storage = Path(scratch) / language
            storage.mkdir()
            log = logs / f"{language}.log"
            environment = {
                **os.environ,
                "PYTHONIOENCODING": "utf-8",
                "CADRUMO_DOCS_BUILD_ROOT": str(build_root),
                "CADRUMO_DOCS_JOBS": str(jobs),
                "CADRUMO_LOCAL_STORAGE_ROOT": str(storage),
            }
            print(f"Building {language} documentation; log: {log}", flush=True)
            result = run_command(language_build_command(language, html_root), cwd=REPO_ROOT, environment=environment)
            log.write_text(result.stdout + result.stderr, encoding="utf-8")
            print(f"Documentation {language}: exit {result.returncode}; log: {log}", flush=True)
            return result.returncode

        with ThreadPoolExecutor(max_workers=len(TARGET_LANGUAGES)) as pool:
            results = list(pool.map(build, TARGET_LANGUAGES))
    return int(any(results))


if __name__ == "__main__":
    raise SystemExit(main())
