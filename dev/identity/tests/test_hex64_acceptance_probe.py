"""Tests for the hex-64 acceptance probe's verdicts and its report line.

`dev.quality.module_test_reach` listed `dev/identity/hex64_acceptance_probe.py`
as unreached. It is the second of two instruments: the census reads what a field
DECLARES, and this probe establishes what a field actually ACCEPTS at runtime,
which is the only one of the two that can say a malformed digest gets through.

Its report line understated its own finding. The shape label was derived from a
leading ``Z`` and read ``upper-hex``, but neither probe value is hexadecimal -
they are sixty-four ``Z`` characters and sixty-four exclamation marks. A
reviewer reading ``upper-hex`` would reasonably triage it as case-insensitivity
and move on, when what the field accepted was sixty-four arbitrary letters
standing in for a SHA-256.

The verdict cases drive the real :func:`probe` against real models in this tree,
including its vacuity gate - a refusal probe that has never once seen an
acceptance is measuring its own harness, and that distinction is the module's
central claim.
"""

from __future__ import annotations

import pytest

from ..hex64_acceptance_probe import (
    INVALID_VALUES,
    VALID_DIGEST,
    ProbeResult,
    Verdict,
    admitted_shape,
    module_name_for,
    probe,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _result(verdict: Verdict, accepted: tuple[str, ...] = (), detail: str = "") -> ProbeResult:
    return ProbeResult("src/cadrumo/x.py", "Model", "digest", verdict, accepted, detail)


def test_the_probe_values_are_not_hexadecimal() -> None:
    """The premise of the whole instrument, and of the label defect.

    A probe value that happened to be valid hex would be admitted by a correct
    field, and every REFUSES verdict in the sweep would be a false negative.
    """
    for value in INVALID_VALUES:
        assert len(value) == 64
        assert not all(character in "0123456789abcdefABCDEF" for character in value)


def test_the_valid_digest_is_a_real_sha256() -> None:
    """The vacuity gate validates this first; if it were malformed, every field would look vacuous."""
    assert len(VALID_DIGEST) == 64
    assert all(character in "0123456789abcdef" for character in VALID_DIGEST)


def test_sixty_four_letters_are_not_called_upper_hex() -> None:
    """The defect: the label named a shape the value does not have.

    ``upper-hex`` reads as a formatting nit. ``non-hex-letters`` reads as a
    field accepting arbitrary text where a digest belongs, which is what
    happened.
    """
    assert admitted_shape("Z" * 64) == "non-hex-letters"


def test_punctuation_is_named_as_punctuation() -> None:
    """The other probe value, unchanged, so the fix is not a blanket rename."""
    assert admitted_shape("!" * 64) == "punctuation"


def test_a_genuinely_hexadecimal_value_is_named_hex() -> None:
    """Uppercase hex is a real, milder finding, and now has its own name.

    The old label claimed this case for a value that was nothing like it, which
    is why the honest name had to be freed up.
    """
    assert admitted_shape("ABCDEF" + "0" * 58) == "hex"


def test_the_rendered_line_names_every_admitted_shape() -> None:
    """One deterministic line carrying what was accepted, not merely that something was."""
    rendered = _result(Verdict.ACCEPTS_NON_HEX, INVALID_VALUES).rendered()

    assert "ACCEPTS_NON_HEX" in rendered
    assert "non-hex-letters" in rendered
    assert "punctuation" in rendered
    assert "upper-hex" not in rendered


def test_an_unmeasured_field_reports_its_reason_instead_of_shapes() -> None:
    """VACUOUS is not a pass, so the line must carry why it could not measure."""
    rendered = _result(Verdict.VACUOUS, detail="ValidationError: forward ref").rendered()

    assert "VACUOUS" in rendered
    assert "forward ref" in rendered


def test_a_module_path_becomes_its_importable_name() -> None:
    """The sweep imports what the census reported as a path."""
    assert module_name_for("src/cadrumo/domain/x.py") == "cadrumo.domain.x"


def test_a_field_that_enforces_the_digest_shape_refuses() -> None:
    """The field the module's docstring names as the reason a second instrument exists.

    ``RawProvenance.source_sha256`` declares a length and no pattern, so the
    census must flag it; a hand-written validator enforces the shape anyway, so
    the probe must clear it. That gap is the whole point of this module.
    """
    result = probe(
        "src/cadrumo/domain/transactions/raw_transaction.py",
        "RawProvenance",
        "source_sha256",
    )

    assert result.verdict is Verdict.REFUSES
    assert result.accepted == ()


def test_an_unresolvable_field_is_unreached_rather_than_refusing() -> None:
    """An import that failed must never read as a field that held the line.

    Counting a resolution failure as a refusal is how a sweep reports fields it
    never tested as passing, which is the harness defect this module was
    rebuilt to avoid.
    """
    result = probe("src/cadrumo/does_not_exist.py", "Missing", "field")

    assert result.verdict is Verdict.UNREACHED
    assert result.detail
    assert result.accepted == ()


def test_an_unknown_field_on_a_real_model_is_unreached() -> None:
    """The same distinction one level in: the module imports, the field does not exist.

    Written after the first draft of this file pointed at a guessed module path
    and passed for the wrong reason - the import failed, so the missing FIELD
    was never the thing being measured.
    """
    result = probe(
        "src/cadrumo/domain/transactions/raw_transaction.py",
        "RawProvenance",
        "no_such_field_anywhere",
    )

    assert result.verdict is Verdict.UNREACHED
