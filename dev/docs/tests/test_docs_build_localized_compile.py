"""The one strict compile that carries every published language, and its witness.

There was one nitpicky ``-n -W`` build per translation target here, each in its
own module so pytest-xdist could spread three multi-minute builds over three
workers. The documentation is now compiled once for every language
(:func:`dev.docs.compile_once.compile_language_roots`), so the gate is one
compile: a warning in any language's prose, in any language's translated
reference, fails the one build that reads them all, and there is no longer a
per-language module set that a new translation target could silently fall out
of.

What the retired modules refused, this keeps: a warning or error under ``-n -W``
with the catalogues read, and a language that is published but built by nobody
-- which is now read off the compile's own stored form rather than off a
hand-authored list of module files.

It also keeps what nothing else can: the proof that a composed root is the page
set a reader would have been served. One language's own strict build runs here
BESIDE the compile -- the witness (:data:`dev.docs.compile_once.WITNESS_LANGUAGE`)
-- and that language's composed root is compared with it byte for byte. The
witness replaced the English user-scope dummy build that used to stand in this
module's place, so the lane runs the same number of real builds it always has:
a translated witness and an English one cost the same, and only the translated
one can see a mechanism that silently followed the Sphinx language.

The two builds are two concurrent subprocesses, so the gate costs the longer of
them rather than their sum, and they are one module-scoped fixture, because
pytest-xdist distributes by file: the assertions below are readings of one pair
of builds, not a build each.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import CommandResult, run_command

from ..compile_once import INTENDED_DIFFERENCES, WITNESS_LANGUAGE, Comparison, compare, witness_build
from ..i18n import SITE_ROOT_LANGUAGES
from ._sphinx_build_harness import gate_build_env, gate_build_jobs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

#: The flavour the gate compiles. The web flavour with an address of its own is
#: the superset of the mark mechanisms: it is the only flavour that writes page
#: descriptions, canonical and OpenGraph URLs, the error page and the sitemap,
#: each of which carries strings that depend on the language. The packaged
#: desktop flavour's own compile is held to the same standard by the packaging
#: driver (:func:`dev.packaging.native.docs_build.compile_command`).
_FLAVOR: Final[str] = "web"

#: An address for the site above the language directories. Any address does:
#: what it has to be is the same one both builds are given, because a page
#: states where it is served and two roots told different addresses differ
#: wherever it does.
_BASE_URL: Final[str] = "https://docs.example.test/docs"

#: Floor for the pages the comparison reads. The user-scope site is a little
#: over three hundred pages in each language; a floor rather than a count,
#: because a page added or retired is not this gate's business, and without one
#: a comparison that read two empty roots would report nothing and pass.
_MINIMUM_PAGES: Final[int] = 250


@dataclass(frozen=True)
class _Built:
    """One compile of every language, and one language's own build beside it.

    Attributes:
        comparison: What the witness language's composed root differs from its
            own build in.
        html_root: The directory the composed roots were written under.
        witness: The root that language's own build wrote.
        stored: The structure and each language's text the roots came from.
    """

    comparison: Comparison
    html_root: Path
    witness: Path
    stored: Path


def _compile_command(html_root: Path, build_root: Path, stored: Path) -> list[str]:
    """Return the one compile of every language, as this gate runs it."""
    return [
        sys.executable,
        "-m",
        "dev.docs.compile_once",
        "--html-root",
        str(html_root),
        "--build-root",
        str(build_root),
        "--stored",
        str(stored),
        "--flavor",
        _FLAVOR,
        "--base-url",
        _BASE_URL,
        "--strict",
        "--jobs",
        gate_build_jobs(),
    ]


def _succeeded(result: CommandResult, what: str) -> CommandResult:
    """Return one finished build, reporting its own output when it failed."""
    assert result.returncode == 0, (
        f"the {what} reported warnings or errors:\n" + result.stdout[-6000:] + result.stderr[-6000:]
    )
    return result


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_Built]:
    """Run the one compile and the witness build at the same time, and compare them."""
    root = tmp_path_factory.mktemp("localized-compile")
    html_root, build_root = root / "html", root / "build"
    # The stored form is the roots' own intermediate, removed once they are
    # composed from it, so the gate that reads what the compile carried asks
    # for it to be kept.
    stored = build_root / "compiled-text"
    witness = root / "witness" / WITNESS_LANGUAGE
    environment = gate_build_env(root)
    witness_command, witness_environment = witness_build(
        WITNESS_LANGUAGE,
        witness,
        flavor=_FLAVOR,
        base_url=_BASE_URL,
        build_root=root / "witness" / "build",
        # The witness reads as narrowly as the compile beside it: the gate's own
        # bounded width, not one worker per core. The compile is told with
        # ``--jobs``; a build driven directly reads the same key, which the
        # compile's selectors keep from its caller for exactly this.
        base=gate_build_env(root / "witness-state", CADRUMO_DOCS_JOBS=gate_build_jobs()),
    )
    # Two threads over the owned command runner: the builds are concurrent, so
    # the gate costs the longer of them rather than their sum, and each reports
    # its own duration and its own output rather than the pair's.
    with ThreadPoolExecutor(max_workers=2) as pool:
        building = pool.submit(
            run_command,
            witness_command,
            cwd=REPO_ROOT,
            environment=witness_environment,
            errors="replace",
        )
        compiling = pool.submit(
            run_command,
            _compile_command(html_root, build_root, stored),
            cwd=REPO_ROOT,
            environment=environment,
            errors="replace",
        )
        compiled = _succeeded(compiling.result(), "one nitpicky compile")
        witnessed = _succeeded(building.result(), f"nitpicky {WITNESS_LANGUAGE} build the compile is measured against")
    print(
        f"One compile of {len(SITE_ROOT_LANGUAGES)} language(s) in {compiled.duration_seconds:.0f} s, "
        f"beside the {WITNESS_LANGUAGE} build it is measured against in {witnessed.duration_seconds:.0f} s",
        flush=True,
    )
    yield _Built(
        comparison=compare(html_root / WITNESS_LANGUAGE, witness, WITNESS_LANGUAGE),
        html_root=html_root,
        witness=witness,
        stored=stored,
    )


def test_the_witness_root_is_composed_byte_for_byte(built: _Built) -> None:
    """The composed root of the witness language is what its own build wrote.

    This is the whole proof. Every other language's root is the same structure
    composed with that language's own strings, so what a second witness could
    show is a defect in one language's strings, which the catalogue gates own.
    """
    assert built.comparison.differences == 0, (
        f"the composed {WITNESS_LANGUAGE} root differs from its own build:\n{built.comparison.report()}"
    )


def test_the_witness_root_is_the_same_set_of_files(built: _Built) -> None:
    """A site that is not the same set of files is not the same site.

    Reported apart from the differing stretches: the files the two roots share
    can all match while a whole page, or the script every page loads, is absent
    from one of them.
    """
    assert (built.comparison.missing, built.comparison.extra) == ([], []), (
        f"the composed {WITNESS_LANGUAGE} root is not the file set its own build wrote:\n{built.comparison.report()}"
    )


def test_the_comparison_read_the_whole_page_set(built: _Built) -> None:
    """Two empty roots are equal, so the claims above need a floor under them."""
    assert built.comparison.pages >= _MINIMUM_PAGES, (
        f"the comparison read {built.comparison.pages} page(s) of the {WITNESS_LANGUAGE} root, under the "
        f"{_MINIMUM_PAGES} the user-scope site has: the equality above says nothing about the pages it "
        "never opened"
    )


def test_every_declared_intended_difference_was_actually_observed(built: _Built) -> None:
    """A declaration nothing matches any more is a standing permission, so it fails.

    Each entry of ``INTENDED_DIFFERENCES`` names one page, one markup context
    and the exact bytes it excuses. A declaration that no longer matches has
    stopped describing this site and has started excusing whatever lands in that
    context next; a change made to every build at once belongs in
    ``UNWITNESSED_CHANGES``, which claims nothing the comparison could check.
    """
    declared = {entry.key for entry in INTENDED_DIFFERENCES}
    observed = {key for key, count in built.comparison.intended.items() if count}

    assert observed == declared, (
        f"declared but not observed: {sorted(declared - observed)}; "
        f"observed but not declared: {sorted(observed - declared)}"
    )


def test_the_compile_carries_every_language_the_product_publishes(built: _Built) -> None:
    """A published language the compile left out would be merely absent from the output."""
    # The published set is the OutputLanguage closed set, and the compile's own
    # stored form declares what it carried.
    carried = json.loads((built.stored / "layout.json").read_text(encoding="utf-8"))
    assert carried["languages"] == list(SITE_ROOT_LANGUAGES), (
        f"the compile carried {carried['languages']}, and the product publishes {list(SITE_ROOT_LANGUAGES)}"
    )
    absent = [language for language in SITE_ROOT_LANGUAGES if not (built.html_root / language / "index.html").is_file()]
    assert not absent, f"the compile wrote no entry page for {absent} under {built.html_root}"


def test_the_witness_build_is_the_operator_surface_and_excludes_the_api_tree(built: _Built) -> None:
    """The user scope builds its own pages and never reads the API autodoc tree.

    What the retired English dummy build asserted about its own read set, read
    here off the root the witness wrote instead: an enrolled user page is
    present, and the excluded API tree produced no page at all -- which is also
    what makes the API reference English-only, and therefore what the language
    switcher's entry-page substitution exists for.
    """
    assert (built.witness / "how-to" / "quickstart.html").is_file(), (
        f"the witness build wrote no enrolled user page under {built.witness}"
    )
    assert not (built.witness / "api").exists(), (
        f"the user-scope witness build rendered the API autodoc tree into {built.witness / 'api'}"
    )
