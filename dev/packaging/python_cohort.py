"""Build, load, and verify one immutable local Python distribution cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tarfile
import zipfile
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path
from typing import Any, Final

from packaging.requirements import Requirement

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.product_identity import PRODUCT_IDENTITY
from dev._paths import REPO_ROOT, UTF_8
from dev.packaging.command_execution import CommandResult, run_command
from dev.packaging.google_oauth import build_client_json, stage_build_client
from dev.source_tree import content_digest, repository_files, snapshot

from ._distribution_limits import PYPI_FILE_CAP_BYTES
from ._distribution_names import normalise_distribution_name
from .authority_staging import stage_published_authority
from .build_scratch_reclaim import (
    COHORT_BUILD_TREE_FAMILY,
    COHORT_SOURCE_ARCHIVE_FAMILY,
    var_scratch_name,
)
from .command_spec_attestation import (
    _cached_artifact_command_projection,
    _forbidden_command_artifacts,
    _projection_digest,
    _validate_command_spec_attestation,
    attest_command_specs,
)
from .hashing import sha256_path
from .proof_ledger import record_proof
from .runtime_wheelhouse import build_runtime_wheelhouse
from .runtime_wheelhouse_reader import load_runtime_wheelhouse
from .wheel_metadata import read_wheel_metadata

_UTF_8: Final[str] = UTF_8


_MANIFEST_NAME: Final[str] = "python-cohort.json"


# ``uv build --out-dir`` writes a one-byte ``.gitignore`` (containing ``*``) into
# its output directory, so the cohort directory acquires a file no manifest can
# declare. It is build-tool bookkeeping, never an installable artifact, and is
# excluded by exact name: the closed-world inventory below must keep refusing any
# unmanifested wheel or sdist, which a broader pattern would stop doing.
_BUILD_TOOL_EMITTED_FILES: Final[frozenset[str]] = frozenset({".gitignore"})


_BUILD_TREE_SOURCE_DIR: Final[str] = "src"


_DISTRIBUTIONS: Final[tuple[str, ...]] = PRODUCT_IDENTITY.cohort_distributions


_INSTALLED_PROBE: Final[str] = (
    f"""
import json
from importlib.metadata import distribution

names = {_DISTRIBUTIONS!r}
"""
    + """items = {name: distribution(name) for name in names}
print(json.dumps({
    "versions": {name: item.version for name, item in items.items()},
    "direct_urls": {
        name: json.loads(item.read_text("direct_url.json") or "null")
        for name, item in items.items()
    },
    "root_requirements": list(items[names[0]].requires or ()),
}, sort_keys=True))
"""
)


@dataclass(frozen=True)
class PythonCohort:
    """The base command and its mandatory data-distribution artifacts."""

    directory: Path
    manifest: Path
    source_digest: str
    version: str
    root_wheel: Path
    root_sdist: Path
    source_archive: Path
    runtime_wheelhouse: Path
    runtime_wheelhouse_manifest: dict[str, Any]
    manuals_wheel: Path
    manuals_sdist: Path
    official_wheel: Path
    official_sdist: Path
    sha256: dict[str, str]
    command_spec_attestation: dict[str, object] | None = None

    @property
    def companion_wheels(self) -> tuple[Path, Path]:
        """Return the mandatory data wheels in stable install order."""
        return (self.manuals_wheel, self.official_wheel)

    @property
    def product_wheels(self) -> tuple[Path, Path, Path]:
        """Return every exact installable product wheel in stable order."""
        return (self.root_wheel, self.manuals_wheel, self.official_wheel)


def _run(argv: list[str], *, cwd: Path) -> CommandResult:
    completed = run_command(
        argv,
        cwd=cwd,
        errors="strict",
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"command failed ({completed.returncode}): {argv!r}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
    return completed


def _single(directory: Path, pattern: str, *, label: str) -> Path:
    matches = scan_directory(directory, pattern=pattern)
    if len(matches) != 1:
        raise SystemExit(
            f"expected exactly one {label} matching {pattern!r} in {directory}; "
            f"got {[path.name for path in matches]!r}",
        )
    return matches[0].resolve(strict=True)


def _wheel_identity(wheel: Path) -> tuple[str, str, tuple[str, ...]]:
    metadata = read_wheel_metadata(wheel)
    name = metadata.get("Name")
    version = metadata.get("Version")
    if not name or not version:
        raise SystemExit(f"wheel metadata lacks Name or Version: {wheel}")
    return (
        normalise_distribution_name(name),
        version,
        tuple(metadata.get_all("Requires-Dist") or ()),
    )


def _sdist_identity(sdist: Path) -> tuple[str, str, tuple[str, ...]]:
    try:
        with tarfile.open(sdist, mode="r:gz") as archive:
            metadata_names = tuple(member for member in archive.getmembers() if member.name.endswith("/PKG-INFO"))
            if len(metadata_names) != 1:
                raise SystemExit(
                    f"expected one PKG-INFO member in {sdist}; got {[member.name for member in metadata_names]!r}",
                )
            handle = archive.extractfile(metadata_names[0])
            if handle is None:
                raise SystemExit(f"could not read PKG-INFO from {sdist}")
            metadata = Parser().parsestr(handle.read().decode(_UTF_8))
    except (tarfile.TarError, UnicodeDecodeError) as exc:
        raise SystemExit(f"invalid source distribution {sdist}: {exc}") from exc
    name = metadata.get("Name")
    version = metadata.get("Version")
    if not name or not version:
        raise SystemExit(f"sdist metadata lacks Name or Version: {sdist}")
    return (
        normalise_distribution_name(name),
        version,
        tuple(metadata.get_all("Requires-Dist") or ()),
    )


def _validate_companion_pins(
    requirements: tuple[str, ...],
    *,
    version: str,
    artifact_kind: str,
) -> None:
    parsed = tuple(Requirement(row) for row in requirements)
    for companion in _DISTRIBUTIONS[1:]:
        matches = tuple(
            requirement for requirement in parsed if normalise_distribution_name(requirement.name) == companion
        )
        if len(matches) != 1:
            raise SystemExit(
                f"root {artifact_kind} must declare exactly one dependency on {companion}",
            )
        requirement = matches[0]
        if requirement.extras or requirement.marker is not None or str(requirement.specifier) != f"=={version}":
            raise SystemExit(
                f"root {artifact_kind} must require {companion}=={version} "
                f"unconditionally and without extras; found {requirement}",
            )


def _validate_wheel_contract(
    root_wheel: Path,
    manuals_wheel: Path,
    official_wheel: Path,
) -> str:
    root_name, version, requirements = _wheel_identity(root_wheel)
    manuals_name, manuals_version, _ = _wheel_identity(manuals_wheel)
    official_name, official_version, _ = _wheel_identity(official_wheel)
    observed = {
        root_name: version,
        manuals_name: manuals_version,
        official_name: official_version,
    }
    if observed != {name: version for name in _DISTRIBUTIONS}:
        raise SystemExit(
            "Python cohort distribution identities or versions drifted: "
            f"expected {{name: {version!r} for name in {_DISTRIBUTIONS!r}}}, got {observed!r}",
        )
    _validate_companion_pins(
        requirements,
        version=version,
        artifact_kind="wheel",
    )
    for wheel in (root_wheel, manuals_wheel, official_wheel):
        if wheel.stat().st_size >= PYPI_FILE_CAP_BYTES:
            raise SystemExit(
                f"{wheel.name} exceeds PyPI's 100 MB per-file cap: {wheel.stat().st_size} bytes",
            )
    return version


def _validate_sdist_contract(
    root_sdist: Path,
    manuals_sdist: Path,
    official_sdist: Path,
    *,
    expected_version: str,
) -> None:
    root_name, root_version, requirements = _sdist_identity(root_sdist)
    manuals_name, manuals_version, _ = _sdist_identity(manuals_sdist)
    official_name, official_version, _ = _sdist_identity(official_sdist)
    observed = {
        root_name: root_version,
        manuals_name: manuals_version,
        official_name: official_version,
    }
    expected = {name: expected_version for name in _DISTRIBUTIONS}
    if observed != expected:
        raise SystemExit(
            f"Python cohort sdist identities or versions drifted: expected {expected!r}, got {observed!r}",
        )
    _validate_companion_pins(
        requirements,
        version=expected_version,
        artifact_kind="sdist",
    )
    for sdist in (root_sdist, manuals_sdist, official_sdist):
        if sdist.stat().st_size >= PYPI_FILE_CAP_BYTES:
            raise SystemExit(
                f"{sdist.name} exceeds PyPI's 100 MB per-file cap: {sdist.stat().st_size} bytes",
            )


def _safe_recreate(directory: Path, *, repo_root: Path) -> None:
    resolved_repo = repo_root.resolve(strict=True)
    resolved_var = (resolved_repo / "var").resolve()
    resolved = directory.resolve()
    if resolved_var not in resolved.parents:
        raise SystemExit(f"cohort output must stay under {resolved_var}: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def _archive_source_snapshot(build_root: Path, files: Sequence[str], destination: Path) -> Path:
    """Archive an already-extracted source snapshot into one flat-member zip.

    ``build_root`` already carries ``files`` with the repository's own
    line-ending rules applied (:func:`dev.source_tree.snapshot` wrote them),
    so this reads bytes rather than renormalising them. Members are written
    at their bare relative path, matching the flat (no top-level directory)
    layout the retained source archive has always carried.
    """
    with zipfile.ZipFile(destination, mode="x", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in sorted(files):
            archive.write(build_root / relative, arcname=relative)
    return destination


def _assert_closed_cohort_inventory(cohort_dir: Path, declared_filenames: Collection[str]) -> None:
    """Refuse a cohort directory holding anything the manifest does not declare.

    The cohort directory is a closed world: the manifest plus exactly the
    artifacts it names. An extra file crosses acquisition, smoke, and promote
    gates unnoticed when only the declared names are checked, so the inventory
    is compared before any per-artifact digest work.
    """
    declared = set(declared_filenames) | {_MANIFEST_NAME}
    observed = {
        path.relative_to(cohort_dir).as_posix()
        for path in scan_directory(cohort_dir, recursive=True)
        if path.is_file() and path.name not in _BUILD_TOOL_EMITTED_FILES
    }
    if observed != declared:
        raise SystemExit(
            f"Python cohort file inventory drifted: declared={sorted(declared)!r}, observed={sorted(observed)!r}",
        )


def _sealed_lock_digest(source_archive: Path) -> str:
    """Return the digest of the ``uv.lock`` the cohort's source archive seals."""
    with zipfile.ZipFile(source_archive) as source_bundle:
        try:
            return hashlib.sha256(source_bundle.read("uv.lock")).hexdigest()
        except KeyError as exc:
            raise SystemExit("Python cohort source archive omits uv.lock") from exc


def _assert_source_archive_binds_wheelhouse(
    source_archive: Path,
    wheelhouse_manifest: dict[str, Any],
) -> None:
    """Refuse a wheelhouse resolved from a lock the sealed source does not carry."""
    if wheelhouse_manifest.get("lock_sha256") != _sealed_lock_digest(source_archive):
        raise SystemExit("runtime wheelhouse does not bind the tested uv.lock")


def build_python_cohort(repo_root: Path, output_dir: Path) -> PythonCohort:
    """Build one immutable cohort from a content snapshot and write its digest manifest.

    Returns the cohort assembled from what the build already derived -- the
    resolved artifact paths, the digests written into the manifest, the runtime
    wheelhouse this build validated, and the attestation it sealed -- rather
    than by reading the manifest back through :func:`load_python_cohort`. That
    reload re-hashed every artifact, re-walked the member projection, re-parsed
    the wheel and sdist metadata and revalidated the attestation, all against
    bytes this function had just produced and checked.

    The invariants that reload asserted which are NOT restatements of work
    already done here are kept and asserted directly: the closed-world file
    inventory, and the binding between the sealed source archive's lock and the
    wheelhouse resolved from it.
    """
    root = repo_root.resolve(strict=True)
    source_files = repository_files(root)
    source_digest = content_digest(root, source_files)
    output = output_dir.resolve()
    _safe_recreate(output, repo_root=root)
    build_root = output.parent / var_scratch_name(COHORT_BUILD_TREE_FAMILY, output.name)
    if build_root.exists():
        shutil.rmtree(build_root)
    try:
        snapshot(root, source_files, build_root)
        return _build_python_cohort_from_snapshot(
            build_root=build_root,
            output=output,
            source_files=source_files,
            source_digest=source_digest,
            authority_source_root=root,
            remove_build_root=True,
        )
    except BaseException:
        if build_root.exists():
            shutil.rmtree(build_root)
        raise


def build_python_cohort_from_clean_snapshot(
    clean_root: Path,
    output_dir: Path,
    *,
    source_files: Sequence[str],
    source_digest: str,
) -> PythonCohort:
    """Build from a release-verified clean source without copying it again.

    Only the release builder calls this path, after it has compared the supplied
    file set and digest with ``clean_root`` and staged the generated authority.
    The ordinary builder above retains its independent snapshot boundary for
    callers whose source directory may still be changing.
    """
    root = clean_root.resolve(strict=True)
    output = output_dir.resolve()
    _safe_recreate(output, repo_root=root)
    return _build_python_cohort_from_snapshot(
        build_root=root,
        output=output,
        source_files=source_files,
        source_digest=source_digest,
        authority_source_root=None,
        remove_build_root=False,
    )


def _build_python_cohort_from_snapshot(
    *,
    build_root: Path,
    output: Path,
    source_files: Sequence[str],
    source_digest: str,
    authority_source_root: Path | None,
    remove_build_root: bool,
) -> PythonCohort:
    """Build a cohort from a source tree whose identity was already verified."""
    archive = output.parent / var_scratch_name(COHORT_SOURCE_ARCHIVE_FAMILY, output.name)
    if archive.exists():
        archive.unlink()
    retained_source_archive = output / f"cadrumo-source-{source_digest}.zip"
    try:
        # The ordinary builder made this snapshot just before entering here;
        # the release builder has already verified its clean snapshot. The
        # retained archive is written from those same normalized source bytes.
        _archive_source_snapshot(build_root, source_files, archive)
        stage_build_client(build_root, build_client_json(authority_source_root or build_root))
        if authority_source_root is not None:
            # The published authority is absent from the source archive but is
            # staged into the private build root after that archive is sealed.
            stage_published_authority(authority_source_root, build_root)
        uv = shutil.which("uv")
        if uv is None:
            raise SystemExit("uv is required to build the Python cohort")
        _run([uv, "build", "--wheel", "--sdist", "--out-dir", str(output)], cwd=build_root)
        _run(
            [
                uv,
                "build",
                "--wheel",
                "--sdist",
                "--project",
                str(build_root / "packaging" / "cadrumo_data_manuals"),
                "--out-dir",
                str(output),
            ],
            cwd=build_root,
        )
        wheelhouse = build_runtime_wheelhouse(
            build_root,
            output / "cadrumo-runtime-wheelhouse.zip",
        )
        shutil.move(archive, retained_source_archive)
        _run(
            [
                uv,
                "build",
                "--wheel",
                "--sdist",
                "--project",
                str(build_root / "packaging" / "cadrumo_data_official"),
                "--out-dir",
                str(output),
            ],
            cwd=build_root,
        )
        # uv seeds its --out-dir with a `.gitignore`; that is a build-tool
        # artifact, not a release artifact, and the release-cohort completeness
        # check refuses any file the manifest does not declare.
        uv_gitignore = output / ".gitignore"
        if uv_gitignore.exists():
            uv_gitignore.unlink()

        root_wheel = _single(output, "cadrumo-*.whl", label="cadrumo wheel")
        root_sdist = _single(output, "cadrumo-*.tar.gz", label="cadrumo sdist")
        runtime_wheelhouse = _single(
            output,
            "cadrumo-runtime-wheelhouse*.zip",
            label="runtime dependency wheelhouse",
        )
        manuals_wheel = _single(
            output,
            "cadrumo_data_manuals-*.whl",
            label="manuals wheel",
        )
        official_wheel = _single(
            output,
            "cadrumo_data_official-*.whl",
            label="official wheel",
        )
        manuals_sdist = _single(
            output,
            "cadrumo_data_manuals-*.tar.gz",
            label="manuals sdist",
        )
        official_sdist = _single(
            output,
            "cadrumo_data_official-*.tar.gz",
            label="official sdist",
        )
        version = _validate_wheel_contract(
            root_wheel,
            manuals_wheel,
            official_wheel,
        )
        _validate_sdist_contract(
            root_sdist,
            manuals_sdist,
            official_sdist,
            expected_version=version,
        )
        artifacts = {
            "cadrumo": root_wheel.name,
            "cadrumo-sdist": root_sdist.name,
            "source-archive": retained_source_archive.name,
            "runtime-wheelhouse": runtime_wheelhouse.name,
            "cadrumo-data-manuals": manuals_wheel.name,
            "cadrumo-data-manuals-sdist": manuals_sdist.name,
            "cadrumo-data-official": official_wheel.name,
            "cadrumo-data-official-sdist": official_sdist.name,
        }
        sha256 = {name: sha256_path(output / filename) for name, filename in artifacts.items()}
        # Attested here, INSIDE the block that owns the build tree, because the
        # probe reads the tree `uv build` packaged the wheel from. Below this
        # block that tree is gone, and reconstructing an importable copy of it
        # costs a full unpack of the wheel that was just written from it.
        command_spec_attestation = attest_command_specs(
            site_root=(build_root / _BUILD_TREE_SOURCE_DIR).resolve(strict=True),
            root_wheel=root_wheel,
            root_sdist=root_sdist,
            source_archive=retained_source_archive,
            source_digest=source_digest,
            work_root=output.parent,
            digests=(sha256["cadrumo"], sha256["cadrumo-sdist"], sha256["source-archive"]),
        )
    finally:
        if archive.exists():
            archive.unlink()
        if remove_build_root and build_root.exists():
            shutil.rmtree(build_root)

    manifest = output / _MANIFEST_NAME
    manifest.write_text(
        json.dumps(
            {
                "artifacts": artifacts,
                "sha256": sha256,
                "source_digest": source_digest,
                "version": version,
                "command_spec_attestation": command_spec_attestation,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding=_UTF_8,
        newline="\n",
    )
    _assert_closed_cohort_inventory(output, artifacts.values())
    _assert_source_archive_binds_wheelhouse(retained_source_archive, wheelhouse.manifest)
    return PythonCohort(
        directory=output,
        manifest=manifest,
        source_digest=source_digest,
        version=version,
        root_wheel=root_wheel,
        root_sdist=root_sdist,
        source_archive=retained_source_archive,
        runtime_wheelhouse=runtime_wheelhouse,
        runtime_wheelhouse_manifest=wheelhouse.manifest,
        manuals_wheel=manuals_wheel,
        manuals_sdist=manuals_sdist,
        official_wheel=official_wheel,
        official_sdist=official_sdist,
        sha256=sha256,
        command_spec_attestation=command_spec_attestation,
    )


def _cohort_manifest_fields(document: Any) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    if not isinstance(document, dict):
        raise SystemExit("Python cohort manifest must be a JSON object")
    artifacts = document.get("artifacts")
    sha256 = document.get("sha256")
    source_digest = document.get("source_digest")
    version = document.get("version")
    if (
        not isinstance(artifacts, dict)
        or not isinstance(sha256, dict)
        or not isinstance(source_digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", source_digest) is None
        or not isinstance(version, str)
        or not version
    ):
        raise SystemExit(f"Python cohort manifest has an invalid schema: {document!r}")
    expected_keys = {
        "cadrumo",
        "cadrumo-sdist",
        "source-archive",
        "runtime-wheelhouse",
        "cadrumo-data-manuals",
        "cadrumo-data-manuals-sdist",
        "cadrumo-data-official",
        "cadrumo-data-official-sdist",
    }
    if set(artifacts) != expected_keys or set(sha256) != expected_keys:
        raise SystemExit(
            f"Python cohort manifest keys drifted: artifacts={set(artifacts)!r}, sha256={set(sha256)!r}",
        )
    return artifacts, sha256, source_digest, version


def _resolved_cohort_artifacts(cohort_dir: Path, artifacts: dict[str, Any], sha256: dict[str, Any]) -> dict[str, Path]:
    _assert_closed_cohort_inventory(cohort_dir, {str(name) for name in artifacts.values()})

    resolved: dict[str, Path] = {}
    for name in sorted(artifacts):
        filename = artifacts[name]
        digest = sha256[name]
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise SystemExit(f"cohort artifact path must be one filename: {filename!r}")
        if not isinstance(digest, str) or len(digest) != 64:
            raise SystemExit(f"cohort artifact digest is invalid for {name!r}: {digest!r}")
        artifact = (cohort_dir / filename).resolve(strict=True)
        if artifact.parent != cohort_dir:
            raise SystemExit(f"cohort artifact escapes its directory: {artifact}")
        actual = sha256_path(artifact)
        if actual != digest:
            raise SystemExit(
                f"cohort artifact digest mismatch for {name!r}: expected {digest}, got {actual}",
            )
        resolved[name] = artifact
    return resolved


def load_python_cohort(directory: Path) -> PythonCohort:
    """Load a cohort manifest and fail on any identity, path, or digest drift."""
    cohort_dir = directory.resolve(strict=True)
    manifest = cohort_dir / _MANIFEST_NAME
    document = json.loads(manifest.read_text(encoding=_UTF_8))
    artifacts, sha256, source_digest, version = _cohort_manifest_fields(document)
    command_spec_attestation_value = document.get("command_spec_attestation")
    resolved = _resolved_cohort_artifacts(cohort_dir, artifacts, sha256)

    root_wheel_digest = str(sha256["cadrumo"])
    root_sdist_digest = str(sha256["cadrumo-sdist"])
    source_archive_digest = str(sha256["source-archive"])
    command_spec_attestation = _validate_command_spec_attestation(
        command_spec_attestation_value,
        expected_source_digest=source_digest,
        expected_root_wheel_sha256=root_wheel_digest,
        expected_root_sdist_sha256=root_sdist_digest,
        expected_source_archive_sha256=source_archive_digest,
    )
    projection = _cached_artifact_command_projection(
        resolved["cadrumo"],
        resolved["cadrumo-sdist"],
        resolved["source-archive"],
        digests=(root_wheel_digest, root_sdist_digest, source_archive_digest),
    )
    if command_spec_attestation["artifact_members_sha256"] != _projection_digest(projection):
        raise SystemExit("Python cohort CommandSpec attestation artifact member projection drifted")
    forbidden_members = _forbidden_command_artifacts(projection)
    if forbidden_members:
        raise SystemExit(f"Python cohort contains forbidden command authority artifacts: {forbidden_members!r}")

    runtime_wheelhouse = load_runtime_wheelhouse(
        resolved["runtime-wheelhouse"],
        expected_lock_sha256=_sealed_lock_digest(resolved["source-archive"]),
    )

    observed_version = _validate_wheel_contract(
        resolved["cadrumo"],
        resolved["cadrumo-data-manuals"],
        resolved["cadrumo-data-official"],
    )
    if observed_version != version:
        raise SystemExit(
            f"cohort manifest version {version!r} != wheel version {observed_version!r}",
        )
    _validate_sdist_contract(
        resolved["cadrumo-sdist"],
        resolved["cadrumo-data-manuals-sdist"],
        resolved["cadrumo-data-official-sdist"],
        expected_version=version,
    )
    return PythonCohort(
        directory=cohort_dir,
        manifest=manifest,
        source_digest=source_digest,
        version=version,
        root_wheel=resolved["cadrumo"],
        root_sdist=resolved["cadrumo-sdist"],
        source_archive=resolved["source-archive"],
        runtime_wheelhouse=resolved["runtime-wheelhouse"],
        runtime_wheelhouse_manifest=runtime_wheelhouse.manifest,
        manuals_wheel=resolved["cadrumo-data-manuals"],
        manuals_sdist=resolved["cadrumo-data-manuals-sdist"],
        official_wheel=resolved["cadrumo-data-official"],
        official_sdist=resolved["cadrumo-data-official-sdist"],
        sha256={str(name): str(digest) for name, digest in sha256.items()},
        command_spec_attestation=command_spec_attestation,
    )


def digest_install_target(
    name: str,
    artifact: Path,
    *,
    extras: tuple[str, ...] = (),
    digest: str | None = None,
) -> str:
    """Return one digest-pinned direct URL requirement for a local artifact.

    The ``#sha256=`` fragment makes the installer itself verify the artifact
    bytes at install time and fail closed on drift — installers do not reliably
    record ``archive_info.hashes`` for bare local paths (uv records an empty
    ``archive_info``), so the fragment is the enforceable digest channel.

    Args:
        name: Distribution name to pin.
        artifact: The local wheel or sdist the requirement points at.
        extras: Extras to bracket between the name and the ``@`` separator.
        digest: The artifact's already-known SHA-256, hashed here when omitted.
            A caller holding a :class:`PythonCohort` holds a digest that was
            computed over these exact bytes and verified against them at load,
            so re-hashing a hundred-megabyte wheel to restate it adds no
            assurance. Supplying a digest that does not match the bytes would
            simply produce a requirement the installer refuses.
    """
    resolved = artifact.resolve(strict=True)
    pinned = sha256_path(resolved) if digest is None else digest
    extras_suffix = f"[{','.join(extras)}]" if extras else ""
    return f"{name}{extras_suffix} @ {resolved.as_uri()}#sha256={pinned}"


def root_install_target(
    root_artifact: Path,
    *,
    extras: tuple[str, ...] = (),
    digest: str | None = None,
) -> str:
    """Return one digest-pinned direct local root target, optionally with extras."""
    return digest_install_target("cadrumo", root_artifact, extras=extras, digest=digest)


def _cohort_digest_for(cohort: PythonCohort, artifact: Path) -> str | None:
    """Return the cohort's recorded digest for ``artifact``, or ``None`` if unrecorded.

    Matched by resolved path against the two shapes a root artifact takes — the
    root wheel and the root sdist — mirroring how :func:`_verify_direct_urls`
    already picks the expected digest for the same choice.
    """
    resolved = artifact.resolve()
    if resolved == cohort.root_wheel.resolve():
        return cohort.sha256.get("cadrumo")
    if resolved == cohort.root_sdist.resolve():
        return cohort.sha256.get("cadrumo-sdist")
    return None


def install_targets(
    cohort: PythonCohort,
    *,
    root_artifact: Path,
    extras: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Return explicit local targets that prevent companion index resolution."""
    return (
        root_install_target(root_artifact, extras=extras, digest=_cohort_digest_for(cohort, root_artifact)),
        digest_install_target(
            "cadrumo-data-manuals",
            cohort.manuals_wheel,
            digest=cohort.sha256.get("cadrumo-data-manuals"),
        ),
        digest_install_target(
            "cadrumo-data-official",
            cohort.official_wheel,
            digest=cohort.sha256.get("cadrumo-data-official"),
        ),
    )


def _recorded_install_sha(direct_url: dict[str, Any], fragment: str) -> str | None:
    archive_info = direct_url.get("archive_info")
    raw_hashes = archive_info.get("hashes") if isinstance(archive_info, dict) else None
    sha_candidate = raw_hashes.get("sha256") if isinstance(raw_hashes, dict) else None
    return (sha_candidate if isinstance(sha_candidate, str) else None) or fragment.removeprefix("sha256=") or None


def _installed_artifact_digest(cohort: PythonCohort, name: str, artifact: Path) -> str:
    if name == "cadrumo" and artifact == cohort.root_sdist:
        return cohort.sha256["cadrumo-sdist"]
    return cohort.sha256[name]


def _verify_direct_urls(
    direct_urls: object,
    cohort: PythonCohort,
    root_artifact: Path,
) -> None:
    """Verify ``direct_url.json`` metadata for every expected cohort member.

    Accepts both uv-style (URL fragment ``#sha256=``) and pip-style
    (``archive_info.hashes``) digest channels, and always re-hashes the origin
    bytes on disk so the proof never rests on installer metadata alone.

    :class:`PythonCohort` holds the expected per-member digests and artifact
    paths that drive the comparison.
    """
    if not isinstance(direct_urls, dict):
        raise SystemExit("installed cohort probe returned no direct URLs")
    expected_artifacts = {
        "cadrumo": root_artifact.resolve(),
        "cadrumo-data-manuals": cohort.manuals_wheel,
        "cadrumo-data-official": cohort.official_wheel,
    }
    for name, artifact in expected_artifacts.items():
        direct_url = direct_urls.get(name)
        recorded_url = direct_url.get("url") if isinstance(direct_url, dict) else None
        base_url, _, fragment = str(recorded_url or "").partition("#")
        if not isinstance(direct_url, dict) or base_url != artifact.as_uri():
            raise SystemExit(
                f"{name} installed from an unrelated origin: {direct_url!r}",
            )
        expected_sha = _installed_artifact_digest(cohort, name, artifact)
        # Installers differ in where they surface the digest of a local direct
        # install: pip records ``archive_info.hashes`` while uv preserves only
        # the requirement's ``#sha256=`` fragment it verified at install time.
        # Accept either recorded channel, and always re-hash the origin bytes
        # so the proof never rests on installer metadata alone.
        recorded_sha = _recorded_install_sha(direct_url, fragment)
        if recorded_sha != expected_sha:
            raise SystemExit(
                f"{name} installed digest drifted: expected {expected_sha}, recorded {recorded_sha!r}",
            )
        origin_sha = sha256_path(artifact.resolve(strict=True))
        if origin_sha != expected_sha:
            raise SystemExit(
                f"{name} origin bytes drifted after install: expected {expected_sha}, hashed {origin_sha}",
            )


def assert_installed_cohort(
    python: Path,
    cohort: PythonCohort,
    *,
    root_artifact: Path,
    cwd: Path,
) -> dict[str, Any]:
    """Prove installed metadata resolves every cohort member from exact local bytes."""
    completed = _run([str(python), "-c", _INSTALLED_PROBE], cwd=cwd)
    document = json.loads(completed.stdout)
    if not isinstance(document, dict):
        raise SystemExit("installed cohort probe did not return a JSON object")
    versions = document.get("versions")
    expected_versions = {name: cohort.version for name in _DISTRIBUTIONS}
    if versions != expected_versions:
        raise SystemExit(f"installed cohort versions drifted: {versions!r}")
    requirements = set(document.get("root_requirements") or ())
    expected_requirements = {
        f"cadrumo-data-manuals=={cohort.version}",
        f"cadrumo-data-official=={cohort.version}",
    }
    if not expected_requirements <= requirements:
        raise SystemExit(
            f"installed root metadata lost companion pins: {requirements!r}",
        )
    _verify_direct_urls(document.get("direct_urls"), cohort, root_artifact)
    record_proof("all installed origins and digests match the supplied cohort")
    record_proof("root metadata declares both exact mandatory companion requirements")
    record_proof("all three installed distributions share one version")
    return document


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--output", required=True, type=Path)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--cohort-dir", required=True, type=Path)
    return parser


def main() -> int:
    """Build or verify one immutable Python cohort."""
    args = _parser().parse_args()
    if args.command == "build":
        cohort = build_python_cohort(REPO_ROOT, args.output)
    else:
        cohort = load_python_cohort(args.cohort_dir)
    print(
        json.dumps(
            {
                "directory": str(cohort.directory),
                "sha256": cohort.sha256,
                "source_digest": cohort.source_digest,
                "version": cohort.version,
            },
            sort_keys=True,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
