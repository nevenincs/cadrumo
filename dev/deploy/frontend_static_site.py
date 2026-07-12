"""Publish the Cadrumo landing page to the documentation stack from a local AWS session."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from dev.deploy.docs_static_site import (
    CANONICAL_DOCS_BASE_URL,
    CANONICAL_SITE_DOMAIN,
    STACK_REGION,
    DeploymentTarget,
    _authenticated_account_id,
    _aws_base_command,
    _endpoint_response,
    _repo_root,
    _require_human_publish_environment,
    _required_executable,
    _run,
    _stack_target,
    _verify_distribution_alias,
)

CANONICAL_SITE_URL = f"https://{CANONICAL_SITE_DOMAIN}"
_CACHE_CONTROL = "public, max-age=300, must-revalidate"
_REQUIRED_ARTIFACTS = (
    "index.html",
    "404.html",
    "favicon.png",
    "og-image.jpg",
    "robots.txt",
    "sitemap.xml",
)
# The landing page shares the documentation bucket; its sync must never touch
# the documentation prefix the docs publisher owns.
_PROTECTED_PREFIX_EXCLUDES = ("docs/*",)
_INVALIDATION_PATHS = (
    "/",
    "/index.html",
    "/404.html",
    "/favicon.png",
    "/og-image.jpg",
    "/robots.txt",
    "/sitemap.xml",
    "/assets/*",
)


def _build_site(repo_root: Path) -> Path:
    """Build the landing page and return its distributable root."""
    npm = _required_executable("npm")
    frontend_root = repo_root / "frontend"
    _run([npm, "run", "build"], cwd=frontend_root, stream_output=True)
    return frontend_root / "dist"


def _validate_site_artifacts(dist_root: Path) -> None:
    """Require the artifacts the landing page cannot serve without."""
    missing = [artifact for artifact in _REQUIRED_ARTIFACTS if not (dist_root / artifact).is_file()]
    if missing:
        raise SystemExit("Landing page build is missing required artifacts: " + ", ".join(missing))
    assets = dist_root / "assets"
    if not any(assets.glob("*.js")) or not any(assets.glob("*.css")):
        raise SystemExit("Landing page build is missing bundled assets under dist/assets/.")


def _sync_site(aws: str, repo_root: Path, dist_root: Path, bucket: str) -> None:
    """Synchronise the site root while leaving the documentation prefix intact."""
    destination = f"s3://{bucket}/"
    command = [
        *_aws_base_command(aws),
        "s3",
        "sync",
        str(dist_root),
        destination,
        "--delete",
        "--cache-control",
        _CACHE_CONTROL,
    ]
    for pattern in _PROTECTED_PREFIX_EXCLUDES:
        command.extend(["--exclude", pattern])
    _run(command, cwd=repo_root)


def _invalidate_site(aws: str, repo_root: Path, distribution_id: str) -> None:
    """Invalidate the published landing paths and wait for completion."""
    created = _run(
        [
            *_aws_base_command(aws),
            "cloudfront",
            "create-invalidation",
            "--distribution-id",
            distribution_id,
            "--paths",
            *_INVALIDATION_PATHS,
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


def _verify_public_delivery(target: DeploymentTarget) -> None:
    """Require the landing root, intact docs, and a private origin."""
    checks = (
        (f"{CANONICAL_SITE_URL}/", 200),
        (f"{CANONICAL_SITE_URL}/__cadrumo-delivery-missing__.html", 404),
        (f"{CANONICAL_DOCS_BASE_URL}/", 200),
        (f"https://{target.bucket}.s3.{STACK_REGION}.amazonaws.com/index.html", 403),
    )
    for url, expected_status in checks:
        actual_status, _headers = _endpoint_response(url)
        if actual_status != expected_status:
            raise SystemExit(
                f"Endpoint check failed for {url}: expected HTTP {expected_status}, received HTTP {actual_status}.",
            )


def _publish(aws: str, repo_root: Path) -> int:
    """Build, validate, upload, and invalidate the fixed Cadrumo landing page."""
    _require_human_publish_environment()
    _authenticated_account_id(aws, repo_root)
    target = _stack_target(aws, repo_root)
    _verify_distribution_alias(aws, repo_root, target.distribution_id)
    dist_root = _build_site(repo_root)
    _validate_site_artifacts(dist_root)
    _sync_site(aws, repo_root, dist_root, target.bucket)
    _invalidate_site(aws, repo_root, target.distribution_id)
    _verify_public_delivery(target)
    print(f"Published {CANONICAL_SITE_URL}/", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Publish the fixed Cadrumo landing page."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    publish = commands.add_parser("publish", help="Build and publish the fixed landing page.")
    publish.add_argument(
        "--confirm",
        choices=("publish-cadrumo-frontend",),
        required=True,
        help="Required literal acknowledgement for the local publishing.",
    )
    parser.parse_args(argv)

    repo_root = _repo_root()
    if shutil.which("npm") is None:
        raise SystemExit("npm is required to build the landing page.")
    aws = _required_executable("aws")
    return _publish(aws, repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
