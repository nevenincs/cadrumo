"""Admit publish environments and sealed release labels before delivery work."""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from dev.deploy.cloudflare_api import (
    CloudflareAccount,
)
from dev.deploy.r2_objects import R2Bucket
from dev.source_tree import content_digest, repository_files

from .docs_delivery_contracts import _CI_MARKERS, _RELEASE_LABEL_RE, DELIVERY_CREDENTIAL_ENV, DeliveryCredentials


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
    """Label a local publish by the actual documentation and producer content."""
    files = repository_files(repo_root, under=("docs", "src", "dev/docs", "pyproject.toml", "uv.lock"))
    return f"local-{content_digest(repo_root, files)[:12]}"


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
