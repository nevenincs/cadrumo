"""Detector-teeth tests for the ``none``-root cause ruling.

The ruling maps a cause onto each root the corpus declares. Both directions of
disagreement are refusals, and each is planted into a temporary registry tree
rather than asserted against a corpus count: a mapped key that stopped being a
root, and a root the ruling never ruled on. The live corpus is read once, for
the invariant that the two sides agree today.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.revision_contracts import NoPredecessorCause

from ..none_root_cause_ruling import CAUSES, entries, survey_roots

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CAUSE = NoPredecessorCause.predecessor_row_without_lineage


def _edition(root: Path, modelo: str, edition: str, *, predecessor: str) -> None:
    """Write one revision manifest declaring ``predecessor`` verbatim."""
    directory = root / modelo / "revisions" / edition
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "revision.toml").write_text(
        f'[revisions."{edition}"]\npredecessor = {predecessor}\n',
        encoding="utf-8",
        newline="\n",
    )


_NONE_TABLE = '{ none = { reason = "No earlier sibling edition exists.", legal_refs = ["x:art-1"] } }'


def test_a_named_predecessor_is_not_read_as_a_root(tmp_path: Path) -> None:
    """The word ``predecessor`` in a manifest is not the ``none`` declaration."""
    _edition(tmp_path, "901", "2024", predecessor='"2023"')
    _edition(tmp_path, "901", "2025", predecessor=_NONE_TABLE)

    assert [root.key for root in survey_roots(tmp_path)] == [("901", "2025")]


def test_a_root_the_ruling_does_not_classify_is_refused_by_name(tmp_path: Path) -> None:
    """A newly authored root cannot be silently omitted from the emitted ruling."""
    _edition(tmp_path, "901", "2025", predecessor=_NONE_TABLE)
    _edition(tmp_path, "902", "2026", predecessor=_NONE_TABLE)

    with pytest.raises(SystemExit) as refusal:
        entries(modelos_dir=tmp_path, causes={("901", "2025"): _CAUSE}, display_root=tmp_path)

    message = str(refusal.value)
    assert "does not classify" in message
    assert "902 2026" in message
    assert "901 2025" not in message


def test_a_mapped_key_that_is_not_a_root_is_refused_by_name(tmp_path: Path) -> None:
    """A key that gained a named predecessor must be re-ruled, not emitted as a cause."""
    _edition(tmp_path, "901", "2025", predecessor=_NONE_TABLE)
    _edition(tmp_path, "902", "2026", predecessor='"2025"')

    with pytest.raises(SystemExit) as refusal:
        entries(
            modelos_dir=tmp_path,
            causes={("901", "2025"): _CAUSE, ("902", "2026"): _CAUSE},
            display_root=tmp_path,
        )

    message = str(refusal.value)
    assert "not corpus roots" in message
    assert "902 2026" in message


def test_an_agreeing_ruling_emits_one_record_per_root(tmp_path: Path) -> None:
    """The clean tree beside the planted defects is silent and emits every root."""
    _edition(tmp_path, "901", "2025", predecessor=_NONE_TABLE)
    _edition(tmp_path, "902", "2026", predecessor=_NONE_TABLE)

    records = entries(
        modelos_dir=tmp_path,
        causes={("901", "2025"): _CAUSE, ("902", "2026"): NoPredecessorCause.lower_grade},
        display_root=tmp_path,
    )

    assert records == [
        {
            "manifest_path": "901/revisions/2025/revision.toml",
            "edition_id": "2025",
            "cause": _CAUSE.value,
        },
        {
            "manifest_path": "902/revisions/2026/revision.toml",
            "edition_id": "2026",
            "cause": NoPredecessorCause.lower_grade.value,
        },
    ]


def test_the_ruling_and_the_live_corpus_agree() -> None:
    """The shipped table classifies exactly the roots the shipped corpus declares."""
    assert {root.key for root in survey_roots()} == set(CAUSES)
