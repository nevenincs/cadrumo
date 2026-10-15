"""Prove agent Python and Node/ACP dependency compatibility inside the assembled app."""

import hashlib
import importlib
import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def require(condition: bool, message: str) -> None:
    """Keep checks active with optimized interpreter invocation."""
    if not condition:
        raise AssertionError(message)


def verify_runtime(root: Path, packages: Path, manifest: dict[str, Any]) -> None:
    """Execute the shipped Node and ACP imports without a provider login or model call."""
    runtime = packages.parent
    receipt_path = runtime / "agent-runtime.json"
    require(
        manifest["files"].get(receipt_path.relative_to(root).as_posix())
        == hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "Agent runtime receipt escaped package inventory",
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(receipt["schema_version"] == 1, "Unsupported agent runtime receipt")
    require(receipt["target"] == manifest["build"]["target"], "Agent runtime targets another platform")
    node_member = "node/node.exe" if sys.platform == "win32" else "node/bin/node"
    for required in (
        node_member,
        "node_modules/@agentclientprotocol/claude-agent-acp/dist/index.js",
        "node_modules/@agentclientprotocol/claude-agent-acp/package.json",
    ):
        require(required in receipt["files"], "Agent runtime receipt omits an executed dependency")
    prefix = runtime.relative_to(root).as_posix() + "/"
    metadata = {"package.json", "package-lock.json", ".node-version", "agent-runtime.json"}
    actual_members = {
        member
        for member in manifest["files"]
        if member.startswith(prefix)
        and (member[len(prefix) :].startswith(("node/", "node_modules/")) or member[len(prefix) :] in metadata)
    }
    expected_members = {prefix + relative for relative in receipt["files"]} | {prefix + "agent-runtime.json"}
    require(actual_members == expected_members, "Installed agent runtime differs from its exact receipt inventory")
    for relative, expected in receipt["files"].items():
        path = runtime / relative
        require(path.resolve().is_relative_to(root), "Agent runtime path escapes package")
        member = path.relative_to(root).as_posix()
        require(manifest["files"].get(member) == expected, "Agent runtime file escaped package inventory")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, "Agent runtime checksum mismatch")
    for member in manifest["files"]:
        parts = PurePosixPath(member).parts
        require(
            not any(
                parts[index].casefold() == "@anthropic-ai"
                and parts[index + 1].casefold().startswith("claude-agent-sdk-")
                for index in range(len(parts) - 1)
            ),
            "Package contains a provider CLI from the adapter dependencies",
        )
    node = runtime / node_member
    adapter = runtime / "node_modules/@agentclientprotocol/claude-agent-acp"
    version = json.loads((adapter / "package.json").read_text(encoding="utf-8"))["version"]
    environment = importlib.import_module("cadrumo_agent_service.host.launch_environment").system_environment(
        os.environ
    )
    for arguments, expected in (
        ([str(node), "--version"], f"v{receipt['node_version']}"),
        ([str(node), str(adapter / "dist/index.js"), "--version"], version),
    ):
        result = subprocess.run(
            arguments, env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20
        )
        require(result.returncode == 0, "Packaged Node/ACP version invocation failed")
        require(result.stdout.strip() == expected, "Packaged Node/ACP version differs from runtime receipt")
    sys.stdout.write(f"Node {receipt['node_version']}, Claude ACP {version}, provider CLI absent from package\n")


def verify(root: Path) -> None:
    """Read only the deployed package and refuse imports from a checkout."""
    manifest = json.loads((root / "data/package-manifest.json").read_text(encoding="utf-8"))
    package_directory = manifest["layout"]["paths"]["packages"]
    require(isinstance(package_directory, str), "Package directory must be a string")
    packages = root / str(package_directory)
    require(Path(sys.executable).resolve().is_relative_to(root), "Agent test needs the package interpreter")
    require(manifest["agent"]["bundled"], "Agent is absent from the app manifest")
    verify_runtime(root, packages, manifest)
    agent = importlib.import_module("cadrumo_agent.cli.main")
    app = importlib.import_module("cadrumo")
    for module in (agent, app):
        require(module.__file__ is not None, "Package module has no installed origin")
        require(Path(str(module.__file__)).resolve().is_relative_to(packages), "Import escaped the deployed package")
    distribution = importlib.metadata.distribution("cadrumo-agent")
    require(
        Path(str(distribution.locate_file(""))).resolve() == packages.resolve(),
        "Agent metadata escaped custom site-packages",
    )
    require(distribution.version == manifest["agent"]["version"], "Installed agent version differs from manifest")
    for value in distribution.requires or ():
        requirement = Requirement(value)
        if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
            version = importlib.metadata.version(requirement.name)
            require(version in requirement.specifier, f"Incompatible agent dependency: {requirement.name}")
            require(
                manifest["distributions"][canonicalize_name(requirement.name)] == version,
                "Dependency escaped inventory",
            )
    for relative, expected in manifest["files"].items():
        prefix = f"{manifest['layout']['paths']['packages']}/cadrumo_agent"
        if relative.startswith((f"{prefix}/", f"{prefix}-")):
            require(
                hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected,
                f"Agent checksum mismatch: {relative}",
            )
    main = agent.main
    require(callable(main), "Installed agent entrypoint is not callable")
    main(["version", "--json"], standalone_mode=False)
    # The host and the bundled agent must speak one hosting contract and one credential frame.
    hosted = importlib.import_module("cadrumo_agent.control.hosting_contract")
    host = importlib.import_module("cadrumo_agent_service.host.controller")
    frame = importlib.import_module("cadrumo_agent_service.host.credential_frame")
    require(hosted.HOSTING_CONTRACT == host.HOSTING_CONTRACT, "Bundled agent speaks another hosting contract")
    require(
        hosted.CREDENTIAL_FRAME_VERSION == frame.CREDENTIAL_FRAME_VERSION,
        "Bundled agent reads another credential frame version",
    )
    sys.stdout.write(
        f"hosting contract {hosted.HOSTING_CONTRACT}, credential frame {hosted.CREDENTIAL_FRAME_VERSION}\n"
    )


if __name__ == "__main__":
    verify(Path(sys.argv[1]).resolve(strict=True))
