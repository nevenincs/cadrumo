"""A CLI-column run starts only with the authority the table run of its own tree published.

The guard reads the table run's meta (tree, logical generation, database digest) and the authority descriptor. The
generation is the authority's identity: a pair of one generation passes whatever the SQLite file bytes are, which are
only recorded; a different generation, another tree, a missing file or an unreadable descriptor is refused with the
reason, and the command exits 2.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..cli_column.authority_guard import (
    DESCRIPTOR,
    AuthorityIdentity,
    AuthorityMismatchError,
    check_authority_matches_tree,
    main,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TREE = "aaaaaaaaaa"
_DIGEST = "d" * 64
_GENERATION = "g" * 64


def _meta(path: Path, *, tree: str = _TREE, digest: str = _DIGEST, generation: str = _GENERATION) -> Path:
    path.write_text(
        json.dumps(
            {"tree": tree, "database_sha256": digest, "logical_generation": generation, "stage_order": "legacy"}
        ),
        encoding="utf-8",
    )
    return path


def _authority(path: Path, *, digest: str = _DIGEST, generation: str = _GENERATION) -> Path:
    path.mkdir()
    (path / DESCRIPTOR).write_text(
        json.dumps({"database_sha256": digest, "logical_generation": generation, "format": "x"}), encoding="utf-8"
    )
    return path


def test_the_authority_published_from_the_tree_is_accepted_and_its_identity_is_the_generation(tmp_path: Path) -> None:
    identity = check_authority_matches_tree(_authority(tmp_path / "a"), _meta(tmp_path / "m.json"), _TREE)

    assert identity == AuthorityIdentity(_GENERATION, _DIGEST, _DIGEST)
    assert identity.same_file


def test_an_authority_of_another_generation_is_refused(tmp_path: Path) -> None:
    authority = _authority(tmp_path / "a", generation="h" * 64)

    with pytest.raises(AuthorityMismatchError, match="logical_generation"):
        check_authority_matches_tree(authority, _meta(tmp_path / "m.json"), _TREE)


def test_the_same_generation_in_different_file_bytes_is_accepted_and_both_hashes_are_recorded(tmp_path: Path) -> None:
    authority = _authority(tmp_path / "a", digest="e" * 64)

    identity = check_authority_matches_tree(authority, _meta(tmp_path / "m.json"), _TREE)

    assert identity == AuthorityIdentity(_GENERATION, "e" * 64, _DIGEST)
    assert not identity.same_file


def test_a_table_run_of_another_tree_is_refused_even_when_the_digests_agree(tmp_path: Path) -> None:
    with pytest.raises(AuthorityMismatchError, match="not on 'bbbbbbbbbb'"):
        check_authority_matches_tree(_authority(tmp_path / "a"), _meta(tmp_path / "m.json"), "bbbbbbbbbb")


def test_a_missing_meta_or_descriptor_or_a_meta_without_a_generation_is_refused(tmp_path: Path) -> None:
    authority = _authority(tmp_path / "a")
    with pytest.raises(AuthorityMismatchError, match="cannot read the table run meta"):
        check_authority_matches_tree(authority, tmp_path / "absent.json", _TREE)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(AuthorityMismatchError, match="cannot read the authority descriptor"):
        check_authority_matches_tree(empty, _meta(tmp_path / "m.json"), _TREE)
    bare = tmp_path / "bare.json"
    bare.write_text(json.dumps({"tree": _TREE}), encoding="utf-8")
    with pytest.raises(AuthorityMismatchError, match="logical_generation"):
        check_authority_matches_tree(authority, bare, _TREE)


def test_the_command_exits_zero_for_a_matching_pair_and_two_with_the_reason_for_a_mismatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    meta = _meta(tmp_path / "m.json")
    good = _authority(tmp_path / "good")
    bad = _authority(tmp_path / "bad", generation="h" * 64)

    assert main(["--authority", str(good), "--meta", str(meta), "--tree", _TREE]) == 0
    assert f"authority generation {_GENERATION}" in capsys.readouterr().out
    assert main(["--authority", str(bad), "--meta", str(meta), "--tree", _TREE]) == 2
    assert "published from another tree" in capsys.readouterr().err
