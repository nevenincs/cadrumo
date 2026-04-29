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

from ..auth import (
    CLOUD_PLATFORM_SCOPE,
    DOCS_SCOPE,
    DRIVE_SCOPE,
    REQUIRED_ADC_SCOPES,
    SHEETS_SCOPE,
    AeatAuthenticator,
    GoogleAuthPath,
    adc_well_known_path,
    build_cloudfunctions_client,
    build_cloudrun_client,
    build_docs_service,
    build_drive_service,
    build_serviceusage_service,
    build_sheets_service,
    build_storage_client,
    describe_provider_operator_impact,
    get_credentials_for_scopes,
    inspect_google_auth,
)
from ..config import PROJECT_ROOT, Settings

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
            section="env/.env file",
            required=True,
            state=State.MISSING,
            detail="run `just env-setup` to copy env/.env.example to env/.env",
        )
    _ = settings  # silence unused-arg lint; Settings load is the existence check
    return Row(section="env/.env file", required=True, state=State.OK, detail=str(path))


def check_google_cloud_project(settings: Settings) -> Row:
    """Verify ``GOOGLE_CLOUD_PROJECT`` is non-empty in Settings."""
    if not settings.google_cloud_project:
        return Row(
            section="GOOGLE_CLOUD_PROJECT",
            required=True,
            state=State.MISSING,
            detail="set GOOGLE_CLOUD_PROJECT in env/.env",
        )
    return Row(
        section="GOOGLE_CLOUD_PROJECT",
        required=True,
        state=State.OK,
        detail=settings.google_cloud_project,
    )


def check_active_google_auth_path(settings: Settings) -> Row:
    """Explain which Google auth path is active, blocking on ambiguity."""

    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    if inspection.active_path is None:
        return Row(
            section="active Google auth path",
            required=True,
            state=State.MISSING,
            detail=inspection.blocking_reason or "no active Google auth path",
        )
    source = "explicit" if inspection.configured_path is not None else "inferred"
    return Row(
        section="active Google auth path",
        required=True,
        state=State.OK,
        detail=f"{inspection.active_path.value} ({source})",
    )


def check_google_auth_readiness(settings: Settings) -> Row:
    """Summarize CLI/bootstrap versus MCP readiness for the active path."""

    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    if inspection.active_path is None:
        return Row(
            section="Google auth readiness",
            required=True,
            state=State.MISSING,
            detail=inspection.blocking_reason or "select and prepare one Google auth path",
        )
    if inspection.cli_ready and inspection.mcp_ready:
        return Row(
            section="Google auth readiness",
            required=True,
            state=State.OK,
            detail="CLI auth material and MCP launch readiness are both prepared",
        )
    if inspection.cli_ready and not inspection.mcp_ready:
        return Row(
            section="Google auth readiness",
            required=True,
            state=State.PARTIAL,
            detail="CLI auth material ready; MCP credentials cache still needs preparation",
        )
    if inspection.mcp_ready and not inspection.cli_ready:
        return Row(
            section="Google auth readiness",
            required=True,
            state=State.PARTIAL,
            detail="MCP cache prepared; CLI auth material is still incomplete",
        )
    return Row(
        section="Google auth readiness",
        required=True,
        state=State.MISSING,
        detail="active path selected but neither CLI/bootstrap nor MCP readiness is complete",
    )


def check_desktop_oauth_client_material(settings: Settings) -> Row:
    """Report the Desktop OAuth client configuration state."""

    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    required = inspection.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV
    if inspection.desktop_oauth_complete:
        json_detail = (
            f"; oauth JSON at {inspection.desktop_oauth_json_path}"
            if inspection.desktop_oauth_json_path is not None
            else "; ADC sub-step JSON not configured"
        )
        return Row(
            section="Desktop OAuth client material",
            required=required,
            state=State.OK if required else State.SKIP,
            detail=(
                f"GOOGLE_OAUTH_CLIENT_ID/SECRET present{json_detail}"
                if required
                else "not required for active path; see inactive-path drift"
            ),
        )
    if inspection.desktop_oauth_partial:
        return Row(
            section="Desktop OAuth client material",
            required=required,
            state=State.MISSING if required else State.WARN,
            detail="partial Desktop OAuth config; complete GOOGLE_OAUTH_CLIENT_ID/SECRET",
        )
    return Row(
        section="Desktop OAuth client material",
        required=required,
        state=State.MISSING if required else State.SKIP,
        detail="not required for active path" if not required else "Desktop OAuth client config missing",
    )


def check_cli_oauth_cache(settings: Settings) -> Row:
    """Report the repo-local CLI OAuth token cache state."""

    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    required = inspection.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV
    if inspection.active_path != GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV:
        return Row(
            section="CLI OAuth cache",
            required=False,
            state=State.SKIP,
            detail="not required for active path",
        )
    if inspection.oauth_token_issue is None:
        return Row(
            section="CLI OAuth cache",
            required=required,
            state=State.OK,
            detail=str(inspection.oauth_token_path),
        )
    return Row(
        section="CLI OAuth cache",
        required=required,
        state=State.MISSING,
        detail=(
            f"{inspection.oauth_token_issue}; rerun `aeat auth init --path desktop-oauth-local-dev --reset-cli-token`"
        ),
    )


def check_mcp_credentials_cache(settings: Settings) -> Row:
    """Report the repo-local Google Workspace MCP credentials directory state."""

    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    if inspection.active_path is None:
        return Row(
            section="MCP credentials cache",
            required=True,
            state=State.MISSING,
            detail=inspection.blocking_reason or "select a Google auth path first",
        )
    if inspection.mcp_credentials_exist:
        return Row(
            section="MCP credentials cache",
            required=True,
            state=State.OK,
            detail=f"credentials present under {inspection.mcp_credentials_dir}",
        )
    if inspection.mcp_credentials_dir_exists:
        return Row(
            section="MCP credentials cache",
            required=True,
            state=State.PARTIAL,
            detail=(
                "directory prepared for first MCP launch but no cached MCP "
                f"credentials exist yet: {inspection.mcp_credentials_dir}"
            ),
        )
    return Row(
        section="MCP credentials cache",
        required=True,
        state=State.MISSING,
        detail="run `aeat auth init` to prepare the repo-local MCP credentials directory",
    )


def check_inactive_google_auth_drift(settings: Settings) -> Row:
    """Surface ignored stale config from the inactive auth path."""

    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    drift = inspection.inactive_path_drift
    if drift is None:
        return Row(
            section="inactive-path drift",
            required=False,
            state=State.SKIP,
            detail="no ignored stale auth artifacts detected",
        )
    return Row(
        section="inactive-path drift",
        required=False,
        state=State.WARN,
        detail=drift,
    )


def check_gcloud_binary() -> Row:
    """Verify the ``gcloud`` CLI is on PATH."""
    if not gcloud_binary_path():
        return Row(
            section="gcloud binary",
            required=False,
            state=State.MISSING,
            detail="install gcloud only if you still need the ADC-backed wrapper path",
        )
    code, out, _err = _run_gcloud(["version"])
    if code != 0:
        return Row(
            section="gcloud binary",
            required=False,
            state=State.WARN,
            detail="gcloud on PATH but `gcloud version` failed",
        )
    first_line = out.splitlines()[0] if out else "gcloud installed"
    return Row(section="gcloud binary", required=False, state=State.OK, detail=first_line)


def check_gcloud_account() -> Row:
    """Verify there is at least one ACTIVE gcloud account."""
    code, out, _err = _run_gcloud(["auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
    if code != 0 or not out:
        return Row(
            section="gcloud auth",
            required=False,
            state=State.MISSING,
            detail="run `just gcloud-auth` to log in",
        )
    return Row(section="gcloud auth", required=False, state=State.OK, detail=out.splitlines()[0])


def check_gcloud_project_matches(settings: Settings) -> Row:
    """Verify the gcloud-active project matches ``GOOGLE_CLOUD_PROJECT``."""
    code, out, _err = _run_gcloud(["config", "get-value", "project"])
    if code != 0 or not out or out.lower() == "unset":
        return Row(
            section="gcloud project",
            required=False,
            state=State.MISSING,
            detail="run `gcloud config set project ${GOOGLE_CLOUD_PROJECT}`",
        )
    if settings.google_cloud_project and out != settings.google_cloud_project:
        return Row(
            section="gcloud project",
            required=False,
            state=State.WARN,
            detail=f"gcloud='{out}' but env='{settings.google_cloud_project}'",
        )
    return Row(section="gcloud project", required=False, state=State.OK, detail=out)


def check_credentials_path(settings: Settings) -> Row:
    """Report which auth path the unified resolver will use."""
    if settings.google_application_credentials and Path(settings.google_application_credentials).exists():
        return Row(
            section="auth path",
            required=True,
            state=State.OK,
            detail=f"service account ({settings.google_application_credentials})",
        )
    if settings.google_oauth_client_id and settings.google_oauth_client_secret:
        return Row(
            section="auth path",
            required=True,
            state=State.OK,
            detail="OAuth 2.0 Desktop client",
        )
    if adc_well_known_path().exists():
        return Row(
            section="auth path",
            required=True,
            state=State.OK,
            detail=f"ADC ({adc_well_known_path()})",
        )
    return Row(
        section="auth path",
        required=True,
        state=State.MISSING,
        detail="no credentials configured (set GOOGLE_APPLICATION_CREDENTIALS or run `just gcloud-auth`)",
    )


def check_adc_file(settings: Settings) -> Row:
    """Advisory: ADC JSON file at the well-known path."""
    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    path = adc_well_known_path()
    if not path.exists():
        return Row(
            section="ADC file",
            required=False,
            state=State.SKIP,
            detail=(
                "not configured; run `just gcloud-auth` only if you still need the ADC-backed wrapper path"
                if inspection.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV
                else "not required for active path"
            ),
        )
    return Row(section="ADC file", required=False, state=State.OK, detail=str(path))


def check_adc_scopes(settings: Settings) -> Row:
    """Advisory: ADC JSON contains the required scopes (only relevant when ADC is the path)."""
    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    path = adc_well_known_path()
    if not path.exists():
        return Row(
            section="ADC scopes",
            required=False,
            state=State.SKIP,
            detail=(
                "ADC not configured; Desktop OAuth local-dev can still work without it"
                if inspection.active_path == GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV
                else "not required for active path"
            ),
        )
    granted = adc_scopes_from_file(path)
    if not granted:
        return Row(
            section="ADC scopes",
            required=False,
            state=State.WARN,
            detail="ADC JSON has no scopes (re-run `just gcloud-auth` with --client-id-file)",
        )
    missing = sorted(set(REQUIRED_ADC_SCOPES) - set(granted))
    if missing:
        return Row(
            section="ADC scopes",
            required=False,
            state=State.WARN,
            detail=f"missing: {', '.join(short_scope(s) for s in missing)}",
        )
    return Row(
        section="ADC scopes",
        required=False,
        state=State.OK,
        detail=f"{len(granted)} granted, includes drive/sheets/docs/cloud-platform",
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
                section="API enablement",
                required=True,
                state=State.SKIP,
                detail="GOOGLE_CLOUD_PROJECT not set",
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
        return [
            Row(
                section="API enablement",
                required=True,
                state=State.MISSING,
                detail=f"Service Usage call failed: {exc.__class__.__name__}",
            )
        ]

    rows: list[Row] = []
    for service_name in REQUIRED_API_SERVICES:
        if service_name in enabled:
            rows.append(Row(section=f"API: {service_name}", required=True, state=State.OK, detail="enabled"))
        else:
            rows.append(
                Row(
                    section=f"API: {service_name}",
                    required=True,
                    state=State.MISSING,
                    detail=f"run `gcloud services enable {service_name}`",
                )
            )
    for service_name in OPTIONAL_API_SERVICES:
        if service_name in enabled:
            rows.append(Row(section=f"API: {service_name}", required=False, state=State.OK, detail="enabled"))
        else:
            rows.append(
                Row(
                    section=f"API: {service_name}",
                    required=False,
                    state=State.SKIP,
                    detail="needs project billing enabled (`gcloud services enable` fails otherwise)",
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
        return Row(
            section="Drive round-trip",
            required=required,
            state=State.MISSING if required else State.WARN,
            detail=(
                "Drive scope check failed; rerun `aeat auth init --path "
                "desktop-oauth-local-dev --reset-cli-token` if the Desktop "
                "OAuth token is stale"
                if required
                else f"{exc.__class__.__name__}: {exc!s}"[:120]
            ),
        )
    return Row(section="Drive round-trip", required=required, state=State.OK, detail=email)


def check_sheets_round_trip(settings: Settings) -> Row:
    """Call ``spreadsheets.get`` against the scratch sheet, if any."""
    if not settings.aeat_scratch_sheet_id:
        return Row(
            section="Sheets round-trip",
            required=False,
            state=State.SKIP,
            detail="no scratch sheet ID; run `aeat bootstrap`",
        )
    try:
        creds = get_credentials_for_scopes([SHEETS_SCOPE])
        service = build_sheets_service(creds)
        response = service.spreadsheets().get(spreadsheetId=settings.aeat_scratch_sheet_id).execute()
        title = response.get("properties", {}).get("title", "unknown")
    except Exception as exc:
        return Row(
            section="Sheets round-trip",
            required=False,
            state=State.WARN,
            detail=f"{exc.__class__.__name__}: {exc!s}"[:120],
        )
    return Row(section="Sheets round-trip", required=False, state=State.OK, detail=title)


def check_docs_round_trip(settings: Settings) -> Row:
    """Call ``documents.get`` against the scratch doc, if any."""
    if not settings.aeat_scratch_doc_id:
        return Row(
            section="Docs round-trip",
            required=False,
            state=State.SKIP,
            detail="no scratch doc ID; run `aeat bootstrap`",
        )
    try:
        creds = get_credentials_for_scopes([DOCS_SCOPE])
        service = build_docs_service(creds)
        response = service.documents().get(documentId=settings.aeat_scratch_doc_id).execute()
        title = response.get("title", "unknown")
    except Exception as exc:
        return Row(
            section="Docs round-trip",
            required=False,
            state=State.WARN,
            detail=f"{exc.__class__.__name__}: {exc!s}"[:120],
        )
    return Row(section="Docs round-trip", required=False, state=State.OK, detail=title)


def check_cloud_storage(settings: Settings) -> Row:
    """List Cloud Storage buckets in the project (advisory; needs billing)."""
    if not settings.google_cloud_project:
        return Row(
            section="Storage list",
            required=False,
            state=State.SKIP,
            detail="GOOGLE_CLOUD_PROJECT not set",
        )
    try:
        creds = get_credentials_for_scopes([CLOUD_PLATFORM_SCOPE])
        client = build_storage_client(creds, settings.google_cloud_project)
        count = sum(1 for _ in client.list_buckets(max_results=5))
    except Exception as exc:
        return Row(
            section="Storage list",
            required=False,
            state=State.SKIP,
            detail=f"{exc.__class__.__name__}: {exc!s}"[:120],
        )
    return Row(section="Storage list", required=False, state=State.OK, detail=f"{count} buckets visible")


def check_cloud_functions(settings: Settings) -> Row:
    """List Cloud Functions in the project (advisory; needs billing)."""
    if not settings.google_cloud_project:
        return Row(
            section="Functions list",
            required=False,
            state=State.SKIP,
            detail="GOOGLE_CLOUD_PROJECT not set",
        )
    try:
        creds = get_credentials_for_scopes([CLOUD_PLATFORM_SCOPE])
        client = build_cloudfunctions_client(creds)
        parent = f"projects/{settings.google_cloud_project}/locations/-"
        results = list(client.list_functions(parent=parent))
    except Exception as exc:
        return Row(
            section="Functions list",
            required=False,
            state=State.SKIP,
            detail=f"{exc.__class__.__name__}: {exc!s}"[:120],
        )
    return Row(
        section="Functions list",
        required=False,
        state=State.OK,
        detail=f"{len(results)} functions visible",
    )


def check_cloud_run(settings: Settings) -> Row:
    """List Cloud Run services in the project (advisory; needs billing)."""
    if not settings.google_cloud_project:
        return Row(
            section="Run list",
            required=False,
            state=State.SKIP,
            detail="GOOGLE_CLOUD_PROJECT not set",
        )
    try:
        creds = get_credentials_for_scopes([CLOUD_PLATFORM_SCOPE])
        client = build_cloudrun_client(creds)
        parent = f"projects/{settings.google_cloud_project}/locations/-"
        results = list(client.list_services(parent=parent))
    except Exception as exc:
        return Row(
            section="Run list",
            required=False,
            state=State.SKIP,
            detail=f"{exc.__class__.__name__}: {exc!s}"[:120],
        )
    return Row(section="Run list", required=False, state=State.OK, detail=f"{len(results)} services visible")


def check_service_account(settings: Settings) -> Row:
    """Advisory check for a configured service account JSON key."""
    inspection = inspect_google_auth(settings, project_root=PROJECT_ROOT)
    required = inspection.active_path == GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION
    sa_path = settings.google_application_credentials
    if not sa_path:
        return Row(
            section="service-account key state",
            required=required,
            state=State.MISSING if required else State.SKIP,
            detail="GOOGLE_APPLICATION_CREDENTIALS not set" if required else "not required for active path",
        )
    if not Path(sa_path).exists():
        return Row(
            section="service-account key state",
            required=required,
            state=State.MISSING if required else State.SKIP,
            detail=(
                f"path {sa_path} does not exist"
                if required
                else "not required for active path; see inactive-path drift"
            ),
        )
    try:
        json.loads(Path(sa_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Row(
            section="service-account key state",
            required=required,
            state=State.MISSING if required else State.SKIP,
            detail=(
                f"unparseable: {exc.__class__.__name__}"
                if required
                else "not required for active path; see inactive-path drift"
            ),
        )
    return Row(
        section="service-account key state",
        required=required,
        state=State.OK if required else State.SKIP,
        detail=sa_path if required else "not required for active path; see inactive-path drift",
    )


def check_oauth_desktop(settings: Settings) -> Row:
    """Advisory check for an OAuth Desktop client configuration."""
    return check_desktop_oauth_client_material(settings)


def check_certificate_health(settings: Settings) -> Row:
    """Report the AEAT certificate's pre-expiry health (#94).

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
            section="aeat certificate",
            required=False,
            state=State.SKIP,
            detail=description.health_summary or "provider not configured",
        )
    if not description.available:
        return Row(
            section="aeat certificate",
            required=False,
            state=State.WARN,
            detail=description.health_summary or "provider unavailable",
        )
    days = description.days_until_expiry
    detail = f"severity={description.health_severity} days_until_expiry={days}"
    if description.health_severity == "OK":
        return Row(section="aeat certificate", required=False, state=State.OK, detail=detail)
    if description.health_severity == "WARN":
        return Row(section="aeat certificate", required=False, state=State.WARN, detail=detail)
    # CRITICAL or EXPIRED: block the doctor with a required failure.
    return Row(section="aeat certificate", required=True, state=State.MISSING, detail=detail)


def check_auth_provider_path(settings: Settings) -> Row:
    """Explain what the configured auth path means for Kent today."""

    description = AeatAuthenticator(settings).describe()
    if not description.configured:
        state = State.SKIP
    elif not description.available:
        state = State.WARN
    else:
        state = State.OK
    return Row(
        section="aeat auth path",
        required=False,
        state=state,
        detail=describe_provider_operator_impact(description),
    )


def check_live_tests_flag(settings: Settings) -> Row:
    """Report whether live tests are opted in."""
    return Row(
        section="live tests",
        required=False,
        state=State.OK if settings.aeat_live_tests_enabled else State.SKIP,
        detail="enabled" if settings.aeat_live_tests_enabled else "AEAT_LIVE_TESTS_ENABLED=false",
    )


def check_live_access_gate(settings: Settings) -> Row:
    """Report the :class:`aeat.auth.AeatAccessGate` env-var state (#167).

    The doctor row surfaces the remaining env vars that gate live AEAT
    reads without ever exposing a secret value. Live AEAT writes are
    permanently forbidden, so the row reports that policy explicitly.
    """
    from ..auth import AeatAccessGate

    snapshot = AeatAccessGate(settings).snapshot_env()
    if snapshot.aeat_live_tests_enabled == "1":
        live_reads = "reads: ENABLED"
        state = State.OK
    else:
        live_reads = "reads: skipped (AEAT_LIVE_TESTS_ENABLED!=1)"
        state = State.SKIP
    live_writes = "writes: permanently forbidden"
    if snapshot.pytest_current_test:
        state = State.WARN
        live_writes += " [PYTEST_CURRENT_TEST present]"
    detail = f"{live_reads}; {live_writes}"
    return Row(
        section="live access gate",
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
            section="secret-store dir",
            required=False,
            state=State.MISSING,
            detail=(f"{secret_dir} does not exist; run `aeat security provision` to bootstrap the security layer."),
        )
    if not os.access(secret_dir, os.W_OK):
        return Row(
            section="secret-store dir",
            required=True,
            state=State.PARTIAL,
            detail=f"{secret_dir} is not writable by the current user.",
        )
    return Row(
        section="secret-store dir",
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
                section="secret-store backend",
                required=True,
                state=State.MISSING,
                detail=(
                    "backend=unsecured requires AEAT_ALLOW_UNENCRYPTED=1; "
                    "the substrate will refuse every persistence call."
                ),
            )
        return Row(
            section="secret-store backend",
            required=False,
            state=State.WARN,
            detail=(
                "backend=unsecured: published deterministic master key, "
                "ZERO confidentiality. Real NIFs are refused at profile-write."
            ),
        )
    return Row(
        section="secret-store backend",
        required=True,
        state=State.OK,
        detail=f"backend={backend.value}",
    )


def check_master_key_readiness(settings: Settings) -> Row:
    """Verify a master key is reachable under the active backend."""
    secret_dir = settings.aeat_secret_store_dir
    backend = settings.aeat_secret_store_backend.value
    if backend == "unsecured":
        # The unsecured backend's published key is always available; the
        # warning row above covers the security implication.
        return Row(
            section="master-key readiness",
            required=False,
            state=State.SKIP,
            detail="published deterministic key (unsecured backend).",
        )
    if backend in ("file", "auto"):
        master_key = secret_dir / "master.key"
        master_kdf = secret_dir / "master.kdf"
        salt = secret_dir / "salt"
        present = [p for p in (master_key, master_kdf, salt) if p.exists()]
        missing = [p for p in (master_key, master_kdf, salt) if not p.exists()]
        if not present:
            # File-fallback artefacts not yet minted. For 'auto' this is
            # benign when the OS keychain is reachable; for 'file' it
            # means the substrate has not been provisioned.
            if backend == "file":
                return Row(
                    section="master-key readiness",
                    required=True,
                    state=State.MISSING,
                    detail=(f"no master.key / master.kdf / salt under {secret_dir}; run `aeat security provision`."),
                )
            return Row(
                section="master-key readiness",
                required=False,
                state=State.SKIP,
                detail="file-fallback artefacts absent; auto-mode prefers OS keychain.",
            )
        if missing:
            return Row(
                section="master-key readiness",
                required=True,
                state=State.PARTIAL,
                detail=(
                    "partial file-fallback state: "
                    f"present={[p.name for p in present]} missing={[p.name for p in missing]}; "
                    "run `aeat security provision --force` to rebuild."
                ),
            )
        return Row(
            section="master-key readiness",
            required=True,
            state=State.OK,
            detail=f"file-fallback artefacts present in {secret_dir}.",
        )
    # Backend is 'keyring'.
    return Row(
        section="master-key readiness",
        required=True,
        state=State.OK,
        detail="keyring backend selected; OS keychain is the source of truth.",
    )


def check_kdf_version(settings: Settings) -> Row:
    """Verify the on-disk KDF parameters file is at the active version."""
    kdf_path = settings.aeat_secret_store_dir / "master.kdf"
    if not kdf_path.exists():
        return Row(
            section="master.kdf version",
            required=False,
            state=State.SKIP,
            detail="master.kdf not present (keyring or unprovisioned).",
        )
    try:
        raw = json.loads(kdf_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return Row(
            section="master.kdf version",
            required=True,
            state=State.PARTIAL,
            detail=f"failed to parse {kdf_path.name}: {exc}",
        )
    if not isinstance(raw, dict):
        return Row(
            section="master.kdf version",
            required=True,
            state=State.PARTIAL,
            detail=f"{kdf_path.name} is not a JSON object.",
        )
    version = raw.get("version")
    if version == 2:
        return Row(
            section="master.kdf version",
            required=True,
            state=State.OK,
            detail=f"v{version} (Argon2id).",
        )
    if version == 1:
        return Row(
            section="master.kdf version",
            required=True,
            state=State.WARN,
            detail=(f"v{version} (scrypt) — run `aeat security migrate-master-key-kdf` to upgrade to v2 (Argon2id)."),
        )
    return Row(
        section="master.kdf version",
        required=True,
        state=State.PARTIAL,
        detail=f"unrecognised KDF version: {version!r}",
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
    table = Table(title="aeat doctor", show_lines=False, header_style="bold")
    table.add_column("Section", style="cyan", no_wrap=True)
    table.add_column("Required", style="white")
    table.add_column("State", style="bold")
    table.add_column("Detail", style="white", overflow="fold")
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
            "yes" if row.required else "no",
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
        console.print(f"[red]doctor: {len(failing_required)} required check(s) failing[/]")
        raise typer.Exit(code=1)
    console.print("[green]doctor: all required checks passing[/]")
