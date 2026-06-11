"""Live-reloading documentation development server.

Wrap ``sphinx-autobuild`` to serve the rendered handbook on localhost and
rebuild incrementally whenever the narrative corpus (``docs/``) or the autodoc
source tree (``src/aeat/``) changes. The Sphinx application stays warm between
rebuilds, so edit-to-refresh is a fraction of a cold ``just docs`` build.

Surfaces that the build itself rewrites are excluded from the watch set so a
rebuild cannot trigger itself: ``docs/cli/`` is regenerated from the live
command tree at ``builder-inited`` (see ``docs/conf.py``) and ``docs/_build``
is the output tree. Editing a docstring under ``src/aeat/`` rebuilds the
affected autodoc page; adding or removing a *module* still requires
``python -m dev.docs.apidocs scaffold`` to refresh the committed ``docs/api``
stub set (per the aeat-docs-scaffolding-cli rule), which this server does not
run. This is the interactive companion to :mod:`dev.docs.build`, which performs
the one-shot incremental and gate builds.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8000


def _repo_root() -> Path:
    """Return the repository root for this module."""
    return Path(__file__).resolve().parents[2]


def _ignore_patterns() -> list[str]:
    """Return fnmatch globs for changed paths that must not trigger a rebuild.

    ``sphinx-autobuild`` matches each pattern against the native (OS-separator)
    absolute path of a changed file, and ``*`` spans separators, so a single
    ``*<sep>dir<sep>*`` glob excludes a directory subtree recursively. The
    ``docs/cli`` exclusion is load-bearing: that tree is rewritten on every
    build, so watching it would loop the server on its own output. The pattern
    is anchored to ``docs/cli`` specifically so changes under the unrelated
    ``src/aeat/entrypoints/cli`` source still rebuild the CLI reference.

    Returns:
        The ignore globs, in declaration order.
    """
    sep = os.sep
    return [
        f"*{sep}_build{sep}*",
        f"*{sep}docs{sep}cli{sep}*",
        f"*{sep}__pycache__{sep}*",
        "*.pyc",
        f"*{sep}.git{sep}*",
        f"*{sep}tests{sep}*",
        f"*{sep}_data{sep}*",
    ]


def serve_command(repo_root: Path, *, host: str, port: int, open_browser: bool) -> list[str]:
    """Build the ``sphinx-autobuild`` argument vector for the dev server.

    Args:
        repo_root: Repository root containing ``docs/`` and ``src/aeat/``.
        host: Loopback interface the server binds.
        port: TCP port the server listens on.
        open_browser: Whether to open a browser tab once the first build lands.

    Returns:
        The full command vector, runnable with the current interpreter.
    """
    docs_root = repo_root / "docs"
    out_dir = docs_root / "_build" / "html"
    command = [
        sys.executable,
        "-m",
        "sphinx_autobuild",
        str(docs_root),
        str(out_dir),
        "-b",
        "html",
        "-j",
        "auto",
        # Bind and serve the existing docs/_build/html immediately instead of
        # blocking the port until a full cold autodoc build finishes; the first
        # rebuild fires on the first detected change.
        "--no-initial",
        "--watch",
        str(repo_root / "src" / "aeat"),
        "--host",
        host,
        "--port",
        str(port),
    ]
    if open_browser:
        command.append("--open-browser")
    for pattern in _ignore_patterns():
        command.extend(["--ignore", pattern])
    return command


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the live-reloading documentation server."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=_DEFAULT_HOST, help="Loopback interface to bind (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT, help="Port to serve on (default: 8000).")
    parser.add_argument("--open-browser", action="store_true", help="Open a browser tab after the first build.")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    # sphinx-autobuild drives Sphinx through the `build` subcommand form
    # (`python -m sphinx build ...`), whose extra leading token defeats the
    # argv heuristic in docs/conf.py that distinguishes a full build from a
    # targeted partial one. That heuristic otherwise skips the deferred
    # pydantic-model rebuild and the CLI-reference generation, leaving autodoc
    # to crash on a not-fully-defined model. The dev server always serves the
    # whole site, so force both build-time steps on via the conf.py overrides.
    env = {
        **os.environ,
        "AEAT_DOCS_PROJECT_ROOT": str(repo_root),
        "AEAT_DOCS_FORCE_DEFERRED_MODELS": "1",
        "AEAT_DOCS_FORCE_CLI_REFERENCE": "1",
    }
    command = serve_command(repo_root, host=args.host, port=args.port, open_browser=args.open_browser)
    print(f"Serving documentation on http://{args.host}:{args.port} (Ctrl-C to stop).", flush=True)
    print("Watching docs/ and src/aeat/; rebuilding on change.", flush=True)
    try:
        result = subprocess.run(command, cwd=repo_root, env=env, check=False)
    except KeyboardInterrupt:
        return 0
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
