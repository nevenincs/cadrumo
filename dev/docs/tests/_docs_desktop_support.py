"""Build the desktop-flavor fixture page through the real ``docs/conf.py`` for the documentation gates."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import CommandResult, run_command

DOCS = REPO_ROOT / "docs"
EXTERNAL_URL = "https://example.org/"
#: A sidebar entry off the documentation origin, titled with its own search word.
SIDEBAR_EXTERNAL_URL = "https://example.com/sidebar"
SIDEBAR_TERM = "zzqsidebarterm"
#: A made-up word only the fixture page body and the injected records carry.
SEARCH_TERM = "zzqbridgeterm"

FIXTURE_PAGE = f"""# Fixture

Body with an [external link]({EXTERNAL_URL}) and a [local link](#second).

The {SEARCH_TERM} paragraph compares a < b & c for the search excerpt.

```{{toctree}}
:hidden:

{SIDEBAR_TERM} outside <{SIDEBAR_EXTERNAL_URL}>
```

## Second

Closing paragraph.
"""


def build_fixture_site(work: Path, **env_overrides: str) -> tuple[Path, CommandResult]:
    """Build the fixture page through the real ``docs/conf.py``; return its HTML root and the run."""
    source = work / "docs"
    source.mkdir(parents=True)
    shutil.copy2(DOCS / "conf.py", source / "conf.py")
    for name in ("_static", "_templates", "_inventories"):
        shutil.copytree(DOCS / name, source / name)
    (source / "fixture.md").write_text(FIXTURE_PAGE, encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if key not in {"CADRUMODOCS_BASE_URL", "CADRUMODOCS_FLAVOR"}}
    env.update(
        {
            "CADRUMODOCS_PROJECT_ROOT": str(REPO_ROOT),
            "CADRUMODOCS_SCOPE": "user",
            "CADRUMODOCS_OFFLINE": "1",
            "CADRUMODOCS_ONLY": "fixture.md",
            "CADRUMODOCS_MASTER_DOC": "fixture",
            "CADRUMODOCS_SKIP_SEQUENCE_CHECK": "1",
            "CADRUMODOCS_SKIP_CLI_TREE": "1",
            "CADRUMODOCS_SKIP_CLI_REFERENCE": "1",
            "CADRUMO_STORAGE_ROOT": str(work / "state"),
            **env_overrides,
        }
    )
    html = work / "html"
    result = run_command(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-b",
            "html",
            "-j",
            "1",
            "-q",
            str(source),
            str(html),
            str(source / "fixture.md"),
        ],
        cwd=REPO_ROOT,
        environment=env,
    )
    return html, result


def built_site(work: Path, **env_overrides: str) -> Path:
    html, result = build_fixture_site(work, **env_overrides)
    assert result.returncode == 0, result.stdout + result.stderr
    return html
