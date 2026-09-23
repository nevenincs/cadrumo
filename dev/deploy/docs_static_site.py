"""Build, publish and roll back the Cadrumo documentation site on Cloudflare.

The site is served by one Worker from a private R2 bucket. Every publish uploads
a complete, immutable release under ``releases/<release id>/`` and then deploys
the Worker with that id, which is the moment the live site changes; a rollback
redeploys the Worker with an earlier id and uploads nothing. Both public
mounts, ``cadrumo.neve.md/docs/`` and ``neve.md/cadrumo/docs/``, are served
from the same bytes and are verified live after every deploy.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

from defusedxml import ElementTree

from cadrumo.core.directory_scan import scan_directory
from dev._paths import REPO_ROOT, UTF_8
from dev.deploy.cloudflare_api import (
    CloudflareAccount,
    WorkerRoute,
    deploy_worker,
    disable_redirect_rules,
    ensure_proxied,
    ensure_routes,
    zone_id,
)
from dev.deploy.r2_objects import R2Bucket, list_keys, upload_tree
from dev.docs import i18n as _docs_i18n
from dev.docs.sequence_build_gate import SEQUENCE_CHECK_SKIP_ENV
from dev.packaging.command_execution import CommandResult, run_command

CANONICAL_DOCS_BASE_URL = "https://cadrumo.neve.md/docs"
CANONICAL_SITE_DOMAIN = "cadrumo.neve.md"
#: The mirror mount serves the same release below the neve.md site.
MIRROR_DOCS_BASE_URL = "https://neve.md/cadrumo/docs"
MIRROR_SITE_DOMAIN = "neve.md"
DOCS_ZONE = "neve.md"
WORKER_SCRIPT = "cadrumo-docs"
WORKER_MODULE = REPO_ROOT / "worker" / "docs-site.mjs"
WORKER_COMPATIBILITY_DATE = "2026-09-01"
#: Every Worker response carries the release id it served under this header.
RELEASE_HEADER = "x-cadrumo-docs-release"
RELEASE_PREFIX = "releases/"
DELIVERY_ROUTES: Final[tuple[WorkerRoute, ...]] = (
    WorkerRoute(pattern=f"{CANONICAL_SITE_DOMAIN}/docs*", script=WORKER_SCRIPT),
    WorkerRoute(pattern=f"{MIRROR_SITE_DOMAIN}/cadrumo/docs*", script=WORKER_SCRIPT),
)
_CACHE_CONTROL = "public, max-age=300, must-revalidate"
_UTF_8: Final[str] = UTF_8
_REQUIRED_ARTIFACTS = (
    "index.html",
    "404.html",
    "sitemap.xml",
    "pagefind/pagefind-entry.json",
    "pagefind/pagefind.js",
    "pagefind/pagefind-ui.js",
    "pagefind/pagefind-ui.css",
)
_DOCTREE_EXCLUDES = (".doctrees/*", "*/.doctrees/*")
# Automation markers every hosted and self-hosted runner sets.
_CI_MARKERS = ("CI", "GITHUB_ACTIONS")
#: Cloudflare delivery credentials, read from the process environment by the
#: publisher, never by the product settings model. They are scoped to
#: Cadrumo's documentation bucket and Worker only.
DELIVERY_CREDENTIAL_ENV: Final[tuple[str, ...]] = (
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "CADRUMO_DOCS_R2_BUCKET",
    "CADRUMO_DOCS_R2_ACCESS_KEY_ID",
    "CADRUMO_DOCS_R2_SECRET_ACCESS_KEY",
)
_RELEASE_LABEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_RELEASE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}-[0-9]{8}T[0-9]{6}Z")
_ENDPOINT_TIMEOUT_SECONDS = 20
_RELEASE_WAIT_SECONDS = 180
_RELEASE_POLL_SECONDS = 5
_MISSING_DOCS_PATH = "__cadrumo-delivery-missing__.html"

#: The runtime download payload the docs download page enhances with
#: (``initDownloadCards`` in ``docs/_static/cadrumo-docs.js``). It is pulled —
#: version agnostically — from the latest release into ``docs/_static`` before
#: the site build so the served ``_static/download-latest.json`` reflects the
#: current release once a release attaches it. Absent it (no release has
#: attached one yet), the offline Tier-1 channel table is the floor and the
#: site build proceeds unchanged.
_DOWNLOAD_LATEST_URL = "https://github.com/nevenincs/cadrumo/releases/latest/download/download-latest.json"
_DOWNLOAD_LATEST_SCHEMA = "cadrumo.download-latest.v1"
_DOWNLOAD_LATEST_STATIC_PATH = ("docs", "_static", "download-latest.json")
_DOWNLOAD_LATEST_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class DeliveryCredentials:
    """The Cloudflare account, API token and R2 key a publish runs with."""

    account: CloudflareAccount
    bucket: R2Bucket


def _repo_root() -> Path:
    """Return the repository root."""
    return REPO_ROOT


def _command_label(command: Sequence[str]) -> str:
    """Return a readable command without invoking a shell."""
    return subprocess.list2cmdline(list(command))


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    stream_output: bool = False,
) -> CommandResult:
    """Run one local command and stop on its real exit status."""
    print(f"+ {_command_label(command)}", flush=True)
    # Callers build fixed command vectors; externally supplied values are validated.
    completed = run_command(
        list(command),
        cwd=cwd,
        environment=env,
    )
    if stream_output:
        if completed.stdout:
            print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n", flush=True)
        if completed.stderr:
            print(completed.stderr, end="" if completed.stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)
    else:
        if completed.stdout:
            print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n", flush=True)
        if completed.stderr:
            print(completed.stderr, end="" if completed.stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return completed


def site_build_environment(*, base_environment: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return the deployment-specific strict docs build environment.

    The Pagefind contract is pinned to ``full`` on every deploy root, English
    and localized alike: the deployed index carries the injected concept,
    casilla, and CLI records, not the rendered pages alone. It is pinned
    explicitly rather than left to the build default so an ambient
    ``CADRUMO_DOCS_PAGEFIND_MODE`` in the publishing session cannot narrow the
    shipped search contract — ``base`` is the real process environment in
    production, and these keys are layered over it.

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
        "CADRUMO_DOCS_JOBS": "1",
        "CADRUMO_DOCS_PAGEFIND_MODE": "full",
    }


def _invalidate_download_latest(destination: Path, reason: str) -> None:
    """Remove a stale ``download-latest.json`` (if any) and report why.

    A failed refresh must never leave a PRIOR release's payload standing as
    if it were current: an absent file is the documented safe floor (the
    offline Tier-1 channel table), while a stale-but-present one silently
    republishes an old release's download links as the current release. The
    removal itself must never raise -- an already-broken destination (e.g. a
    write failure because a path component is not a directory) has no stale
    file at that exact path to remove, and this function degrades silently
    like every other branch of the refresh.
    """
    with contextlib.suppress(OSError):
        destination.unlink(missing_ok=True)
    print(f"{reason}; serving the offline channel table.", flush=True)


def _refresh_download_latest(repo_root: Path, *, source_url: str = _DOWNLOAD_LATEST_URL) -> None:
    """Pull the latest release's ``download-latest.json`` into ``docs/_static``.

    Fetches the version-agnostic latest-release asset, validates it is the
    expected schema, and writes it to ``docs/_static/download-latest.json`` so
    the built site serves a current payload. Any failure — no release yet,
    network error, an unexpected body (e.g. a 404 page), a schema mismatch, or
    a local write failure — degrades silently (never raises) AND invalidates
    any payload retained from an earlier successful run, so the offline
    Tier-1 channel table is the floor
    rather than a stale prior release's links being served as current.

    ``source_url`` defaults to the fixed GitHub release asset URL; tests point it
    at a local HTTP server to exercise the real ``urlopen`` path against a real
    socket instead of faking the response.
    """
    destination = repo_root.joinpath(*_DOWNLOAD_LATEST_STATIC_PATH)
    endpoint = urlsplit(source_url)
    if endpoint.scheme not in {"http", "https"} or endpoint.hostname is None:
        _invalidate_download_latest(destination, f"download-latest.json unavailable (invalid URL: {source_url})")
        return
    try:
        port = endpoint.port
    except ValueError as exc:
        _invalidate_download_latest(destination, f"download-latest.json unavailable ({exc})")
        return
    path = endpoint.path or "/"
    if endpoint.query:
        path = f"{path}?{endpoint.query}"
    connection_type = HTTPSConnection if endpoint.scheme == "https" else HTTPConnection
    connection = connection_type(endpoint.hostname, port, timeout=_DOWNLOAD_LATEST_TIMEOUT_SECONDS)
    try:
        connection.request("GET", path, headers={"User-Agent": "cadrumo-docs-delivery"})
        response = connection.getresponse()
        body = response.read()
        if not 200 <= response.status < 300:
            raise OSError(f"HTTP {response.status}")
    except (HTTPException, TimeoutError, OSError) as exc:
        _invalidate_download_latest(destination, f"download-latest.json unavailable ({exc})")
        return
    finally:
        connection.close()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        _invalidate_download_latest(destination, "download-latest.json response was not JSON")
        return
    if not isinstance(payload, dict) or payload.get("schema_name") != _DOWNLOAD_LATEST_SCHEMA:
        _invalidate_download_latest(destination, "download-latest.json was not the expected payload")
        return
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
    except OSError as exc:
        _invalidate_download_latest(destination, f"download-latest.json could not be written ({exc})")
        return
    print(f"Refreshed {destination.relative_to(repo_root)} from the latest release.", flush=True)


def _build_site(repo_root: Path) -> Path:
    """Build the complete strict site at the canonical Cadrumo URL."""
    try:
        _run(
            [sys.executable, "-m", "dev.docs.build", "--strict", "docs/conf.py"],
            cwd=repo_root,
            env=site_build_environment(),
            stream_output=True,
        )
    except SystemExit as exc:
        raise SystemExit(
            f"Strict docs build failed; refusing to publish site or Pagefind output ({exc.code}).",
        ) from exc
    return repo_root / "docs" / "_build" / "html"


def _require_artifacts_present(html_root: Path, *, root_label: str) -> None:
    """Require every artifact in :data:`_REQUIRED_ARTIFACTS` at ``html_root``.

    Shared by the English root and every localized root: the same page, error
    page, sitemap, and Pagefind bundle are mandatory on every deployed root,
    not only the English one.
    """
    missing = [artifact for artifact in _REQUIRED_ARTIFACTS if not (html_root / artifact).is_file()]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(f"{root_label} is not deployable; required artifacts are missing: {joined}")


def _require_valid_sitemap(html_root: Path, *, expected_base_url: str, root_label: str) -> None:
    """Require a valid, canonically-rooted ``sitemap.xml`` at ``html_root``.

    ``expected_base_url`` is the root's OWN canonical URL (the English site's
    ``CANONICAL_DOCS_BASE_URL``, or a localized root's ``/<language>``
    sub-root via :func:`_language_site_url`) -- shared logic parameterized by
    the caller's expected root, since a localized root's sitemap is correctly
    rooted at its own language sub-path, not the English canonical root.
    """
    try:
        sitemap = ElementTree.parse(html_root / "sitemap.xml")
    except OSError as exc:
        raise SystemExit(
            f"{root_label} did not produce a sitemap at {html_root / 'sitemap.xml'}; "
            "set CADRUMO_DOCS_BASE_URL so the build writes one.",
        ) from exc
    except ElementTree.ParseError as exc:
        raise SystemExit(f"{root_label} sitemap is not valid XML.") from exc
    locations = [(element.text or "").strip() for element in sitemap.iter() if element.tag.endswith("loc")]
    if not locations:
        raise SystemExit(f"{root_label} sitemap has no URLs.")
    canonical_root = f"{expected_base_url}/"
    if canonical_root not in locations:
        raise SystemExit(f"{root_label} sitemap is missing the canonical docs root: {canonical_root}")
    unexpected = [location for location in locations if not location.startswith(f"{expected_base_url}/")]
    if unexpected:
        raise SystemExit(f"{root_label} sitemap contains a non-canonical URL: " + unexpected[0])


def _validate_site_artifacts(html_root: Path) -> None:
    """Require the rendered site and its Pagefind search bundle."""
    _require_artifacts_present(html_root, root_label="Docs build")
    _require_valid_sitemap(html_root, expected_base_url=CANONICAL_DOCS_BASE_URL, root_label="Docs build")
    _require_search_index(html_root, root_label="Docs build")


def _require_search_index(site_root: Path, *, root_label: str) -> None:
    """Refuse a site root whose Pagefind index is empty OR carries no records.

    Two distinct failures, both fatal, checked in order. An index with no
    substantive chunks means the pass produced nothing. An index with chunks but
    no injected records is the shape that shipped for weeks: the deploy
    environment selected the pages-only contract, the build wrote 75 rendered
    pages and not one concept, casilla, or CLI record, and every check in front
    of it stayed green because a pages-only index is full of non-empty chunks.
    Non-emptiness cannot separate the two, so it is kept AND supplemented.

    The record read is :func:`~dev.docs.pagefind_index.injected_record_kinds_in_index`
    -- the same artefact scan the CI parity gate performs, in one place so the
    publish preflight and the gate cannot drift apart.
    """
    from dev.docs.pagefind_index import DECIDED_INJECTED_RECORD_KINDS, injected_record_kinds_in_index

    index_chunks = [
        chunk
        for chunk in scan_directory(site_root / "pagefind" / "index", pattern="*.pf_index", recursive=True)
        if chunk.stat().st_size > 0
    ]
    if not index_chunks:
        raise SystemExit(f"{root_label} Pagefind index has no substantive generated index data.")

    present = injected_record_kinds_in_index(site_root)
    missing = sorted(DECIDED_INJECTED_RECORD_KINDS - present)
    if missing:
        raise SystemExit(
            f"{root_label} Pagefind index carries no records of kind(s) {', '.join(missing)} "
            f"(found: {', '.join(sorted(present)) or 'none'}). The index holds rendered pages only, "
            "so a reader could not search that surface at all. This is a pages-only index: confirm the "
            "build ran with the record-injecting contract (CADRUMO_DOCS_PAGEFIND_MODE=full) for this "
            f"root, then rebuild before publishing. Index read at {site_root / 'pagefind'}.",
        )


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
    strict user-scope build of the operator surface.
    """
    command = [sys.executable, "-m", "dev.docs.build", "--strict"]
    if language == _docs_i18n.DEFAULT_SOURCE_LANGUAGE:
        command += ["--out-dir", str(out_dir)]
        return command
    command += ["--scope", "user", "--language", language, "--out-dir", str(out_dir)]
    return command


def language_build_environment(language: str, *, check_sequences: bool) -> dict[str, str]:
    """Return the deploy build environment for one localized site root.

    The shared deployment environment (serial workers, full record-injected
    Pagefind contract) with the canonical base URL pointed at the language's own
    root so the per-language sitemap and canonical/OpenGraph URLs are correct.
    Each localized root therefore carries the injected records too: a reader on
    ``/es/`` searches the same record kinds as a reader on the English root.

    ``check_sequences`` selects whether this root runs the cli-sequence goldens
    gate. The check's verdict cannot vary by root -- its subprocess scrubs every
    ``CADRUMO_*`` key and pins English output -- so the four roots produce four
    identical answers for four times the cost. One root runs it and the rest set
    the documented opt-out; which root is decided by
    :func:`_language_build_environments`, never here.
    """
    environment = {**site_build_environment(), "CADRUMO_DOCS_BASE_URL": _language_site_url(language)}
    if not check_sequences:
        environment[SEQUENCE_CHECK_SKIP_ENV] = "1"
    return environment


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


def _build_language_roots(repo_root: Path, html_root: Path) -> None:
    """Build every site root into its own subdirectory.

    ``/en/``, ``/es/``, ``/ca/`` and ``/hu/`` are peers, each carrying its own
    Pagefind index. English holds no privileged position: the readers here file
    Spanish tax, so it sits at ``/en/`` like the rest and ``/`` resolves to the
    reader's own language instead (:func:`_write_language_entry`).
    """
    for language, environment in _language_build_environments():
        out_dir = html_root / language
        try:
            _run(
                language_build_command(language, out_dir),
                cwd=repo_root,
                env=environment,
                stream_output=True,
            )
        except SystemExit as exc:
            raise SystemExit(
                f"Localized docs build for {language!r} failed; refusing to publish ({exc.code}).",
            ) from exc


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
        encoding=_UTF_8,
        newline="\n",
    )
    print(f"Wrote language entry: {entry}", flush=True)
    return entry


def _validate_language_entry(html_root: Path) -> None:
    """Require the apex entry to exist and to reach every published root.

    This is the REACHABILITY half of what the apex owes, and only that half: it
    exists and no root is unreachable from it. A language built, uploaded and
    then absent from the entry is invisible to every reader who does not
    already know its URL, and nothing else in the pipeline would notice.

    The apex's own artifact set -- its sitemap, 404 page and Pagefind bundle,
    which it still carries as the English full-scope site -- is required by
    :func:`_validate_site_artifacts` inside the shared composition, not here.
    Every language root carries its own copies too, so neither check is the
    other's substitute.
    """
    entry = html_root / "index.html"
    if not entry.is_file():
        raise SystemExit(f"Language entry missing at {entry}; refusing to publish.")
    body = entry.read_text(encoding=_UTF_8)
    unreachable = [language for language in localized_languages() if f'"{language}"' not in body]
    if unreachable:
        raise SystemExit(
            f"Language entry does not route to {', '.join(unreachable)}; refusing to publish "
            "a root that cannot reach every built language.",
        )
    if _docs_i18n.DEFAULT_SITE_LANGUAGE not in body:
        raise SystemExit(
            f"Language entry declares no {_docs_i18n.DEFAULT_SITE_LANGUAGE!r} fallback; a reader with no "
            "stated preference would reach nothing.",
        )


def _validate_language_roots(html_root: Path) -> None:
    """Require every localized site root to carry the complete required-artifact set.

    The same artifacts mandatory for the English root -- the rendered page,
    the 404 error page, a canonically-rooted sitemap, and the full Pagefind
    bundle -- are mandatory for every localized root too, not only its index
    page and a non-empty Pagefind index.
    """
    for language in localized_languages():
        root = html_root / language
        label = f"Localized site root {language!r}"
        _require_artifacts_present(root, root_label=label)
        _require_valid_sitemap(root, expected_base_url=_language_site_url(language), root_label=label)
        _require_search_index(root, root_label=label)


def _delivery_credentials(environment: Mapping[str, str]) -> DeliveryCredentials:
    """Read the delivery credentials, naming every missing variable at once."""
    values = {name: environment.get(name, "").strip() for name in DELIVERY_CREDENTIAL_ENV}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise SystemExit(
            f"Documentation delivery credentials are missing: {', '.join(missing)}. "
            "Locally they come from env/.env (run with `uv run --env-file env/.env`); "
            "in CI from the protected `docs` environment.",
        )
    return DeliveryCredentials(
        account=CloudflareAccount(account_id=values["CLOUDFLARE_ACCOUNT_ID"], api_token=values["CLOUDFLARE_API_TOKEN"]),
        bucket=R2Bucket(
            account_id=values["CLOUDFLARE_ACCOUNT_ID"],
            name=values["CADRUMO_DOCS_R2_BUCKET"],
            access_key_id=values["CADRUMO_DOCS_R2_ACCESS_KEY_ID"],
            secret_access_key=values["CADRUMO_DOCS_R2_SECRET_ACCESS_KEY"],
        ),
    )


def release_id(label: str, *, now: datetime) -> str:
    """Return the immutable release id for one publish of ``label``.

    The timestamp makes every publish its own prefix, so re-publishing the
    same version never overwrites the bytes an earlier deploy served.
    """
    if _RELEASE_LABEL_RE.fullmatch(label) is None:
        raise SystemExit(f"Release label {label!r} must match {_RELEASE_LABEL_RE.pattern}.")
    return f"{label}-{now.astimezone(UTC):%Y%m%dT%H%M%SZ}"


def _local_release_label(repo_root: Path) -> str:
    """Label a local publish by the commit it was built from."""
    head = _run(["git", "rev-parse", "--short=12", "HEAD"], cwd=repo_root)
    return f"local-{head.stdout.strip()}"


def worker_bindings(credentials: DeliveryCredentials, release: str) -> tuple[dict[str, str], ...]:
    """Return the Worker bindings for serving ``release`` from the delivery bucket."""
    return (
        {"type": "r2_bucket", "name": "SITE", "bucket_name": credentials.bucket.name},
        {"type": "plain_text", "name": "RELEASE_ID", "text": release},
        {"type": "plain_text", "name": "CANONICAL_HOST", "text": CANONICAL_SITE_DOMAIN},
        {"type": "plain_text", "name": "CANONICAL_MOUNT", "text": urlsplit(CANONICAL_DOCS_BASE_URL).path},
        {"type": "plain_text", "name": "MIRROR_HOST", "text": MIRROR_SITE_DOMAIN},
        {"type": "plain_text", "name": "MIRROR_MOUNT", "text": urlsplit(MIRROR_DOCS_BASE_URL).path},
    )


def _upload_release(credentials: DeliveryCredentials, html_root: Path, release: str) -> None:
    """Upload the built site as one release prefix and prove every object landed."""
    prefix = f"{RELEASE_PREFIX}{release}/"
    if list_keys(credentials.bucket, prefix):
        raise SystemExit(f"Release prefix {prefix} already holds objects; a release is never overwritten.")

    def report(done: int, total: int) -> None:
        if done == total or done % 500 == 0:
            print(f"Uploaded {done}/{total} objects to {prefix}", flush=True)

    written = upload_tree(
        credentials.bucket,
        html_root,
        prefix=prefix,
        cache_control=_CACHE_CONTROL,
        excludes=_DOCTREE_EXCLUDES,
        report=report,
    )
    landed = list_keys(credentials.bucket, prefix)
    if landed != written:
        raise SystemExit(
            f"Release {release} is incomplete in R2: wrote {len(written)} objects, listed {len(landed)}; "
            "the Worker was not moved to it.",
        )


def _deploy_release(credentials: DeliveryCredentials, release: str) -> None:
    """Point the Worker at ``release``; this is the moment the live site changes."""
    deploy_worker(
        credentials.account,
        script=WORKER_SCRIPT,
        module=WORKER_MODULE,
        compatibility_date=WORKER_COMPATIBILITY_DATE,
        bindings=worker_bindings(credentials, release),
    )
    print(f"Deployed Worker {WORKER_SCRIPT} serving release {release}", flush=True)


def _endpoint_response(url: str) -> tuple[int, dict[str, str]]:
    """Return one public endpoint's unredirected HTTP status and headers."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname is None:
        raise SystemExit(f"Endpoint check requires a complete HTTPS URL: {url}")
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    connection = HTTPSConnection(parsed.hostname, port=parsed.port, timeout=_ENDPOINT_TIMEOUT_SECONDS)
    try:
        connection.request("GET", path, headers={"User-Agent": "cadrumo-docs-delivery-check"})
        response = connection.getresponse()
        headers = {name.lower(): value for name, value in response.getheaders()}
        response.read()
        return response.status, headers
    except (HTTPException, TimeoutError, OSError) as exc:
        raise SystemExit(f"Endpoint check could not reach {url}: {exc}") from exc
    finally:
        connection.close()


def public_delivery_checks() -> tuple[tuple[str, int], ...]:
    """Return the post-publish endpoint checks as ``(url, expected status)`` pairs.

    Named separately from the run so the deployment-parity gate can assert the
    published surface is covered on both mounts -- every localized root among
    them -- without reaching the network. Every URL here is answered by the
    Worker and must carry the release header.
    """
    checks: list[tuple[str, int]] = []
    for base_url in (CANONICAL_DOCS_BASE_URL, MIRROR_DOCS_BASE_URL):
        checks.append((f"{base_url}/", 200))
        checks.extend((f"{base_url}/{language}/", 200) for language in localized_languages())
        checks.append((f"{base_url}/{_MISSING_DOCS_PATH}", 404))
        checks.append((base_url, 301))
    return tuple(checks)


def _published_body(url: str) -> bytes:
    """Return one published artefact's body, under the same HTTPS guard as the status checks.

    Shared by both publishers: the status checks in :func:`_endpoint_response`
    deliberately discard the body, so a content assertion needs its own read.
    """
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname is None:
        raise SystemExit(f"Endpoint check requires a complete HTTPS URL: {url}")
    path = parsed.path or "/"
    connection = HTTPSConnection(parsed.hostname, port=parsed.port, timeout=_ENDPOINT_TIMEOUT_SECONDS)
    try:
        connection.request("GET", path, headers={"User-Agent": "cadrumo-docs-delivery-check"})
        response = connection.getresponse()
        body = response.read()
        if response.status != 200:
            raise SystemExit(f"Published artefact is not served at {url}: HTTP {response.status}.")
        return body
    except (HTTPException, TimeoutError, OSError) as exc:
        raise SystemExit(f"Endpoint check could not reach {url}: {exc}") from exc
    finally:
        connection.close()


def _indexed_entry_counts(payload: bytes, *, origin: str) -> dict[str, int]:
    """Return ``{language: page_count}`` from a ``pagefind-entry.json`` body."""
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{origin} is not valid JSON: {exc}") from exc
    languages = document.get("languages") if isinstance(document, dict) else None
    if not isinstance(languages, dict) or not languages:
        raise SystemExit(f"{origin} declares no index languages; it is not a Pagefind entry document.")
    return {str(name): int(split["page_count"]) for name, split in languages.items()}


def _assert_served_index_matches_build(*, built: Path, served: bytes, label: str) -> None:
    """Require the served index to carry exactly what the validated build carried.

    The preflight has already refused a record-free build, so the local entry is
    known to carry records. Requiring the SERVED counts to equal the BUILT counts
    therefore proves the published index carries them too -- without hardcoding a
    record total that would rot on the next corpus change.

    This is the check the status codes cannot make. A root serving a record-free
    index answers 200 on every URL the delivery checks probe, which is exactly
    how a pages-only index shipped and stayed shipped: everything answered, and
    nothing read what it answered with.
    """
    if not built.is_file():
        raise SystemExit(f"{label}: no built Pagefind entry at {built} to compare the published one against.")
    expected = _indexed_entry_counts(built.read_bytes(), origin=f"{label} built entry {built}")
    actual = _indexed_entry_counts(served, origin=f"{label} published entry")
    if actual != expected:
        raise SystemExit(
            f"{label}: the published search index does not match the build that was validated. "
            f"Built {expected}, published {actual}. A published count below the built one means the "
            "upload is incomplete or a stale index is being served; either way a reader is searching "
            "an index this publish never approved.",
        )


def _verify_published_search_index(
    html_root: Path,
    *,
    base_url: str = CANONICAL_DOCS_BASE_URL,
    fetch: Callable[[str], bytes] = _published_body,
) -> None:
    """Require every published root to serve the search index its build produced.

    Args:
        html_root: The built site root the publish uploaded from.
        base_url: DI seam. Production uses the canonical docs URL.
        fetch: DI seam for the HTTPS body read, so the comparison can be proven
            against real built artefacts without standing up a TLS endpoint.
    """
    roots: tuple[tuple[str, Path, str], ...] = (
        (f"{base_url}/", html_root, "docs root"),
        *tuple(
            (f"{base_url}/{language}/", html_root / language, f"localized root {language!r}")
            for language in localized_languages()
        ),
    )
    for root_url, built_root, label in roots:
        served = fetch(f"{root_url}pagefind/pagefind-entry.json")
        _assert_served_index_matches_build(
            built=built_root / "pagefind" / "pagefind-entry.json",
            served=served,
            label=label,
        )


def _await_release_served(release: str) -> None:
    """Wait until both mounts answer with ``release`` after a Worker deploy."""
    deadline = time.monotonic() + _RELEASE_WAIT_SECONDS
    pending = {f"{CANONICAL_DOCS_BASE_URL}/", f"{MIRROR_DOCS_BASE_URL}/"}
    while True:
        for url in sorted(pending):
            _status, headers = _endpoint_response(url)
            if headers.get(RELEASE_HEADER) == release:
                pending.discard(url)
        if not pending:
            return
        if time.monotonic() > deadline:
            raise SystemExit(
                f"Release {release} was deployed but {', '.join(sorted(pending))} did not serve it within "
                f"{_RELEASE_WAIT_SECONDS}s. Check the Worker routes, the DNS proxy on {CANONICAL_SITE_DOMAIN} "
                "and any redirect rule ahead of the Worker.",
            )
        time.sleep(_RELEASE_POLL_SECONDS)


def _delivery_mismatch(url: str, expected_status: int, release: str) -> str | None:
    """Return why ``url`` does not yet answer as declared from ``release``, or ``None``."""
    actual_status, headers = _endpoint_response(url)
    if actual_status != expected_status:
        return f"expected HTTP {expected_status}, received HTTP {actual_status}"
    if headers.get(RELEASE_HEADER) != release:
        return f"answered from release {headers.get(RELEASE_HEADER)!r}, not {release!r}"
    if expected_status == 301 and headers.get("location") != f"{urlsplit(url).path}/":
        return f"redirected to {headers.get('location')!r}, not to its directory"
    return None


def _verify_public_delivery(release: str) -> None:
    """Require every checked URL on both mounts to answer as declared, from ``release``.

    A deploy reaches Cloudflare's edge progressively, so one request can meet an
    edge that has not converged yet. Each check is therefore retried until it
    holds or the wait expires; a check still failing at the deadline is a
    delivery failure, never a pass.
    """
    deadline = time.monotonic() + _RELEASE_WAIT_SECONDS
    for url, expected_status in public_delivery_checks():
        while (mismatch := _delivery_mismatch(url, expected_status, release)) is not None:
            if time.monotonic() > deadline:
                raise SystemExit(f"Endpoint check failed for {url}: {mismatch}.")
            time.sleep(_RELEASE_POLL_SECONDS)
    landing_status, _ = _endpoint_response(f"https://{CANONICAL_SITE_DOMAIN}/")
    if landing_status != 200:
        raise SystemExit(f"The {CANONICAL_SITE_DOMAIN} landing page answered HTTP {landing_status} after the deploy.")


def _require_authorized_publish_environment(*, environment: Mapping[str, str] | None = None) -> None:
    """Permit an automated publish only from the provisioned delivery environment.

    The documentation site is published as a release consequence, so an
    automated publish is a supported authority. What must not happen is a
    surprise publish from some other automated run on a shared self-hosted
    fleet. The delivery credentials are stored only in the protected ``docs``
    environment, so an automated run must carry every one of them to proceed:
    their presence is what identifies the sanctioned delivery job. A local
    human session carries no automation marker and is unaffected.

    Args:
        environment: DI seam for tests. When ``None`` (production), the
            check reads the real process environment; a test passes an
            explicit mapping without mutating real process state.
    """
    env = environment if environment is not None else os.environ
    markers = tuple(name for name in _CI_MARKERS if name in env)
    if not markers:
        return
    missing = [name for name in DELIVERY_CREDENTIAL_ENV if not env.get(name, "").strip()]
    if not missing:
        return
    raise SystemExit(
        "Refusing Cadrumo documentation publish from an unprovisioned automated environment "
        f"({', '.join(markers)}): {', '.join(missing)} unset or empty. The delivery workflow "
        "supplies them from the protected `docs` environment. A local human publish sets no "
        "automation marker and is unaffected.",
    )


def _require_local_session(verb: str, *, environment: Mapping[str, str]) -> None:
    """Refuse a zone-level change from any automated run."""
    markers = [name for name in _CI_MARKERS if name in environment]
    if markers:
        raise SystemExit(f"{verb} changes the neve.md zone and runs only from a local session ({', '.join(markers)}).")


def _wire_zone(credentials: DeliveryCredentials, zone: str) -> None:
    """Proxy the canonical host and retire the mirror redirect; idempotent.

    The canonical host keeps its existing origin for every path outside
    ``/docs``; only the proxy flag on its record changes. The redirect rules
    that sent the mirror mount to the canonical host are disabled, not
    deleted, so re-enabling them reverts it.
    """
    ensure_proxied(credentials.account, zone, CANONICAL_SITE_DOMAIN)
    disable_redirect_rules(credentials.account, zone, source_prefix=f"{MIRROR_SITE_DOMAIN}/cadrumo/docs")


def _provision(*, environment: Mapping[str, str] | None = None) -> int:
    """Route both docs mounts to the Worker: one-time zone wiring, local only.

    Run it once a release is live on the Worker routes (``publish --cutover``
    does exactly that): retiring the mirror redirect earlier would leave the
    mirror mount with nothing behind it.
    """
    env = environment if environment is not None else os.environ
    _require_local_session("provision", environment=env)
    credentials = _delivery_credentials(env)
    _wire_zone(credentials, zone_id(credentials.account, DOCS_ZONE))
    print("Zone wiring is in place for both documentation mounts.", flush=True)
    return 0


def _build_site_roots(repo_root: Path) -> Path:
    """Build the apex site, every language root, and the apex language entry.

    The write half of a publish's pre-upload work, factored out so the dry run
    below and the publish share one composition. A second composition would be
    free to drift, and the drift would only ever surface on the live site.

    Returns:
        The built HTML root, carrying every published root.
    """
    html_root = _build_site(repo_root)
    _build_language_roots(repo_root, html_root)
    _write_language_entry(html_root)
    return html_root


def _validate_built_site(html_root: Path) -> None:
    """Run every validation a publish runs against the built tree before uploading.

    The apex is validated here as a root in its own right, not only as the
    language entry. It carries the English full-scope site — the API tree lives
    nowhere else — and its own Pagefind bundle, which
    :func:`_verify_published_search_index` demands back from the served site
    AFTER the upload and the Worker deploy. Checking it only there means a
    publish that cannot succeed still writes to the live destination first, so
    the same artifact set is required before a byte moves.
    """
    _validate_site_artifacts(html_root)
    _validate_language_entry(html_root)
    _validate_language_roots(html_root)


def _dry_run(repo_root: Path, *, build: Callable[[Path], Path] = _build_site_roots) -> int:
    """Build every site root and validate it exactly as a publish would, uploading nothing.

    Without this verb the whole build-and-validate prefix was reachable only
    through ``publish``, so the one check that a language root carries its
    required artifacts, its own canonically-rooted sitemap and a record-bearing
    index could not run until the moment bytes were already being written to a
    live destination.

    Its subject is entirely the built tree and every check reads the filesystem,
    so it deliberately requires no delivery credentials or publish authorization.

    Args:
        repo_root: Repository root the build commands run from.
        build: DI seam for tests. Production builds the real roots; a test
            passes a real prepared multi-root tree so the validation half is
            proven against real on-disk artifacts without paying for five
            Sphinx builds.
    """
    html_root = build(repo_root)
    _validate_built_site(html_root)
    print(
        f"Verified the built docs site at {html_root}: apex entry plus the "
        f"{', '.join(localized_languages())} roots. Uploaded nothing.",
        flush=True,
    )
    return 0


def _publish(
    repo_root: Path,
    *,
    release_label: str | None = None,
    cutover: bool = False,
    environment: Mapping[str, str] | None = None,
) -> int:
    """Build, validate, upload, deploy and verify one documentation release.

    Args:
        repo_root: Repository root the build commands run from.
        release_label: What the release id is labelled with; CI passes the
            release tag, a local publish defaults to the commit.
        cutover: Also wire the zone (:func:`_wire_zone`) once this release is
            live on the Worker routes, so neither mount is left without an
            origin between the old delivery and the new one. Local only.
        environment: DI seam for tests, forwarded to
            :func:`_require_authorized_publish_environment`. ``None``
            (production) reads the real process environment.
    """
    env = environment if environment is not None else os.environ
    _require_authorized_publish_environment(environment=env)
    if cutover:
        _require_local_session("publish --cutover", environment=env)
    credentials = _delivery_credentials(env)
    zone = zone_id(credentials.account, DOCS_ZONE)
    release = release_id(release_label or _local_release_label(repo_root), now=datetime.now(UTC))
    _refresh_download_latest(repo_root)
    html_root = _build_site_roots(repo_root)
    _validate_built_site(html_root)
    _upload_release(credentials, html_root, release)
    _deploy_release(credentials, release)
    ensure_routes(credentials.account, zone, DELIVERY_ROUTES)
    if cutover:
        _wire_zone(credentials, zone)
    _await_release_served(release)
    _verify_public_delivery(release)
    for base_url in (CANONICAL_DOCS_BASE_URL, MIRROR_DOCS_BASE_URL):
        _verify_published_search_index(html_root, base_url=base_url)
    print(f"Published release {release} at {CANONICAL_DOCS_BASE_URL}/ and {MIRROR_DOCS_BASE_URL}/", flush=True)
    return 0


def _rollback(release: str, *, environment: Mapping[str, str] | None = None) -> int:
    """Serve an earlier, already uploaded release again. Uploads nothing."""
    env = environment if environment is not None else os.environ
    _require_authorized_publish_environment(environment=env)
    if _RELEASE_ID_RE.fullmatch(release) is None:
        raise SystemExit(f"{release!r} is not a release id.")
    credentials = _delivery_credentials(env)
    prefix = f"{RELEASE_PREFIX}{release}/"
    if f"{prefix}index.html" not in list_keys(credentials.bucket, prefix):
        raise SystemExit(f"Release {release} is not in the bucket; nothing to roll back to.")
    _deploy_release(credentials, release)
    _await_release_served(release)
    _verify_public_delivery(release)
    print(f"Rolled back to release {release}", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Publish, roll back or wire up the Cadrumo documentation site."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    provision = commands.add_parser("provision", help="Route both docs mounts to the Worker (one-time zone wiring).")
    provision.add_argument(
        "--confirm",
        choices=("provision-cadrumo-docs",),
        required=True,
        help="Required literal acknowledgement for the zone change.",
    )
    publish = commands.add_parser("publish", help="Build, upload and deploy one docs release.")
    publish.add_argument(
        "--confirm",
        choices=("publish-cadrumo-docs",),
        required=True,
        help="Required literal acknowledgement for the publishing.",
    )
    publish.add_argument("--release-label", help="Label for the release id; defaults to the local commit.")
    publish.add_argument(
        "--cutover",
        action="store_true",
        help="Also retire the mirror redirect once the release is live on the routes (one-time, local only).",
    )
    rollback = commands.add_parser("rollback", help="Serve an earlier uploaded release again.")
    rollback.add_argument(
        "--confirm",
        choices=("rollback-cadrumo-docs",),
        required=True,
        help="Required literal acknowledgement for the rollback.",
    )
    rollback.add_argument("--release", required=True, help="The release id to serve.")
    commands.add_parser("dry-run", help="Build and validate every site root without uploading.")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    if args.command == "dry-run":
        return _dry_run(repo_root)
    if args.command == "provision":
        return _provision()
    if args.command == "rollback":
        return _rollback(args.release)
    return _publish(repo_root, release_label=args.release_label, cutover=args.cutover)


if __name__ == "__main__":
    raise SystemExit(main())
