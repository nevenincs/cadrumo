"""A family that reads locale sentences is keyed on the keys it looked up, not on the shards that hold them.

Each case builds an isolated checkout under ``tmp_path`` holding the product's
own catalogue modules, copied unchanged, and a locale catalogue of its own. A
real producer, run observed by ``seed``, looks up one key of the shared
``common.yml`` shard. An edit to another sentence of that shard leaves the
family fresh, an edit to the sentence it read makes it stale naming that key,
and a second family over the same catalogue is judged by its own keys. An input
that changes while the seed runs is reported as drift and the window index is
still written from the consistent snapshot.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from ...paths import REPO_ROOT
from ..cli import WINDOW_DRIFT, Workspace, record_window_index, seed
from ..location import WINDOW_INDEX, WINDOW_ROOT, window_projections
from ..registry import PYTHON, Command, FixtureFamily, InputGroup
from ..stamps import OBSERVED_MODE, FixtureState, InputDigests, family_inputs, family_status, observed_files, stamp_path

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_AUTHORITY = {"database_sha256": "a" * 64, "logical_generation": "b" * 64}

#: The product modules the catalogue is, copied unchanged into the isolated checkout.
_CATALOGUE_MODULES = (
    "cadrumo/core/i18n/lazy_catalogue.py",
    "cadrumo/core/i18n/routing.py",
    "cadrumo/core/type_guards.py",
)

#: Looks up the keys it is given in the English catalogue and writes what it found to ``<output>/<family>.json``.
_PRODUCER = """\
import json, sys
from pathlib import Path

from cadrumo.core.i18n.lazy_catalogue import LazyLocaleCatalogue

output, name, *keys = sys.argv[1:]
catalogue = LazyLocaleCatalogue("en", shard_dir=Path("src/cadrumo/locales/en"))
found = {key: catalogue.get(key) for key in keys}
Path(output, f"{name}.json").write_text(json.dumps(found), encoding="utf-8")
with Path("writes.log").open("a", encoding="utf-8") as log:
    log.write(name + "\\n")
"""

_COMMON = "screen:\n  title: Ledger\n  hint: Pick a row\nother:\n  word: Kept\n"


def _family(name: str, *keys: str, output_root: str = "out") -> FixtureFamily:
    script = (PYTHON, "tools/produce.py", output_root, name, *keys)
    return FixtureFamily(
        name=name,
        summary="A sample projection.",
        inputs=(
            InputGroup("producer", ("tools/produce.py",)),
            InputGroup("product", ("src",), observed=True),
        ),
        check=(Command(script),),
        producer=Command(script),
        output_root=output_root,
        outputs=(f"{name}.json",),
        committed=False,
    )


def _checkout(root: Path) -> Path:
    (root / "tools").mkdir(parents=True)
    (root / "tools" / "produce.py").write_text(_PRODUCER, encoding="utf-8")
    for member in _CATALOGUE_MODULES:
        target = root / "src" / member
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / "src" / member, target)
    for package in ("cadrumo", "cadrumo/core", "cadrumo/core/i18n"):
        (root / "src" / package / "__init__.py").write_text("", encoding="utf-8")
    # The catalogue reads one constant from this module, whose product original imports the whole core.
    (root / "src" / "cadrumo" / "core" / "external_constants.py").write_text(
        'UTF_8_ENCODING = "utf-8"\n', encoding="utf-8"
    )
    (root / "src" / "cadrumo" / "locales" / "en").mkdir(parents=True)
    _edit(root, _COMMON)
    (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    (root / "out").mkdir()
    (root / "authority.json").write_text("{}", encoding="utf-8")
    return root


def _edit(root: Path, text: str) -> None:
    (root / "src" / "cadrumo" / "locales" / "en" / "common.yml").write_text(text, encoding="utf-8")


def _workspace(root: Path, *families: FixtureFamily) -> Workspace:
    return Workspace(
        root=root,
        families=families,
        authority=lambda: _AUTHORITY,
        authority_source=lambda: root / "authority.json",
        persona_check=lambda: (),
        cache_directory=root.parent / "cache",
        scratch_root=root.parent / "scratch",
    )


def _status(workspace: Workspace, family: FixtureFamily):
    digests = InputDigests(workspace.root)
    inputs = family_inputs(family, digests, workspace.authority())
    return family_status(family, workspace.root, inputs, digests=digests, cache_directory=workspace.cache_directory)


def _stamp(workspace: Workspace, family: FixtureFamily) -> dict[str, Any]:
    path = stamp_path(family, workspace.root, cache_directory=workspace.cache_directory)
    return json.loads(path.read_text(encoding="utf-8"))


def _writes(root: Path) -> list[str]:
    log = root / "writes.log"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_a_family_is_keyed_on_the_catalogue_keys_it_read_not_on_the_shard(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    family = _family("titles", "screen.title")
    workspace = _workspace(root, family)
    assert seed([], force=False, workspace=workspace) == 0

    observation = _stamp(workspace, family)["observation"]
    assert observation["mode"] == OBSERVED_MODE
    assert [identity.split("\x1f") for identity in observation["keys"]] == [["src/cadrumo/locales/en", "screen.title"]]
    assert "src/cadrumo/locales/en/common.yml" not in observation["files"]
    shard = root / "src" / "cadrumo" / "locales" / "en" / "common.yml"
    assert shard in observed_files(family, root, cache_directory=workspace.cache_directory)

    _edit(root, _COMMON.replace("Pick a row", "Choose a row").replace("Kept", "Changed"))
    unrelated = _status(workspace, family)
    assert unrelated.state is FixtureState.FRESH, unrelated.reasons
    assert seed([], force=False, workspace=workspace) == 0
    assert _writes(root) == ["titles"]

    _edit(root, _COMMON.replace("title: Ledger", "title: Book"))
    result = _status(workspace, family)
    assert result.state is FixtureState.STALE
    assert result.reasons == ("observed: screen.title in src/cadrumo/locales/en changed",)


def test_a_key_moved_out_of_the_shard_or_removed_makes_the_family_stale(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    family = _family("titles", "screen.title")
    workspace = _workspace(root, family)
    assert seed([], force=False, workspace=workspace) == 0

    _edit(root, "screen:\n  hint: Pick a row\n")
    assert _status(workspace, family).reasons == ("observed: screen.title in src/cadrumo/locales/en changed",)


def test_a_sentence_change_makes_only_the_family_that_read_it_stale(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    titles, words = _family("titles", "screen.title"), _family("words", "other.word")
    workspace = _workspace(root, titles, words)
    assert seed([], force=False, workspace=workspace) == 0

    _edit(root, _COMMON.replace("Kept", "Changed"))
    unrelated = _status(workspace, titles)
    assert unrelated.state is FixtureState.FRESH, unrelated.reasons
    assert _status(workspace, words).state is FixtureState.STALE
    assert seed([], force=False, workspace=workspace) == 0
    assert _writes(root) == ["titles", "words", "words"]


def test_an_input_changed_during_the_seed_is_reported_as_drift_and_the_index_still_stands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _checkout(tmp_path / "repo")
    monkeypatch.setenv("CADRUMO_CMAKE_BINARY_DIR", str(root / "build" / "test"))
    family = _family("titles", "screen.title", output_root=WINDOW_ROOT)
    workspace = _workspace(root, family)
    window_projections(root).mkdir(parents=True)
    assert seed([], force=False, window=True, workspace=workspace) == 0
    index = window_projections(root) / WINDOW_INDEX
    assert index.is_file()

    # The family was produced from the stamped sentence; the checkout then moved on before the index was judged.
    _edit(root, _COMMON.replace("title: Ledger", "title: Book"))
    recorded = record_window_index(workspace, _AUTHORITY)
    assert recorded.path == index
    assert recorded.drift == ("titles: observed: screen.title in src/cadrumo/locales/en changed",)

    # A stamp that no longer records the outputs is no snapshot: the index is removed, naming why.
    (index.parent / "titles.json").write_text("{}", encoding="utf-8")
    assert record_window_index(workspace, _AUTHORITY).path is None
    assert not index.exists()
    assert not (index.parent / WINDOW_DRIFT).exists()


def test_a_producer_that_fails_removes_the_window_index_though_its_outputs_still_match_its_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _checkout(tmp_path / "repo")
    monkeypatch.setenv("CADRUMO_CMAKE_BINARY_DIR", str(root / "build" / "test"))
    family = _family("titles", "screen.title", output_root=WINDOW_ROOT)
    workspace = _workspace(root, family)
    window_projections(root).mkdir(parents=True)
    assert seed([], force=False, window=True, workspace=workspace) == 0
    index = window_projections(root) / WINDOW_INDEX
    (index.parent / WINDOW_DRIFT).write_text("titles: an earlier seed's drift\n", encoding="utf-8")

    # The producer changes and now fails before writing, so the earlier stamp still records the outputs.
    (root / "tools" / "produce.py").write_text("raise SystemExit(3)\n", encoding="utf-8")
    assert seed([], force=False, window=True, workspace=workspace) == 1
    assert not index.exists()
    assert not (index.parent / WINDOW_DRIFT).exists()
