"""``aeat doctor`` — Google Workspace + GCP health check.

Single read-only command that reports the state of every layer the
gsuite-bootstrap pipeline depends on. Designed to be the only thing a
developer or CI job needs to know about: if ``aeat doctor`` exits 0,
the workstation is fully provisioned. If it exits non-zero, the printed
table tells you which row to fix.

The doctor never mutates state. It does perform real Google API calls
when ADC are present, because the only honest answer to "are my
credentials actually working" is "I called the API and it returned a
2xx".
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from ...adapters.outbound.aeat.auth import (
    AeatAuthenticator,
)
from ...adapters.outbound.google import (
    CLOUD_PLATFORM_SCOPE,
    DOCS_SCOPE,
    DRIVE_SCOPE,
    REQUIRED_ADC_SCOPES,
    SHEETS_SCOPE,
    GoogleAuthPath,
    adc_well_known_path,
    build_cloudfunctions_client,
    build_cloudrun_client,
    build_docs_service,
    build_drive_service,
    build_serviceusage_service,
    build_sheets_service,
    build_storage_client,
    get_credentials_for_scopes,
    inspect_google_auth,
)
from ...application.auth import describe_provider_operator_impact
from ...core.config import PROJECT_ROOT, Settings
from ...core.logging import get_logger
from ._i18n import tr

_log = get_logger(__name__)

# ── Row primitives ──────────────────────────────────────────────────────────


class State(StrEnum):
    """The verdict for a single doctor row."""

    OK = "OK"
    MISSING = "MISSING"
    PARTIAL = "PARTIAL"
    WARN = "WARN"
    SKIP = "SKIP"


@dataclass(frozen=True)
class Row:
    """One line in the doctor table.

    Attributes:
        section: The surface or check this row covers.
        required: True if a non-OK state should cause non-zero exit.
        state: The verdict.
        detail: One-line remediation hint shown in the table.
    """

    section: str
    required: bool
    state: State
    detail: str


# ── API services split by billing requirement ───────────────────────────────
#
# Drive/Sheets/Docs/IAM/Service Usage are billing-free and required.
# Cloud Functions/Run/Storage all require an active billing account on
# the project — they are advisory rows, surfaced if the operator opts
# in by linking billing.


REQUIRED_API_SERVICES: list[str] = [
    "drive.googleapis.com",
    "sheets.googleapis.com",
    "docs.googleapis.com",
    "iam.googleapis.com",
    "serviceusage.googleapis.com",
]

OPTIONAL_API_SERVICES: list[str] = [
    "cloudfunctions.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
]


# ── Pure helpers (unit tested) ──────────────────────────────────────────────


def adc_scopes_from_file(path: Path) -> list[str]:
    """Extract the granted scope list from an ADC JSON file.

    The ADC JSON written by ``gcloud auth application-default login``
    stores granted scopes in either the top-level ``scopes`` field or
    inside ``client_secret``-style nested structures depending on the
    gcloud version. This helper checks both shapes.

    Args:
        path: Path to the ADC JSON file.

    Returns:
        Sorted list of granted scope strings, or an empty list if the
        file does not exist or has no recognisable scope field.
    """
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    scopes: list[str] = []
    if isinstance(payload, dict):
        raw = payload.get("scopes")
        if isinstance(raw, list):
            scopes.extend(str(item) for item in raw)
    return sorted(set(scopes))


def gcloud_binary_path() -> str | None:
    """Return the path to the ``gcloud`` binary on PATH, or ``None``."""
    return shutil.which("gcloud")


def _run_gcloud(args: list[str]) -> tuple[int, str, str]:
    """Run a ``gcloud`` command and return ``(exit_code, stdout, stderr)``.

    Honours ``CLOUDSDK_PYTHON`` if it is already set in the environment;
    the doctor itself does not bootstrap it (the recipe layer does).
    """
    binary = gcloud_binary_path()
    if not binary:
        return (127, "", "gcloud not on PATH")
    completed = subprocess.run(  # noqa: S603 - args are static, binary is from PATH
        [binary, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return (completed.returncode, completed.stdout.strip(), completed.stderr.strip())


# ── Individual check functions ──────────────────────────────────────────────


def check_env_file(settings: Settings) -> Row:
    """Verify the canonical ``env/.env`` file exists."""
    path = PROJECT_ROOT / "env" / ".env"
    if not path.exists():
        return Row(
            section=tr("cli.doctor.sections.env_file"),
            required=True,
            state=State.MISSING,
            detail=tr("cli.doctor.details.run_env_setup"),
        )
    _ = settings  # silence unused-arg lint; Settings load is the existence check
    return Row(section=tr("cli.doctor.sections.env_file"), required=True, state=State.OK, detail=str(path))


def check_google_cloud_project(settings: Settings) -> Row:
    """Verify ``GOOGLE_CLOUD_PROJECT`` is non-empty in Settings."""
    if not settings.google_cloud_project:
        return Row(
            section=tr("cli.doctor.sections.google_cloud_project"),
            required=True,
            state=State.MISSING,
            detail=tr("cli.doctor.details.set_gcp_project"),
        )
    return Row(
        section=tr("cli.doctor.sections.google_cloud_project"),
        required=True,
        state=State.OK,
        detail=settings.google_cloud_project,
    )


def check_active_google_auth_path(settings: Settings) -> Row:
    """Explain which Google auth path is active, blocking on ambiguity."""

    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    if inspection.active_path is None:
        return Row(
            section=tr("cli.doctor.sections.active_google_auth_path"),
            required=True,
            state=State.MISSING,
            detail=inspection.blocking_reason or tr("cli.doctor.details.no_active_auth_path"),
        )
    source = "explicit" if inspection.configured_path is not None else "inferred"
    return Row(
        section=tr("cli.doctor.sections.active_google_auth_path"),
        required=True,
        state=State.OK,
        detail=tr("cli.doctor.details.auth_path_active", path=inspection.active_path.value, source=source),
    )


def check_google_auth_readiness(settings: Settings) -> Row:
    """Summarize CLI/bootstrap versus MCP readiness for the active path."""

    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    if inspection.active_path is None:
        return Row(
            section=tr("cli.doctor.sections.google_auth_readiness"),
            required=True,
            state=State.MISSING,
            detail=inspection.blocking_reason or tr("cli.doctor.details.select_prepare_auth_path"),
        )
    if inspection.cli_ready and inspection.mcp_ready:
        return Row(
            section=tr("cli.doctor.sections.google_auth_readiness"),
            required=True,
            state=State.OK,
            detail=tr("cli.doctor.details.auth_ready_both"),
        )
    if inspection.cli_ready and not inspection.mcp_ready:
        return Row(
            section=tr("cli.doctor.sections.google_auth_readiness"),
            required=True,
            state=State.PARTIAL,
            detail=tr("cli.doctor.details.auth_ready_cli_only"),
        )
    if inspection.mcp_ready and not inspection.cli_ready:
        return Row(
            section=tr("cli.doctor.sections.google_auth_readiness"),
            required=True,
            state=State.PARTIAL,
            detail=tr("cli.doctor.details.auth_ready_mcp_only"),
        )
    return Row(
        section=tr("cli.doctor.sections.google_auth_readiness"),
        required=True,
        state=State.MISSING,
        detail=tr("cli.doctor.details.auth_ready_none"),
    )


def check_desktop_oauth_client_material(settings: Settings) -> Row:
    """Report the Desktop OAuth client configuration state."""

    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    required = inspection.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV
    if inspection.desktop_oauth_complete:
        detail = (
            tr("cli.doctor.details.oauth_json_present", path=inspection.desktop_oauth_json_path)
            if inspection.desktop_oauth_json_path is not None
            else tr("cli.doctor.details.adc_substep_json_not_configured")
        )
        return Row(
            section=tr("cli.doctor.sections.desktop_oauth_client_material"),
            required=required,
            state=State.OK if required else State.SKIP,
            detail=(detail if required else tr("cli.doctor.details.not_required_see_drift")),
        )
    if inspection.desktop_oauth_partial:
        return Row(
            section=tr("cli.doctor.sections.desktop_oauth_client_material"),
            required=required,
            state=State.MISSING if required else State.WARN,
            detail=tr("cli.doctor.details.oauth_config_partial"),
        )
    return Row(
        section=tr("cli.doctor.sections.desktop_oauth_client_material"),
        required=required,
        state=State.MISSING if required else State.SKIP,
        detail=tr("cli.doctor.details.not_required_active_path")
        if not required
        else tr("cli.doctor.details.oauth_config_missing"),
    )


def check_cli_oauth_cache(settings: Settings) -> Row:
    """Report the repo-local CLI OAuth token cache state."""

    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    required = inspection.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV
    if inspection.active_path != GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV:
        return Row(
            section=tr("cli.doctor.sections.cli_oauth_cache"),
            required=False,
            state=State.SKIP,
            detail=tr("cli.doctor.details.not_required_active_path"),
        )
    if inspection.oauth_token_issue is None:
        return Row(
            section=tr("cli.doctor.sections.cli_oauth_cache"),
            required=required,
            state=State.OK,
            detail=str(inspection.oauth_token_path),
        )
    return Row(
        section=tr("cli.doctor.sections.cli_oauth_cache"),
        required=required,
        state=State.MISSING,
        detail=tr("cli.doctor.details.oauth_token_issue", issue=inspection.oauth_token_issue),
    )


def check_mcp_credentials_cache(settings: Settings) -> Row:
    """Report the repo-local Google Workspace MCP credentials directory state."""

    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    if inspection.active_path is None:
        return Row(
            section=tr("cli.doctor.sections.mcp_credentials_cache"),
            required=True,
            state=State.MISSING,
            detail=inspection.blocking_reason or tr("cli.doctor.details.select_auth_path_first"),
        )
    if inspection.mcp_credentials_exist:
        return Row(
            section=tr("cli.doctor.sections.mcp_credentials_cache"),
            required=True,
            state=State.OK,
            detail=tr("cli.doctor.details.mcp_credentials_present", dir=inspection.mcp_credentials_dir),
        )
    if inspection.mcp_credentials_dir_exists:
        return Row(
            section=tr("cli.doctor.sections.mcp_credentials_cache"),
            required=True,
            state=State.PARTIAL,
            detail=tr("cli.doctor.details.mcp_credentials_dir_prepared", dir=inspection.mcp_credentials_dir),
        )
    return Row(
        section=tr("cli.doctor.sections.mcp_credentials_cache"),
        required=True,
        state=State.MISSING,
        detail=tr("cli.doctor.details.run_auth_init_mcp"),
    )


def check_inactive_google_auth_drift(settings: Settings) -> Row:
    """Surface ignored stale config from the inactive auth path."""

    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    drift = inspection.inactive_path_drift
    if drift is None:
        return Row(
            section=tr("cli.doctor.sections.inactive_path_drift"),
            required=False,
            state=State.SKIP,
            detail=tr("cli.doctor.details.no_stale_artifacts"),
        )
    return Row(
        section=tr("cli.doctor.sections.inactive_path_drift"),
        required=False,
        state=State.WARN,
        detail=drift,
    )


def check_gcloud_binary() -> Row:
    """Verify the ``gcloud`` CLI is on PATH."""
    if not gcloud_binary_path():
        return Row(
            section=tr("cli.doctor.sections.gcloud_binary"),
            required=False,
            state=State.MISSING,
            detail=tr("cli.doctor.details.install_gcloud_advisory"),
        )
    code, out, _err = _run_gcloud(["version"])
    if code != 0:
        return Row(
            section=tr("cli.doctor.sections.gcloud_binary"),
            required=False,
            state=State.WARN,
            detail=tr("cli.doctor.details.gcloud_version_failed"),
        )
    first_line = out.splitlines()[0] if out else tr("cli.doctor.details.gcloud_installed")
    return Row(section=tr("cli.doctor.sections.gcloud_binary"), required=False, state=State.OK, detail=first_line)


def check_gcloud_account() -> Row:
    """Verify there is at least one ACTIVE gcloud account."""
    code, out, _err = _run_gcloud(["auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
    if code != 0 or not out:
        return Row(
            section=tr("cli.doctor.sections.gcloud_auth"),
            required=False,
            state=State.MISSING,
            detail=tr("cli.doctor.details.run_gcloud_auth"),
        )
    return Row(
        section=tr("cli.doctor.sections.gcloud_auth"), required=False, state=State.OK, detail=out.splitlines()[0]
    )


def check_gcloud_project_matches(settings: Settings) -> Row:
    """Verify the gcloud-active project matches ``GOOGLE_CLOUD_PROJECT``."""
    code, out, _err = _run_gcloud(["config", "get-value", "project"])
    if code != 0 or not out or out.lower() == "unset":
        return Row(
            section=tr("cli.doctor.sections.gcloud_project"),
            required=False,
            state=State.MISSING,
            detail=tr("cli.doctor.details.run_gcloud_config_set_project"),
        )
    if settings.google_cloud_project and out != settings.google_cloud_project:
        return Row(
            section=tr("cli.doctor.sections.gcloud_project"),
            required=False,
            state=State.WARN,
            detail=tr(
                "cli.doctor.details.gcloud_env_project_mismatch",
                out=out,
                settings_project=settings.google_cloud_project,
            ),
        )
    return Row(section=tr("cli.doctor.sections.gcloud_project"), required=False, state=State.OK, detail=out)


def check_credentials_path(settings: Settings) -> Row:
    """Report which auth path the unified resolver will use."""
    if settings.google_application_credentials and Path(settings.google_application_credentials).exists():
        return Row(
            section=tr("cli.doctor.sections.auth_path"),
            required=True,
            state=State.OK,
            detail=tr("cli.doctor.details.auth_path_service_account", path=settings.google_application_credentials),
        )
    if settings.google_oauth_client_id and settings.google_oauth_client_secret:
        return Row(
            section=tr("cli.doctor.sections.auth_path"),
            required=True,
            state=State.OK,
            detail=tr("cli.doctor.details.auth_path_oauth_desktop"),
        )
    if adc_well_known_path().exists():
        return Row(
            section=tr("cli.doctor.sections.auth_path"),
            required=True,
            state=State.OK,
            detail=tr("cli.doctor.details.auth_path_adc", path=adc_well_known_path()),
        )
    return Row(
        section=tr("cli.doctor.sections.auth_path"),
        required=True,
        state=State.MISSING,
        detail=tr("cli.doctor.details.no_credentials_configured"),
    )


def check_adc_file(settings: Settings) -> Row:
    """Advisory: ADC JSON file at the well-known path."""
    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    path = adc_well_known_path()
    if not path.exists():
        return Row(
            section=tr("cli.doctor.sections.adc_file"),
            required=False,
            state=State.SKIP,
            detail=(
                tr("cli.doctor.details.adc_not_configured_advisory")
                if inspection.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV
                else tr("cli.doctor.details.not_required_active_path")
            ),
        )
    return Row(section=tr("cli.doctor.sections.adc_file"), required=False, state=State.OK, detail=str(path))


def check_adc_scopes(settings: Settings) -> Row:
    """Advisory: ADC JSON contains the required scopes (only relevant when ADC is the path)."""
    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    path = adc_well_known_path()
    if not path.exists():
        return Row(
            section=tr("cli.doctor.sections.adc_scopes"),
            required=False,
            state=State.SKIP,
            detail=(
                tr("cli.doctor.details.adc_not_configured_advisory")
                if inspection.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV
                else tr("cli.doctor.details.not_required_active_path")
            ),
        )
    granted = adc_scopes_from_file(path)
    if not granted:
        return Row(
            section=tr("cli.doctor.sections.adc_scopes"),
            required=False,
            state=State.WARN,
            detail=tr("cli.doctor.details.adc_no_scopes"),
        )
    missing = sorted(set(REQUIRED_ADC_SCOPES) - set(granted))
    if missing:
        return Row(
            section=tr("cli.doctor.sections.adc_scopes"),
            required=False,
            state=State.WARN,
            detail=tr("cli.doctor.details.adc_missing_scopes", missing=", ".join(short_scope(s) for s in missing)),
        )
    return Row(
        section=tr("cli.doctor.sections.adc_scopes"),
        required=False,
        state=State.OK,
        detail=tr("cli.doctor.details.adc_granted_scopes", count=len(granted)),
    )


def short_scope(scope: str) -> str:
    """Trim a scope URI to its trailing path segment for display."""
    return scope.rsplit("/", 1)[-1]


def check_api_enablement(settings: Settings) -> list[Row]:
    """Verify each required API is enabled in the active project.

    Performs one Service Usage list call covering every required service
    so the doctor only pays one round-trip for the whole set.
    """
    if not settings.google_cloud_project:
        return [
            Row(
                section=tr("cli.doctor.sections.api_enablement"),
                required=True,
                state=State.SKIP,
                detail=tr("cli.doctor.details.gcp_project_not_set"),
            )
        ]
    try:
        creds = get_credentials_for_scopes([CLOUD_PLATFORM_SCOPE])
        service = build_serviceusage_service(creds)
        parent = f"projects/{settings.google_cloud_project}"
        enabled: set[str] = set()
        request: Any = service.services().list(parent=parent, filter="state:ENABLED", pageSize=200)
        while request is not None:
            response = request.execute()
            for item in response.get("services", []):
                name = item.get("config", {}).get("name") or item.get("name", "")
                if name:
                    enabled.add(name.rsplit("/", 1)[-1])
            request = service.services().list_next(previous_request=request, previous_response=response)
    except Exception as exc:
        _log.warning("check_api_enablement: service usage call failed", exc_info=True)
        return [
            Row(
                section=tr("cli.doctor.sections.api_enablement"),
                required=True,
                state=State.MISSING,
                detail=tr("cli.doctor.details.service_usage_failed", exc_name=exc.__class__.__name__),
            )
        ]

    rows: list[Row] = []
    for service_name in REQUIRED_API_SERVICES:
        if service_name in enabled:
            rows.append(
                Row(
                    section=tr("cli.doctor.sections.api_service", service_name=service_name),
                    required=True,
                    state=State.OK,
                    detail=tr("cli.doctor.details.api_enabled"),
                )
            )
        else:
            rows.append(
                Row(
                    section=tr("cli.doctor.sections.api_service", service_name=service_name),
                    required=True,
                    state=State.MISSING,
                    detail=tr("cli.doctor.details.run_gcloud_services_enable", service_name=service_name),
                )
            )
    for service_name in OPTIONAL_API_SERVICES:
        if service_name in enabled:
            rows.append(
                Row(
                    section=tr("cli.doctor.sections.api_service", service_name=service_name),
                    required=False,
                    state=State.OK,
                    detail=tr("cli.doctor.details.api_enabled"),
                )
            )
        else:
            rows.append(
                Row(
                    section=tr("cli.doctor.sections.api_service", service_name=service_name),
                    required=False,
                    state=State.SKIP,
                    detail=tr("cli.doctor.details.api_needs_billing"),
                )
            )
    return rows


def check_drive_round_trip() -> Row:
    """Call ``drive.about().get`` to confirm Drive auth round-trip.

    Advisory rather than required because consumer-Gmail service
    accounts return ``invalid_grant`` / quota errors here even though
    the credentials are otherwise valid for non-Drive APIs.
    """
    settings = Settings()
    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    required = inspection.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV
    try:
        creds = get_credentials_for_scopes([DRIVE_SCOPE])
        service = build_drive_service(creds)
        response = service.about().get(fields="user(emailAddress)").execute()
        email = response.get("user", {}).get("emailAddress", "unknown")
    except Exception as exc:
        _log.warning("check_drive_round_trip: drive api call failed", exc_info=True)
        return Row(
            section=tr("cli.doctor.sections.drive_round_trip"),
            required=required,
            state=State.MISSING if required else State.WARN,
            detail=(
                tr("cli.doctor.details.drive_scope_check_failed")
                if required
                else tr("cli.doctor.details.api_call_failed", exc_name=exc.__class__.__name__, exc_msg=str(exc)[:120])
            ),
        )
    return Row(section=tr("cli.doctor.sections.drive_round_trip"), required=required, state=State.OK, detail=email)


def check_sheets_round_trip(settings: Settings) -> Row:
    """Call ``spreadsheets.get`` against the scratch sheet, if any."""
    if not settings.aeat_scratch_sheet_id:
        return Row(
            section=tr("cli.doctor.sections.sheets_round_trip"),
            required=False,
            state=State.SKIP,
            detail=tr("cli.doctor.details.no_scratch_sheet"),
        )
    try:
        creds = get_credentials_for_scopes([SHEETS_SCOPE])
        service = build_sheets_service(creds)
        response = service.spreadsheets().get(spreadsheetId=settings.aeat_scratch_sheet_id).execute()
        title = response.get("properties", {}).get("title", "unknown")
    except Exception as exc:
        _log.warning("check_sheets_round_trip: sheets api call failed", exc_info=True)
        return Row(
            section=tr("cli.doctor.sections.sheets_round_trip"),
            required=False,
            state=State.WARN,
            detail=tr("cli.doctor.details.api_call_failed", exc_name=exc.__class__.__name__, exc_msg=str(exc)[:120]),
        )
    return Row(section=tr("cli.doctor.sections.sheets_round_trip"), required=False, state=State.OK, detail=title)


def check_docs_round_trip(settings: Settings) -> Row:
    """Call ``documents.get`` against the scratch doc, if any."""
    if not settings.aeat_scratch_doc_id:
        return Row(
            section=tr("cli.doctor.sections.docs_round_trip"),
            required=False,
            state=State.SKIP,
            detail=tr("cli.doctor.details.no_scratch_doc"),
        )
    try:
        creds = get_credentials_for_scopes([DOCS_SCOPE])
        service = build_docs_service(creds)
        response = service.documents().get(documentId=settings.aeat_scratch_doc_id).execute()
        title = response.get("title", "unknown")
    except Exception as exc:
        _log.warning("check_docs_round_trip: docs api call failed", exc_info=True)
        return Row(
            section=tr("cli.doctor.sections.docs_round_trip"),
            required=False,
            state=State.WARN,
            detail=tr("cli.doctor.details.api_call_failed", exc_name=exc.__class__.__name__, exc_msg=str(exc)[:120]),
        )
    return Row(section=tr("cli.doctor.sections.docs_round_trip"), required=False, state=State.OK, detail=title)


def check_cloud_storage(settings: Settings) -> Row:
    """List Cloud Storage buckets in the project (advisory; needs billing)."""
    if not settings.google_cloud_project:
        return Row(
            section=tr("cli.doctor.sections.storage_list"),
            required=False,
            state=State.SKIP,
            detail=tr("cli.doctor.details.gcp_project_not_set"),
        )
    try:
        creds = get_credentials_for_scopes([CLOUD_PLATFORM_SCOPE])
        client = build_storage_client(creds, settings.google_cloud_project)
        count = sum(1 for _ in client.list_buckets(max_results=5))
    except Exception as exc:
        _log.warning("check_cloud_storage: storage api call failed", exc_info=True)
        return Row(
            section=tr("cli.doctor.sections.storage_list"),
            required=False,
            state=State.SKIP,
            detail=tr("cli.doctor.details.api_call_failed", exc_name=exc.__class__.__name__, exc_msg=str(exc)[:120]),
        )
    return Row(
        section=tr("cli.doctor.sections.storage_list"),
        required=False,
        state=State.OK,
        detail=tr("cli.doctor.details.buckets_visible", count=count),
    )


def check_cloud_functions(settings: Settings) -> Row:
    """List Cloud Functions in the project (advisory; needs billing)."""
    if not settings.google_cloud_project:
        return Row(
            section=tr("cli.doctor.sections.functions_list"),
            required=False,
            state=State.SKIP,
            detail=tr("cli.doctor.details.gcp_project_not_set"),
        )
    try:
        creds = get_credentials_for_scopes([CLOUD_PLATFORM_SCOPE])
        client = build_cloudfunctions_client(creds)
        parent = f"projects/{settings.google_cloud_project}/locations/-"
        results = list(client.list_functions(parent=parent))
    except Exception as exc:
        _log.warning("check_cloud_functions: functions api call failed", exc_info=True)
        return Row(
            section=tr("cli.doctor.sections.functions_list"),
            required=False,
            state=State.SKIP,
            detail=tr("cli.doctor.details.api_call_failed", exc_name=exc.__class__.__name__, exc_msg=str(exc)[:120]),
        )
    return Row(
        section=tr("cli.doctor.sections.functions_list"),
        required=False,
        state=State.OK,
        detail=tr("cli.doctor.details.functions_visible", count=len(results)),
    )


def check_cloud_run(settings: Settings) -> Row:
    """List Cloud Run services in the project (advisory; needs billing)."""
    if not settings.google_cloud_project:
        return Row(
            section=tr("cli.doctor.sections.run_list"),
            required=False,
            state=State.SKIP,
            detail=tr("cli.doctor.details.gcp_project_not_set"),
        )
    try:
        creds = get_credentials_for_scopes([CLOUD_PLATFORM_SCOPE])
        client = build_cloudrun_client(creds)
        parent = f"projects/{settings.google_cloud_project}/locations/-"
        results = list(client.list_services(parent=parent))
    except Exception as exc:
        _log.warning("check_cloud_run: cloud run api call failed", exc_info=True)
        return Row(
            section=tr("cli.doctor.sections.run_list"),
            required=False,
            state=State.SKIP,
            detail=tr("cli.doctor.details.api_call_failed", exc_name=exc.__class__.__name__, exc_msg=str(exc)[:120]),
        )
    return Row(
        section=tr("cli.doctor.sections.run_list"),
        required=False,
        state=State.OK,
        detail=tr("cli.doctor.details.services_visible", count=len(results)),
    )


def check_service_account(settings: Settings) -> Row:
    """Advisory check for a configured service account JSON key."""
    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    required = inspection.active_path == GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION
    sa_path = settings.google_application_credentials
    if not sa_path:
        return Row(
            section=tr("cli.doctor.sections.service_account_key_state"),
            required=required,
            state=State.MISSING if required else State.SKIP,
            detail=tr("cli.doctor.details.sa_key_unset")
            if required
            else tr("cli.doctor.details.not_required_active_path"),
        )
    if not Path(sa_path).exists():
        return Row(
            section=tr("cli.doctor.sections.service_account_key_state"),
            required=required,
            state=State.MISSING if required else State.SKIP,
            detail=(
                tr("cli.doctor.details.sa_key_not_found", path=sa_path)
                if required
                else tr("cli.doctor.details.not_required_see_drift")
            ),
        )
    try:
        json.loads(Path(sa_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Row(
            section=tr("cli.doctor.sections.service_account_key_state"),
            required=required,
            state=State.MISSING if required else State.SKIP,
            detail=(
                tr("cli.doctor.details.sa_key_unparseable", exc_name=exc.__class__.__name__)
                if required
                else tr("cli.doctor.details.not_required_see_drift")
            ),
        )
    return Row(
        section=tr("cli.doctor.sections.service_account_key_state"),
        required=required,
        state=State.OK if required else State.SKIP,
        detail=sa_path if required else tr("cli.doctor.details.not_required_see_drift"),
    )


def check_oauth_desktop(settings: Settings) -> Row:
    """Advisory check for an OAuth Desktop client configuration."""
    return check_desktop_oauth_client_material(settings)


def check_certificate_health(settings: Settings) -> Row:
    """Report the AEAT certificate's pre-expiry health.

    Skips cleanly when no certificate is configured. On successful
    evaluation, maps the :class:`CertificateHealthSeverity` buckets to
    doctor states:

    - ``OK`` → :attr:`State.OK`, advisory.
    - ``WARN`` → :attr:`State.WARN`, advisory (not required).
    - ``CRITICAL`` / ``EXPIRED`` → :attr:`State.MISSING`, required →
      the doctor exits non-zero.

    Load failures surface as :attr:`State.WARN` with the exception
    class name so the doctor never aborts mid-table.
    """
    description = AeatAuthenticator(settings).describe()
    if not description.configured:
        return Row(
            section=tr("cli.doctor.sections.aeat_certificate"),
            required=False,
            state=State.SKIP,
            detail=description.health_summary or tr("cli.doctor.details.provider_not_configured"),
        )
    if not description.available:
        return Row(
            section=tr("cli.doctor.sections.aeat_certificate"),
            required=False,
            state=State.WARN,
            detail=description.health_summary or tr("cli.doctor.details.provider_unavailable"),
        )
    days = description.days_until_expiry
    detail = tr("cli.doctor.details.cert_health_detail", severity=description.health_severity, days=days)
    if description.health_severity == "OK":
        return Row(section=tr("cli.doctor.sections.aeat_certificate"), required=False, state=State.OK, detail=detail)
    if description.health_severity == "WARN":
        return Row(section=tr("cli.doctor.sections.aeat_certificate"), required=False, state=State.WARN, detail=detail)
    # CRITICAL or EXPIRED: block the doctor with a required failure.
    return Row(section=tr("cli.doctor.sections.aeat_certificate"), required=True, state=State.MISSING, detail=detail)


def check_auth_provider_path(settings: Settings) -> Row:
    """Explain what the configured auth path means for the operator today."""

    description = AeatAuthenticator(settings).describe()
    if not description.configured:
        state = State.SKIP
    elif not description.available:
        state = State.WARN
    else:
        state = State.OK
    return Row(
        section=tr("cli.doctor.sections.aeat_auth_path"),
        required=False,
        state=state,
        detail=describe_provider_operator_impact(description),
    )


def check_live_tests_flag(settings: Settings) -> Row:
    """Report whether live tests are opted in."""
    return Row(
        section=tr("cli.doctor.sections.live_tests"),
        required=False,
        state=State.OK if settings.aeat_live_tests_enabled else State.SKIP,
        detail=tr("cli.doctor.details.api_enabled")
        if settings.aeat_live_tests_enabled
        else tr("cli.doctor.details.live_tests_disabled"),
    )


def check_live_access_gate(settings: Settings) -> Row:
    """Report the :class:`aeat.adapters.outbound.aeat.auth.AeatAccessGate` env-var state.

    The doctor row surfaces the remaining env vars that gate live AEAT
    reads without ever exposing a secret value. Live AEAT writes are
    permanently forbidden, so the row reports that policy explicitly.
    """
    from ...adapters.outbound.aeat.auth import AeatAccessGate

    snapshot = AeatAccessGate(settings).snapshot_env()
    if snapshot.aeat_live_tests_enabled == "1":
        live_reads = tr("cli.doctor.details.live_reads_enabled")
        state = State.OK
    else:
        live_reads = tr("cli.doctor.details.live_reads_skipped")
        state = State.SKIP
    live_writes = tr("cli.doctor.details.live_writes_forbidden")
    if snapshot.pytest_current_test:
        state = State.WARN
        live_writes += tr("cli.doctor.details.pytest_current_test_present")
    detail = f"{live_reads}; {live_writes}"
    return Row(
        section=tr("cli.doctor.sections.live_access_gate"),
        required=False,
        state=state,
        detail=detail,
    )


# ── Security-layer rows ─────────────────────────────────────────────────────


def check_secret_store_directory(settings: Settings) -> Row:
    """Verify the secret-store directory exists and is operator-writable."""
    secret_dir = settings.aeat_secret_store_dir
    if not secret_dir.exists():
        return Row(
            section=tr("cli.doctor.sections.secret_store_dir"),
            required=False,
            state=State.MISSING,
            detail=tr("cli.doctor.details.secret_store_dir_missing", dir=secret_dir),
        )
    if not os.access(secret_dir, os.W_OK):
        return Row(
            section=tr("cli.doctor.sections.secret_store_dir"),
            required=True,
            state=State.PARTIAL,
            detail=tr("cli.doctor.details.secret_store_dir_not_writable", dir=secret_dir),
        )
    return Row(
        section=tr("cli.doctor.sections.secret_store_dir"),
        required=True,
        state=State.OK,
        detail=f"{secret_dir}",
    )


def check_secret_store_backend(settings: Settings) -> Row:
    """Report which backend is active and warn loudly on the unsecured path."""
    backend = settings.aeat_secret_store_backend
    if backend.value == "unsecured":
        if not settings.aeat_allow_unencrypted:
            return Row(
                section=tr("cli.doctor.sections.secret_store_backend"),
                required=True,
                state=State.MISSING,
                detail=tr("cli.doctor.details.unsecured_requires_allow"),
            )
        return Row(
            section=tr("cli.doctor.sections.secret_store_backend"),
            required=False,
            state=State.WARN,
            detail=tr("cli.doctor.details.unsecured_warning"),
        )
    return Row(
        section=tr("cli.doctor.sections.secret_store_backend"),
        required=True,
        state=State.OK,
        detail=tr("cli.doctor.details.backend_active", backend=backend.value),
    )


def check_master_key_readiness(settings: Settings) -> Row:
    """Verify a master key is reachable under the active backend."""
    secret_dir = settings.aeat_secret_store_dir
    backend = settings.aeat_secret_store_backend.value
    if backend == "unsecured":
        # The unsecured backend's published key is always available; the
        # warning row above covers the security implication.
        return Row(
            section=tr("cli.doctor.sections.master_key_readiness"),
            required=False,
            state=State.SKIP,
            detail=tr("cli.doctor.details.master_key_unsecured"),
        )
    if backend in ("file", "auto"):
        master_key = secret_dir / "master.key"
        master_kdf = secret_dir / "master.kdf"
        salt = secret_dir / "salt"
        present = [p for p in (master_key, master_kdf, salt) if p.exists()]
        missing = [p for p in (master_key, master_kdf, salt) if not p.exists()]
        if not present:
            # Missing file-fallback artefacts are benign for 'auto' when
            # the OS keychain is reachable; for 'file' the substrate has
            # not been provisioned.
            if backend == "file":
                return Row(
                    section=tr("cli.doctor.sections.master_key_readiness"),
                    required=True,
                    state=State.MISSING,
                    detail=tr("cli.doctor.details.master_key_missing", dir=secret_dir),
                )
            return Row(
                section=tr("cli.doctor.sections.master_key_readiness"),
                required=False,
                state=State.SKIP,
                detail=tr("cli.doctor.details.master_key_keychain_preferred"),
            )
        if missing:
            return Row(
                section=tr("cli.doctor.sections.master_key_readiness"),
                required=True,
                state=State.PARTIAL,
                detail=tr(
                    "cli.doctor.details.master_key_partial",
                    present=[p.name for p in present],
                    missing=[p.name for p in missing],
                ),
            )
        return Row(
            section=tr("cli.doctor.sections.master_key_readiness"),
            required=True,
            state=State.OK,
            detail=tr("cli.doctor.details.master_key_file_present", dir=secret_dir),
        )
    # Backend is 'keyring'.
    return Row(
        section=tr("cli.doctor.sections.master_key_readiness"),
        required=True,
        state=State.OK,
        detail=tr("cli.doctor.details.master_key_keyring"),
    )


def check_kdf_version(settings: Settings) -> Row:
    """Verify the on-disk KDF parameters file is at the active version."""
    kdf_path = settings.aeat_secret_store_dir / "master.kdf"
    if not kdf_path.exists():
        return Row(
            section=tr("cli.doctor.sections.kdf_version"),
            required=False,
            state=State.SKIP,
            detail=tr("cli.doctor.details.master_kdf_absent"),
        )
    try:
        raw = json.loads(kdf_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return Row(
            section=tr("cli.doctor.sections.kdf_version"),
            required=True,
            state=State.PARTIAL,
            detail=tr("cli.doctor.details.master_kdf_parse_failed", name=kdf_path.name, exc=exc),
        )
    if not isinstance(raw, dict):
        return Row(
            section=tr("cli.doctor.sections.kdf_version"),
            required=True,
            state=State.PARTIAL,
            detail=tr("cli.doctor.details.master_kdf_not_object", name=kdf_path.name),
        )
    version = raw.get("version")
    if version == 2:
        return Row(
            section=tr("cli.doctor.sections.kdf_version"),
            required=True,
            state=State.OK,
            detail=tr("cli.doctor.details.master_kdf_argon2id", version=version),
        )
    if version == 1:
        return Row(
            section=tr("cli.doctor.sections.kdf_version"),
            required=True,
            state=State.PARTIAL,
            detail=tr("cli.doctor.details.master_kdf_unsupported", version=version),
        )
    return Row(
        section=tr("cli.doctor.sections.kdf_version"),
        required=True,
        state=State.PARTIAL,
        detail=tr("cli.doctor.details.master_kdf_unrecognised", version=version),
    )


# ── Orchestrator ────────────────────────────────────────────────────────────


def collect_rows(settings: Settings) -> list[Row]:
    """Run every check in order and return the full list of rows."""
    rows: list[Row] = []
    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    rows.append(check_env_file(settings))
    rows.append(check_google_cloud_project(settings))
    rows.append(check_active_google_auth_path(settings))
    rows.append(check_google_auth_readiness(settings))
    rows.append(check_desktop_oauth_client_material(settings))
    rows.append(check_cli_oauth_cache(settings))
    rows.append(check_mcp_credentials_cache(settings))
    rows.append(check_adc_file(settings))
    rows.append(check_adc_scopes(settings))
    rows.append(check_service_account(settings))
    rows.append(check_inactive_google_auth_drift(settings))
    if inspection.adc_exists or inspection.desktop_oauth_json_path is not None:
        rows.append(check_gcloud_binary())
        if gcloud_binary_path():
            rows.append(check_gcloud_account())
            rows.append(check_gcloud_project_matches(settings))
    if inspection.cli_ready:
        rows.extend(check_api_enablement(settings))
        rows.append(check_drive_round_trip())
        rows.append(check_sheets_round_trip(settings))
        rows.append(check_docs_round_trip(settings))
        rows.append(check_cloud_storage(settings))
        rows.append(check_cloud_functions(settings))
        rows.append(check_cloud_run(settings))
    rows.append(check_certificate_health(settings))
    rows.append(check_auth_provider_path(settings))
    rows.append(check_live_tests_flag(settings))
    rows.append(check_live_access_gate(settings))
    # Security-layer rows: secret-store dir health, active backend,
    # master-key readiness, KDF version. Provisioning state is a hard
    # prerequisite for every persisting CLI command, so these rows
    # surface gaps before the operator hits an opaque
    # MasterKeyMaterialMissingError downstream.
    rows.append(check_secret_store_directory(settings))
    rows.append(check_secret_store_backend(settings))
    rows.append(check_master_key_readiness(settings))
    rows.append(check_kdf_version(settings))
    return rows


def render_table(rows: list[Row]) -> Table:
    """Render rows into a rich Table for console output."""
    table = Table(title=tr("cli.doctor.table.title"), show_lines=False, header_style="bold")
    table.add_column(tr("cli.doctor.table.section"), style="cyan", no_wrap=True)
    table.add_column(tr("cli.doctor.table.required"), style="white")
    table.add_column(tr("cli.doctor.table.state"), style="bold")
    table.add_column(tr("cli.doctor.table.detail"), style="white", overflow="fold")
    state_styles = {
        State.OK: "green",
        State.MISSING: "red",
        State.PARTIAL: "yellow",
        State.WARN: "yellow",
        State.SKIP: "dim",
    }
    for row in rows:
        table.add_row(
            row.section,
            tr("cli.doctor.table.yes") if row.required else tr("cli.doctor.table.no"),
            f"[{state_styles[row.state]}]{row.state.value}[/]",
            row.detail,
        )
    return table


def doctor() -> None:
    """Print the health table and exit non-zero on any required failure."""
    settings = Settings()
    rows = collect_rows(settings)
    console = Console()
    console.print(render_table(rows))
    failing_required = [r for r in rows if r.required and r.state in (State.MISSING, State.PARTIAL, State.WARN)]
    if failing_required:
        n = len(failing_required)
        console.print("[red]doctor: " + tr("cli.doctor.errors.findings", n=n) + "[/]")
        raise typer.Exit(code=1)
    console.print("[green]doctor: " + tr("cli.doctor.success.all_clean") + "[/]")
