"""Gates on the operator-authored column-role truth and its scoring wiring.

Two failure modes are guarded, both of which would let a mapping figure look
sound while measuring nothing:

**The truth drifting from the files.** The expectations are positional, so a
corpus edit that renames a header or inserts a column silently misaligns every
verdict. The headers are therefore re-read from the real exports through the
production normalizer and asserted equal, rather than trusted.

**The wiring passing under any emission.** A scorer reached through a translation
layer can be wired so that nothing it reports ever moves. Each verdict class is
driven deliberately -- a perfect emission, a wrong one, an invented one, an
abstaining one -- so a green result means the path discriminates.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from cadrumo.core.field_role import FieldRole
from cadrumo.core.tabular import normalize_tabular_bytes

from .. import (
    CORPUS_ROOT,
    TABULAR_COLUMN_ROLE_TRUTH,
    TabularTruthError,
    column_role_truth_document,
    defensible_alternate_fields,
    emission_from_roles,
    load_corpus_key,
    score_emission,
    slot_name,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_CSV_FORMAT = "csv_spreadsheet"


def _corpus_key():
    return load_corpus_key()


def _tabular_entries() -> list[dict[str, Any]]:
    payload = json.loads((CORPUS_ROOT / "GROUND_TRUTH.json").read_bytes())
    return [row for row in payload["documents"] if row["axes"]["file_format"] == _CSV_FORMAT]


def test_truth_covers_every_tabular_export_and_nothing_else() -> None:
    """The authored set is exactly the corpus's tabular set.

    Derived from the key rather than from a literal count, so a corpus that gains
    a tenth export fails here instead of being silently excluded from a figure.
    """
    corpus_ids = {row["doc_id"] for row in _tabular_entries()}
    assert set(TABULAR_COLUMN_ROLE_TRUTH) == corpus_ids


def test_authored_headers_equal_the_files_own_headers() -> None:
    """Every expectation names the header the file actually prints, in order.

    The anti-drift gate. Positional truth against a file that moved is worse than
    no truth, because it still produces a number.
    """
    for entry in _tabular_entries():
        table = normalize_tabular_bytes((CORPUS_ROOT / entry["path"]).read_bytes())
        expectations = TABULAR_COLUMN_ROLE_TRUTH[entry["doc_id"]]
        authored = tuple(expectation.header for expectation in expectations)
        assert authored == tuple(table.headers), entry["doc_id"]
        assert tuple(e.column_index for e in expectations) == tuple(range(len(table.headers))), entry["doc_id"]


def test_every_authored_role_is_a_real_field_role_member() -> None:
    """No expectation names a token outside the closed vocabulary.

    A typo'd role would be permanently WRONG against every reader, and would read
    as a model failure rather than as a truth defect.
    """
    permitted = {role.value for role in FieldRole}
    for doc_id, expectations in TABULAR_COLUMN_ROLE_TRUTH.items():
        for expectation in expectations:
            if expectation.expected is not None:
                assert expectation.expected in permitted, f"{doc_id} {expectation.header}"
            for alternate in expectation.also_defensible:
                if alternate is not None:
                    assert alternate in permitted, f"{doc_id} {expectation.header}"


def test_unmapped_is_never_an_authored_expectation() -> None:
    """An expected-unmapped column is declared ``None``, never the token.

    The two are not interchangeable here: ``None`` projects to a null-truth slot
    and makes a claim there a FABRICATION, while the token would project to a
    scorable slot and make it merely wrong.
    """
    for doc_id, expectations in TABULAR_COLUMN_ROLE_TRUTH.items():
        for expectation in expectations:
            assert expectation.expected != FieldRole.UNMAPPED.value, f"{doc_id} {expectation.header}"


#: The authored split, declared here rather than recomputed from the truth it
#: describes. Deriving both sides of the assertion from the same tuple makes a
#: gate that passes under every possible edit -- this pair was exactly that until
#: a mutation run showed it could not be made to fail. These are the anchor: a
#: truth edit that reclassifies a column has to change a number here too, in
#: view, rather than silently moving a denominator.
AUTHORED_SPLIT: dict[str, tuple[int, int]] = {
    "OP-ISS-libro_facturas_expedidas_2025_2026": (9, 1),
    "OP-ISS-pos_zreport_20260514": (5, 3),
    "OP-PUR-bank_bbva_2026Q1": (4, 4),
    "OP-PUR-bank_caixa_excel_export_2026Q1": (3, 2),
    "OP-PUR-bank_neobank_2026Q1": (5, 3),
    "OP-PUR-bank_statement_2026Q1_Q2": (3, 2),
    "OP-PUR-expenses_app_export_2026": (8, 2),
    "OP-REC-ledger_erp_export_2026Q1": (3, 4),
    "OP-REC-libro_facturas_recibidas_2025_2026": (10, 0),
}


def test_projection_splits_slots_into_the_declared_scorable_and_trap_counts() -> None:
    """The projection matches the declared split, and closes on the FILE's width.

    Two independent anchors, because the truth cannot be its own witness. The
    split is asserted against :data:`AUTHORED_SPLIT`, declared separately; the
    closure is asserted against the column count the production normalizer reads
    off the real export, which no edit to the authored truth can move.
    """
    key = _corpus_key()
    file_widths = {
        entry["doc_id"]: len(normalize_tabular_bytes((CORPUS_ROOT / entry["path"]).read_bytes()).headers)
        for entry in _tabular_entries()
    }
    total_scorable = 0
    total_traps = 0
    for doc_id in TABULAR_COLUMN_ROLE_TRUTH:
        document = column_role_truth_document(doc_id, key=key)
        scorable = len(document.scorable_fields)
        traps = len(document.fabrication_trap_fields)
        assert (scorable, traps) == AUTHORED_SPLIT[doc_id], doc_id
        assert scorable + traps == file_widths[doc_id], doc_id
        total_scorable += scorable
        total_traps += traps
    assert (total_scorable, total_traps) == (50, 21)
    assert total_scorable + total_traps == sum(file_widths.values()) == 71


def test_a_perfect_emission_scores_every_slot_correctly() -> None:
    """The wiring control: the authored answer must score as a clean sweep.

    Without this, every "the reader did badly" figure could equally be the wiring
    being incapable of reporting a success.

    **This proves the WIRING, not the truth.** The emission is built from the same
    expectations it is scored against, so it passes under any truth whatever and
    cannot detect a truth change -- a mutation run confirmed exactly that. The
    counts are therefore asserted against :data:`AUTHORED_SPLIT` rather than
    against the tuple the emission came from, which is the one part of this test
    a truth edit can move.
    """
    key = _corpus_key()
    for doc_id, expectations in TABULAR_COLUMN_ROLE_TRUTH.items():
        roles = [e.expected if e.expected is not None else FieldRole.UNMAPPED.value for e in expectations]
        scoring = score_emission(
            document=column_role_truth_document(doc_id, key=key),
            emitted=emission_from_roles(doc_id, roles),
        )
        assert scoring.wrong == 0, doc_id
        assert scoring.missed == 0, doc_id
        assert scoring.fabricated == 0, doc_id
        expected_scorable, expected_traps = AUTHORED_SPLIT[doc_id]
        assert scoring.matched == expected_scorable, doc_id
        assert scoring.correctly_abstained == expected_traps, doc_id


def test_a_claim_on_an_expected_unmapped_column_scores_fabricated() -> None:
    """The trap must bite: inventing a meaning is a hard error, not a miss."""
    key = _corpus_key()
    doc_id = "OP-PUR-bank_bbva_2026Q1"
    expectations = TABULAR_COLUMN_ROLE_TRUTH[doc_id]
    roles = [e.expected if e.expected is not None else FieldRole.UNMAPPED.value for e in expectations]
    # "Disponible" is a running balance: the file's own closing figure, which is
    # not a movement amount and is the classic wrong copy.
    disponible = next(i for i, e in enumerate(expectations) if e.header == "Disponible")
    roles[disponible] = FieldRole.GRAND_TOTAL.value
    scoring = score_emission(
        document=column_role_truth_document(doc_id, key=key), emitted=emission_from_roles(doc_id, roles)
    )
    assert scoring.fabricated == 1
    assert slot_name(expectations[disponible]) in scoring.fabricated_fields()


def test_a_wrong_role_on_a_scorable_column_scores_wrong_not_fabricated() -> None:
    """Wrong and fabricated must stay distinct, or the severity signal is lost."""
    key = _corpus_key()
    doc_id = "OP-REC-libro_facturas_recibidas_2025_2026"
    expectations = TABULAR_COLUMN_ROLE_TRUTH[doc_id]
    roles = [e.expected if e.expected is not None else FieldRole.UNMAPPED.value for e in expectations]
    base = next(i for i, e in enumerate(expectations) if e.header == "BASE")
    roles[base] = FieldRole.SUPLIDO_AMOUNT.value
    scoring = score_emission(
        document=column_role_truth_document(doc_id, key=key), emitted=emission_from_roles(doc_id, roles)
    )
    assert scoring.wrong == 1
    assert scoring.fabricated == 0


def test_declining_a_scorable_column_scores_missed_not_fabricated() -> None:
    """Abstention on a real column is a miss; the UNMAPPED translation proves out."""
    key = _corpus_key()
    doc_id = "OP-REC-libro_facturas_recibidas_2025_2026"
    expectations = TABULAR_COLUMN_ROLE_TRUTH[doc_id]
    roles = [e.expected if e.expected is not None else FieldRole.UNMAPPED.value for e in expectations]
    roles[0] = FieldRole.UNMAPPED.value
    scoring = score_emission(
        document=column_role_truth_document(doc_id, key=key), emitted=emission_from_roles(doc_id, roles)
    )
    assert scoring.missed == 1
    assert scoring.fabricated == 0


def test_a_defensible_alternate_is_reported_and_never_scored_as_matched() -> None:
    """The decomposition must surface the alternate AND leave the score strict."""
    key = _corpus_key()
    doc_id = "OP-PUR-bank_bbva_2026Q1"
    expectations = TABULAR_COLUMN_ROLE_TRUTH[doc_id]
    roles = [e.expected if e.expected is not None else FieldRole.UNMAPPED.value for e in expectations]
    value_date = next(i for i, e in enumerate(expectations) if e.header == "F.Valor")
    roles[value_date] = FieldRole.BOOKED_DATE.value

    alternates = defensible_alternate_fields(doc_id, roles)
    assert slot_name(expectations[value_date]) in alternates

    scoring = score_emission(
        document=column_role_truth_document(doc_id, key=key), emitted=emission_from_roles(doc_id, roles)
    )
    # Strict: the alternate lands on a trap slot, so it scores fabricated and is
    # NOT quietly upgraded to matched by the decomposition existing.
    assert scoring.fabricated == 1
    assert scoring.matched == sum(1 for e in expectations if e.expected is not None)


def test_a_length_mismatch_refuses_rather_than_misaligning() -> None:
    """A proposal of the wrong width must raise, never score by position anyway."""
    with pytest.raises(TabularTruthError, match="positional score across a length mismatch"):
        emission_from_roles("OP-PUR-bank_caixa_excel_export_2026Q1", [FieldRole.BOOKED_DATE.value])


def test_an_unauthored_document_refuses() -> None:
    """A document with no authored truth names the authored set rather than returning empty."""
    with pytest.raises(TabularTruthError, match="no column-role truth is authored"):
        emission_from_roles("OP-NOT-a-real-document", [])
