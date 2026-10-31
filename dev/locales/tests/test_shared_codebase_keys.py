"""The codebase-key scan over the checkout is shared across a run and follows every file it reads."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dev.quality import shared_scan

from .. import manager as manager_module
from .._paths import LOCALE_SOURCE_EXTRA_DIRS, SRC_DIR
from ..manager import LocaleManager, _codebase_key_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LITERAL = re.compile(r'tr\("([\w.]+)"\)')


def test_a_shared_key_scan_follows_an_edit_to_a_scanned_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Managers over one tree share one scan; an edited source is scanned again, not served stale.

    Only the scan body is replaced, by one reading the planted tree's literals:
    the subject is the sharing and its key, which run unchanged.
    """
    repository = tmp_path.resolve()
    package = repository / "src" / "planted"
    package.mkdir(parents=True)
    module = package / "module.py"
    module.write_text('tr("planted.first")\n', encoding="utf-8")
    calls: list[None] = []

    def scan(self: LocaleManager) -> tuple[frozenset[str], tuple[str, ...]]:
        calls.append(None)
        keys = frozenset(str(key) for key in _LITERAL.findall(module.read_text(encoding="utf-8")))
        return keys, ()

    monkeypatch.setattr(manager_module, "REPO_ROOT", repository)
    monkeypatch.setattr(LocaleManager, "_scan_codebase_keys", scan)
    monkeypatch.setattr(shared_scan, "_memo", {})
    monkeypatch.setenv("CADRUMO_RUN_ARTIFACT_ROOT", str(repository / "run-cache"))

    first = LocaleManager(package, repository / "locales").get_codebase_keys()
    second = LocaleManager(package, repository / "locales").get_codebase_keys()
    module.write_text('tr("planted.second")\n', encoding="utf-8")
    edited = LocaleManager(package, repository / "locales").get_codebase_keys()

    assert first == second == {"planted.first"}
    assert edited == {"planted.second"}
    assert len(calls) == 2, "an unchanged tree must be scanned once for every manager over it"


def test_the_shared_key_scan_is_keyed_on_every_kind_of_input_it_reads() -> None:
    """The key covers source, packaged TOML data, the extra roots and the scanner's own code."""
    inputs = set(_codebase_key_inputs((SRC_DIR, *LOCALE_SOURCE_EXTRA_DIRS)))
    repository = manager_module.REPO_ROOT

    assert SRC_DIR / "core" / "hashing.py" in inputs
    assert repository / "src" / "cadrumo_client" / "contracts" / "navigation.toml" in inputs
    assert any(path.suffix == ".toml" and "registry" in path.parts for path in inputs)
    assert any(path.is_relative_to(repository / "dev" / "docs") for path in inputs)
    assert repository / "dev" / "locales" / "manager.py" in inputs
    assert repository / "dev" / "registry" / "compiler" / "loader.py" in inputs
    assert not any("__pycache__" in path.parts for path in inputs)
