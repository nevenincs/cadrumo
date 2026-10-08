"""Build, validate, publish, activate, or roll back the documentation site through its CLI."""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable
from pathlib import Path

from dev.deploy.cloudflare_api import (
    zone_id,
)
from dev.deploy.docs_delivery_settings import configure_delivery, prepare_storage

from .docs_delivery_activation import _activate_existing, _provision, _publish, _rollback
from .docs_delivery_contracts import DOCS_ZONE
from .docs_delivery_policy import _delivery_credentials, _require_local_session
from .docs_site_build import _build_site_roots
from .docs_site_commands import _repo_root
from .docs_site_languages import localized_languages
from .docs_site_preflight import _validate_built_site


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


def main(argv: list[str] | None = None) -> int:
    """Publish, roll back or wire up the Cadrumo documentation site."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    settings = commands.add_parser(
        "configure", help="Reconcile documentation-owned storage, cache and transport settings."
    )
    settings.add_argument("--confirm", choices=("configure-cadrumo-docs",), required=True)
    settings.add_argument("--snapshot", type=Path, required=True, help="New directory for the previous configuration.")
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
    activate = commands.add_parser("activate", help="Activate a completed release from verified local bytes.")
    activate.add_argument("--confirm", choices=("activate-cadrumo-docs",), required=True)
    activate.add_argument("--release", required=True)
    activate.add_argument("--directory", type=Path, required=True)
    commands.add_parser("dry-run", help="Build and validate every site root without uploading.")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    if args.command == "dry-run":
        return _dry_run(repo_root)
    if args.command == "configure":
        _require_local_session("configure", environment=os.environ)
        credentials = _delivery_credentials(os.environ)
        prepare_storage(credentials.account)
        configure_delivery(credentials.account, zone_id(credentials.account, DOCS_ZONE), args.snapshot)
        return 0
    if args.command == "provision":
        return _provision()
    if args.command == "rollback":
        return _rollback(args.release)
    if args.command == "activate":
        return _activate_existing(args.release, args.directory)
    return _publish(repo_root, release_label=args.release_label, cutover=args.cutover)


if __name__ == "__main__":
    raise SystemExit(main())
