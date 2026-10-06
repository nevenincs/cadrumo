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
from typing import Final, override

import pytest

import dev.docs.i18n as _docs_i18n
from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.tests.env_scope import scoped_env_var
from dev._paths import REPO_ROOT
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
from ..docs_site_build import _build_language_roots, _clear_apex, _compose_apex, _indexed_roots
from ..docs_site_download import _DOWNLOAD_LATEST_SCHEMA, _DOWNLOAD_LATEST_STATIC_PATH, _refresh_download_latest
from ..docs_site_languages import (
    _language_build_environments,
    _language_site_url,
    _write_language_entry,
    language_build_command,
    language_build_environment,
    localized_languages,
    root_build_jobs,
    site_build_environment,
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


def test_language_build_command_reuses_the_driver_language_and_out_dir_flags(tmp_path: Path) -> None:
    """The localized build command drives dev.docs.build with the user scope, language, and out-dir."""
    out_dir = tmp_path / "html" / "ca"
    command = language_build_command("ca", out_dir)
    assert command[1:] == [
        "-m",
        "dev.docs.build",
        "--strict",
        "--isolated-source",
        "--scope",
        "user",
        "--language",
        "ca",
        "--out-dir",
        str(out_dir),
    ]


# Each stand-in root records the storage root it was given, then waits until
# every root has started: roots built one after another never all start, so the
# wait times out and the root fails. ``ca`` then fails on purpose.
_ROOT_STAND_IN = textwrap.dedent(
    """
    import os, pathlib, sys, time
    out = pathlib.Path(sys.argv[1])
    started = out.parent / "started"
    started.mkdir(parents=True, exist_ok=True)
    (started / out.name).touch()
    deadline = time.monotonic() + 60
    while len(list(started.iterdir())) < int(sys.argv[2]):
        if time.monotonic() > deadline:
            sys.exit(9)
        time.sleep(0.05)
    out.mkdir(parents=True, exist_ok=True)
    (out / "storage.txt").write_text(os.environ["CADRUMO_LOCAL_STORAGE_ROOT"], encoding="utf-8")
    (out / "jobs.txt").write_text(os.environ["CADRUMO_DOCS_JOBS"], encoding="utf-8")
    print(f"built {out.name}")
    sys.exit(3 if out.name == "ca" else 0)
    """,
)


def test_the_language_roots_build_at_once_each_with_its_own_storage_and_every_failure_named(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every root runs concurrently, in its own storage root, and a failed root stops the publish by name."""
    html_root = tmp_path / "html"
    languages = localized_languages()

    def stand_in(_language: str, out_dir: Path) -> list[str]:
        return [sys.executable, "-c", _ROOT_STAND_IN, str(out_dir), str(len(languages))]

    with pytest.raises(SystemExit, match=r"failed for ca \(3\); refusing to publish") as refused:
        _build_language_roots(REPO_ROOT, html_root, command_for=stand_in)

    assert "9)" not in str(refused.value), "the roots did not all run at once"
    storage_roots = {(html_root / language / "storage.txt").read_text(encoding="utf-8") for language in languages}
    assert len(storage_roots) == len(languages)
    expected_jobs = root_build_jobs(languages, os.cpu_count() or 1)
    for language in languages:
        assert (html_root / language / "jobs.txt").read_text(encoding="utf-8") == expected_jobs[language]
    output = capsys.readouterr().out
    for language in languages:
        assert f"built {language}" in output


def test_a_previous_publishs_per_root_index_is_removed_before_the_build(tmp_path: Path) -> None:
    """A root kept between publishes must not carry last release's index.

    The roots survive a publish for their Sphinx environment, and a build that
    writes no index of its own clears nothing. An index left inside a root would
    upload as current and answer a reader with the previous release's site,
    while every check stayed green because nothing asks a root for an index.
    """
    html_root = tmp_path / "html"
    languages = localized_languages()
    for language in languages:
        stale = html_root / language / "pagefind" / "index"
        stale.mkdir(parents=True)
        (stale / "es_stale.pf_index").write_bytes(b"last release")

    def stand_in(_language: str, out_dir: Path) -> list[str]:
        return [sys.executable, "-c", _ROOT_STAND_IN, str(out_dir), str(len(languages))]

    with pytest.raises(SystemExit, match="refusing to publish"):
        _build_language_roots(REPO_ROOT, html_root, command_for=stand_in)

    for language in languages:
        assert not (html_root / language / "pagefind").exists(), f"the {language!r} root kept a stale index"


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

    The producer is about to be replaced: the roots will be composed from one
    stored structure plus each language's text instead of built per language.
    That is a change to this one function only as long as nothing downstream
    reaches for the roots itself, which is what this pins.
    """
    calls = _direct_calls(_docs_site_build._build_site_roots)

    assert calls.index("_produce_language_roots") < calls.index("_index_site") < calls.index("_compose_apex")
    assert "_build_language_roots" not in calls, "the build bypasses its own root producer"
    produced = _direct_calls(_docs_site_build._produce_language_roots)
    assert "_build_language_roots" in produced, "the root producer no longer produces the roots"


@pytest.mark.parametrize("cpus", [1, 2, 4, 12, 64])
def test_concurrent_roots_share_the_cpus_the_full_scope_root_taking_half(cpus: int) -> None:
    """The roots never fork more workers than CPUs between them once each has one."""
    languages = localized_languages()
    jobs = {language: int(count) for language, count in root_build_jobs(languages, cpus).items()}

    assert set(jobs) == set(languages)
    assert min(jobs.values()) >= 1
    assert sum(jobs.values()) <= max(cpus, len(languages))
    source = _docs_i18n.DEFAULT_SOURCE_LANGUAGE
    assert all(jobs[source] >= count for count in jobs.values())
    if cpus >= 2 * (len(languages) - 1):
        assert jobs[source] == cpus // 2


def test_language_build_environment_points_the_base_url_at_the_language_root() -> None:
    """Each root build carries its own base URL, its site prefix, and no index of its own."""
    env = language_build_environment("hu", check_sequences=True)
    assert env["CADRUMO_DOCS_BASE_URL"] == f"{CANONICAL_DOCS_BASE_URL}/hu"
    assert env["CADRUMO_DOCS_PAGEFIND_MODE"] == "none"
    assert env["CADRUMO_DOCS_JOBS"] == "auto"


@pytest.mark.parametrize("language", localized_languages())
def test_every_root_declares_the_directory_it_is_served_under(language: str) -> None:
    """Each root's pages carry their own directory as the site prefix.

    This is what makes a page resolve the site's one index one level up from its
    own root, and what completes a shared record's destination inside the
    language being read. Read through :func:`docs_site_prefix` -- the build's own
    resolver -- so a value the build would refuse cannot pass here.
    """
    environment = language_build_environment(language, check_sequences=False)

    assert docs_site_prefix(environment) == f"{language}/"


def test_the_site_pins_the_record_injected_contract_and_no_root_indexes_itself() -> None:
    """The one index is record-injected; the roots that feed it write no index at all.

    The deployed contract is ``full`` for the SITE, which is the environment the
    one index pass resolves its injector from, and ``none`` for every root,
    because the site's index spans them all and a root that indexed itself would
    write one the served site never loads. Both are read through
    :func:`pagefind_index_mode` - the build's own resolver - rather than compared
    as raw strings, so this pins the contract the build will actually select.

    An ambient ``pages`` in the publishing session must not narrow the site's
    contract, which is why the deploy layer pins the key explicitly instead of
    relying on the build default; the hostile base below is the proof.
    """
    hostile_base = {"CADRUMO_DOCS_PAGEFIND_MODE": "pages"}

    assert pagefind_index_mode(site_build_environment(base_environment={})) == "full"
    assert pagefind_index_mode(site_build_environment(base_environment=hostile_base)) == "full"
    for language in localized_languages():
        assert pagefind_index_mode(language_build_environment(language, check_sequences=False)) == "none"


def test_exactly_one_site_root_runs_the_cli_sequence_goldens_check() -> None:
    """The deploy pays for the goldens check once, and never zero times.

    The check's subprocess scrubs every ``CADRUMO_*`` key and pins English, so
    the four roots cannot disagree and running it per-root buys four identical
    answers. Read through :func:`should_check_sequences` - the build's own
    resolver - so this pins the behaviour the build will select rather than a
    key that merely looks right.
    """
    environments = _language_build_environments()
    checking = [language for language, env in environments if SEQUENCE_CHECK_SKIP_ENV not in env]

    assert len(environments) == len(localized_languages())
    assert len(checking) == 1
    for _language, env in environments:
        with scoped_env_var(SEQUENCE_CHECK_SKIP_ENV, env.get(SEQUENCE_CHECK_SKIP_ENV)):
            assert should_check_sequences() is (SEQUENCE_CHECK_SKIP_ENV not in env)


def test_a_deploy_that_would_skip_the_goldens_check_everywhere_refuses() -> None:
    """Losing the check on every root must stop the publish, not pass quietly.

    Skipping the repeats is only sound because one root still runs it. A
    refactor that drops that root would leave the deploy publishing a site
    whose CLI sequences were never checked against their goldens -- and would
    look exactly like a successful build.
    """
    with (
        _replacing(
            _docs_site_languages,
            "language_build_environment",
            lambda language, *, check_sequences: {SEQUENCE_CHECK_SKIP_ENV: "1"},
        ),
        pytest.raises(SystemExit) as refusal,
    ):
        _language_build_environments()

    assert "exactly one site root" in str(refusal.value)


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
        {"_build_language_roots", "_write_language_entry", "_validate_language_entry", "_validate_language_roots"}
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
