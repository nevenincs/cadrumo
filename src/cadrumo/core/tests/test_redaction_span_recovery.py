"""The recorded-output oracle recovers replacements without exhaustive substring hashing."""

from __future__ import annotations

import pytest

from ..hashing import sha256_hex
from .redaction_span_recovery import recover_replaced_spans

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _digest(value: str) -> str:
    return f"sha256:{sha256_hex(value.encode('utf-8'))[:8]}"


@pytest.mark.parametrize(
    ("prefix", "spans", "separator", "suffix"),
    [
        ("before ", ("ESB12345674",), "", " after"),
        ("", ("first", "second"), "", ""),
        ("", ("a repeated delimiter", "mañana"), " ", " final"),
        ("x" * 508_000, ("ESB12345674",), "", ""),
        (_digest("preexisting") * 9_230, ("ESB12345674",), "", ""),
        ("", ("x" * 508_000,), "", " trailing"),
    ],
    ids=[
        "surrounding-text",
        "adjacent-digests",
        "ambiguous-delimiter-and-unicode",
        "long-line",
        "existing-digests",
        "long-replacement",
    ],
)
def test_recovers_only_replaced_spans(prefix: str, spans: tuple[str, ...], separator: str, suffix: str) -> None:
    source = prefix + separator.join(spans) + suffix
    emitted = prefix + separator.join(_digest(span) for span in spans) + suffix

    assert recover_replaced_spans(source, emitted) == set(spans)


@pytest.mark.parametrize(
    ("source", "emitted"),
    [
        ("before value", "changed " + _digest("value")),
        ("value after", _digest("value") + " changed"),
        ("value", _digest("absent")),
        ("value after", _digest("absent") + " after"),
        ("x" * 508_000, _digest("absent")),
    ],
    ids=["changed-prefix", "changed-suffix", "wrong-digest", "wrong-digest-before-suffix", "long-wrong-digest"],
)
def test_refuses_changes_not_explained_by_verified_replacements(source: str, emitted: str) -> None:
    with pytest.raises(AssertionError):
        recover_replaced_spans(source, emitted)


def test_nonidentity_replacement_is_recovered_for_the_authority_to_refuse() -> None:
    assert recover_replaced_spans("ordinary prose", _digest("ordinary prose")) == {"ordinary prose"}
