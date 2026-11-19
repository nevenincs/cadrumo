"""A sequence's verdict is reused only for exactly the inputs it was proven on."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from cadrumo.tests.env_scope import scoped_env_var
from dev.cache_root import DEV_CACHE_ROOT_ENV

from ..errors import SequenceEngineError
from ..verdict_cache import FORCE_ENV, engine_import_closure, write_depfile
from .verdict_tree_support import ALPHA, BETA, PAGE_ONE, SyntheticTree, build_tree, write

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_ONE = (ALPHA, "a-one")
_TWO = (ALPHA, "a-two")
_OTHER_PAGE = (BETA, "b-one")


@pytest.fixture
def tree(tmp_path: Path) -> SyntheticTree:
    return build_tree(tmp_path / "repo")


@pytest.fixture
def cache(tmp_path: Path) -> Iterator[Path]:
    """Scope the verdict records to an empty root and clear the force switch."""
    with scoped_env_var(DEV_CACHE_ROOT_ENV, str(tmp_path / "cache")), scoped_env_var(FORCE_ENV, None):
        yield tmp_path / "cache"


def _unchanged(before: dict[tuple[str, str], str], after: dict[tuple[str, str], str]) -> list[tuple[str, str]]:
    assert before.keys() == after.keys()
    return [name for name in before if before[name] == after[name]]


def _changed(before: dict[tuple[str, str], str], after: dict[tuple[str, str], str]) -> list[tuple[str, str]]:
    assert before.keys() == after.keys()
    return [name for name in before if before[name] != after[name]]


@pytest.mark.parametrize(
    "relative",
    [
        "src/cadrumo/cli.py",
        "src/cadrumo_client/transport.py",
        "src/cadrumo_runtime/host.py",
        "dev/docs/sequences/runner.py",
        "dev/docs/build.py",
        "dev/helper.py",
        "dev/registry/compiler.py",
        "uv.lock",
        "docs/_sequences/seeds/shared.json",
        "docs/_sequences/fixtures/shared.txt",
    ],
)
def test_a_shared_input_changes_the_key_of_every_sequence(tree: SyntheticTree, relative: str) -> None:
    before = tree.keys()
    assert set(before) == {_ONE, _TWO, _OTHER_PAGE}
    path = tree.repo / relative
    write(path, path.read_text(encoding="utf-8") + "# edited\n")
    assert _unchanged(before, tree.keys()) == []


def test_a_new_shared_file_changes_every_key(tree: SyntheticTree) -> None:
    before = tree.keys()
    write(tree.sequences / "seeds" / "added.json", "{}\n")
    assert _unchanged(before, tree.keys()) == []


def test_a_new_authority_identity_changes_every_key(tree: SyntheticTree) -> None:
    first = tree.keys("generation-1")
    assert _unchanged(first, tree.keys("generation-2")) == []
    assert tree.keys("generation-1") == first


def test_keys_are_stable_across_fresh_authorities_and_distinct_per_sequence(tree: SyntheticTree) -> None:
    first, second = tree.keys(), tree.keys()
    assert first == second
    assert len(set(first.values())) == 3


@pytest.mark.parametrize("own", ["contract", "golden"])
@pytest.mark.parametrize("target", [_ONE, _OTHER_PAGE])
def test_one_sequences_own_contract_or_golden_re_keys_only_that_sequence(
    tree: SyntheticTree, own: str, target: tuple[str, str]
) -> None:
    before = tree.keys()
    path = tree.contract(*target) if own == "contract" else tree.golden(*target)
    write(path, path.read_text(encoding="utf-8") + ("@expect exit_code == 0\n" if own == "contract" else "\n"))
    assert _changed(before, tree.keys()) == [target]


def test_a_golden_that_appears_or_vanishes_re_keys_its_sequence_only(tree: SyntheticTree) -> None:
    before = tree.keys()
    tree.golden(*_TWO).unlink()
    missing = tree.keys()
    assert _changed(before, missing) == [_TWO]
    write(tree.golden(*_TWO), "{}\n")
    restored = tree.keys()
    assert restored[_TWO] not in (before[_TWO], missing[_TWO])


def test_a_directive_option_re_keys_only_its_own_sequence(tree: SyntheticTree) -> None:
    before = tree.keys()
    write(tree.docs / f"{ALPHA}.md", PAGE_ONE.replace(":verify: One.", ":verify: One, reworded."))
    assert _changed(before, tree.keys()) == [_ONE]


def test_page_prose_outside_the_directives_changes_no_key(tree: SyntheticTree) -> None:
    before = tree.keys()
    write(tree.docs / f"{ALPHA}.md", PAGE_ONE.replace("Prose.", "Reworded prose, entirely."))
    assert tree.keys() == before


def test_the_catalogue_writers_transient_lock_is_not_a_verdict_input(tree: SyntheticTree) -> None:
    """A locale writer's lock appears and disappears while the gate runs; it must not move a key."""
    before = tree.keys()
    write(tree.repo / "src" / "cadrumo" / "locales" / ".catalogue-write.lock", "pid")
    assert tree.keys() == before


def _engine_importing_helpers(tree: SyntheticTree) -> None:
    """Extend the engine module to reach dev helpers plainly, lazily, relatively and under typing only."""
    files = {
        "dev/docs/sequences/checks.py": (
            "from __future__ import annotations\n"
            "from typing import TYPE_CHECKING\n"
            "from dev.packaging.command_execution import run_command\n"
            "from .runner import frames\n"
            "if TYPE_CHECKING:\n"
            "    from dev.typing_only import Shape\n"
            "def currency() -> None:\n"
            "    from dev.registry.pipeline.publication import generation\n"
            "def spawn() -> None:\n"
            "    from dev.lazy_helper import launch\n"
        ),
        "dev/packaging/__init__.py": "",
        "dev/packaging/command_execution.py": "from dev.paths import REPO_ROOT\n",
        "dev/paths.py": "REPO_ROOT = None\n",
        "dev/lazy_helper.py": "def launch() -> None: ...\n",
        "dev/typing_only.py": "class Shape: ...\n",
        "dev/registry/pipeline/__init__.py": "",
        "dev/registry/pipeline/publication.py": "generation = 1\n",
    }
    for relative, text in files.items():
        write(tree.repo / relative, text)


def test_the_closure_follows_runtime_dev_imports_and_skips_typing_and_registry_tooling(tree: SyntheticTree) -> None:
    _engine_importing_helpers(tree)

    closure = engine_import_closure(tree.repo)

    assert "dev/packaging/command_execution.py" in closure
    assert "dev/paths.py" in closure
    assert "dev/lazy_helper.py" in closure
    assert "dev/packaging/__init__.py" in closure
    assert "dev/typing_only.py" not in closure
    assert not any(path.startswith("dev/registry/") for path in closure)


@pytest.mark.parametrize(
    ("relative", "changes_keys"),
    [
        ("dev/packaging/command_execution.py", True),
        ("dev/paths.py", True),
        ("dev/lazy_helper.py", True),
        ("dev/typing_only.py", False),
        # Authority tooling is keyed as its own tree, not through the import walk.
        ("dev/registry/pipeline/publication.py", True),
    ],
)
def test_a_dev_module_in_the_engine_closure_is_a_verdict_input(
    tree: SyntheticTree, relative: str, changes_keys: bool
) -> None:
    _engine_importing_helpers(tree)
    before = tree.keys()
    path = tree.repo / relative
    write(path, path.read_text(encoding="utf-8") + "# edited\n")
    assert (tree.keys() != before) is changes_keys


def test_a_recorded_clean_verdict_is_reused_with_its_key_prefix(tree: SyntheticTree, cache: Path) -> None:
    verdicts = tree.verdicts()
    item = tree.discovered()[_ONE]
    key = verdicts.key(item)
    assert verdicts.reused(item) is None

    verdicts.record_clean(item, key=key)

    description = tree.verdicts().reused(item)
    assert description is not None
    assert key[:12] in description
    assert tree.verdicts().reused(tree.discovered()[_TWO]) is None, "a sibling must still execute"
    assert tree.verdicts("generation-2").reused(item) is None, "another authority must not reuse it"


def test_force_disables_reuse_but_the_record_stays_servable_afterwards(tree: SyntheticTree, cache: Path) -> None:
    verdicts = tree.verdicts()
    item = tree.discovered()[_ONE]
    verdicts.record_clean(item, key=verdicts.key(item))
    with scoped_env_var(FORCE_ENV, "1"):
        assert tree.verdicts().reused(item) is None
    assert tree.verdicts().reused(item) is not None


def _only_record(cache: Path) -> Path:
    (record,) = cache.rglob("*.json")
    return record


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: {**document, "key": "0" * 64},
        lambda document: {**document, "verdict": "diverged"},
        lambda document: {key: value for key, value in document.items() if key != "verdict"},
        lambda document: [document],
    ],
    ids=["foreign-key", "not-clean", "no-verdict", "not-an-object"],
)
def test_a_record_that_is_not_a_clean_verdict_for_its_own_key_is_not_reused(
    tree: SyntheticTree, cache: Path, mutate: Callable[[dict[str, object]], object]
) -> None:
    verdicts = tree.verdicts()
    item = tree.discovered()[_ONE]
    verdicts.record_clean(item, key=verdicts.key(item))
    record = _only_record(cache)
    document = json.loads(record.read_text(encoding="utf-8"))
    record.write_text(json.dumps(mutate(document)), encoding="utf-8")
    assert tree.verdicts().reused(item) is None


def test_a_corrupt_record_is_a_miss(tree: SyntheticTree, cache: Path) -> None:
    verdicts = tree.verdicts()
    item = tree.discovered()[_ONE]
    verdicts.record_clean(item, key=verdicts.key(item))
    _only_record(cache).write_text("{not json", encoding="utf-8")
    assert tree.verdicts().reused(item) is None


def _recorded_after(tree: SyntheticTree, cache: Path, edit: Callable[[SyntheticTree], object]) -> list[Path]:
    """Take a key, edit an input, attempt to record, and return what reached the cache."""
    verdicts = tree.verdicts()
    item = tree.discovered()[_ONE]
    key = verdicts.key(item)
    edit(tree)
    with pytest.raises(SequenceEngineError, match="inputs changed during execution"):
        verdicts.record_clean(item, key=key)
    return list(cache.rglob("*.json")) if cache.exists() else []


def test_recording_is_refused_when_a_shared_file_is_modified_after_construction(
    tree: SyntheticTree, cache: Path
) -> None:
    assert (
        _recorded_after(
            tree, cache, lambda t: write(t.repo / "src/cadrumo_runtime/host.py", "# changed while the sequence ran\n")
        )
        == []
    )


def test_recording_is_refused_when_a_shared_file_is_added_after_construction(tree: SyntheticTree, cache: Path) -> None:
    assert _recorded_after(tree, cache, lambda t: write(t.repo / "src/cadrumo/added_late.py", "x = 1\n")) == []


def test_recording_is_refused_when_a_shared_file_is_removed_after_construction(
    tree: SyntheticTree, cache: Path
) -> None:
    assert _recorded_after(tree, cache, lambda t: (t.repo / "uv.lock").unlink()) == []


def test_recording_is_refused_when_the_items_golden_changed_after_the_key_was_taken(
    tree: SyntheticTree, cache: Path
) -> None:
    assert _recorded_after(tree, cache, lambda t: write(t.golden(*_ONE), '{"frames": [1]}\n')) == []


def test_a_sibling_golden_changing_during_a_run_does_not_refuse_recording_another_sequence(
    tree: SyntheticTree, cache: Path
) -> None:
    verdicts = tree.verdicts()
    item = tree.discovered()[_ONE]
    key = verdicts.key(item)
    write(tree.golden(*_TWO), '{"frames": ["refreshed concurrently"]}\n')
    verdicts.record_clean(item, key=key)
    assert tree.verdicts().reused(item) is not None


def test_the_depfile_names_the_target_and_escapes_make_metacharacters(tmp_path: Path) -> None:
    target = tmp_path / "out dir" / "stamp$#"
    depfile = tmp_path / "stamp.d"
    first = tmp_path / "a b" / "plain.txt"
    second = tmp_path / "c$d" / "e#f.txt"
    write_depfile(depfile, target=target, dependencies=[first, second])

    text = depfile.read_text(encoding="utf-8")
    lines = text.splitlines()

    assert lines[0].endswith(": \\")
    assert "out\\ dir" in lines[0]
    assert lines[0].count("stamp$$\\#") == 1
    assert "a\\ b" in lines[1]
    assert "c$$d" in lines[2]
    assert "e\\#f" in lines[2]
    assert "\r" not in text


def test_dependency_paths_cover_the_trees_pages_and_each_sequences_own_inputs(tree: SyntheticTree) -> None:
    paths = set(tree.verdicts().dependency_paths(tree.discovered().values()))
    assert tree.repo / "src/cadrumo/cli.py" in paths
    assert tree.repo / "uv.lock" in paths
    assert tree.repo / "src/cadrumo" in paths, "a directory is listed so an added file re-runs the check"
    assert tree.docs / f"{ALPHA}.md" in paths
    assert tree.docs in paths
    assert tree.contract(*_ONE) in paths
    assert tree.golden(*_OTHER_PAGE) in paths
    assert tree.sequences / "seeds" / "shared.json" in paths


def test_dependency_paths_name_the_parent_of_an_absent_golden(tree: SyntheticTree) -> None:
    tree.golden(*_ONE).unlink()
    paths = set(tree.verdicts().dependency_paths(tree.discovered().values()))
    assert tree.golden(*_ONE) not in paths
    assert tree.golden(*_ONE).parent in paths
