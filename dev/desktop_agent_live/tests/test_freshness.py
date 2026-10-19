"""The lane names each staged part, and the test host, that is older than a source it is built from."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ...packaging.native.layout import load_layout
from ..freshness import built_from, host_part, newer_source, package_parts, stale_parts

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUILT = 1_800_000_000_000_000_000
_SECOND = 1_000_000_000
_OLD = _BUILT - 10 * _SECOND
_NEW = _BUILT + 10 * _SECOND


def _write(path: Path, *, at: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    os.utime(path, ns=(at, at))
    return path


@pytest.mark.parametrize(
    ("relative", "built"),
    [
        ("native/desktop/src-tauri/src/manager.rs", True),
        ("native/desktop/frontend/src/App.tsx", True),
        ("Y:/code/agent/src/cadrumo_agent/service.py", True),
        ("native/desktop/src-tauri/src/manager/tests.rs", False),
        ("native/desktop/src-tauri/src/shell/setup/track_tests.rs", False),
        ("native/desktop/frontend/tests/live/attach.live.ts", False),
        ("native/desktop/frontend/src/components/Rail.stories.tsx", False),
        ("native/desktop/frontend/src/shell/agentCatalog.test.ts", False),
        ("src/cadrumo/core/tests/test_hashing.py", False),
    ],
)
def test_only_files_built_into_the_product_count_as_its_sources(relative: str, built: bool) -> None:
    assert built_from(relative) is built


def test_the_newest_source_changed_after_the_artifact_is_named(tmp_path: Path) -> None:
    artifact = _write(tmp_path / "image.exe", at=_BUILT)
    older = _write(tmp_path / "a.rs", at=_BUILT - _SECOND)
    newer = _write(tmp_path / "b.rs", at=_BUILT + _SECOND)
    newest = _write(tmp_path / "c.rs", at=_BUILT + 2 * _SECOND)
    assert newer_source(artifact, [older]) is None
    assert newer_source(artifact, [older, newer, newest, tmp_path / "removed.rs"]) == newest


class _Checkout:
    """A synthetic checkout, binary directory and staged package, every part built at ``_BUILT``."""

    def __init__(self, root: Path) -> None:
        self.layout = load_layout("windows-x64")
        self.repository, self.build = root / "checkout", root / "build"
        self.package = self.build / "stage" / "Debug" / "app"
        packages = self.package / self.layout["paths"]["packages"]
        self.desktop = _write(self.package / "cadrumo.exe", at=_BUILT)
        self.manager = _write(self.package / "cadrumo-manager.exe", at=_BUILT)
        _write(self.package / self.layout["paths"]["executable"], at=_BUILT)
        for image in ("aeat", "cadrumo-mcp", "cadrumo-runtime", "cadrumo-agent-service"):
            _write(self.package / "bin" / f"{image}.exe", at=_BUILT)
        self.product = _write(packages / "cadrumo-0.6.0.dist-info" / "RECORD", at=_BUILT)
        self.agent = _write(packages / "cadrumo_agent-0.1.0.dist-info" / "RECORD", at=_BUILT)
        self.record = _write(self.build / "desktop" / "testing" / "packaged" / "host.json", at=_BUILT)
        self.sources = {
            "desktop": _write(self.repository / "native/desktop/src-tauri/src/app.rs", at=_OLD),
            "desktop test": _write(self.repository / "native/desktop/src-tauri/src/app/tests.rs", at=_NEW),
            "manager": _write(self.repository / "native/manager/src/lib.rs", at=_OLD),
            "interpreter": _write(self.repository / "native/interpreter/windows/python.c", at=_OLD),
            "product": _write(self.repository / "src/cadrumo/module.py", at=_OLD),
            "tooling": _write(self.repository / "dev/packaging/assemble.py", at=_NEW),
            "build output": _write(self.build / "inputs/runtime/ready", at=_NEW),
            "agent": _write(root / "agent/src/cadrumo_agent/service.py", at=_OLD),
        }
        listing = [self.sources[name] for name in ("product", "tooling", "build output")]
        (self.build / "inputs-product.txt").write_text("".join(f"{path.as_posix()}\n" for path in listing))
        (self.build / "inputs-agent.txt").write_text(f"{self.sources['agent'].as_posix()}\n")

    def touch(self, name: str) -> None:
        os.utime(self.sources[name], ns=(_NEW, _NEW))

    def stale(self) -> list[tuple[str, Path, Path, str]]:
        parts = [*package_parts(self.package, self.layout, self.build, self.repository)]
        parts.append(host_part(self.record, self.repository))
        stale, missing = stale_parts(parts)
        assert missing == []
        return [(part.part, part.artifact, part.source, part.target) for part in stale]


def test_parts_older_than_only_tests_tooling_or_build_outputs_are_current(tmp_path: Path) -> None:
    assert _Checkout(tmp_path).stale() == []


def test_a_desktop_crate_change_names_the_desktop_image_and_the_test_host(tmp_path: Path) -> None:
    checkout = _Checkout(tmp_path)
    checkout.touch("desktop")
    source = checkout.sources["desktop"]
    assert checkout.stale() == [
        ("desktop image", checkout.desktop, source, "app-native"),
        ("test host", checkout.record, source, "desktop-packaged-host"),
    ]


@pytest.mark.parametrize(
    ("source", "named"),
    [
        # The desktop image and the test host link the manager crate too.
        (
            "manager",
            [
                ("desktop image", "app-native"),
                ("background-services manager", "app-native"),
                ("test host", "desktop-packaged-host"),
            ],
        ),
        ("interpreter", [("interpreter hosts and entry points", "app-native")]),
        ("product", [("Python product", "app-payload")]),
        ("agent", [("bundled agent", "app-agent")]),
    ],
)
def test_only_the_parts_built_from_a_changed_source_are_named(
    tmp_path: Path, source: str, named: list[tuple[str, str]]
) -> None:
    checkout = _Checkout(tmp_path)
    checkout.touch(source)
    stale = checkout.stale()
    assert [(name, rebuild) for name, _artifact, _source, rebuild in stale] == named
    assert {changed for _name, _artifact, changed, _rebuild in stale} == {checkout.sources[source]}


def test_a_part_with_nothing_staged_is_reported_missing(tmp_path: Path) -> None:
    checkout = _Checkout(tmp_path)
    checkout.agent.unlink()
    parts = package_parts(checkout.package, checkout.layout, checkout.build, checkout.repository)
    assert stale_parts(parts)[1] == ["bundled agent"]
