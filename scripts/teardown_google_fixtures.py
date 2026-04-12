"""Teardown counterpart to :mod:`provision_google_fixtures`.

Permanently deletes the Google Workspace fixture tree rooted at
``AEAT_GOOGLE_TEST_FIXTURES_FOLDER_ID``. Drive's recursive delete
cascades through every child resource — one API call removes the
smoke Sheet, the smoke Doc, and the root folder in a single stroke.

After the delete succeeds, every fixture env var written by
:mod:`provision_google_fixtures` is cleared back to empty in
``env/.env`` so a subsequent provisioning run starts from a pristine
state.

Safe to run on a machine that has never provisioned fixtures: if
``AEAT_GOOGLE_TEST_FIXTURES_FOLDER_ID`` is empty the script logs a
notice and exits 0 without calling Google.

Usage::

    uv run python scripts/teardown_google_fixtures.py
    # or, via the cross-platform justfile recipe:
    just google-fixtures-teardown
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Keep the sibling-import pattern consistent with the provisioning
# script. See its docstring for rationale.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _fixture_catalogue import CATALOGUE  # noqa: E402
from googleapiclient.errors import HttpError  # noqa: E402

from aeat.auth import DRIVE_SCOPE, build_drive_service, get_credentials_for_scopes  # noqa: E402
from aeat.config import PROJECT_ROOT, Settings  # noqa: E402
from aeat.env_io import write_env_vars  # noqa: E402
from aeat.errors import FixtureProvisioningError  # noqa: E402
from aeat.logging import get_logger  # noqa: E402

log = get_logger(__name__)


def _delete_folder(drive: Any, folder_id: str) -> None:
    """Permanently delete a Drive folder and every descendant.

    Uses ``files.delete`` (not ``files.update`` with ``trashed=true``)
    so the resource cannot be resurrected from trash; fixture IDs must
    not outlive a teardown.

    Args:
        drive: Authenticated Drive v3 service.
        folder_id: The Drive folder ID to remove.

    Raises:
        FixtureProvisioningError: If the Drive API rejects the delete
            for any reason other than "already absent".
    """
    try:
        drive.files().delete(fileId=folder_id).execute()
    except HttpError as exc:
        # Treat 404 as a successful no-op so the teardown stays
        # idempotent against partial cleanups or already-deleted trees.
        if exc.resp.status == 404:
            log.info("fixture folder %s already absent — nothing to delete", folder_id)
            return
        msg = f"Drive API rejected delete of fixture folder {folder_id}: status={exc.resp.status}"
        raise FixtureProvisioningError(msg) from exc


def _clear_env_vars() -> Path:
    """Clear every fixture env var back to empty in ``env/.env``.

    Returns:
        The absolute path to the env file that was rewritten.
    """
    env_path = PROJECT_ROOT / "env" / ".env"
    mapping: dict[str, str] = {spec.env_var_name: "" for spec in CATALOGUE.iter_specs()}
    write_env_vars(env_path, mapping)
    return env_path


def teardown() -> int:
    """Delete the fixture tree and clear its env-var footprint.

    Returns:
        Process exit code: ``0`` on success (including the no-op case
        where no fixture folder was ever provisioned), ``1`` on failure.
    """
    settings = Settings()
    folder_id = settings.aeat_google_test_fixtures_folder_id
    if not folder_id:
        log.info(
            "AEAT_GOOGLE_TEST_FIXTURES_FOLDER_ID is empty — nothing to tear down; "
            "clearing env-var footprint for a clean state"
        )
        _clear_env_vars()
        return 0

    creds = get_credentials_for_scopes([DRIVE_SCOPE])
    drive = build_drive_service(creds)

    try:
        _delete_folder(drive, folder_id)
    except FixtureProvisioningError as exc:
        log.error("teardown failed: %s", exc)
        return 1

    env_path = _clear_env_vars()
    log.info("fixture tree rooted at %s deleted; cleared env footprint in %s", folder_id, env_path)
    return 0


def main() -> int:
    """CLI entry point."""
    return teardown()


if __name__ == "__main__":
    raise SystemExit(main())
