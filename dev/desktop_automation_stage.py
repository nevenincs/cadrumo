"""Stage the recorded native automation host in an isolated package mirror."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .desktop_agent_live.freshness import stage_verdict
from .desktop_agent_live.package import stage_lane_package
from .packaging.native.build_directory import require_enrolled_build, require_enrolled_output
from .packaging.native.build_paths import build_paths
from .packaging.native.hashing import digest
from .packaging.native.layout import load_layout


def _automation_record(testing: Path, configuration: str) -> dict[str, Any]:
    """Read the packaged host record, refusing one not built for this configuration with native automation."""
    record = require_enrolled_output(testing / "packaged" / "host.json")
    value = json.loads(record.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("The packaged automation host record must be an object")
    if value.get("configuration") != configuration:
        raise ValueError(f"The packaged automation host was not built for {configuration}")
    features = value.get("features")
    if not isinstance(features, list) or "native-automation" not in features:
        raise ValueError("The packaged host was not built with native-automation")
    if value.get("variant") != "packaged" or value.get("shell") is not None:
        raise ValueError("The automation host must use the embedded packaged shell")
    return value


def _automation_host(testing: Path, configuration: str) -> Path:
    value = _automation_record(testing, configuration)
    executable = value.get("executable")
    if not isinstance(executable, str) or not Path(executable).is_absolute():
        raise ValueError("The packaged automation host must name an absolute executable")
    host = require_enrolled_output(executable)
    cargo = testing / "packaged" / "cargo" / configuration.lower()
    if host.parent != cargo or host.name not in {"cadrumo", "cadrumo.exe"}:
        raise ValueError("The automation host executable is outside its packaged Cargo configuration")
    if not host.is_file() or digest(host) != value.get("sha256"):
        raise ValueError("The automation host changed after its build recorded it; rebuild desktop-packaged-host")
    return host


def stage_automation_package(build: Path, configuration: str) -> dict[str, str]:
    """Admit an existing native stage and mirror it with its recorded automation host."""
    if not build.is_absolute():
        raise ValueError("The native build directory must be absolute")
    if configuration not in {"Debug", "Release"}:
        raise ValueError("The native build configuration must be Debug or Release")
    build = require_enrolled_build(build)
    paths = build_paths(build)
    testing = paths["desktop_testing"]
    staged = require_enrolled_output(paths["stage"] / configuration / "app")
    destination = require_enrolled_output(testing / "automation" / "package" / configuration / "app")
    host = _automation_host(testing, configuration)
    verdict = stage_verdict(build, configuration)
    if verdict.refusals:
        raise ValueError("; ".join(verdict.refusals))
    identity = require_enrolled_output(paths["generated"] / "identity.json")
    target = json.loads(identity.read_text(encoding="utf-8"))["target"]
    image = stage_lane_package(load_layout(target), staged, host, destination)
    return {"package": str(destination), "executable": str(image)}


def main(argv: list[str] | None = None) -> int:
    """Print one JSON object naming the mirror and its executable, or the refusal."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--config", required=True, choices=("Debug", "Release"))
    options = parser.parse_args(argv)
    try:
        result = stage_automation_package(options.build, options.config)
    except (OSError, ValueError, KeyError, TypeError) as refused:
        print(json.dumps({"error": str(refused)}), flush=True)
        return 3
    print(json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
