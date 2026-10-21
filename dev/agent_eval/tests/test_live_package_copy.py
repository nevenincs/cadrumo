"""The live lane's package copy is verified against its manifest and against the checkout.

Every test builds a small synthetic package with a real manifest in the shape
the bundle writes, so the real manifest walker and digest code run. The
positive controls are the changed byte, the extra file, the edited copy and the
stale module: each must be refused.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ..live.outcome import UnavailableError
from ..live.package_copy import (
    PackageCopyError,
    compare_with_checkout,
    require_current,
    reverify_copy,
    verified_copy,
    verify_package,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MODULE = "cadrumo/site-packages/cadrumo/core/thing.py"


def _package(root: Path, files: dict[str, bytes]) -> Path:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    manifest = {
        "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
        "user_docs": {"directory": "docs/user", "bundled": False},
    }
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data/package-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def _files() -> dict[str, bytes]:
    return {
        "python.exe": b"interpreter",
        "bin/aeat.exe": b"cli",
        "data/build.json": json.dumps({"version": "0.0.0"}).encode(),
        _MODULE: b"VALUE = 1\n",
    }


def test_an_unchanged_package_verifies_and_reports_its_build(tmp_path: Path) -> None:
    identity = verify_package(_package(tmp_path / "staged", _files()))
    assert identity.file_count == 5
    assert identity.build == {"version": "0.0.0"}


def test_a_changed_byte_is_refused(tmp_path: Path) -> None:
    root = _package(tmp_path / "staged", _files())
    (root / "bin/aeat.exe").write_bytes(b"clj")
    with pytest.raises(PackageCopyError, match=r"bin/aeat.exe"):
        verify_package(root)


def test_an_unlisted_file_is_refused(tmp_path: Path) -> None:
    root = _package(tmp_path / "staged", _files())
    (root / "bin/planted.dll").write_bytes(b"x")
    with pytest.raises(PackageCopyError, match="planted"):
        verify_package(root)


def test_a_staged_package_that_is_not_as_built_is_unavailable_and_never_copied(tmp_path: Path) -> None:
    root = _package(tmp_path / "staged", _files())
    (root / "python.exe").write_bytes(b"tampered")
    copies = tmp_path / "copies"
    with pytest.raises(UnavailableError) as raised:
        verified_copy(root, copies)
    assert raised.value.reason == "package_unverified"
    assert not copies.exists() or not any(copies.iterdir())


def test_the_copy_is_reused_while_it_matches_and_replaced_once_it_changes(tmp_path: Path) -> None:
    staged = _package(tmp_path / "staged", _files())
    copies = tmp_path / "copies"
    first = verified_copy(staged, copies)
    assert Path(first.root).parent == copies
    assert verified_copy(staged, copies).root == first.root
    (Path(first.root) / "bin/aeat.exe").write_bytes(b"edited by a run")
    with pytest.raises(PackageCopyError):
        reverify_copy(first)
    assert not Path(first.root).exists()
    again = verified_copy(staged, copies)
    assert (Path(again.root) / "bin/aeat.exe").read_bytes() == b"cli"
    assert (staged / "bin/aeat.exe").read_bytes() == b"cli"


def _checkout(root: Path, module: bytes) -> Path:
    for relative, content in {
        "cadrumo/core/thing.py": module,
        "cadrumo/core/tests/test_thing.py": b"",
        "cadrumo/conftest.py": b"",
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return root


def test_a_package_equal_to_the_checkout_is_current(tmp_path: Path) -> None:
    package = _package(tmp_path / "staged", _files())
    comparison = compare_with_checkout(package, _checkout(tmp_path / "src", b"VALUE = 1\n"))
    assert comparison.current
    assert comparison.compared == 1
    require_current(comparison, measure_stale=False)


def test_a_stale_module_is_refused_unless_measuring_it_was_asked(tmp_path: Path) -> None:
    package = _package(tmp_path / "staged", _files())
    comparison = compare_with_checkout(package, _checkout(tmp_path / "src", b"VALUE = 2\n"))
    assert comparison.differing == ("cadrumo/core/thing.py",)
    with pytest.raises(UnavailableError) as raised:
        require_current(comparison, measure_stale=False)
    assert raised.value.reason == "package_stale"
    require_current(comparison, measure_stale=True)


def test_a_module_missing_from_the_package_is_stale(tmp_path: Path) -> None:
    package = _package(tmp_path / "staged", _files())
    source = _checkout(tmp_path / "src", b"VALUE = 1\n")
    (source / "cadrumo/core/added.py").write_bytes(b"NEW = True\n")
    comparison = compare_with_checkout(package, source)
    assert comparison.only_in_checkout == ("cadrumo/core/added.py",)
    assert not comparison.current
