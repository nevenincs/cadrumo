"""A clean validation recorded by one process is honoured by the next one.

Each phase runs in its own child interpreter, so a verdict counts only if it
survived its writer's exit. The store must also stay in one place for the
whole of a process: the development path constants seed the storage root, and
validation used to import them only partway through a compile, after the
verdict had already been looked up under the default root.
"""

from __future__ import annotations

import os
import shutil
import sys
import textwrap
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.tests.audited_process import run_audited_process
from cadrumo.tests.env_scope import scoped_env_var
from dev.cache_root import DEV_CACHE_ROOT_ENV

from ..authority import compilation_receipt
from ..loader_cache import REGISTRY_DISK_CACHE_DIR_ENV
from ..validation_verdict_cache import (
    VERDICT_CACHE_DIR_ENV,
    is_validated,
    record_validated,
    validation_verdict_scope,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_STORAGE_ROOT_ENV = "CADRUMO_STORAGE_ROOT"
_YEAR_POLICY = Path("legal") / "supported-filing-years.toml"

_STORE_PROBE = textwrap.dedent(
    """
    from dev.registry.compiler.loader_cache import registry_disk_cache_dir
    from dev.registry.compiler.validation_verdict_cache import verdict_cache_dir

    before = (verdict_cache_dir(), registry_disk_cache_dir())
    import dev.paths  # validation reaches this lazily, part-way through a compile
    after = (verdict_cache_dir(), registry_disk_cache_dir())
    print("same" if before == after else f"moved {before} -> {after}")
    """
)

_VERDICT_PROBE = textwrap.dedent(
    """
    import sys
    from pathlib import Path

    from cadrumo.core.resources.bundled_data import bundled_path
    from dev.registry.compiler.authority import compilation_receipt
    from dev.registry.compiler.validation_verdict_cache import is_validated, record_validated

    verdicts = compilation_receipt(Path(sys.argv[1]), bundled_path()).verdicts
    assert verdicts is not None
    print(f"key={verdicts.registry_key}")
    print(f"validated={is_validated(verdicts.registry_key)}")
    if sys.argv[2] == "record":
        record_validated(verdicts.registry_key, subject="registry")
    """
)


def _run_child(program: str, *arguments: str, env: dict[str, str]) -> dict[str, str]:
    completed = run_audited_process(
        [sys.executable, "-c", program, *arguments],
        cwd=_REPOSITORY_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=None,
    )
    assert completed.returncode == 0, completed.stderr
    output = str(completed.stdout)
    return dict(line.split("=", 1) for line in output.splitlines() if "=" in line) | {"stdout": output.strip()}


def _registry_tree(tmp_path: Path) -> Path:
    """Stage one real registry declaration under a temporary root."""
    root = tmp_path / "registry" / "aeat"
    target = root / _YEAR_POLICY
    target.parent.mkdir(parents=True)
    shutil.copyfile(bundled_path("registry", "aeat") / _YEAR_POLICY, target)
    return root


def test_the_stores_do_not_move_when_the_development_paths_load() -> None:
    """A fresh process resolves its verdict and compiled stores to the same place throughout.

    The child starts with no storage root, cache root or store override, as a
    plain developer command does. Before the stores seeded the storage root
    themselves, the lookup went to the default root and the record, made after
    validation imported the path constants, to the checkout's.
    """
    env = dict(os.environ)
    for name in (_STORAGE_ROOT_ENV, DEV_CACHE_ROOT_ENV, VERDICT_CACHE_DIR_ENV, REGISTRY_DISK_CACHE_DIR_ENV):
        env.pop(name, None)

    reported = _run_child(_STORE_PROBE, env=env)

    assert reported["stdout"] == "same"


def test_a_recorded_verdict_survives_its_process_and_an_input_edit_refuses_it(tmp_path: Path) -> None:
    root = _registry_tree(tmp_path)
    store = tmp_path / "verdicts"
    env = {**os.environ, VERDICT_CACHE_DIR_ENV: str(store)}

    first = _run_child(_VERDICT_PROBE, str(root), "record", env=env)
    assert first["validated"] == "False", "the empty store must not already hold a verdict"
    assert (store / f"verdict_{first['key']}.json").is_file(), "the record did not survive its writer's exit"

    second = _run_child(_VERDICT_PROBE, str(root), "check", env=env)
    assert second["key"] == first["key"]
    assert second["validated"] == "True"

    declaration = root / _YEAR_POLICY
    declaration.write_bytes(declaration.read_bytes() + b"\n# edited\n")
    edited = _run_child(_VERDICT_PROBE, str(root), "check", env=env)
    assert edited["key"] != first["key"]
    assert edited["validated"] == "False", "an edited declaration must validate in full again"


def test_a_compiler_change_keys_a_new_verdict(tmp_path: Path) -> None:
    root = _registry_tree(tmp_path)
    receipt = compilation_receipt(root, bundled_path())
    assert receipt.verdicts is not None
    with scoped_env_var(VERDICT_CACHE_DIR_ENV, str(tmp_path / "verdicts")):
        record_validated(receipt.verdicts.registry_key, subject="registry")
        changed = validation_verdict_scope(
            registry_root=receipt.pair.registry_root,
            fingerprints=receipt.identity.fingerprints,
            source_receipt=receipt.source_receipt,
            compiler_source_tree_digest="0" * 64,
        )
        assert is_validated(receipt.verdicts.registry_key)
        assert changed.registry_key != receipt.verdicts.registry_key
        assert not is_validated(changed.registry_key)
