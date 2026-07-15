"""Provision and publish the Cadrumo documentation site from a local AWS session."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from http.client import HTTPException, HTTPSConnection
from pathlib import Path
from urllib.parse import urlsplit

from defusedxml import ElementTree

CANONICAL_DOCS_BASE_URL = "https://cadrumo.neve.md/docs"
CANONICAL_SITE_DOMAIN = "cadrumo.neve.md"
STACK_NAME = "cadrumo-docs"
STACK_REGION = "us-east-1"
_BUCKET_NAME_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?")
_DISTRIBUTION_ID_RE = re.compile(r"[A-Z0-9]+")
_CACHE_CONTROL = "public, max-age=300, must-revalidate"
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
_ENDPOINT_TIMEOUT_SECONDS = 20
_LEGACY_DOCS_URL = "https://neve.md/cadrumo/docs"
_MISSING_DOCS_PATH = "__cadrumo-delivery-missing__.html"


@dataclass(frozen=True)
class DeploymentTarget:
    """Stack-owned destination for the documentation deployment."""

    bucket: str
    distribution_id: str


def _repo_root() -> Path:
    """Return the repository root."""
    return Path(__file__).resolve().parents[2]


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


def _site_build_environment() -> dict[str, str]:
    """Return the deployment-specific strict docs build environment."""
    return {
        **os.environ,
        "CADRUMO_DOCS_BASE_URL": CANONICAL_DOCS_BASE_URL,
        "CADRUMO_DOCS_JOBS": "1",
        "CADRUMO_DOCS_PAGEFIND_MODE": "pages",
    }


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


def _validate_site_artifacts(html_root: Path) -> None:
    """Require the rendered site and its Pagefind search bundle."""
    missing = [artifact for artifact in _REQUIRED_ARTIFACTS if not (html_root / artifact).is_file()]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(f"Docs build is not deployable; required artifacts are missing: {joined}")
    try:
        sitemap = ElementTree.parse(html_root / "sitemap.xml")
    except OSError as exc:
        raise SystemExit(
            f"Docs build did not produce a sitemap at {html_root / 'sitemap.xml'}; "
            "set CADRUMO_DOCS_BASE_URL so the build writes one.",
        ) from exc
    except ElementTree.ParseError as exc:
        raise SystemExit("Docs build sitemap is not valid XML.") from exc
    locations = [(element.text or "").strip() for element in sitemap.iter() if element.tag.endswith("loc")]
    if not locations:
        raise SystemExit("Docs build sitemap has no URLs.")
    canonical_root = f"{CANONICAL_DOCS_BASE_URL}/"
    if canonical_root not in locations:
        raise SystemExit(f"Docs build sitemap is missing the canonical docs root: {canonical_root}")
    unexpected = [location for location in locations if not location.startswith(f"{CANONICAL_DOCS_BASE_URL}/")]
    if unexpected:
        raise SystemExit("Docs build sitemap contains a non-canonical URL: " + unexpected[0])
    pagefind_index = html_root / "pagefind" / "index"
    index_chunks = [chunk for chunk in pagefind_index.rglob("*.pf_index") if chunk.stat().st_size > 0]
    if not index_chunks:
        raise SystemExit("Docs build Pagefind index has no substantive generated index data.")


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


def _invalidate_site(aws: str, repo_root: Path, distribution_id: str) -> None:
    """Invalidate the published documentation paths and wait for completion."""
    created = _run(
        [
            *_aws_base_command(aws),
            "cloudfront",
            "create-invalidation",
            "--distribution-id",
            distribution_id,
            "--paths",
            "/docs/*",
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


def _verify_public_delivery(target: DeploymentTarget) -> None:
    """Require the canonical, legacy, missing, and private-origin responses."""
    checks = (
        (f"{CANONICAL_DOCS_BASE_URL}/", 200),
        (_LEGACY_DOCS_URL, 308),
        (f"{CANONICAL_DOCS_BASE_URL}/{_MISSING_DOCS_PATH}", 404),
        (f"https://{target.bucket}.s3.{STACK_REGION}.amazonaws.com/docs/index.html", 403),
    )
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


def _require_human_publish_environment() -> None:
    """Refuse publishing when a continuous-integration marker is present."""
    markers = tuple(name for name in ("CI", "GITHUB_ACTIONS") if name in os.environ)
    if markers:
        raise SystemExit("Refusing Cadrumo documentation publish from CI: " + ", ".join(markers))


def _provision(aws: str, repo_root: Path) -> int:
    """Provision the fixed Cadrumo documentation stack."""
    account_id = _authenticated_account_id(aws, repo_root)
    certificate_arn = _issued_certificate_arn(aws, repo_root)
    _provision_stack(aws, repo_root, account_id, certificate_arn)
    _print_stack_outputs(aws, repo_root)
    return 0


def _publish(aws: str, repo_root: Path) -> int:
    """Build, validate, upload, and invalidate the fixed Cadrumo documentation site."""
    _require_human_publish_environment()
    _authenticated_account_id(aws, repo_root)
    target = _stack_target(aws, repo_root)
    _verify_distribution_alias(aws, repo_root, target.distribution_id)
    html_root = _build_site(repo_root)
    _validate_site_artifacts(html_root)
    _sync_site(aws, repo_root, html_root, target.bucket)
    _invalidate_site(aws, repo_root, target.distribution_id)
    _verify_public_delivery(target)
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
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    aws = _required_executable("aws")
    if args.command == "provision":
        return _provision(aws, repo_root)
    return _publish(aws, repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
