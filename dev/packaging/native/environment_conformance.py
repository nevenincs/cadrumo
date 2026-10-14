"""The package-side conformance check: the package's declaration is the reference.

``native/application-environment.toml`` states which environment names each
packaged image sets, passes or lets an operator override, where the storage
root defaults, which exit statuses the native host reserves and which
invocations the agent image admits. The installed command line, the runtime and
the bundled agent each keep their own copy of some of those facts. This check
compares each copy with the declaration and reports every disagreement. It
never reads a component to learn what the package should say, and it changes
nothing.

Run against an assembled package, the facts come from that package's own
interpreter (``environment_facts``), so a stale or substituted component is
caught here and not in a checkout.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Any, Final

from dev._paths import REPO_ROOT

from ..command_execution import run_command
from .application_environment import (
    DECLARATION,
    ApplicationEnvironment,
    channel_directory,
    compile_section,
    parse,
)

LOG_RELOCATION: Final = "relocated-logs"
"""A relative diagnostic-log directory the command line must anchor beneath its storage root."""
CHANNELS: Final = ("stable", "preview")
"""The release channels a package is built for."""
_INTERPRETER_IMAGE: Final = "python"
"""The image name the declaration gives the package's own interpreter."""

# A package kind may be no wider than the component's own field: the package must never
# declare, pass or validate a value the component's schema would refuse. A narrower kind is
# fine, so a numeric kind is satisfied by a field that holds any string.
_FIELD_ACCEPTS: Final[Mapping[str, frozenset[str]]] = {
    "path": frozenset({"directory", "file", "executable"}),
    "boolean": frozenset({"boolean"}),
    "integer": frozenset({"integer", "port"}),
    "number": frozenset({"number", "integer"}),
    "language": frozenset({"language"}),
    "text": frozenset({"text", "language", "integer", "number", "boolean", "port"}),
}


@dataclass(frozen=True)
class Finding:
    """One disagreement between the package's declaration and an installed component."""

    check: str
    subject: str
    message: str

    def render(self) -> str:
        """Spell the finding on one line."""
        return f"[{self.check}] {self.subject}: {self.message}"


@dataclass(frozen=True)
class Reference:
    """The package's declaration, resolved for one build target: the side every comparison trusts."""

    declaration: ApplicationEnvironment
    section: Mapping[str, Any]
    layout: Mapping[str, Any]
    agent: Mapping[str, Any]
    family: str

    @property
    def windows(self) -> bool:
        """Whether the target's environment names compare without case."""
        return self.family == "windows"


def reference_from_text(text: str, layout: Mapping[str, Any]) -> Reference:
    """Validate the declaration's text and resolve it for ``layout``'s target."""
    declaration = parse(text)
    section = compile_section(declaration, layout)
    return Reference(declaration, section, layout, tomllib.loads(text)["agent"], str(section["platform_family"]))


def load_reference(source: Path, layout: Mapping[str, Any]) -> Reference:
    """Read the declaration under ``source`` and resolve it for ``layout``'s target."""
    return reference_from_text((source / DECLARATION).read_text(encoding="utf-8"), layout)


def installed_platform() -> str:
    """Name this host's installed-default platform in the declaration's own tokens."""
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


def build_request(reference: Reference) -> dict[str, Any]:
    """Describe the caller's environment the installed components are asked about.

    It holds every operating-system name the declaration's bases list, at an
    absolute sample path, and names no component may forward or honour: a
    foreign credential, the agent's settings file and the root itself.
    """
    sample = (lambda name: f"C:\\conformance\\{name}") if reference.windows else (lambda name: f"/conformance/{name}")
    declaration = reference.declaration
    received = {name: sample(name) for group in declaration.base[reference.family].values() for name in group}
    for name in ("ANTHROPIC_API_KEY", "AWS_SECRET_ACCESS_KEY", declaration.root["variable"]):
        received[name] = "conformance-noise"
    received.update(dict.fromkeys(reference.agent["never_admitted"], "conformance-noise"))
    return {"received": received, "channels": list(CHANNELS), "log_relative": LOG_RELOCATION}


def _fold(reference: Reference, name: str) -> str:
    return name.upper() if reference.windows else name


def _accepts(label: str | None, kind: str) -> bool:
    return label is not None and kind in _FIELD_ACCEPTS.get(label, frozenset())


def _reads(subject: str, reader: str, name: str, kind: str, settings: Mapping[str, str | None]) -> list[Finding]:
    if name not in settings:
        return [Finding(subject, name, f"{reader} reads no such setting")]
    label = settings[name]
    if label is None:
        return [Finding(subject, name, f"{reader} names it without a settings field to hold a value")]
    if label == "secret":
        return [Finding(subject, name, f"{reader} holds a credential in it; a package name never carries one")]
    if not _accepts(label, kind):
        return [Finding(subject, name, f"the package declares kind {kind}, wider than {reader}'s {label} field")]
    return []


def check_command_line_names(reference: Reference, cli: Mapping[str, Any]) -> list[Finding]:
    """Hold every name the package sets, passes or lets an operator override to what the command line reads."""
    check, reader = "command-line-names", "the command line"
    declaration = reference.declaration
    settings = cli["settings"]
    findings: list[Finding] = []
    for name, entry in declaration.names.items():
        role, kind = entry["role"], entry["kind"]
        if role in {"location", "operator"}:
            findings += _reads(check, reader, name, kind, settings)
        elif role == "package":
            if name in settings:
                findings += _reads(check, reader, name, kind, settings)
            elif name != declaration.path_external:
                findings.append(Finding(check, name, "neither the command line reads it nor the host consumes it"))
        elif role == "pin":
            if name not in cli["temporary_variables"]:
                findings.append(Finding(check, name, "is pinned as a temporary variable the command line does not use"))
        elif role == "fixed":
            if name == declaration.authority.name:
                findings += _reads(check, reader, name, kind, settings)
                if name not in cli["authority_variables"]:
                    findings.append(Finding(check, name, "is not the setting that names the command line's authority"))
        elif not name.startswith(reference.agent["prefix"]):
            findings.append(Finding(check, name, f"role {role} is read by no installed component"))
    if set(declaration.temporary) != set(cli["temporary_variables"]):
        findings.append(
            Finding(
                check,
                "temporary variables",
                f"the package pins {sorted(declaration.temporary)}; the command line pins {cli['temporary_variables']}",
            )
        )
    return findings


def gateway_profile(reference: Reference, arguments: Sequence[str]) -> Mapping[str, Any] | None:
    """Return the declared profile whose invocation is exactly the runtime's gateway invocation."""
    for invocation in reference.section["invocations"]:
        if [argument.get("literal") for argument in invocation["arguments"]] == list(arguments):
            return next(
                profile for profile in reference.section["profiles"] if profile["name"] == invocation["profile"]
            )
    return None


def _admitted(profile: Mapping[str, Any]) -> set[str]:
    return {
        *profile["base"],
        *profile["operator"],
        *profile["pass"],
        *(slot["name"] for slot in profile["slots"]),
        *(value["name"] for value in profile["fixed"]),
    }


def _admits_by_prefix(reference: Reference, profile: Mapping[str, Any], name: str) -> bool:
    prefix = profile["prefix"]
    refused = {_fold(reference, other) for other in profile["prefix_refused"]}
    folded = _fold(reference, name)
    return bool(prefix) and folded.startswith(prefix) and len(name) > len(prefix) and folded not in refused


def check_agent(reference: Reference, runtime: Mapping[str, Any], agent: Mapping[str, Any] | None) -> list[Finding]:
    """Hold the agent image's names to the bundled agent's own settings, credentials and worker handover.

    The gateway and worker admit the agent's names by its prefix, so no agent setting is listed:
    what is compared is the prefix, the contract version, the declared slots, the names never
    admitted, and that every name the gateway writes for its worker reaches the worker.
    """
    check = "agent-names"
    if agent is None:
        return [Finding(check, "bundled agent", "is not installed in the interpreter under test")]
    findings: list[Finding] = []
    declared = reference.agent
    if agent["prefix"] != declared["prefix"]:
        findings.append(
            Finding(check, "prefix", f"the package says {declared['prefix']!r}, the agent {agent['prefix']!r}")
        )
    if agent["hosting_contract"] != declared["hosting_contract"]:
        findings.append(
            Finding(
                check,
                "hosting contract",
                f"the package declares version {declared['hosting_contract']}; "
                f"the agent speaks {agent['hosting_contract']}",
            )
        )
    if agent["settings_file_variable"] not in declared["never_admitted"]:
        findings.append(Finding(check, agent["settings_file_variable"], "is the agent's settings file and is admitted"))
    for name, entry in reference.declaration.names.items():
        if name.startswith(declared["prefix"]):
            label = agent["settings"].get(name)
            if label is None:
                findings.append(Finding(check, name, "the bundled agent reads no such setting"))
            elif not _accepts(label, entry["kind"]):
                findings.append(
                    Finding(check, name, f"the package declares kind {entry['kind']}, wider than the agent's {label}")
                )
    gateway = gateway_profile(reference, runtime["gateway_arguments"])
    profiles = [profile for profile in reference.section["profiles"] if profile["image"] == declared["image"]]
    # A credential is never a name the package declares; one the prefix admits meets the agent's own refusals.
    for profile in profiles:
        findings.extend(
            Finding(check, name, f"is a credential the agent holds, declared for {profile['name']}")
            for name in sorted(_admitted(profile) & set(agent["credentials"]))
        )
    writes = set(agent["worker_environment_writes"])
    if not writes:
        findings.append(Finding(check, "worker handover", "found no environment the gateway writes for its worker"))
    worker = [
        profile
        for profile in profiles
        if gateway is not None and profile["name"] != gateway["name"] and profile["prefix"]
    ]
    if gateway is not None and not worker:
        findings.append(Finding(check, "worker handover", "no agent profile but the gateway's admits the prefix"))
    for profile in worker:
        slots = {slot["name"] for slot in profile["slots"]}
        findings.extend(
            Finding(check, name, f"the gateway writes it for its worker, which {profile['name']} does not admit")
            for name in sorted(writes)
            if name not in slots and name not in profile["pass"] and not _admits_by_prefix(reference, profile, name)
        )
    return findings


def check_runtime_launch(reference: Reference, runtime: Mapping[str, Any]) -> list[Finding]:
    """Hold the runtime's agent launch to the gateway profile: its invocation, its slots and nothing else."""
    check = "runtime-launch"
    gateway = gateway_profile(reference, runtime["gateway_arguments"])
    if gateway is None:
        return [Finding(check, "gateway invocation", f"no declared invocation is {runtime['gateway_arguments']}")]
    findings: list[Finding] = []
    slots = {slot["name"] for slot in gateway["slots"]}
    runtime_slots = set(runtime["gateway_slots"])
    findings.extend(
        Finding(check, name, "is a declared gateway slot the runtime does not fill")
        for name in sorted(slots - runtime_slots)
    )
    findings.extend(
        Finding(check, name, "is a slot the runtime fills that the gateway does not declare")
        for name in sorted(runtime_slots - slots)
    )
    composed = {_fold(reference, name) for name in runtime["composed"]}
    base = {_fold(reference, name) for name in gateway["base"]}
    pins = {_fold(reference, name) for name in reference.section["pins"]["temporary"]}
    declared_slots = {_fold(reference, name) for name in slots}
    advertised = {_fold(reference, name) for name in runtime["advertised_variables"]}
    admitted_by_prefix = {name for name in advertised if _admits_by_prefix(reference, gateway, name)}
    findings.extend(
        Finding(
            check, name, "is advertised to the agent, and the gateway profile does not admit it by the agent's prefix"
        )
        for name in sorted(advertised - admitted_by_prefix)
    )
    findings.extend(
        Finding(check, name, "is advertised to the agent and declared as a launch slot")
        for name in sorted(advertised & declared_slots)
    )
    unadmitted = composed - declared_slots - base - pins - {"PATH"} - admitted_by_prefix
    findings.extend(
        Finding(check, name, "is written by the composer, and the gateway profile does not admit it")
        for name in sorted(unadmitted)
    )
    findings.extend(
        Finding(check, name, "is an advertised name the composer does not write")
        for name in sorted(advertised - composed)
    )
    findings.extend(
        Finding(check, name, "is a declared gateway slot the composer does not write")
        for name in sorted(declared_slots - composed)
    )
    findings.extend(
        Finding(check, name, "is an operating-system name the gateway profile admits and the composer omits")
        for name in sorted(base - composed)
    )
    section = reference.section
    fixed = {value["name"]: value for profile in section["profiles"] for value in profile["fixed"]}
    bundled = set(reference.layout.get("bundled_images", {}))
    agent_variable, relay_variable = runtime["agent_variable"], runtime["relay_variable"]
    aeat_variable, python_variable = runtime["program_variables"]
    agent_fixed, relay_fixed = fixed.get(agent_variable), fixed.get(relay_variable)
    aeat_fixed, python_fixed = fixed.get(aeat_variable), fixed.get(python_variable)
    if agent_fixed is None or agent_fixed["source"] != "image" or agent_fixed["value"] not in bundled:
        findings.append(Finding(check, agent_variable, "is not fixed as the path of a bundled agent image"))
    for variable, program in ((relay_variable, relay_fixed), (aeat_variable, aeat_fixed)):
        if program is None or program["source"] != "image" or program["value"] not in reference.layout["entrypoints"]:
            findings.append(Finding(check, variable, "is not fixed as the path of an entrypoint image"))
    if python_fixed is None or python_fixed["source"] != "image" or python_fixed["value"] != _INTERPRETER_IMAGE:
        findings.append(Finding(check, python_variable, "is not fixed as the path of the package's interpreter image"))
    reads_it = {agent_variable, relay_variable, aeat_variable, python_variable, reference.declaration.authority.name}
    findings.extend(
        Finding(check, name, "is fixed by the package and read by no installed component")
        for name in sorted(set(fixed) - reads_it)
    )
    return findings


def check_native_host(reference: Reference, runtime: Mapping[str, Any]) -> list[Finding]:
    """Hold the runtime's reserved native-host exit range and refusal codes to the declaration."""
    check = "native-host"
    declared = reference.declaration.native_host
    findings: list[Finding] = []
    owned = [item for item in runtime["reserved_exit_codes"] if item["owner"] == declared["owner"]]
    if len(owned) != 1:
        return [Finding(check, declared["owner"], f"the runtime reserves {len(owned)} ranges for this owner, not one")]
    if (owned[0]["first"], owned[0]["last"]) != (declared["first"], declared["last"]):
        findings.append(
            Finding(
                check,
                declared["owner"],
                f"the package reserves {declared['first']}-{declared['last']}; "
                f"the runtime reserves {owned[0]['first']}-{owned[0]['last']}",
            )
        )
    for other in runtime["reserved_exit_codes"]:
        if other is not owned[0] and not (other["last"] < declared["first"] or other["first"] > declared["last"]):
            findings.append(Finding(check, other["owner"], "overlaps the native host's reserved range"))
    if runtime["launch_profile_refused"] != declared["launch_profile_refused"]:
        findings.append(
            Finding(
                check,
                "launch_profile_refused",
                f"the package exits {declared['launch_profile_refused']}; "
                f"the runtime reads {runtime['launch_profile_refused']}",
            )
        )
    if list(runtime["native_refusals"]) != list(declared["refusals"]):
        findings.append(
            Finding(
                check,
                "refusal codes",
                f"the package writes {list(declared['refusals'])}; "
                f"the runtime reads {list(runtime['native_refusals'])}",
            )
        )
    return findings


def expected_default_root(reference: Reference, received: Mapping[str, str]) -> dict[str, str]:
    """Evaluate the declared installed-default rule for the stable channel over ``received``, as the package does."""
    root = reference.declaration.root
    path_type: type[PurePath] = PureWindowsPath if reference.windows else PurePosixPath
    rule = next(item for item in root["installed_defaults"] if item["platform"] == installed_platform())
    lookup = {_fold(reference, name): value for name, value in received.items()}
    for candidate in rule["candidates"]:
        value = lookup.get(_fold(reference, candidate["variable"]), "").strip()
        if value and path_type(value).is_absolute():
            directory = channel_directory(root, root["channel"]["stable"])
            return {"root": str(path_type(value).joinpath(*candidate["subpath"], directory))}
    return {"refusal": "installed_base_unavailable"}


def check_storage_root(reference: Reference, cli: Mapping[str, Any], received: Mapping[str, str]) -> list[Finding]:
    """Hold the command line's built-in storage root, for each platform and channel, to the package's declared root."""
    check = "storage-root"
    declared, built_in = reference.declaration.root, cli["root"]
    findings: list[Finding] = []
    for key, expected in built_in.items():
        if declared[key] != expected:
            findings.append(
                Finding(check, key, f"the package declares {declared[key]!r}; the command line {expected!r}")
            )
    for channel in CHANNELS:
        named = channel_directory(declared, channel)
        if cli["channel_directories"].get(channel) != named:
            findings.append(
                Finding(
                    check,
                    f"channel {channel}",
                    f"the package names {named!r}; the command line {cli['channel_directories'].get(channel)!r}",
                )
            )
    expected = expected_default_root(reference, received)
    if cli["default_root"] != expected:
        findings.append(
            Finding(
                check,
                "installed default",
                f"the package resolves {expected}; the command line resolves {cli['default_root']}",
            )
        )
    return findings


def check_log_location(reference: Reference, cli: Mapping[str, Any]) -> list[Finding]:
    """Hold the command line's diagnostic-log placement to the package's, including a relative relocation."""
    check = "log-location"
    components, log = reference.declaration.components, cli["log"]
    findings: list[Finding] = []
    if log["default"] != components["logs"]:
        findings.append(
            Finding(
                check,
                "default",
                f"the package places logs at {components['logs']!r}; the command line at {log['default']!r}",
            )
        )
    if log["relocated"] != LOG_RELOCATION:
        findings.append(
            Finding(
                check,
                components["log_variable"],
                f"a relative value {LOG_RELOCATION!r} is anchored beneath the storage root by the package's host; "
                f"the command line placed it at {log['relocated']!r}",
            )
        )
    if log["file_name"] != PurePosixPath(components["log_file"]).name:
        findings.append(
            Finding(
                check,
                "log file",
                f"the package names {components['log_file']!r}; the command line {log['file_name']!r}",
            )
        )
    return findings


def conformance_findings(
    reference: Reference, facts: Mapping[str, Any], received: Mapping[str, str], *, require_agent: bool = True
) -> list[Finding]:
    """Compare every installed component's facts with the declaration and return each disagreement."""
    cli, runtime, agent = facts["cli"], facts["runtime"], facts["agent"]
    findings = [
        *check_command_line_names(reference, cli),
        *check_runtime_launch(reference, runtime),
        *check_native_host(reference, runtime),
        *check_storage_root(reference, cli, received),
        *check_log_location(reference, cli),
    ]
    if agent is not None or require_agent:
        findings += check_agent(reference, runtime, agent)
    return findings


def collect_facts(python: Path, request: Mapping[str, Any], *, cwd: Path) -> dict[str, Any]:
    """Ask an interpreter what its installed components declare."""
    script = Path(__file__).with_name("environment_facts.py")
    result = run_command([str(python), str(script)], cwd=cwd, input_text=json.dumps(request), timeout_seconds=300)
    if result.returncode != 0:
        raise RuntimeError(
            f"{python} could not report its components' environment (exit {result.returncode}):\n{result.stderr}"
        )
    facts: dict[str, Any] = json.loads(result.stdout)
    return facts


def run(package: Path, manifest: str, source: Path, *, python: Path | None = None) -> int:
    """Check the package at ``package``; return 1 on any disagreement and 2 when the package cannot be asked.

    ``python`` replaces the package's own interpreter only where a caller needs
    to ask a different one; the check of an assembled package never sets it.
    """
    layout = json.loads((package / manifest).read_text(encoding="utf-8"))["layout"]
    reference = load_reference(source, layout)
    if reference.family != ("windows" if installed_platform() == "windows" else "posix"):
        sys.stderr.write("The package was built for another platform family; run its conformance check there.\n")
        return 2
    request = build_request(reference)
    interpreter = package / layout["paths"]["executable"] if python is None else python
    try:
        facts = collect_facts(interpreter, request, cwd=package)
    except (RuntimeError, ValueError, OSError) as error:
        sys.stderr.write(f"{error}\n")
        return 2
    findings = conformance_findings(reference, facts, request["received"])
    for finding in findings:
        sys.stdout.write(finding.render() + "\n")
    agent_settings = len(facts["agent"]["settings"]) if facts["agent"] else 0
    sys.stdout.write(
        f"environment conformance: {len(reference.declaration.names)} names, "
        f"{len(facts['cli']['settings'])} command line settings, {agent_settings} agent settings: "
        f"{len(findings)} disagreement(s)\n"
    )
    return 1 if findings else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Check the assembled package named on the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True, help="The assembled package's root directory.")
    parser.add_argument(
        "--manifest", default="data/package-manifest.json", help="The manifest, relative to the package."
    )
    parser.add_argument("--source", type=Path, default=REPO_ROOT, help="The source tree holding the declaration.")
    arguments = parser.parse_args(argv)
    return run(arguments.package.resolve(strict=True), arguments.manifest, arguments.source)


if __name__ == "__main__":
    raise SystemExit(main())
