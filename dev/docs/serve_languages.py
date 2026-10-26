"""Write the localized roots served by the canonical documentation preview."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from cadrumo.core.storage_environment import STORAGE_ROOT, prepare_temporary_directory
from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command

from .build_paths import docs_build_root, docs_html_root
from .i18n import TARGET_LANGUAGES


def languages_compile_command(html_root: Path, build_root: Path) -> list[str]:
    """Return the ONE compile that writes every language's root under the preview.

    Every language comes from a single read of the pages, so a save costs one
    compile however many languages the header's dropdown offers. The compile
    reads a private copy of the sources, so the localized generated references
    cannot overwrite the English ones the preview watches. Only the translated
    roots are written: the English site is the one the preview itself builds.
    """
    return [
        sys.executable,
        "-m",
        "dev.docs.compile_once",
        "--html-root",
        str(html_root),
        "--build-root",
        str(build_root),
        "--flavor",
        "web",
        "--languages",
        *TARGET_LANGUAGES,
    ]


def main() -> int:
    """Refresh every translated site without rewriting the watched English sources."""
    build_root = docs_build_root(REPO_ROOT)
    html_root = docs_html_root(REPO_ROOT)
    log = build_root / "locale-logs" / "languages.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cadrumo-docs-preview-", dir=prepare_temporary_directory()) as scratch:
        environment = {
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            STORAGE_ROOT.variable: scratch,
        }
        print(f"Compiling the documentation's languages once; log: {log}", flush=True)
        result = run_command(languages_compile_command(html_root, build_root), cwd=REPO_ROOT, environment=environment)
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    print(f"Documentation languages: exit {result.returncode}; log: {log}", flush=True)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
