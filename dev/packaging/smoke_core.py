"""Build and verify the core AEAT wheel in a fresh installed environment."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tomllib
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from email.parser import Parser
from pathlib import Path
from typing import Any, Final

_UTF_8: Final[str] = "utf-8"
_REPRESENTATIVE_DATA_LEAVES = (
    "registry/aeat/modelos/036/manifest.toml",
    "registry/aeat/user_profile/schema.toml",
    "corpus/aeat_official/disenos_registro/modelo_100/manifest.json",
)
_TRACKED_DATA_ROOTS = (
    "src/aeat/_data/corpus",
    "src/aeat/_data/registry",
    "src/aeat/_data/terminology",
)
_SOURCE_DATA_PREFIX = "src/aeat/_data/"
_WHEEL_DATA_PREFIX = "aeat/_data"
_RENTA_PDF_ALLOW_LIST = {
    f"src/aeat/_data/corpus/manuals/renta/{year}/part1/source.pdf"
    for year in ("2020", "2021", "2022", "2023", "2024", "2025")
} | {"src/aeat/_data/corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf"}
_CORE_ABSENT_NAMES = {
    "anthropic",
    "google-api-python-client",
    "playwright",
    "pytest",
    "ruff",
    "semgrep",
    "sphinx",
    "torch",
}
_EXTRAS_PRESENT_NAMES = {
    "anthropic",
    "google-api-python-client",
    "playwright",
}
_DEV_PRESENT_NAMES = {
    "deptry",
    "pytest",
    "ruff",
    "sphinx",
    "torch",
}


@dataclass(frozen=True)
class CommandResult:
    """Captured subprocess result with decoded output."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class DependencySurfaces:
    """Direct dependency names declared by project, optional, and dev surfaces."""

    project_name: str
    project_names: set[str]
    project_active_names: set[str]
    optional_names: set[str]
    optional_active_names: set[str]
    extras: set[str]
    dev_names: set[str]
    dev_active_names: set[str]

    @property
    def external_optional_names(self) -> set[str]:
        """Optional dependency names excluding self-referential aggregate extras."""
        return self.optional_names - {self.project_name}

    @property
    def external_optional_active_names(self) -> set[str]:
        """Platform-active optional dependency names excluding self-references."""
        return self.optional_active_names - {self.project_name}

    @property
    def dev_only_names(self) -> set[str]:
        """Developer dependencies that are not also runtime or optional packages."""
        return self.dev_names - self.project_names - self.optional_names - {self.project_name}

    @property
    def dev_only_active_names(self) -> set[str]:
        """Platform-active developer-only dependencies."""
        return self.dev_active_names - self.project_active_names - self.optional_active_names - {self.project_name}


def _repo_root() -> Path:
    """Return the repository root for this module."""
    return Path(__file__).resolve().parents[2]


def _wsl_path_from_windows_gitdir(gitdir: str) -> Path | None:
    """Translate a Windows gitdir pointer for WSL-mounted worktrees."""
    if os.name == "nt":
        return None
    normalized = gitdir.replace("\\", "/")
    match = re.fullmatch(r"([A-Za-z]):/(.+)", normalized)
    if match is None:
        return None
    candidate = Path("/mnt") / match.group(1).lower() / match.group(2)
    if not candidate.exists():
        return None
    return candidate


def _git_env(repo_root: Path) -> dict[str, str] | None:
    """Return environment overrides for Git when WSL reads a Windows worktree."""
    dot_git = repo_root / ".git"
    if not dot_git.is_file():
        return None
    gitdir_line = dot_git.read_text(encoding=_UTF_8).strip()
    prefix = "gitdir: "
    if not gitdir_line.startswith(prefix):
        return None
    translated = _wsl_path_from_windows_gitdir(gitdir_line.removeprefix(prefix).strip())
    if translated is None:
        return None
    return {**os.environ, "GIT_DIR": str(translated), "GIT_WORK_TREE": str(repo_root)}


def _executable(name: str) -> str:
    """Resolve an executable from PATH or stop with an actionable error."""
    resolved = shutil.which(name)
    if resolved is None:
        raise SystemExit(f"required executable not found on PATH: {name}")
    return resolved


def _run(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    expected: set[int] | None = None,
) -> CommandResult:
    """Run a subprocess and replay output only when the return code is unexpected."""
    expected_codes = {0} if expected is None else expected
    result = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    completed = CommandResult(tuple(argv), result.returncode, result.stdout, result.stderr)
    if result.returncode not in expected_codes:
        command = " ".join(argv)
        sys.stderr.write(f"\ncommand failed ({result.returncode}): {command}\n")
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode or 1)
    return completed


def _normalize_name(name: str) -> str:
    """Normalize a Python distribution name per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_name(requirement: str) -> str:
    """Extract the distribution name from a dependency requirement string."""
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", requirement)
    if match is None:
        raise ValueError(f"could not parse requirement name from {requirement!r}")
    return _normalize_name(match.group(1))


def _requirement_applies_to_current_platform(requirement: str) -> bool:
    """Return whether a requirement marker applies to the current smoke platform."""
    marker = requirement.partition(";")[2].strip()
    if not marker:
        return True
    match = re.fullmatch(r"sys_platform\s*==\s*['\"]([^'\"]+)['\"]", marker)
    if match is None:
        return True
    return sys.platform == match.group(1)


def _dependency_group_name(entry: str | dict[str, Any]) -> str:
    """Extract a distribution name from a dependency-group entry."""
    if isinstance(entry, str):
        return _requirement_name(entry)
    name = entry.get("name")
    if not isinstance(name, str):
        raise ValueError(f"dependency-group entry is missing a string name: {entry!r}")
    return _normalize_name(name)


def _dependency_group_applies_to_current_platform(entry: str | dict[str, Any]) -> bool:
    """Return whether a dependency-group entry applies to the current platform."""
    if isinstance(entry, str):
        return _requirement_applies_to_current_platform(entry)
    marker = entry.get("marker")
    if not isinstance(marker, str):
        return True
    match = re.fullmatch(r"sys_platform\s*==\s*['\"]([^'\"]+)['\"]", marker.strip())
    if match is None:
        return True
    return sys.platform == match.group(1)


def _pyproject_surfaces(repo_root: Path) -> DependencySurfaces:
    """Return project, optional, extras, and dev dependency name sets from pyproject."""
    with (repo_root / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    project = pyproject["project"]
    project_name = _normalize_name(project["name"])
    project_requirements = project.get("dependencies", [])
    project_names = {_requirement_name(req) for req in project.get("dependencies", [])}
    project_active_names = {
        _requirement_name(req) for req in project_requirements if _requirement_applies_to_current_platform(req)
    }
    optional_dependencies = project.get("optional-dependencies", {})
    extras = {_normalize_name(extra) for extra in optional_dependencies}
    optional_requirements = [req for requirements in optional_dependencies.values() for req in requirements]
    optional_names = {_requirement_name(req) for req in optional_requirements}
    optional_active_names = {
        _requirement_name(req) for req in optional_requirements if _requirement_applies_to_current_platform(req)
    }
    dev_entries = pyproject.get("dependency-groups", {}).get("dev", [])
    dev_names = {_dependency_group_name(entry) for entry in dev_entries}
    dev_active_names = {
        _dependency_group_name(entry) for entry in dev_entries if _dependency_group_applies_to_current_platform(entry)
    }
    return DependencySurfaces(
        project_name=project_name,
        project_names=project_names,
        project_active_names=project_active_names,
        optional_names=optional_names,
        optional_active_names=optional_active_names,
        extras=extras,
        dev_names=dev_names,
        dev_active_names=dev_active_names,
    )


def _optional_extra_registry(repo_root: Path) -> tuple[dict[str, str], set[str]]:
    """Return capability-gated optional extras declared by the core registry."""
    source = repo_root / "src" / "aeat" / "core" / "_optional_extras.py"
    module = ast.parse(source.read_text(encoding=_UTF_8), filename=str(source))
    records_by_symbol: dict[str, tuple[str, str]] = {}
    tuple_symbols: set[str] = set()
    for node in module.body:
        assignments: tuple[tuple[ast.Name, ast.expr | None], ...] = ()
        if isinstance(node, ast.Assign):
            assignments = tuple((target, node.value) for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assignments = ((node.target, node.value),)
        for target, value in assignments:
            if target.id == "OPTIONAL_EXTRAS" and isinstance(value, ast.Tuple):
                tuple_symbols = {elt.id for elt in value.elts if isinstance(elt, ast.Name)}
                continue
            if not target.id.endswith("_EXTRA") or not isinstance(value, ast.Call):
                continue
            func = value.func
            if not isinstance(func, ast.Name) or func.id != "OptionalExtra":
                continue
            kwargs = {keyword.arg: keyword.value for keyword in value.keywords if keyword.arg is not None}
            extra = kwargs.get("extra")
            import_name = kwargs.get("import_name")
            if (
                isinstance(extra, ast.Constant)
                and isinstance(extra.value, str)
                and isinstance(import_name, ast.Constant)
                and isinstance(import_name.value, str)
            ):
                records_by_symbol[target.id] = (extra.value, import_name.value)
    if not records_by_symbol:
        raise SystemExit(f"no OptionalExtra records found in {source}")
    if not tuple_symbols:
        raise SystemExit(f"OPTIONAL_EXTRAS tuple is missing or empty in {source}")
    missing_symbols = sorted(tuple_symbols - set(records_by_symbol))
    if missing_symbols:
        raise SystemExit(f"OPTIONAL_EXTRAS references unknown symbols: {missing_symbols!r}")
    extra_to_import_name = {records_by_symbol[symbol][0]: records_by_symbol[symbol][1] for symbol in tuple_symbols}
    if len(extra_to_import_name) != len(tuple_symbols):
        raise SystemExit(f"duplicate optional-extra names in {source}: {sorted(extra_to_import_name)!r}")
    return extra_to_import_name, tuple_symbols


def _assert_optional_extra_registry_matches_pyproject(repo_root: Path) -> None:
    """Verify capability-gated optional extras match pyproject declarations."""
    with (repo_root / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    optional_dependencies = pyproject["project"].get("optional-dependencies", {})
    project_name = pyproject["project"]["name"]
    registry_extras, _symbols = _optional_extra_registry(repo_root)
    missing_pyproject = sorted(extra for extra in registry_extras if extra not in optional_dependencies)
    if missing_pyproject:
        raise SystemExit(
            f"core optional-extra registry names extras missing from pyproject.toml: {missing_pyproject!r}"
        )
    empty_pyproject = sorted(extra for extra in registry_extras if not optional_dependencies.get(extra))
    if empty_pyproject:
        raise SystemExit(f"capability-gated pyproject extras have no dependencies: {empty_pyproject!r}")
    aggregate = set(optional_dependencies.get("all", []))
    missing_aggregate = sorted(
        f"{project_name}[{extra}]" for extra in registry_extras if f"{project_name}[{extra}]" not in aggregate
    )
    if missing_aggregate:
        raise SystemExit(f"pyproject all extra is missing capability extras: {missing_aggregate!r}")


def _wheel_metadata(wheel: Path) -> tuple[list[str], set[str]]:
    """Return wheel Requires-Dist rows and Provided-Extra names."""
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = Parser().parsestr(archive.read(metadata_name).decode(_UTF_8))
    return metadata.get_all("Requires-Dist") or [], {
        _normalize_name(extra) for extra in (metadata.get_all("Provides-Extra") or [])
    }


def _format_path_sample(paths: list[str], *, limit: int = 20) -> str:
    """Format a bounded path list for actionable gate failures."""
    sample = paths[:limit]
    if len(paths) <= limit:
        return repr(sample)
    return f"{sample!r}; plus {len(paths) - limit} more"


def _tracked_source_data_paths(repo_root: Path) -> set[str]:
    """Return tracked shipped-data source paths relative to the repository root."""
    result = _run(["git", "ls-files", *_TRACKED_DATA_ROOTS], cwd=repo_root, env=_git_env(repo_root))
    tracked = {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}
    if not tracked:
        raise SystemExit("git ls-files reported no tracked shipped data under src/aeat/_data")
    outside = sorted(path for path in tracked if not path.startswith(_SOURCE_DATA_PREFIX))
    if outside:
        raise SystemExit(f"git ls-files returned paths outside {_SOURCE_DATA_PREFIX}: {outside[:10]!r}")
    absent = sorted(path for path in tracked if not (repo_root / path).is_file())
    if absent:
        raise SystemExit(
            f"{len(absent)} tracked shipped-data files are absent from the worktree: "
            f"{_format_path_sample(absent)}. Reconcile these paths before packaging: restore the tracked files, "
            "or remove them from git tracking if they were intentionally retired."
        )
    missing_allow_list = sorted(_RENTA_PDF_ALLOW_LIST - tracked)
    if missing_allow_list:
        raise SystemExit(f"tracked shipped data is missing Renta PDF allow-list files: {missing_allow_list!r}")
    return tracked


def _expected_wheel_data_paths(repo_root: Path) -> set[str]:
    """Return expected bundled-data paths inside the wheel archive."""
    expected: set[str] = set()
    for path in _tracked_source_data_paths(repo_root):
        expected.add(f"{_WHEEL_DATA_PREFIX}/{path.removeprefix(_SOURCE_DATA_PREFIX)}")
    return expected


def _assert_wheel_contains_tracked_data(repo_root: Path, wheel: Path, expected: set[str] | None = None) -> None:
    """Verify every tracked shipped-data file appears in the built wheel."""
    expected_paths = _expected_wheel_data_paths(repo_root) if expected is None else expected
    with zipfile.ZipFile(wheel) as archive:
        names = {info.filename for info in archive.infolist()}
    missing = sorted(expected_paths - names)
    if missing:
        raise SystemExit(f"wheel is missing {len(missing)} tracked shipped-data files; first ten: {missing[:10]!r}")


def _assert_wheel_metadata_matches_pyproject(repo_root: Path, wheel: Path) -> None:
    """Verify direct wheel metadata preserves prod/optional/dev intent."""
    _assert_optional_extra_registry_matches_pyproject(repo_root)
    surfaces = _pyproject_surfaces(repo_root)
    requires_dist, provided_extras = _wheel_metadata(wheel)
    core_requires = {_requirement_name(req) for req in requires_dist if "extra ==" not in req.lower()}
    optional_requires = {_requirement_name(req) for req in requires_dist if "extra ==" in req.lower()}
    all_requires = {_requirement_name(req) for req in requires_dist}
    missing_core = sorted(surfaces.project_names - core_requires)
    if missing_core:
        raise SystemExit(f"wheel metadata is missing project dependencies: {missing_core!r}")
    leaked_optional_core = sorted(surfaces.external_optional_names & core_requires)
    if leaked_optional_core:
        raise SystemExit(f"optional dependencies leaked into core wheel metadata: {leaked_optional_core!r}")
    missing_optional = sorted(surfaces.external_optional_names - optional_requires)
    if missing_optional:
        raise SystemExit(f"wheel metadata is missing optional dependency rows: {missing_optional!r}")
    missing_extras = sorted(surfaces.extras - provided_extras)
    if missing_extras:
        raise SystemExit(f"wheel metadata is missing optional extras: {missing_extras!r}")
    leaked_dev = sorted(surfaces.dev_only_names & all_requires)
    if leaked_dev:
        raise SystemExit(f"dev-only dependencies leaked into wheel metadata: {leaked_dev!r}")


def _export_names(output: str) -> set[str]:
    """Return normalized package names from a requirements export."""
    names: set[str] = set()
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        names.add(_requirement_name(stripped))
    return names


def _assert_export_surface(
    name: str, names: set[str], *, present: set[str] = frozenset(), absent: set[str] = frozenset()
) -> None:
    """Assert selected packages are present or absent from one uv export."""
    missing = sorted(present - names)
    if missing:
        raise SystemExit(f"{name} export is missing expected packages: {missing!r}")
    leaked = sorted(absent & names)
    if leaked:
        raise SystemExit(f"{name} export contains packages outside its surface: {leaked!r}")


def _validate_frozen_exports(repo_root: Path, uv: str) -> None:
    """Validate frozen lock exports for core, optional-runtime, and dev surfaces."""
    surfaces = _pyproject_surfaces(repo_root)
    _run([uv, "lock", "--check"], cwd=repo_root)
    core = _run(
        [uv, "export", "--frozen", "--no-dev", "--no-emit-project", "--no-hashes"],
        cwd=repo_root,
    )
    extras = _run(
        [uv, "export", "--frozen", "--all-extras", "--no-dev", "--no-emit-project", "--no-hashes"],
        cwd=repo_root,
    )
    dev = _run(
        [uv, "export", "--frozen", "--all-extras", "--all-groups", "--no-emit-project", "--no-hashes"],
        cwd=repo_root,
    )
    core_names = _export_names(core.stdout)
    extras_names = _export_names(extras.stdout)
    dev_names = _export_names(dev.stdout)
    _assert_export_surface(
        "core",
        core_names,
        present=surfaces.project_active_names,
        absent=surfaces.external_optional_active_names | surfaces.dev_only_active_names | _CORE_ABSENT_NAMES,
    )
    _assert_export_surface(
        "extras",
        extras_names,
        present=surfaces.project_active_names | surfaces.external_optional_active_names | _EXTRAS_PRESENT_NAMES,
        absent=surfaces.dev_only_active_names,
    )
    _assert_export_surface(
        "dev",
        dev_names,
        present=surfaces.project_active_names
        | surfaces.external_optional_active_names
        | surfaces.dev_active_names
        | _DEV_PRESENT_NAMES,
    )


def _venv_bin(venv: Path) -> Path:
    """Return the platform-specific virtualenv executable directory."""
    return venv / ("Scripts" if os.name == "nt" else "bin")


def _venv_python(venv: Path) -> Path:
    """Return the virtualenv Python executable path."""
    executable = "python.exe" if os.name == "nt" else "python"
    return _venv_bin(venv) / executable


def _venv_aeat(venv: Path) -> Path:
    """Return the virtualenv AEAT console-script path."""
    executable = "aeat.exe" if os.name == "nt" else "aeat"
    return _venv_bin(venv) / executable


def _build_wheel(repo_root: Path, work_dir: Path, uv: str) -> Path:
    """Build the AEAT wheel into the smoke work directory."""
    expected_data_paths = _expected_wheel_data_paths(repo_root)
    wheel_dir = work_dir / "wheel"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    _run([uv, "build", "--wheel", "--out-dir", str(wheel_dir)], cwd=repo_root)
    wheels = sorted(wheel_dir.glob("aeat-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one aeat wheel in {wheel_dir}; got {[wheel.name for wheel in wheels]!r}")
    _assert_wheel_contains_tracked_data(repo_root, wheels[0], expected_data_paths)
    return wheels[0]


def _install_wheel(
    repo_root: Path,
    work_dir: Path,
    wheel: Path,
    uv: str,
    python: str,
    *,
    extras: tuple[str, ...] = (),
) -> Path:
    """Install the built wheel into a fresh virtualenv and return the venv path."""
    venv = work_dir / "venv"
    _run([uv, "venv", str(venv), "--python", python], cwd=repo_root)
    target = str(wheel) if not extras else f"aeat[{','.join(extras)}] @ {wheel.resolve().as_uri()}"
    _run(
        [uv, "pip", "install", "--python", str(_venv_python(venv)), target],
        cwd=repo_root,
    )
    _run([uv, "pip", "check", "--python", str(_venv_python(venv))], cwd=repo_root)
    return venv


def _json_payload(output: str) -> dict[str, Any]:
    """Parse a CLI JSON envelope from subprocess stdout."""
    start = output.find("{")
    if start < 0:
        raise SystemExit(f"command did not emit a JSON envelope: {output!r}")
    try:
        payload = json.loads(output[start:])
    except json.JSONDecodeError as exc:
        raise SystemExit(f"command emitted invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"command JSON envelope was not an object: {payload!r}")
    return payload


def _assert_installed_data(work_dir: Path, venv: Path) -> None:
    """Verify representative bundled data leaves through the installed package."""
    leaves_literal = repr(list(_REPRESENTATIVE_DATA_LEAVES))
    code = f"""
from importlib.resources import files

root = files("aeat").joinpath("_data")
missing = []
for rel in {leaves_literal}:
    if not root.joinpath(*rel.split("/")).is_file():
        missing.append(rel)
if missing:
    raise SystemExit(f"missing installed bundled data leaves: {{missing!r}}")
print(root)
"""
    _run([str(_venv_python(venv)), "-c", code], cwd=work_dir)


def _assert_attachment_and_llm_surfaces(work_dir: Path, venv: Path) -> None:
    """Verify installed attachment storage and LLM optional-boundary behavior."""
    runtime_root = work_dir / "runtime-surfaces"
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_root_literal = repr(str(runtime_root))
    code = f"""
from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path

from aeat.adapters.outbound.llm._client import LLMClient
from aeat.adapters.outbound.llm._errors import LLMConfigError
from aeat.adapters.outbound.llm._models import LLMProvider
from aeat.adapters.persistence.storage.attachment import AttachmentStore
from aeat.adapters.persistence.storage.master_key import activate_session
from aeat.adapters.persistence.storage.master_key._bucket_session import BucketSession
from aeat.adapters.persistence.storage.sql import SecureObjectRepository, dispose_engine, get_engine
from aeat.core.config import Settings
from aeat.domain.attachments import (
    AttachmentKind,
    AttachmentSource,
    add_attachment_bytes,
    list_attachments,
    load_attachment,
)

root = Path({runtime_root_literal})
root.mkdir(parents=True, exist_ok=True)
settings = Settings(
    aeat_database_url=f"sqlite:///{{(root / 'attachments.db').as_posix()}}",
    aeat_local_storage_root=root / "state",
)
session = BucketSession.open(
    bucket_id="packaging-smoke",
    kek=os.urandom(32),
    dek=os.urandom(32),
    idle_minutes=15,
    opened_at=datetime.now(UTC).replace(microsecond=0),
    unsecured_backend=True,
)
payload = b"%PDF-1.4\\n%aeat-packaging-attachment-smoke\\n"
try:
    engine = get_engine(settings)
    with activate_session(session):
        store = AttachmentStore(objects=SecureObjectRepository(engine=engine))
        attachment = add_attachment_bytes(
            store,
            data=payload,
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="packaging-smoke.pdf",
            mime_type="application/pdf",
            captured_at=datetime.now(UTC).replace(microsecond=0),
            bucket_id="packaging-smoke",
            link_transaction_ids=("tx-packaging-smoke",),
        )
        expected = hashlib.sha256(payload).hexdigest()
        if attachment.attachment_id != expected:
            raise SystemExit(f"attachment digest mismatch: {{attachment.attachment_id}} != {{expected}}")
        if store.read_bytes(attachment.attachment_id) != payload:
            raise SystemExit("attachment bytes did not round-trip")
        loaded = load_attachment(store, attachment.attachment_id)
        if loaded.attachment_id != attachment.attachment_id:
            raise SystemExit("attachment manifest did not round-trip")
        listed = tuple(list_attachments(store))
        if [item.attachment_id for item in listed] != [attachment.attachment_id]:
            raise SystemExit(f"unexpected attachment listing: {{listed!r}}")
finally:
    session.close()
    dispose_engine(settings)

try:
    LLMClient(settings=Settings(aeat_local_storage_root=root / "llm-state"))._build_adapter(LLMProvider.ANTHROPIC)
except LLMConfigError as exc:
    if exc.suggestion != "pip install aeat[anthropic]":
        raise SystemExit(f"unexpected Anthropic install hint: {{exc.suggestion!r}}")
else:
    raise SystemExit("Anthropic adapter unexpectedly built in a core wheel install")

print("attachment-and-llm-surfaces-ok")
"""
    _run([str(_venv_python(venv)), "-c", code], cwd=work_dir)


def _assert_cli_smoke(work_dir: Path, venv: Path) -> None:
    """Run installed CLI smoke checks against the clean wheel venv."""
    aeat = str(_venv_aeat(venv))
    version = _run([aeat, "--version"], cwd=work_dir)
    if "aeat " not in version.stdout:
        raise SystemExit(f"unexpected aeat --version output: {version.stdout!r}")

    default_check = _run(
        [aeat, "--format", "json", "config", "check"],
        cwd=work_dir,
        expected={1, 2},
    )
    default_payload = _json_payload(default_check.stdout)
    if default_payload.get("status") != "success" or default_payload.get("result", {}).get("ok") is not False:
        raise SystemExit(
            f"default config check did not report typed missing-dependency diagnostics: {default_payload!r}"
        )

    storage_root = work_dir / "profile-root"
    storage_root.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "AEAT_LOCAL_STORAGE_ROOT": str(storage_root),
        "AEAT_OUTPUT_LANGUAGE": "en",
        "AEAT_SECRET_PASSPHRASE": secrets.token_urlsafe(24),
    }
    create = _run(
        [
            aeat,
            "--format",
            "json",
            "config",
            "profile",
            "create",
            "packaging-smoke",
            "--entity-type",
            "natural_person",
            "--tax-id",
            "00000000T",
            "--name",
            "Packaging",
            "--surnames",
            "Smoke",
            "--irpf-income-categories",
            "actividad_economica",
            "--quiet",
            "--accept-defaults",
            "--no-llm-vision",
            "--no-google-export",
        ],
        cwd=work_dir,
        env=env,
    )
    create_payload = _json_payload(create.stdout)
    if create_payload.get("status") != "success":
        raise SystemExit(f"profile create did not succeed: {create_payload!r}")

    ready = _run([aeat, "--format", "json", "config", "check"], cwd=work_dir, env=env)
    ready_payload = _json_payload(ready.stdout)
    result = ready_payload.get("result", {})
    if ready_payload.get("status") != "success" or result.get("ok") is not True or result.get("issues") != []:
        raise SystemExit(f"opted-out config check did not pass cleanly: {ready_payload!r}")


def _work_dir(repo_root: Path, requested: str | None, *, prefix: str = "core") -> Path:
    """Resolve a new packaging smoke work directory."""
    if requested is not None:
        path = Path(requested).resolve()
        if path.exists() and any(path.iterdir()):
            raise SystemExit(f"--work-dir must be empty or absent: {path}")
        path.mkdir(parents=True, exist_ok=True)
        return path
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = repo_root / "var" / "packaging-smoke" / f"{prefix}-{stamp}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _manifest_path(work_dir: Path, path: Path) -> str:
    """Return a stable manifest path, relative to the smoke work dir when possible."""
    resolved_work_dir = work_dir.resolve()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(resolved_work_dir).as_posix()
    except ValueError:
        return str(resolved_path)


def _write_smoke_manifest(
    work_dir: Path,
    *,
    lane: str,
    artifacts: dict[str, str],
    checks: tuple[str, ...],
    details: dict[str, Any] | None = None,
) -> Path:
    """Write a machine-readable record for one successful packaging smoke run."""
    payload: dict[str, Any] = {
        "ok": True,
        "lane": lane,
        "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "work_dir": str(work_dir.resolve()),
        "artifacts": artifacts,
        "checks": list(checks),
    }
    if details:
        payload["details"] = details
    path = work_dir / "packaging-smoke-manifest.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding=_UTF_8)
    return path


def main(argv: list[str] | None = None) -> int:
    """Run the core installed-wheel packaging smoke gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default="3.13", help="Python interpreter/version for the fresh venv.")
    parser.add_argument("--work-dir", help="Empty directory for wheel, venv, and profile smoke artifacts.")
    parser.add_argument(
        "--skip-export-checks",
        action="store_true",
        help="Skip frozen uv export surface checks and run only the installed-wheel smoke.",
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    uv = _executable("uv")
    work_dir = _work_dir(repo_root, args.work_dir)
    print(f"packaging smoke work dir: {work_dir}", flush=True)

    if not args.skip_export_checks:
        print("validating frozen dependency exports", flush=True)
        _validate_frozen_exports(repo_root, uv)

    print("building wheel", flush=True)
    wheel = _build_wheel(repo_root, work_dir, uv)
    _assert_wheel_metadata_matches_pyproject(repo_root, wheel)

    print("installing wheel into fresh venv", flush=True)
    venv = _install_wheel(repo_root, work_dir, wheel, uv, args.python)
    _assert_installed_data(work_dir, venv)
    _assert_attachment_and_llm_surfaces(work_dir, venv)
    _assert_cli_smoke(work_dir, venv)

    checks = [
        "wheel tracked shipped-data payload",
        "wheel metadata dependency surface",
        "fresh uv virtualenv install",
        "installed bundled data resources",
        "attachment storage round-trip",
        "core LLM missing-extra boundary",
        "installed CLI config/profile smoke",
    ]
    if not args.skip_export_checks:
        checks.insert(0, "frozen dependency exports")
    manifest = _write_smoke_manifest(
        work_dir,
        lane="core-wheel",
        artifacts={
            "wheel": _manifest_path(work_dir, wheel),
            "venv": _manifest_path(work_dir, venv),
        },
        checks=tuple(checks),
        details={"python": args.python},
    )

    print(f"core packaging smoke passed: {wheel}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
