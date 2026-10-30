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
import tempfile
import tomllib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Any, Final, cast

from dev._paths import REPO_ROOT

from ..command_execution import run_command
from .application_environment import bind_build_provisioning, parse
from .build_directory import require_enrolled_build
from .build_paths import build_paths
from .environment_compile import compile_section
from .environment_conformance_cli import accepts_kind, check_command_line_names
from .environment_conformance_types import Finding, Reference
from .environment_declaration_primitives import DECLARATION
from .environment_root import channel_directory

CHANNELS: Final = ("stable", "preview")
"""The release channels a package is built for."""
_INTERPRETER_IMAGE: Final = "python"
"""The image name the declaration gives the package's own interpreter."""

# A package kind may be no wider than the component's own field: the package must never
# declare, pass or validate a value the component's schema would refuse. A narrower kind is
# fine, so a numeric kind is satisfied by a field that holds any string.


def reference_from_text(text: str, layout: Mapping[str, Any], *, source: Path = REPO_ROOT) -> Reference:
    """Validate the declaration's text and resolve it for ``layout``'s target."""
    declaration = bind_build_provisioning(parse(text), source)
    section = compile_section(declaration, layout)
    return Reference(declaration, section, layout, tomllib.loads(text)["agent"], str(section["platform_family"]))


def load_reference(source: Path, layout: Mapping[str, Any]) -> Reference:
    """Read the declaration under ``source`` and resolve it for ``layout``'s target."""
    return reference_from_text((source / DECLARATION).read_text(encoding="utf-8"), layout, source=source)


def installed_platform() -> str:
    """Name this host's installed-default platform in the declaration's own tokens."""
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


def build_request(reference: Reference) -> dict[str, Any]:
    """Describe the caller's environment the installed components are asked about.

    It holds every operating-system name the declaration's bases list, at an
    absolute sample path, and names no component may forward or honour: a
    foreign credential, the agent's settings file and the root itself.
    """
    sample: Callable[[str], str] = (
        (lambda name: f"C:\\conformance\\{name}") if reference.windows else (lambda name: f"/conformance/{name}")
    )
    declaration = reference.declaration
    received = {name: sample(name) for group in declaration.base[reference.family].values() for name in group}
    for name in ("ANTHROPIC_API_KEY", "AWS_SECRET_ACCESS_KEY", declaration.root["variable"]):
        received[name] = "conformance-noise"
    received.update(dict.fromkeys(reference.agent["never_admitted"], "conformance-noise"))
    return {"received": received, "channels": list(CHANNELS)}


def _fold(reference: Reference, name: str) -> str:
    return name.upper() if reference.windows else name


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


def _check_agent_settings(reference: Reference, agent: Mapping[str, object], findings: list[Finding]) -> None:
    check = "agent-names"
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
    if agent["settings_file_source"]:
        findings.append(Finding(check, "settings file", "the bundled agent admits a dotenv settings source"))
    for name, entry in reference.declaration.names.items():
        if name.startswith(declared["prefix"]):
            label = cast(Mapping[str, str | None], agent["settings"]).get(name)
            if label is None:
                findings.append(Finding(check, name, "the bundled agent reads no such setting"))
            elif not accepts_kind(label, entry["kind"]):
                findings.append(
                    Finding(check, name, f"the package declares kind {entry['kind']}, wider than the agent's {label}")
                )


def _check_agent_credentials(
    agent: Mapping[str, object], profiles: list[Mapping[str, object]], findings: list[Finding]
) -> None:
    check = "agent-names"
    # A credential is never a name the package declares; one the prefix admits meets the agent's own refusals.
    for profile in profiles:
        findings.extend(
            Finding(check, name, f"is a credential the agent holds, declared for {profile['name']}")
            for name in sorted(_admitted(profile) & set(cast(Sequence[str], agent["credentials"])))
        )


def _check_one_worker(
    reference: Reference, profile: Mapping[str, object], writes: set[str], findings: list[Finding]
) -> None:
    check = "agent-names"
    slots = {slot["name"] for slot in cast(Sequence[Mapping[str, str]], profile["slots"])}
    findings.extend(
        Finding(check, name, f"the gateway writes it for its worker, which {profile['name']} does not admit")
        for name in sorted(writes)
        if name not in slots
        and name not in cast(Sequence[str], profile["pass"])
        and not _admits_by_prefix(reference, profile, name)
    )


def _check_worker_admission(
    reference: Reference,
    gateway: Mapping[str, object] | None,
    profiles: list[Mapping[str, object]],
    writes: set[str],
    findings: list[Finding],
) -> None:
    check = "agent-names"
    worker = [
        profile
        for profile in profiles
        if gateway is not None and profile["name"] != gateway["name"] and profile["prefix"]
    ]
    if gateway is not None and not worker:
        findings.append(Finding(check, "worker handover", "no agent profile but the gateway's admits the prefix"))
    for profile in worker:
        _check_one_worker(reference, profile, writes, findings)


def _check_agent_worker(
    reference: Reference,
    agent: Mapping[str, object],
    gateway: Mapping[str, object] | None,
    profiles: list[Mapping[str, object]],
    findings: list[Finding],
) -> None:
    check = "agent-names"
    _check_agent_credentials(agent, profiles, findings)
    writes = set(cast(Sequence[str], agent["worker_environment_writes"]))
    if not writes:
        findings.append(Finding(check, "worker handover", "found no environment the gateway writes for its worker"))
    _check_worker_admission(reference, gateway, profiles, writes, findings)


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
    _check_agent_settings(reference, agent, findings)
    declared = reference.agent
    gateway = gateway_profile(reference, runtime["gateway_arguments"])
    profiles = [profile for profile in reference.section["profiles"] if profile["image"] == declared["image"]]
    _check_agent_worker(reference, agent, gateway, profiles, findings)
    return findings


def _check_gateway_advertised(
    reference: Reference,
    gateway: Mapping[str, object],
    advertised: set[str],
    declared_slots: set[str],
    findings: list[Finding],
) -> None:
    check = "runtime-launch"
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


def _check_gateway_slots(
    gateway: Mapping[str, object], runtime: Mapping[str, object], findings: list[Finding]
) -> set[str]:
    check = "runtime-launch"
    slots = {slot["name"] for slot in cast(Sequence[Mapping[str, str]], gateway["slots"])}
    runtime_slots = set(cast(Sequence[str], runtime["gateway_slots"]))
    findings.extend(
        Finding(check, name, "is a declared gateway slot the runtime does not fill")
        for name in sorted(slots - runtime_slots)
    )
    findings.extend(
        Finding(check, name, "is a slot the runtime fills that the gateway does not declare")
        for name in sorted(runtime_slots - slots)
    )
    return slots


def _check_composed_names(
    reference: Reference,
    gateway: Mapping[str, object],
    composed: set[str],
    declared_slots: set[str],
    base: set[str],
    pins: set[str],
    advertised: set[str],
    findings: list[Finding],
) -> None:
    check = "runtime-launch"
    # The gateway admits every name under the agent's prefix but the never-admitted ones, so a
    # setting the composer writes there, advertised or not, reaches the agent without a listing.
    composed_by_prefix = {name for name in composed if _admits_by_prefix(reference, gateway, name)}
    passed = {_fold(reference, name) for name in cast(Sequence[str], gateway["pass"])}
    unadmitted = composed - declared_slots - base - pins - passed - {"PATH"} - composed_by_prefix
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


def _check_gateway_composition(
    reference: Reference, gateway: Mapping[str, object], runtime: Mapping[str, object], findings: list[Finding]
) -> None:
    slots = _check_gateway_slots(gateway, runtime, findings)
    composed = {_fold(reference, name) for name in cast(Sequence[str], runtime["composed"])}
    base = {_fold(reference, name) for name in cast(Sequence[str], gateway["base"])}
    pins = {_fold(reference, name) for name in reference.section["pins"]["temporary"]}
    declared_slots = {_fold(reference, name) for name in slots}
    advertised = {_fold(reference, name) for name in cast(Sequence[str], runtime["advertised_variables"])}
    _check_gateway_advertised(reference, gateway, advertised, declared_slots, findings)
    _check_composed_names(reference, gateway, composed, declared_slots, base, pins, advertised, findings)


def _check_one_entrypoint(
    reference: Reference, variable: str, program: Mapping[str, str] | None, findings: list[Finding]
) -> None:
    check = "runtime-launch"
    if program is None or program["source"] != "image" or program["value"] not in reference.layout["entrypoints"]:
        findings.append(Finding(check, variable, "is not fixed as the path of an entrypoint image"))


def _check_fixed_entrypoints(
    reference: Reference,
    bundled: set[str],
    agent_variable: str,
    relay_variable: str,
    aeat_variable: str,
    python_variable: str,
    agent_fixed: Mapping[str, str] | None,
    relay_fixed: Mapping[str, str] | None,
    aeat_fixed: Mapping[str, str] | None,
    python_fixed: Mapping[str, str] | None,
    findings: list[Finding],
) -> None:
    check = "runtime-launch"
    if agent_fixed is None or agent_fixed["source"] != "image" or agent_fixed["value"] not in bundled:
        findings.append(Finding(check, agent_variable, "is not fixed as the path of a bundled agent image"))
    for variable, program in ((relay_variable, relay_fixed), (aeat_variable, aeat_fixed)):
        _check_one_entrypoint(reference, variable, program, findings)
    if python_fixed is None or python_fixed["source"] != "image" or python_fixed["value"] != _INTERPRETER_IMAGE:
        findings.append(Finding(check, python_variable, "is not fixed as the path of the package's interpreter image"))


def _check_fixed_programs(reference: Reference, runtime: Mapping[str, object], findings: list[Finding]) -> None:
    check = "runtime-launch"
    section = reference.section
    fixed = {value["name"]: value for profile in section["profiles"] for value in profile["fixed"]}
    bundled = set(reference.layout.get("bundled_images", {}))
    agent_variable, relay_variable = cast(str, runtime["agent_variable"]), cast(str, runtime["relay_variable"])
    aeat_variable, python_variable = cast(tuple[str, str], runtime["program_variables"])
    agent_fixed, relay_fixed = fixed.get(agent_variable), fixed.get(relay_variable)
    aeat_fixed, python_fixed = fixed.get(aeat_variable), fixed.get(python_variable)
    _check_fixed_entrypoints(
        reference,
        bundled,
        agent_variable,
        relay_variable,
        aeat_variable,
        python_variable,
        agent_fixed,
        relay_fixed,
        aeat_fixed,
        python_fixed,
        findings,
    )
    reads_it = {agent_variable, relay_variable, aeat_variable, python_variable, reference.declaration.authority.name}
    findings.extend(
        Finding(check, name, "is fixed by the package and read by no installed component")
        for name in sorted(set(fixed) - reads_it)
    )


def check_runtime_launch(reference: Reference, runtime: Mapping[str, Any]) -> list[Finding]:
    """Hold the runtime's agent launch to the gateway profile: its invocation, its slots and nothing else."""
    check = "runtime-launch"
    gateway = gateway_profile(reference, runtime["gateway_arguments"])
    if gateway is None:
        return [Finding(check, "gateway invocation", f"no declared invocation is {runtime['gateway_arguments']}")]
    findings: list[Finding] = []
    _check_gateway_composition(reference, gateway, runtime, findings)
    _check_fixed_programs(reference, runtime, findings)
    return findings


def _check_native_refusals(
    declared: Mapping[str, object], runtime: Mapping[str, object], findings: list[Finding]
) -> None:
    check = "native-host"
    if runtime["launch_profile_refused"] != declared["launch_profile_refused"]:
        findings.append(
            Finding(
                check,
                "launch_profile_refused",
                f"the package exits {declared['launch_profile_refused']}; "
                f"the runtime reads {runtime['launch_profile_refused']}",
            )
        )
    if list(cast(Sequence[object], runtime["native_refusals"])) != list(cast(Sequence[object], declared["refusals"])):
        findings.append(
            Finding(
                check,
                "refusal codes",
                f"the package writes {list(cast(Sequence[object], declared['refusals']))}; "
                f"the runtime reads {list(cast(Sequence[object], runtime['native_refusals']))}",
            )
        )


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
    _check_native_refusals(declared, runtime, findings)
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
    """Hold the command line's diagnostic-log placement beneath its storage root to the package's."""
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


def run(
    package: Path,
    manifest: str,
    source: Path,
    *,
    scratch_root: Path,
    python: Path | None = None,
) -> int:
    """Check the package at ``package``; return 1 on any disagreement and 2 when the package cannot be asked.

    ``python`` replaces the package's own interpreter only where a caller needs
    to ask a different one; the check of an assembled package never sets it.
    """
    layout = json.loads((package / manifest).read_text(encoding="utf-8"))["layout"]
    reference = load_reference(source, layout)
    if reference.family != ("windows" if installed_platform() == "windows" else "posix"):
        sys.stderr.write("The package was built for another platform family; run its conformance check there.\n")
        return 2
    scratch_root.mkdir(parents=True, exist_ok=True)
    scratch_root = scratch_root.resolve(strict=True)
    interpreter = package / layout["paths"]["executable"] if python is None else python
    try:
        with tempfile.TemporaryDirectory(prefix="environment-conformance-", dir=scratch_root) as scratch:
            request: dict[str, Any] = {**build_request(reference), "scratch": scratch}
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
    parser.add_argument(
        "--build", type=require_enrolled_build, required=True, help="The owning CMake binary directory."
    )
    arguments = parser.parse_args(argv)
    paths = build_paths(arguments.build)
    return run(
        arguments.package.resolve(strict=True),
        arguments.manifest,
        arguments.source,
        scratch_root=paths["testing"],
    )


if __name__ == "__main__":
    raise SystemExit(main())
