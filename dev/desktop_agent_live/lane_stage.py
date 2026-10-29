"""Verify and stage the recorded desktop host and package snapshot."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .freshness import StageVerdict, stage_verdict
from .lane_errors import UnavailableError
from .package import stage_lane_package

_REPOSITORY: Final = Path(__file__).resolve().parents[2]
_BUILD: Final = _REPOSITORY / "build" / "windows-x64"
_STAGE: Final = _BUILD / "stage"
_TESTING: Final = _BUILD / "desktop" / "testing"
_PACKAGED_ENTRY: Final = "http://tauri.localhost/index.html"


@dataclass(frozen=True, slots=True)
class TestHost:
    """The recorded remote-debugging desktop host, the shell it loads and the configuration it was built in."""

    executable: Path
    entry: str
    configuration: str
    record: Path

    @property
    def package(self) -> Path:
        """The staged package of the host's own configuration, which the run's package mirrors."""
        return _STAGE / self.configuration / "app"

    @property
    def lane_package(self) -> Path:
        """Where the run's package mirrors :attr:`package` with this host as its desktop image."""
        return _TESTING / "agent-live-package" / self.configuration / "app"


def test_host(served: bool) -> TestHost:
    """Read the remote-debugging host record the host build wrote, refusing a changed image."""
    import hashlib

    variant = "served" if served else "packaged"
    record = _TESTING / variant / "host.json"
    build = (
        "node native/desktop/tests/packaged/host.mjs --served (with CADRUMO_CMAKE_BINARY_DIR, CADRUMO_BUILD_CONFIG "
        "and CADRUMO_NATIVE_CONTRACT set)"
        if served
        else "just build-native Release desktop-packaged-host"
    )
    if not record.is_file():
        raise UnavailableError(f"no remote-debugging desktop host is built; build it with: {build}")
    value = json.loads(record.read_text(encoding="utf-8"))
    executable = Path(value.get("executable", ""))
    if "webview2-remote-debugging" not in value.get("features", ()) or not executable.is_file():
        raise UnavailableError(f"the desktop host record is not a remote-debugging host; rebuild it with: {build}")
    if hashlib.sha256(executable.read_bytes()).hexdigest() != value.get("sha256"):
        raise UnavailableError(f"the desktop host changed after its build recorded it; rebuild it with: {build}")
    shell = value.get("shell")
    configuration = value.get("configuration")
    if configuration not in ("Debug", "Release"):
        raise UnavailableError(f"the desktop host record names no build configuration; rebuild it with: {build}")
    return TestHost(executable, f"{shell}index.html" if served and shell else _PACKAGED_ENTRY, configuration, record)


def require_current(host: TestHost) -> StageVerdict:
    """Refuse a stage or test host whose build records do not vouch for its bytes.

    Inputs edited since the stage was built do not refuse the run: the verdict
    names the build each component's bytes come from and what was edited since,
    for the run to report with its results.
    """
    configuration = host.configuration
    verdict = stage_verdict(_BUILD, configuration)
    if verdict.refusals:
        raise UnavailableError("; ".join(verdict.refusals))
    return verdict


def snapshot_report(verdict: StageVerdict) -> dict[str, object]:
    """What the run's results are for: each component's build, and the inputs edited since it."""
    edited = sorted({name for names in verdict.changed.values() for name in names})
    return {
        "snapshot": verdict.snapshot,
        "newer_edits": len(edited),
        "edited_since": edited,
        "summary": (
            "results are for snapshot "
            + ", ".join(f"{component} {build}" for component, build in verdict.snapshot.items())
            + (f"; {len(edited)} inputs changed since" if edited else "; no input changed since")
        ),
    }


def stage_package(host: TestHost, destination: Path) -> Path:
    """Mirror the host's staged package into ``destination`` with the host as its desktop; return its image."""
    from ..packaging.native.layout import load_layout

    target = json.loads((_BUILD / "generated" / "identity.json").read_text(encoding="utf-8"))["target"]
    try:
        image = stage_lane_package(load_layout(target), host.package, host.executable, destination)
    except (OSError, ValueError) as refused:
        raise UnavailableError(f"the lane package could not be staged from {host.package}: {refused}") from refused
    print(json.dumps({"step": "package_staged", "package": str(destination)}), flush=True)
    return image
