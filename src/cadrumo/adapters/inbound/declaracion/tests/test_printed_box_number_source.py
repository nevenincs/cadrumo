"""The printed box number is read from ``form_number``, never from ``number``.

Two places in the parser need the number a taxpayer sees printed on the page:
the blank-box guard, which refuses a captured token identical to it, and the
``numeric_casilla`` strategy, which anchors on it at line start. Both read it
from the same registry field, and both once read the wrong one.

``number`` is reviewed AEAT record-design metadata. It answers a different
question and coincides with the printed number only when the casilla id is
itself numeric -- so reading it works by accident across most of the registry and
fails silently wherever a casilla is named semantically. Modelo 390's totals
carry their own id string there; Modelo 190's resumen summaries carry
fichero-BOE positional ranges such as ``145-160``, which is correct for what that
field means. The separate ``form_number`` is the printed form's number, and the
in-tree precedent predates this: Modelo 303's casilla 46 has carried
``form_number = "46"`` alongside a semantic ``number`` all along.

The two consumers fail differently when the number is wrong, which is why they
degrade differently and why this module tests both:

- The guard loses a safety net. A blank box then returns its own printed number
  as a monetary value, so the failure is a fabricated amount.
- ``numeric_casilla`` loses the target entirely. An anchor that can never match
  drops the casilla out of every extraction, so the failure is a silent absence
  that only the coverage floor could catch.

Neither is currently reachable in production: every ``numeric_casilla`` target in
the registry happens to carry a numeric ``number``. That is precisely the
accident that hid the same defect in the guard until a real render exposed it,
so the contract is pinned here rather than left to hold by luck. The subjects
below are real casillas from real revisions, chosen because they are the shapes
the accident does not cover.

See Also:
    :mod:`~adapters.inbound.declaracion.tests.test_parser_blank_box_never_yields_box_number`
        The same contract on the guard, including its blank-box behaviour.
"""

from __future__ import annotations

import pytest

from .....core import validated_casilla_id
from .....domain.calculations.registry.authority import bundled_authority
from .....domain.calculations.registry.schema_extraction import ExtractionProfileDefinition, ExtractionTargetDefinition
from .._parser import _numeric_casilla_anchors
from ..errors import DeclaracionParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _revision(modelo: str, filing_year: int, period: str):
    return bundled_authority().snapshot(modelo, filing_year=filing_year, period=period).revision


def _numeric_profile(casilla_id: str) -> ExtractionProfileDefinition:
    """A minimal profile whose single target anchors on a printed box number."""
    return ExtractionProfileDefinition(
        id="probe-numeric-casilla-profile",
        surface="declaracion_pdf",
        artefact_kind="declaration_pdf",
        accepted_artefact_kinds=("declaration_pdf",),
        parser="cadrumo.adapters.inbound.declaracion.parse_declaracion",
        target_casillas=(
            ExtractionTargetDefinition(
                casilla_id=validated_casilla_id(casilla_id, surface="printed-box-number source probe"),
                match_strategy="numeric_casilla",
                value_kind="amount",
            ),
        ),
        confidence="strict",
        min_coverage="1",
        failure_semantics="fail_hard",
        legal_refs=("ley-58-2003:art-93",),
        source_refs=("aeat-dr-390-2025",),
    )


@pytest.mark.parametrize(
    "modelo,filing_year,period,casilla_id,printed,record_design",
    [
        ("390", 2021, "0A", "iva.anual.cuota-deducible-total", "64", "iva.anual.cuota-deducible-total"),
        ("390", 2021, "0A", "iva.anual.resultado-regimen-general", "65", "iva.anual.resultado-regimen-general"),
        ("190", 2024, "0A", "decl.percepciones-total", "02", "145-160"),
        ("190", 2024, "0A", "decl.retenciones-total", "03", "161-175"),
    ],
    ids=[
        "m390-box-64-id-string-in-number",
        "m390-box-65-id-string-in-number",
        "m190-box-02-positional-range-in-number",
        "m190-box-03-positional-range-in-number",
    ],
)
def test_numeric_anchor_is_the_printed_number_not_the_record_design_field(
    modelo: str,
    filing_year: int,
    period: str,
    casilla_id: str,
    printed: str,
    record_design: str,
) -> None:
    """A semantically-named casilla anchors on its printed number.

    Fails on the pre-fix parser, which returned ``record_design`` -- an id string
    for Modelo 390 and a fichero-BOE positional range for Modelo 190. Neither can
    ever appear at the start of a printed line, so each target would have dropped
    out of every extraction without raising anything.

    The expected values are the numbers the bundled AEAT renders print, not
    values read back from the casillas under test: the annual-summary render
    prints ``Suma de deducciones (...) ... 64`` and ``Resultado regimen general
    (4 7 - 64) ... 65``, and the Modelo 190 resumen prints ``Importe total de las
    percepciones relacionadas ... 02`` and ``... las retenciones e ingresos a
    cuenta relacionados ... 03``.
    """
    revision = _revision(modelo, filing_year, period)
    profile = _numeric_profile(casilla_id)

    anchors = {str(k): v for k, v in _numeric_casilla_anchors(profile, revision).items()}

    assert anchors[casilla_id] == printed, (
        f"M{modelo} {casilla_id!r}: numeric_casilla anchors on {anchors[casilla_id]!r}, but the "
        f"AEAT render prints {printed!r}. Anchoring on {record_design!r} matches no line, so this "
        f"target would be absent from every extraction without any error being raised"
    )


def test_a_casilla_with_no_printed_number_is_refused_rather_than_mis_anchored() -> None:
    """A target that cannot be addressed refuses, instead of anchoring on anything.

    The alternative -- falling back to ``number`` regardless -- is what produced
    the defect above, and silently returning no anchor would leave the target
    missing for a reason no message names. Modelo 190's perceptor count carries a
    positional range in ``number`` and is the subject here with its
    ``form_number`` withheld, which is the state every affected casilla was in
    before that field was populated.
    """
    revision = _revision("190", 2024, "0A")
    profile = _numeric_profile("decl.total-percepciones")

    stripped = revision.model_copy(
        update={
            "casillas": tuple(
                c.model_copy(update={"form_number": None}) if str(c.id) == "decl.total-percepciones" else c
                for c in revision.casillas
            )
        }
    )

    with pytest.raises(DeclaracionParseError) as excinfo:
        _numeric_casilla_anchors(profile, stripped)

    message = str(excinfo.value)
    assert "136-144" in message, (
        f"the refusal must name the record-design value it declined to anchor on, got: {message}"
    )
