"""Provision and publish the Cadrumo documentation site from a local AWS session."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from http.client import HTTPException, HTTPSConnection
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

from defusedxml import ElementTree

from cadrumo.core.directory_scan import scan_directory

from .._paths import REPO_ROOT, UTF_8
from ..docs.i18n import DEFAULT_SITE_LANGUAGE, DEFAULT_SOURCE_LANGUAGE, SITE_ROOT_LANGUAGES
from ..docs.sequence_build_gate import SEQUENCE_CHECK_SKIP_ENV

CANONICAL_DOCS_BASE_URL = "https://cadrumo.neve.md/docs"
CANONICAL_SITE_DOMAIN = "cadrumo.neve.md"
STACK_NAME = "cadrumo-docs"
STACK_REGION = "us-east-1"
_BUCKET_NAME_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?")
_DISTRIBUTION_ID_RE = re.compile(r"[A-Z0-9]+")
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
# The delivery role identifier, published to the job by the protected
# environment. Its presence is what distinguishes the sanctioned automated
# publish from any other automated run on a shared fleet.
_DEPLOY_ROLE_VARIABLE = "CADRUMO_DOCS_DEPLOY_ROLE"
_ENDPOINT_TIMEOUT_SECONDS = 20
_LEGACY_DOCS_URL = "https://neve.md/cadrumo/docs"
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
class DeploymentTarget:
    """Stack-owned destination for the documentation deployment."""

    bucket: str
    distribution_id: str


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
) -> subprocess.CompletedProcess[str]:
    """Run one local command and stop on its real exit status."""
    print(f"+ {_command_label(command)}", flush=True)
    # Callers build fixed Python/AWS command vectors; externally supplied IDs are validated.
    completed = subprocess.run(  # noqa: S603
        list(command),
        cwd=cwd,
        env=env,
        text=True,
        capture_output=not stream_output,
        check=False,
    )
    if not stream_output:
        if completed.stdout:
            print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n", flush=True)
        if completed.stderr:
            print(completed.stderr, end="" if completed.stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return completed


def _required_executable(name: str) -> str:
    """Return an executable on PATH or stop before deployment."""
    executable = shutil.which(name)
    if executable is None:
        raise SystemExit(f"Required executable not found on PATH: {name}")
    return executable


def _site_build_environment(*, base_environment: Mapping[str, str] | None = None) -> dict[str, str]:
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
    request = urllib.request.Request(  # noqa: S310 — fixed HTTPS GitHub release URL (or test-supplied local URL)
        source_url,
        headers={"User-Agent": "cadrumo-docs-delivery"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_DOWNLOAD_LATEST_TIMEOUT_SECONDS) as response:  # noqa: S310
            body = response.read()
    except (urllib.error.URLError, HTTPException, TimeoutError, OSError) as exc:
        _invalidate_download_latest(destination, f"download-latest.json unavailable ({exc})")
        return
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
            env=_site_build_environment(),
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
    from ..docs.pagefind_index import DECIDED_INJECTED_RECORD_KINDS, injected_record_kinds_in_index

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


def _localized_languages() -> tuple[str, ...]:
    """Return the per-language deploy roots, English included.

    Derived from the shared :data:`SITE_ROOT_LANGUAGES` so the deploy matrix
    never re-lists the language set. English is a root like any other: the
    readers here file Spanish tax, so no language holds the apex path and ``/``
    resolves to the reader's own instead (see :func:`_write_language_entry`).
    """
    return SITE_ROOT_LANGUAGES


def _language_site_url(language: str) -> str:
    """Return the canonical deploy URL for one localized site root."""
    return f"{CANONICAL_DOCS_BASE_URL}/{language}"


def _language_build_command(language: str, out_dir: Path) -> list[str]:
    """Return the build-driver command for one site root.

    Reuses the ``dev.docs.build`` driver's flags rather than duplicating build
    logic. English is built WITHOUT ``--language``: it is the msgid source, so
    it has no catalogue to select, and passing the flag would force the user
    scope and drop the API autodoc tree. It therefore keeps the full scope and
    carries ``api/`` inside its own root, while every translated root is a
    strict user-scope build of the operator surface.
    """
    command = [sys.executable, "-m", "dev.docs.build", "--strict"]
    if language == DEFAULT_SOURCE_LANGUAGE:
        command += ["--out-dir", str(out_dir)]
        return command
    command += ["--scope", "user", "--language", language, "--out-dir", str(out_dir)]
    return command


def _language_build_environment(language: str, *, check_sequences: bool) -> dict[str, str]:
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
    environment = {**_site_build_environment(), "CADRUMO_DOCS_BASE_URL": _language_site_url(language)}
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
        (language, _language_build_environment(language, check_sequences=index == 0))
        for index, language in enumerate(_localized_languages())
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
                _language_build_command(language, out_dir),
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
    languages = ", ".join(f'"{language}"' for language in _localized_languages())
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
        f'  var fallback = "{DEFAULT_SITE_LANGUAGE}";\n'
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
        + "".join(f'<li><a href="{language}/">{language}</a></li>\n' for language in _localized_languages())
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
    unreachable = [language for language in _localized_languages() if f'"{language}"' not in body]
    if unreachable:
        raise SystemExit(
            f"Language entry does not route to {', '.join(unreachable)}; refusing to publish "
            "a root that cannot reach every built language.",
        )
    if DEFAULT_SITE_LANGUAGE not in body:
        raise SystemExit(
            f"Language entry declares no {DEFAULT_SITE_LANGUAGE!r} fallback; a reader with no "
            "stated preference would reach nothing.",
        )


def _validate_language_roots(html_root: Path) -> None:
    """Require every localized site root to carry the complete required-artifact set.

    The same artifacts mandatory for the English root -- the rendered page,
    the 404 error page, a canonically-rooted sitemap, and the full Pagefind
    bundle -- are mandatory for every localized root too, not only its index
    page and a non-empty Pagefind index.
    """
    for language in _localized_languages():
        root = html_root / language
        label = f"Localized site root {language!r}"
        _require_artifacts_present(root, root_label=label)
        _require_valid_sitemap(root, expected_base_url=_language_site_url(language), root_label=label)
        _require_search_index(root, root_label=label)


def _aws_base_command(aws: str) -> list[str]:
    """Return the shared AWS CLI command prefix."""
    return [aws, "--no-cli-pager"]


def _authenticated_account_id(aws: str, repo_root: Path) -> str:
    """Return the current account ID from the authenticated local AWS session."""
    identity = _run(
        [*_aws_base_command(aws), "sts", "get-caller-identity", "--output", "json"],
        cwd=repo_root,
    )
    try:
        account_id = json.loads(identity.stdout)["Account"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SystemExit("AWS did not return an account ID.") from exc
    if not isinstance(account_id, str) or re.fullmatch(r"[0-9]{12}", account_id) is None:
        raise SystemExit("AWS returned an invalid account ID.")
    return account_id


def _issued_certificate_arn(aws: str, repo_root: Path) -> str:
    """Return the one issued us-east-1 ACM certificate for the Cadrumo host."""
    listed = _run(
        [
            *_aws_base_command(aws),
            "acm",
            "list-certificates",
            "--region",
            STACK_REGION,
            "--certificate-statuses",
            "ISSUED",
            "--output",
            "json",
        ],
        cwd=repo_root,
    )
    try:
        certificates = json.loads(listed.stdout)["CertificateSummaryList"]
        matches = [
            certificate["CertificateArn"]
            for certificate in certificates
            if certificate["DomainName"].rstrip(".").lower() == CANONICAL_SITE_DOMAIN
        ]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SystemExit("AWS did not return ACM certificate summaries.") from exc
    if len(matches) != 1:
        raise SystemExit(
            "Expected exactly one issued "
            f"{STACK_REGION} ACM certificate for {CANONICAL_SITE_DOMAIN}; found {len(matches)}.",
        )
    return matches[0]


def _provision_stack(aws: str, repo_root: Path, account_id: str, certificate_arn: str) -> None:
    """Create or update the fixed Cadrumo docs delivery stack."""
    bucket = f"cadrumo-docs-{account_id}"
    _run(
        [
            *_aws_base_command(aws),
            "cloudformation",
            "deploy",
            "--region",
            STACK_REGION,
            "--stack-name",
            STACK_NAME,
            "--template-file",
            "infra/docs-static-site.yaml",
            "--parameter-overrides",
            f"BucketName={bucket}",
            f"CertificateArn={certificate_arn}",
            f"SiteDomainName={CANONICAL_SITE_DOMAIN}",
            "PriceClass=PriceClass_100",
            "--no-fail-on-empty-changeset",
        ],
        cwd=repo_root,
    )


def _print_stack_outputs(aws: str, repo_root: Path) -> None:
    """Print the fixed stack's outputs after a successful provision."""
    _run(
        [
            *_aws_base_command(aws),
            "cloudformation",
            "describe-stacks",
            "--region",
            STACK_REGION,
            "--stack-name",
            STACK_NAME,
            "--query",
            "Stacks[0].Outputs",
            "--output",
            "json",
        ],
        cwd=repo_root,
    )


def _stack_target(aws: str, repo_root: Path) -> DeploymentTarget:
    """Read the deployment target from the approved CloudFormation stack."""
    described = _run(
        [
            *_aws_base_command(aws),
            "cloudformation",
            "describe-stacks",
            "--region",
            STACK_REGION,
            "--stack-name",
            STACK_NAME,
            "--output",
            "json",
        ],
        cwd=repo_root,
    )
    try:
        stack = json.loads(described.stdout)["Stacks"][0]
        outputs = {output["OutputKey"]: output["OutputValue"] for output in stack["Outputs"]}
        target = DeploymentTarget(
            bucket=outputs["DocsBucketName"],
            distribution_id=outputs["DocsDistributionId"],
        )
    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SystemExit("CloudFormation stack does not expose the required Cadrumo docs outputs.") from exc
    if _BUCKET_NAME_RE.fullmatch(target.bucket) is None:
        raise SystemExit("CloudFormation returned an invalid documentation bucket name.")
    if _DISTRIBUTION_ID_RE.fullmatch(target.distribution_id) is None:
        raise SystemExit("CloudFormation returned an invalid CloudFront distribution ID.")
    return target


def _verify_distribution_alias(aws: str, repo_root: Path, distribution_id: str) -> None:
    """Require the stack distribution to serve only the canonical Cadrumo host."""
    described = _run(
        [
            *_aws_base_command(aws),
            "cloudfront",
            "get-distribution",
            "--id",
            distribution_id,
            "--output",
            "json",
        ],
        cwd=repo_root,
    )
    try:
        aliases = json.loads(described.stdout)["Distribution"]["DistributionConfig"]["Aliases"]
        names = aliases.get("Items", [])
    except (AttributeError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SystemExit("CloudFront did not return distribution aliases.") from exc
    if names != [CANONICAL_SITE_DOMAIN]:
        raise SystemExit(f"CloudFront distribution aliases must be exactly [{CANONICAL_SITE_DOMAIN!r}].")


def _sync_site(aws: str, repo_root: Path, html_root: Path, bucket: str) -> None:
    """Synchronise only the generated documentation prefix."""
    destination = f"s3://{bucket}/docs/"
    command = [
        *_aws_base_command(aws),
        "s3",
        "sync",
        str(html_root),
        destination,
        "--delete",
        "--cache-control",
        _CACHE_CONTROL,
    ]
    for pattern in _DOCTREE_EXCLUDES:
        command.extend(["--exclude", pattern])
    _run(command, cwd=repo_root)


_DOCS_INVALIDATION_PATHS: tuple[str, ...] = ("/docs/*",)


def _invalidate_distribution_paths(
    aws: str,
    repo_root: Path,
    distribution_id: str,
    paths: Sequence[str],
) -> None:
    """Invalidate the given published paths on the distribution and wait for completion.

    The documentation publisher invalidates its own subtree through this
    single create-invalidation, id-extract, and wait-for-completion sequence.
    """
    created = _run(
        [
            *_aws_base_command(aws),
            "cloudfront",
            "create-invalidation",
            "--distribution-id",
            distribution_id,
            "--paths",
            *paths,
            "--output",
            "json",
        ],
        cwd=repo_root,
    )
    try:
        invalidation_id = json.loads(created.stdout)["Invalidation"]["Id"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SystemExit("CloudFront did not return an invalidation ID.") from exc
    _run(
        [
            *_aws_base_command(aws),
            "cloudfront",
            "wait",
            "invalidation-completed",
            "--distribution-id",
            distribution_id,
            "--id",
            invalidation_id,
        ],
        cwd=repo_root,
    )


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


def _public_delivery_checks(target: DeploymentTarget) -> tuple[tuple[str, int], ...]:
    """Return the post-publish endpoint checks as ``(url, expected status)`` pairs.

    Named separately from the run so the deployment-parity gate can assert the
    published surface is covered — every localized root among them — without
    reaching the network.
    """
    return (
        (f"{CANONICAL_DOCS_BASE_URL}/", 200),
        *tuple((f"{_language_site_url(language)}/", 200) for language in _localized_languages()),
        (_LEGACY_DOCS_URL, 308),
        (f"{CANONICAL_DOCS_BASE_URL}/{_MISSING_DOCS_PATH}", 404),
        (f"https://{target.bucket}.s3.{STACK_REGION}.amazonaws.com/docs/index.html", 403),
    )


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
            for language in _localized_languages()
        ),
    )
    for root_url, built_root, label in roots:
        served = fetch(f"{root_url}pagefind/pagefind-entry.json")
        _assert_served_index_matches_build(
            built=built_root / "pagefind" / "pagefind-entry.json",
            served=served,
            label=label,
        )


def _verify_public_delivery(target: DeploymentTarget) -> None:
    """Require the canonical, legacy, missing, and private-origin responses."""
    checks = _public_delivery_checks(target)
    legacy_headers: dict[str, str] | None = None
    for url, expected_status in checks:
        actual_status, headers = _endpoint_response(url)
        if actual_status != expected_status:
            raise SystemExit(
                f"Endpoint check failed for {url}: expected HTTP {expected_status}, received HTTP {actual_status}.",
            )
        if url == _LEGACY_DOCS_URL:
            legacy_headers = headers
    expected_location = f"{CANONICAL_DOCS_BASE_URL}/"
    actual_location = legacy_headers.get("location") if legacy_headers is not None else None
    if actual_location != expected_location:
        raise SystemExit(
            f"Legacy redirect check failed: expected Location {expected_location!r}, received {actual_location!r}.",
        )


def _require_authorized_publish_environment(*, environment: Mapping[str, str] | None = None) -> None:
    """Permit an automated publish only from the provisioned delivery environment.

    A blanket continuous-integration refusal used to stand here, and it is
    deliberately gone: the documentation site is published as a release
    consequence, so an automated publish is a supported authority rather than an
    accident. What that refusal protected against survives, because the property
    worth keeping was never "no automation" but "no surprise publish".

    The distinction is load-bearing on a shared self-hosted fleet. A co-resident
    automated run may inherit an ambient cloud session and would then never need
    the federated role at all, so the delivery workflow's own identity is the
    only thing that separates the sanctioned publish from an accidental one. An
    automated run must therefore name itself: the deploy role identifier is
    published to the job as an environment-scoped variable, so it is present
    only inside the protected delivery environment, and it exists at all only
    once the operator has provisioned the role.

    Two consequences follow, both intended. Before provisioning this refuses
    every automated run exactly as its predecessor did, so the permission opens
    when the role exists rather than when this change lands. And a local human
    session carries no automation marker, so the local publish authority is
    untouched in either state.

    The variable's environment scoping is an operator provisioning property, not
    something this process can verify from the inside; it is the same trust the
    workflow's own role assumption rests on.

    Args:
        environment: DI seam for tests. When ``None`` (production), the
            check reads the real process environment; a test passes an
            explicit mapping to exercise a marker/role combination without
            mutating real process state.
    """
    env = environment if environment is not None else os.environ
    markers = tuple(name for name in _CI_MARKERS if name in env)
    if not markers:
        return
    if env.get(_DEPLOY_ROLE_VARIABLE, "").strip():
        return
    raise SystemExit(
        "Refusing Cadrumo documentation publish from an unprovisioned automated environment "
        f"({', '.join(markers)}): {_DEPLOY_ROLE_VARIABLE} is unset or empty. The delivery "
        "workflow supplies it from the protected environment once the operator has created "
        "the deploy role. A local human publish sets no automation marker and is unaffected.",
    )


def _provision(aws: str, repo_root: Path) -> int:
    """Provision the fixed Cadrumo documentation stack."""
    account_id = _authenticated_account_id(aws, repo_root)
    certificate_arn = _issued_certificate_arn(aws, repo_root)
    _provision_stack(aws, repo_root, account_id, certificate_arn)
    _print_stack_outputs(aws, repo_root)
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
    AFTER the upload and the cache invalidation. Checking it only there means a
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
    so it deliberately requires no AWS session or publish authorization.

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
        f"{', '.join(_localized_languages())} roots. Uploaded nothing.",
        flush=True,
    )
    return 0


def _publish(aws: str, repo_root: Path, *, environment: Mapping[str, str] | None = None) -> int:
    """Build, validate, upload, and invalidate the fixed Cadrumo documentation site.

    Args:
        aws: Path to the AWS CLI executable.
        repo_root: Repository root the build and sync commands run from.
        environment: DI seam for tests, forwarded to
            :func:`_require_authorized_publish_environment`. ``None``
            (production) reads the real process environment.
    """
    _require_authorized_publish_environment(environment=environment)
    _authenticated_account_id(aws, repo_root)
    target = _stack_target(aws, repo_root)
    _verify_distribution_alias(aws, repo_root, target.distribution_id)
    _refresh_download_latest(repo_root)
    html_root = _build_site_roots(repo_root)
    _validate_built_site(html_root)
    _sync_site(aws, repo_root, html_root, target.bucket)
    _invalidate_distribution_paths(aws, repo_root, target.distribution_id, _DOCS_INVALIDATION_PATHS)
    _verify_public_delivery(target)
    _verify_published_search_index(html_root)
    print(f"Published {CANONICAL_DOCS_BASE_URL}/", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Provision or publish the fixed Cadrumo documentation site."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    provision = commands.add_parser("provision", help="Create or update the fixed docs stack.")
    provision.add_argument(
        "--confirm",
        choices=("provision-cadrumo-docs",),
        required=True,
        help="Required literal acknowledgement for the local provisioning.",
    )
    publish = commands.add_parser("publish", help="Build and publish the fixed docs site.")
    publish.add_argument(
        "--confirm",
        choices=("publish-cadrumo-docs",),
        required=True,
        help="Required literal acknowledgement for the local publishing.",
    )
    commands.add_parser("dry-run", help="Build and validate every site root without uploading.")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    if args.command == "dry-run":
        return _dry_run(repo_root)
    aws = _required_executable("aws")
    if args.command == "provision":
        return _provision(aws, repo_root)
    return _publish(aws, repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
