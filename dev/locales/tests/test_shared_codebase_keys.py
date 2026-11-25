"""The codebase-key scan over the checkout is shared across a run and follows every file it reads."""

from __future__ import annotations

import re
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import pytest

from dev.quality import shared_scan

from .. import manager as manager_module
from ..manager import LocaleManager, codebase_key_inputs
from ..paths import LOCALE_SOURCE_EXTRA_DIRS, SRC_DIR

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
    monkeypatch.setattr(manager_module, "discovery_path_inputs", lambda: ())
    monkeypatch.setattr(LocaleManager, "scan_codebase_keys", scan)
    monkeypatch.setattr(shared_scan, "memo", {})
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
    inputs = set(codebase_key_inputs((SRC_DIR, *LOCALE_SOURCE_EXTRA_DIRS)))
    repository = manager_module.REPO_ROOT

    assert SRC_DIR / "core" / "hashing.py" in inputs
    assert repository / "src" / "cadrumo_client" / "contracts" / "navigation.toml" in inputs
    assert any(path.suffix == ".toml" and "registry" in path.parts for path in inputs)
    assert any(path.is_relative_to(repository / "dev" / "docs") for path in inputs)
    assert repository / "dev" / "locales" / "manager.py" in inputs
    assert repository / "dev" / "registry" / "compiler" / "loader.py" in inputs
    assert not any("__pycache__" in path.parts for path in inputs)


@pytest.mark.parametrize("constant", [False, True])
def test_an_import_before_a_scanner_edit_cannot_poison_the_current_implementation_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, constant: bool
) -> None:
    repository = tmp_path.resolve()
    package = repository / "src" / "planted"
    package.mkdir(parents=True)
    (package / "module.py").write_text("value = 1\n", encoding="utf-8")
    tooling = repository / "dev" / "locales"
    tooling.mkdir(parents=True)
    helper = tooling / "_ast_planted.py"

    def load(key: str) -> ModuleType:
        source = (
            f"KEYS = frozenset({{{key!r}}})\ndef keys(): return KEYS\n"
            if constant
            else f"def keys(): return frozenset({{{key!r}}})\n"
        )
        helper.write_text(source, encoding="utf-8")
        spec = spec_from_file_location("planted_scanner", helper)
        assert spec is not None and spec.loader is not None
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    imported = [load("planted.old")]
    current = load("planted.current")
    calls: list[None] = []

    def scan(self: LocaleManager) -> tuple[frozenset[str], tuple[str, ...]]:
        calls.append(None)
        keys = imported[0].keys()
        assert isinstance(keys, frozenset)
        return frozenset(str(key) for key in keys), ()

    monkeypatch.setattr(manager_module, "REPO_ROOT", repository)
    monkeypatch.setattr(manager_module, "codebase_key_scanner_modules", lambda: tuple(imported))
    monkeypatch.setattr(manager_module, "discovery_path_inputs", lambda: (helper,))
    monkeypatch.setattr(LocaleManager, "scan_codebase_keys", scan)
    monkeypatch.setattr(shared_scan, "memo", {})
    monkeypatch.setenv("CADRUMO_RUN_ARTIFACT_ROOT", str(repository / "run-cache"))

    assert LocaleManager(package, repository / "locales").get_codebase_keys() == {"planted.old"}
    imported[0] = current
    monkeypatch.setattr(shared_scan, "memo", {})

    assert LocaleManager(package, repository / "locales").get_codebase_keys() == {"planted.current"}
    assert len(calls) == 2, "different loaded implementations must not share a source-only cache entry"
