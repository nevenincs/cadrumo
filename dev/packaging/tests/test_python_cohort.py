"""Real repository and artifact tests for immutable Python cohort construction."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

from .._hashing import sha256_path
from ..python_cohort import (
    _artifact_command_projection,
    _assert_probe_reads_are_wheel_members,
    _cached_artifact_command_projection,
    _command_spec_attestation,
    _install_relative_probe_reads,
    _validate_command_spec_attestation,
    digest_install_target,
    load_python_cohort,
    source_snapshot_drift,
)
from ._cohort_attestation import (
    add_test_runtime_wheelhouse,
    add_test_source_archive,
    make_test_command_spec_attestation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    git = shutil.which("git")
    assert git is not None
    return subprocess.run(  # noqa: S603 - resolved Git with test-owned declarative argv.
        [git, *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_source_snapshot_drift_detects_worktree_index_and_untracked_bytes(
    tmp_path: Path,
) -> None:
    """A HEAD archive cannot be labelled current while any source byte is excluded."""
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "cohort-test@example.invalid")
    _git(tmp_path, "config", "user.name", "Cohort Test")
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("committed\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.txt")
    _git(tmp_path, "commit", "-m", "seed")
    assert source_snapshot_drift(tmp_path) == ()

    tracked.write_text("working\n", encoding="utf-8")
    untracked = tmp_path / "untracked.txt"
    untracked.write_text("untracked\n", encoding="utf-8")
    working = source_snapshot_drift(tmp_path)
    assert " M tracked.txt" in working
    assert "?? untracked.txt" in working

    _git(tmp_path, "add", "tracked.txt")
    staged = source_snapshot_drift(tmp_path)
    assert "M  tracked.txt" in staged
    assert "?? untracked.txt" in staged


def _write_placeholder_cohort(root: Path) -> dict[str, str]:
    """Write a digest-consistent cohort whose artifact bytes are placeholders.

    The bytes are not real wheels, so loading reaches -- and fails at -- the
    wheel-contract stage. That makes this fixture a precise probe for the
    checks that run *before* metadata parsing.
    """
    names = {
        "cadrumo": "cadrumo-1.0.0-py3-none-any.whl",
        "cadrumo-sdist": "cadrumo-1.0.0.tar.gz",
        "cadrumo-data-manuals": "cadrumo_data_manuals-1.0.0-py3-none-any.whl",
        "cadrumo-data-manuals-sdist": "cadrumo_data_manuals-1.0.0.tar.gz",
        "cadrumo-data-official": "cadrumo_data_official-1.0.0-py3-none-any.whl",
        "cadrumo-data-official-sdist": "cadrumo_data_official-1.0.0.tar.gz",
    }
    sha256: dict[str, str] = {}
    for label, filename in names.items():
        payload = f"{label}\n".encode()
        (root / filename).write_bytes(payload)
        sha256[label] = hashlib.sha256(payload).hexdigest()
    add_test_source_archive(root, names, sha256)
    add_test_runtime_wheelhouse(root, names, sha256)
    (root / "python-cohort.json").write_text(
        json.dumps(
            {
                "artifacts": names,
                "sha256": sha256,
                "source_commit": "a" * 40,
                "version": "1.0.0",
                "command_spec_attestation": make_test_command_spec_attestation(root, names, source_commit="a" * 40),
            },
        ),
        encoding="utf-8",
    )
    return names


def test_load_python_cohort_refuses_an_unmanifested_file(tmp_path: Path) -> None:
    """The cohort directory is a closed world: manifest plus declared artifacts only.

    The release-cohort authority already refuses inventory drift. A Python cohort
    carrying an undeclared file must fail the same way, or the extra file crosses
    every acquisition, smoke, and promote gate that loads it.
    """
    _write_placeholder_cohort(tmp_path)
    (tmp_path / "unmanifested-extra.bin").write_bytes(b"stowaway")

    with pytest.raises(SystemExit, match="file inventory drifted"):
        load_python_cohort(tmp_path)


def test_load_python_cohort_accepts_the_declared_inventory(tmp_path: Path) -> None:
    """The inventory check does not fire on a cohort holding exactly its declared files.

    Loading proceeds past the inventory gate into wheel-metadata parsing, where the
    placeholder bytes fail for an unrelated reason. That later failure is the proof
    the inventory comparison passed rather than short-circuiting every cohort.
    """
    _write_placeholder_cohort(tmp_path)

    with pytest.raises(zipfile.BadZipFile):
        load_python_cohort(tmp_path)


def test_load_python_cohort_rejects_digest_drift_before_metadata_parsing(
    tmp_path: Path,
) -> None:
    """A changed retained artifact fails closed before it could be promoted."""
    names = {
        "cadrumo": "cadrumo-1.0.0-py3-none-any.whl",
        "cadrumo-sdist": "cadrumo-1.0.0.tar.gz",
        "cadrumo-data-manuals": "cadrumo_data_manuals-1.0.0-py3-none-any.whl",
        "cadrumo-data-manuals-sdist": "cadrumo_data_manuals-1.0.0.tar.gz",
        "cadrumo-data-official": "cadrumo_data_official-1.0.0-py3-none-any.whl",
        "cadrumo-data-official-sdist": "cadrumo_data_official-1.0.0.tar.gz",
    }
    sha256: dict[str, str] = {}
    for label, filename in names.items():
        payload = f"{label}\n".encode()
        (tmp_path / filename).write_bytes(payload)
        sha256[label] = hashlib.sha256(payload).hexdigest()
    add_test_source_archive(tmp_path, names, sha256)
    add_test_runtime_wheelhouse(tmp_path, names, sha256)
    (tmp_path / "python-cohort.json").write_text(
        json.dumps(
            {
                "artifacts": names,
                "sha256": sha256,
                "source_commit": "a" * 40,
                "version": "1.0.0",
                "command_spec_attestation": make_test_command_spec_attestation(tmp_path, names, source_commit="a" * 40),
            },
        ),
        encoding="utf-8",
    )
    (tmp_path / names["cadrumo"]).write_bytes(b"changed")

    with pytest.raises(SystemExit, match="digest mismatch"):
        load_python_cohort(tmp_path)


def _projection_over(
    root: Path,
    origins: tuple[str, ...],
    resources: tuple[str, ...] = ("cadrumo/locales/en/application.yml",),
) -> dict[str, object]:
    """Return a CommandSpec projection naming ``origins`` and ``resources`` beneath ``root``.

    Both halves are supplied because the probe reports both: the modules it
    imported, and the packaged locale files the sealed locale rows were read
    out of. The resource default is one real shard name, so a case that is
    about modules does not accidentally exercise the empty-resource refusal.

    Every field the sealed envelope digests is present, so a projection built
    here can be carried through the whole attestation composition rather than
    only through the member check. The fields that carry no path are constant:
    the cases below vary location, and holding the rest still is what makes a
    digest difference attributable.
    """
    return {
        "identities": [["cadrumo", "root", "group"]],
        "locales": [["cadrumo", "key", "en", "{}"]],
        "policies": [["cadrumo"]],
        "schemas": [["cadrumo", "absent", "identity", None]],
        "import_budgets": {"graph_projection_first_party_modules": ["cadrumo"]},
        "origins": [[member.replace("/", "."), str(root / member)] for member in origins],
        "packaged_resources": [str(root / member) for member in resources],
    }


def _wheel_carrying(path: Path, members: tuple[str, ...]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for member in members:
            archive.writestr(member, b"payload")
    return path


def test_attestation_refuses_an_origin_the_root_wheel_does_not_ship(tmp_path: Path) -> None:
    """A module importable from the build tree but absent from the wheel fails closed.

    This is the exact hazard of probing the tree ``uv build`` packaged from
    rather than the finished wheel: the wheel target excludes the test payload,
    so the tree is a strict superset and a projection taken over it could
    describe a module no installation would ever have. The probe proves the
    imports stayed inside the tree; this proves the tree's copy is also shipped.
    """
    site_root = tmp_path / "src"
    (site_root / "cadrumo" / "tests").mkdir(parents=True)
    artifact_projection = (
        ("wheel", "cadrumo/__init__.py"),
        ("wheel", "cadrumo/locales/en/application.yml"),
        ("source", "src/cadrumo/tests/helper.py"),
    )
    projection = _install_relative_probe_reads(
        _projection_over(site_root, ("cadrumo/__init__.py", "cadrumo/tests/helper.py")),
        site_root=site_root,
    )

    with pytest.raises(SystemExit, match="does not ship"):
        _assert_probe_reads_are_wheel_members(projection, artifact_projection)


def test_attestation_refuses_packaged_data_the_root_wheel_does_not_ship(tmp_path: Path) -> None:
    """A locale shard present in the build tree and absent from the wheel fails closed.

    The DATA half, and the one with the sharper consequence. The probe reads the
    packaged catalogue out of its tree, refuses an incomplete locale projection,
    and the digest of those rows is sealed into the published envelope. A wheel
    exclusion that sheds one language leaves the tree complete and the archive
    short, so without this the release ships a Spanish command surface rendering
    raw translation keys under an attestation certifying a complete catalogue.

    The wheel listing here carries the English shard and not the Spanish one,
    which is exactly that exclusion.
    """
    site_root = tmp_path / "src"
    (site_root / "cadrumo" / "locales" / "es").mkdir(parents=True)
    artifact_projection = (
        ("wheel", "cadrumo/__init__.py"),
        ("wheel", "cadrumo/locales/en/application.yml"),
        ("source", "src/cadrumo/locales/es/application.yml"),
    )
    projection = _install_relative_probe_reads(
        _projection_over(
            site_root,
            ("cadrumo/__init__.py",),
            resources=("cadrumo/locales/en/application.yml", "cadrumo/locales/es/application.yml"),
        ),
        site_root=site_root,
    )

    with pytest.raises(SystemExit, match="does not ship") as refusal:
        _assert_probe_reads_are_wheel_members(projection, artifact_projection)

    assert "cadrumo/locales/es/application.yml" in str(refusal.value)


def test_attestation_refuses_a_projection_that_read_no_packaged_data(tmp_path: Path) -> None:
    """An empty resource report is vacuity, not absence.

    The probe's locale completeness check passes trivially over a catalogue with
    nothing in it, so a projection reporting no resource read cannot have sealed
    the locale rows it claims to. Refused rather than skipped, because skipping
    would restore exactly the module-only check this replaced.
    """
    site_root = tmp_path / "src"
    (site_root / "cadrumo").mkdir(parents=True)
    projection = _install_relative_probe_reads(
        _projection_over(site_root, ("cadrumo/__init__.py",), resources=()),
        site_root=site_root,
    )

    with pytest.raises(SystemExit, match="no packaged resource file"):
        _assert_probe_reads_are_wheel_members(projection, (("wheel", "cadrumo/__init__.py"),))


def test_attestation_accepts_origins_and_data_the_root_wheel_carries(tmp_path: Path) -> None:
    """Every module and resource present as a wheel member passes, from a real archive listing."""
    site_root = tmp_path / "src"
    (site_root / "cadrumo").mkdir(parents=True)
    members = (
        "cadrumo/__init__.py",
        "cadrumo/core/i18n/render.py",
        "cadrumo/locales/en/application.yml",
        "cadrumo/locales/es/application.yml",
    )
    root_wheel = _wheel_carrying(tmp_path / "cadrumo-1.0.0-py3-none-any.whl", members)
    root_sdist = tmp_path / "cadrumo-1.0.0.tar.gz"
    with tarfile.open(root_sdist, "w:gz") as archive:
        info = tarfile.TarInfo("cadrumo-1.0.0/pyproject.toml")
        info.size = 0
        archive.addfile(info, io.BytesIO(b""))
    source_archive = _wheel_carrying(tmp_path / "cadrumo-source.zip", ("pyproject.toml",))

    artifact_projection = _artifact_command_projection(root_wheel, root_sdist, source_archive)
    projection = _install_relative_probe_reads(
        _projection_over(site_root, members[:2], resources=members[2:]),
        site_root=site_root,
    )

    _assert_probe_reads_are_wheel_members(projection, artifact_projection)


def test_attestation_names_probe_reads_by_install_member_not_build_location(tmp_path: Path) -> None:
    """The same reads under two build trees seal to one envelope.

    The property the immutable cohort rests on. A build's probe tree is scratch
    -- its name carries the building process and a fresh discriminator -- so a
    projection that kept the probe's absolute paths made the sealed envelope,
    and therefore the cohort identifier every evidence row binds to, differ
    between two builds of one commit that agreed on every artifact byte.

    Both halves are asserted: that the projection names install members, and
    that the envelope sealed from it is location-independent.
    """
    members = ("cadrumo/__init__.py", "cadrumo/locales/en/application.yml")
    artifact_projection = tuple(("wheel", member) for member in members)
    envelopes = []
    for build in ("build-a", "build-b"):
        site_root = tmp_path / build / "src"
        site_root.mkdir(parents=True)
        projection = _install_relative_probe_reads(
            _projection_over(site_root, members[:1], resources=members[1:]),
            site_root=site_root,
        )
        assert projection["origins"] == [["cadrumo.__init__.py", "cadrumo/__init__.py"]]
        assert projection["packaged_resources"] == ["cadrumo/locales/en/application.yml"]
        _assert_probe_reads_are_wheel_members(projection, artifact_projection)
        envelopes.append(
            _command_spec_attestation(
                projection,
                artifact_projection,
                source_commit="a" * 40,
                root_wheel_sha256="1" * 64,
                root_sdist_sha256="2" * 64,
                source_archive_sha256="3" * 64,
            ),
        )

    assert envelopes[0] == envelopes[1]


def test_attestation_refuses_an_origin_outside_the_probe_tree(tmp_path: Path) -> None:
    """An origin resolving outside the probed root is a refusal, not a skipped row."""
    site_root = tmp_path / "src"
    site_root.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    with pytest.raises(SystemExit, match="escaped its probe tree"):
        _install_relative_probe_reads(
            _projection_over(elsewhere, ("cadrumo/__init__.py",)),
            site_root=site_root,
        )


def test_attestation_refuses_packaged_data_outside_the_probe_tree(tmp_path: Path) -> None:
    """A resource resolving outside the probed root is refused for the same reason.

    A catalogue read from a neighbouring installation would describe locale rows
    the wheel under attestation has no relationship to.
    """
    site_root = tmp_path / "src"
    site_root.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    projection = {
        "identities": [["cadrumo", "root", "group"]],
        "origins": [["cadrumo", str(site_root / "cadrumo" / "__init__.py")]],
        "packaged_resources": [str(elsewhere / "cadrumo" / "locales" / "en" / "application.yml")],
    }

    with pytest.raises(SystemExit, match="escaped its probe tree"):
        _install_relative_probe_reads(projection, site_root=site_root)


def test_attestation_binds_the_digests_it_is_handed(tmp_path: Path) -> None:
    """The sealed envelope carries the caller's digests and validates against them."""
    site_root = tmp_path / "src"
    site_root.mkdir()
    projection = {
        "identities": [["cadrumo", "root", "group"]],
        "locales": [["key", "en", "{}"]],
        "policies": [["cadrumo"]],
        "schemas": [["cadrumo", "absent", "identity", None]],
        "import_budgets": {"graph_projection_first_party_modules": ["cadrumo"]},
        "origins": [["cadrumo", str(site_root / "cadrumo" / "__init__.py")]],
    }
    digests = ("1" * 64, "2" * 64, "3" * 64)

    attestation = _command_spec_attestation(
        projection,
        (("wheel", "cadrumo/__init__.py"),),
        source_commit="a" * 40,
        root_wheel_sha256=digests[0],
        root_sdist_sha256=digests[1],
        source_archive_sha256=digests[2],
    )

    assert attestation["root_wheel_sha256"] == digests[0]
    assert attestation["root_sdist_sha256"] == digests[1]
    assert attestation["source_archive_sha256"] == digests[2]
    assert attestation["node_count"] == 1
    # Revalidating the sealed envelope against its own bindings is the proof
    # the digests were threaded rather than recomputed from unrelated bytes.
    assert (
        _validate_command_spec_attestation(
            attestation,
            expected_source_commit="a" * 40,
            expected_root_wheel_sha256=digests[0],
            expected_root_sdist_sha256=digests[1],
            expected_source_archive_sha256=digests[2],
        )
        == attestation
    )


def test_artifact_projection_is_reused_for_one_artifact_triple(tmp_path: Path) -> None:
    """A second request for the same digests answers without reopening the archives.

    Proved by removing the archives between the two calls: a cache that quietly
    re-read them would raise here, and one keyed on paths or timestamps rather
    than on content could not tell this triple from any other.
    """
    members = ("cadrumo/__init__.py",)
    root_wheel = _wheel_carrying(tmp_path / "cadrumo-2.0.0-py3-none-any.whl", members)
    root_sdist = tmp_path / "cadrumo-2.0.0.tar.gz"
    with tarfile.open(root_sdist, "w:gz") as archive:
        info = tarfile.TarInfo("cadrumo-2.0.0/pyproject.toml")
        info.size = 0
        archive.addfile(info, io.BytesIO(b""))
    source_archive = _wheel_carrying(tmp_path / "cadrumo-source.zip", ("pyproject.toml",))
    digests = (sha256_path(root_wheel), sha256_path(root_sdist), sha256_path(source_archive))

    first = _cached_artifact_command_projection(root_wheel, root_sdist, source_archive, digests=digests)
    for artifact in (root_wheel, root_sdist, source_archive):
        artifact.unlink()

    assert _cached_artifact_command_projection(root_wheel, root_sdist, source_archive, digests=digests) == first
    assert ("wheel", "cadrumo/__init__.py") in first


def test_install_target_uses_a_supplied_digest_without_rehashing(tmp_path: Path) -> None:
    """A caller holding the cohort's digest pins with it rather than reading the file again."""
    artifact = tmp_path / "cadrumo-3.0.0-py3-none-any.whl"
    artifact.write_bytes(b"wheel bytes")
    supplied = "c" * 64

    assert digest_install_target("cadrumo", artifact, digest=supplied).endswith(f"#sha256={supplied}")
    assert digest_install_target("cadrumo", artifact).endswith(f"#sha256={sha256_path(artifact)}")
