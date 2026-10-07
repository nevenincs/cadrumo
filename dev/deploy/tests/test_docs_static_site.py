"""Per-language root contracts and the one-index site composition of the documentation publisher."""

from __future__ import annotations

import ast
import contextlib
import gzip
import http.server
import inspect
import json
import os
import sys
import textwrap
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Final, override

import pytest

import dev.docs.i18n as _docs_i18n
from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.tests.env_scope import scoped_env_var
from dev._paths import REPO_ROOT
from dev.docs import compile_once as _compile_once
from dev.docs.build import pagefind_index_mode
from dev.docs.build_paths import docs_site_prefix
from dev.docs.pagefind_index import DECIDED_INJECTED_RECORD_KINDS
from dev.docs.sequence_build_gate import SEQUENCE_CHECK_SKIP_ENV, should_check_sequences

from .. import docs_delivery_activation as _docs_delivery_activation
from .. import docs_site_build as _docs_site_build
from .. import docs_site_languages as _docs_site_languages
from ..docs_delivery_contracts import (
    _REQUIRED_ROOT_ARTIFACTS,
    _REQUIRED_SITE_SEARCH_ARTIFACTS,
    CANONICAL_DOCS_BASE_URL,
)
from ..docs_site_build import _clear_apex, _compose_apex, _indexed_roots, _run_site_builds
from ..docs_site_download import _DOWNLOAD_LATEST_SCHEMA, _DOWNLOAD_LATEST_STATIC_PATH, _refresh_download_latest
from ..docs_site_languages import (
    TRANSLATED_ROOTS_BUILD,
    SiteBuild,
    _language_site_url,
    _write_language_entry,
    localized_languages,
    site_build_environment,
    site_build_jobs,
    site_builds,
    source_root_build_command,
    source_root_build_environment,
    translated_roots_compile_command,
)
from ..docs_site_preflight import _validate_built_site, _validate_language_entry, _validate_language_roots
from ..docs_static_site import _dry_run

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: An index page, an error page and a sitemap: the floor below which a
#: published root is not a usable site. Asserted before the set equality so
#: an emptied fixture and an emptied production tuple cannot satisfy each
#: other.
_MINIMUM_REQUIRED_ROOT_ARTIFACTS: Final[int] = 3

#: The four-file Pagefind bundle the site carries once, at its apex, for every
#: language's pages to load. Asserted for the same reason as the floor above.
_MINIMUM_REQUIRED_SEARCH_ARTIFACTS: Final[int] = 4

#: Pagefind writes these two trees with generated, content-derived file
#: names, so they are checked for substance rather than by name and are
#: not part of the fixed required-artifact set.
_GENERATED_INDEX_PREFIXES: Final[tuple[str, ...]] = ("pagefind/index/", "pagefind/fragment/")


@contextlib.contextmanager
def _replacing(target: object, name: str, value: object) -> Iterator[None]:
    """Replace ``target.name`` for the scope, restoring the original on exit."""
    original = getattr(target, name)
    setattr(target, name, value)
    try:
        yield
    finally:
        setattr(target, name, original)


def _materialise_language_root(html_root: Path, language: str) -> None:
    """Write a minimal VALID published site root satisfying the FULL artifact contract.

    "Valid" means what the publish contract means by it: every artifact
    ``_REQUIRED_ROOT_ARTIFACTS`` names -- the same complete set the English root
    must carry -- plus a sitemap correctly rooted at the language's own
    canonical sub-path. Before the fix a localized root was accepted with none
    of these.

    The search index is deliberately NOT written here: the site carries one, at
    its apex (:func:`_materialise_site_search_index`), and a root that carried
    its own would be exactly the per-language index this layout replaced.
    """
    _materialise_site_root(html_root / language, canonical_base=_language_site_url(language))


def _materialise_apex_root(html_root: Path) -> None:
    """Compose the apex around the language roots exactly as a publish does.

    The one search index is part of what the apex owes, and the index pass that
    writes it is the real Pagefind pass over the built roots; these tests supply
    it in its real on-disk shape instead (:func:`_materialise_site_search_index`).
    """
    _materialise_site_search_index(html_root)
    _compose_apex(html_root)


def _materialise_site_root(root: Path, *, canonical_base: str) -> None:
    """Write one site root's complete required-artifact set, rooted at its own URL.

    The error page declares the root's own site prefix, as a built page does:
    the apex copy of it is taken from the source-language root and has to be
    given the apex's prefix instead.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.html").write_text("<html></html>", encoding="utf-8")
    (root / "404.html").write_text(
        f'<html><head><meta name="cadrumo-docs-site-prefix" content="{root.name}/"></head></html>',
        encoding="utf-8",
    )
    canonical_root = f"{canonical_base}/"
    (root / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{canonical_root}</loc></url>\n"
        "</urlset>\n",
        encoding="utf-8",
    )


def _materialise_site_search_index(html_root: Path) -> None:
    """Write the site's ONE Pagefind bundle at the apex, carrying every decided kind.

    These fragments are SYNTHESISED, in the real on-disk shape, because what
    this module tests is the site-COMPOSITION logic: which roots are built,
    what the apex owes, and which failure stops a publish. The index READ
    itself is proven against real Pagefind output in
    ``test_publish_preflight_search_records``, where a genuine no-injection
    build is the subject.
    """
    pagefind_dir = html_root / "pagefind"
    pagefind_dir.mkdir(parents=True, exist_ok=True)
    (pagefind_dir / "pagefind-entry.json").write_text("{}", encoding="utf-8")
    (pagefind_dir / "pagefind.js").write_text("// pagefind", encoding="utf-8")
    (pagefind_dir / "pagefind-ui.js").write_text("// pagefind-ui", encoding="utf-8")
    (pagefind_dir / "pagefind-ui.css").write_text("/* pagefind-ui */", encoding="utf-8")
    index_dir = pagefind_dir / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "es_abc.pf_index").write_bytes(b"substantive-index-data")
    fragment_dir = pagefind_dir / "fragment"
    fragment_dir.mkdir(parents=True, exist_ok=True)
    for kind in sorted(DECIDED_INJECTED_RECORD_KINDS):
        payload = json.dumps({"url": f"/records/{kind}.html", "filters": {"kind": [kind]}})
        (fragment_dir / f"es_{kind}.pf_fragment").write_bytes(gzip.compress(f"pagefind_dcd{payload}".encode()))


def test_every_language_is_a_published_root_including_english() -> None:
    """No language holds the apex path; English is a root like the rest.

    The deploy roots deliberately are NOT the translation targets. English is
    absent from ``TARGET_LANGUAGES`` because it is the msgid source and needs no
    catalogue -- a translation fact. Reusing that set as the publish matrix is
    what put English at ``/`` and left readers of a Spanish-tax site landing in
    English, so the two concepts are now separate constants.
    """
    languages = localized_languages()
    assert set(languages) == {member.value for member in OutputLanguage}
    assert OutputLanguage.EN.value in languages
    assert languages != _docs_i18n.TARGET_LANGUAGES, "deploy roots must not be re-derived from the catalogue set"
    assert languages[0] == _docs_i18n.DEFAULT_SITE_LANGUAGE


def test_default_site_language_is_spanish() -> None:
    """A reader who has expressed no preference is sent to Spanish, not English."""
    assert OutputLanguage.ES.value == _docs_i18n.DEFAULT_SITE_LANGUAGE


def test_language_entry_routes_to_every_root_and_declares_the_spanish_floor(tmp_path: Path) -> None:
    """The apex entry reaches every built language and names the fallback."""
    _write_language_entry(tmp_path)
    body = (tmp_path / "index.html").read_text(encoding="utf-8")
    for language in localized_languages():
        assert f'"{language}"' in body
    assert _docs_i18n.DEFAULT_SITE_LANGUAGE in body
    _validate_language_entry(tmp_path)


def test_language_entry_validation_refuses_a_root_it_cannot_reach(tmp_path: Path) -> None:
    """A language that builds but is missing from the entry is invisible; refuse it.

    Nothing else in the pipeline notices an unreachable root: it uploads, it
    responds on its own URL, and no reader without that URL ever finds it.
    """
    _write_language_entry(tmp_path)
    entry = tmp_path / "index.html"
    entry.write_text(entry.read_text(encoding="utf-8").replace('"hu"', '"xx"'), encoding="utf-8")
    with pytest.raises(SystemExit, match="hu"):
        _validate_language_entry(tmp_path)


def test_language_site_url_is_a_subroot_of_the_canonical_docs_url() -> None:
    """A localized root URL is the canonical docs URL plus the language segment."""
    assert _language_site_url("es") == f"{CANONICAL_DOCS_BASE_URL}/es"


_SOURCE = _docs_i18n.DEFAULT_SOURCE_LANGUAGE
_TRANSLATED: tuple[str, ...] = tuple(language for language in localized_languages() if language != _SOURCE)


def test_the_source_root_is_the_full_scope_build_of_the_driver(tmp_path: Path) -> None:
    """English keeps the one Sphinx build of its own: strict, full scope, and no catalogue selected."""
    out_dir = tmp_path / "html" / _SOURCE
    command = source_root_build_command(out_dir)
    assert command[1:] == ["-m", "dev.docs.build", "--strict", "--isolated-source", "--out-dir", str(out_dir)]


def test_every_translated_root_comes_from_one_strict_compile_given_the_site_address(tmp_path: Path) -> None:
    """One command writes every translated root, and none of them is built with ``--language``.

    The compile is told the site's address ABOVE the language directories: each
    root takes its own canonical address and its own site prefix from it, so a
    per-language address here would be one language's address on every page.
    """
    html_root = tmp_path / "html"
    command = translated_roots_compile_command(html_root, ("es", "ca", "hu"), jobs=6)
    assert command[1:] == [
        "-m",
        "dev.docs.compile_once",
        "--html-root",
        str(html_root),
        "--build-root",
        str(tmp_path),
        "--flavor",
        "web",
        "--strict",
        "--base-url",
        CANONICAL_DOCS_BASE_URL,
        "--jobs",
        "6",
        "--languages",
        "es",
        "ca",
        "hu",
    ]
    assert "--language" not in command


def test_the_compile_reads_the_publishers_command_as_the_publisher_means_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The command is read back through the compile's own argument parser.

    Asserting the flags through the parser that consumes them is what keeps a
    renamed or dropped flag from passing: the compile would write the English
    root over the full-scope one, or every root without an address, while a
    comparison of raw strings went on agreeing with itself.
    """
    html_root = tmp_path / "html"
    command = translated_roots_compile_command(html_root, _TRANSLATED, jobs=3)
    recorded: dict[str, object] = {}
    named: list[str] = []

    def record(written_under: Path, *, languages: tuple[str, ...] | None = None, **settings: object) -> object:
        recorded.update(settings, html_root=written_under)
        named.extend(languages or ())
        return SimpleNamespace(
            languages=localized_languages(), roots=dict.fromkeys(named), seconds=0.0, html_root=written_under
        )

    monkeypatch.setattr(_compile_once, "compile_language_roots", record)
    monkeypatch.delenv(SEQUENCE_CHECK_SKIP_ENV, raising=False)

    assert _compile_once.main(command[3:]) == 0
    assert recorded["html_root"] == html_root
    assert recorded["build_root"] == tmp_path
    assert recorded["flavor"] == "web"
    assert recorded["strict"] is True
    assert recorded["base_url"] == CANONICAL_DOCS_BASE_URL
    assert recorded["jobs"] == 3
    assert tuple(named) == _TRANSLATED
    assert _SOURCE not in named


def test_two_builds_write_the_site_however_many_languages_it_publishes(tmp_path: Path) -> None:
    """A language added to the site adds text to the one compile, not a build to the publish."""
    builds = site_builds(tmp_path / "html")

    assert [build.name for build in builds] == [_SOURCE, TRANSLATED_ROOTS_BUILD]
    assert builds[0].languages == (_SOURCE,)
    assert builds[1].languages == _TRANSLATED
    assert len(_TRANSLATED) >= 3, "the fixture no longer proves that several languages share one build"
    source_jobs, compile_jobs = site_build_jobs(os.cpu_count() or 1, translated=True)
    assert builds[0].environment["CADRUMO_DOCS_JOBS"] == str(source_jobs)
    assert builds[1].command[builds[1].command.index("--jobs") + 1] == str(compile_jobs)


# Each stand-in build marks that it started, then waits until every build has
# started: builds run one after another never all start, so the wait times out
# and the build fails. It then writes a root for each language it was given,
# recording the storage root it ran under.
_BUILD_STAND_IN = textwrap.dedent(
    """
    import os, pathlib, sys, time
    html_root, expected, outcome = pathlib.Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    languages = sys.argv[4:]
    started = html_root.parent / "started"
    started.mkdir(parents=True, exist_ok=True)
    (started / languages[0]).touch()
    deadline = time.monotonic() + 60
    while len(list(started.iterdir())) < expected:
        if time.monotonic() > deadline:
            sys.exit(9)
        time.sleep(0.05)
    for language in languages:
        out = html_root / language
        out.mkdir(parents=True, exist_ok=True)
        (out / "storage.txt").write_text(os.environ["CADRUMO_LOCAL_STORAGE_ROOT"], encoding="utf-8")
        if outcome == "indexes":
            (out / "pagefind").mkdir()
    print(f"built {' '.join(languages)}")
    sys.exit(3 if outcome == "fails" else 0)
    """,
)


def _stand_in_builds(
    *, translated_outcome: str = "passes", translated_writes: tuple[str, ...] = _TRANSLATED
) -> Callable[[Path], tuple[SiteBuild, ...]]:
    """Return the publish's two builds with a small real command in place of each Sphinx run."""

    def builds(html_root: Path) -> tuple[SiteBuild, ...]:
        def command(outcome: str, languages: tuple[str, ...]) -> list[str]:
            return [sys.executable, "-c", _BUILD_STAND_IN, str(html_root), "2", outcome, *languages]

        return (
            SiteBuild(name=_SOURCE, languages=(_SOURCE,), command=command("passes", (_SOURCE,)), environment={}),
            SiteBuild(
                name=TRANSLATED_ROOTS_BUILD,
                languages=_TRANSLATED,
                command=command(translated_outcome, translated_writes),
                environment={},
            ),
        )

    return builds


def test_the_site_builds_run_at_once_each_with_its_own_storage_and_every_failure_named(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Both builds run concurrently, each in its own storage root, and a failed build stops the publish by name."""
    html_root = tmp_path / "html"

    with pytest.raises(SystemExit, match=r"failed for translated roots \(3\); refusing to publish") as refused:
        _run_site_builds(REPO_ROOT, html_root, builds_for=_stand_in_builds(translated_outcome="fails"))

    assert "9)" not in str(refused.value), "the builds did not run at once"
    storage = {
        language: (html_root / language / "storage.txt").read_text(encoding="utf-8")
        for language in localized_languages()
    }
    assert len({storage[language] for language in _TRANSLATED}) == 1, "one compile ran under more than one storage root"
    assert storage[_SOURCE] != storage[_TRANSLATED[0]], "the two builds shared a storage root"
    output = capsys.readouterr().out
    assert f"built {_SOURCE}" in output
    assert f"built {' '.join(_TRANSLATED)}" in output


def test_a_previous_publishs_per_root_index_is_removed_before_the_build(tmp_path: Path) -> None:
    """A root kept between publishes must not carry last release's index.

    The source root survives a publish for its Sphinx environment, and a build
    that writes no index of its own clears nothing. An index left inside a root
    would upload as current and answer a reader with the previous release's
    site, while every check stayed green because nothing asks a root for an
    index.
    """
    html_root = tmp_path / "html"
    languages = localized_languages()
    for language in languages:
        stale = html_root / language / "pagefind" / "index"
        stale.mkdir(parents=True)
        (stale / "es_stale.pf_index").write_bytes(b"last release")

    _run_site_builds(REPO_ROOT, html_root, builds_for=_stand_in_builds())

    for language in languages:
        assert not (html_root / language / "pagefind").exists(), f"the {language!r} root kept a stale index"


def test_a_build_that_succeeds_without_writing_one_of_its_roots_stops_the_publish(tmp_path: Path) -> None:
    """A compile that carried fewer languages than the site publishes must not publish a site missing one."""
    missing = _TRANSLATED[-1]

    with pytest.raises(SystemExit, match=rf"wrote no root for {missing}; refusing to publish"):
        _run_site_builds(REPO_ROOT, tmp_path / "html", builds_for=_stand_in_builds(translated_writes=_TRANSLATED[:-1]))


def test_a_root_that_comes_out_of_its_build_with_an_index_stops_the_publish(tmp_path: Path) -> None:
    """No root indexes itself, whichever build wrote it: the site's one index is at its apex."""
    with pytest.raises(SystemExit, match="holding a search index of their own"):
        _run_site_builds(REPO_ROOT, tmp_path / "html", builds_for=_stand_in_builds(translated_outcome="indexes"))


def test_the_one_index_covers_every_root_at_its_served_address(tmp_path: Path) -> None:
    """Every produced root is indexed under the directory it is served from.

    The prefix is the whole mechanism by which one index addresses four roots:
    a page's indexed URL becomes its address on the site, and the apex, which
    carries the index, carries no pages of its own.
    """
    roots = {language: tmp_path / language for language in localized_languages()}

    indexed = _indexed_roots(roots)

    assert [root.language for root in indexed] == sorted(roots)
    assert [root.url_prefix for root in indexed] == [f"{language}/" for language in sorted(roots)]
    assert [root.html_root for root in indexed] == [roots[language] for language in sorted(roots)]
    assert all(root.url_prefix for root in indexed), "no language holds the apex path on the published site"


def test_the_publisher_produces_its_roots_in_one_place(tmp_path: Path) -> None:
    """The build reaches its roots through one producer, and consumes what it returns.

    How the roots are produced has already changed once, from one build per
    language to one compile for every translated root. It stayed a change to
    this one function because nothing downstream reaches for the roots itself,
    which is what this pins.
    """
    calls = _direct_calls(_docs_site_build._build_site_roots)

    assert calls.index("_produce_language_roots") < calls.index("_index_site") < calls.index("_compose_apex")
    assert "_run_site_builds" not in calls, "the build bypasses its own root producer"
    produced = _direct_calls(_docs_site_build._produce_language_roots)
    assert "_run_site_builds" in produced, "the root producer no longer produces the roots"


@pytest.mark.parametrize("cpus", [1, 2, 4, 12, 64])
def test_the_two_builds_share_the_cpus_the_full_scope_root_taking_half(cpus: int) -> None:
    """The builds never fork more workers than CPUs between them once each has one."""
    source_jobs, compile_jobs = site_build_jobs(cpus, translated=True)

    assert source_jobs >= 1
    assert compile_jobs >= 1
    assert source_jobs + compile_jobs <= max(cpus, 2)
    if cpus >= 2:
        assert source_jobs == cpus // 2
        assert compile_jobs == cpus - cpus // 2
    assert site_build_jobs(cpus, translated=False) == (cpus, 0)


def test_the_source_root_environment_points_the_base_url_at_its_own_root() -> None:
    """The source root's build carries its own base URL, its site prefix, and no index of its own."""
    env = source_root_build_environment(check_sequences=True)
    assert env["CADRUMO_DOCS_BASE_URL"] == f"{CANONICAL_DOCS_BASE_URL}/{_SOURCE}"
    assert env["CADRUMO_DOCS_PAGEFIND_MODE"] == "none"
    assert env["CADRUMO_DOCS_JOBS"] == "auto"


def test_the_source_root_declares_the_directory_it_is_served_under() -> None:
    """The source root's pages carry their own directory as the site prefix.

    This is what makes a page resolve the site's one index one level up from its
    own root, and what completes a shared record's destination inside the
    language being read. Read through :func:`docs_site_prefix` -- the build's own
    resolver -- so a value the build would refuse cannot pass here. The
    translated roots take theirs from the compile, which derives every
    language's prefix from the site address it is given.
    """
    environment = source_root_build_environment(check_sequences=False)

    assert docs_site_prefix(environment) == f"{_SOURCE}/"


def test_the_site_pins_the_record_injected_contract_and_no_root_indexes_itself() -> None:
    """The one index is record-injected; the roots that feed it write no index at all.

    The deployed contract is ``full`` for the SITE, which is the environment the
    one index pass resolves its injector from, and ``none`` for the source root,
    because the site's index spans every root and a root that indexed itself
    would write one the served site never loads. Both are read through
    :func:`pagefind_index_mode` - the build's own resolver - rather than compared
    as raw strings, so this pins the contract the build will actually select.
    The translated roots are written by the compile, which pins its own
    selectors; the publish refuses any root that comes out of its build holding
    an index, whichever build wrote it.

    An ambient ``pages`` in the publishing session must not narrow the site's
    contract, which is why the deploy layer pins the key explicitly instead of
    relying on the build default; the hostile base below is the proof.
    """
    hostile_base = {"CADRUMO_DOCS_PAGEFIND_MODE": "pages"}

    assert pagefind_index_mode(site_build_environment(base_environment={})) == "full"
    assert pagefind_index_mode(site_build_environment(base_environment=hostile_base)) == "full"
    assert pagefind_index_mode(source_root_build_environment(check_sequences=False)) == "none"


def test_exactly_one_site_build_runs_the_cli_sequence_goldens_check(tmp_path: Path) -> None:
    """The deploy pays for the goldens check once, and never zero times.

    The check's subprocess scrubs every ``CADRUMO_*`` key and pins English, so
    the two builds cannot disagree and running it in both buys two identical
    answers. Read through :func:`should_check_sequences` - the build's own
    resolver - so this pins the behaviour the build will select rather than a
    key that merely looks right.
    """
    builds = site_builds(tmp_path / "html")
    checking = [build.name for build in builds if SEQUENCE_CHECK_SKIP_ENV not in build.environment]

    assert checking == [_SOURCE]
    for build in builds:
        with scoped_env_var(SEQUENCE_CHECK_SKIP_ENV, build.environment.get(SEQUENCE_CHECK_SKIP_ENV)):
            assert should_check_sequences() is (SEQUENCE_CHECK_SKIP_ENV not in build.environment)


def test_a_deploy_that_would_skip_the_goldens_check_everywhere_refuses(tmp_path: Path) -> None:
    """Losing the check in every build must stop the publish, not pass quietly.

    Skipping the repeat is only sound because one build still runs it. A
    refactor that drops it there would leave the deploy publishing a site
    whose CLI sequences were never checked against their goldens -- and would
    look exactly like a successful build.
    """
    with (
        _replacing(
            _docs_site_languages,
            "source_root_build_environment",
            lambda *, check_sequences: {SEQUENCE_CHECK_SKIP_ENV: "1"},
        ),
        pytest.raises(SystemExit) as refusal,
    ):
        site_builds(tmp_path / "html")

    assert "exactly one site build" in str(refusal.value)


def test_validate_language_roots_accepts_a_complete_matrix(tmp_path: Path) -> None:
    """Validation passes when every localized root carries the complete required-artifact set."""
    for language in localized_languages():
        _materialise_language_root(tmp_path, language)
    _validate_language_roots(tmp_path)


def test_validate_language_roots_refuses_a_missing_index(tmp_path: Path) -> None:
    """A localized root without its rendered index page fails validation."""
    for language in localized_languages():
        _materialise_language_root(tmp_path, language)
    missing = localized_languages()[0]
    (tmp_path / missing / "index.html").unlink()
    with pytest.raises(SystemExit, match="required artifacts are missing"):
        _validate_language_roots(tmp_path)


@pytest.mark.parametrize("missing_artifact", sorted(_REQUIRED_ROOT_ARTIFACTS))
def test_validate_language_roots_refuses_each_missing_required_artifact(tmp_path: Path, missing_artifact: str) -> None:
    """A localized root missing ANY required artifact fails validation, not only its index page.

    Reproduces the audit finding: before the fix, a localized root could pass
    with no 404 page and no sitemap at all -- only ``index.html`` and a
    substantive Pagefind index chunk were mandatory.
    """
    for language in localized_languages():
        _materialise_language_root(tmp_path, language)
    target_language = localized_languages()[0]
    (tmp_path / target_language / missing_artifact).unlink()
    with pytest.raises(SystemExit, match="required artifacts are missing"):
        _validate_language_roots(tmp_path)


def test_every_artifact_a_valid_root_carries_is_a_required_root_artifact(tmp_path: Path) -> None:
    """The required-artifact tuple itself is pinned, not only the rule that reads it.

    Every check above draws its cases FROM ``_REQUIRED_ROOT_ARTIFACTS``: the
    parametrized refusal iterates it, and the roots the fixture builds are
    accepted precisely because they carry it. That proves the rule and
    leaves the roster unverified -- dropping one entry deletes both the
    publish requirement and the case that would have missed it, and the
    suite stays green with one silently fewer test.

    So the roster is compared against the independently spelled root that
    ``_materialise_site_root`` writes, which is what a deployable root
    actually contains. Removing an artifact from the publish contract now
    has to be a deliberate edit on both sides rather than a silent one.
    """
    _materialise_site_root(tmp_path, canonical_base=CANONICAL_DOCS_BASE_URL)
    carried = {
        path.relative_to(tmp_path).as_posix()
        for path in scan_directory(tmp_path, pattern="*", recursive=True, select=DirectoryEntryKind.FILES)
    }

    assert len(carried) >= _MINIMUM_REQUIRED_ROOT_ARTIFACTS, carried
    assert set(_REQUIRED_ROOT_ARTIFACTS) == carried


def test_every_search_artifact_the_apex_carries_is_a_required_site_artifact(tmp_path: Path) -> None:
    """The site search roster is pinned the same way, against the apex bundle.

    The second half of the contract, and the half the roots no longer carry:
    the bundle is the site's, written once, so a dropped entry would be every
    language's search gone rather than one root's.
    """
    _materialise_site_search_index(tmp_path)
    carried = {
        path.relative_to(tmp_path).as_posix()
        for path in scan_directory(tmp_path, pattern="*", recursive=True, select=DirectoryEntryKind.FILES)
    }
    named = {artifact for artifact in carried if not artifact.startswith(_GENERATED_INDEX_PREFIXES)}

    assert len(named) >= _MINIMUM_REQUIRED_SEARCH_ARTIFACTS, named
    assert set(_REQUIRED_SITE_SEARCH_ARTIFACTS) == named


def test_validate_language_roots_refuses_a_sitemap_rooted_at_the_wrong_url(tmp_path: Path) -> None:
    """A localized root's sitemap must be rooted at its OWN language sub-path, not English."""
    for language in localized_languages():
        _materialise_language_root(tmp_path, language)
    target_language = localized_languages()[0]
    (tmp_path / target_language / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{CANONICAL_DOCS_BASE_URL}/</loc></url>\n"
        "</urlset>\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="missing the canonical docs root"):
        _validate_language_roots(tmp_path)


def test_the_site_is_refused_when_its_one_pagefind_index_has_no_substantive_data(tmp_path: Path) -> None:
    """An apex index with no substantive data fails validation for the whole site.

    One index means one failure for every language at once, so the refusal
    belongs to the site and not to a root. Before, four roots each carried one
    and an emptied one named its own language.
    """
    for language in localized_languages():
        _materialise_language_root(tmp_path, language)
    _materialise_apex_root(tmp_path)
    for chunk in scan_directory(tmp_path / "pagefind" / "index", pattern="*.pf_index", recursive=True):
        chunk.write_bytes(b"")

    with pytest.raises(SystemExit, match="no substantive generated index data"):
        _validate_built_site(tmp_path)


def test_the_site_is_refused_when_the_apex_carries_no_search_bundle(tmp_path: Path) -> None:
    """The apex owes the one bundle every language's pages load; a gap stops the publish."""
    for language in localized_languages():
        _materialise_language_root(tmp_path, language)
    _materialise_apex_root(tmp_path)
    (tmp_path / "pagefind" / "pagefind.js").unlink()

    with pytest.raises(SystemExit, match="apex is not deployable"):
        _validate_built_site(tmp_path)


def test_no_published_root_carries_a_search_index_of_its_own(tmp_path: Path) -> None:
    """A valid published root has no ``pagefind/`` directory at all.

    The point of one index is that the per-language ones are gone; a root that
    still carried one would be uploaded, served and searched, and every check
    above would stay green because nothing asks a root for an index any more.
    """
    for language in localized_languages():
        _materialise_language_root(tmp_path, language)
    _materialise_apex_root(tmp_path)

    _validate_built_site(tmp_path)

    for language in localized_languages():
        assert not (tmp_path / language / "pagefind").exists(), f"the {language!r} root carries its own index"


def _direct_calls(function: Callable[..., object]) -> list[str]:
    """Return the plain-name calls a function makes, in source order."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    return [node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]


def test_the_publish_reaches_upload_through_the_composition_the_dry_run_runs() -> None:
    """Publish and dry run share ONE build-and-validate prefix, and nothing may re-inline it.

    The dry run is only worth running if its verdict is the publish's verdict.
    That holds today because both go through ``_build_site_roots`` and
    ``_validate_built_site``, but "holds by construction" is not a gate: the
    exact shape that existed before this composition was extracted -- the
    validation calls written out inline in the publish -- would reintroduce a
    dry run that passes where a publish refuses, with a green suite. So the
    inlined form is refused here by name.
    """
    calls = _direct_calls(_docs_delivery_activation._publish)
    assert calls.index("_build_site_roots") < calls.index("_validate_built_site") < calls.index("_upload_release"), (
        f"the publish no longer builds, then validates, then uploads: {calls}"
    )
    inlined = sorted(
        {"_run_site_builds", "_write_language_entry", "_validate_language_entry", "_validate_language_roots"}
        & set(calls)
    )
    assert not inlined, f"the publish re-inlines {inlined} instead of sharing the dry run's composition"

    assert inspect.signature(_dry_run).parameters["build"].default is _docs_site_build._build_site_roots


def test_dry_run_validates_a_complete_built_site_and_uploads_nothing(tmp_path: Path) -> None:
    """The dry run passes on a complete multi-root tree, touching no AWS surface.

    The verb exists because the whole build-and-validate prefix used to be
    reachable only through ``publish``: the roots could not be checked until
    bytes were already going to a live destination. Its subject is the built
    tree, so the build is supplied here as a real prepared multi-root artefact
    and the validation half runs production code against real files on disk.
    """
    for language in localized_languages():
        _materialise_language_root(tmp_path, language)
    _materialise_apex_root(tmp_path)

    assert _dry_run(tmp_path, build=lambda _: tmp_path) == 0


def test_dry_run_refuses_a_root_that_would_publish_incomplete(tmp_path: Path) -> None:
    """The dry run's verdict is the publish's verdict: an incomplete root refuses.

    A dry run that passed where the publish would refuse would be worse than
    no dry run at all, so the refusal is asserted on the same defect the
    publish path refuses on.
    """
    for language in localized_languages():
        _materialise_language_root(tmp_path, language)
    _materialise_apex_root(tmp_path)
    (tmp_path / localized_languages()[0] / "404.html").unlink()

    with pytest.raises(SystemExit, match="required artifacts are missing"):
        _dry_run(tmp_path, build=lambda _: tmp_path)


def test_the_apex_carries_the_entry_error_page_sitemap_index_and_the_one_search_index(tmp_path: Path) -> None:
    """No site is built at the apex; it indexes every root's sitemap and holds the one index."""
    for language in localized_languages():
        _materialise_language_root(tmp_path, language)
    _materialise_apex_root(tmp_path)

    apex_files = {entry.name for entry in tmp_path.iterdir() if entry.is_file()}
    assert apex_files == {"index.html", "404.html", "sitemap.xml"}
    apex_directories = {entry.name for entry in tmp_path.iterdir() if entry.is_dir()}
    assert apex_directories == {"pagefind", *localized_languages()}
    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    for language in localized_languages():
        assert f"<loc>{_language_site_url(language)}/sitemap.xml</loc>" in sitemap


def test_the_apex_error_page_declares_the_apex_as_its_place_in_the_site(tmp_path: Path) -> None:
    """The apex copy of the source-language error page carries no language prefix.

    A page resolves the site's one index by walking back the prefix it declares.
    The source-language root's error page declares that root, which is right at
    ``/en/404.html`` and one level too far at ``/404.html``: the apex copy would
    look for the index above the documentation mount. Its own root's copy keeps
    its prefix, so this is a property of the copy, not of the page.
    """
    for language in localized_languages():
        _materialise_language_root(tmp_path, language)
    _materialise_apex_root(tmp_path)

    source = _docs_i18n.DEFAULT_SOURCE_LANGUAGE
    assert 'content=""' in (tmp_path / "404.html").read_text(encoding="utf-8")
    assert f'content="{source}/"' in (tmp_path / source / "404.html").read_text(encoding="utf-8")


def test_an_error_page_declaring_no_site_prefix_stops_the_publish(tmp_path: Path) -> None:
    """A page the template stopped declaring a prefix on must not be copied blind.

    The substitution would silently do nothing, which happens to be correct
    while the apex is the site's root and is wrong the moment it is not. A
    template change has to reach this composition.
    """
    for language in localized_languages():
        _materialise_language_root(tmp_path, language)
    source = tmp_path / _docs_i18n.DEFAULT_SOURCE_LANGUAGE / "404.html"
    source.write_text("<html><head></head></html>", encoding="utf-8")

    with pytest.raises(SystemExit, match="declares no site prefix"):
        _compose_apex(tmp_path)


def test_dry_run_refuses_an_apex_sitemap_index_missing_a_root(tmp_path: Path) -> None:
    for language in localized_languages():
        _materialise_language_root(tmp_path, language)
    _materialise_apex_root(tmp_path)
    dropped = localized_languages()[-1]
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text(
        sitemap.read_text(encoding="utf-8").replace(f"{_language_site_url(dropped)}/sitemap.xml", "https://x.invalid/"),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="not every language root's sitemap"):
        _dry_run(tmp_path, build=lambda _: tmp_path)


def test_clearing_the_apex_keeps_only_the_language_roots(tmp_path: Path) -> None:
    """A full site or an index left at the apex by an earlier publish is never uploaded as current.

    The apex now carries the site's one search index, so the clearing also has
    to remove it: a previous release's index left in place would be uploaded
    beside this release's pages and answer readers from the wrong corpus.
    """
    for language in localized_languages():
        _materialise_language_root(tmp_path, language)
    _materialise_site_search_index(tmp_path)
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "stale.html").write_text("x", encoding="utf-8")
    (tmp_path / "how-to.html").write_text("x", encoding="utf-8")

    _clear_apex(tmp_path)

    assert {entry.name for entry in tmp_path.iterdir()} == set(localized_languages())


def test_dry_run_refuses_an_apex_entry_that_strands_a_root(tmp_path: Path) -> None:
    """The apex half of the publish's validation runs in the dry run too."""
    for language in localized_languages():
        _materialise_language_root(tmp_path, language)
    _materialise_apex_root(tmp_path)
    stranded = localized_languages()[-1]
    entry = tmp_path / "index.html"
    entry.write_text(entry.read_text(encoding="utf-8").replace(f'"{stranded}"', '"zz"'), encoding="utf-8")

    with pytest.raises(SystemExit, match="does not route to"):
        _dry_run(tmp_path, build=lambda _: tmp_path)


class _StaticResponseHandler(http.server.BaseHTTPRequestHandler):
    """Serve one fixed status/body for every request; overridden per server instance."""

    response_status = 200
    response_body = b""

    def do_GET(self) -> None:
        self.send_response(self.response_status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.response_body)

    @override
    def log_message(self, format: str, *args: object) -> None:
        return  # silence per-request access logging in test output


@contextlib.contextmanager
def _serving(*, status: int = 200, body: bytes = b"") -> Iterator[str]:
    """Run a real localhost HTTP server for the duration of the block; yield its URL."""
    handler_cls = type("_Handler", (_StaticResponseHandler,), {"response_status": status, "response_body": body})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[0], server.server_address[1]
        yield f"http://{host}:{port}/download-latest.json"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def _closed_port_url() -> str:
    """Return a URL to a localhost port with nothing listening, for a real connection failure."""
    with _serving() as url:
        pass
    return url  # the server above is torn down; the port is now refused


def _download_latest_path(repo_root: Path) -> Path:
    return repo_root.joinpath(*_DOWNLOAD_LATEST_STATIC_PATH)


def _seed_stale_download_latest(repo_root: Path) -> Path:
    """Pre-seed a valid-looking prior release payload at the destination.

    Simulates the shape the audit finding names: a previous successful
    refresh already wrote a real payload, and a LATER refresh attempt fails.
    """
    destination = _download_latest_path(repo_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps({"schema_name": _DOWNLOAD_LATEST_SCHEMA, "version": "0.1.0-stale", "assets": []}),
        encoding="utf-8",
    )
    return destination


def test_refresh_download_latest_writes_a_valid_payload(tmp_path: Path) -> None:
    """A valid latest-release payload is written into docs/_static."""
    body = json.dumps({"schema_name": _DOWNLOAD_LATEST_SCHEMA, "version": "9.9.9", "assets": []}).encode("utf-8")
    with _serving(body=body) as url:
        _refresh_download_latest(tmp_path, source_url=url)
    written = _download_latest_path(tmp_path)
    assert written.is_file()
    assert json.loads(written.read_bytes())["schema_name"] == _DOWNLOAD_LATEST_SCHEMA


def test_refresh_download_latest_degrades_on_network_error(tmp_path: Path) -> None:
    """No release yet / network error degrades silently: no raise, no file."""
    _refresh_download_latest(tmp_path, source_url=_closed_port_url())  # must not raise
    assert not _download_latest_path(tmp_path).exists()


def test_refresh_download_latest_degrades_on_unexpected_payload(tmp_path: Path) -> None:
    """A body that is not the expected schema (e.g. a 404 page) degrades silently."""
    with _serving(body=b"<html>not found</html>") as url:
        _refresh_download_latest(tmp_path, source_url=url)  # must not raise
    assert not _download_latest_path(tmp_path).exists()


def test_refresh_download_latest_degrades_on_write_failure(tmp_path: Path) -> None:
    """A local write failure (a path component is a plain file, not a directory) degrades silently."""
    body = json.dumps({"schema_name": _DOWNLOAD_LATEST_SCHEMA, "version": "9.9.9", "assets": []}).encode("utf-8")
    # `docs/_static/download-latest.json` requires `docs/` to be a directory; making it a
    # plain file forces a real OSError (NotADirectoryError) out of destination.parent.mkdir.
    (tmp_path / "docs").write_text("not a directory", encoding="utf-8")
    with _serving(body=body) as url:
        _refresh_download_latest(tmp_path, source_url=url)  # must not raise despite the write failure
    assert not _download_latest_path(tmp_path).exists()


def test_refresh_download_latest_invalidates_a_preseeded_stale_payload_on_network_error(tmp_path: Path) -> None:
    """A prior successful refresh's payload must not survive a failed re-run.

    Reproduces the audit finding: every failure branch used to return
    without touching a payload retained from an earlier successful run, so a
    later documentation build would publish that prior release's stale
    download links as though they were current.
    """
    stale = _seed_stale_download_latest(tmp_path)
    assert stale.is_file()

    _refresh_download_latest(tmp_path, source_url=_closed_port_url())

    assert not stale.exists()


def test_refresh_download_latest_invalidates_a_preseeded_stale_payload_on_malformed_json(tmp_path: Path) -> None:
    """A preseeded stale payload is invalidated when the new response is not JSON."""
    stale = _seed_stale_download_latest(tmp_path)
    assert stale.is_file()

    with _serving(body=b"<html>not found</html>") as url:
        _refresh_download_latest(tmp_path, source_url=url)

    assert not stale.exists()


def test_refresh_download_latest_invalidates_a_preseeded_stale_payload_on_schema_mismatch(tmp_path: Path) -> None:
    """A preseeded stale payload is invalidated when the new response is valid JSON but the wrong schema."""
    stale = _seed_stale_download_latest(tmp_path)
    assert stale.is_file()
    body = json.dumps({"schema_name": "cadrumo.some-other-schema.v1", "version": "9.9.9"}).encode("utf-8")

    with _serving(body=body) as url:
        _refresh_download_latest(tmp_path, source_url=url)

    assert not stale.exists()
