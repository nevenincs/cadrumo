"""Construct the builds that write the published roots, and the language entry."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

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
    build narrows it to ``none`` (:func:`source_root_build_environment`) because a
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


def source_root_build_command(out_dir: Path) -> list[str]:
    """Return the build-driver command for the source-language root.

    English is the one root with a Sphinx build of its own, because it is the
    one root that carries the API reference: it is built at the full scope and
    WITHOUT ``--language``, which would select a catalogue the msgid source
    does not have and force the user scope. It reads its own copy of the
    sources (``--isolated-source``), because the compile of the translated
    roots runs at the same time and renders its generated pages itself.
    """
    return [sys.executable, "-m", "dev.docs.build", "--strict", "--isolated-source", "--out-dir", str(out_dir)]


def translated_roots_compile_command(html_root: Path, languages: Sequence[str], *, jobs: int) -> list[str]:
    """Return the ONE compile that writes every translated root.

    The translated roots are not built one by one: the documentation is
    compiled once, strictly, at the user scope, and each language's root is
    composed from the shared structure and that language's text. The compile is
    given the site's address above the language directories, from which every
    root takes its own canonical address and its own site prefix, and it writes
    no search index, because the site has one and it is built over every root
    afterwards (:func:`~dev.deploy.docs_site_build._index_site`).

    Args:
        html_root: The composed HTML root; each language's root is written at
            its own code beneath it.
        languages: The roots to write. The source-language root is left out,
            because its own full-scope build writes it.
        jobs: How many workers the compile may read with.
    """
    return [
        sys.executable,
        "-m",
        "dev.docs.compile_once",
        "--html-root",
        str(html_root),
        "--build-root",
        str(html_root.parent),
        "--flavor",
        "web",
        "--strict",
        "--base-url",
        CANONICAL_DOCS_BASE_URL,
        "--jobs",
        str(jobs),
        "--languages",
        *languages,
    ]


def source_root_build_environment(*, check_sequences: bool) -> dict[str, str]:
    """Return the deploy build environment for the source-language root.

    The shared deployment environment (parallel workers) with the canonical base
    URL pointed at the root's own directory so its canonical/OpenGraph URLs are
    correct, and two keys that place this root in a site it does not own alone:

    - ``CADRUMO_DOCS_PAGEFIND_MODE=none``, because the site has ONE search index
      and it is built over every root once they all exist
      (:func:`~dev.deploy.docs_site_build._index_site`). A root that indexed
      itself would write a second index the served site never loads, addressed
      to its own root rather than to the apex.
    - ``CADRUMO_DOCS_SITE_PREFIX``, this root's own directory in the served
      site. It is what makes a page resolve the apex index one level up from its
      own root, and what completes a shared record's destination inside the
      language being read.

    ``check_sequences`` selects whether this build runs the cli-sequence goldens
    gate; which build of the publish runs it is decided by :func:`site_builds`,
    never here.
    """
    source = _docs_i18n.DEFAULT_SOURCE_LANGUAGE
    environment = {
        **site_build_environment(),
        "CADRUMO_DOCS_BASE_URL": _language_site_url(source),
        "CADRUMO_DOCS_PAGEFIND_MODE": "none",
        DOCS_SITE_PREFIX_ENV: source,
    }
    if not check_sequences:
        environment[SEQUENCE_CHECK_SKIP_ENV] = "1"
    return environment


def translated_roots_compile_environment(*, check_sequences: bool) -> dict[str, str]:
    """Return the environment the one compile of the translated roots runs under.

    The compile pins every documentation selector itself, from its own
    arguments, so nothing of the site is said here a second time. What it does
    read from its caller is whether the cli-sequence goldens gate runs.
    """
    environment = dict(os.environ)
    environment.pop(SEQUENCE_CHECK_SKIP_ENV, None)
    if not check_sequences:
        environment[SEQUENCE_CHECK_SKIP_ENV] = "1"
    return environment


@dataclass(frozen=True)
class SiteBuild:
    """One of the builds a publish runs at the same time, and the roots it writes.

    Attributes:
        name: What the build is called in the publish's output.
        languages: The site roots this build writes.
        command: The build's command line.
        environment: The environment it runs under, before its own storage
            root is added.
    """

    name: str
    languages: tuple[str, ...]
    command: list[str]
    environment: dict[str, str]


#: The build that writes every translated root, as the publish's output names it.
TRANSLATED_ROOTS_BUILD: Final[str] = "translated roots"


def site_build_jobs(cpus: int, *, translated: bool) -> tuple[int, int]:
    """Share one machine's CPUs between the two builds a publish runs at the same time.

    Each build left at ``auto`` forks a worker per CPU, so concurrent builds ran
    more workers than CPUs; every full-scope worker imports the whole
    application, and the English build's workers died mid-read. The full-scope
    source root carries more than ten times the pages of the user scope the
    compile reads, so it takes half the CPUs and the compile takes the rest,
    however many languages the compile carries. Each build gets at least one
    worker.

    Args:
        cpus: The CPUs of the machine.
        translated: Whether a compile of translated roots runs beside the
            source root's build.

    Returns:
        The source root build's workers and the compile's.
    """
    if not translated:
        return max(1, cpus), 0
    source_jobs = max(1, cpus // 2)
    return source_jobs, max(1, cpus - source_jobs)


def site_builds(html_root: Path) -> tuple[SiteBuild, ...]:
    """Return the builds that write every published root, and what each runs under.

    Two builds write the site however many languages it publishes: the
    source-language root's own full-scope build, and one compile for every
    translated root. A language added to the site adds text to the compile, not
    a build to this list.

    The cli-sequence goldens gate runs in exactly one of them. Its verdict
    cannot vary by build -- its subprocess scrubs every ``CADRUMO_*`` key and
    pins English output -- so the source root's build runs it and the compile
    takes the documented opt-out. Deciding that here, rather than inside the
    build loop, makes the invariant checkable without running a build, and the
    refusal below is the teeth: a future edit that skips the check in every
    build (silently dropping the gate from the whole deploy) cannot reach a
    published site.
    """
    source = _docs_i18n.DEFAULT_SOURCE_LANGUAGE
    translated = tuple(language for language in localized_languages() if language != source)
    source_jobs, compile_jobs = site_build_jobs(os.cpu_count() or 1, translated=bool(translated))
    builds = [
        SiteBuild(
            name=source,
            languages=(source,),
            command=source_root_build_command(html_root / source),
            environment={**source_root_build_environment(check_sequences=True), "CADRUMO_DOCS_JOBS": str(source_jobs)},
        )
    ]
    if translated:
        builds.append(
            SiteBuild(
                name=TRANSLATED_ROOTS_BUILD,
                languages=translated,
                command=translated_roots_compile_command(html_root, translated, jobs=compile_jobs),
                environment=translated_roots_compile_environment(check_sequences=False),
            )
        )
    checked = [build.name for build in builds if SEQUENCE_CHECK_SKIP_ENV not in build.environment]
    if len(checked) != 1:
        raise SystemExit(
            f"The deploy must run the cli-sequence goldens check in exactly one site build; "
            f"{len(checked)} build(s) would run it ({', '.join(checked) or 'none'}). "
            "Refusing to publish a site whose CLI sequences were never checked against their goldens.",
        )
    written = sorted(language for build in builds for language in build.languages)
    if written != sorted(localized_languages()):
        raise SystemExit(
            f"The deploy's builds write the roots {written}, and the site publishes "
            f"{sorted(localized_languages())}. Refusing to publish a site with a root no build writes."
        )
    return tuple(builds)


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
