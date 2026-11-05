"""The dictionary provisioner installs only verified, contained, pinned packages.

Archives are real gzip tarballs built here and served through the transport
seam; the lock reading, integrity check, extraction, publication and the
dictionary loader that consumes the result are the production code.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import os
import shutil
import tarfile
import time
from typing import TYPE_CHECKING

import pytest

from dev.init import plan
from dev.paths import REPO_ROOT

from .. import dictionary_provisioning as provisioning
from .._spelling import DICTIONARY_SPECS, dictionary_roots, load_dictionaries
from ..dictionary_provisioning import ProvisioningError, read_locked_packages

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

PACKAGES = tuple(spec.package for spec in DICTIONARY_SPECS if spec.package is not None)
VERSION = "1.2.3"
AFF = b"SET UTF-8\n"
DIC = b"2\nhello\nworld\n"


def _tarball(entries: list[tuple[tarfile.TarInfo, bytes | None]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as bundle:
        for info, content in entries:
            bundle.addfile(info, io.BytesIO(content) if content is not None else None)
    return buffer.getvalue()


def _file(name: str, content: bytes) -> tuple[tarfile.TarInfo, bytes]:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    return info, content


def _special(name: str, kind: bytes, target: str = "") -> tuple[tarfile.TarInfo, None]:
    info = tarfile.TarInfo(name)
    info.type = kind
    info.linkname = target
    return info, None


def _good_entries(name: str, version: str = VERSION) -> list[tuple[tarfile.TarInfo, bytes | None]]:
    manifest = json.dumps({"name": name, "version": version}).encode()
    return [
        _file("package/package.json", manifest),
        _file("package/index.aff", AFF),
        _file("package/index.dic", DIC),
        _file("package/license", b"license\n"),
    ]


def _integrity(archive: bytes) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(archive).digest()).decode()


def _write_inputs(root: Path, archives: dict[str, bytes], *, lock_version: str = VERSION) -> None:
    (root / "package.json").write_text(
        json.dumps({"devDependencies": dict.fromkeys(archives, VERSION)}), encoding="utf-8"
    )
    packages = {
        f"node_modules/{name}": {
            "version": lock_version,
            "resolved": f"https://registry.npmjs.org/{name}/-/{name}-{lock_version}.tgz",
            "integrity": _integrity(archive),
        }
        for name, archive in archives.items()
    }
    (root / "package-lock.json").write_text(json.dumps({"lockfileVersion": 3, "packages": packages}), encoding="utf-8")


def _transport(archives: dict[str, bytes], calls: list[str] | None = None) -> Callable[[str, int, float], bytes]:
    def fetch(path: str, limit: int, timeout: float) -> bytes:
        assert limit == provisioning.MAX_ARCHIVE_BYTES
        assert timeout == provisioning.FETCH_TIMEOUT_SECONDS
        if calls is not None:
            calls.append(path)
        name = path.split("/", 1)[0]
        return archives[name]

    return fetch


def _no_network(path: str, limit: int, timeout: float) -> bytes:
    raise AssertionError(f"unexpected download of {path}")


def _good_archives() -> dict[str, bytes]:
    return {name: _tarball(_good_entries(name)) for name in PACKAGES}


def _quiet(_: str) -> None:
    return None


def _assert_untouched(root: Path, package: str) -> None:
    modules = root / "node_modules"
    assert not (modules / package).exists()
    leftovers = [entry.name for entry in modules.iterdir()] if modules.is_dir() else []
    assert leftovers == []


def test_provisioned_packages_satisfy_the_real_dictionary_loader(tmp_path: Path) -> None:
    archives = _good_archives()
    _write_inputs(tmp_path, archives)
    shutil.copytree(
        dictionary_roots(REPO_ROOT)["hu"].parent, dictionary_roots(tmp_path)["hu"].parent, dirs_exist_ok=True
    )

    installed = provisioning.provision(tmp_path, _transport(archives), _quiet)

    assert sorted(installed) == sorted(PACKAGES)
    dictionaries = load_dictionaries(tmp_path)
    assert sorted(dictionaries) == ["ca", "en", "es", "hu"]
    assert dictionaries["en"].lookup("hello")
    assert not dictionaries["en"].lookup("helo")
    assert sorted(entry.name for entry in (tmp_path / "node_modules").iterdir()) == sorted(PACKAGES)


def test_repository_lock_pins_exactly_the_packages_the_loader_requires() -> None:
    locked = read_locked_packages(REPO_ROOT)

    assert sorted(package.name for package in locked) == sorted(PACKAGES)
    assert all(package.url.startswith("https://registry.npmjs.org/") for package in locked)


def test_setup_plan_names_the_packages_the_loader_requires() -> None:
    assert sorted(plan.LOCALE_DICTIONARY_PACKAGES) == sorted(PACKAGES)
    steps = [step for step in plan.TOOLS.steps if step.name == "locale-dictionaries"]
    assert [step.argv[1:] for step in steps] == [("-m", "dev.locales.dictionary_provisioning")]
    assert not steps[0].advisory
    assert {"package.json", "package-lock.json"} <= set(plan.TOOLS.inputs)
    for package in PACKAGES:
        assert f"node_modules/{package}/index.aff" in plan.TOOLS.artifacts
        assert f"node_modules/{package}/index.dic" in plan.TOOLS.artifacts


def test_wrong_integrity_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    name = PACKAGES[0]
    served = _tarball(_good_entries(name))
    _write_inputs(tmp_path, {name: _tarball(_good_entries(name, "9.9.9"))})

    with pytest.raises(ProvisioningError, match=name) as raised:
        provisioning.provision(tmp_path, _transport({name: served}), _quiet)

    assert "integrity" in raised.value.detail
    assert "setup-locale-spelling" in raised.value.next_action
    _assert_untouched(tmp_path, name)


@pytest.mark.parametrize(
    "member",
    [
        "package/../escaped.txt",
        "package/sub/../../escaped.txt",
        "/escaped.txt",
        "package\\..\\escaped.txt",
        "package/C:/escaped.txt",
        "other/index.aff",
    ],
)
def test_entry_escaping_the_package_is_refused(tmp_path: Path, member: str) -> None:
    name = PACKAGES[0]
    archive = _tarball([*_good_entries(name), _file(member, b"x")])
    (tmp_path / "root").mkdir()
    _write_inputs(tmp_path / "root", {name: archive})

    with pytest.raises(ProvisioningError, match=name):
        provisioning.provision(tmp_path / "root", _transport({name: archive}), _quiet)

    assert not (tmp_path / "escaped.txt").exists()
    assert not (tmp_path / "root" / "escaped.txt").exists()
    _assert_untouched(tmp_path / "root", name)


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE])
def test_link_and_special_entries_are_refused(tmp_path: Path, kind: bytes) -> None:
    name = PACKAGES[0]
    archive = _tarball([*_good_entries(name), _special("package/linked", kind, "package/index.aff")])
    _write_inputs(tmp_path, {name: archive})

    with pytest.raises(ProvisioningError, match=name) as raised:
        provisioning.provision(tmp_path, _transport({name: archive}), _quiet)

    assert "link or special" in raised.value.detail
    _assert_untouched(tmp_path, name)


def test_archive_of_another_version_than_the_lock_is_refused(tmp_path: Path) -> None:
    name = PACKAGES[0]
    archive = _tarball(_good_entries(name, "9.9.9"))
    _write_inputs(tmp_path, {name: archive})

    with pytest.raises(ProvisioningError, match=name) as raised:
        provisioning.provision(tmp_path, _transport({name: archive}), _quiet)

    assert "9.9.9" in raised.value.detail
    _assert_untouched(tmp_path, name)


def test_archive_of_another_package_than_the_lock_is_refused(tmp_path: Path) -> None:
    name = PACKAGES[0]
    archive = _tarball(_good_entries("dictionary-other"))
    _write_inputs(tmp_path, {name: archive})

    with pytest.raises(ProvisioningError, match=name):
        provisioning.provision(tmp_path, _transport({name: archive}), _quiet)

    _assert_untouched(tmp_path, name)


def test_lock_that_disagrees_with_the_manifest_is_refused_without_network(tmp_path: Path) -> None:
    name = PACKAGES[0]
    _write_inputs(tmp_path, {name: _tarball(_good_entries(name))}, lock_version="2.0.0")

    with pytest.raises(ProvisioningError, match=name) as raised:
        provisioning.provision(tmp_path, _no_network, _quiet)

    assert "2.0.0" in raised.value.detail


def test_lock_url_outside_the_registry_is_refused_without_network(tmp_path: Path) -> None:
    name = PACKAGES[0]
    archive = _tarball(_good_entries(name))
    _write_inputs(tmp_path, {name: archive})
    lock = json.loads((tmp_path / "package-lock.json").read_text(encoding="utf-8"))
    lock["packages"][f"node_modules/{name}"]["resolved"] = f"https://example.invalid/{name}.tgz"
    (tmp_path / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")

    with pytest.raises(ProvisioningError, match=name):
        provisioning.provision(tmp_path, _no_network, _quiet)


def test_lock_without_a_sha512_integrity_is_refused(tmp_path: Path) -> None:
    name = PACKAGES[0]
    _write_inputs(tmp_path, {name: _tarball(_good_entries(name))})
    lock = json.loads((tmp_path / "package-lock.json").read_text(encoding="utf-8"))
    lock["packages"][f"node_modules/{name}"]["integrity"] = "sha1-AAAA"
    (tmp_path / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")

    with pytest.raises(ProvisioningError, match=name):
        provisioning.provision(tmp_path, _no_network, _quiet)


def test_second_run_over_valid_packages_uses_no_network(tmp_path: Path) -> None:
    archives = _good_archives()
    _write_inputs(tmp_path, archives)
    calls: list[str] = []
    provisioning.provision(tmp_path, _transport(archives, calls), _quiet)
    assert len(calls) == len(PACKAGES)

    again = provisioning.provision(tmp_path, _no_network, _quiet)

    assert again == ()


def test_package_installed_by_another_tool_is_accepted_without_network(tmp_path: Path) -> None:
    name = PACKAGES[0]
    _write_inputs(tmp_path, {name: _tarball(_good_entries(name))})
    package = tmp_path / "node_modules" / name
    package.mkdir(parents=True)
    (package / "package.json").write_text(json.dumps({"name": name, "version": VERSION}), encoding="utf-8")
    (package / "index.aff").write_bytes(AFF)
    (package / "index.dic").write_bytes(DIC)

    assert provisioning.provision(tmp_path, _no_network, _quiet) == ()


@pytest.mark.parametrize("damage", ["wrong-version", "missing-dic", "no-manifest"])
def test_partial_or_mismatched_package_is_replaced(tmp_path: Path, damage: str) -> None:
    name = PACKAGES[0]
    archives = {name: _tarball(_good_entries(name))}
    _write_inputs(tmp_path, archives)
    package = tmp_path / "node_modules" / name
    package.mkdir(parents=True)
    (package / "index.aff").write_bytes(b"old")
    (package / "stale-extra.txt").write_bytes(b"old")
    if damage != "no-manifest":
        version = "0.0.1" if damage == "wrong-version" else VERSION
        (package / "package.json").write_text(json.dumps({"name": name, "version": version}), encoding="utf-8")
    if damage != "missing-dic":
        (package / "index.dic").write_bytes(b"old")

    assert provisioning.provision(tmp_path, _transport(archives), _quiet) == (name,)

    assert (package / "index.aff").read_bytes() == AFF
    assert not (package / "stale-extra.txt").exists()
    assert [entry.name for entry in (tmp_path / "node_modules").iterdir()] == [name]


def test_corrupt_download_leaves_the_previous_package_and_no_staging(tmp_path: Path) -> None:
    name = PACKAGES[0]
    good = _tarball(_good_entries(name))
    truncated = good[: len(good) // 2]
    _write_inputs(tmp_path, {name: truncated})
    package = tmp_path / "node_modules" / name
    package.mkdir(parents=True)
    (package / "marker.txt").write_bytes(b"previous")

    with pytest.raises(ProvisioningError, match=name) as raised:
        provisioning.provision(tmp_path, _transport({name: truncated}), _quiet)

    assert "cannot be unpacked" in raised.value.detail
    assert (package / "marker.txt").read_bytes() == b"previous"
    assert [entry.name for entry in (tmp_path / "node_modules").iterdir()] == [name]


def test_failed_move_into_place_restores_the_previous_package(tmp_path: Path) -> None:
    destination = tmp_path / "pkg"
    destination.mkdir()
    (destination / "marker.txt").write_bytes(b"previous")

    with pytest.raises(FileNotFoundError):
        provisioning.publish(tmp_path / "never-built", destination)

    assert (destination / "marker.txt").read_bytes() == b"previous"
    assert [entry.name for entry in tmp_path.iterdir()] == ["pkg"]


def test_abandoned_staging_from_a_killed_run_is_cleared_and_fresh_staging_kept(tmp_path: Path) -> None:
    name = PACKAGES[0]
    archives = {name: _tarball(_good_entries(name))}
    _write_inputs(tmp_path, archives)
    modules = tmp_path / "node_modules"
    old = modules / f"{provisioning.STAGING_PREFIX}killed"
    fresh = modules / f"{provisioning.STAGING_PREFIX}running"
    for staging in (old, fresh):
        staging.mkdir(parents=True)
        (staging / "index.aff").write_bytes(b"half")
    aged = time.time() - provisioning.STALE_STAGING_SECONDS - 60
    os.utime(old, (aged, aged))

    provisioning.provision(tmp_path, _transport(archives), _quiet)

    assert sorted(entry.name for entry in modules.iterdir()) == sorted([name, fresh.name])
    assert provisioning.is_installed(tmp_path, read_locked_packages(tmp_path)[0])


def test_transport_failure_names_the_package_and_the_next_action(tmp_path: Path) -> None:
    name = PACKAGES[0]
    _write_inputs(tmp_path, {name: _tarball(_good_entries(name))})

    def offline(path: str, limit: int, timeout: float) -> bytes:
        raise OSError("network is unreachable")

    with pytest.raises(ProvisioningError, match=name) as raised:
        provisioning.provision(tmp_path, offline, _quiet)

    assert "network is unreachable" in raised.value.detail
    assert "registry.npmjs.org" in raised.value.next_action
    assert "setup-locale-spelling" in raised.value.next_action
    _assert_untouched(tmp_path, name)


def test_real_transport_refuses_anything_but_a_registry_path() -> None:
    for path in ("https://evil.example/x.tgz", "/absolute/x.tgz", "a\\b.tgz"):
        with pytest.raises(ValueError, match="registry path"):
            provisioning.fetch_https(path, 1024, 1.0)


def test_command_line_reports_the_package_and_returns_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    name = PACKAGES[0]
    _write_inputs(tmp_path, {name: _tarball(_good_entries(name))}, lock_version="2.0.0")

    status = provisioning.main(["--root", str(tmp_path)])

    captured = capsys.readouterr()
    assert status == 1
    assert name in captured.err
    assert "next:" in captured.err
    assert captured.out == ""


def test_command_line_succeeds_without_network_when_packages_are_present(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    name = PACKAGES[0]
    archives = {name: _tarball(_good_entries(name))}
    _write_inputs(tmp_path, archives)
    provisioning.provision(tmp_path, _transport(archives), _quiet)

    assert provisioning.main(["--root", str(tmp_path)]) == 0
    assert "already installed" in capsys.readouterr().err


def test_gzip_stream_that_is_not_a_tarball_is_refused(tmp_path: Path) -> None:
    name = PACKAGES[0]
    archive = gzip.compress(b"not a tarball")
    _write_inputs(tmp_path, {name: archive})

    with pytest.raises(ProvisioningError, match=name):
        provisioning.provision(tmp_path, _transport({name: archive}), _quiet)

    _assert_untouched(tmp_path, name)
