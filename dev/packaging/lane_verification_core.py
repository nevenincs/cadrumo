"""Execute packaging probes, build artifacts, and record verified lane evidence."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import venv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from cadrumo.core.directory_scan import iter_directory, scan_directory
from cadrumo.core.product_identity import PRODUCT_IDENTITY
from dev._paths import REPO_ROOT, UTF_8
from dev.product_environment import clean_product_env
from dev.source_tree import repository_files, snapshot

from ._distribution_limits import PYPI_FILE_CAP_BYTES
from ._distribution_names import normalise_distribution_name
from .authority_staging import stage_published_authority
from .command_execution import CommandResult, run_command
from .evidence import PackagingSmokeManifest
from .proof_ledger import (
    ProofContractError,
    record_proof,
    recorded_proofs,
)
from .python_cohort import digest_install_target
from .source_data_contract import assert_wheel_contains_source_data, expected_wheel_data_paths_from_source_tree

_UTF_8: Final[str] = UTF_8


_REPRESENTATIVE_DATA_LEAVES = (
    "registry/aeat/modelos/036/manifest.toml",
    "registry/cadrumo/user_profile/schema.toml",
    "corpus/aeat_official/disenos_registro/modelo_100/manifest.json",
)


_DATA_COMPANION_PROJECTS = tuple(
    (name, f"packaging/{name.replace('-', '_')}", f"{name.replace('-', '_')}-*.whl")
    for name in PRODUCT_IDENTITY.companion_distributions
)


def find_repo_root() -> Path:
    """Return the repository root for this module."""
    return REPO_ROOT


def build_root_snapshot(repo_root: Path, work_dir: Path) -> Path:
    """Snapshot the enumerated tree into an isolated build root.

    A working tree may carry uncommitted changes (including registry TOML
    mid-edits) that a live-tree-built artifact would sweep into a lane's
    registry-validation probes, failing them for reasons outside that lane's
    contract. In the multi-agent factory worktree the failure mode is sharper
    still: a build can straddle a peer's mid-edit, landing half of a torn
    change and none of the other half. Every lane therefore builds from an
    isolated copy of the enumerated tree rather than the live one, so a
    concurrent edit to ``repo_root`` cannot land inside a build already in
    flight.

    The enumeration omits the published registry authority, which is gitignored
    generated output, so it is staged separately; see
    :mod:`dev.packaging.authority_staging` for why that is the enumeration
    behaving correctly rather than a gap to patch in the seam itself.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    destination = work_dir / "source"
    snapshot(repo_root, repository_files(repo_root), destination)
    stage_published_authority(repo_root, destination)
    return destination


def require_executable(name: str) -> str:
    """Resolve an executable from PATH or stop with an actionable error."""
    resolved = shutil.which(name)
    if resolved is None:
        raise SystemExit(f"required executable not found on PATH: {name}")
    return resolved


def run_checked(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    expected: set[int] | None = None,
) -> CommandResult:
    """Run a subprocess and replay output only when the return code is unexpected."""
    expected_codes = {0} if expected is None else expected
    completed = run_command(argv, cwd=cwd, environment=env)
    if completed.returncode not in expected_codes:
        command = " ".join(argv)
        sys.stderr.write(f"\ncommand failed ({completed.returncode}): {command}\n")
        sys.stdout.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode or 1)
    return completed


def run_checked_marker(
    argv: list[str],
    *,
    cwd: Path,
    marker: str,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Run a child that ends with a completion marker, and require the marker.

    Five child programs across these lanes end with a print naming what they
    proved, and nothing asserted any of them: the parent read the exit code
    alone. A child that exits 0 having skipped its tail - a mis-assembled
    program string, an early return, a truncated block - was indistinguishable
    from one that ran every assertion in it. The marker is the evidence the
    tail was reached, so it is required here rather than printed into a void.
    """
    completed = run_checked(argv, cwd=cwd, env=env)
    if marker not in completed.stdout:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SystemExit(f"the child exited 0 without printing {marker!r}, so its assertions did not all run")
    return completed


def venv_bin_dir(venv_path: Path) -> Path:
    """Return the platform-specific virtualenv executable directory."""
    return venv_path / ("Scripts" if os.name == "nt" else "bin")


def venv_python_path(venv_path: Path) -> Path:
    """Return the virtualenv Python executable path."""
    executable = "python.exe" if os.name == "nt" else "python"
    return venv_bin_dir(venv_path) / executable


def venv_cadrumo_path(venv_path: Path) -> Path:
    """Return the virtualenv Cadrumo console-script path."""
    executable = "aeat.exe" if os.name == "nt" else "aeat"
    return venv_bin_dir(venv_path) / executable


def assert_cadrumo_version_output(version: CommandResult, *, context: str) -> None:
    """Require the installed CLI to project the canonical product identity."""
    if not version.stdout.startswith("CADRUMO "):
        raise SystemExit(f"unexpected aeat --version output {context}: {version.stdout!r}")


def build_wheel(repo_root: Path, work_dir: Path, uv: str, *, build_root: Path) -> Path:
    """Build the Cadrumo wheel into the smoke work directory.

    ``build_root`` is both the tree the wheel is built from and the authority
    for its expected shipped-data inventory: consulting ``repo_root`` for that
    inventory would let an unrelated checkout describe the payload of an
    otherwise isolated artifact proof. A live working tree and a snapshot
    build root are both accepted, because the inventory is the enumerated
    tree and so does not vary between them.
    """
    expected_data_paths = expected_wheel_data_paths_from_source_tree(build_root)
    wheel_dir = work_dir / "wheel"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    run_checked([uv, "build", "--wheel", "--out-dir", str(wheel_dir)], cwd=build_root)
    wheels = scan_directory(wheel_dir, pattern="cadrumo-*.whl")
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one Cadrumo wheel in {wheel_dir}; got {[wheel.name for wheel in wheels]!r}")
    assert_wheel_contains_source_data(repo_root, wheels[0], expected_data_paths)
    return wheels[0]


def build_companion_wheels(work_dir: Path, uv: str, *, build_root: Path) -> tuple[Path, Path, Path]:
    """Build the three mandatory data companions for a complete local cohort.

    Built from ``build_root`` for the same reason as :func:`build_wheel`; pass
    a :func:`build_root_snapshot` tree so the companions correspond to one
    fixed source content.
    """
    out_dir = work_dir / "companion-wheels"
    wheels: list[Path] = []
    for project_name, project_dir, wheel_glob in _DATA_COMPANION_PROJECTS:
        run_checked(
            [uv, "build", "--project", str(build_root / project_dir), "--out-dir", str(out_dir)],
            cwd=build_root,
        )
        built = scan_directory(out_dir, pattern=wheel_glob)
        if len(built) != 1:
            raise SystemExit(f"expected one {project_name} wheel in {out_dir}; got {built!r}")
        wheel = built[0]
        if wheel.stat().st_size >= PYPI_FILE_CAP_BYTES:
            raise SystemExit(
                f"{wheel.name} exceeds PyPI's 100 MB per-file cap: {wheel.stat().st_size} bytes",
            )
        wheels.append(wheel)
    if len(wheels) != 3:
        raise SystemExit(f"expected three mandatory companion wheels, got {wheels!r}")
    return wheels[0], wheels[1], wheels[2]


def build_sdist(work_dir: Path, uv: str, *, build_root: Path) -> Path:
    """Build the Cadrumo source distribution into the smoke work directory.

    Built from ``build_root`` so the sdist corresponds to one fixed source
    content rather than to whatever the shared worktree happened to hold; pass
    a :func:`build_root_snapshot` tree. This is the lane that caught a torn
    peer edit live, shipping an sdist whose ``application/aggregation`` import
    did not resolve against its own ``source_mesh`` and failing as if it were
    a packaging regression.
    """
    sdist_dir = work_dir / "sdist"
    sdist_dir.mkdir(parents=True, exist_ok=True)
    run_checked([uv, "build", "--sdist", "--out-dir", str(sdist_dir)], cwd=build_root)
    sdists = scan_directory(sdist_dir, pattern="cadrumo-*.tar.gz")
    if len(sdists) != 1:
        names = [sdist.name for sdist in sdists]
        raise SystemExit(f"expected exactly one cadrumo sdist in {sdist_dir}; got {names!r}")
    return sdists[0]


def install_wheel(
    repo_root: Path,
    work_dir: Path,
    wheel: Path,
    uv: str,
    python: str,
    *,
    extras: tuple[str, ...] = (),
    companion_wheels: tuple[Path, ...] = (),
) -> Path:
    """Install the command wheel and supplied companions into a fresh virtualenv."""
    venv_path = work_dir / "venv"
    run_checked([uv, "venv", str(venv_path), "--python", python], cwd=repo_root)
    # Digest-pinned direct URL requirements: the installer verifies every
    # artifact's bytes at install time and records the digest channel that
    # assert_installed_cohort later re-checks.
    target = digest_install_target("cadrumo", wheel, extras=extras)
    companion_targets = tuple(
        digest_install_target(normalise_distribution_name(companion.name.split("-")[0]), companion)
        for companion in companion_wheels
    )
    run_checked(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(venv_python_path(venv_path)),
            target,
            *companion_targets,
        ],
        cwd=repo_root,
    )
    run_checked([uv, "pip", "check", "--python", str(venv_python_path(venv_path))], cwd=repo_root)
    record_proof("fresh uv virtualenv install")
    record_proof("pip dependency check")
    return venv_path


def create_pip_venv(work_dir: Path, python_executable: str) -> Path:
    """Create a clean virtualenv and ensure a real ``pip`` is present.

    ``venv --with-pip`` runs ``ensurepip``, whose bundled-wheel install is
    unreliable on the uv-managed python-build-standalone interpreter this smoke
    runs under (it fails outright on the self-hosted macOS runner). When
    ensurepip fails the venv is created WITHOUT pip and pip is seeded with uv;
    the cadrumo wheel is still installed by that plain ``pip`` afterwards, so
    the "installs under real pip" contract this lane proves is preserved - only
    the bootstrap of pip itself changes.

    The interpreter is linked with the platform-default strategy (symlinks on
    POSIX, copies on Windows). A COPIED python-build-standalone binary loses its
    ``@executable_path``-relative ``libpython`` on macOS and aborts (SIGABRT) on
    every launch; a symlink resolves through to the real interpreter's lib dir.
    """
    use_symlinks = os.name != "nt"
    venv_path = work_dir / "pip-venv"
    try:
        venv.EnvBuilder(with_pip=True, clear=False, symlinks=use_symlinks).create(venv_path)
    except subprocess.CalledProcessError:
        shutil.rmtree(venv_path, ignore_errors=True)
        venv.EnvBuilder(with_pip=False, clear=False, symlinks=use_symlinks).create(venv_path)
        run_checked(
            ["uv", "pip", "install", "--python", str(venv_python_path(venv_path)), "pip"],
            cwd=work_dir,
        )
    python = venv_python_path(venv_path)
    version = run_checked([str(python), "--version"], cwd=work_dir)
    requested_major_minor = ".".join(python_executable.split(".")[:2])
    if python_executable[0].isdigit() and requested_major_minor not in version.stdout:
        raise SystemExit(
            f"pip venv interpreter {version.stdout.strip()!r} does not match requested {python_executable!r}"
        )
    record_proof("stdlib venv creation")
    return venv_path


def install_targets_with_pip(
    work_dir: Path,
    targets: tuple[str, ...],
    venv_path: Path,
) -> None:
    """Install explicit local targets in one pip transaction."""
    python = venv_python_path(venv_path)
    run_checked(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            *targets,
        ],
        cwd=work_dir,
    )
    run_checked([str(python), "-m", "pip", "check"], cwd=work_dir)
    record_proof("exact local cohort install with pip")
    record_proof("pip dependency check")


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


def isolated_product_env(storage_root: Path) -> dict[str, str]:
    """Return a clean product environment rooted in isolated temporary storage."""
    return {
        **clean_product_env(),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
        "CADRUMO_DATABASE_URL": f"sqlite:///{(storage_root / 'cadrumo.db').as_posix()}",
    }


def installed_product_env(storage_root: Path, venv_path: Path) -> dict[str, str]:
    """Return isolated product state and make the selected venv the only command path.

    Installed-wheel acceptance always receives an absolute target interpreter or
    console script.  Restricting ``PATH`` as well closes the remaining route to a
    checkout-installed command or an unrelated ambient ``aeat`` executable.
    """
    environment = isolated_product_env(storage_root)
    environment.update(
        {
            "PATH": str(venv_bin_dir(venv_path.resolve())),
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    return environment


def assert_installed_data(work_dir: Path, venv_path: Path) -> None:
    """Verify representative bundled data leaves through the installed package."""
    leaves_literal = repr(list(_REPRESENTATIVE_DATA_LEAVES))
    code = f"""
from importlib.resources import files

root = files("cadrumo").joinpath("_data")
missing = []
for rel in {leaves_literal}:
    if not root.joinpath(*rel.split("/")).is_file():
        missing.append(rel)
if missing:
    raise SystemExit(f"missing installed bundled data leaves: {{missing!r}}")
print(root)
"""
    runtime_root = work_dir / "installed-data-state"
    env = installed_product_env(runtime_root, venv_path)
    run_checked([str(venv_python_path(venv_path)), "-c", code], cwd=work_dir, env=env)
    record_proof("installed bundled data resources")


def assert_attachment_and_llm_surfaces(work_dir: Path, venv_path: Path) -> None:
    """Verify installed attachment storage and LLM optional-boundary behavior."""
    runtime_root = work_dir / "runtime-surfaces"
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_root_literal = repr(str(runtime_root))
    code = f"""
from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cadrumo.adapters.outbound.llm.client import LLMClient
from cadrumo.adapters.outbound.llm.errors import LLMConfigError
from cadrumo.adapters.outbound.llm.models import LLMProvider
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.master_key.active_session import activate_session
from cadrumo.adapters.persistence.storage.master_key.bucket_session import BucketSession
from cadrumo.adapters.persistence.storage.sql import SecureObjectRepository, dispose_engine, get_engine
from cadrumo.core.config import Settings
from cadrumo.domain.attachments import (
    AttachmentBytesContent,
    AttachmentIngestionRequest,
    AttachmentKind,
    AttachmentSource,
    add_attachment,
    list_attachments,
    load_attachment,
)

root = Path({runtime_root_literal})
root.mkdir(parents=True, exist_ok=True)
settings = Settings(
    cadrumo_database_url=f"sqlite:///{{(root / 'attachments.db').as_posix()}}",
    cadrumo_local_storage_root=root / "state",
)
opened_at = datetime.now(UTC).replace(microsecond=0)
session = BucketSession.open_resumed(
    bucket_id="packaging-smoke",
    dek=os.urandom(32),
    idle_minutes=15,
    opened_at=opened_at,
    idle_deadline=opened_at + timedelta(minutes=15),
    absolute_deadline=opened_at + timedelta(minutes=15),
)
payload = b"%PDF-1.4\\n%cadrumo-packaging-attachment-smoke\\n"
try:
    engine = get_engine(settings)
    with activate_session(session):
        store = AttachmentStore(objects=SecureObjectRepository(engine=engine))
        attachment = add_attachment(
            store,
            content=AttachmentBytesContent(data=payload),
            request=AttachmentIngestionRequest(
                kind=AttachmentKind.INVOICE_PDF,
                source=AttachmentSource.LOCAL_FILE,
                source_reference="packaging-smoke.pdf",
                mime_type="application/pdf",
                captured_at=datetime.now(UTC).replace(microsecond=0),
                bucket_id="packaging-smoke",
                link_transaction_ids=("tx-packaging-smoke",),
            ),
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
    LLMClient(settings=Settings(cadrumo_local_storage_root=root / "llm-state"))._build_adapter(LLMProvider.ANTHROPIC)
except LLMConfigError as exc:
    if exc.suggestion != "pip install cadrumo[anthropic]":
        raise SystemExit(f"unexpected Anthropic install hint: {{exc.suggestion!r}}")
else:
    raise SystemExit("Anthropic adapter unexpectedly built in a core wheel install")

print("attachment-and-llm-surfaces-ok")
"""
    env = installed_product_env(runtime_root / "import-state", venv_path)
    run_checked_marker(
        [str(venv_python_path(venv_path)), "-c", code], cwd=work_dir, env=env, marker="attachment-and-llm-surfaces-ok"
    )
    record_proof("attachment storage round-trip")
    record_proof("core LLM missing-extra boundary")


def assert_cli_smoke(work_dir: Path, venv_path: Path) -> None:
    """Run installed CLI smoke checks against the clean wheel venv."""
    cadrumo = str(venv_cadrumo_path(venv_path))
    version = run_checked(
        [cadrumo, "--version"],
        cwd=work_dir,
        env=installed_product_env(work_dir / "version-state", venv_path),
    )
    assert_cadrumo_version_output(version, context="in core venv")

    default_root = work_dir / "default-check-state"
    default_env = installed_product_env(default_root, venv_path)
    default_check = run_checked(
        [cadrumo, "--format", "json", "config", "check"],
        cwd=work_dir,
        env=default_env,
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
        **installed_product_env(storage_root, venv_path),
        "CADRUMO_OUTPUT_LANGUAGE": "en",
        "CADRUMO_SECRET_PASSPHRASE": secrets.token_urlsafe(24),
        # Headless custody: the AUTO backend writes to the OS keychain, which
        # a self-hosted runner's service session refuses (macOS launchd has no
        # unlocked login keychain - AUTH_STORAGE_KEYRING_UNAVAILABLE on the
        # first run on a fresh macOS host). The passphrase-backed file backend is the
        # smoke's posture everywhere, and keeps smoke runs from writing real
        # keys into any host keychain.
    }
    create = run_checked(
        [
            cadrumo,
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
            # Choose a comunidad autónoma explicitly: leaving it unset makes the
            # create envelope carry a `ccaa_defaulted` warning notice, which
            # flips the envelope status to "warning" and reds this success probe.
            "--tax-residence-ccaa",
            "madrid",
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

    ready = run_checked([cadrumo, "--format", "json", "config", "check"], cwd=work_dir, env=env)
    ready_payload = _json_payload(ready.stdout)
    result = ready_payload.get("result", {})
    if ready_payload.get("status") != "success" or result.get("ok") is not True or result.get("issues") != []:
        raise SystemExit(f"opted-out config check did not pass cleanly: {ready_payload!r}")
    record_proof("installed CLI config/profile smoke")


def resolve_work_dir(repo_root: Path, requested: str | None, *, prefix: str = "core") -> Path:
    """Resolve a new packaging smoke work directory."""
    if requested is not None:
        path = Path(requested).resolve()
        if path.exists() and any(iter_directory(path)):
            raise SystemExit(f"--work-dir must be empty or absent: {path}")
        path.mkdir(parents=True, exist_ok=True)
        return path
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = repo_root / "var" / "packaging-smoke" / f"{prefix}-{stamp}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def relative_manifest_path(work_dir: Path, path: Path) -> str:
    """Return a stable manifest path, relative to the smoke work dir when possible."""
    resolved_work_dir = work_dir.resolve()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(resolved_work_dir).as_posix()
    except ValueError:
        return str(resolved_path)


def write_smoke_manifest(
    work_dir: Path,
    *,
    lane: str,
    artifacts: dict[str, str],
    declared: tuple[str, ...],
    details: dict[str, Any] | None = None,
) -> Path:
    """Write the record for one successful run, deriving its checks from the ledger.

    ``declared`` is the contract the form promises to satisfy. The written
    ``checks`` are the RECORDED proofs, never the declaration, so a claim cannot
    appear unless its assertion ran. A declared claim that was never recorded
    raises :class:`ProofContractError` before anything is written.

    :class:`PackagingSmokeManifest` is unchanged — ``checks`` keeps its name,
    type and schema, so every existing evidence row stays valid and readable.
    Only the provenance of the value changes, from a hand-written literal to a
    derived record.

    Raises:
        ProofContractError: On a declared claim with no recorded assertion.
    """
    recorded = recorded_proofs()
    unperformed = [claim for claim in declared if claim not in recorded]
    if unperformed:
        raise ProofContractError(
            f"{lane}: declared proofs never executed: {unperformed!r}; recorded this run: {list(recorded)!r}",
        )
    manifest = PackagingSmokeManifest(
        ok=True,
        lane=lane,
        completed_at=datetime.now(UTC),
        work_dir=str(work_dir.resolve()),
        artifacts=artifacts,
        checks=recorded,
        details=details or None,
    )
    path = work_dir / "packaging-smoke-manifest.json"
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding=_UTF_8, newline="\n")
    return path
