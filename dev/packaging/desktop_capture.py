"""Reusable primitives for the automated Claude Desktop real-client capture.

The operator directive is that the ``claude-desktop-mcpb`` / ``claude-desktop-plugin``
real-client rows are minted by an automated, reproducible harness with a clean
environment every run, not by a manual in-app capture. Claude Desktop is a
Windows MSIX / Store FullTrust Electron app, which shapes every primitive here:

* **Launch requires MSIX activation.** Custom Electron flags
  (``--remote-debugging-port``, ``--user-data-dir``) only reach the app through
  a Store activation (``IApplicationActivationManager::ActivateApplication``).
  That activation is DENIED to an elevated Session-0 non-interactive caller, so
  the launch step MUST run in the operator's (or a CI runner's) non-elevated
  interactive session. :func:`activate_desktop` performs the activation; the
  caller is responsible for being in that session.
* **Single-instance forwarding.** A second Desktop launch while one is already
  running forwards its argv to the primary and exits, so startup-only Chromium
  flags are ignored and no debug port opens. The harness must therefore be the
  PRIMARY instance: :func:`running_desktop_pids` lets the caller assert
  exclusivity before launching.
* **Auth is seedable.** Session auth is the Electron safeStorage ``oauth`` token
  in ``config.json``, DPAPI-bound to the Windows USER (not the user-data dir).
  Copying the curated :data:`AUTH_SEED_PATHS` from a blessed source profile into
  a fresh per-run user-data dir lets the same Windows user decrypt it, so every
  run is clean except the seeded auth — mirroring the ``.credentials.json`` copy
  in :mod:`dev.packaging.smoke_plugin_install`.

The CDP drive itself (:func:`drive_tax_prompt`) is the integration surface and
runs only against a real launched app; the pure logic around it
(seeding, telemetry parsing, retry/fail-closed, leak scanning) is factored into
independently testable functions.
"""

from __future__ import annotations

import http.client
import json
import re
import shutil
import subprocess
import time
import urllib.parse
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Final

from cadrumo.core import scan_directory

from .._paths import UTF_8

_UTF_8: Final[str] = UTF_8
_NUMERIC_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"(?<![0-9A-Za-z])\d(?:[\d., ]*\d)?(?![0-9A-Za-z])")
_POWERSHELL: Final[str] = shutil.which("powershell.exe") or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
_CDP_SCHEME: Final[str] = "http"
_CDP_HOST: Final[str] = "127.0.0.1"
_CDP_PATH: Final[str] = "/json/version"

# The Store AppUserModelId and the running-process signature of Claude Desktop.
# Discovered empirically (Get-AppxPackage Claude): the package family is stable,
# the AppId is ``Claude``, and the FullTrust executable lives under WindowsApps.
DESKTOP_PACKAGE_FAMILY: Final[str] = "Claude_pzs8sxrjxfjjc"
DESKTOP_APP_ID: Final[str] = "Claude"
DESKTOP_AUMID: Final[str] = f"{DESKTOP_PACKAGE_FAMILY}!{DESKTOP_APP_ID}"

# The curated state an isolated per-run user-data dir is seeded with. Every entry
# is DPAPI-user-bound or a session artifact the same Windows user can decrypt; a
# path absent from the source profile is skipped, not an error. Everything NOT
# listed (conversation history, telemetry, caches, GPU state, prior extensions)
# starts empty, which is the "clean environment every run" guarantee. The
# installed MCPB extension under test is provisioned separately (see
# :func:`seed_extension`), never copied wholesale from the source profile.
AUTH_SEED_PATHS: Final[tuple[str, ...]] = (
    "config.json",
    "Local State",
    "Network/Cookies",
    "Network/Cookies-journal",
    "Network/Trust Tokens",
    "Local Storage",
    "Session Storage",
)


class DesktopCaptureError(RuntimeError):
    """A fail-closed refusal from the Desktop capture harness."""


@dataclass(frozen=True)
class DesktopPackage:
    """The installed Claude Desktop Store package the harness drives."""

    aumid: str
    version: str
    executable: Path
    state_dir: Path


def parse_appx_package(document: Mapping[str, Any], *, state_dir: Path) -> DesktopPackage:
    r"""Build a :class:`DesktopPackage` from a ``Get-AppxPackage`` JSON object.

    Split from :func:`discover_desktop_package` so the parse is testable without
    a real Appx query. ``document`` is the object PowerShell emits for the Claude
    package; ``InstallLocation`` plus the manifest's ``app\\Claude.exe`` entry
    point resolve the FullTrust executable.
    """
    version = str(document.get("Version") or "").strip()
    install_location = str(document.get("InstallLocation") or "").strip()
    family = str(document.get("PackageFamilyName") or "").strip()
    if not version or not install_location:
        raise DesktopCaptureError(f"Get-AppxPackage returned an incomplete Claude package record: {document!r}")
    if family and family != DESKTOP_PACKAGE_FAMILY:
        raise DesktopCaptureError(f"unexpected Claude package family {family!r}; expected {DESKTOP_PACKAGE_FAMILY!r}")
    executable = Path(install_location) / "app" / "Claude.exe"
    return DesktopPackage(aumid=DESKTOP_AUMID, version=version, executable=executable, state_dir=state_dir)


def discover_desktop_package(*, state_dir: Path) -> DesktopPackage:
    """Resolve the installed Claude Desktop package via ``Get-AppxPackage``.

    Raises:
        DesktopCaptureError: If PowerShell fails or no Claude package is installed.
    """
    completed = subprocess.run(  # noqa: S603 - fixed PowerShell inventory/process command
        [
            _POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-AppxPackage -Name Claude | Select-Object Version,InstallLocation,PackageFamilyName "
            "| ConvertTo-Json -Compress",
        ],
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="replace",
        check=False,
        timeout=60,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise DesktopCaptureError(f"could not query the Claude Desktop package: {completed.stderr.strip()[:300]}")
    document = json.loads(completed.stdout)
    if isinstance(document, list):  # multiple side-by-side versions: take the highest Version
        document = max(document, key=lambda item: tuple(int(p) for p in str(item.get("Version", "0")).split(".")))
    return parse_appx_package(document, state_dir=state_dir)


def running_desktop_pids(executable: Path) -> tuple[int, ...]:
    """Return the PIDs of every running Claude Desktop process.

    The harness must be the PRIMARY instance (single-instance forwarding drops
    startup flags otherwise), so the caller asserts this is empty before launch.
    """
    completed = subprocess.run(  # noqa: S603 - fixed PowerShell inventory/process command
        [
            _POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-Process -Name claude -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Path -like '*WindowsApps*' } | Select-Object -ExpandProperty Id",
        ],
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="replace",
        check=False,
        timeout=60,
    )
    return tuple(int(line) for line in completed.stdout.split() if line.strip().isdigit())


def seed_auth_state(
    source_profile: Path,
    target_user_data_dir: Path,
    *,
    seed_paths: Sequence[str] = AUTH_SEED_PATHS,
) -> tuple[str, ...]:
    """Copy the curated auth/session state into a fresh isolated user-data dir.

    Returns the seed-path names that were actually present in the source and
    copied. A path absent from the source is skipped (a fresh source profile may
    lack ``Session Storage`` until first use). The target dir must be independent
    of the source — the whole point is a clean per-run environment.

    Raises:
        DesktopCaptureError: If the target dir is inside the source profile (or
            vice versa), or if no auth-bearing state (``config.json``) was seeded.
    """
    source = source_profile.resolve()
    target = target_user_data_dir.resolve()
    if source == target or source in target.parents or target in source.parents:
        raise DesktopCaptureError(
            f"isolated user-data dir {target} must be independent of the source profile {source}",
        )
    target.mkdir(parents=True, exist_ok=True)
    seeded: list[str] = []
    for name in seed_paths:
        src = source / name
        if not src.exists():
            continue
        dst = target / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        seeded.append(name)
    if "config.json" not in seeded:
        raise DesktopCaptureError(
            f"source profile {source} carried no config.json to seed session auth from; "
            "log in once to the harness source profile before capturing",
        )
    return tuple(seeded)


def seed_extension(target_user_data_dir: Path, source_extension_dir: Path, *, settings_json: str) -> Path:
    """Provision the single MCPB extension under test into the isolated profile.

    The extension payload is copied under ``Claude Extensions/<id>`` and its
    enablement/user-config record under ``Claude Extensions Settings/<id>.json``,
    reproducing exactly the one extension the run tests and nothing else.
    Returns the copied extension directory.
    """
    extension_id = source_extension_dir.name
    extensions_root = target_user_data_dir / "Claude Extensions"
    settings_root = target_user_data_dir / "Claude Extensions Settings"
    extensions_root.mkdir(parents=True, exist_ok=True)
    settings_root.mkdir(parents=True, exist_ok=True)
    destination = extensions_root / extension_id
    shutil.copytree(source_extension_dir, destination, dirs_exist_ok=True)
    (settings_root / f"{extension_id}.json").write_text(settings_json, encoding=_UTF_8, newline="\n")
    return destination


_REAL_TRANSPORTS: Final[frozenset[str]] = frozenset({"inprocess", "subprocess", "subprocess_fallback"})
_ERROR_STATUSES: Final[frozenset[str]] = frozenset({"error", "failed", "failure"})


@dataclass(frozen=True)
class McpToolCall:
    """One MCP tool call observed in Desktop's per-server console log."""

    transport: str
    executable: str
    tool_name: str | None = None
    is_error: bool | None = None
    status: str | None = None

    @property
    def is_real_transport(self) -> bool:
        """True when the telemetry ``transport`` (per 60d7120e22) is genuine."""
        return self.transport in _REAL_TRANSPORTS

    @property
    def succeeded(self) -> bool:
        """True when the call was really served AND its RESULT did not error.

        A dispatched call whose telemetry carries an explicit error marker
        (``is_error`` true or an error-like ``status``) is NOT a success; a
        capture gated only on connected+dispatched would record "passed" over a
        failing tool result, which this property exists to refuse.
        """
        if not self.is_real_transport:
            return False
        if self.is_error is True:
            return False
        return not (self.status is not None and self.status.lower() in _ERROR_STATUSES)


@dataclass(frozen=True)
class McpLogObservation:
    """The telemetry proof extracted from a Desktop MCP server console log."""

    connected: bool
    calls: tuple[McpToolCall, ...]

    @property
    def successful_calls(self) -> tuple[McpToolCall, ...]:
        """The calls that were genuinely served and whose results succeeded."""
        return tuple(call for call in self.calls if call.succeeded)

    @property
    def served_by_real_transport(self) -> bool:
        """True when at least one call was served by a genuine transport."""
        return any(call.is_real_transport for call in self.calls)


def parse_mcp_server_log(text: str) -> McpLogObservation:
    """Extract the connection + tool-call telemetry from a Desktop MCP log.

    Desktop pipes each MCP server's stderr into
    ``logs/mcp-server-<name>.log``. The cadrumo server emits one JSON telemetry
    object per served call carrying the typed ``transport`` field and the
    attested environment CLI ``executable`` (per 60d7120e22). This scans for
    those objects and for the connection marker, tolerating interleaved
    non-JSON log lines.
    """
    connected = False
    calls: list[McpToolCall] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        lowered = line.lower()
        if "successfully connected" in lowered or '"connected"' in lowered or "server started" in lowered:
            connected = True
        brace = line.find("{")
        if brace == -1:
            continue
        candidate = line[brace:]
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        transport = obj.get("transport")
        if isinstance(transport, str) and transport:
            raw_error = obj.get("is_error")
            raw_status = obj.get("status")
            calls.append(
                McpToolCall(
                    transport=transport,
                    executable=str(obj.get("executable") or ""),
                    tool_name=(str(obj["tool"]) if isinstance(obj.get("tool"), str) else None),
                    is_error=(raw_error if isinstance(raw_error, bool) else None),
                    status=(raw_status if isinstance(raw_status, str) else None),
                ),
            )
            connected = True
    return McpLogObservation(connected=connected, calls=tuple(calls))


def extract_target_value(reply_text: str, *, target_value: str) -> bool:
    """Return whether the assistant reply reproduces the grounded oracle value.

    The canonical prompt asks for Modelo 200 cuota íntegra (casilla
    ``DP200014:00562`` = ``23000.00``); the reply proving a real tool call
    contains that exact figure. Each numeric token is normalized independently,
    so ``23000.00``, ``23,000.00`` and ``23.000,00`` satisfy it but a larger or
    embedded digit sequence cannot.
    """
    expected = _normalise_numeric_token(target_value)
    if expected is None:
        raise DesktopCaptureError(f"target value is not a canonical numeric value: {target_value!r}")
    return any(
        observed == expected
        for token in _NUMERIC_TOKEN_PATTERN.finditer(reply_text)
        if (observed := _normalise_numeric_token(token.group())) is not None
    )


def _normalise_numeric_token(token: str) -> Decimal | None:
    """Parse one bounded desktop numeric token without collapsing its value.

    A single separator with one or two trailing digits is decimal; a separator
    followed by a three-digit group is thousands only when every group is valid.
    Mixed separators use the rightmost separator as decimal.  Ambiguous forms
    such as ``2300.000`` are refused instead of being treated as ``2300000``.
    """
    compact = token.replace("\xa0", " ").strip()
    if not compact or not re.fullmatch(r"\d(?:[\d., ]*\d)?", compact):
        return None
    dot_count = compact.count(".")
    comma_count = compact.count(",")
    if dot_count and comma_count:
        decimal_separator = "." if compact.rfind(".") > compact.rfind(",") else ","
        grouping_separator = "," if decimal_separator == "." else "."
        integer_part, fractional_part = compact.rsplit(decimal_separator, 1)
        if not 1 <= len(fractional_part) <= 2 or grouping_separator in fractional_part or " " in fractional_part:
            return None
        digits = _integer_digits(integer_part, grouping_separator)
        if digits is None:
            return None
        canonical = f"{digits}.{fractional_part}"
    else:
        separator = "." if dot_count else "," if comma_count else ""
        if not separator:
            digits = _integer_digits(compact, None)
            if digits is None:
                return None
            canonical = digits
        else:
            parts = compact.split(separator)
            if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
                digits = _integer_digits(parts[0], None)
                if digits is None or not parts[1].isdigit():
                    return None
                canonical = f"{digits}.{parts[1]}"
            else:
                digits = _grouped_integer_digits(compact, separator)
                if digits is None:
                    return None
                canonical = digits
    try:
        return Decimal(canonical)
    except InvalidOperation:
        return None


def _grouped_integer_digits(value: str, separator: str) -> str | None:
    """Return valid grouped integer digits, rejecting malformed separators."""
    groups = value.split(separator)
    if not groups or not 1 <= len(groups[0]) <= 3 or not groups[0].isdigit():
        return None
    if any(len(group) != 3 or not group.isdigit() for group in groups[1:]):
        return None
    return "".join(groups)


def _integer_digits(value: str, grouping_separator: str | None) -> str | None:
    """Return digits from an ungrouped or consistently grouped integer portion."""
    if " " in value:
        if grouping_separator is not None and grouping_separator in value:
            return None
        return _grouped_integer_digits(value, " ")
    if grouping_separator is None:
        return value if value.isdigit() else None
    return _grouped_integer_digits(value, grouping_separator)


@dataclass
class AttemptLog:
    """Per-attempt diagnostics retained on every capture attempt."""

    attempt: int
    ok: bool
    detail: str
    reply_excerpt: str = ""


@dataclass
class CaptureResult:
    """The outcome of the bounded, fail-closed capture loop."""

    ok: bool
    attempts: list[AttemptLog] = field(default_factory=list)
    reply_text: str = ""


def _retryable_attempt_errors() -> tuple[type[BaseException], ...]:
    """Return the exception types one capture attempt may legitimately fail with.

    An attempt fails RETRYABLY when the launched app was not ready, its UI did
    not settle, or the model did not tool-call — all transient states of a real
    running application. Playwright raises its own hierarchy for those and is an
    optional extra, so its base error is resolved lazily and simply omitted when
    the package is absent.

    Everything else is a harness defect — a log-parser ``AttributeError``, a
    changed-manifest ``KeyError``, a missing-profile ``OSError`` — and MUST
    propagate on the first attempt. Retrying a deterministic bug twice more
    burns two further app launches and, worse, records it in the evidence as if
    it were model flakiness, making the two indistinguishable to a later reader.
    """
    retryable: tuple[type[BaseException], ...] = (DesktopCaptureError, TimeoutError)
    try:
        from playwright.sync_api import Error as PlaywrightError
    except ImportError:
        return retryable
    return (*retryable, PlaywrightError)


def capture_with_retries(
    perform: Callable[[int], AttemptLog],
    *,
    attempts: int = 3,
) -> CaptureResult:
    """Run the send-and-verify loop with bounded retries, fail-closed.

    ``perform`` executes one full attempt — send the canonical prompt over CDP,
    then verify a real cadrumo tool call landed (the primary proof is the MCP
    server log telemetry, not the model's prose) — and returns an
    :class:`AttemptLog` whose ``ok`` states whether that attempt proved a real
    tool call. The model may not tool-call on the first attempt, so attempts are
    bounded and every one is logged; exhaustion returns a non-ok result carrying
    all diagnostics rather than raising, so the caller bundles them into the
    fail-closed evidence.

    Only the transient classes in :func:`_retryable_attempt_errors` are retried;
    a harness defect propagates immediately rather than being logged as a failed
    attempt, so a deterministic bug can never be diagnosed as model flakiness.

    The default of three attempts is a CHOSEN convention, not a derived
    threshold: no measurement of the model's first-attempt tool-call rate backs
    it. It is safe to state plainly because the count never launders a result —
    exhaustion fails closed, and every attempt is retained in the emitted
    evidence row, so a run that needed three tries is visibly weaker than one
    that needed one. Deriving it would need a first-attempt success series.
    """
    result = CaptureResult(ok=False)
    retryable = _retryable_attempt_errors()
    for index in range(1, attempts + 1):
        try:
            attempt = perform(index)
        except retryable as exc:  # transient app/model state; a harness defect propagates
            result.attempts.append(AttemptLog(attempt=index, ok=False, detail=f"attempt raised: {exc}"))
            continue
        result.attempts.append(attempt)
        if attempt.ok:
            result.ok = True
            result.reply_text = attempt.reply_excerpt
            return result
    return result


def scan_for_secret_leak(logs_dir: Path, secrets: Iterable[str]) -> None:
    """Refuse to retain any capture artifact carrying a seeded auth secret.

    The retained artifact tree (attempt logs, CDP dumps, copied MCP logs) can be
    uploaded as CI evidence, so it is scanned for the seeded credential secrets
    before the run is trusted. A hit deletes the leaking file and refuses,
    mirroring :mod:`dev.packaging.smoke_plugin_install`. Reduces, not eliminates,
    leak risk: an exotic re-encoding could still pass.

    Raises:
        DesktopCaptureError: On the first artifact found to carry a secret.
    """
    needles = tuple(secret for secret in secrets if secret)
    if not needles:
        return
    for path in scan_directory(logs_dir, recursive=True):
        if not path.is_file():
            continue
        text = path.read_text(encoding=_UTF_8, errors="replace")
        if any(needle in text for needle in needles):
            path.unlink()
            raise DesktopCaptureError(
                f"seeded auth secret leaked into capture artifact {path.name}; "
                "the leaking file was deleted and the capture is refused",
            )


def collect_seed_secrets(config_json_path: Path) -> tuple[str, ...]:
    """Return the encrypted-token strings from a seeded ``config.json``.

    The safeStorage ``oauth:tokenCache*`` and ``dxt:allowlistCache*`` values are
    ciphertext, but they are still per-user secrets that must not appear verbatim
    in a retained, uploadable artifact. Any string value >= 32 chars is treated
    as a secret so an unrecognised token field stays covered.
    """
    try:
        document = json.loads(config_json_path.read_text(encoding=_UTF_8))
    except (OSError, json.JSONDecodeError):
        return ()
    if not isinstance(document, dict):
        return ()
    return tuple(dict.fromkeys(value for value in document.values() if isinstance(value, str) and len(value) >= 32))


def _validated_cdp_target(port: int) -> tuple[str, int, str]:
    parsed = urllib.parse.urlsplit(f"{_CDP_SCHEME}://{_CDP_HOST}:{port}{_CDP_PATH}")
    if (
        parsed.scheme != _CDP_SCHEME
        or parsed.hostname != _CDP_HOST
        or parsed.port != port
        or parsed.path != _CDP_PATH
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("CDP target is not the fixed local HTTP endpoint")
    return parsed.hostname, parsed.port, parsed.path


def _read_cdp_version(port: int) -> bytes:
    host, validated_port, target = _validated_cdp_target(port)
    connection = http.client.HTTPConnection(host, validated_port, timeout=5)
    try:
        connection.request("GET", target)
        response = connection.getresponse()
        if not 200 <= response.status < 300:
            raise ConnectionError(f"CDP endpoint returned HTTP {response.status}")
        return response.read()
    finally:
        connection.close()


def wait_for_cdp(port: int, *, timeout_seconds: float = 60.0, poll_seconds: float = 1.0) -> dict[str, Any]:
    """Poll the CDP ``/json/version`` endpoint until the launched app answers.

    Returns the version document (carries the ``webSocketDebuggerUrl``). This is
    how the harness confirms it won the single-instance race and owns a
    debug-enabled primary instance.

    Raises:
        DesktopCaptureError: If no CDP endpoint answers within the budget.
    """
    deadline = time.monotonic() + timeout_seconds
    last_error = "no response"
    while time.monotonic() < deadline:
        try:
            return json.loads(_read_cdp_version(port).decode(_UTF_8))
        except (http.client.HTTPException, TimeoutError, ConnectionError, json.JSONDecodeError, OSError) as exc:
            last_error = str(exc)
            time.sleep(poll_seconds)
    raise DesktopCaptureError(
        f"no CDP endpoint answered on 127.0.0.1:{port} within {timeout_seconds}s "
        f"(last error: {last_error}); the app likely forwarded to an already-running "
        "instance — ensure no other Claude Desktop is running before launch",
    )


_ACTIVATE_PS1: Final[str] = r"""
$ErrorActionPreference = 'Stop'
$src = @'
using System;
using System.Runtime.InteropServices;
[ComImport, Guid("2e941141-7f97-4756-ba1d-9decde894a3d"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IApplicationActivationManager {
  IntPtr ActivateApplication([In] string appUserModelId, [In] string arguments,
    [In] int options, [Out] out uint processId);
}
[ComImport, Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")]
public class ApplicationActivationManager { }
public static class DesktopActivator {
  public static uint Activate(string aumid, string args) {
    var mgr = (IApplicationActivationManager)new ApplicationActivationManager();
    uint pid; mgr.ActivateApplication(aumid, args, 0, out pid); return pid;
  }
}
'@
Add-Type -TypeDefinition $src -ErrorAction Stop
$activatedPid = [DesktopActivator]::Activate($env:CADRUMO_ACTIVATE_AUMID, $env:CADRUMO_ACTIVATE_ARGS)
Write-Output $activatedPid
"""


def activate_desktop(aumid: str, *, remote_debugging_port: int, user_data_dir: Path) -> int:
    """Activate the Store app with the debug port + isolated user-data dir.

    Uses ``IApplicationActivationManager::ActivateApplication`` (the only launch
    that carries custom Electron flags into a Store app). MUST be called from a
    NON-ELEVATED INTERACTIVE session — an elevated Session-0 caller gets
    ``E_ACCESSDENIED``. Returns the activated process id.

    Raises:
        DesktopCaptureError: If activation fails (commonly the elevation/session
            wall or an already-running instance).
    """
    arguments = f'--remote-debugging-port={remote_debugging_port} --user-data-dir="{user_data_dir}"'
    environment = {
        "CADRUMO_ACTIVATE_AUMID": aumid,
        "CADRUMO_ACTIVATE_ARGS": arguments,
    }
    completed = subprocess.run(  # noqa: S603 - fixed PowerShell COM activation
        [_POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _ACTIVATE_PS1],
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="replace",
        check=False,
        timeout=120,
        env={**_os_environ(), **environment},
    )
    if completed.returncode != 0:
        raise DesktopCaptureError(
            f"MSIX activation of {aumid} failed (rc={completed.returncode}): {completed.stderr.strip()[:400]}. "
            "If this is E_ACCESSDENIED, the caller is elevated or Session-0; run the harness from a "
            "non-elevated interactive session.",
        )
    pid_line = next((line for line in completed.stdout.split() if line.strip().isdigit()), None)
    if pid_line is None:
        raise DesktopCaptureError(f"activation returned no process id; stdout={completed.stdout.strip()[:300]}")
    return int(pid_line)


def _os_environ() -> dict[str, str]:
    import os

    return dict(os.environ)


def launch_desktop_direct_appdata(
    executable: Path,
    *,
    remote_debugging_port: int,
    profile_appdata_root: Path,
) -> int:
    """FALLBACK launch: run ``Claude.exe`` directly with a redirected ``APPDATA``.

    Designed in advance for the case where the app ignores ``--user-data-dir``:
    Electron resolves its userData as ``%APPDATA%/<app name>``, so redirecting
    the ``APPDATA`` environment variable at process creation points ALL profile
    state at ``profile_appdata_root/Claude`` without relying on the Chromium
    switch. Direct CreateProcess of a WindowsApps executable runs it with
    package identity on current Windows builds when invoked by the installing
    user from a non-elevated interactive session; if Windows refuses
    (``ERROR_ELEVATION_REQUIRED`` or a package-identity error), the refusal
    surfaces here and the capture aborts fail-closed. Returns the process id.
    """
    profile_appdata_root.mkdir(parents=True, exist_ok=True)
    environment = {
        **_os_environ(),
        "APPDATA": str(profile_appdata_root),
    }
    process = subprocess.Popen(  # noqa: S603 - the fixed installed Desktop executable
        [str(executable), f"--remote-debugging-port={remote_debugging_port}"],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return process.pid


def drive_tax_prompt(
    cdp_endpoint: str,
    prompt: str,
    *,
    ready_timeout_ms: int = 120_000,
    reply_timeout_ms: int = 180_000,
) -> str:
    """Drive the launched Desktop app over CDP to send the prompt and read the reply.

    Connects to the already-launched app's debug endpoint with Playwright
    (``connect_over_cdp`` attaches to a running instance — it never spawns, which
    is required because only the MSIX activation can launch the Store app). Finds
    the main renderer window, types the canonical tax prompt into the composer,
    submits, waits for the assistant turn to settle, and returns the visible
    reply text.

    This is the integration surface: it runs only against a real launched app and
    is exercised by the operator/coordinator-dispatched real run, not per-push.
    """
    from playwright.sync_api import sync_playwright  # lazily imported: playwright is an extra

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_endpoint)
        try:
            page = _main_desktop_page(browser, ready_timeout_ms=ready_timeout_ms)
            composer = page.get_by_role("textbox").last
            composer.wait_for(state="visible", timeout=ready_timeout_ms)
            composer.click()
            composer.fill(prompt)
            composer.press("Enter")
            return _await_assistant_reply(page, reply_timeout_ms=reply_timeout_ms)
        finally:
            browser.close()


def _main_desktop_page(browser: Any, *, ready_timeout_ms: int) -> Any:
    """Return the primary renderer page (the chat window) from the CDP contexts."""
    deadline = time.monotonic() + ready_timeout_ms / 1000
    while time.monotonic() < deadline:
        for context in browser.contexts:
            for page in context.pages:
                title = (page.title() or "").lower()
                url = (page.url or "").lower()
                is_claude = "claude" in title or "claude.ai" in url or url.startswith("file")
                if is_claude and page.get_by_role("textbox").count() > 0:
                    return page
        time.sleep(1.0)
    raise DesktopCaptureError("no Claude Desktop chat window with a composer appeared over CDP within the ready budget")


def _await_assistant_reply(page: Any, *, reply_timeout_ms: int) -> str:
    """Wait for the assistant turn to finish streaming and return its text."""
    page.wait_for_timeout(2000)
    deadline = time.monotonic() + reply_timeout_ms / 1000
    previous = ""
    stable_since = time.monotonic()
    while time.monotonic() < deadline:
        text = page.inner_text("body")
        if text != previous:
            previous = text
            stable_since = time.monotonic()
        elif time.monotonic() - stable_since > 4.0:
            return text
        page.wait_for_timeout(1500)
    return previous
