"""Idempotent provisioner for the Google Workspace test fixture set.

Reads :data:`scripts._fixture_catalogue.CATALOGUE`, walks it parent-first,
idempotently creates each Drive / Sheets / Docs artefact under the
project account, seeds newly-created resources with the catalogue's
sentinel values, and writes the resulting resource IDs back into
``env/.env`` so ``tests/live/test_google_fixtures_smoke.py`` can pick
them up on its next run.

Re-runs are safe and non-destructive: existing resources are discovered
by title under their parent and reused verbatim. Only fixtures that did
not exist before the run are seeded — previously-provisioned fixtures
are left untouched so any hand-annotated review notes survive
re-provisioning.

The script reuses the Google client surface provisioned by chore/4
(:mod:`aeat.auth`, :mod:`aeat.env_io`) rather than defining a competing
client. See ``.vault/adr/2026-04-12-google-fixtures-adr.md``.

Usage::

    uv run python scripts/provision_google_fixtures.py
    # or, via the cross-platform justfile recipe:
    just google-fixtures-provision
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Allow ``python scripts/provision_google_fixtures.py`` to import the
# sibling catalogue module without the project installing ``scripts`` as
# a package. Python already adds the script's directory to ``sys.path``
# on direct execution; this line is a no-op in that mode but makes the
# import work when the script is loaded via ``runpy`` / test harnesses.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _fixture_catalogue import CATALOGUE, FixtureKind, FixtureSpec  # noqa: E402

from aeat.auth import (  # noqa: E402
    DOCS_SCOPE,
    DRIVE_SCOPE,
    SHEETS_SCOPE,
    build_docs_service,
    build_drive_service,
    build_sheets_service,
    get_credentials_for_scopes,
)
from aeat.config import PROJECT_ROOT  # noqa: E402
from aeat.env_io import write_env_vars  # noqa: E402
from aeat.errors import FixtureProvisioningError  # noqa: E402
from aeat.logging import get_logger  # noqa: E402

log = get_logger(__name__)

# Drive mime types for the supported fixture kinds.
_FOLDER_MIME = "application/vnd.google-apps.folder"
_SHEET_MIME = "application/vnd.google-apps.spreadsheet"
_DOC_MIME = "application/vnd.google-apps.document"
_FORM_MIME = "application/vnd.google-apps.form"

_MIME_BY_KIND: dict[FixtureKind, str] = {
    FixtureKind.DRIVE_FOLDER: _FOLDER_MIME,
    FixtureKind.SHEET: _SHEET_MIME,
    FixtureKind.DOC: _DOC_MIME,
    FixtureKind.FORM: _FORM_MIME,
}


@dataclass(frozen=True)
class ProvisioningResult:
    """Outcome of provisioning a single fixture.

    Attributes:
        spec: The originating :class:`FixtureSpec`.
        resource_id: The Google resource ID (Drive file ID, Sheet ID, Doc ID).
        created: ``True`` if the resource was freshly created on this run,
            ``False`` if an existing resource was discovered and reused.
    """

    spec: FixtureSpec
    resource_id: str
    created: bool


# ── Drive helpers (typed thin wrappers) ────────────────────────────────────


def _escape_drive_literal(value: str) -> str:
    """Escape a string literal for inclusion in a Drive ``q=`` parameter.

    Drive's query language uses single-quoted strings; inner single
    quotes and backslashes must be escaped. The Google client library
    does not do this for callers.
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _find_existing(drive: Any, title: str, mime: str, parent_id: str) -> str | None:
    """Return the ID of the first existing file matching ``title``/``mime``.

    Args:
        drive: Authenticated Drive v3 service.
        title: Expected ``name`` field.
        mime: Expected ``mimeType`` field.
        parent_id: Drive folder ID to scope the search under. Use
            ``"root"`` for the My Drive root.

    Returns:
        The resource ID, or ``None`` if no matching entry exists.
    """
    title_literal = _escape_drive_literal(title)
    parent_literal = _escape_drive_literal(parent_id)
    query = f"name='{title_literal}' and mimeType='{mime}' and '{parent_literal}' in parents and trashed=false"
    response = drive.files().list(q=query, fields="files(id, name, mimeType)", pageSize=10).execute()
    for entry in response.get("files", []):
        ident = entry.get("id")
        if isinstance(ident, str):
            return ident
    return None


def _create_resource(drive: Any, title: str, mime: str, parent_id: str) -> str:
    """Create a Drive-managed resource by title, mime, and parent.

    Args:
        drive: Authenticated Drive v3 service.
        title: Name to set on the new resource.
        mime: The Workspace mime type (folder / sheet / doc / form).
        parent_id: Drive folder ID to place the resource in.

    Returns:
        The new resource ID.

    Raises:
        FixtureProvisioningError: If the Drive API returns no ``id``.
    """
    body: dict[str, Any] = {"name": title, "mimeType": mime}
    if parent_id and parent_id != "root":
        body["parents"] = [parent_id]
    response = drive.files().create(body=body, fields="id").execute()
    ident = response.get("id")
    if not isinstance(ident, str) or not ident:
        msg = f"Drive create returned no id for {title!r} ({mime})"
        raise FixtureProvisioningError(msg)
    return ident


def _find_or_create(drive: Any, title: str, mime: str, parent_id: str) -> tuple[str, bool]:
    """Find-or-create a resource under ``parent_id``.

    Returns:
        Tuple of ``(resource_id, created)``.
    """
    existing = _find_existing(drive, title, mime, parent_id)
    if existing is not None:
        return existing, False
    created_id = _create_resource(drive, title, mime, parent_id)
    return created_id, True


# ── Seeding helpers ────────────────────────────────────────────────────────


def _seed_sheet(sheets: Any, spreadsheet_id: str, value: str) -> None:
    """Write ``value`` into cell ``A1`` of a freshly provisioned Sheet."""
    body: dict[str, Any] = {"values": [[value]]}
    sheets.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="A1",
        valueInputOption="RAW",
        body=body,
    ).execute()


def _seed_doc(docs: Any, document_id: str, text: str) -> None:
    """Insert ``text`` at the very beginning of a freshly provisioned Doc.

    A newly-created Google Doc has a single empty paragraph at index 1
    (index 0 is the document start sentinel). Inserting at index 1
    places the text as the body's first paragraph, which is what the
    smoke test asserts.
    """
    requests: list[dict[str, Any]] = [
        {"insertText": {"location": {"index": 1}, "text": text}},
    ]
    docs.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()


# ── Provisioning walk ──────────────────────────────────────────────────────


def provision() -> list[ProvisioningResult]:
    """Provision every fixture in :data:`CATALOGUE` end-to-end.

    Returns:
        The ordered list of :class:`ProvisioningResult` entries —
        parent-first, matching catalogue insertion order.

    Raises:
        FixtureProvisioningError: On any dedup / creation / seeding
            failure from the Google APIs.
    """
    creds = get_credentials_for_scopes([DRIVE_SCOPE, SHEETS_SCOPE, DOCS_SCOPE])
    drive = build_drive_service(creds)
    sheets = build_sheets_service(creds)
    docs = build_docs_service(creds)

    results: list[ProvisioningResult] = []
    resolved_ids: dict[str, str] = {}

    # Walk in catalogue insertion order. The root folder comes first and
    # every child references it via ``parent_id`` → fixture_id, which we
    # translate to the real Drive ID using ``resolved_ids``.
    for spec in CATALOGUE:
        mime = _MIME_BY_KIND[spec.kind]
        if spec.parent_id is None:
            # Root folder — live under My Drive root.
            parent_drive_id = "root"
        else:
            parent_drive_id = resolved_ids.get(spec.parent_id, "")
            if not parent_drive_id:
                msg = (
                    f"fixture {spec.fixture_id!r} references unknown parent "
                    f"{spec.parent_id!r}; check catalogue insertion order"
                )
                raise FixtureProvisioningError(msg)

        log.info("provisioning %s (%s) under parent %s", spec.fixture_id, spec.kind.value, parent_drive_id)
        resource_id, created = _find_or_create(drive, spec.title, mime, parent_drive_id)
        resolved_ids[spec.fixture_id] = resource_id

        # Only seed resources that were freshly created. Re-runs leave
        # existing fixtures untouched so review annotations survive.
        if created:
            if spec.kind is FixtureKind.SHEET and spec.seed_a1 is not None:
                _seed_sheet(sheets, resource_id, spec.seed_a1)
                log.info("seeded Sheet %s cell A1", spec.fixture_id)
            elif spec.kind is FixtureKind.DOC and spec.seed_body is not None:
                _seed_doc(docs, resource_id, spec.seed_body)
                log.info("seeded Doc %s body", spec.fixture_id)

        results.append(ProvisioningResult(spec=spec, resource_id=resource_id, created=created))

    return results


def _persist_env(results: list[ProvisioningResult]) -> Path:
    """Write every provisioned resource ID back into ``env/.env``.

    Args:
        results: Ordered provisioning outcomes from :func:`provision`.

    Returns:
        The absolute path to the env file that was rewritten.
    """
    mapping: dict[str, str] = {r.spec.env_var_name: r.resource_id for r in results}
    env_path = PROJECT_ROOT / "env" / ".env"
    write_env_vars(env_path, mapping)
    return env_path


def _render_summary(results: list[ProvisioningResult]) -> None:
    """Print a rich table summarising the provisioning outcome."""
    # Local import keeps rich optional at module load time for tests that
    # may import this module purely for its helpers.
    from rich.console import Console
    from rich.table import Table

    table = Table(title="google-fixtures-provision", header_style="bold")
    table.add_column("fixture_id", style="cyan")
    table.add_column("kind", style="white")
    table.add_column("status", style="white")
    table.add_column("resource id", style="white", overflow="fold")
    for result in results:
        status = "[green]created[/]" if result.created else "[dim]existing[/]"
        table.add_row(result.spec.fixture_id, result.spec.kind.value, status, result.resource_id)
    Console().print(table)


def main() -> int:
    """CLI entry point for ``python scripts/provision_google_fixtures.py``.

    Returns:
        Process exit code: ``0`` on success, ``1`` on provisioning failure.
    """
    try:
        results = provision()
    except FixtureProvisioningError as exc:
        log.error("fixture provisioning failed: %s", exc)
        return 1
    env_path = _persist_env(results)
    _render_summary(results)
    log.info("wrote %d fixture IDs to %s", len(results), env_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
