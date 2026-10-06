"""C++ ABI admission uses complete needs and the exact reviewed floor provider."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ...runtime_wheelhouse_contract import target_platform
from .. import linux_cxx_abi
from ..hashing import digest
from ..target import toolchain_for_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_IMAGE = "quay.io/pypa/manylinux_2_28_x86_64@sha256:" + "a" * 64
_EXPORTED = ("GLIBCXX_3.4", "GLIBCXX_3.4.21", "GLIBCXX_3.4.25", "CXXABI_1.3", "CXXABI_1.3.11", "CXXABI_FLOAT128")


def _definitions(names: tuple[str, ...] = _EXPORTED, base: str = "libstdc++.so.6") -> str:
    entries = [("BASE", base), *(("none", name) for name in names)]
    lines = [f"Version definition section '.gnu.version_d' contains {len(entries)} entries:"]
    lines.append(" Addr: 0x10  Offset: 0x10  Link: 2 (.dynstr)")
    for index, (flags, name) in enumerate(entries):
        lines.append(f"  0x{index * 28:04x}: Rev: 1  Flags: {flags}  Index: {index + 1}  Cnt: 1  Name: {name}")
    return "\n".join(lines) + "\n"


def _needs(*names: str, dependency: str = "libstdc++.so.6") -> str:
    lines = [
        "Version needs section '.gnu.version_r' contains 1 entry:",
        " Addr: 0x10  Offset: 0x10  Link: 2 (.dynstr)",
        f"  000000: Version: 1  File: {dependency}  Cnt: {len(names)}",
    ]
    for index, name in enumerate(names):
        lines.append(f"  0x{(index + 1) * 16:04x}: Name: {name}  Flags: none  Version: {index + 2}")
    return "\n".join(lines) + "\n"


def _elf(path: Path, machine: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(64)
    data[:7] = b"\x7fELF\x02\x01\x01"
    struct.pack_into("<H", data, 18, machine)
    path.write_bytes(data)
    return path


@dataclass
class _Campaign:
    package: Path
    manifest: dict[str, Any]
    proof_path: Path
    proof: dict[str, Any]
    tool: Path
    tool_sha256: str
    provider: Path
    outputs: dict[str, str]
    calls: list[str]
    proof_sha256: str = ""
    admitted_image: str = _IMAGE

    def write_proof(self) -> None:
        self.proof_path.write_text(json.dumps(self.proof), encoding="utf-8")
        self.proof_sha256 = digest(self.proof_path)

    def add_image(self, relative: str, output: str, machine: int | None = None) -> Path:
        path = _elf(self.package / relative, machine or self.proof["provider"]["elf_machine"])
        self.manifest["files"][relative] = digest(path)
        self.outputs[str(path)] = output
        return path

    def verify(self) -> dict[str, Any]:
        return linux_cxx_abi.verify_linux_cxx_abi(
            self.package,
            self.manifest,
            provider_evidence=self.proof_path,
            provider_evidence_sha256=self.proof_sha256,
            admitted_image=self.admitted_image,
            readelf=self.tool,
            readelf_sha256=self.tool_sha256,
        )


@pytest.fixture
def campaign(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Campaign:
    package = tmp_path / "package á with spaces"
    package.mkdir()
    proof_root = tmp_path / "retained floor"
    provider = _elf(proof_root / "lib/libstdc++.so.6.0.25", 62)
    tool = tmp_path / "selected-readelf"
    tool.write_bytes(b"exact admitted builder tool")
    manifest = {
        "build": {"target": "linux-x86-64"},
        "layout": {"platform": "linux-x86-64", "native_system_libraries": ["libstdc++.so.6"]},
        "files": {},
        "user_docs": {"directory": "docs", "bundled": False},
        "inputs": {"build_toolchain": {"native_tool_sha256": {"readelf": digest(tool)}}},
    }
    proof = {
        "schema": linux_cxx_abi.SCHEMA,
        "target": "linux-x86-64",
        "floor": "glibc-2.28",
        "image": _IMAGE,
        "provider": {
            "path": "lib/libstdc++.so.6.0.25",
            "source_path": "/usr/lib64/libstdc++.so.6.0.25",
            "sha256": digest(provider),
            "soname": "libstdc++.so.6",
            "elf_machine": 62,
        },
    }
    result = _Campaign(package, manifest, proof_root / "provider.json", proof, tool, digest(tool), provider, {}, [])
    result.outputs[str(provider)] = _definitions()
    result.write_proof()

    def selected_tool(argv: list[str], *, cwd: Path, environment: dict[str, str], timeout_seconds: int) -> Any:
        assert argv[:3] == [str(tool), "--version-info", "--wide"]
        assert cwd == Path(argv[-1]).parent
        assert environment["LC_ALL"] == "C" and timeout_seconds == 30
        result.calls.append(argv[-1])
        return SimpleNamespace(returncode=0, stdout=result.outputs[argv[-1]], stderr="")

    monkeypatch.setattr(linux_cxx_abi, "run_command", selected_tool)
    return result


@pytest.mark.parametrize("target,machine", [("linux-x86-64", 62), ("linux-aarch64", 183)])
def test_all_delivered_elf_images_use_exact_floor_exports(campaign: _Campaign, target: str, machine: int) -> None:
    campaign.manifest["build"]["target"] = campaign.manifest["layout"]["platform"] = target
    campaign.proof["target"] = target
    if target == "linux-aarch64":
        campaign.admitted_image = _IMAGE.replace("x86_64", "aarch64")
        campaign.proof["image"] = campaign.admitted_image
    campaign.proof["provider"]["elf_machine"] = machine
    _elf(campaign.provider, machine)
    campaign.proof["provider"]["sha256"] = digest(campaign.provider)
    campaign.write_proof()
    executable = campaign.add_image("cadrumo", _needs("GLIBCXX_3.4.21", "CXXABI_1.3.11"))
    private = campaign.add_image("bin/private/libdependency.so", _needs("CXXABI_FLOAT128"))
    result = campaign.verify()
    assert result["passed"] and result["elf_machine"] == machine
    assert result["images"]["bin/private/libdependency.so"]["required"] == ["CXXABI_FLOAT128"]
    assert result["provider_sha256"] == digest(campaign.provider)
    assert result["proof_sha256"] == digest(campaign.proof_path) and result["tool_sha256"] == digest(campaign.tool)
    assert set(campaign.calls) == {str(campaign.provider), str(executable), str(private)}


@pytest.mark.parametrize("missing", ["GLIBCXX_3.4.22", "CXXABI_1.3.10", "CXXABI_TM_1"])
def test_maximum_version_does_not_cover_a_missing_exact_requirement(campaign: _Campaign, missing: str) -> None:
    campaign.add_image("bin/private/libdependency.so", _needs(missing))
    with pytest.raises(ValueError, match="versions absent from target-floor provider"):
        campaign.verify()


def test_image_exports_are_not_mistaken_for_requirements(campaign: _Campaign) -> None:
    campaign.add_image("image.so", _definitions(("GLIBCXX_99.0",), base="image.so") + _needs("GLIBCXX_3.4"))
    assert campaign.verify()["images"]["image.so"]["required"] == ["GLIBCXX_3.4"]


@pytest.mark.parametrize("shadow", ["filename", "renamed_base"])
def test_bundled_system_provider_is_refused(campaign: _Campaign, shadow: str) -> None:
    relative = "bin/libstdc++.so.6" if shadow == "filename" else "bin/private/renamed.so"
    campaign.add_image(relative, _definitions())
    with pytest.raises(ValueError, match="shadows system libstdc"):
        campaign.verify()


def test_cxx_versions_cannot_be_attributed_to_another_dependency(campaign: _Campaign) -> None:
    campaign.add_image("image.so", _needs("GLIBCXX_3.4", dependency="other.so"))
    with pytest.raises(ValueError, match="names a different provider"):
        campaign.verify()


@pytest.mark.parametrize(
    "owner,field,value,reason",
    [
        ("proof", "target", "linux-aarch64", "schema/target/floor mismatch"),
        ("proof", "floor", "glibc-2.29", "schema/target/floor mismatch"),
        ("proof", "schema", "unknown", "schema/target/floor mismatch"),
        ("proof", "exports", [], "Malformed floor-provider proof fields"),
        ("proof", "image", "quay.io/pypa/floor:latest", "digest-pinned"),
        ("proof", "image", "quay.io/pypa/other@sha256:" + "b" * 64, "separately admitted"),
        ("provider", "soname", "other.so", "SONAME/ELF machine mismatch"),
        ("provider", "elf_machine", 183, "SONAME/ELF machine mismatch"),
        ("provider", "path", "../libstdc++.so.6", "Unsafe package-relative"),
        ("provider", "source_path", "host/libstdc++.so.6", "resolved system library"),
    ],
)
def test_proof_identity_and_finite_fields_fail_closed(
    campaign: _Campaign, owner: str, field: str, value: Any, reason: str
) -> None:
    record = campaign.proof if owner == "proof" else campaign.proof["provider"]
    record[field] = value
    campaign.write_proof()
    with pytest.raises(ValueError, match=reason):
        campaign.verify()
    assert not campaign.calls


@pytest.mark.parametrize("owner", ["proof", "provider", "tool", "image"])
def test_changed_input_bytes_cannot_use_an_admitted_identity(campaign: _Campaign, owner: str) -> None:
    image = campaign.add_image("image.so", _needs("GLIBCXX_3.4"))
    path = {"proof": campaign.proof_path, "provider": campaign.provider, "tool": campaign.tool, "image": image}[owner]
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="bytes differ from admitted"):
        campaign.verify()


@pytest.mark.parametrize("owner", ["provider", "image"])
def test_actual_elf_machine_must_match_the_proof(campaign: _Campaign, owner: str) -> None:
    image = campaign.add_image("image.so", _needs("GLIBCXX_3.4"))
    if owner == "provider":
        _elf(campaign.provider, 183)
        campaign.proof["provider"]["sha256"] = digest(campaign.provider)
        campaign.write_proof()
    else:
        _elf(image, 183)
        campaign.manifest["files"]["image.so"] = digest(image)
    with pytest.raises(ValueError, match="Wrong target ELF architecture"):
        campaign.verify()


@pytest.mark.parametrize(
    "output,reason",
    [
        (_needs("GLIBCXX_3.4").replace("Cnt: 1", "Cnt: 2"), "Truncated readelf version-needs group"),
        (_needs("GLIBCXX_3.4").replace("contains 1 entry", "contains 2 entries"), "Truncated readelf version section"),
        (_needs("GLIBCXX_3.4").replace("Name: GLIBCXX_3.4", "Name:"), "Malformed readelf version need"),
        ("", "Missing readelf version information"),
    ],
)
def test_partial_or_malformed_tool_output_cannot_pass(campaign: _Campaign, output: str, reason: str) -> None:
    campaign.add_image("image.so", output)
    with pytest.raises(ValueError, match=reason):
        campaign.verify()


def test_truncated_provider_definitions_cannot_pass(campaign: _Campaign) -> None:
    campaign.outputs[str(campaign.provider)] = _definitions().replace("contains 7 entries", "contains 8 entries")
    with pytest.raises(ValueError, match="Truncated readelf version section"):
        campaign.verify()


def test_wrong_actual_provider_soname_cannot_pass(campaign: _Campaign) -> None:
    campaign.outputs[str(campaign.provider)] = _definitions(base="other.so")
    with pytest.raises(ValueError, match="version BASE"):
        campaign.verify()


def test_tool_identity_must_match_the_package_build(campaign: _Campaign) -> None:
    campaign.manifest["inputs"]["build_toolchain"]["native_tool_sha256"]["readelf"] = "f" * 64
    with pytest.raises(ValueError, match="differs from package build provenance"):
        campaign.verify()
    assert not campaign.calls


def test_duplicate_proof_fields_are_refused(campaign: _Campaign) -> None:
    text = campaign.proof_path.read_text(encoding="utf-8")
    campaign.proof_path.write_text(text.replace('"target":', '"target":"linux-aarch64","target":'), encoding="utf-8")
    campaign.proof_sha256 = digest(campaign.proof_path)
    with pytest.raises(ValueError, match="Duplicate floor-provider proof field"):
        campaign.verify()


def test_missing_proof_is_not_a_skipped_check(campaign: _Campaign) -> None:
    campaign.proof_path.unlink()
    with pytest.raises(ValueError, match="floor-provider proof bytes differ"):
        campaign.verify()


def test_unversioned_images_still_require_real_floor_evidence(campaign: _Campaign) -> None:
    campaign.add_image("plain", "No version information found in this file.\n")
    assert campaign.verify()["images"]["plain"]["required"] == []


def test_tool_failure_is_retained_as_failure(campaign: _Campaign, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        linux_cxx_abi,
        "run_command",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="cannot read provider"),
    )
    with pytest.raises(ValueError, match=r"readelf failed.*cannot read provider"):
        campaign.verify()


def test_tool_replacement_during_invocation_is_refused(campaign: _Campaign, monkeypatch: pytest.MonkeyPatch) -> None:
    def replace_tool(*args: Any, **kwargs: Any) -> Any:
        campaign.tool.write_bytes(b"replacement tool")
        return SimpleNamespace(returncode=0, stdout=_definitions(), stderr="")

    monkeypatch.setattr(linux_cxx_abi, "run_command", replace_tool)
    with pytest.raises(ValueError, match="readelf tool bytes differ"):
        campaign.verify()


def test_unlisted_elf_cannot_bypass_abi_admission(campaign: _Campaign) -> None:
    campaign.add_image("image.so", _needs("GLIBCXX_3.4"))
    _elf(campaign.package / "bin/private/unlisted.so", 62)
    with pytest.raises(ValueError, match="Delivered files differ"):
        campaign.verify()


def test_a_layout_without_system_only_provider_policy_is_refused(campaign: _Campaign) -> None:
    campaign.manifest["layout"]["native_system_libraries"] = []
    with pytest.raises(ValueError, match="declared system libstdc"):
        campaign.verify()


def test_an_empty_elf_inventory_is_not_success(campaign: _Campaign) -> None:
    with pytest.raises(ValueError, match="no target ELF images"):
        campaign.verify()


@pytest.mark.parametrize(
    "output,reason",
    [
        (
            "Version symbols section '.gnu.version' contains 1340 entries:\n",
            "Truncated readelf version section",
        ),
        (
            "Version symbols section '.gnu.version' contains 2 entries:\n"
            " Addr: 0x000000000001bed8  Offset: 0x0001bed8  Link: 1 (.dynsym)\n"
            "  000:   0 (*local*)       2 (GLIBCXX_3.4)\n",
            "symbols reference missing version definitions/needs",
        ),
    ],
)
def test_truncated_symbols_prefix_does_not_mean_no_requirements(campaign: _Campaign, output: str, reason: str) -> None:
    campaign.add_image("image.so", output)
    with pytest.raises(ValueError, match=reason):
        campaign.verify()


def test_real_gnu_symbol_shape_resolves_names_from_the_needs_section(campaign: _Campaign) -> None:
    # Shape and names are from the retained GNU readelf2.41 pikepdf stage24 output;
    # the complete 46-image output corpora are validated separately for both targets.
    symbols = (
        "Version symbols section '.gnu.version' contains 4 entries:\n"
        " Addr: 0x000000000001bed8  Offset: 0x0001bed8  Link: 1 (.dynsym)\n"
        "  000:   0 (*local*)       2 (GLIBCXX_3.4)   3 (CXXABI_1.3)    1 (*global*)\n"
    )
    campaign.add_image("image.so", symbols + _needs("GLIBCXX_3.4", "CXXABI_1.3"))
    assert campaign.verify()["images"]["image.so"]["required"] == ["CXXABI_1.3", "GLIBCXX_3.4"]


@pytest.mark.parametrize(
    "target,image",
    [
        (
            "linux-x86-64",
            "quay.io/pypa/manylinux_2_28_x86_64@sha256:39df0042d5cc900b085aa25a0659368b42a0006c54c474299b785b44c1b4ff82",
        ),
        (
            "linux-aarch64",
            "quay.io/pypa/manylinux_2_28_aarch64@sha256:f5f03dedf61b47d69d0742d36047db78adeee3bdb7a9910ff52304750ecf2514",
        ),
    ],
)
def test_separate_provider_admission_matches_the_canonical_target_floor(target: str, image: str) -> None:
    provider = toolchain_for_target(target)["cpp_abi_floor"]
    assert provider == {"floor": target_platform(target).floor, "image": image}


def test_configure_admission_returns_exact_contained_provider_without_running_a_tool(campaign: _Campaign) -> None:
    proof, provider = linux_cxx_abi.admit_linux_cxx_proof(
        campaign.proof_path,
        campaign.proof_sha256,
        target="linux-x86-64",
        admitted_image=campaign.admitted_image,
    )
    assert proof == campaign.proof and provider == campaign.provider
    assert not campaign.calls
