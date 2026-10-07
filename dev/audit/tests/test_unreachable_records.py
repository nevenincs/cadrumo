"""Native generation consumes qualified record fields and whole enum declarations."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..unreachable_code import scan_unreachable_code
from ..unreachable_models import ShippedModule, UnreachableCodeOutcome
from ..unreachable_records import record_member_uses
from ..unreachable_tree import EntryPoint, OutsideCorpus, ShippedTreeSpec

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _module(name: str, source: str) -> ShippedModule:
    return ShippedModule(name, Path(name + ".py"), False, ast.parse(source))


def test_whole_reads_resolve_only_the_declared_record_owner() -> None:
    records = _module(
        "pkg.records",
        """
from typing import NamedTuple
from enum import StrEnum
class Record(NamedTuple):
    value: str
    def orphan(self): pass
class Other(NamedTuple):
    value: str
class Kind(StrEnum):
    USED = 'used'
    OPAQUE = 'opaque'
class OtherKind(StrEnum):
    OPAQUE = 'opaque'
RECORD = Record('a')
""",
    )
    consumer = _module(
        "dev.consumer",
        """
from pkg.records import RECORD, Other, Kind as K, OtherKind
result = RECORD._asdict()
constructed = Other('b')
values = [kind.value for kind in K]
def shadow(K):
    return [kind.value for kind in K]
def unused(value):
    return value._asdict()
""",
    )
    assert record_member_uses({records.name: records, consumer.name: consumer}, frozenset({consumer.name})) == {
        (records.name, "Record.value"),
        (records.name, "Kind.USED"),
        (records.name, "Kind.OPAQUE"),
    }


def test_native_storage_generator_reads_the_live_record_and_enum() -> None:
    modules = {}
    for name, relative in (
        ("cadrumo.core.storage_environment", "src/cadrumo/core/storage_environment.py"),
        ("dev.packaging.native.generate", "dev/packaging/native/generate.py"),
    ):
        path = REPO_ROOT / relative
        modules[name] = ShippedModule(name, path, False, ast.parse(path.read_bytes()))
    uses = record_member_uses(modules, frozenset({"dev.packaging.native.generate"}))
    assert ("cadrumo.core.storage_environment", "StoragePathRules.enforce_existing_permissions") in uses
    assert ("cadrumo.core.storage_environment", "InheritedEnvironmentValueKind.OPAQUE") in uses


@pytest.mark.parametrize("directory,label", [("dev", "dev"), ("tests", "tests")])
def test_only_developer_consumers_clear_shipped_record_members(tmp_path: Path, directory: str, label: str) -> None:
    package = tmp_path / "src/pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "cli.py").write_text("from . import records\ndef main(): pass", encoding="utf-8")
    (package / "records.py").write_text(
        """
from typing import NamedTuple
from enum import StrEnum
class Record(NamedTuple):
    value: str
class Kind(StrEnum):
    MEMBER = 'member'
RECORD = Record('a')
""",
        encoding="utf-8",
    )
    outside = tmp_path / directory
    outside.mkdir()
    (outside / "consumer.py").write_text(
        """
from pkg.records import RECORD, Kind
result = RECORD._asdict()
values = [kind.value for kind in Kind]
""",
        encoding="utf-8",
    )
    spec = ShippedTreeSpec(
        repo_root=tmp_path,
        src_root=tmp_path / "src",
        package="pkg",
        entry_points=(EntryPoint("pkg.cli", "main"),),
        outside=(OutsideCorpus(label, outside),),
    )
    result = scan_unreachable_code(spec)
    assert result.outcome is not UnreachableCodeOutcome.ERROR
    findings = {(finding.module, finding.qualname) for finding in result.symbols}
    for member in ("Record.value", "Kind.MEMBER"):
        assert (("pkg.records", member) in findings) is (label == "tests")
