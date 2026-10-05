"""Delegated package inventories: every Python consumer refuses escapes, collisions and drift."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from collections.abc import Callable, Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from dev._paths import REPO_ROOT
from dev.packaging.native.hashing import digest
from dev.packaging.native.identity import identity
from dev.packaging.native.installation import validate_payload
from dev.packaging.native.package_inventory import checked_member, package_inventory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

PREFIX = "docs/user"
MEMBER = f"{PREFIX}/manifest.json"


def _write_package(root: Path, docs: dict[str, str], *, listed: dict[str, str] | None = None) -> dict[str, Any]:
    """Write a synthetic package whose docs subtree is inventoried by its own manifest."""
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "python.exe").write_text("synthetic interpreter", encoding="utf-8")
    for name, text in docs.items():
        (root / PREFIX / name).parent.mkdir(parents=True, exist_ok=True)
        (root / PREFIX / name).write_text(text, encoding="utf-8")
    nested = listed if listed is not None else {name: digest(root / PREFIX / name) for name in docs}
    (root / MEMBER).write_text(json.dumps({"files": nested}), encoding="utf-8")
    manifest = {
        "build": asdict(identity("windows-x86-64")),
        "files": {"python.exe": digest(root / "python.exe"), MEMBER: digest(root / MEMBER)},
        "delegated_inventories": {PREFIX: MEMBER},
        "user_docs": {"directory": PREFIX, "bundled": True},
    }
    (root / "data/package-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def _write_docsless_package(root: Path) -> dict[str, Any]:
    """Write a synthetic package assembled with the documentation explicitly left out."""
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "python.exe").write_text("synthetic interpreter", encoding="utf-8")
    manifest = {
        "build": asdict(identity("windows-x86-64")),
        "files": {"python.exe": digest(root / "python.exe")},
        "delegated_inventories": {},
        "user_docs": {"directory": PREFIX, "bundled": False},
    }
    (root / "data/package-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def _bootstrap_package(
    bootstrap: types.ModuleType, root: Path, manifest: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Point the shipped bootstrap at a synthetic package root built for this interpreter."""
    build = {"version": "1", "build_number": 1, "build_date": "d", "python": ".".join(map(str, sys.version_info[:3]))}
    manifest["build"] = build
    manifest["startup_files"] = ["python.exe"]
    (root / "data/package-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(sys, "cadrumo_build", build, raising=False)
    # An absolute package root replaces the executable-relative anchor when joined.
    layout = {"package_root_from_executable": str(root), "files": {"package_manifest": "data/package-manifest.json"}}
    monkeypatch.setattr(bootstrap, "LAYOUT", layout)


@pytest.fixture
def bootstrap() -> Iterator[types.ModuleType]:
    """Load the shipped bootstrap source; only its native import-time module is absent here."""
    sys.modules["_cadrumo_native"] = types.ModuleType("_cadrumo_native")
    spec = importlib.util.spec_from_file_location(
        "_cadrumo_bootstrap_under_test", REPO_ROOT / "native/interpreter/bootstrap.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        del sys.modules["_cadrumo_native"]


def _consumers(bootstrap: types.ModuleType, tmp_path: Path) -> dict[str, Callable[[Path, dict[str, Any]], object]]:
    identity_file = tmp_path / "identity.json"
    identity_file.write_text(json.dumps(asdict(identity("windows-x86-64"))), encoding="utf-8")
    return {
        "helper": lambda root, manifest: package_inventory(root, manifest),
        "installation": lambda root, _manifest: validate_payload(root, identity_file),
        "bootstrap": lambda root, manifest: bootstrap._delegated_inventory(root.resolve(), manifest),
    }


def test_delegated_inventory_merges_the_hashed_subtree(tmp_path: Path, bootstrap: types.ModuleType) -> None:
    root = tmp_path / "package"
    manifest = _write_package(root, {"index.html": "apex", "es/index.html": "es"})
    expected = {**manifest["files"], f"{PREFIX}/index.html": digest(root / PREFIX / "index.html")}
    expected[f"{PREFIX}/es/index.html"] = digest(root / PREFIX / "es/index.html")
    assert package_inventory(root, manifest) == expected
    assert bootstrap._delegated_inventory(root.resolve(), manifest) == expected
    validate_payload(root, _identity(tmp_path))


def _identity(tmp_path: Path) -> Path:
    identity_file = tmp_path / "identity.json"
    identity_file.write_text(json.dumps(asdict(identity("windows-x86-64"))), encoding="utf-8")
    return identity_file


@pytest.mark.parametrize("consumer", ["helper", "installation", "bootstrap"])
@pytest.mark.parametrize(
    "listed",
    [
        {"../../python.exe": "0" * 64},
        {"..\\..\\python.exe": "0" * 64},
        {"/python.exe": "0" * 64},
        {"C:/python.exe": "0" * 64},
    ],
    ids=["dot-dot", "backslash", "absolute", "drive"],
)
def test_delegated_entries_cannot_escape_their_prefix(
    tmp_path: Path, bootstrap: types.ModuleType, consumer: str, listed: dict[str, str]
) -> None:
    root = tmp_path / "package"
    manifest = _write_package(root, {"index.html": "apex"}, listed=listed)
    with pytest.raises((ValueError, ImportError)):
        _consumers(bootstrap, tmp_path)[consumer](root, manifest)


@pytest.mark.parametrize("consumer", ["helper", "installation", "bootstrap"])
def test_a_delegated_entry_cannot_rehash_a_package_file(
    tmp_path: Path, bootstrap: types.ModuleType, consumer: str
) -> None:
    root = tmp_path / "package"
    manifest = _write_package(root, {"index.html": "apex"}, listed={"manifest.json": "0" * 64})
    with pytest.raises((ValueError, ImportError), match="collides"):
        _consumers(bootstrap, tmp_path)[consumer](root, manifest)


@pytest.mark.parametrize("consumer", ["helper", "installation", "bootstrap"])
def test_a_tampered_delegated_manifest_is_refused(tmp_path: Path, bootstrap: types.ModuleType, consumer: str) -> None:
    root = tmp_path / "package"
    manifest = _write_package(root, {"index.html": "apex"})
    nested = json.loads((root / MEMBER).read_text(encoding="utf-8"))
    nested["files"]["index.html"] = "0" * 64
    (root / MEMBER).write_text(json.dumps(nested), encoding="utf-8")
    with pytest.raises((ValueError, ImportError), match=r"modified|Damaged"):
        _consumers(bootstrap, tmp_path)[consumer](root, manifest)


def test_payload_validation_refuses_an_unlisted_or_changed_docs_file(tmp_path: Path) -> None:
    root = tmp_path / "package"
    _write_package(root, {"index.html": "apex"})
    (root / PREFIX / "stray.html").write_text("unlisted", encoding="utf-8")
    with pytest.raises(ValueError, match="inventory differs"):
        validate_payload(root, _identity(tmp_path))
    (root / PREFIX / "stray.html").unlink()
    (root / PREFIX / "index.html").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="modified"):
        validate_payload(root, _identity(tmp_path))


def test_portable_member_rules_match_the_rust_relative_path_contract() -> None:
    for relative in [
        "",
        "../x",
        "a/../../x",
        "/abs/x",
        "C:/x",
        "a\\x",
        "a//x",
        "./x",
        "NUL",
        "a/COM1.txt",
        "a/x.",
        "a/x ",
    ]:
        with pytest.raises(ValueError):
            checked_member(relative)
    assert checked_member("á 漢字/index.html") == "á 漢字/index.html"


def test_full_bootstrap_verification_refuses_unlisted_and_changed_docs_files(
    tmp_path: Path, bootstrap: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = (tmp_path / "package").resolve()
    _bootstrap_package(bootstrap, root, _write_package(root, {"index.html": "apex"}), monkeypatch)
    bootstrap.verify(full=True)
    bootstrap.verify(full=False)
    (root / PREFIX / "stray.html").write_text("unlisted", encoding="utf-8")
    with pytest.raises(ImportError, match="Unexpected package files"):
        bootstrap.verify(full=True)
    (root / PREFIX / "stray.html").unlink()
    (root / PREFIX / "index.html").write_text("changed", encoding="utf-8")
    with pytest.raises(ImportError, match="Damaged"):
        bootstrap.verify(full=True)
    bootstrap.verify(full=False)


def test_a_package_assembled_without_documentation_verifies_only_because_it_says_so(
    tmp_path: Path, bootstrap: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = (tmp_path / "package").resolve()
    manifest = _write_docsless_package(root)
    assert package_inventory(root, manifest) == manifest["files"]
    validate_payload(root, _identity(tmp_path))
    with pytest.raises(ValueError, match="requires bundled user documentation"):
        validate_payload(root, _identity(tmp_path), desktop="python.exe")
    (root / PREFIX).mkdir(parents=True)
    (root / PREFIX / "index.html").write_text("stale copy", encoding="utf-8")
    with pytest.raises(ValueError, match="inventory differs"):
        validate_payload(root, _identity(tmp_path))
    _bootstrap_package(bootstrap, root, manifest, monkeypatch)
    with pytest.raises(ImportError, match="Unexpected package files"):
        bootstrap.verify(full=True)
    (root / PREFIX / "index.html").unlink()
    bootstrap.verify(full=True)


@pytest.mark.parametrize("consumer", ["helper", "installation", "bootstrap"])
@pytest.mark.parametrize("statement", [None, {"directory": PREFIX, "bundled": False}, {"bundled": True}])
def test_the_documentation_statement_must_exist_and_agree_with_the_inventory(
    tmp_path: Path, bootstrap: types.ModuleType, consumer: str, statement: dict[str, object] | None
) -> None:
    root = tmp_path / "package"
    manifest = _write_package(root, {"index.html": "apex"})
    if statement is None:
        del manifest["user_docs"]
    else:
        manifest["user_docs"] = statement
    (root / "data/package-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises((ValueError, ImportError), match=r"(?i)documentation"):
        _consumers(bootstrap, tmp_path)[consumer](root, manifest)


@pytest.mark.parametrize("consumer", ["helper", "installation", "bootstrap"])
def test_a_manifest_claiming_documentation_with_the_tree_missing_is_refused(
    tmp_path: Path, bootstrap: types.ModuleType, consumer: str
) -> None:
    root = tmp_path / "package"
    manifest = _write_package(root, {"index.html": "apex"})
    for path in sorted((root / PREFIX).rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    (root / PREFIX).rmdir()
    with pytest.raises((ValueError, ImportError, FileNotFoundError)):
        _consumers(bootstrap, tmp_path)[consumer](root, manifest)
