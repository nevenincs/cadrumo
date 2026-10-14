"""Prove agent imports and dependency compatibility inside the assembled app."""

import hashlib
import importlib
import importlib.metadata
import json
import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def require(condition: bool, message: str) -> None:
    """Keep checks active with optimized interpreter invocation."""
    if not condition:
        raise AssertionError(message)


def verify(root: Path) -> None:
    """Read only the deployed package and refuse imports from a checkout."""
    manifest = json.loads((root / "data/package-manifest.json").read_text(encoding="utf-8"))
    package_directory = manifest["layout"]["paths"]["packages"]
    require(isinstance(package_directory, str), "Package directory must be a string")
    packages = root / str(package_directory)
    require(Path(sys.executable).resolve().is_relative_to(root), "Agent test needs the package interpreter")
    require(manifest["agent"]["bundled"], "Agent is absent from the app manifest")
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
