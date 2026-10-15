"""A stand-in for the package's interpreter hosts and the bundled agent, for exercising the launch probe.

The stand-in host applies the package declaration's own launch profiles through the independent Python reading
(``reference_select`` and ``reference_define``) and then runs this interpreter with the environment it defined.
The stand-in agent speaks the hosting protocol's lines. Neither is the real thing: the real host and agent are
exercised by the probe once a bundle is built. A faults file makes the host misbehave in the ways the probe must
notice; a mode file makes the agent answer each way the probe must tell apart.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dev._paths import REPO_ROOT

from ..generate import generate
from ..layout import load_layout

HOST = """
import json, os, subprocess, sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, {root!r})
from dev.packaging.native.application_environment import (
    DECLARATION, LaunchRefusedError, parse, reference_define, reference_select,
)
from dev.packaging.native.layout import load_layout

here = Path(__file__).resolve().parent
faults = json.loads((here / "faults.json").read_text(encoding="utf-8"))
package, image, *arguments = sys.argv[1:]
compiled = json.loads((here / "contract.json").read_text(encoding="utf-8"))
declaration = replace(parse((Path({root!r}) / DECLARATION).read_text(encoding="utf-8")),
                      package_values=compiled["application_environment"]["package_fixed"])
layout = load_layout({target!r})
windows = os.name == "nt"
family = "windows" if windows else "posix"


def refuse(code, subject):
    separators = (", ", ": ") if faults.get("spaced_json") else (",", ":")
    sys.stderr.write(json.dumps({{"native_refusal": code, "subject": subject}}, separators=separators) + "\\n")
    sys.stderr.flush()
    raise SystemExit(125)


def lookup(name):
    for key, value in os.environ.items():
        if (key.upper() == name.upper()) if windows else (key == name):
            return value
    return None


if faults.get("refuse") and image != "python" and faults.get("only", "") in ("", *arguments):
    refuse(*faults["refuse"])
try:
    profile = reference_select(declaration, family, image, arguments)
except LaunchRefusedError as error:
    if faults.get("admit_all"):
        raise SystemExit(0)
    refuse(error.code, error.subject)
root = lookup(declaration.root["variable"])
if not root:
    platform = {{"nt": "windows"}}.get(os.name, "linux")
    rule = next(item for item in declaration.root["installed_defaults"] if item["platform"] == platform)
    for candidate in rule["candidates"]:
        value = lookup(candidate["variable"])
        if value and Path(value).is_absolute():
            root = str(Path(value, *candidate["subpath"], declaration.root["channel"]["product_directory"]))
            break
root = faults.get("root") or root
try:
    defined = reference_define(
        declaration,
        family,
        profile,
        dict(os.environ),
        package=package,
        root=root,
        layout_paths=layout["paths"],
        suffix=layout["entrypoint_suffix"],
    )
except LaunchRefusedError as error:
    refuse(error.code, error.subject)
if faults.get("path"):
    defined["PATH"] = faults["path"]
for name in faults.get("leak", []):
    defined[name] = os.environ[name]
for name in ("TEMP", "TMP", "TMPDIR"):
    if name in defined:
        os.makedirs(defined[name], exist_ok=True)
defined["PYTHONPATH"] = str(here / "stub")
raise SystemExit(subprocess.Popen([sys.executable, *arguments], env=defined).wait())
"""

AGENT_MAIN = """
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
NAMES = json.loads((HERE / "names.json").read_text(encoding="utf-8"))
MODE = (HERE / "mode.txt").read_text(encoding="utf-8").strip()


def _root():
    value = os.environ.get(NAMES["hosted_root"], "")
    return Path(value) if value else None


def _emit(document):
    sys.stdout.write(json.dumps(document, separators=(",", ":")) + "\\n")
    sys.stdout.flush()


def _refuse(code):
    _emit({"event": "refused", "code": code})
    sys.stderr.write(json.dumps({"startup_refusal": code}) + "\\n")
    sys.stderr.flush()
    raise SystemExit(78)


def serve():
    (HERE / "gateway.pid").write_text(str(os.getpid()), encoding="utf-8")
    if json.loads(sys.stdin.readline()) != {"version": 1, "credentials": {}}:
        raise SystemExit(3)
    root = _root()
    if root is None or MODE == "crash":
        raise SystemExit(1)
    if MODE == "hang":
        time.sleep(3600)
    if MODE == "stores_mismatch" or not (root / "stores.marker").exists():
        _refuse("hosted_stores_mismatch")
    if MODE == "proof_policy":
        _refuse("hosted_proof_policy")
    if MODE == "ready":
        _emit({"event": "agent_ready", "gateway_port": 1, "agent_version": "0", "hosting_contract": 1})
        sys.stdin.read()
        raise SystemExit(0)
    _refuse("hosted_lane_unproven")


def main(argv=None, standalone_mode=True):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["stores-state"]:
        root = _root()
        if root is None:
            raise SystemExit(1)
        state = "current" if (root / "stores.marker").exists() else "absent"
        if MODE == "garbled_state":
            state = "weird"
        _emit({"state": state, "primary": {"state": state}, "checkpoint": {"state": state}})
        return
    if arguments == ["setup"]:
        root = _root()
        if root is None or MODE == "setup_fails":
            _emit({"status": "failed"})
            raise SystemExit(1)
        if MODE != "no_setup":
            (root / "stores.marker").write_text("current", encoding="utf-8")
        _emit({"status": "succeeded"})
        return
    if arguments == ["version", "--json"]:
        _emit({"package_version": "0", "api_version": "v1"})
        return
    if arguments == ["serve"]:
        serve()
        return
    raise SystemExit(2)


if __name__ == "__main__":
    main()
"""

AGENT_WORKER = """
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
NAMES = json.loads((HERE / "names.json").read_text(encoding="utf-8"))
MODE = (HERE / "mode.txt").read_text(encoding="utf-8").strip()


def main():
    frame = json.loads(sys.stdin.readline())
    wanted = [os.environ.get(NAMES[key], "") for key in ("hosted_root", "worker_host", "gateway_url")]
    if not frame.get("internal_token") or not all(wanted) or os.environ.get(NAMES["worker_generation"]) != "1":
        raise SystemExit(78)
    if MODE == "hang":
        time.sleep(3600)
    sys.stdout.write(json.dumps({"event": "worker_bound", "port": 4242}) + "\\n")
    sys.stdout.flush()
    sys.stdin.read()


if __name__ == "__main__":
    main()
"""


@dataclass(frozen=True)
class StandIn:
    """A fake package tree, its generated contract and the files that steer the stand-in host and agent."""

    package: Path
    contract: dict[str, Any]
    command: Path
    stub: Path
    faults: Path
    agent_names: dict[str, str]

    def agent_mode(self, mode: str) -> None:
        """Make the stand-in agent answer ``mode``.

        One of unproven, ready, proof_policy, crash, hang, no_setup (setup succeeds and leaves the stores absent),
        setup_fails (setup exits 1), garbled_state (stores-state names no state) or stores_mismatch (the stores
        read current and serve refuses them anyway).
        """
        (self.stub / "mode.txt").write_text(mode, encoding="utf-8")

    def host_faults(self, **faults: object) -> None:
        """Make the stand-in host misbehave as the keywords say; no keyword restores it."""
        self.faults.write_text(json.dumps(faults), encoding="utf-8")

    def gateway_pid(self) -> int | None:
        """The process identifier the stand-in gateway recorded, if it started."""
        recorded = self.stub / "gateway.pid"
        return int(recorded.read_text(encoding="utf-8")) if recorded.is_file() else None


def generated_contract(directory: Path, target: str) -> dict[str, Any]:
    """Generate the target's native contract once and read it."""
    generate(REPO_ROOT, directory, target=target)
    document: dict[str, Any] = json.loads((directory / "contract.json").read_text(encoding="utf-8"))
    return document


def build(directory: Path, target: str, contract: dict[str, Any]) -> StandIn:
    """Lay out a package of empty images around ``contract`` and write the stand-in host and agent."""
    layout = load_layout(target)
    package = directory / "package"
    suffix = layout["entrypoint_suffix"]
    native = package / layout["paths"]["native"]
    native.mkdir(parents=True)
    for image in ("python", "aeat", "cadrumo-mcp", *layout["bundled_images"]):
        (native / f"{image}{suffix}").write_bytes(b"")
    # The stand-in agent spells its settings as the agent does: its prefix, which the contract carries, and the
    # setting's name. The contract lists none of them but the gateway's launch parameters.
    prefix = next(profile["prefix"] for profile in contract["application_environment"]["profiles"] if profile["prefix"])

    def spelled(field: str) -> str:
        return f"{prefix}{field.upper()}"

    agent_names = {
        field: spelled(field)
        for field in ("hosted_root", "worker_port", "gateway_url", "worker_host", "gateway_lifetime_id")
    } | {"worker_generation": spelled("worker_generation")}
    stub = directory / "stand-in" / "stub"
    (stub / "cadrumo_agent" / "cli").mkdir(parents=True)
    (stub / "cadrumo_agent" / "__init__.py").write_text("", encoding="utf-8")
    (stub / "cadrumo_agent" / "cli" / "__init__.py").write_text("", encoding="utf-8")
    (stub / "cadrumo_agent" / "cli" / "main.py").write_text(AGENT_MAIN, encoding="utf-8")
    (stub / "cadrumo_agent" / "worker.py").write_text(AGENT_WORKER, encoding="utf-8")
    (stub / "names.json").write_text(json.dumps(agent_names), encoding="utf-8")
    command = directory / "stand-in" / "host.py"
    (command.parent / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
    command.write_text(HOST.format(root=str(REPO_ROOT), target=target), encoding="utf-8")
    stand_in = StandIn(package, contract, command, stub, directory / "stand-in" / "faults.json", agent_names)
    stand_in.agent_mode("unproven")
    stand_in.host_faults()
    return stand_in


def host_command(stand_in: StandIn, image: str, arguments: list[str]) -> list[str]:
    """The argv that runs the stand-in host as ``image`` with ``arguments``."""
    return [sys.executable, str(stand_in.command), str(stand_in.package), image, *arguments]
