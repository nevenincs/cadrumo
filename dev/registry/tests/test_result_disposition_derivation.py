"""The diseño-read disposition derivation reproduces the hand-authored table exactly.

The table in ``core`` was written by reading each modelo's diseño de registro.
This derivation claims to read the same thing. The only evidence for that claim
is that it lands on the same answer for every modelo the table covers, without
having seen it -- so the agreement is asserted here, per modelo, and a single
divergence fails.

Agreement alone would still be satisfiable by a derivation that returned the
table's own values, so the negative cases are proved too: a modelo whose diseño
never carries the field must derive nothing, and the letter precedence must
actually select rather than always answering the same way.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..derive_result_dispositions import (
    DisenoDispositionEvidence,
    core_table_expectations,
    derivation_disagreements,
    read_diseno_evidence,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Modelos whose diseno carries no Tipo de declaracion field at all. Verified by
#: scanning their real corpus files, not by a failed match on a missing dir.
_INFORMATIVE_WITHOUT_THE_FIELD = ("347", "349", "190", "193", "720", "184", "180")


def test_the_derivation_reproduces_every_hand_authored_mapping() -> None:
    """Zero divergence against the core table, per modelo."""
    disagreements = derivation_disagreements()

    assert disagreements == (), "\n".join(disagreements)


def test_the_core_table_is_not_empty_so_the_agreement_means_something() -> None:
    """Anti-vacuity: agreeing with an empty table proves nothing."""
    expectations = core_table_expectations()

    assert len(expectations) >= 5, f"only {len(expectations)} mappings to check the derivation against"


def test_an_informative_modelo_derives_no_disposition_from_real_corpus_files() -> None:
    """A modelo without the field derives nothing, and the corpus was actually read.

    The scanned-file count is asserted so an absent directory cannot masquerade
    as a modelo that carries no field.
    """
    for modelo in _INFORMATIVE_WITHOUT_THE_FIELD:
        evidence = read_diseno_evidence(modelo)

        assert evidence.corpus_files_scanned > 0, f"modelo {modelo}: no corpus files scanned; absence is unproven"
        assert not evidence.declares_the_field, f"modelo {modelo}: expected no Tipo de declaracion field"
        assert evidence.negative_disposition is None
        assert evidence.zero_disposition is None


def test_the_letter_precedence_actually_selects() -> None:
    """The rule must discriminate, not answer the same way regardless of input."""

    def evidence(*codes: str) -> DisenoDispositionEvidence:
        return DisenoDispositionEvidence(
            modelo="test",
            codes=frozenset(codes),
            note="synthetic",
            corpus_files_scanned=1,
        )

    assert evidence("C", "D", "I", "N").negative_disposition == "C"
    assert evidence("B", "G", "I", "N").negative_disposition == "B"
    assert evidence("D", "I", "N", "R").negative_disposition == "D"
    assert evidence("G", "I", "N", "U").negative_disposition == "N"
    # C outranks both B and D when a diseno somehow admits several.
    assert evidence("B", "C", "D").negative_disposition == "C"
    assert evidence("B", "D").negative_disposition == "B"


def test_a_zero_result_is_negativa_wherever_the_field_exists() -> None:
    """Every modelo carrying the field admits N, so zero maps there uniformly."""
    for modelo in sorted(core_table_expectations()):
        evidence = read_diseno_evidence(modelo)

        assert evidence.zero_disposition == "N", f"modelo {modelo} did not derive N for a zero result"


def test_a_missing_corpus_directory_is_distinguishable_from_an_absent_field(tmp_path: Path) -> None:
    """Anti-tautology: a directory that is not there must not read as evidence of absence."""
    evidence = read_diseno_evidence("999", tmp_path)

    assert evidence.corpus_files_scanned == 0
    assert not evidence.declares_the_field


def test_an_unreadable_file_is_not_counted_as_scanned(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``corpus_files_scanned`` exists to tell a real zero from an absent directory.

    Counting a file before reading it inflated exactly that denominator with
    files never examined, so the anti-vacuity signal this evidence carries was
    itself vacuous. The lenient decode was the other half: a replaced byte can
    break the field anchor or the code pattern and lose evidence with no sign.
    """
    from ..derive_result_dispositions import read_diseno_evidence

    base = tmp_path / "modelo_999"
    base.mkdir()
    (base / "sound.txt").write_text("nothing of interest" + chr(10), encoding="utf-8")
    (base / "undecodable.txt").write_bytes(bytes([0xFF, 0xFE]) + b"nothing of interest")

    evidence = read_diseno_evidence("999", root=tmp_path)

    assert evidence.corpus_files_scanned == 1, "the unreadable file was counted as scanned"
    error = capsys.readouterr().err
    assert "over-stated the corpus" in error
    assert "undecodable.txt" in error


def test_a_readable_corpus_counts_every_file_and_stays_silent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The success path, so the new guard cannot be satisfied by counting nothing."""
    from ..derive_result_dispositions import read_diseno_evidence

    base = tmp_path / "modelo_999"
    base.mkdir()
    (base / "one.txt").write_text("alpha" + chr(10), encoding="utf-8")
    (base / "two.txt").write_text("bravo" + chr(10), encoding="utf-8")

    evidence = read_diseno_evidence("999", root=tmp_path)

    assert evidence.corpus_files_scanned == 2
    assert capsys.readouterr().err == ""
