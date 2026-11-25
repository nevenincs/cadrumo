"""An observed verdict is recorded only when the observation can stand in for the product it read.

Each case names a stale-PASS hazard: a record that would be reused after an
edit to a product file the sequence did read. The guards send such an
observation to the whole-product closure instead, so the edit ends reuse. The
cases record through the real ``SequenceVerdicts`` over a synthetic repository
and re-open it as a later process would. Expected digests are computed with
``hashlib`` over the bytes on disk.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.tests.env_scope import scoped_env_var
from dev.cache_root import DEV_CACHE_ROOT_ENV, dev_cache_dir
from dev.dependency_observation.observation import CHILD_SCRIPT_NAME, Observation

from ..observed_journals import WORKER_SCRIPT_NAME
from ..verdict_cache import (
    _CACHE_NAME,
    _TOOLING_ENVIRONMENT,
    FORCE_ENV,
    OBSERVATION_SENTINEL,
    authority_compiler_closure,
    configuring_environment,
    write_depfile,
)
from .verdict_tree_support import ALPHA, SyntheticTree, build_tree, write

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_ONE = (ALPHA, "a-one")
_TWO = (ALPHA, "a-two")
_CLI = "src/cadrumo/cli.py"
_RUNTIME = "src/cadrumo_runtime/host.py"
_CONFIGURING = (
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "LC_MESSAGES",
    "TZ",
    "PYTHONHASHSEED",
    "PYTHONUTF8",
    "PYTHONIOENCODING",
    "PYTHONPATH",
    "COLUMNS",
    "NO_COLOR",
    "FORCE_COLOR",
    "TERM",
)


@pytest.fixture
def tree(tmp_path: Path) -> SyntheticTree:
    return build_tree(tmp_path / "repo")


@pytest.fixture
def cache(tmp_path: Path) -> Iterator[Path]:
    with scoped_env_var(DEV_CACHE_ROOT_ENV, str(tmp_path / "cache")), scoped_env_var(FORCE_ENV, None):
        yield tmp_path / "cache"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(tree: SyntheticTree, observation: Observation | None, *, item: tuple[str, str] = _ONE) -> Path:
    verdicts = tree.verdicts()
    sequence = tree.discovered()[item]
    verdicts.record_clean(sequence, key=verdicts.key(sequence), observation=observation)
    directory = dev_cache_dir(_CACHE_NAME)
    return directory / f"{verdicts.key(sequence)}.json"


def _product(record: Path) -> dict[str, object]:
    product = json.loads(record.read_text(encoding="utf-8"))["product"]
    assert isinstance(product, dict)
    return {str(name): value for name, value in product.items()}


def _reusable(tree: SyntheticTree, item: tuple[str, str] = _ONE) -> bool:
    return tree.verdicts().reused(tree.discovered()[item]) is not None


def _edit(tree: SyntheticTree, relative: str) -> None:
    path = tree.repo / relative
    write(path, path.read_text(encoding="utf-8") + "# edited\n")


# Child processes -----------------------------------------------------------------


def test_an_unjudged_child_process_records_the_whole_product_so_any_product_edit_ends_reuse(
    tree: SyntheticTree, cache: Path
) -> None:
    observation = tree.observe(_CLI)
    observation.audit("os.system", ("echo launched",))
    assert observation.incomplete

    assert _product(_record(tree, observation))["mode"] == "closure"
    assert _reusable(tree)
    _edit(tree, _RUNTIME)
    assert not _reusable(tree), "a product file the unjudged child may have read changed"


def test_a_covered_child_launch_leaves_the_record_observed_and_an_unread_edit_harmless(
    tree: SyntheticTree, cache: Path, tmp_path: Path
) -> None:
    journals = tmp_path / "journals"
    observation = tree.observe(_CLI)
    observation.adopt_journal_directory(journals, (WORKER_SCRIPT_NAME, CHILD_SCRIPT_NAME))
    for script in (WORKER_SCRIPT_NAME, CHILD_SCRIPT_NAME):
        observation.audit("subprocess.Popen", (None, [sys.executable, str(journals / script)], None, None))

    assert observation.incomplete == []
    assert _product(_record(tree, observation))["mode"] == "observed"
    _edit(tree, _RUNTIME)
    assert _reusable(tree)
    _edit(tree, _CLI)
    assert not _reusable(tree)


# Entries outside the repository ---------------------------------------------------


def test_an_outside_file_is_recorded_by_absolute_path_and_editing_it_ends_reuse(
    tree: SyntheticTree, cache: Path
) -> None:
    outside = tree.repo.parent / "outside.txt"
    write(outside, "outside")
    observation = tree.observe(_CLI)
    observation.files[outside] = _sha(b"outside")

    product = _product(_record(tree, observation))
    assert product["mode"] == "observed"
    files = product["files"]
    assert isinstance(files, dict)
    assert files[outside.resolve().as_posix()] == _sha(b"outside")
    assert _reusable(tree)
    _edit(tree, _RUNTIME)
    assert _reusable(tree), "a repository file the sequence never read is no input"

    write(outside, "outside, edited")
    assert not _reusable(tree), "the outside file was read, so its edit is the stale-PASS case"


def test_an_outside_file_that_is_deleted_ends_reuse(tree: SyntheticTree, cache: Path) -> None:
    outside = tree.repo.parent / "outside.txt"
    write(outside, "outside")
    observation = tree.observe(_CLI)
    observation.files[outside] = _sha(b"outside")
    _record(tree, observation)
    assert _reusable(tree)
    outside.unlink()
    assert not _reusable(tree)


def test_an_outside_listing_is_recorded_by_absolute_path_and_a_new_entry_ends_reuse(
    tree: SyntheticTree, cache: Path
) -> None:
    directory = tree.repo.parent / "outside-listed"
    write(directory / "a.txt", "a")
    observation = tree.observe(_CLI)
    observation.listings[directory] = _sha(b"a.txt")

    product = _product(_record(tree, observation))
    assert product["mode"] == "observed"
    listings = product["listings"]
    assert isinstance(listings, dict)
    assert listings[directory.resolve().as_posix()] == _sha(b"a.txt")
    assert _reusable(tree)

    write(directory / "b.txt", "b")
    assert not _reusable(tree)


def test_an_outside_entry_does_not_hide_a_missing_sentinel(tree: SyntheticTree, cache: Path) -> None:
    outside = tree.repo.parent / "outside.txt"
    write(outside, "outside")
    observation = tree.observe(_CLI, sentinel=False)
    observation.files[outside] = _sha(b"outside")

    assert _product(_record(tree, observation))["mode"] == "closure"
    _edit(tree, _RUNTIME)
    assert not _reusable(tree)


def test_an_entry_reached_through_a_link_inside_the_repository_to_a_directory_outside_it_is_keyed_outside(
    tree: SyntheticTree, cache: Path
) -> None:
    outside = tree.repo.parent / "linked-outside"
    write(outside / "data.txt", "outside bytes")
    link = tree.repo / "jump"
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(outside), str(link))
    else:
        os.symlink(outside, link, target_is_directory=True)
    observation = tree.observe(_CLI)
    observation.note_file(str(link / "data.txt"))
    assert observation.incomplete == []
    assert link / "data.txt" in observation.files

    product = _product(_record(tree, observation))
    assert product["mode"] == "observed"
    files = product["files"]
    assert isinstance(files, dict)
    assert files[(outside / "data.txt").resolve().as_posix()] == _sha(b"outside bytes")
    assert "jump/data.txt" not in files
    assert _reusable(tree)
    write(outside / "data.txt", "changed through the link")
    assert not _reusable(tree)


def test_an_observation_without_the_product_package_sentinel_records_the_whole_product(
    tree: SyntheticTree, cache: Path
) -> None:
    observation = tree.observe(_CLI, sentinel=False)
    assert tree.repo / OBSERVATION_SENTINEL not in observation.files

    assert _product(_record(tree, observation))["mode"] == "closure"
    _edit(tree, _RUNTIME)
    assert not _reusable(tree)


def test_an_empty_observation_records_the_whole_product_instead_of_reusing_across_every_edit(
    tree: SyntheticTree, cache: Path
) -> None:
    observation = Observation(tree.repo, started_ns=time.time_ns())
    assert observation.files == {} and observation.listings == {} and observation.incomplete == []

    assert _product(_record(tree, observation))["mode"] == "closure"
    assert _reusable(tree)
    _edit(tree, _CLI)
    assert not _reusable(tree), "an empty observed record would have survived this edit"


def test_an_observation_that_read_the_sentinel_is_recorded_as_observed(tree: SyntheticTree, cache: Path) -> None:
    product = _product(_record(tree, tree.observe()))
    assert product["mode"] == "observed"
    assert product["files"] == {OBSERVATION_SENTINEL: _sha((tree.repo / OBSERVATION_SENTINEL).read_bytes())}


# Probed paths --------------------------------------------------------------------


def test_a_probed_absent_path_is_recorded_as_absent_and_creating_it_ends_reuse(
    tree: SyntheticTree, cache: Path
) -> None:
    optional = "src/cadrumo/optional.toml"
    observation = tree.observe(_CLI)
    observation.probe(tree.repo / optional)
    record = _record(tree, observation)
    product = _product(record)
    assert product["mode"] == "observed"
    assert isinstance(product["files"], dict) and product["files"][optional] == "absent"

    # Isolate the file's own digest from the directory listing that also moves.
    document = json.loads(record.read_text(encoding="utf-8"))
    document["product"]["listings"] = {}
    record.write_text(json.dumps(document), encoding="utf-8")
    assert _reusable(tree)

    write(tree.repo / optional, "now = 'present'\n")
    assert not _reusable(tree)


def test_a_probed_directory_is_recorded_as_directory_and_replacing_it_ends_reuse(
    tree: SyntheticTree, cache: Path
) -> None:
    observation = tree.observe(_CLI)
    observation.probe(tree.repo / "src" / "cadrumo_client")
    record = _record(tree, observation)
    product = _product(record)
    assert isinstance(product["files"], dict) and product["files"]["src/cadrumo_client"] == "directory"

    document = json.loads(record.read_text(encoding="utf-8"))
    document["product"]["listings"] = {}
    record.write_text(json.dumps(document), encoding="utf-8")
    assert _reusable(tree)

    (tree.repo / "src/cadrumo_client/transport.py").unlink()
    (tree.repo / "src/cadrumo_client").rmdir()
    write(tree.repo / "src" / "cadrumo_client", "now a file\n")
    assert not _reusable(tree)


# The depfile ---------------------------------------------------------------------


def _depfile_lines(depfile: Path) -> set[str]:
    return {line.removesuffix(" \\").strip() for line in depfile.read_text(encoding="utf-8").splitlines()[1:]}


def test_dependency_paths_include_every_observed_file_and_listing_even_outside_the_product_roots(
    tree: SyntheticTree, cache: Path, tmp_path: Path
) -> None:
    write(tree.repo / "pyproject.toml", "[project]\n")
    item = tree.discovered()[_ONE]
    before = set(tree.verdicts().dependency_paths([item]))
    assert tree.repo / "pyproject.toml" not in before

    _record(tree, tree.observe(_CLI, "pyproject.toml"))

    after = set(tree.verdicts().dependency_paths([item]))
    assert tree.repo / "pyproject.toml" in after
    assert tree.repo in after, "the listing of the directory holding pyproject.toml"
    assert tree.repo / _CLI in after

    depfile = tmp_path / "out" / "stamp.d"
    write_depfile(depfile, target=tmp_path / "stamp", dependencies=sorted(after))
    assert (tree.repo / "pyproject.toml").resolve().as_posix() in _depfile_lines(depfile)


def test_dependency_paths_carry_only_the_record_the_current_key_selects(tree: SyntheticTree, cache: Path) -> None:
    write(tree.repo / "pyproject.toml", "[project]\n")
    _record(tree, tree.observe(_CLI, "pyproject.toml"))

    other_sequence = tree.verdicts().dependency_paths([tree.discovered()[_TWO]])
    other_authority = tree.verdicts("generation-2").dependency_paths([tree.discovered()[_ONE]])

    assert tree.repo / "pyproject.toml" not in other_sequence
    assert tree.repo / "pyproject.toml" not in other_authority


def test_dependency_paths_name_the_directory_of_an_observed_file_that_is_absent(
    tree: SyntheticTree, cache: Path
) -> None:
    write(tree.repo / "config" / "present.toml", "x = 1\n")
    absent = tree.repo / "config" / "absent.toml"
    observation = tree.observe(_CLI)
    observation.files[absent] = "absent"
    _record(tree, observation)

    paths = set(tree.verdicts().dependency_paths([tree.discovered()[_ONE]]))

    assert tree.repo / "config" in paths
    assert absent not in paths


def test_dependency_paths_ignore_a_closure_record(tree: SyntheticTree, cache: Path) -> None:
    write(tree.repo / "pyproject.toml", "[project]\n")
    _record(tree, None)
    paths = set(tree.verdicts().dependency_paths([tree.discovered()[_ONE]]))
    assert tree.repo / "pyproject.toml" not in paths


# The corpus key ------------------------------------------------------------------


def test_the_configuring_environment_names_the_product_and_locale_variables_but_no_tooling_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {"CADRUMO_ANY_SETTING": "1", **{name: f"value-of-{name}" for name in _CONFIGURING}}
    for name, value in expected.items():
        monkeypatch.setenv(name, value)
    for name in (*_TOOLING_ENVIRONMENT, "UNRELATED_SETTING"):
        monkeypatch.setenv(name, "ignored")

    environment = configuring_environment()

    assert set(expected.items()) <= set(environment)
    assert not {name for name, _ in environment} & {*_TOOLING_ENVIRONMENT, "UNRELATED_SETTING"}
    assert list(environment) == sorted(environment)


def test_the_tooling_variables_are_exactly_the_cache_root_the_force_switch_and_the_test_worker_count() -> None:
    assert set(_TOOLING_ENVIRONMENT) == {DEV_CACHE_ROOT_ENV, FORCE_ENV, "CADRUMO_PYTEST_WORKERS"}


@pytest.mark.parametrize("name", ["CADRUMO_ANY_SETTING", *_CONFIGURING])
def test_changing_a_configuring_variable_changes_every_key(
    tree: SyntheticTree, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.delenv(name, raising=False)
    before = tree.verdicts().corpus_key
    keys = tree.keys()
    monkeypatch.setenv(name, "changed")
    assert tree.verdicts().corpus_key != before
    assert all(tree.keys()[sequence] != key for sequence, key in keys.items())


@pytest.mark.parametrize("name", [DEV_CACHE_ROOT_ENV, FORCE_ENV, "CADRUMO_PYTEST_WORKERS"])
def test_changing_a_tooling_variable_changes_no_key(
    tree: SyntheticTree, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
) -> None:
    monkeypatch.delenv(name, raising=False)
    before = tree.verdicts().corpus_key
    keys = tree.keys()
    monkeypatch.setenv(name, str(tmp_path / "cache") if name == DEV_CACHE_ROOT_ENV else "4")
    assert tree.verdicts().corpus_key == before
    assert tree.keys() == keys


def _authority_chain(tree: SyntheticTree) -> None:
    """The compiler imports a registry module that imports a product module and a dev helper."""
    files = {
        "dev/registry/pipeline/authority_publication.py": "from dev.registry.assemble import assemble\n",
        "dev/registry/assemble.py": "from cadrumo.domain.leaf import leaf\nfrom dev.shared_tool import tool\n",
        "dev/shared_tool.py": "tool = 1\n",
        "src/cadrumo/domain/__init__.py": "",
        "src/cadrumo/domain/leaf.py": "leaf = 1\n",
    }
    for relative, text in files.items():
        write(tree.repo / relative, text)


def test_the_authority_compiler_closure_walks_through_the_tooling_and_excludes_it(tree: SyntheticTree) -> None:
    _authority_chain(tree)
    assert authority_compiler_closure(tree.repo) == (
        "dev/__init__.py",
        "dev/shared_tool.py",
        "src/cadrumo/__init__.py",
        "src/cadrumo/domain/__init__.py",
        "src/cadrumo/domain/leaf.py",
    )


def test_the_authority_compiler_closure_of_a_compiler_with_no_imports_outside_the_tooling_is_empty(
    tree: SyntheticTree,
) -> None:
    assert authority_compiler_closure(tree.repo) == ()


@pytest.mark.parametrize("relative", ["src/cadrumo/domain/leaf.py", "dev/shared_tool.py"])
def test_editing_a_module_the_compiler_reaches_through_the_tooling_changes_every_key(
    tree: SyntheticTree, relative: str
) -> None:
    _authority_chain(tree)
    before = tree.keys()
    _edit(tree, relative)
    after = tree.keys()
    assert before.keys() == after.keys()
    assert [name for name in before if before[name] == after[name]] == []


def test_editing_a_product_module_the_compiler_never_reaches_changes_no_key(tree: SyntheticTree) -> None:
    _authority_chain(tree)
    before = tree.keys()
    _edit(tree, _CLI)
    assert tree.keys() == before


# The sequence tree ----------------------------------------------------------------


def test_another_sequences_golden_and_contract_read_in_the_same_process_are_not_recorded(
    tree: SyntheticTree, cache: Path
) -> None:
    """Sequences share one process, so the observer sees every earlier sequence's golden and contract.

    Those files are keyed by their own sequence, so editing them must leave
    this record reusable; its own golden and the shared seeds still end reuse
    through the key.
    """
    other_golden = tree.golden(*_TWO).relative_to(tree.repo).as_posix()
    other_contract = tree.contract(*_TWO).relative_to(tree.repo).as_posix()
    observation = tree.observe(_CLI, other_golden, other_contract, "docs/_sequences/seeds/shared.json")

    product = _product(_record(tree, observation))
    assert product["mode"] == "observed"
    files = product["files"]
    assert isinstance(files, dict)
    assert not [name for name in files if name.startswith("docs/_sequences/")], files
    assert files[_CLI] == _sha((tree.repo / _CLI).read_bytes())

    for relative in (other_golden, other_contract):
        path = tree.repo / relative
        write(path, path.read_text(encoding="utf-8") + "\n")
    assert _reusable(tree), "another sequence's inputs do not shape this one"
    _edit(tree, "docs/_sequences/seeds/shared.json")
    assert not _reusable(tree), "a shared seed is a corpus input"


def test_a_sequences_own_golden_still_ends_reuse_when_it_is_not_recorded(tree: SyntheticTree, cache: Path) -> None:
    own_golden = tree.golden(*_ONE).relative_to(tree.repo).as_posix()
    _record(tree, tree.observe(_CLI, own_golden))
    assert _reusable(tree)
    _edit(tree, own_golden)
    assert not _reusable(tree)
