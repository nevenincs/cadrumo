"""Real-behaviour anti-tautology tests for ``CasillaDefinition.internal_only``.

The ``internal_only`` flag declares a casilla as an app-internal computed
ceiling or intermediate that intentionally has no presence in the
AEAT-published Diseño de Registros (e.g. the LIS art. 26.1 BIN compensation
ceiling materialised so the BLOCKING verification predicate can bound the
operator-elective applied amount). The schema validator MUST refuse two
incoherent shapes at registry load: an internal-only casilla that also
declares ``export_refs`` (it cannot both be app-internal and exported to a
fichero record AEAT does not publish), and an internal-only casilla whose
``input_kind`` is not ``COMPUTED`` (an internal ceiling has no legitimate
computation surface unless formula-derived).

These tests exercise the validator contract directly, not a hand-computed
calculation expectation — the ``aeat-quality-gates`` rule is
satisfied because the assertions are about a validation refusal, not about
a Decimal output produced from a formula-under-test.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_INTERNAL_ONLY_LEGAL_ID = "ley-27-2014:art-26"
_INTERNAL_ONLY_SOURCE_ID = "aeat-dr-200-2025"
_INTERNAL_ONLY_EXPORT_FIELD_ID = "modelo-200-2024:DP200014:00552"
_INTERNAL_ONLY_FORMULA_ID = "modelo-200-2024-bin-aplicada-maxima"


def test_internal_only_casilla_rejects_non_empty_export_refs() -> None:
    """A casilla flagged internal_only=True with export_refs raises at load.

    The two shapes are mutually incoherent: an app-internal casilla
    cannot also be exported to a fichero record AEAT does not publish.
    The validator MUST raise ``RegistryValidationError`` so the
    mis-declaration cannot reach the runtime.
    """
    with pytest.raises(ValidationError, match="internal_only"):
        CasillaDefinition(
            id="DP200014:bin-aplicada-maxima",
            number="DP200014:bin-aplicada-maxima",
            segmento="DP200014",
            localization_keys=("test.schema.casilla.label",),
            section=("liquidacion_iii", "base_imponible"),
            input_kind=InputKind.COMPUTED,
            formula=_INTERNAL_ONLY_FORMULA_ID,
            export_refs=(_INTERNAL_ONLY_EXPORT_FIELD_ID,),
            internal_only=True,
            legal_refs=(_INTERNAL_ONLY_LEGAL_ID,),
            source_refs=(_INTERNAL_ONLY_SOURCE_ID,),
        )


def test_internal_only_casilla_rejects_non_computed_input_kind() -> None:
    """A casilla flagged internal_only=True with input_kind!=COMPUTED raises at load.

    An internal ceiling must be formula-derived: a MANUAL or BOUND
    internal-only casilla has no legitimate computation surface (the
    regulatory ceiling is computed from real casillas; an operator does
    not type it and a binding does not source it from another modelo).
    The validator MUST raise ``RegistryValidationError``.
    """
    with pytest.raises(ValidationError, match="internal_only"):
        CasillaDefinition(
            id="DP200014:bin-aplicada-maxima",
            number="DP200014:bin-aplicada-maxima",
            segmento="DP200014",
            localization_keys=("test.schema.casilla.label",),
            section=("liquidacion_iii", "base_imponible"),
            input_kind=InputKind.MANUAL,
            internal_only=True,
            legal_refs=(_INTERNAL_ONLY_LEGAL_ID,),
            source_refs=(_INTERNAL_ONLY_SOURCE_ID,),
        )


def test_internal_only_casilla_accepted_when_computed_and_no_exports() -> None:
    """The coherent shape (COMPUTED + empty export_refs) loads cleanly.

    Bookends the two refusal tests: prove the validator is not a blanket
    refusal of internal_only=True. A formula-derived ceiling with no
    export_refs is the legitimate shape declared by
    ``DP200014:bin-aplicada-maxima`` and any future internal-only casilla.
    """
    casilla = CasillaDefinition(
        id="DP200014:bin-aplicada-maxima",
        number="DP200014:bin-aplicada-maxima",
        segmento="DP200014",
        localization_keys=("test.schema.casilla.label",),
        section=("liquidacion_iii", "base_imponible"),
        input_kind=InputKind.COMPUTED,
        formula=_INTERNAL_ONLY_FORMULA_ID,
        internal_only=True,
        legal_refs=(_INTERNAL_ONLY_LEGAL_ID,),
        source_refs=(_INTERNAL_ONLY_SOURCE_ID,),
    )
    assert casilla.internal_only is True
    assert casilla.export_refs == ()
    assert casilla.input_kind == InputKind.COMPUTED
