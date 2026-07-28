"""Gettext extraction and per-language catalogue management for the user docs.

The user documentation surface (the operator-facing Sphinx pages: index,
how-to, explanation, reference, architecture, glossary, top-level pages) is
localized through Sphinx's first-party gettext workflow rather than parallel
per-language page trees. This module owns the two build-time steps that feed
that workflow:

* :func:`extract_pot` renders the POT message templates for the authored
  user-scope pages with the ``gettext`` builder under ``CADRUMO_DOCS_SCOPE=user``
  and ``gettext_compact = False`` (see ``docs/conf.py``), so each source page
  owns one template. The templates land under ``docs/locales/pot/`` and are an
  uncommitted build product, regenerated on demand like the generated CLI and
  glossary surfaces.
* :func:`update_catalogues` runs ``sphinx-intl update`` to create or refresh the
  committed per-language ``.po`` catalogues under
  ``docs/locales/<lang>/LC_MESSAGES/**`` for every translation target.

The target-language set is derived from
:class:`~cadrumo.core.external_constants.OutputLanguage` (the single language
authority shared with the runtime CLI catalogues) minus English, which is the
msgid source and carries no catalogue. :func:`user_scope_source_pages` is the
one definition of "which pages are the localized surface"; the all-languages
completeness gate imports it so extraction and the gate can never disagree on
the page set.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

_ROOT_FOR_DIRECT_INVOCATION = Path(__file__).resolve().parents[2]
if str(_ROOT_FOR_DIRECT_INVOCATION) not in sys.path:
    sys.path.insert(0, str(_ROOT_FOR_DIRECT_INVOCATION))

from cadrumo.core.external_constants import OutputLanguage
from dev.docs.build import docs_build_jobs, ensure_isolated_storage_root

_DOC_SUFFIXES: Final[frozenset[str]] = frozenset({".md", ".rst"})

#: Top-level ``docs/`` directories that carry no authored, translatable pages:
#: the generated API autodoc tree and viewcode source, the build output, the
#: asset / template / inventory infrastructure, the executed cli-sequence
#: contracts, and the two build-time generated surfaces (the CLI reference and
#: the ``_generated`` glossary/casilla pages, both gitignored English build
#: products). The authored user surface is everything else.
_EXCLUDED_TOP_DIRS: Final[frozenset[str]] = frozenset(
    {
        "api",
        "_modules",
        "_build",
        "_static",
        "_templates",
        "_inventories",
        "_sequences",
        "cli",
        "_generated",
    },
)

#: Authored files under ``docs/`` that are not part of the published surface.
_EXCLUDED_FILES: Final[frozenset[str]] = frozenset({"USERDOCS-KICKOFF-BRIEF.md"})

#: The BCP-47 tags translated as documentation targets: the OutputLanguage
#: closed set minus English (the msgid source, which needs no catalogue).
TARGET_LANGUAGES: Final[tuple[str, ...]] = tuple(
    member.value for member in OutputLanguage if member is not OutputLanguage.EN
)


def _repo_root() -> Path:
    """Return the repository root for this module."""
    return Path(__file__).resolve().parents[2]


def user_scope_source_pages(docs_root: Path) -> list[str]:
    """Return the authored user-scope documentation pages as POSIX docpaths.

    The result is the single definition of the localized surface: every authored
    ``.md`` / ``.rst`` source under ``docs/`` minus the generated, infrastructure,
    and API trees in :data:`_EXCLUDED_TOP_DIRS`. Both :func:`extract_pot` and the
    all-languages completeness gate consume this set, so the extracted templates
    and the gate's page set are guaranteed identical.

    Args:
        docs_root: The documentation source root (the repository ``docs/``).

    Returns:
        Sorted POSIX-relative source paths (with suffix), for example
        ``["disclaimer.md", "how-to/quickstart.md", "index.md"]``.
    """
    pages: list[str] = []
    for source in docs_root.rglob("*"):
        if source.suffix not in _DOC_SUFFIXES or not source.is_file():
            continue
        relative = source.relative_to(docs_root)
        if relative.parts[0] in _EXCLUDED_TOP_DIRS:
            continue
        if relative.name in _EXCLUDED_FILES or relative.name.startswith(("test_", "_test_")):
            continue
        pages.append(relative.as_posix())
    return sorted(pages)


def pot_root(docs_root: Path) -> Path:
    """Return the uncommitted POT template directory under ``docs/locales``."""
    return docs_root / "locales" / "pot"


def locale_root(docs_root: Path) -> Path:
    """Return the committed per-language catalogue root under ``docs/locales``."""
    return docs_root / "locales"


#: Wall-clock ceiling for a shelled documentation build, in seconds.
#:
#: Generous rather than tight: the full-scope nitpicky build is documented
#: in-tree at roughly 840 seconds, and the gettext extraction below covers a
#: subset of that page set. The point is not to be fast, it is to be BOUNDED -
#: an unbounded shell call converts any upstream hang into an indefinite lane
#: wedge with no diagnostic, which is exactly how a hanging gettext build cost
#: three separate investigations before anyone read a stack trace. It reproduces
#: at zero pytest workers, so it is not a parallelism artefact.
_SHELL_TIMEOUT_S: Final[float] = 900.0


def _run_bounded(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None,
    what: str,
) -> subprocess.CompletedProcess[bytes]:
    """Run ``command`` with a wall-clock bound, failing loudly on timeout.

    Args:
        command: The argument vector to execute.
        cwd: Working directory for the child.
        env: Environment mapping, or ``None`` to inherit.
        what: Human-readable name of the step, used in the timeout message.

    Returns:
        The completed process.

    Raises:
        SystemExit: If the command exceeds :data:`_SHELL_TIMEOUT_S`, naming the
            step, the bound and the command so the failure is diagnosable
            instead of presenting as a silent stall.
    """
    try:
        return subprocess.run(command, cwd=cwd, env=env, check=False, timeout=_SHELL_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        rendered = " ".join(command)
        raise SystemExit(
            f"{what} exceeded its {_SHELL_TIMEOUT_S:.0f}s bound and was terminated. "
            f"Command: {rendered}. A hang here presents to pytest as an unresponsive "
            "worker (`node down: Not properly terminated`) or as a lane that stops "
            "emitting output, so it is reported here as a named failure instead."
        ) from exc


def extract_pot(repo_root: Path, out_dir: Path | None = None) -> Path:
    """Extract user-scope POT message templates into ``docs/locales/pot``.

    Runs Sphinx's ``gettext`` builder over exactly the authored user-scope page
    set (:func:`user_scope_source_pages`) under ``CADRUMO_DOCS_SCOPE=user`` so the
    application is never imported to render an API page, and with the generated
    CLI reference suppressed. ``gettext_compact = False`` (set in ``docs/conf.py``)
    makes each source page own one ``.pot`` template.

    Args:
        repo_root: The repository root.
        out_dir: The POT output directory. Defaults to the committed-tree
            ``docs/locales/pot``; the catalogue-vs-source drift gate passes a
            temporary directory so a freshness check never mutates the tree.

    Returns:
        The POT output directory.

    Raises:
        SystemExit: If the gettext build fails.
    """
    docs_root = repo_root / "docs"
    out_dir = pot_root(docs_root) if out_dir is None else out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    ensure_isolated_storage_root()
    pages = user_scope_source_pages(docs_root)
    env = {
        **os.environ,
        "CADRUMO_DOCS_PROJECT_ROOT": str(repo_root),
        "CADRUMO_DOCS_SCOPE": "user",
        "CADRUMO_DOCS_LANGUAGE": "en",
        "CADRUMO_DOCS_OFFLINE": "1",
        "CADRUMO_DOCS_ONLY": os.pathsep.join(pages),
        "CADRUMO_DOCS_MASTER_DOC": "index",
        "CADRUMO_DOCS_SKIP_CLI_REFERENCE": "1",
    }
    command = [
        sys.executable,
        "-m",
        "sphinx",
        "-b",
        "gettext",
        "-j",
        docs_build_jobs(os.environ),
        str(docs_root),
        str(out_dir),
    ]
    result = _run_bounded(command, cwd=repo_root, env=env, what="gettext POT extraction")
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return out_dir


def update_catalogues(repo_root: Path, languages: tuple[str, ...] = TARGET_LANGUAGES) -> None:
    """Create or refresh the committed per-language ``.po`` catalogues.

    Runs ``sphinx-intl update`` from the extracted POT templates so every
    translation target gains one ``.po`` catalogue per source page under
    ``docs/locales/<lang>/LC_MESSAGES/**``. Existing translated leaves are
    preserved and only new or changed messages are added (gettext marks a changed
    source segment fuzzy, which the completeness gate counts as missing).

    Args:
        repo_root: The repository root.
        languages: The BCP-47 target tags to update. Defaults to every
            documentation translation target.

    Raises:
        SystemExit: If the catalogue update fails.
    """
    docs_root = repo_root / "docs"
    templates = pot_root(docs_root)
    if not templates.is_dir():
        raise SystemExit(f"POT templates not found at {templates}; run extraction first.")
    command = [
        sys.executable,
        "-m",
        "sphinx_intl",
        "update",
        "-p",
        str(templates),
        "-d",
        str(locale_root(docs_root)),
    ]
    for language in languages:
        command.extend(["-l", language])
    result = _run_bounded(command, cwd=repo_root, env=None, what="sphinx-intl catalogue update")
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: extract POT templates and refresh the language catalogues.

    Args:
        argv: Optional argument vector for testing.

    Returns:
        A process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Extract POT templates without refreshing the per-language catalogues.",
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    templates = extract_pot(repo_root)
    print(f"Extracted POT templates: {templates}", flush=True)
    if args.extract_only:
        return 0
    update_catalogues(repo_root)
    print(
        f"Updated catalogues for {', '.join(TARGET_LANGUAGES)} under {locale_root(repo_root / 'docs')}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
