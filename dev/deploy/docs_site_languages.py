"""Construct isolated per-language build environments and the language entry."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from dev._paths import UTF_8
from dev.docs import i18n as _docs_i18n
from dev.docs.build_paths import DOCS_SITE_PREFIX_ENV
from dev.docs.sequence_build_gate import SEQUENCE_CHECK_SKIP_ENV

from .docs_delivery_contracts import CANONICAL_DOCS_BASE_URL


def site_build_environment(*, base_environment: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return the deployment-specific strict docs build environment.

    The Pagefind contract is pinned to ``full``: the deployed index carries the
    injected concept, casilla, legal and CLI records, not the rendered pages
    alone. This is the SITE's contract, and the site has one index -- so this is
    the environment the one index pass resolves its injector from
    (:func:`~dev.deploy.docs_site_build._index_site`), while one root's own
    build narrows it to ``none`` (:func:`language_build_environment`) because a
    root does not index itself. It is pinned explicitly rather than left to the
    build default so an ambient ``CADRUMO_DOCS_PAGEFIND_MODE`` in the
    publishing session cannot narrow the shipped search contract — ``base`` is
    the real process environment in production, and these keys are layered over
    it.

    The value is decided, not incidental: a ``pages`` value arrived here inside
    an unrelated env-key rename and silently discarded every injected record
    from the published site for as long as it stood.

    Args:
        base_environment: DI seam for tests. When ``None`` (production), the
            deploy-specific keys are layered over the real process
            environment; a test passes an explicit mapping to prove the
            deploy-specific keys are fixed regardless of what surrounds them,
            without mutating real process state.
    """
    base = base_environment if base_environment is not None else os.environ
    return {
        **base,
        "CADRUMO_DOCS_BASE_URL": CANONICAL_DOCS_BASE_URL,
        # Serially, the strict roots exceed a release job's time budget. The
        # prove phase already builds and checks the same site in parallel.
        "CADRUMO_DOCS_JOBS": "auto",
        "CADRUMO_DOCS_PAGEFIND_MODE": "full",
    }


def localized_languages() -> tuple[str, ...]:
    """Return the per-language deploy roots, English included.

    Derived from the shared :data:`SITE_ROOT_LANGUAGES` so the deploy matrix
    never re-lists the language set. English is a root like any other: the
    readers here file Spanish tax, so no language holds the apex path and ``/``
    resolves to the reader's own instead (see :func:`_write_language_entry`).
    """
    return _docs_i18n.SITE_ROOT_LANGUAGES


def _language_site_url(language: str) -> str:
    """Return the canonical deploy URL for one localized site root."""
    return f"{CANONICAL_DOCS_BASE_URL}/{language}"


def language_build_command(language: str, out_dir: Path) -> list[str]:
    """Return the build-driver command for one site root.

    Reuses the ``dev.docs.build`` driver's flags rather than duplicating build
    logic. English is built WITHOUT ``--language``: it is the msgid source, so
    it has no catalogue to select, and passing the flag would force the user
    scope and drop the API autodoc tree. It therefore keeps the full scope and
    carries ``api/`` inside its own root, while every translated root is a
    strict user-scope build of the operator surface. Every root reads its own
    copy of the sources (``--isolated-source``), because the roots build at the
    same time and each renders its generated pages in its own language.
    """
    command = [sys.executable, "-m", "dev.docs.build", "--strict", "--isolated-source"]
    if language == _docs_i18n.DEFAULT_SOURCE_LANGUAGE:
        command += ["--out-dir", str(out_dir)]
        return command
    command += ["--scope", "user", "--language", language, "--out-dir", str(out_dir)]
    return command


def language_build_environment(language: str, *, check_sequences: bool) -> dict[str, str]:
    """Return the deploy build environment for one published site root.

    The shared deployment environment (parallel workers) with the canonical base
    URL pointed at the language's own root so the per-language sitemap and
    canonical/OpenGraph URLs are correct, and two keys that place this root in a
    site it does not own alone:

    - ``CADRUMO_DOCS_PAGEFIND_MODE=none``, because the site has ONE search index
      and it is built over every root once they are all built
      (:func:`~dev.deploy.docs_site_build._index_site`). A root that indexed
      itself would write a second index the served site never loads, addressed
      to its own root rather than to the apex.
    - ``CADRUMO_DOCS_SITE_PREFIX``, this root's own directory in the served
      site. It is what makes a page resolve the apex index one level up from its
      own root, and what completes a shared record's destination inside the
      language being read.

    ``check_sequences`` selects whether this root runs the cli-sequence goldens
    gate. The check's verdict cannot vary by root -- its subprocess scrubs every
    ``CADRUMO_*`` key and pins English output -- so the four roots produce four
    identical answers for four times the cost. One root runs it and the rest set
    the documented opt-out; which root is decided by
    :func:`_language_build_environments`, never here.
    """
    environment = {
        **site_build_environment(),
        "CADRUMO_DOCS_BASE_URL": _language_site_url(language),
        "CADRUMO_DOCS_PAGEFIND_MODE": "none",
        DOCS_SITE_PREFIX_ENV: language,
    }
    if not check_sequences:
        environment[SEQUENCE_CHECK_SKIP_ENV] = "1"
    return environment


def root_build_jobs(languages: Sequence[str], cpus: int) -> dict[str, str]:
    """Share one machine's CPUs between site roots that build at the same time.

    Each root left at ``auto`` forks a worker per CPU, so four roots ran four
    times as many workers as CPUs; every full-scope worker imports the whole
    application, and the English build's workers died mid-read. The full-scope
    source root carries more than ten times the pages of a translated root, so
    it takes half the CPUs and the translated roots share the rest. Every root
    gets at least one worker, so on a machine with fewer CPUs than that needs,
    the full-scope root yields its half first.
    """
    source = _docs_i18n.DEFAULT_SOURCE_LANGUAGE
    translated = [language for language in languages if language != source]
    source_jobs = max(1, min(cpus // 2, cpus - len(translated))) if translated else max(1, cpus)
    translated_jobs = max(1, (cpus - source_jobs) // len(translated)) if translated else 0
    return {language: str(source_jobs if language == source else translated_jobs) for language in languages}


def _language_build_environments() -> tuple[tuple[str, dict[str, str]], ...]:
    """Return each site root paired with the environment it is built under.

    The cli-sequence goldens gate runs on exactly one root. Pairing the decision
    with the languages here -- rather than branching inside the build loop --
    makes the invariant checkable without running a build, and the refusal below
    is the teeth: a future edit that skips the check on every root (silently
    dropping the gate from the whole deploy) cannot reach a published site.
    """
    environments = tuple(
        (language, language_build_environment(language, check_sequences=index == 0))
        for index, language in enumerate(localized_languages())
    )
    checked = [language for language, environment in environments if SEQUENCE_CHECK_SKIP_ENV not in environment]
    if len(checked) != 1:
        raise SystemExit(
            f"The deploy must run the cli-sequence goldens check on exactly one site root; "
            f"{len(checked)} root(s) would run it ({', '.join(checked) or 'none'}). "
            "Refusing to publish a site whose CLI sequences were never checked against their goldens.",
        )
    return environments


def _write_language_entry(html_root: Path) -> Path:
    """Write the language-agnostic entry served at ``/``.

    No language owns the apex path. The entry resolves a reader to a root in a
    fixed order -- a previously chosen language remembered in the ``cadrumo_docs_lang``
    cookie, then the browser's declared preferences, then Spanish -- and sends
    them there. Spanish is the floor because this documentation is about filing
    Spanish tax; a reader who has expressed nothing is far likelier to want it
    than English.

    The redirect is client-side because the site is static objects behind a CDN:
    there is no request-time hook to read a cookie in. That has one consequence
    worth stating plainly -- a reader with JavaScript disabled sees the links
    rather than being moved -- so the page is a usable language index in its own
    right, not a bare redirect stub, and it carries a ``noscript`` list.

    Returns:
        The path written, so the caller can assert on it.
    """
    languages = ", ".join(f'"{language}"' for language in localized_languages())
    entry = html_root / "index.html"
    entry.write_text(
        "<!doctype html>\n"
        '<html lang="es">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Cadrumo</title>\n"
        # A language selector must never be the canonical result for a query;
        # every localized root carries its own canonical URLs.
        '<meta name="robots" content="noindex,follow">\n'
        "<script>\n"
        "(function () {\n"
        f"  var roots = [{languages}];\n"
        f'  var fallback = "{_docs_i18n.DEFAULT_SITE_LANGUAGE}";\n'
        "  var cookie = document.cookie.match(/(?:^|;\\s*)cadrumo_docs_lang=([a-zA-Z-]+)/);\n"
        "  var wanted = [];\n"
        "  if (cookie) { wanted.push(cookie[1]); }\n"
        "  var declared = navigator.languages || [navigator.language];\n"
        "  for (var i = 0; i < declared.length; i++) {\n"
        "    if (declared[i]) { wanted.push(declared[i]); }\n"
        "  }\n"
        "  wanted.push(fallback);\n"
        "  for (var j = 0; j < wanted.length; j++) {\n"
        '    var tag = String(wanted[j]).toLowerCase().split("-")[0];\n'
        "    if (roots.indexOf(tag) >= 0) {\n"
        '      window.location.replace(tag + "/");\n'
        "      return;\n"
        "    }\n"
        "  }\n"
        '  window.location.replace(fallback + "/");\n'
        "})();\n"
        "</script>\n"
        "</head>\n<body>\n"
        "<noscript>\n<ul>\n"
        + "".join(f'<li><a href="{language}/">{language}</a></li>\n' for language in localized_languages())
        + "</ul>\n</noscript>\n</body>\n</html>\n",
        encoding=UTF_8,
        newline="\n",
    )
    print(f"Wrote language entry: {entry}", flush=True)
    return entry
