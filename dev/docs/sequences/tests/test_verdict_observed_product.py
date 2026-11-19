"""A recorded verdict is reused only while the product it observed (or, failing that, all of it) is unchanged.

The product source is no part of a verdict key. A record carries either the
checkout files and listings the sequence's processes read, each with the digest
first seen, or the digest of the whole product source when observation was
unavailable or incomplete. These cases record through the real
``SequenceVerdicts`` over a synthetic repository and re-open it as a later
process would.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from cadrumo.tests.env_scope import scoped_env_var
from dev.cache_root import DEV_CACHE_ROOT_ENV, dev_cache_dir

from ..dependency_observation import Observation
from ..errors import SequenceEngineError
from ..verdict_cache import _CACHE_NAME, FORCE_ENV, OBSERVATION_SENTINEL, SequenceVerdicts
from .verdict_tree_support import SyntheticTree, build_tree, write

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_ONE = ("how-to/alpha", "a-one")
_CLI = "src/cadrumo/cli.py"
_CLIENT = "src/cadrumo_client/transport.py"
_RUNTIME = "src/cadrumo_runtime/host.py"


@pytest.fixture
def tree(tmp_path: Path) -> SyntheticTree:
    return build_tree(tmp_path / "repo")


@pytest.fixture
def cache(tmp_path: Path) -> Iterator[Path]:
    with scoped_env_var(DEV_CACHE_ROOT_ENV, str(tmp_path / "cache")), scoped_env_var(FORCE_ENV, None):
        yield tmp_path / "cache"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _on_disk(tree: SyntheticTree, relative: str) -> str:
    """The digest of the bytes now on disk (the synthetic writer's newline translation included)."""
    return hashlib.sha256((tree.repo / relative).read_bytes()).hexdigest()


def _record(tree: SyntheticTree, observation: Observation | None) -> dict[str, object]:
    verdicts = tree.verdicts()
    item = tree.discovered()[_ONE]
    verdicts.record_clean(item, key=verdicts.key(item), observation=observation)
    return _recorded(tree)


def _recorded(tree: SyntheticTree) -> dict[str, object]:
    (record,) = _cache_files(tree)
    document = json.loads(record.read_text(encoding="utf-8"))
    product = document["product"]
    assert isinstance(product, dict)
    return {str(name): value for name, value in product.items()}


def _cache_files(tree: SyntheticTree) -> list[Path]:
    directory = dev_cache_dir(_CACHE_NAME)
    return sorted(directory.glob("*.json")) if directory.exists() else []


def _reusable(tree: SyntheticTree) -> bool:
    return tree.verdicts().reused(tree.discovered()[_ONE]) is not None


def _append(tree: SyntheticTree, relative: str) -> None:
    path = tree.repo / relative
    write(path, path.read_text(encoding="utf-8") + "# edited\n")


def test_a_complete_observation_records_observed_mode_with_first_seen_digests_and_listings(
    tree: SyntheticTree, cache: Path
) -> None:
    product = _record(tree, tree.observe(_CLI, _CLIENT))
    assert product["mode"] == "observed"
    assert product["files"] == {
        OBSERVATION_SENTINEL: _on_disk(tree, OBSERVATION_SENTINEL),
        _CLI: _on_disk(tree, _CLI),
        _CLIENT: _on_disk(tree, _CLIENT),
    }
    assert product["listings"] == {
        "src/cadrumo": hashlib.sha256(b"__init__.py\ncli.py").hexdigest(),
        "src/cadrumo_client": hashlib.sha256(b"transport.py").hexdigest(),
    }


def test_an_incomplete_observation_records_the_whole_product_source_instead(tree: SyntheticTree, cache: Path) -> None:
    observation = tree.observe(_CLI)
    observation.note_incomplete("listing by file descriptor")
    product = _record(tree, observation)
    assert product["mode"] == "closure"
    assert set(product) == {"mode", "digest"}
    assert isinstance(product["digest"], str) and len(product["digest"]) == 64


def test_no_observation_records_the_whole_product_source(tree: SyntheticTree, cache: Path) -> None:
    assert _record(tree, None)["mode"] == "closure"


def test_a_closure_digest_follows_the_product_source(tree: SyntheticTree, cache: Path) -> None:
    before = _record(tree, None)["digest"]
    for record in _cache_files(tree):
        record.unlink()
    _append(tree, _CLI)
    assert _record(tree, None)["digest"] != before


def test_an_observed_record_is_reused_and_says_how_many_files_still_match(tree: SyntheticTree, cache: Path) -> None:
    _record(tree, tree.observe(_CLI, _CLIENT))
    description = tree.verdicts().reused(tree.discovered()[_ONE])
    assert description is not None
    assert "3 observed product files unchanged" in description


@pytest.mark.parametrize("unrelated", [_RUNTIME, "src/cadrumo_runtime/new_leaf.py"])
def test_an_edit_to_a_product_file_outside_the_observed_set_does_not_invalidate_reuse(
    tree: SyntheticTree, cache: Path, unrelated: str
) -> None:
    _record(tree, tree.observe(_CLI))
    key = tree.verdicts().key(tree.discovered()[_ONE])
    write(tree.repo / unrelated, "# an unrelated leaf, edited\n")
    assert tree.verdicts().key(tree.discovered()[_ONE]) == key
    assert _reusable(tree)


def test_an_edit_to_an_observed_file_invalidates_reuse(tree: SyntheticTree, cache: Path) -> None:
    _record(tree, tree.observe(_CLI, _CLIENT))
    _append(tree, _CLI)
    assert not _reusable(tree)


def test_a_file_added_to_an_observed_directory_invalidates_reuse(tree: SyntheticTree, cache: Path) -> None:
    _record(tree, tree.observe(_CLI))
    write(tree.repo / "src/cadrumo/added_module.py", "x = 1\n")
    assert not _reusable(tree)


def test_a_file_removed_from_an_observed_directory_invalidates_reuse(tree: SyntheticTree, cache: Path) -> None:
    write(tree.repo / "src/cadrumo/extra.py", "y = 2\n")
    _record(tree, tree.observe(_CLI))
    (tree.repo / "src/cadrumo/extra.py").unlink()
    assert not _reusable(tree)


def test_a_deleted_observed_file_invalidates_reuse(tree: SyntheticTree, cache: Path) -> None:
    _record(tree, tree.observe(_CLI, _CLIENT))
    (tree.repo / _CLIENT).unlink()
    assert not _reusable(tree)


def test_a_bytecode_cache_appearing_beside_an_observed_file_does_not_invalidate_reuse(
    tree: SyntheticTree, cache: Path
) -> None:
    _record(tree, tree.observe(_CLI))
    write(tree.repo / "src/cadrumo/__pycache__/cli.cpython-313.pyc", "compiled")
    assert _reusable(tree)


@pytest.mark.parametrize("relative", [_CLI, _CLIENT, _RUNTIME])
def test_a_record_without_a_complete_observation_is_invalidated_by_any_product_edit(
    tree: SyntheticTree, cache: Path, relative: str
) -> None:
    incomplete = tree.observe(_CLI)
    incomplete.note_incomplete("module imported before the hook changed after start")
    _record(tree, incomplete)
    assert _reusable(tree)
    _append(tree, relative)
    assert not _reusable(tree)


def test_a_record_without_any_observation_is_invalidated_by_a_product_file_being_added(
    tree: SyntheticTree, cache: Path
) -> None:
    _record(tree, None)
    write(tree.repo / "src/cadrumo_runtime/added.py", "z = 3\n")
    assert not _reusable(tree)


def test_an_observed_file_edited_after_it_was_first_seen_records_a_verdict_the_edited_tree_does_not_reuse(
    tree: SyntheticTree, cache: Path
) -> None:
    observation = tree.observe(_CLI)
    first_seen = _on_disk(tree, _CLI)
    _append(tree, _CLI)
    assert _on_disk(tree, _CLI) != first_seen
    product = _record(tree, observation)
    assert product["files"] == {
        OBSERVATION_SENTINEL: _on_disk(tree, OBSERVATION_SENTINEL),
        _CLI: first_seen,
    }, "the digest read, not the digest on disk now"
    assert not _reusable(tree)


def test_the_content_first_seen_remains_reusable_when_the_file_returns_to_it(tree: SyntheticTree, cache: Path) -> None:
    _record(tree, tree.observe(_CLI))
    original = (tree.repo / _CLI).read_text(encoding="utf-8")
    _append(tree, _CLI)
    assert not _reusable(tree)
    write(tree.repo / _CLI, original)
    assert _reusable(tree)


def test_an_incomplete_observation_started_before_a_product_edit_refuses_the_record(
    tree: SyntheticTree, cache: Path
) -> None:
    """The whole-source digest is taken after the run, so a file touched since the process started is refused."""
    verdicts = tree.verdicts()
    item = tree.discovered()[_ONE]
    key = verdicts.key(item)
    observation = tree.observe(_CLI)
    observation.note_incomplete("opaque read")
    time.sleep(0.05)
    _append(tree, _RUNTIME)
    with pytest.raises(SequenceEngineError, match="inputs changed during execution"):
        verdicts.record_clean(item, key=key, observation=observation)
    assert _cache_files(tree) == []


def test_preparing_the_closure_before_execution_refuses_a_record_when_the_product_changes_during_it(
    tree: SyntheticTree, cache: Path
) -> None:
    verdicts = tree.verdicts()
    item = tree.discovered()[_ONE]
    key = verdicts.key(item)
    verdicts.prepare_unobserved_run()
    time.sleep(0.05)
    _append(tree, _CLI)
    with pytest.raises(SequenceEngineError, match="inputs changed during execution"):
        verdicts.record_clean(item, key=key)
    assert _cache_files(tree) == []


def test_an_observed_record_does_not_refuse_when_unobserved_product_changes_during_the_run(
    tree: SyntheticTree, cache: Path
) -> None:
    """Only what the sequence read matters: a product edit it never read cannot invalidate the record."""
    verdicts = tree.verdicts()
    item = tree.discovered()[_ONE]
    key = verdicts.key(item)
    observation = tree.observe(_CLI)
    _append(tree, _RUNTIME)
    verdicts.record_clean(item, key=key, observation=observation)
    assert _reusable(tree)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: {key: value for key, value in document.items() if key != "product"},
        lambda document: {**document, "product": "observed"},
        lambda document: {**document, "product": {"mode": "guess", "files": {}, "listings": {}}},
        lambda document: {**document, "product": {"mode": "observed", "files": [], "listings": {}}},
        lambda document: {**document, "product": {"mode": "observed", "files": {}}},
        lambda document: {**document, "product": {"mode": "closure", "digest": "0" * 64}},
        lambda document: {**document, "product": {"mode": "observed", "files": {_CLI: "0" * 64}, "listings": {}}},
    ],
    ids=[
        "no-product",
        "not-an-object",
        "unknown-mode",
        "files-not-an-object",
        "listings-missing",
        "foreign-closure-digest",
        "wrong-file-digest",
    ],
)
def test_a_record_whose_product_part_is_missing_malformed_or_foreign_is_not_reused(
    tree: SyntheticTree, cache: Path, mutate: Callable[[dict[str, object]], object]
) -> None:
    _record(tree, tree.observe(_CLI))
    (record,) = _cache_files(tree)
    document = json.loads(record.read_text(encoding="utf-8"))
    record.write_text(json.dumps(mutate(document)), encoding="utf-8")
    assert not _reusable(tree)


def test_an_observed_set_is_reusable_until_a_listing_it_holds_changes(tree: SyntheticTree, cache: Path) -> None:
    product = _record(tree, tree.observe())
    assert product["files"] == {OBSERVATION_SENTINEL: _on_disk(tree, OBSERVATION_SENTINEL)}
    assert _reusable(tree)
    write(tree.repo / "src/cadrumo/appeared.py", "")
    assert not _reusable(tree)


def test_recording_drops_paths_under_the_cache_and_the_authority_directory(tmp_path: Path) -> None:
    tree = build_tree(tmp_path / "repo")
    cache_root = tree.repo / "var" / "devcache"
    authority = tree.repo / "var" / "authority" / "descriptor.json"
    outside = tmp_path / "outside.txt"
    write(authority, "{}\n")
    write(cache_root / "something.bin", "cached")
    write(outside, "outside")
    with scoped_env_var(DEV_CACHE_ROOT_ENV, str(cache_root)), scoped_env_var(FORCE_ENV, None):
        verdicts = SequenceVerdicts(
            docs_root=tree.docs,
            goldens_root=tree.sequences,
            authority_identity="generation-1",
            repo_root=tree.repo,
            authority_files=(authority,),
        )
        item = tree.discovered()[_ONE]
        observation = tree.observe(_CLI, "var/devcache/something.bin", "var/authority/descriptor.json")
        assert outside.is_file()

        verdicts.record_clean(item, key=verdicts.key(item), observation=observation)

        records = list(cache_root.rglob("*.json"))
        assert len(records) == 1
        product = json.loads(records[0].read_text(encoding="utf-8"))["product"]
    assert product["mode"] == "observed"
    assert product["files"] == {
        OBSERVATION_SENTINEL: _on_disk(tree, OBSERVATION_SENTINEL),
        _CLI: _on_disk(tree, _CLI),
    }
    assert product["listings"] == {"src/cadrumo": _sha("__init__.py\ncli.py")}
