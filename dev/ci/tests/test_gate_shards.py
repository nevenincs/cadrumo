"""The merge gate's shard partition: complete, disjoint, deterministic and equal to a pytest walk."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from dev.paths import REPO_ROOT

from ..change_scope import ChangeScope
from ..gate_shards import (
    DEFAULT_FILES_PER_SHARD,
    DEFAULT_MAX_SHARDS,
    ShardPlan,
    main,
    parse_shard,
    partition,
    plan_shards,
    selected_test_files,
    shard_count,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TEST_BODY = "def test_probe():\n    assert True\n"


def _tree(root: Path, *relative: str) -> None:
    for name in relative:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_TEST_BODY if path.name.startswith("test_") else "", encoding="utf-8")


def _scope(*targets: str) -> ChangeScope:
    return ChangeScope(targets=targets, ci_contracts=False, sequence_goldens=False, too_broad=False, reason=None)


def test_every_file_lands_in_exactly_one_shard() -> None:
    weights = [(f"pkg/tests/test_{index:03}.py", (index * 37) % 11) for index in range(101)]
    shards = partition(weights, 7)
    dealt = [name for shard in shards for name in shard]
    assert len(shards) == 7
    assert sorted(dealt) == sorted(name for name, _ in weights)
    assert len(set(dealt)) == len(dealt)
    assert all(shard == tuple(sorted(shard)) for shard in shards)


def test_the_partition_depends_on_nothing_but_its_arguments() -> None:
    weights = [(f"test_{index}.py", index % 5) for index in range(40)]
    assert partition(weights, 4) == partition(list(reversed(weights)), 4)


def test_the_partition_balances_weight_rather_than_count() -> None:
    """One heavy file is not stacked with others while a shard sits lighter."""
    weights = [("test_heavy.py", 90), *[(f"test_light_{index}.py", 10) for index in range(9)]]
    shards = partition(weights, 2)
    assert shards[0] == ("test_heavy.py",)
    assert len(shards[1]) == 9


def test_the_partition_refuses_a_file_named_twice_and_a_shard_count_of_zero() -> None:
    with pytest.raises(ValueError, match="one shard only"):
        partition([("test_a.py", 1), ("test_a.py", 2)], 2)
    with pytest.raises(ValueError, match="at least one shard"):
        partition([("test_a.py", 1)], 0)


@pytest.mark.parametrize(
    ("files", "expected"),
    [(1, 1), (900, 1), (901, 2), (1800, 2), (7200, 8), (100_000, 8)],
)
def test_the_shard_count_grows_with_the_selection_up_to_its_ceiling(files: int, expected: int) -> None:
    assert shard_count(files, files_per_shard=900, max_shards=8) == expected


def test_an_empty_selection_is_refused_rather_than_planned_as_a_green_matrix() -> None:
    with pytest.raises(ValueError, match="nothing to shard"):
        shard_count(0, files_per_shard=900, max_shards=8)
    with pytest.raises(ValueError, match="must be positive"):
        shard_count(10, files_per_shard=0, max_shards=8)


@pytest.mark.parametrize(
    "text", ["", "1", "0/3", "4/3", "1/0", "a/b", "1/3/5", "-1/3", " 1/3", f"{chr(0x661)}/{chr(0x663)}"]
)
def test_a_malformed_shard_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match=r"shard"):
        parse_shard(text)


def test_a_shard_is_read_one_based() -> None:
    assert parse_shard("1/1") == (1, 1)
    assert parse_shard("8/8") == (8, 8)


def test_selection_keeps_test_modules_below_the_targets_and_drops_the_held_out(tmp_path: Path) -> None:
    _tree(
        tmp_path,
        "pkg/tests/test_kept.py",
        "pkg/tests/test_held.py",
        "pkg/tests/helper.py",
        "pkg/tests/conftest.py",
        "pkg/build/test_generated.py",
        "pkg/.hidden/test_hidden.py",
        "pkg/node_modules/dep/test_vendored.py",
        "other/tests/test_unselected.py",
        "single/test_named.py",
    )
    files = selected_test_files(["pkg", "single/test_named.py"], root=tmp_path, excluded=["pkg/tests/test_held.py"])
    assert files == ("pkg/tests/test_kept.py", "single/test_named.py")


def test_a_target_inside_an_unwalked_directory_is_still_walked_from_there(tmp_path: Path) -> None:
    """Only what lies below a target is judged, as pytest judges a directory it was pointed at."""
    _tree(tmp_path, "build/tools/tests/test_inside.py")
    assert selected_test_files(["build/tools"], root=tmp_path) == ("build/tools/tests/test_inside.py",)


def test_a_missing_target_is_refused_rather_than_read_as_empty(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        selected_test_files(["absent"], root=tmp_path)


def test_the_plan_names_every_shard_once(tmp_path: Path) -> None:
    _tree(tmp_path, *(f"pkg/tests/test_{index}.py" for index in range(5)))
    plan = plan_shards(_scope("pkg"), root=tmp_path, files_per_shard=2, max_shards=8)
    assert plan == ShardPlan(
        shards=("1/3", "2/3", "3/3"),
        files=5,
        ci_contracts=False,
        sequence_goldens=False,
        too_broad=False,
        reason=None,
    )
    assert plan.github_outputs() == (
        'shards=["1/3","2/3","3/3"]',
        "files=5",
        "ci-contracts=false",
        "sequence-goldens=false",
    )


def test_selection_equals_what_a_pytest_walk_collects(tmp_path: Path) -> None:
    """The shards name files explicitly, so they must name exactly what the directory walk finds."""
    _tree(
        tmp_path,
        "pkg/tests/test_one.py",
        "pkg/tests/nested/test_two.py",
        "pkg/build/test_generated.py",
        "pkg/dist/test_packed.py",
        "pkg/.cache/test_hidden.py",
        "pkg/venv/test_environment.py",
        "pkg/tests/check_not_a_test.py",
    )
    (tmp_path / "pytest.ini").write_text("[pytest]\npython_files = test_*.py\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "-c", "pytest.ini", "pkg"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    collected = sorted({line.split("::")[0] for line in result.stdout.splitlines() if "::" in line})
    assert collected == ["pkg/tests/nested/test_two.py", "pkg/tests/test_one.py"]
    assert list(selected_test_files(["pkg"], root=tmp_path)) == collected


def test_the_planned_shards_together_select_the_whole_full_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """On the real tree: the plan's shards, each written by the CLI, cover every file once."""
    assert main(["plan", "--max-shards", "3", "--files-per-shard", "1"]) == 0
    planned = json.loads(capsys.readouterr().out)
    assert planned["shards"] == ["1/3", "2/3", "3/3"]
    written: list[str] = []
    for shard in planned["shards"]:
        output = tmp_path / f"{shard.replace('/', '-')}.txt"
        assert main(["select", "--shard", shard, "--output", str(output)]) == 0
        written.extend(output.read_text(encoding="utf-8").splitlines())
    assert len(written) == planned["files"] == len(set(written))
    assert planned["files"] > 1000, "the full gate selects the repository's test population"
    assert all((REPO_ROOT / name).is_file() and Path(name).name.startswith("test_") for name in written)
    assert "dev/ci/tests/test_gate_shards.py" in written


def test_the_default_matrix_holds_the_full_tree_without_growing_a_shard(capsys: pytest.CaptureFixture[str]) -> None:
    """On the real tree: the cap on the matrix never stretches a shard past its file budget.

    A cap the tree has outgrown deals every shard more files than its budget,
    silently, so each runs longer than the plan was sized for.
    """
    assert main(["plan"]) == 0
    planned = json.loads(capsys.readouterr().out)
    count = len(planned["shards"])
    assert count < DEFAULT_MAX_SHARDS or planned["files"] <= DEFAULT_MAX_SHARDS * DEFAULT_FILES_PER_SHARD, (
        f"{planned['files']} test files over at most {DEFAULT_MAX_SHARDS} shards exceeds "
        f"{DEFAULT_FILES_PER_SHARD} files per shard: raise the cap, do not grow the shards"
    )
    assert -(-planned["files"] // count) <= DEFAULT_FILES_PER_SHARD


def test_the_cli_refuses_a_shard_outside_its_count(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as refused:
        main(["select", "--shard", "4/3", "--output", str(tmp_path / "shard.txt")])
    assert refused.value.code == 2
    assert not (tmp_path / "shard.txt").exists()
