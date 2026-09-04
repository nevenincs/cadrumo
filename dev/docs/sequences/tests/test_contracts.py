"""Tests for the private sequence-contract reader and its docname guard.

`dev.quality.module_test_reach` listed `dev/docs/sequences/contracts.py` as
unreached. It turns a page docname and a sequence id into a path it then reads,
and the guard standing between those inputs and the filesystem had nothing
proving it holds.

It did not. The docname was split on ``/`` alone, so on Windows a backslash kept
the whole name in ONE segment and the ``..`` check never saw it, while a UNC
segment made ``joinpath`` discard the contracts root entirely and resolve
outside the tree. Both were measured against the real function before the guard
was changed.

The path cases assert on the resolved path rather than on the refusal message,
because what matters is where the read would land.
"""

from __future__ import annotations

import pathlib

import pytest

from ..contracts import read_sequence_contract, sequence_contract_path
from ..errors import SequenceEngineError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _contracts_root(docs_root: pathlib.Path) -> pathlib.Path:
    return docs_root / "_sequences" / "contracts"


def test_a_page_keyed_contract_lands_under_the_contracts_root(tmp_path: pathlib.Path) -> None:
    """The ordinary case, and the layout every authored contract relies on."""
    resolved = sequence_contract_path("guide/install", "first-run", docs_root=tmp_path)

    assert resolved == _contracts_root(tmp_path) / "guide" / "install" / "first-run.seq"


def test_an_explicit_contracts_root_wins_over_the_docs_root(tmp_path: pathlib.Path) -> None:
    """The override exists so a caller can key contracts outside the docs tree."""
    elsewhere = tmp_path / "elsewhere"

    resolved = sequence_contract_path("guide", "seq", docs_root=tmp_path, contracts_root=elsewhere)

    assert resolved == elsewhere / "guide" / "seq.seq"


@pytest.mark.parametrize(
    "page",
    [
        "../etc",
        "a/../..",
        "",
        ".",
        "guide/./install",
    ],
)
def test_a_traversing_posix_docname_is_refused(page: str, tmp_path: pathlib.Path) -> None:
    """A docname is a page key, not a path expression."""
    with pytest.raises(SequenceEngineError):
        sequence_contract_path(page, "seq", docs_root=tmp_path)


def test_a_backslash_docname_is_refused(tmp_path: pathlib.Path) -> None:
    """The hole: splitting on ``/`` left ``..`` inside a single segment unexamined.

    On Windows the join then honoured those separators, so the guard passed a
    docname whose read walked back out of the contracts root.
    """
    page = "a" + chr(92) + ".." + chr(92) + ".." + chr(92) + ".."

    with pytest.raises(SequenceEngineError):
        sequence_contract_path(page, "seq", docs_root=tmp_path)


def test_a_unc_docname_is_refused(tmp_path: pathlib.Path) -> None:
    """The sharper hole: an absolute segment makes ``joinpath`` discard the root.

    Measured before the fix, this returned a path on another host entirely,
    with the contracts root nowhere in it.
    """
    page = chr(92) * 2 + "server" + chr(92) + "share"

    with pytest.raises(SequenceEngineError):
        sequence_contract_path(page, "seq", docs_root=tmp_path)


def test_a_drive_qualified_docname_is_refused(tmp_path: pathlib.Path) -> None:
    """A drive letter is not a page key, and silently dropping it invents a page."""
    with pytest.raises(SequenceEngineError):
        sequence_contract_path("C:/absolute", "seq", docs_root=tmp_path)


@pytest.mark.parametrize("sequence_id", ["../escape", "Upper", "with space", "", "-leading"])
def test_an_invalid_sequence_id_is_refused(sequence_id: str, tmp_path: pathlib.Path) -> None:
    """The id names a file, so it is the other half of the same guard."""
    with pytest.raises(SequenceEngineError):
        sequence_contract_path("guide", sequence_id, docs_root=tmp_path)


def _write(docs_root: pathlib.Path, page: str, sequence_id: str, text: str) -> None:
    target = sequence_contract_path(page, sequence_id, docs_root=docs_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_options_are_split_from_the_frame_grammar(tmp_path: pathlib.Path) -> None:
    """The contract's whole job: private settings above, frame lines below."""
    _write(
        tmp_path,
        "guide",
        "first-run",
        chr(10).join((":seed: 42", ":shells: bash", "run aeat config profile status", "expect exit 0")) + chr(10),
    )

    options, body = read_sequence_contract("guide", "first-run", docs_root=tmp_path)

    assert options == {"seed": "42", "shells": "bash"}
    assert body == chr(10).join(("run aeat config profile status", "expect exit 0"))


def test_a_contract_with_no_options_still_yields_its_frames(tmp_path: pathlib.Path) -> None:
    """Options are optional; frames are not."""
    _write(tmp_path, "guide", "plain", "run aeat --version" + chr(10))

    options, body = read_sequence_contract("guide", "plain", docs_root=tmp_path)

    assert options == {}
    assert body == "run aeat --version"


def test_an_unsupported_option_is_refused(tmp_path: pathlib.Path) -> None:
    """Only seed and shells belong here; the reader-facing promise lives in the page.

    Accepting an unknown key would let a verification sentence be authored where
    no editor reviews it, which is the separation this module exists to keep.
    """
    _write(tmp_path, "guide", "sneaky", ":verify: it worked" + chr(10) + "run aeat --version" + chr(10))

    with pytest.raises(SequenceEngineError, match="verify"):
        read_sequence_contract("guide", "sneaky", docs_root=tmp_path)


def test_a_repeated_option_is_refused(tmp_path: pathlib.Path) -> None:
    """Two values for one key means one of them is silently ignored."""
    _write(tmp_path, "guide", "twice", chr(10).join((":seed: 1", ":seed: 2", "run aeat --version")) + chr(10))

    with pytest.raises(SequenceEngineError, match="repeats"):
        read_sequence_contract("guide", "twice", docs_root=tmp_path)


def test_a_contract_with_no_frames_is_refused(tmp_path: pathlib.Path) -> None:
    """Options alone execute nothing, and would pass as a verified sequence."""
    _write(tmp_path, "guide", "empty", ":seed: 1" + chr(10))

    with pytest.raises(SequenceEngineError, match="no frame grammar"):
        read_sequence_contract("guide", "empty", docs_root=tmp_path)


def test_a_missing_contract_names_the_page_and_the_path(tmp_path: pathlib.Path) -> None:
    """An author who mistyped a key needs both halves to find the file."""
    with pytest.raises(SequenceEngineError, match="missing private sequence contract"):
        read_sequence_contract("guide", "absent", docs_root=tmp_path)
