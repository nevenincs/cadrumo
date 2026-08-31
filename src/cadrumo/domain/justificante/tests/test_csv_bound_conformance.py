"""The adopted 8-32 CSV bound, pinned at both of its acceptance surfaces.

One CSV shape is enforced through two surfaces that deliberately disagree:

* The **model boundary** — :attr:`Justificante.csv`, typed
  :data:`~core.identity.AeatCsv` — runs ``normalise_aeat_csv`` as a
  ``BeforeValidator``, so it strips and uppercases *before* its own constraints
  see the value. A lowercase or space-padded token is therefore
  ACCEPTED-AND-CORRECTED here, not refused.
* The **predicate** — :func:`~core.is_aeat_csv` — normalises nothing. It answers
  whether a token *already is* one complete CSV, so the same lowercase or padded
  token is REFUSED.

Both verdicts are correct for their surface, and a test that conflates them
asserts the wrong outcome for every case-variant input. Each case below carries
an explicit verdict for each surface.

Every verdict is a **literal**, never derived from :data:`AeatCsv`, from
:func:`is_aeat_csv`, or from the published length constants at runtime. A test
that parameterises its expectations off the bound it is checking passes just as
happily when the bound is loosened, which is the failure mode this module
exists to close: the sibling shape test at ``core/tests/test_aeat_csv_shape.py``
builds its case widths from ``AEAT_CSV_MIN_LENGTH`` / ``AEAT_CSV_MAX_LENGTH``
and so cannot detect the bound moving. That module covers the predicate's
character class; ``adapters/inbound/justificante/tests/test_csv_shape_contract.py``
covers the extractor's regex tiers. Neither reaches the pydantic alias, and
neither pins the bound as a value.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, ValidationError

from ....core.aeat_csv import AEAT_CSV_MAX_LENGTH, AEAT_CSV_MIN_LENGTH, is_aeat_csv
from ....core.period import Period
from ....tests.aeat_literal_fixtures import COTEJO_VERIFICATION_URL_FIXTURE
from .._schema import Justificante

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PERIOD = Period.from_year_and_code(2025, "1T")

# --- Length axis. Literal tokens, counted by the guard test below. ------------
_LEN_07 = "A1B2C3D"
_LEN_08 = "A1B2C3D4"
_LEN_16 = "A1B2C3D4E5F6G7H8"
_LEN_32 = "A1B2C3D4E5F6G7H8J9K0L1M2N3P4Q5R6"
_LEN_33 = "A1B2C3D4E5F6G7H8J9K0L1M2N3P4Q5R6S"

# --- Character-class axis, all at an in-range width. -------------------------
_LOWERCASE = "a1b2c3d4e5f6g7h8"
_PADDED = "   A1B2C3D4E5F6G7H8   "
_TAB_AND_NEWLINE = "\tA1B2C3D4E5F6G7H8\n"
_HYPHENATED = "A1B2C3D4-E5F6G7H8"
_EMBEDDED_SPACE = "A1B2C3D4 E5F6G7H8"
_TRAILING_PUNCTUATION = "A1B2C3D4E5F6G7H."
_NON_ASCII = "A1B2C3D4E5F6G7HÑ"
_UNANCHORED = "PREFIX-A1B2C3D4E5F6G7H8-SUFFIX"

# --- Interaction: the normaliser must not rescue an out-of-range width. ------
_PADDED_TOO_SHORT = "   A1B2C3D   "
_LOWERCASE_TOO_LONG = "a1b2c3d4e5f6g7h8j9k0l1m2n3p4q5r6s"


_MODEL_BOUNDARY_CASES: tuple[tuple[str, str, bool, str], ...] = (
    # (label, value, accepted_by_model_boundary, canonical form when accepted)
    ("shortest accepted width", _LEN_08, True, _LEN_08),
    ("mid-window width", _LEN_16, True, _LEN_16),
    ("longest accepted width", _LEN_32, True, _LEN_32),
    ("one short of the floor", _LEN_07, False, ""),
    ("one past the ceiling", _LEN_33, False, ""),
    ("empty", "", False, ""),
    ("uppercase alphanumeric", _LEN_16, True, _LEN_16),
    ("lowercase, corrected", _LOWERCASE, True, _LEN_16),
    ("space padded, corrected", _PADDED, True, _LEN_16),
    ("tab and newline padded, corrected", _TAB_AND_NEWLINE, True, _LEN_16),
    ("hyphen separator", _HYPHENATED, False, ""),
    ("embedded space", _EMBEDDED_SPACE, False, ""),
    ("trailing punctuation", _TRAILING_PUNCTUATION, False, ""),
    ("non-ascii letter", _NON_ASCII, False, ""),
    ("well-shaped run inside a longer token", _UNANCHORED, False, ""),
    ("padding does not rescue a short token", _PADDED_TOO_SHORT, False, ""),
    ("uppercasing does not rescue a long token", _LOWERCASE_TOO_LONG, False, ""),
)

_PREDICATE_CASES: tuple[tuple[str, str, bool], ...] = (
    # (label, value, accepted_by_predicate)
    ("shortest accepted width", _LEN_08, True),
    ("mid-window width", _LEN_16, True),
    ("longest accepted width", _LEN_32, True),
    ("one short of the floor", _LEN_07, False),
    ("one past the ceiling", _LEN_33, False),
    ("empty", "", False),
    ("uppercase alphanumeric", _LEN_16, True),
    ("lowercase, not normalised here", _LOWERCASE, False),
    ("space padded, not normalised here", _PADDED, False),
    ("tab and newline padded, not normalised here", _TAB_AND_NEWLINE, False),
    ("hyphen separator", _HYPHENATED, False),
    ("embedded space", _EMBEDDED_SPACE, False),
    ("trailing punctuation", _TRAILING_PUNCTUATION, False),
    ("non-ascii letter", _NON_ASCII, False),
    ("well-shaped run inside a longer token", _UNANCHORED, False),
    ("padding does not rescue a short token", _PADDED_TOO_SHORT, False),
    ("uppercasing does not rescue a long token", _LOWERCASE_TOO_LONG, False),
)

_SURFACES_DIVERGE_ON: tuple[str, ...] = (
    _LOWERCASE,
    _PADDED,
    _TAB_AND_NEWLINE,
)
"""The tokens the two surfaces answer differently, listed so the divergence is
asserted rather than left implicit in two separate case tables."""


def _receipt_with_csv(value: str) -> Justificante:
    return Justificante(
        csv=value,
        modelo="303",
        ejercicio="2025",
        period=_PERIOD,
        presentation_id="3032512345678",
        presented_at=datetime(2026, 4, 18, 11, 5, 0, tzinfo=UTC),
        tax_id="12345678Z",
        total_a_ingresar=Decimal("1234.56"),
        total_a_devolver=Decimal("78.90"),
        verification_url=AnyHttpUrl(COTEJO_VERIFICATION_URL_FIXTURE),
        source_pdf_path=Path("justificantes/303-2025-1T.pdf"),
        source_pdf_sha256="3f" * 32,
        parsed_at=datetime(2026, 4, 18, 11, 7, 30, tzinfo=UTC),
    )


def test_the_adopted_bound_is_eight_to_thirty_two() -> None:
    """The decided bound, pinned as values rather than read back as symbols.

    Moving either constant is a change to the canonical CSV contract and must
    be a deliberate, reviewed edit here — not a silent widening that every
    constant-derived test in the tree absorbs without a red.
    """

    assert AEAT_CSV_MIN_LENGTH == 8
    assert AEAT_CSV_MAX_LENGTH == 32


def test_boundary_fixture_widths_are_what_their_names_claim() -> None:
    """Guard the literals: a mistyped token would weaken every case silently."""

    assert len(_LEN_07) == 7
    assert len(_LEN_08) == 8
    assert len(_LEN_16) == 16
    assert len(_LEN_32) == 32
    assert len(_LEN_33) == 33
    assert len(_PADDED.strip()) == 16
    assert len(_PADDED_TOO_SHORT.strip()) == 7
    assert len(_LOWERCASE_TOO_LONG.strip()) == 33


@pytest.mark.parametrize(
    ("label", "value", "accepted", "canonical"),
    _MODEL_BOUNDARY_CASES,
    ids=[case[0] for case in _MODEL_BOUNDARY_CASES],
)
def test_model_boundary_verdict(label: str, value: str, accepted: bool, canonical: str) -> None:
    """The normalising surface: accepted values arrive in canonical form."""

    if accepted:
        receipt = _receipt_with_csv(value)
        assert receipt.csv == canonical, (
            f"{label}: the model boundary accepted {value!r} but stored {receipt.csv!r}; "
            f"the BeforeValidator must deliver the canonical form {canonical!r}"
        )
        return

    with pytest.raises(ValidationError):
        _receipt_with_csv(value)


@pytest.mark.parametrize(
    ("label", "value", "accepted"),
    _PREDICATE_CASES,
    ids=[case[0] for case in _PREDICATE_CASES],
)
def test_predicate_verdict(label: str, value: str, accepted: bool) -> None:
    """The non-normalising surface: is this token already one complete CSV?"""

    assert is_aeat_csv(value) is accepted, f"{label}: is_aeat_csv({value!r}) disagrees with the pinned verdict"


@pytest.mark.parametrize("value", _SURFACES_DIVERGE_ON)
def test_the_two_surfaces_diverge_exactly_where_normalisation_applies(value: str) -> None:
    """A case-variant or padded token is corrected at the model, refused by the predicate.

    Asserted directly, because the divergence is a designed property and not an
    accident of two tables: normalising at the model boundary is what preserves
    case-insensitive CSV matching, and refusing at the predicate is what keeps
    the predicate honest about what it was handed.
    """

    assert is_aeat_csv(value) is False
    assert _receipt_with_csv(value).csv == _LEN_16
