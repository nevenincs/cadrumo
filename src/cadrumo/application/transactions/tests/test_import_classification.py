"""Unit tests for the single import-row verdict.

Two classifiers once answered this question and disagreed: the diagnostics path
counted an intra-batch fingerprint repeat as skipped, the persisting path
imported both rows. These tests pin the reasoned position that survived — an
intra-batch repeat imports, because two identical same-day movements are two
movements and dropping one under-declares — and the precedence between the
three refusal cases, which is the part a later edit could silently reorder.
"""

from __future__ import annotations

import pytest

from ..import_classification import ImportRowVerdict, classify_import_row

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FP = "fingerprint-a"
_TX = "tx-a"


def _classify(
    *,
    stored: set[str] | None = None,
    batch_fps: set[str] | None = None,
    batch_ids: set[str] | None = None,
) -> ImportRowVerdict:
    return classify_import_row(
        fingerprint=_FP,
        transaction_id=_TX,
        stored_fingerprints=stored or set(),
        batch_fingerprints=batch_fps or set(),
        batch_transaction_ids=batch_ids or set(),
    )


def test_an_unseen_row_is_new_and_imports() -> None:
    """Nothing matches, so the row is new."""
    verdict = _classify()
    assert verdict is ImportRowVerdict.NEW
    assert verdict.imports


def test_a_stored_fingerprint_is_a_reimport_and_is_skipped() -> None:
    """The same movement seen before — a re-imported statement or a re-export."""
    verdict = _classify(stored={_FP})
    assert verdict is ImportRowVerdict.DUPLICATE_OF_STORED
    assert not verdict.imports


def test_an_intra_batch_fingerprint_repeat_still_imports() -> None:
    """Two identical same-day movements are two movements.

    This is the whole point of the consolidation: skipping here silently
    under-declares, which is the worse error of the two directions.
    """
    verdict = _classify(batch_fps={_FP})
    assert verdict is ImportRowVerdict.REPEATED_IN_BATCH
    assert verdict.imports


def test_an_intra_batch_id_collision_is_skipped() -> None:
    """The catalogue keys on the id, so the later row would overwrite the earlier."""
    verdict = _classify(batch_ids={_TX})
    assert verdict is ImportRowVerdict.COLLIDING_TRANSACTION_ID
    assert not verdict.imports


def test_a_stored_fingerprint_outranks_every_batch_signal() -> None:
    """An already-stored fingerprint is a re-import whatever else the batch holds."""
    assert _classify(stored={_FP}, batch_fps={_FP}, batch_ids={_TX}) is ImportRowVerdict.DUPLICATE_OF_STORED


def test_an_id_collision_outranks_a_fingerprint_repeat() -> None:
    """The id collision is the one that cannot persist, so it must win.

    Reversing these two would turn a row that physically cannot be stored into
    a reported import, and the count would claim a row the catalogue dropped.
    """
    assert _classify(batch_fps={_FP}, batch_ids={_TX}) is ImportRowVerdict.COLLIDING_TRANSACTION_ID


def test_exactly_the_two_intended_verdicts_import() -> None:
    """Guards the import/skip split against a member being added on either side."""
    importing = {verdict for verdict in ImportRowVerdict if verdict.imports}
    assert importing == {ImportRowVerdict.NEW, ImportRowVerdict.REPEATED_IN_BATCH}
