"""Per-language deploy-matrix contracts of the documentation publisher."""

from __future__ import annotations

import ast
import contextlib
import gzip
import http.server
import inspect
import json
import textwrap
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Final, override

import pytest

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.tests.env_scope import scoped_env_var

from ...docs.build import pagefind_index_mode
from ...docs.i18n import DEFAULT_SITE_LANGUAGE, TARGET_LANGUAGES
from ...docs.pagefind_index import DECIDED_INJECTED_RECORD_KINDS
from ...docs.sequence_build_gate import SEQUENCE_CHECK_SKIP_ENV, should_check_sequences
from .. import docs_static_site as _docs_static_site
from ..docs_static_site import (
    _DOWNLOAD_LATEST_SCHEMA,
    _DOWNLOAD_LATEST_STATIC_PATH,
    _REQUIRED_ARTIFACTS,
    CANONICAL_DOCS_BASE_URL,
    _dry_run,
    _language_build_command,
    _language_build_environment,
    _language_build_environments,
    _language_site_url,
    _localized_languages,
    _refresh_download_latest,
    _site_build_environment,
    _validate_language_entry,
    _validate_language_roots,
    _write_language_entry,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: An index page, an error page, a sitemap, and the four-file Pagefind
#: bundle: the floor below which a published root is not a usable site.
#: Asserted before the set equality so an emptied fixture and an emptied
#: production tuple cannot satisfy each other.
_MINIMUM_REQUIRED_ARTIFACTS: Final[int] = 7

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
    """Write a minimal VALID localized site root satisfying the FULL artifact contract.

    "Valid" now means what the publish contract means by it: not only the
    index page and a non-empty, record-carrying Pagefind index, but every
    artifact ``_REQUIRED_ARTIFACTS`` names -- the same complete set the
    English root must carry -- plus a sitemap correctly rooted at the
    language's own canonical sub-path. Before the fix a localized root was
    accepted with none of these; the fragments below carry the decided
    record kinds so a complete matrix is complete under the real contract.

    These fragments are SYNTHESISED, in the real on-disk shape, because what
    this module tests is the root-MATRIX logic: that every language is visited
    and the failing one is named. The index READ itself is proven against real
    Pagefind output in ``test_publish_preflight_search_records``, where a
    genuine no-injection build is the subject.
    """
    _materialise_site_root(html_root / language, canonical_base=_language_site_url(language))


def _materialise_apex_root(html_root: Path) -> None:
    """Write the apex's own artifact set, then the language entry over its index page.

    The apex is a site root in its own right -- it carries the English
    full-scope build, its sitemap is rooted at the canonical docs URL rather
    than a language sub-path, and its Pagefind bundle is the one the published
    site is checked against after upload -- so a tree that omits it is not a
    complete built site and must not stand in for one here.
    """
    _materialise_site_root(html_root, canonical_base=CANONICAL_DOCS_BASE_URL)
    _write_language_entry(html_root)


def _materialise_site_root(root: Path, *, canonical_base: str) -> None:
    """Write one site root's complete required-artifact set, rooted at its own URL."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.html").write_text("<html></html>", encoding="utf-8")
    (root / "404.html").write_text("<html></html>", encoding="utf-8")
    canonical_root = f"{canonical_base}/"
    (root / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{canonical_root}</loc></url>\n"
        "</urlset>\n",
        encoding="utf-8",
    )
    pagefind_dir = root / "pagefind"
    pagefind_dir.mkdir(parents=True, exist_ok=True)
    (pagefind_dir / "pagefind-entry.json").write_text("{}", encoding="utf-8")
    (pagefind_dir / "pagefind.js").write_text("// pagefind", encoding="utf-8")
    (pagefind_dir / "pagefind-ui.js").write_text("// pagefind-ui", encoding="utf-8")
    (pagefind_dir / "pagefind-ui.css").write_text("/* pagefind-ui */", encoding="utf-8")
    index_dir = pagefind_dir / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "en_abc.pf_index").write_bytes(b"substantive-index-data")
    fragment_dir = pagefind_dir / "fragment"
    fragment_dir.mkdir(parents=True, exist_ok=True)
    for kind in sorted(DECIDED_INJECTED_RECORD_KINDS):
        payload = json.dumps({"url": f"/records/{kind}.html", "filters": {"kind": [kind]}})
        (fragment_dir / f"en_{kind}.pf_fragment").write_bytes(gzip.compress(f"pagefind_dcd{payload}".encode()))


def test_every_language_is_a_published_root_including_english() -> None:
    """No language holds the apex path; English is a root like the rest.

    The deploy roots deliberately are NOT the translation targets. English is
    absent from ``TARGET_LANGUAGES`` because it is the msgid source and needs no
    catalogue -- a translation fact. Reusing that set as the publish matrix is
    what put English at ``/`` and left readers of a Spanish-tax site landing in
    English, so the two concepts are now separate constants.
    """
    languages = _localized_languages()
    assert set(languages) == {member.value for member in OutputLanguage}
    assert OutputLanguage.EN.value in languages
    assert languages != TARGET_LANGUAGES, "deploy roots must not be re-derived from the catalogue set"
    assert languages[0] == DEFAULT_SITE_LANGUAGE


def test_default_site_language_is_spanish() -> None:
    """A reader who has expressed no preference is sent to Spanish, not English."""
    assert OutputLanguage.ES.value == DEFAULT_SITE_LANGUAGE


def test_language_entry_routes_to_every_root_and_declares_the_spanish_floor(tmp_path: Path) -> None:
    """The apex entry reaches every built language and names the fallback."""
    _write_language_entry(tmp_path)
    body = (tmp_path / "index.html").read_text(encoding="utf-8")
    for language in _localized_languages():
        assert f'"{language}"' in body
    assert DEFAULT_SITE_LANGUAGE in body
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
    command = _language_build_command("ca", out_dir)
    assert command[1:] == [
        "-m",
        "dev.docs.build",
        "--strict",
        "--scope",
        "user",
        "--language",
        "ca",
        "--out-dir",
        str(out_dir),
    ]


def test_language_build_environment_points_the_base_url_at_the_language_root() -> None:
    """Each localized build carries the full Pagefind contract and its own base URL."""
    env = _language_build_environment("hu", check_sequences=True)
    assert env["CADRUMO_DOCS_BASE_URL"] == f"{CANONICAL_DOCS_BASE_URL}/hu"
    assert env["CADRUMO_DOCS_PAGEFIND_MODE"] == "full"
    assert env["CADRUMO_DOCS_JOBS"] == "1"


def test_every_deploy_root_pins_the_full_record_injected_search_contract() -> None:
    """English and every localized root deploy the record-injected index, not pages alone.

    The deployed contract is ``full`` on every root. Read through
    :func:`pagefind_index_mode` - the build's own resolver - rather than
    comparing the raw string, so this pins the contract the build will actually
    select rather than a value that merely looks right.

    An ambient ``pages`` in the publishing session must not narrow it either,
    which is why the deploy layer pins the key explicitly instead of relying on
    the build default; the hostile base below is the proof.
    """
    hostile_base = {"CADRUMO_DOCS_PAGEFIND_MODE": "pages"}

    assert pagefind_index_mode(_site_build_environment(base_environment={})) == "full"
    assert pagefind_index_mode(_site_build_environment(base_environment=hostile_base)) == "full"
    for language in _localized_languages():
        assert pagefind_index_mode(_language_build_environment(language, check_sequences=False)) == "full"


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

    assert len(environments) == len(_localized_languages())
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
            _docs_static_site,
            "_language_build_environment",
            lambda language, *, check_sequences: {SEQUENCE_CHECK_SKIP_ENV: "1"},
        ),
        pytest.raises(SystemExit) as refusal,
    ):
        _language_build_environments()

    assert "exactly one site root" in str(refusal.value)


def test_validate_language_roots_accepts_a_complete_matrix(tmp_path: Path) -> None:
    """Validation passes when every localized root carries the complete required-artifact set."""
    for language in _localized_languages():
        _materialise_language_root(tmp_path, language)
    _validate_language_roots(tmp_path)


def test_validate_language_roots_refuses_a_missing_index(tmp_path: Path) -> None:
    """A localized root without its rendered index page fails validation."""
    for language in _localized_languages():
        _materialise_language_root(tmp_path, language)
    missing = _localized_languages()[0]
    (tmp_path / missing / "index.html").unlink()
    with pytest.raises(SystemExit, match="required artifacts are missing"):
        _validate_language_roots(tmp_path)


@pytest.mark.parametrize("missing_artifact", sorted(_REQUIRED_ARTIFACTS))
def test_validate_language_roots_refuses_each_missing_required_artifact(tmp_path: Path, missing_artifact: str) -> None:
    """A localized root missing ANY required artifact fails validation, not only its index page.

    Reproduces the audit finding: before the fix, a localized root could pass
    with no 404 page, no sitemap, and no Pagefind JS/CSS bundle at all -- only
    ``index.html`` and a substantive Pagefind index chunk were mandatory.
    """
    for language in _localized_languages():
        _materialise_language_root(tmp_path, language)
    target_language = _localized_languages()[0]
    (tmp_path / target_language / missing_artifact).unlink()
    with pytest.raises(SystemExit, match="required artifacts are missing"):
        _validate_language_roots(tmp_path)


def test_every_artifact_a_valid_root_carries_is_a_required_artifact(tmp_path: Path) -> None:
    """The required-artifact tuple itself is pinned, not only the rule that reads it.

    Every check above draws its cases FROM ``_REQUIRED_ARTIFACTS``: the
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
    named = {artifact for artifact in carried if not artifact.startswith(_GENERATED_INDEX_PREFIXES)}

    assert len(named) >= _MINIMUM_REQUIRED_ARTIFACTS, named
    assert set(_REQUIRED_ARTIFACTS) == named


def test_validate_language_roots_refuses_a_sitemap_rooted_at_the_wrong_url(tmp_path: Path) -> None:
    """A localized root's sitemap must be rooted at its OWN language sub-path, not English."""
    for language in _localized_languages():
        _materialise_language_root(tmp_path, language)
    target_language = _localized_languages()[0]
    (tmp_path / target_language / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{CANONICAL_DOCS_BASE_URL}/</loc></url>\n"
        "</urlset>\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="missing the canonical docs root"):
        _validate_language_roots(tmp_path)


def test_validate_language_roots_refuses_an_empty_pagefind_index(tmp_path: Path) -> None:
    """A localized root whose Pagefind index has no substantive data fails validation."""
    for language in _localized_languages():
        _materialise_language_root(tmp_path, language)
    empty = _localized_languages()[0]
    for chunk in scan_directory(tmp_path / empty / "pagefind" / "index", pattern="*.pf_index", recursive=True):
        chunk.write_bytes(b"")
    with pytest.raises(SystemExit, match="no substantive generated index data"):
        _validate_language_roots(tmp_path)


def _direct_calls(function: object) -> list[str]:
    """Return the plain-name calls a function makes, in source order."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))  # type: ignore[arg-type]
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
    calls = _direct_calls(_docs_static_site._publish)
    assert calls.index("_build_site_roots") < calls.index("_validate_built_site") < calls.index("_sync_site"), (
        f"the publish no longer builds, then validates, then uploads: {calls}"
    )
    inlined = sorted(
        {"_build_language_roots", "_write_language_entry", "_validate_language_entry", "_validate_language_roots"}
        & set(calls)
    )
    assert not inlined, f"the publish re-inlines {inlined} instead of sharing the dry run's composition"

    assert inspect.signature(_dry_run).parameters["build"].default is _docs_static_site._build_site_roots


def test_dry_run_validates_a_complete_built_site_and_uploads_nothing(tmp_path: Path) -> None:
    """The dry run passes on a complete multi-root tree, touching no AWS surface.

    The verb exists because the whole build-and-validate prefix used to be
    reachable only through ``publish``: the roots could not be checked until
    bytes were already going to a live destination. Its subject is the built
    tree, so the build is supplied here as a real prepared multi-root artefact
    and the validation half runs production code against real files on disk.
    """
    for language in _localized_languages():
        _materialise_language_root(tmp_path, language)
    _materialise_apex_root(tmp_path)

    assert _dry_run(tmp_path, build=lambda _: tmp_path) == 0


def test_dry_run_refuses_a_root_that_would_publish_incomplete(tmp_path: Path) -> None:
    """The dry run's verdict is the publish's verdict: an incomplete root refuses.

    A dry run that passed where the publish would refuse would be worse than
    no dry run at all, so the refusal is asserted on the same defect the
    publish path refuses on.
    """
    for language in _localized_languages():
        _materialise_language_root(tmp_path, language)
    _materialise_apex_root(tmp_path)
    (tmp_path / _localized_languages()[0] / "404.html").unlink()

    with pytest.raises(SystemExit, match="required artifacts are missing"):
        _dry_run(tmp_path, build=lambda _: tmp_path)


def test_dry_run_refuses_an_apex_missing_the_bundle_the_publish_checks_after_upload(tmp_path: Path) -> None:
    """The apex is validated as a root BEFORE the upload, not only after it.

    ``_verify_published_search_index`` fetches the apex's served Pagefind entry
    and compares it against the built file at the apex root, raising when that
    built file is absent -- but it runs after the sync and after the cache
    invalidation. An apex that cannot satisfy the publish would therefore have
    written to the live destination first and failed second. The same file is
    now required before a byte moves, and this deletes exactly it.
    """
    for language in _localized_languages():
        _materialise_language_root(tmp_path, language)
    _materialise_apex_root(tmp_path)
    (tmp_path / "pagefind" / "pagefind-entry.json").unlink()

    with pytest.raises(SystemExit, match="required artifacts are missing"):
        _dry_run(tmp_path, build=lambda _: tmp_path)


def test_dry_run_refuses_an_apex_entry_that_strands_a_root(tmp_path: Path) -> None:
    """The apex half of the publish's validation runs in the dry run too."""
    for language in _localized_languages():
        _materialise_language_root(tmp_path, language)
    _materialise_apex_root(tmp_path)
    stranded = _localized_languages()[-1]
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
