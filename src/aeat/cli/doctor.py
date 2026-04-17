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
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from aeat.auth import (
    CLOUD_PLATFORM_SCOPE,
    DOCS_SCOPE,
    DRIVE_SCOPE,
    REQUIRED_ADC_SCOPES,
    SHEETS_SCOPE,
    CertificateError,
    CertificateHealthSeverity,
    build_cloudfunctions_client,
    build_cloudrun_client,
    build_docs_service,
    build_drive_service,
    build_serviceusage_service,
    build_sheets_service,
    build_storage_client,
    get_credentials_for_scopes,
)
from aeat.auth import health as certificate_health
from aeat.config import PROJECT_ROOT, Settings

# ── Row primitives ──────────────────────────────────────────────────────────


class State(StrEnum):
    """The verdict for a single doctor row."""

    OK = "OK"
    MISSING = "MISSING"
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


def adc_well_known_path() -> Path:
    """Return the well-known path where gcloud writes ADC JSON.

    Honours ``CLOUDSDK_CONFIG`` if set, otherwise falls back to the
    documented per-platform default. Used by both the doctor and any
    future test that needs to inspect ADC state without performing an
    auth flow.
    """
    override = os.environ.get("CLOUDSDK_CONFIG")
    if override:
        return Path(override) / "application_default_credentials.json"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "gcloud" / "application_default_credentials.json"
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


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


def check_gcloud_binary() -> Row:
    """Verify the ``gcloud`` CLI is on PATH."""
    if not gcloud_binary_path():
        return Row(
            section="gcloud binary",
            required=True,
            state=State.MISSING,
            detail="run `just gcloud-install` to install Google Cloud CLI",
        )
    code, out, _err = _run_gcloud(["version"])
    if code != 0:
        return Row(
            section="gcloud binary",
            required=True,
            state=State.WARN,
            detail="gcloud on PATH but `gcloud version` failed",
        )
    first_line = out.splitlines()[0] if out else "gcloud installed"
    return Row(section="gcloud binary", required=True, state=State.OK, detail=first_line)


def check_gcloud_account() -> Row:
    """Verify there is at least one ACTIVE gcloud account."""
    code, out, _err = _run_gcloud(["auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
    if code != 0 or not out:
        return Row(
            section="gcloud auth",
            required=True,
            state=State.MISSING,
            detail="run `just gcloud-auth` to log in",
        )
    return Row(section="gcloud auth", required=True, state=State.OK, detail=out.splitlines()[0])


def check_gcloud_project_matches(settings: Settings) -> Row:
    """Verify the gcloud-active project matches ``GOOGLE_CLOUD_PROJECT``."""
    code, out, _err = _run_gcloud(["config", "get-value", "project"])
    if code != 0 or not out or out.lower() == "unset":
        return Row(
            section="gcloud project",
            required=True,
            state=State.MISSING,
            detail="run `gcloud config set project ${GOOGLE_CLOUD_PROJECT}`",
        )
    if settings.google_cloud_project and out != settings.google_cloud_project:
        return Row(
            section="gcloud project",
            required=True,
            state=State.WARN,
            detail=f"gcloud='{out}' but env='{settings.google_cloud_project}'",
        )
    return Row(section="gcloud project", required=True, state=State.OK, detail=out)


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


def check_adc_file() -> Row:
    """Advisory: ADC JSON file at the well-known path."""
    path = adc_well_known_path()
    if not path.exists():
        return Row(
            section="ADC file",
            required=False,
            state=State.SKIP,
            detail="not configured (using SA or OAuth instead)",
        )
    return Row(section="ADC file", required=False, state=State.OK, detail=str(path))


def check_adc_scopes() -> Row:
    """Advisory: ADC JSON contains the required scopes (only relevant when ADC is the path)."""
    path = adc_well_known_path()
    if not path.exists():
        return Row(
            section="ADC scopes",
            required=False,
            state=State.SKIP,
            detail="ADC not in use",
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
    try:
        creds = get_credentials_for_scopes([DRIVE_SCOPE])
        service = build_drive_service(creds)
        response = service.about().get(fields="user(emailAddress)").execute()
        email = response.get("user", {}).get("emailAddress", "unknown")
    except Exception as exc:
        return Row(
            section="Drive round-trip",
            required=False,
            state=State.WARN,
            detail=f"{exc.__class__.__name__}: {exc!s}"[:120],
        )
    return Row(section="Drive round-trip", required=False, state=State.OK, detail=email)


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
    sa_path = settings.google_application_credentials
    if not sa_path:
        return Row(
            section="service account",
            required=False,
            state=State.SKIP,
            detail="GOOGLE_APPLICATION_CREDENTIALS not set",
        )
    if not Path(sa_path).exists():
        return Row(
            section="service account",
            required=False,
            state=State.WARN,
            detail=f"path {sa_path} does not exist",
        )
    try:
        json.loads(Path(sa_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Row(
            section="service account",
            required=False,
            state=State.WARN,
            detail=f"unparseable: {exc.__class__.__name__}",
        )
    return Row(section="service account", required=False, state=State.OK, detail=sa_path)


def check_oauth_desktop(settings: Settings) -> Row:
    """Advisory check for an OAuth Desktop client configuration."""
    if not (settings.google_oauth_client_id and settings.google_oauth_client_secret):
        return Row(
            section="oauth desktop",
            required=False,
            state=State.SKIP,
            detail="GOOGLE_OAUTH_CLIENT_ID/SECRET not set",
        )
    return Row(
        section="oauth desktop",
        required=False,
        state=State.OK,
        detail="client_id and client_secret present",
    )


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
    if settings.aeat_certificate_path is None:
        return Row(
            section="aeat certificate",
            required=False,
            state=State.SKIP,
            detail="AEAT_CERTIFICATE_PATH not set",
        )
    if settings.aeat_certificate_password_secret is None:
        return Row(
            section="aeat certificate",
            required=False,
            state=State.WARN,
            detail="AEAT_CERTIFICATE_PASSWORD_SECRET not set",
        )
    # pydantic-settings loads the passphrase from env/.env into the
    # Settings model but does NOT export it to os.environ, while the
    # cert loader reads it via os.environ.get(). Bridge the gap the
    # same way aeat.auth.test_certificate_live does: export the
    # SecretStr into the process environment for the duration of
    # the health call. Scope is the current CLI process only.
    os.environ["AEAT_CERTIFICATE_PASSWORD_SECRET"] = settings.aeat_certificate_password_secret.get_secret_value()
    try:
        result = certificate_health(
            settings.aeat_certificate_path,
            password_env_var="AEAT_CERTIFICATE_PASSWORD_SECRET",  # noqa: S106 - env var NAME, not a secret
            warn_days=settings.aeat_cert_warn_days,
            critical_days=settings.aeat_cert_critical_days,
            friendly_name=settings.aeat_certificate_friendly_name,
            backend=settings.aeat_certificate_backend,
        )
    except CertificateError as exc:
        return Row(
            section="aeat certificate",
            required=False,
            state=State.WARN,
            detail=f"{exc.__class__.__name__}: {exc!s}"[:120],
        )
    days = result.days_until_expiry
    detail = f"severity={result.severity.value} days_until_expiry={days}"
    if result.severity is CertificateHealthSeverity.OK:
        return Row(section="aeat certificate", required=False, state=State.OK, detail=detail)
    if result.severity is CertificateHealthSeverity.WARN:
        return Row(section="aeat certificate", required=False, state=State.WARN, detail=detail)
    # CRITICAL or EXPIRED: block the doctor with a required failure.
    return Row(section="aeat certificate", required=True, state=State.MISSING, detail=detail)


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

    The doctor row surfaces the three env vars that gate live AEAT
    operations without ever exposing a secret value. It states
    whether live READS are currently enabled (the only operator-
    settable dial for day-to-day live work). Live WRITES gate on
    ``AEAT_LIVE_SUBMIT_ENABLED`` which is **never** expected to be
    persisted, so the row treats the common "not set" case as the
    desired state and only surfaces a diagnostic when the var is
    present.
    """
    from aeat.auth import AeatAccessGate

    snapshot = AeatAccessGate(settings).snapshot_env()
    if snapshot.aeat_live_tests_enabled == "1":
        live_reads = "reads: ENABLED"
        state = State.OK
    else:
        live_reads = "reads: skipped (AEAT_LIVE_TESTS_ENABLED!=1)"
        state = State.SKIP
    if snapshot.aeat_live_submit_enabled:
        live_writes = f"writes: {snapshot.aeat_live_submit_enabled!r} (charter #116 — unset after filing)"
        state = State.WARN
    else:
        live_writes = "writes: unset (charter #116 default)"
    # submit_env + pytest_current_test together is the most dangerous
    # state: a live-write capability inside a test runtime. R5 of the
    # charter refuses the actual call, but the doctor must shout.
    if snapshot.pytest_current_test and snapshot.aeat_live_submit_enabled:
        state = State.MISSING
        live_writes += " [DANGER: PYTEST_CURRENT_TEST + submit both set]"
    elif snapshot.pytest_current_test:
        state = State.WARN
        live_writes += " [PYTEST_CURRENT_TEST present]"
    detail = f"{live_reads}; {live_writes}"
    return Row(
        section="live access gate",
        required=False,
        state=state,
        detail=detail,
    )


# ── Orchestrator ────────────────────────────────────────────────────────────


def collect_rows(settings: Settings) -> list[Row]:
    """Run every check in order and return the full list of rows."""
    rows: list[Row] = []
    rows.append(check_env_file(settings))
    rows.append(check_google_cloud_project(settings))
    rows.append(check_gcloud_binary())
    if gcloud_binary_path():
        rows.append(check_gcloud_account())
        rows.append(check_gcloud_project_matches(settings))
    auth_row = check_credentials_path(settings)
    rows.append(auth_row)
    rows.append(check_adc_file())
    rows.append(check_adc_scopes())
    if auth_row.state == State.OK:
        rows.extend(check_api_enablement(settings))
        rows.append(check_drive_round_trip())
        rows.append(check_sheets_round_trip(settings))
        rows.append(check_docs_round_trip(settings))
        rows.append(check_cloud_storage(settings))
        rows.append(check_cloud_functions(settings))
        rows.append(check_cloud_run(settings))
    rows.append(check_service_account(settings))
    rows.append(check_oauth_desktop(settings))
    rows.append(check_certificate_health(settings))
    rows.append(check_live_tests_flag(settings))
    rows.append(check_live_access_gate(settings))
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
    failing_required = [r for r in rows if r.required and r.state in (State.MISSING, State.WARN)]
    if failing_required:
        console.print(f"[red]doctor: {len(failing_required)} required check(s) failing[/]")
        raise typer.Exit(code=1)
    console.print("[green]doctor: all required checks passing[/]")
