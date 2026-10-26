"""The grouped recovery code: minting, cosmetic normalisation and wipeable custody."""

from __future__ import annotations

import pytest

from ..errors import StorageValidationError
from ..recovery_key import (
    RECOVERY_CODE_ALPHABET,
    RECOVERY_CODE_GROUP_COUNT,
    RECOVERY_CODE_GROUP_LENGTH,
    RECOVERY_CODE_SEPARATOR,
    RECOVERY_CODE_SYMBOL_COUNT,
    RecoveryKey,
    canonical_recovery_code,
    format_recovery_code,
    generate_recovery_key,
    normalise_recovery_code,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_SYMBOLS = "ABCDEFGHJKLMNPQRSTUVWXYZ234567"
_CANONICAL = "ABCDE-FGHJK-LMNPQ-RSTUV-WXYZ2-34567"


def test_the_alphabet_omits_every_symbol_people_misread() -> None:
    assert len(RECOVERY_CODE_ALPHABET) == 32
    assert len(set(RECOVERY_CODE_ALPHABET)) == 32
    assert set("01IO") & set(RECOVERY_CODE_ALPHABET) == set()
    assert RECOVERY_CODE_SYMBOL_COUNT == RECOVERY_CODE_GROUP_LENGTH * RECOVERY_CODE_GROUP_COUNT == 30


def test_minted_codes_are_canonical_full_alphabet_and_distinct() -> None:
    minted = [generate_recovery_key() for _ in range(64)]
    codes = {key.code for key in minted}

    assert len(codes) == 64
    for code in codes:
        groups = code.split(RECOVERY_CODE_SEPARATOR)
        assert len(groups) == RECOVERY_CODE_GROUP_COUNT
        assert all(len(group) == RECOVERY_CODE_GROUP_LENGTH for group in groups)
        assert set(code.replace(RECOVERY_CODE_SEPARATOR, "")) <= set(RECOVERY_CODE_ALPHABET)
        assert canonical_recovery_code(code) == code
    # Sixty-four independent draws of thirty symbols cover the alphabet; a
    # generator stuck on a subset would betray itself here.
    assert set("".join(codes).replace(RECOVERY_CODE_SEPARATOR, "")) == set(RECOVERY_CODE_ALPHABET)


@pytest.mark.parametrize(
    "typed",
    (
        _CANONICAL,
        _SYMBOLS,
        _CANONICAL.lower(),
        _SYMBOLS.lower(),
        " abcde fghjk lmnpq rstuv wxyz2 34567 ",
        "abcde_fghjk_lmnpq_rstuv_wxyz2_34567",
        "ABC-DEF-GHJ-KLM-NPQ-RST-UVW-XYZ-234-567",
        "ABCDE\tFGHJK\nLMNPQ\r\nRSTUV WXYZ2-34567",
    ),
)
def test_case_separators_and_whitespace_are_cosmetic(typed: str) -> None:
    assert normalise_recovery_code(typed) == _SYMBOLS
    assert canonical_recovery_code(typed) == _CANONICAL
    assert format_recovery_code(normalise_recovery_code(typed)) == _CANONICAL


@pytest.mark.parametrize(
    "typed",
    (
        "",
        _SYMBOLS[:-1],
        _SYMBOLS + "A",
        _CANONICAL + "-ABCDE",
        _SYMBOLS[:-1] + "0",
        _SYMBOLS[:-1] + "O",
        _SYMBOLS[:-1] + "I",
        _SYMBOLS[:-1] + "1",
        _SYMBOLS[:-1] + "é",
        _SYMBOLS[:-1] + ".",
        "correct horse battery staple",
    ),
)
def test_a_code_outside_the_alphabet_or_length_is_refused_before_any_proof(typed: str) -> None:
    with pytest.raises(StorageValidationError):
        normalise_recovery_code(typed)
    with pytest.raises(StorageValidationError):
        canonical_recovery_code(typed)


@pytest.mark.parametrize("symbols", ("", _SYMBOLS[:-1], _SYMBOLS + "A", _SYMBOLS.lower(), _CANONICAL))
def test_format_refuses_anything_but_a_complete_bare_symbol_run(symbols: str) -> None:
    with pytest.raises(StorageValidationError):
        format_recovery_code(symbols)


@pytest.mark.parametrize("code", (_SYMBOLS, _CANONICAL.lower(), _CANONICAL + " "))
def test_a_recovery_key_holds_only_the_canonical_grouped_form(code: str) -> None:
    with pytest.raises(StorageValidationError):
        RecoveryKey(code=code)


def test_wipe_zeroes_the_buffer_in_place_and_is_idempotent() -> None:
    key = RecoveryKey(code=_CANONICAL)
    assert key.code == _CANONICAL

    key.wipe()

    wiped = key.code
    assert len(wiped) == len(_CANONICAL)
    assert set(wiped) == {"\x00"}
    key.wipe()
    assert key.code == wiped


def test_the_context_manager_wipes_on_exit_even_when_the_body_raises() -> None:
    key = generate_recovery_key()
    with key as held:
        assert held is key
        assert canonical_recovery_code(held.code) == held.code
    assert set(key.code) == {"\x00"}

    raising = generate_recovery_key()
    with pytest.raises(RuntimeError, match="handover failed"), raising:
        raise RuntimeError("handover failed")
    assert set(raising.code) == {"\x00"}


def test_a_recovery_key_cannot_be_serialised_or_grow_new_attributes() -> None:
    key = RecoveryKey(code=_CANONICAL)
    assert not hasattr(key, "model_dump_json")
    assert not hasattr(key, "__dict__")
    with pytest.raises(AttributeError):
        object.__setattr__(key, "extra", "value")
    assert _CANONICAL not in repr(key)
