"""``aeat bootstrap`` — provision scratch resources after authentication.

Picks up where ``just gcloud-auth`` and ``just gsuite-enable-apis``
leave off: validates ADC + scope set + API enablement, then idempotently
creates the ``aeat-scratch`` Drive folder, Sheet, and Doc (if they do
not already exist), and writes their IDs back into ``env/.env``.

The :func:`bootstrap` command is safe to re-run. The first run creates
the resources; the second discovers them by name and rewrites the same
IDs. The name-based dedup uses ``trashed=false`` so a deleted scratch
folder is re-created cleanly on next run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from ._i18n import t, tr

SCRATCH_FOLDER_NAME = "aeat-scratch"
"""Drive folder name used as the parent for all scratch resources."""

SCRATCH_SHEET_NAME = "aeat-scratch-sheet"
"""Spreadsheet name created inside :data:`SCRATCH_FOLDER_NAME`."""

SCRATCH_DOC_NAME = "aeat-scratch-doc"
"""Document name created inside :data:`SCRATCH_FOLDER_NAME`."""

FOLDER_MIME = "application/vnd.google-apps.folder"
"""Drive MIME type for a regular folder."""

SHEET_MIME = "application/vnd.google-apps.spreadsheet"
"""Drive MIME type for a Google Sheets spreadsheet."""

DOC_MIME = "application/vnd.google-apps.document"
"""Drive MIME type for a Google Docs document."""


@dataclass(frozen=True)
class ScratchResources:
    """The IDs of the three scratch resources after bootstrap.

    Attributes:
        folder_id: Drive ID of the parent ``aeat-scratch`` folder.
        sheet_id: Drive ID of the scratch spreadsheet.
        doc_id: Drive ID of the scratch document.
    """

    folder_id: str
    sheet_id: str
    doc_id: str


def dedup_existing_resource(
    name: str,
    mime: str,
    listing: list[dict[str, Any]],
) -> str | None:
    """Return the ID of the first listing entry matching ``name`` and ``mime``.

    Pure helper so the dedup logic is unit-testable without touching
    Google APIs.

    Args:
        name: Expected resource name.
        mime: Expected ``mimeType`` field.
        listing: Drive ``files.list`` items.

    Returns:
        The ``id`` of the first matching entry, or None if no entry
        matches.
    """
    for item in listing:
        if item.get("name") == name and item.get("mimeType") == mime:
            ident = item.get("id")
            if isinstance(ident, str):
                return ident
    return None


def _find_or_create_folder(drive: Any, name: str) -> str:
    """Locate or create a Drive folder by name in the user's My Drive root."""
    response = (
        drive.files()
        .list(
            q=(f"name='{name}' and mimeType='{FOLDER_MIME}' and 'root' in parents and trashed=false"),
            fields="files(id, name, mimeType)",
            pageSize=10,
        )
        .execute()
    )
    existing = dedup_existing_resource(name, FOLDER_MIME, response.get("files", []))
    if existing:
        return existing
    created = (
        drive.files()
        .create(
            body={"name": name, "mimeType": FOLDER_MIME},
            fields="id",
        )
        .execute()
    )
    return str(created["id"])


def _find_or_create_workspace_doc(
    drive: Any,
    name: str,
    mime: str,
    parent_id: str,
) -> str:
    """Locate or create a Workspace document (Sheet or Doc) inside ``parent_id``."""
    response = (
        drive.files()
        .list(
            q=(f"name='{name}' and mimeType='{mime}' and '{parent_id}' in parents and trashed=false"),
            fields="files(id, name, mimeType)",
            pageSize=10,
        )
        .execute()
    )
    existing = dedup_existing_resource(name, mime, response.get("files", []))
    if existing:
        return existing
    created = (
        drive.files()
        .create(
            body={"name": name, "mimeType": mime, "parents": [parent_id]},
            fields="id",
        )
        .execute()
    )
    return str(created["id"])


def _persist_ids(resources: ScratchResources) -> None:
    """Write the scratch IDs back into ``env/.env``."""
    from ...core.config import PROJECT_ROOT
    from ...core.env_io import write_env_vars

    write_env_vars(
        PROJECT_ROOT / "env" / ".env",
        {
            "AEAT_SCRATCH_FOLDER_ID": resources.folder_id,
            "AEAT_SCRATCH_SHEET_ID": resources.sheet_id,
            "AEAT_SCRATCH_DOC_ID": resources.doc_id,
        },
    )


def bootstrap() -> None:
    """Provision the scratch resource set, persist IDs, print a summary.

    Walks the full bootstrap path: validate ADC + scopes, locate or
    create the scratch folder, then create the matching Sheet and Doc
    inside it. Persisted IDs land in ``env/.env`` via
    :func:`aeat.core.env_io.write_env_vars`.

    Raises:
        typer.Exit: With code ``1`` when ``GOOGLE_CLOUD_PROJECT`` is
            unset or ADC is unavailable; with code ``2`` when the
            backing credentials cannot own Drive files (typical for
            consumer-tenant service accounts without storage quota).
    """
    # Local imports keep the CLI startup path light when only --help is used.
    from ...adapters.outbound.google import (
        REQUIRED_ADC_SCOPES,
        build_drive_service,
        get_credentials_for_scopes,
    )
    from ...core.config import Settings

    console = Console()
    settings = Settings()

    if not settings.google_cloud_project:
        console.print(
            "[red]"
            + tr(
                t(
                    "bootstrap: GOOGLE_CLOUD_PROJECT está vacío en env/.env",
                    "bootstrap: GOOGLE_CLOUD_PROJECT is empty in env/.env",
                    "bootstrap: GOOGLE_CLOUD_PROJECT és buit a env/.env",
                    "bootstrap: GOOGLE_CLOUD_PROJECT üres a env/.env-ben",
                )
            )
            + "[/]"
        )
        raise typer.Exit(code=1)

    try:
        creds = get_credentials_for_scopes(REQUIRED_ADC_SCOPES)
    except Exception as exc:
        console.print(
            "[red]"
            + tr(
                t(
                    f"bootstrap: credenciales no disponibles: {exc}",
                    f"bootstrap: credentials unavailable: {exc}",
                    f"bootstrap: credencials no disponibles: {exc}",
                    f"bootstrap: hitelesito adatok nem elerhetok: {exc}",
                )
            )
            + "[/]"
        )
        console.print(
            tr(
                t(
                    "Configura GOOGLE_APPLICATION_CREDENTIALS o ejecuta `just gcloud-auth`.",
                    "Configure GOOGLE_APPLICATION_CREDENTIALS or run `just gcloud-auth`.",
                    "Configura GOOGLE_APPLICATION_CREDENTIALS o executa `just gcloud-auth`.",
                    "Állítsd be a GOOGLE_APPLICATION_CREDENTIALS-t vagy futtasd: `just gcloud-auth`.",
                )
            )
        )
        raise typer.Exit(code=1) from exc

    drive = build_drive_service(creds)

    try:
        folder_id = _find_or_create_folder(drive, SCRATCH_FOLDER_NAME)
        sheet_id = _find_or_create_workspace_doc(drive, SCRATCH_SHEET_NAME, SHEET_MIME, folder_id)
        doc_id = _find_or_create_workspace_doc(drive, SCRATCH_DOC_NAME, DOC_MIME, folder_id)
    except Exception as exc:
        text = repr(exc).lower()
        if "storagequotaexceeded" in text or "storage quota" in text:
            console.print(
                "[yellow]"
                + tr(
                    t(
                        "bootstrap: no se pueden crear recursos de Drive con las credenciales activas.",
                        "bootstrap: cannot create Drive resources under the active credentials.",
                        "bootstrap: no es poden crear recursos de Drive amb les credencials actives.",
                        "bootstrap: nem lehet Drive erőforrásokat létrehozni az aktív hitelesito adatokkal.",
                    )
                )
                + "[/]"
            )
            console.print(
                tr(
                    t(
                        "Las cuentas de servicio en cuentas Google de consumo (no Workspace) tienen cuota cero "
                        "de almacenamiento en Drive y no pueden ser propietarias de archivos.",
                        "Service accounts on consumer (non-Workspace) Google accounts have zero "
                        "Drive storage quota and cannot own Drive files.",
                        "Els comptes de servei en comptes Google de consum (no Workspace) tenen quota zero "
                        "d'emmagatzematge a Drive i no poden ser propietaris de fitxers.",
                        "A fogyasztoi (nem Workspace) Google fiokokon a szolgaltatasi fiokoknak nulla a Drive tárhelykvótája, es nem birtokolhatnak Drive fajlokat.",
                    )
                )
            )
            console.print(
                tr(
                    t(
                        "Ejecuta `aeat oauth-client init` para crear un cliente OAuth Desktop + "
                        "`just gcloud-auth`, u opera desde un tenant Google Workspace donde "
                        "la SA pueda ser propietaria en una unidad compartida.",
                        "Run `aeat oauth-client init` to create an OAuth Desktop client + "
                        "`just gcloud-auth`, or operate from a Google Workspace tenant where "
                        "the SA can own files in a Shared Drive.",
                        "Executa `aeat oauth-client init` per crear un client OAuth Desktop + "
                        "`just gcloud-auth`, o opera des d'un tenant Google Workspace on "
                        "el SA pugui ser propietari en una unitat compartida.",
                        "Futtasd: `aeat oauth-client init` egy OAuth Desktop kliens letrehozasahoz + `just gcloud-auth`, vagy használj Google Workspace tenantot, ahol az SA tulajdonolhat fajlokat egy megosztott meghajtón.",
                    )
                )
            )
            raise typer.Exit(code=2) from exc
        raise

    resources = ScratchResources(folder_id=folder_id, sheet_id=sheet_id, doc_id=doc_id)
    _persist_ids(resources)

    table = Table(title="aeat bootstrap", show_lines=False, header_style="bold")
    table.add_column(
        tr(t("Recurso", "Resource", "Recurs", "Erőforrás")),
        style="cyan",
    )
    table.add_column(tr(t("ID", "ID", "ID", "Azonosító")), style="white", overflow="fold")
    table.add_row(
        tr(t("carpeta scratch", "scratch folder", "carpeta scratch", "scratch mappa")),
        folder_id,
    )
    table.add_row(
        tr(t("hoja scratch", "scratch sheet", "full scratch", "scratch táblázat")),
        sheet_id,
    )
    table.add_row(
        tr(t("documento scratch", "scratch doc", "document scratch", "scratch dokumentum")),
        doc_id,
    )
    console.print(table)
    console.print(
        "[green]"
        + tr(
            t(
                "bootstrap: env/.env actualizado. Vuelve a ejecutar `aeat doctor` para verificar.",
                "bootstrap: env/.env updated. Re-run `aeat doctor` to verify.",
                "bootstrap: env/.env actualitzat. Torna a executar `aeat doctor` per verificar.",
                "bootstrap: env/.env frissítve. Futtasd újra: `aeat doctor` az ellenorzeshez.",
            )
        )
        + "[/]"
    )
