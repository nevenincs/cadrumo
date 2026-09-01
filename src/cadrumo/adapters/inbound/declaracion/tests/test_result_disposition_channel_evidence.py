"""Which channel carries the filed result disposition, measured on AEAT's own renders.

Recovering the disposition a taxpayer actually elected is the precondition for
suppressing compensación carry-forward: a credit filed ``a compensar`` carries
forward, and the same credit filed ``a devolver`` does not. Three candidate
channels exist, and only one carries the signal.

**The justificante receipt does not.** Its parsed record carries exactly two
amounts, ``total_a_ingresar`` and ``total_a_devolver``. A populated devolver
amount identifies a refund, but a compensación filing and a negativa filing both
present with NEITHER amount, so the receipt collapses precisely the two cases the
carry-forward decision has to tell apart.

**The declaración register row does not either.** Its ``tipo_solicitud`` cell is
free text that this project reads but has never verified against AEAT; the
register test that exercises it asserts only that the two filings of one period
carry DIFFERENT values, never what either value says.

**The filed declaración render does.** These tests measure that on AEAT's own
published facsimiles, and they measure one more thing that matters more than the
positive result: the pre-printed election letters are NOT the signal. ``C``,
``I`` and ``D`` are printed form furniture, present on every render whether or
not that election was made, so an implementation keying on the letter would
report compensación for every filing including the ones that are ingreso. The
discriminating signal is which election's amount casilla carries a value.

See Also:
    :class:`~core.ResultDisposition`
        The code set these renders' elections correspond to.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from .....tests import FIXTURES_DIR
from .._parsers.pdfplumber_backend import extract_pages_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_ANNEX_DIR = FIXTURES_DIR / "manual_annexes" / "303"

_SPECIMENS = ("2024-1T", "2024-2T", "2024-3T", "2024-4T")
"""The AEAT-published M303 facsimiles for one worked example's four quarters.

Two of the four filed a negative resultado and elected compensación; two filed a
positive resultado and elected ingreso. That split is what lets these tests
discriminate rather than merely observe.
"""

_PREPRINTED_SECTIONS = {
    "sin actividad": r"Sin\s+actividad\s+\(4\)",
    "compensacion": r"Compensaci[oó]n\s+\(6\)",
    "ingreso": r"Ingreso\s+\(7\)",
    "devolucion": r"Devoluci[oó]n\s+\(8\)",
}

_PREPRINTED_LETTERS = {
    "C beside the compensacion casilla": r"compensar\s+72\s+C\b",
    "I beside the ingreso importe": r"Importe:\s+I\b",
    "D beside the devolucion casilla": r"Importe\s*\.*\s*73\s+D\b",
}

_RESULTADO_71 = r"Resultado\s+\(69\s*-\s*70\s*\+\s*109\)\s*\.*\s*71\s+(-?[\d.,]+)"
_CASILLA_72_AMOUNT = r"compensar\s+72\s+C\s+([\d.,]+)"


def _flat_text(specimen: str) -> str:
    path: Path = _ANNEX_DIR / f"{specimen}.pdf"
    assert path.is_file(), f"missing AEAT facsimile {specimen}; this suite measures AEAT artefacts only"
    return re.sub(r"\s+", " ", "\n".join(extract_pages_text(path)))


def _spanish_decimal(printed: str) -> Decimal:
    return Decimal(printed.replace(".", "").replace(",", "."))


@pytest.mark.parametrize("specimen", _SPECIMENS)
def test_the_render_prints_every_election_section(specimen: str) -> None:
    """All four election sections are printed on every render.

    Establishes the premise the next test rests on: the sections are form
    furniture, so their presence carries no information about what was elected.
    """
    flat = _flat_text(specimen)

    missing = [name for name, pattern in _PREPRINTED_SECTIONS.items() if not re.search(pattern, flat)]
    assert missing == [], f"{specimen} does not print election section(s) {missing}"


@pytest.mark.parametrize("specimen", _SPECIMENS)
def test_the_election_letters_are_preprinted_and_therefore_not_the_signal(specimen: str) -> None:
    """The C, I and D letters appear on every render regardless of the election.

    This is the load-bearing negative result. Two of these four specimens elected
    ingreso and two elected compensación, yet all three letters are printed on all
    four. An implementation that recovered the disposition by finding a letter
    would therefore report the same disposition for every filing, and would do so
    while looking like it read the form.
    """
    flat = _flat_text(specimen)

    absent = [name for name, pattern in _PREPRINTED_LETTERS.items() if not re.search(pattern, flat)]
    assert absent == [], f"{specimen} does not print election letter(s) {absent}"


@pytest.mark.parametrize("specimen", _SPECIMENS)
def test_the_populated_compensacion_casilla_tracks_the_sign_of_the_result(specimen: str) -> None:
    """Casilla 72 carries an amount exactly when the resultado is negative.

    This is the channel's actual discriminating signal, and it is measured against
    AEAT's own renders rather than against any value this project computed. A
    negative resultado is a credit and the taxpayer elected to carry it forward,
    so 72 is populated; a positive resultado is payable and 72 is empty.
    """
    flat = _flat_text(specimen)

    resultado_match = re.search(_RESULTADO_71, flat)
    assert resultado_match is not None, f"{specimen} does not print casilla 71"
    resultado = _spanish_decimal(resultado_match.group(1))

    casilla_72 = re.search(_CASILLA_72_AMOUNT, flat)
    if resultado < 0:
        assert casilla_72 is not None, (
            f"{specimen} filed a negative resultado {resultado} but prints no amount in casilla 72, "
            "so the compensación election cannot be read off this render"
        )
        assert _spanish_decimal(casilla_72.group(1)) == -resultado, (
            f"{specimen} casilla 72 does not carry the magnitude of the negative resultado"
        )
    else:
        assert casilla_72 is None, (
            f"{specimen} filed a positive resultado {resultado} yet prints an amount in casilla 72, "
            "so a populated 72 would not discriminate the compensación election"
        )


def test_the_channel_discriminates_rather_than_reporting_one_reading() -> None:
    """Across the four specimens the channel yields BOTH readings, not one.

    A channel that reported compensación for everything would satisfy every
    per-specimen assertion above that concerns compensación. This asserts the
    partition is non-trivial on both sides, which is the property that makes the
    channel usable at all.
    """
    populated, empty = [], []
    for specimen in _SPECIMENS:
        flat = _flat_text(specimen)
        (populated if re.search(_CASILLA_72_AMOUNT, flat) else empty).append(specimen)

    assert populated, "no specimen carries a populated casilla 72"
    assert empty, "every specimen carries a populated casilla 72, so the signal cannot discriminate"


def test_negativa_has_its_own_marker_position_distinct_from_compensacion() -> None:
    """A negativa filing is addressable separately from a compensación filing.

    ``Sin actividad (4)`` is printed as its own section, at a different position
    from ``Compensación (6)``, so the two elections do not share a slot. That is
    what keeps them distinguishable through this channel where the justificante
    receipt collapses them: on the receipt both present with neither amount.

    LIMIT, stated rather than implied: none of the four bundled specimens filed a
    negativa, so this asserts the channel SHAPE carries a distinct position for
    it, not that a ticked sin-actividad box has been observed and read. Proving
    the value requires an AEAT specimen of a sin-actividad filing, which the tree
    does not bundle.
    """
    flat = _flat_text(_SPECIMENS[0])

    sin_actividad = re.search(_PREPRINTED_SECTIONS["sin actividad"], flat)
    compensacion = re.search(_PREPRINTED_SECTIONS["compensacion"], flat)
    assert sin_actividad is not None and compensacion is not None
    assert sin_actividad.start() != compensacion.start(), (
        "sin actividad and compensación resolve to the same position, so the render "
        "does not separate a negativa filing from a compensación filing"
    )


def test_the_justificante_record_cannot_carry_the_disposition() -> None:
    """The receipt's parsed shape has no field the disposition could occupy.

    Asserted structurally against the model rather than by reading a fixture, so
    it stays true for every receipt rather than for the ones bundled today. If a
    disposition field is ever added, this test fails and the channel verdict above
    must be revisited rather than silently outliving its evidence.
    """
    from .....domain.justificante import Justificante

    fields = set(Justificante.model_fields)

    assert {"total_a_ingresar", "total_a_devolver"} <= fields
    disposition_like = {name for name in fields if "disposition" in name or "tipo" in name}
    assert disposition_like == set(), (
        f"the justificante record now carries {disposition_like}, so the receipt may "
        "have become a disposition channel and this suite's verdict is stale"
    )
