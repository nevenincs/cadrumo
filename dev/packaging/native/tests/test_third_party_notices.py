"""The notices page lists what a package stages, and assembly refuses what may not ship."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from cadrumo.core.product_identity import PRODUCT_IDENTITY

from ..assembly_identity import installed_distributions
from ..layout import load_layout
from ..third_party_notices import (
    build_render_path,
    collect_notices,
    declared_licence,
    package_refusals,
    require_current_notices,
    target_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TARGET = "windows-x86-64"
_LAYOUT: dict[str, Any] = load_layout(_TARGET)
_PATHS = cast("dict[str, str]", _LAYOUT["paths"])
_FILES = cast("dict[str, str]", _LAYOUT["files"])
_LLAMA_LICENCE = f"{_PATHS['docs']}/licenses/llama.cpp/LICENSE"


def _dist(site: Path, name: str, version: str, *headers: str) -> None:
    folder = f"{name.replace('-', '_')}-{version}.dist-info"
    directory = site / folder
    directory.mkdir(parents=True)
    body = "".join(f"{header}\n" for header in headers)
    (directory / "METADATA").write_text(
        f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n{body}", encoding="utf-8"
    )
    (directory / "RECORD").write_text(f"{folder}/METADATA,,\n{folder}/RECORD,,\n", encoding="utf-8")


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _package(root: Path) -> Path:
    """Assemble the parts of a Windows package the notices read."""
    site = root / _PATHS["packages"]
    _dist(site, "zeta", "2.0", "License-Expression: MIT")
    _dist(site, "playwright", "1.64.1", "License-Expression: Apache-2.0")
    _dist(site, PRODUCT_IDENTITY.cohort_distributions[0], "9.9", "License-Expression: MIT")
    for name in ("llama-server.exe", "llama.dll", "ggml-base.dll", "mtmd.dll", "libomp.dll", "vcruntime140.dll"):
        _write(root / _PATHS["llama_server"] / name)
    licences = root / _PATHS["docs"] / "licenses"
    for name in ("CPython.txt", "llama.cpp/LICENSE", "llama.cpp/LICENSE-LLVM-OpenMP"):
        _write(licences / name)
    runtime = site.parent
    _write(runtime / "agent-runtime.json", json.dumps({"node_version": "26.12.1"}))
    _write(runtime / "node" / "LICENSE")
    _write(site / "playwright" / "driver" / "LICENSE")
    (runtime / "node_modules" / "@scope" / "kept").mkdir(parents=True)
    lock = {
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "runtime"},
            "node_modules/@scope/kept": {"version": "1.0.0", "license": "ISC"},
            "node_modules/absent-optional": {"version": "1.0.0", "license": "MIT"},
            "node_modules/dev-only": {"version": "1.0.0", "license": "MIT", "dev": True},
        },
    }
    _write(runtime / "package-lock.json", json.dumps(lock))
    manifest = {
        "python": "3.13.11",
        "inputs": {
            "llama_server": {"tag": "b12184"},
            "build_toolchain": {"msvc_redist": {"directory": "C:/VS/VC/Redist/MSVC/14.44.35112/x64/CRT"}},
        },
    }
    _write(root / _FILES["package_manifest"], json.dumps(manifest))
    return root


def _refusals(root: Path) -> list[str]:
    notices = collect_notices(root, _PATHS, _FILES)
    return package_refusals(root, notices, installed_distributions(root / _PATHS["packages"]))


def test_every_component_is_listed_with_its_version_licence_and_text(tmp_path: Path) -> None:
    root = _package(tmp_path / "app")
    notices = collect_notices(root, _PATHS, _FILES)

    assert [(n.component, n.version, n.licence) for n in notices.native] == [
        (
            "CPython, with the libraries of its build",
            "3.13.11",
            "PSF-2.0, with the notices of the libraries it bundles",
        ),
        ("llama.cpp: llama-server and the llama, ggml and mtmd libraries", "b12184", "MIT"),
        ("LLVM OpenMP runtime (libomp.dll) from the llama.cpp release", "b12184", "Apache-2.0 WITH LLVM-exception"),
        (
            "Microsoft Visual C++ runtime (vcruntime140.dll)",
            "14.44.35112",
            "Microsoft Visual C++ Redistributable terms",
        ),
        ("Node.js, the agent runtime", "26.12.1", "MIT"),
        ("Node.js, the Playwright driver", "as shipped in playwright 1.64.1", "MIT"),
    ]
    assert [(n.component, n.version, n.licence) for n in notices.python] == [
        ("playwright", "1.64.1", "Apache-2.0"),
        ("zeta", "2.0", "MIT"),
    ]
    assert [(n.component, n.licence) for n in notices.javascript] == [("@scope/kept", "ISC")]
    assert _refusals(root) == []


def test_a_missing_licence_text_refuses_the_package(tmp_path: Path) -> None:
    root = _package(tmp_path / "app")
    (root / _LLAMA_LICENCE).unlink()

    assert _refusals(root) == [f"licence texts the package does not carry: {_LLAMA_LICENCE}"]


def test_a_program_file_no_component_claims_refuses_the_package(tmp_path: Path) -> None:
    root = _package(tmp_path / "app")
    _write(root / _PATHS["llama_server"] / "vulkan-1.dll")

    assert _refusals(root) == ["program files attributed to no listed component: vulkan-1.dll"]


@pytest.mark.parametrize("where", ["python", "javascript"])
def test_a_gpl_component_refuses_the_package(tmp_path: Path, where: str) -> None:
    root = _package(tmp_path / "app")
    if where == "python":
        _dist(root / _PATHS["packages"], "ofxtools", "0.9.5", "License-Expression: GPL-3.0-only")
    else:
        runtime = (root / _PATHS["packages"]).parent
        lock = json.loads((runtime / "package-lock.json").read_text(encoding="utf-8"))
        lock["packages"]["node_modules/copyleft"] = {"version": "1.0.0", "license": "AGPL-3.0-only"}
        (runtime / "node_modules" / "copyleft").mkdir()
        (runtime / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")

    refusals = _refusals(root)
    assert len(refusals) == 1
    assert refusals[0].startswith("GPL- or AGPL-licensed components: ")
    assert ("ofxtools" if where == "python" else "copyleft") in refusals[0]


def test_assembly_writes_the_fresh_page_and_accepts_only_its_committed_copy(tmp_path: Path) -> None:
    root, build, repo = _package(tmp_path / "app"), tmp_path / "build", tmp_path / "repo"

    with pytest.raises(ValueError, match="does not list what this package stages"):
        require_current_notices(_TARGET, root, _PATHS, _FILES, build, repo)
    rendered = build_render_path(build, _TARGET)
    page = target_path(_TARGET, repo)
    page.parent.mkdir(parents=True)
    page.write_bytes(rendered.read_bytes())
    require_current_notices(_TARGET, root, _PATHS, _FILES, build, repo)

    _dist(root / _PATHS["packages"], "added", "1.0", "License-Expression: MIT")
    with pytest.raises(ValueError, match="does not list what this package stages"):
        require_current_notices(_TARGET, root, _PATHS, _FILES, build, repo)


def test_the_licence_is_read_from_the_most_precise_statement(tmp_path: Path) -> None:
    _dist(tmp_path, "expr", "1", "License-Expression: MIT OR Apache-2.0", "Classifier: License :: OSI Approved :: BSD")
    _dist(tmp_path, "classed", "1", "Classifier: License :: OSI Approved :: MIT License", "License: whatever")
    _dist(tmp_path, "fielded", "1", "License: BSD-3-Clause")
    _dist(tmp_path, "long-text", "1", "License: " + "x" * 120, "License-File: LICENSE.txt")
    _dist(tmp_path, "silent", "1")

    assert {d.metadata["Name"]: declared_licence(d) for d in installed_distributions(tmp_path)} == {
        "expr": "MIT OR Apache-2.0",
        "classed": "MIT License",
        "fielded": "BSD-3-Clause",
        "long-text": "stated in LICENSE.txt",
        "silent": "not declared",
    }


@pytest.mark.parametrize(
    ("header", "refused"),
    [
        ("Classifier: License :: OSI Approved :: GNU General Public License v3 (GPLv3)", True),
        ("Classifier: License :: OSI Approved :: GNU Affero General Public License v3", True),
        ("License-Expression: LGPL-2.1-or-later", False),
        ("Classifier: License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)", False),
        ("License-Expression: MPL-2.0", False),
    ],
)
def test_strong_copyleft_is_refused_and_weak_copyleft_is_not(tmp_path: Path, header: str, refused: bool) -> None:
    root = _package(tmp_path / "app")
    _dist(root / _PATHS["packages"], "subject", "1", header)

    assert bool(_refusals(root)) is refused
