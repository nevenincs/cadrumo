"""Assemble the secondary Cadrumo MCP Bundle (``.mcpb``).

The accepted distribution-readiness architecture makes the retained Python
cohort manifest the sole authority for product artifact names, versions, and
SHA-256 digests. This builder therefore accepts only a cohort validated by
``dev.packaging.python_cohort.load_python_cohort`` and embeds its exact root,
manuals, and official-data wheel bytes.

MCPB construction is deliberately not an installation or support claim. The
result is unsigned and remains unapproved until a declared client installs the
same bytes, starts the server, and completes the grounded MCP tax oracle.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Final, cast

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dev.packaging.python_cohort import PythonCohort, load_python_cohort  # noqa: E402

_MANIFEST = _HERE / "manifest.json"
_UTF_8: Final[str] = "utf-8"
_DISTRIBUTIONS: Final[tuple[str, str, str]] = (
    "cadrumo",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)
_MCP_LAUNCHER: Final[str] = "uv"
_CONSOLE_SCRIPT: Final[str] = "cadrumo-mcp"
_REQUIRED_VERSION_ENV: Final[str] = "CADRUMO_MCP_REQUIRED_VERSION"
_REQUIRED_COHORT_ENV: Final[str] = "CADRUMO_MCP_COHORT_SHA256"
_STORAGE_ROOT_ENV: Final[str] = "CADRUMO_LOCAL_STORAGE_ROOT"
_SERVER_ENTRY_POINT: Final[str] = "src/server.py"
_SERVE_ENTRY_POINT: Final[str] = "src/_serve.py"
#: The manifest launch: ``uv run --no-project`` runs the bootstrap on a bare
#: interpreter with NO project resolution, so the per-session ``uv run`` project
#: resolve/sync (robustness research F4) is paid only on the very first launch,
#: inside the bootstrap, and never again. Every later session direct-execs the
#: provisioned venv interpreter.
_LAUNCH_ARGS: Final[list[str]] = ["run", "--no-project", "--directory", "${__dirname}", _SERVER_ENTRY_POINT]
_ZIP_TIMESTAMP: Final[tuple[int, int, int, int, int, int]] = (1980, 1, 1, 0, 0, 0)
# The real server entry, run by the PROVISIONED venv interpreter. It verifies the
# installed cohort wheel digests (the digest-pinned cohort guarantee) and starts
# the server. It runs inside the venv where the cohort is installed, so
# ``distribution(name)`` sees the bundle-local wheels exactly as before.
_SERVE_SOURCE: Final[str] = """\
from __future__ import annotations

import json
import os
import hashlib
from importlib.metadata import distribution
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

EXPECTED = json.loads(os.environ["CADRUMO_MCP_COHORT_SHA256"])
ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts"
for name, expected_sha256 in EXPECTED.items():
    metadata = distribution(name)
    direct_url = json.loads(metadata.read_text("direct_url.json") or "null")
    source_url = (direct_url or {}).get("url")
    parsed = urlparse(source_url or "")
    if parsed.scheme != "file":
        raise SystemExit(f"{name} did not install from a bundle-local wheel: {source_url}")
    source = Path(url2pathname(parsed.path)).resolve(strict=True)
    if source.parent != ARTIFACTS:
        raise SystemExit(f"{name} installed from outside the MCPB: {source}")
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_sha256 = digest.hexdigest()
    if actual_sha256 != expected_sha256:
        raise SystemExit(
            f"{name} installed digest drifted: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )

from cadrumo.entrypoints.mcp import main

if __name__ == "__main__":
    main()
"""
# The self-healing bootstrap launched by ``uv run --no-project`` (``src/server.py``).
# On the first launch it provisions the bundle-local ``.venv`` once (``uv sync``),
# recording the cohort digest in a marker; every launch then execs that provisioned
# interpreter directly on ``src/_serve.py``, so no session after the first pays uv's
# project resolution. A marker keyed by the cohort digest re-provisions after a
# version upgrade; the digest-pin verification in ``_serve.py`` remains the final
# guard against serving a mismatched cohort.
_BOOTSTRAP_SOURCE: Final[str] = """\
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_BUNDLE = Path(__file__).resolve().parents[1]
_VENV = _BUNDLE / ".venv"
_MARKER = _VENV / ".cadrumo-cohort"
_SERVE = _BUNDLE / "src" / "_serve.py"


def _cohort_digest():
    return os.environ.get("CADRUMO_MCP_COHORT_SHA256", "")


def _venv_python():
    if sys.platform == "win32":
        return _VENV / "Scripts" / "python.exe"
    return _VENV / "bin" / "python"


def _is_provisioned(python):
    try:
        return python.is_file() and _MARKER.read_text(encoding="utf-8") == _cohort_digest()
    except OSError:
        return False


def _provision():
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv is required to provision the Cadrumo MCP environment on first launch")
    result = subprocess.run(
        [uv, "sync", "--directory", str(_BUNDLE)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit("Cadrumo MCP environment provisioning failed")
    _MARKER.write_text(_cohort_digest(), encoding="utf-8")


def main():
    python = _venv_python()
    if not _is_provisioned(python):
        _provision()
    if sys.platform == "win32":
        # CPython's os.exec* on Windows joins argv with spaces WITHOUT
        # quoting, so a bundle under a spaced path (every real install:
        # "...\\Claude Extensions\\...") hands the child a word-split
        # command line and it tries to open half of its own interpreter
        # path as the script. Supervise instead; the extra shim process
        # still skips uv resolution on every warm launch.
        raise SystemExit(subprocess.call([str(python), str(_SERVE)]))
    os.execv(str(python), [str(python), str(_SERVE)])


if __name__ == "__main__":
    main()
"""


class ManifestError(ValueError):
    """Raised when the bundle template or supplied cohort is invalid."""


def load_cohort(cohort_dir: Path) -> PythonCohort:
    """Load the canonical immutable Python cohort without a second schema."""
    try:
        return load_python_cohort(cohort_dir.expanduser())
    except (FileNotFoundError, json.JSONDecodeError, OSError, SystemExit) as exc:
        raise ManifestError(f"invalid Python cohort: {exc}") from exc


def _product_wheels(cohort: PythonCohort) -> tuple[Path, Path, Path]:
    return (cohort.root_wheel, cohort.manuals_wheel, cohort.official_wheel)


def _product_sha256(cohort: PythonCohort) -> dict[str, str]:
    """Select product wheel digests from the canonical cohort manifest."""
    return {name: cohort.sha256[name] for name in _DISTRIBUTIONS}


def load_manifest() -> dict[str, object]:
    """Load and validate the committed MCPB v0.4 manifest template."""
    data = json.loads(_MANIFEST.read_text(encoding=_UTF_8))
    if not isinstance(data, dict):
        raise ManifestError("manifest.json must be a JSON object")
    required = ("manifest_version", "name", "version", "description", "author", "server")
    missing = [key for key in required if key not in data]
    if missing:
        raise ManifestError(f"manifest.json missing required fields: {', '.join(missing)}")
    if data["manifest_version"] != "0.4":
        raise ManifestError("manifest.json must use MCPB manifest_version 0.4")
    server = data["server"]
    if not isinstance(server, dict):
        raise ManifestError("manifest.json 'server' must be an object")
    if server.get("type") != "uv" or server.get("entry_point") != _SERVER_ENTRY_POINT:
        raise ManifestError("manifest server must be the bundled UV launcher at src/server.py")
    mcp_config = server.get("mcp_config")
    if not isinstance(mcp_config, dict):
        raise ManifestError("manifest server.mcp_config must be an object")
    if mcp_config.get("command") != _MCP_LAUNCHER:
        raise ManifestError("manifest server.mcp_config.command must be 'uv'")
    if mcp_config.get("args") != _LAUNCH_ARGS:
        raise ManifestError(
            "manifest server.mcp_config.args must launch the bundle-local bootstrap "
            "through 'uv run --no-project' so no session re-resolves the project",
        )
    env = mcp_config.get("env")
    if not isinstance(env, dict):
        raise ManifestError("manifest server.mcp_config.env must be an object")
    if set(env) != {
        _STORAGE_ROOT_ENV,
        "CADRUMO_MCP_PERSONA",
        "CADRUMO_MCP_SURFACE",
    }:
        raise ManifestError("the committed manifest env must contain only user-config passthrough")
    compatibility = data.get("compatibility")
    if compatibility != {"runtimes": {"python": ">=3.13,<3.14"}}:
        raise ManifestError("manifest compatibility must claim only the tested Python runtime range")
    return data


def stamped_manifest(cohort: PythonCohort) -> dict[str, object]:
    """Bind the bundle manifest to one canonical product-wheel cohort."""
    data = load_manifest()
    data["version"] = cohort.version
    server = cast("dict[str, object]", data["server"])
    mcp_config = cast("dict[str, object]", server["mcp_config"])
    env = cast("dict[str, object]", mcp_config["env"])
    env[_REQUIRED_VERSION_ENV] = cohort.version
    env[_REQUIRED_COHORT_ENV] = json.dumps(
        _product_sha256(cohort),
        sort_keys=True,
        separators=(",", ":"),
    )
    return data


def runtime_pyproject(cohort: PythonCohort) -> str:
    """Render the UV project that resolves product packages from embedded wheels."""
    filenames = dict(
        zip(
            _DISTRIBUTIONS,
            (wheel.name for wheel in _product_wheels(cohort)),
            strict=True,
        ),
    )
    dependencies = "\n".join(
        (
            f'  "cadrumo[agent]=={cohort.version}",',
            f'  "cadrumo-data-manuals=={cohort.version}",',
            f'  "cadrumo-data-official=={cohort.version}",',
        ),
    )
    sources = "\n".join(f'{name} = {{ path = "artifacts/{filenames[name]}" }}' for name in _DISTRIBUTIONS)
    return (
        "[project]\n"
        'name = "cadrumo-mcpb-runtime"\n'
        f'version = "{cohort.version}"\n'
        'description = "Cohort-bound Cadrumo MCPB runtime"\n'
        'requires-python = ">=3.13,<3.14"\n'
        "dependencies = [\n"
        f"{dependencies}\n"
        "]\n\n"
        "[tool.uv.sources]\n"
        f"{sources}\n"
    )


def _stage_bundle(stage: Path, cohort: PythonCohort) -> None:
    artifacts = stage / "artifacts"
    artifacts.mkdir(parents=True)
    server = stage / "src"
    server.mkdir()
    for wheel in _product_wheels(cohort):
        destination = artifacts / wheel.name
        shutil.copy2(wheel, destination)
        if not filecmp.cmp(wheel, destination, shallow=False):
            raise ManifestError(f"staged wheel bytes drifted: {wheel}")
    (stage / "manifest.json").write_text(
        json.dumps(stamped_manifest(cohort), indent=2, ensure_ascii=False) + "\n",
        encoding=_UTF_8,
    )
    (stage / "pyproject.toml").write_text(
        runtime_pyproject(cohort),
        encoding=_UTF_8,
    )
    (server / "server.py").write_text(_BOOTSTRAP_SOURCE, encoding=_UTF_8)
    (server / "_serve.py").write_text(_SERVE_SOURCE, encoding=_UTF_8)


def _write_archive_member(
    archive: zipfile.ZipFile,
    *,
    source: Path,
    member: str,
) -> None:
    """Stream one file into the MCPB with reproducible ZIP metadata."""
    info = zipfile.ZipInfo(member, date_time=_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o100644 & 0xFFFF) << 16
    with (
        source.open("rb") as source_handle,
        archive.open(
            info,
            mode="w",
            force_zip64=True,
        ) as destination_handle,
    ):
        shutil.copyfileobj(source_handle, destination_handle, length=1024 * 1024)


def build(*, cohort_dir: Path, dist_dir: Path | None = None) -> Path:
    """Build an unsigned MCPB containing one exact immutable product cohort."""
    cohort = load_cohort(cohort_dir)
    dist = (dist_dir if dist_dir is not None else _REPO_ROOT / "dist").resolve()
    dist.mkdir(parents=True, exist_ok=True)
    bundle = dist / f"cadrumo-{cohort.version}.mcpb"
    with tempfile.TemporaryDirectory(prefix="cadrumo-mcpb-") as temporary:
        stage = Path(temporary)
        _stage_bundle(stage, cohort)
        with zipfile.ZipFile(
            bundle,
            "w",
            zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    _write_archive_member(
                        archive,
                        source=path,
                        member=path.relative_to(stage).as_posix(),
                    )
    sys.stdout.write(
        f"built {bundle} [UNSIGNED; assembly only; client installation unproved]\n",
    )
    return bundle


def main(argv: list[str] | None = None) -> int:
    """Validate the template or build one cohort-bound unsigned MCPB."""
    parser = argparse.ArgumentParser(description="Build the secondary Cadrumo MCP Bundle.")
    parser.add_argument("--check", action="store_true", help="Validate the committed manifest template.")
    parser.add_argument("--cohort-dir", type=Path, help="Canonical retained Python cohort directory.")
    parser.add_argument("--dist-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest()
        if args.check:
            sys.stdout.write(f"manifest.json valid: {manifest['name']} {manifest['version']}\n")
            return 0
        if args.cohort_dir is None:
            parser.error("--cohort-dir is required when building")
        build(cohort_dir=args.cohort_dir, dist_dir=args.dist_dir)
    except ManifestError as exc:
        sys.stderr.write(f"MCPB input invalid: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
