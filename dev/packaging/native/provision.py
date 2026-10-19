"""Acquire the platform runtime and install the locked production dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from collections.abc import Callable, Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from packaging.utils import canonicalize_name

from dev._paths import REPO_ROOT

from ..command_execution import run_command
from ..runtime_wheel_selection import plan_target_wheels
from .agent import AGENT_DEPENDENCIES, AGENT_DEPENDENCY_RECORD, resolved_requirements
from .build_directory import require_enrolled_output
from .build_log import BuildLog, display_path
from .build_toolchain import selected_uv
from .hashing import digest
from .layout import backend, load_layout
from .product import BUNDLED_EXTRAS
from .target import toolchain_for_target, uv_environment, uv_platform

WHEEL_CACHE = "wheel-installs"
"""Beside the runtime inputs: one installed tree per pinned requirement, kept across builds."""


def _uv_install(uv: str, target: str, pin: str, requirements: Path, into: Path) -> None:
    result = run_command(
        [
            uv,
            "pip",
            "install",
            "--python",
            sys.executable,
            "--python-version",
            pin,
            "--python-platform",
            uv_platform(target),
            "--require-hashes",
            "--target",
            str(into),
            "--only-binary",
            ":all:",
            "--no-deps",
            "--link-mode",
            "copy",
            "-r",
            str(requirements),
        ],
        cwd=REPO_ROOT,
        environment=uv_environment(target),
    )
    if result.returncode:
        raise RuntimeError(result.stderr)


def tree_files(root: Path) -> dict[str, str]:
    """Every regular file below ``root`` by its root-relative path, with its digest."""
    found: dict[str, str] = {}
    for directory, _names, files in os.walk(root):
        for name in files:
            path = Path(directory, name)
            if not path.is_symlink():
                found[path.relative_to(root).as_posix()] = digest(path)
    return dict(sorted(found.items()))


class InstalledWheels:
    """Install each hash-pinned requirement once into its own tree, and reuse it while its bytes are intact.

    A tree is keyed by its requirement line, which names the wheel by its
    hashes, and by what shapes an install: the target platform, the Python pin
    and the interpreter. A tree whose files no longer match what was installed
    is removed and installed again.
    """

    def __init__(
        self,
        cache: Path,
        *,
        uv: str,
        target: str,
        pin: str,
        install: Callable[[str, str, str, Path, Path], None] | None = None,
    ) -> None:
        """Keep installed trees in ``cache`` for one target, Python pin and uv; ``install`` runs one install."""
        self.cache, self.uv, self.target, self.pin = cache, uv, target, pin
        self.install = _uv_install if install is None else install
        self.installed = self.reused = 0

    def key(self, line: str) -> str:
        """The cache name of one requirement line's installed tree."""
        context = json.dumps([line.strip(), self.target, self.pin, uv_platform(self.target), sys.executable])
        return hashlib.sha256(context.encode("utf-8")).hexdigest()[:32]

    def intact(self, tree: Path, manifest: Path) -> dict[str, str] | None:
        """The tree's files when they are exactly the ones its install recorded, else ``None``."""
        try:
            recorded = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(recorded, dict) or not recorded or not tree.is_dir():
            return None
        files = {str(name): str(value) for name, value in recorded.items()}
        return files if tree_files(tree) == files else None

    def tree(self, line: str) -> tuple[Path, dict[str, str]]:
        """The installed tree of one requirement line, installed now unless an intact one is kept."""
        key = self.key(line)
        tree, manifest = self.cache / key, self.cache / f"{key}.json"
        files = self.intact(tree, manifest)
        if files is not None:
            self.reused += 1
            return tree, files
        manifest.unlink(missing_ok=True)
        if tree.exists():
            shutil.rmtree(tree)
        staging = self.cache / f"{key}.installing-{os.getpid()}"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        requirement = self.cache / f"{key}.requirement-{os.getpid()}.txt"
        requirement.write_text(line.strip() + "\n", encoding="utf-8")
        try:
            self.install(self.uv, self.target, self.pin, requirement, staging)
        finally:
            requirement.unlink(missing_ok=True)
        files = tree_files(staging)
        # Published whole: a tree is either complete with its manifest or absent.
        os.replace(staging, tree)
        manifest.write_text(json.dumps(files, sort_keys=True), encoding="utf-8")
        self.installed += 1
        return tree, files


def compose(dependencies: Path, trees: list[tuple[Path, dict[str, str]]]) -> None:
    """Make the fresh ``dependencies`` the union of the installed trees, a later tree's file replacing an earlier one's.

    Files are linked from the trees, so an unchanged wheel keeps its bytes and
    file identities from one build to the next.
    """
    dependencies.mkdir(parents=True)
    for tree, files in trees:
        for name in files:
            source, destination = tree / name, dependencies / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.unlink(missing_ok=True)
            try:
                os.link(source, destination)
            except OSError:
                shutil.copy2(source, destination)


def provisioning_tools(target: str, build_toolchain: Mapping[str, Any] | None) -> dict[str, Any]:
    """Project an admitted builder decoder without changing the reviewed target pins."""
    tools = toolchain_for_target(target)
    if tools.get("cpython_archive_format") != "tar.zst":
        return tools
    if build_toolchain is None or build_toolchain.get("CADRUMO_TARGET") != target:
        raise ValueError("SDK archive provisioning requires the selected target's explicit build toolchain")
    decoder = build_toolchain.get("cpython_archive_decoder")
    if not isinstance(decoder, dict):
        raise ValueError("SDK archive provisioning requires an explicit builder decoder")
    if decoder.get("provenance") != tools.get("cpython_archive_decoder_provenance"):
        raise ValueError("SDK archive decoder provenance differs from the reviewed source pin")
    executable = decoder.get("executable")
    if not isinstance(executable, str) or not Path(executable).is_absolute() or not Path(executable).is_file():
        raise ValueError("SDK archive decoder requires an existing absolute builder executable")
    if digest(Path(executable)) != decoder.get("sha256"):
        raise ValueError("SDK archive decoder differs from its configured content identity")
    return dict(tools, cpython_archive_decoder=decoder)


def provision(
    destination: Path,
    target: str,
    *,
    build_toolchain: Mapping[str, Any] | None = None,
    uv_executable: Path | None = None,
    sdk: Path | None = None,
    agent_dependencies: Path,
) -> None:
    """Download one verified SDK and install Cadrumo's base closure with the agent's resolved additions.

    ``agent_dependencies`` is the agent build directory holding the bundle-time resolution
    of the agent wheel against both projects' locks. A distribution it names replaces
    Cadrumo's locked wheel of the same name, so one version of each ships.
    """
    destination = destination.resolve()
    uv = selected_uv(build_toolchain, executable=uv_executable)
    destination.mkdir(parents=True, exist_ok=True)
    pin = (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
    tools = provisioning_tools(target, build_toolchain)
    contract = load_layout(target)
    agent_requirements = resolved_requirements(agent_dependencies, target, pin)
    wheels = tuple(
        wheel
        for wheel in plan_target_wheels(REPO_ROOT, target, pin, extras=BUNDLED_EXTRAS)
        if canonicalize_name(wheel.distribution) not in agent_requirements
    )
    if sdk is None:
        produced = backend(contract).provision_sdk(destination, pin, tools, contract)
        if not isinstance(produced, Path):
            raise ValueError("SDK backend must return its produced directory")
        sdk = produced
        if sdk.resolve() != (destination / contract["sdk"]["root"]).resolve():
            raise ValueError("SDK backend output differs from the declared SDK root")
    elif not sdk.is_dir():
        raise ValueError("Provisioning requires the separately verified SDK target")
    requirements = destination / "requirements.txt"
    requirements.write_text(
        "".join(f"{wheel.distribution} @ {wheel.url} --hash=sha256:{wheel.sha256}\n" for wheel in wheels),
        encoding="utf-8",
    )
    dependencies = destination / "dependencies"
    if dependencies.exists():
        raise FileExistsError("Use a fresh dependency destination")
    lines = requirements.read_text(encoding="utf-8").splitlines()
    if agent_requirements:
        # The agent's resolution comes after, so a distribution it names wins.
        lines += (agent_dependencies / AGENT_DEPENDENCIES).read_text(encoding="utf-8").splitlines()
    install = InstalledWheels(destination.parent / WHEEL_CACHE, uv=uv, target=target, pin=pin)
    compose(dependencies, [install.tree(line) for line in lines if line.strip()])
    record = json.loads((agent_dependencies / AGENT_DEPENDENCY_RECORD).read_text(encoding="utf-8"))
    (destination / "runtime-inputs.json").write_text(
        json.dumps(
            {
                "target": target,
                "python": pin,
                "toolchain": {name: value for name, value in tools.items() if name.startswith("cpython_")},
                "wheels": [asdict(wheel) for wheel in wheels],
                "agent_dependencies": {
                    "requirements_sha256": digest(agent_dependencies / AGENT_DEPENDENCIES),
                    "cadrumo_lock_sha256": record["cadrumo_lock_sha256"],
                    "agent_lock_sha256": record["agent_lock_sha256"],
                    "versions": {name: str(requirement.specifier) for name, requirement in agent_requirements.items()},
                    "replaced": record["replaced"],
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log = BuildLog("provision")
    log.status(
        f"installed {len(wheels)} hash-pinned runtime wheels and {len(agent_requirements)} agent dependencies "
        f"for {target} into {display_path(dependencies)}"
    )
    log.verbose(f"{install.installed} wheels installed, {install.reused} reused from {display_path(install.cache)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=require_enrolled_output)
    parser.add_argument("--target", required=True)
    parser.add_argument("--uv", type=Path, help="Explicit uv executable for a standalone invocation")
    parser.add_argument(
        "--agent-dependencies", type=Path, required=True, help="Agent build directory holding its resolved dependencies"
    )
    parser.add_argument(
        "--build-toolchain", type=Path, help="Explicit builder toolchain JSON, required for tar.zst SDKs"
    )
    args = parser.parse_args()
    build_toolchain = None
    if args.build_toolchain is not None:
        build_toolchain = json.loads(args.build_toolchain.read_text(encoding="utf-8"))
        if not isinstance(build_toolchain, dict):
            parser.error("build toolchain must be a JSON object")
    provision(
        args.destination,
        args.target,
        build_toolchain=build_toolchain,
        uv_executable=args.uv,
        agent_dependencies=args.agent_dependencies,
    )
