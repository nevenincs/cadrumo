"""Assembly smoke-imports each bundled distribution through the shortest module its RECORD lists."""

from __future__ import annotations

from importlib.metadata import PackagePath

import pytest

from ..assemble import import_surface

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_a_record_written_with_windows_separators_names_its_package() -> None:
    recorded = [
        PackagePath("ormsgpack-1.0.0.dist-info\\RECORD"),
        PackagePath("ormsgpack\\__init__.py"),
        PackagePath("ormsgpack\\_ormsgpack.pyi"),
    ]
    assert import_surface("ormsgpack", recorded) == "ormsgpack"


def test_posix_and_windows_separators_select_the_same_module() -> None:
    posix = [PackagePath("example/sub/module.py"), PackagePath("example/__init__.py")]
    windows = [PackagePath("example\\sub\\module.py"), PackagePath("example\\__init__.py")]
    assert import_surface("example", posix) == import_surface("example", windows) == "example"


def test_tests_entry_points_and_non_identifiers_are_never_the_surface() -> None:
    recorded = [
        PackagePath("example\\tests\\test_thing.py"),
        PackagePath("example\\__main__.py"),
        PackagePath("not-a-module\\thing.py"),
        PackagePath("example\\core.py"),
    ]
    assert import_surface("example", recorded) == "example.core"


def test_a_distribution_without_a_python_module_is_refused() -> None:
    with pytest.raises(ValueError, match="No reviewed Python import surface for distribution data-only"):
        import_surface("data-only", [PackagePath("data-only\\payload.bin"), PackagePath("data_only\\tests\\x.py")])
