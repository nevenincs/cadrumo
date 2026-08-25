"""Previous-filing target-relative expanding-span selector grammar.

Covers the Modelo 130 casilla-05 carry primitive added by the
modelo-130-pagos-fraccionados-carry plan (P01): a target-relative
prior-quarter expanding span that emits every same-ejercicio quarter
strictly preceding the target into the existing multi-anchor sum path,
plus the per-anchor positive-part aggregation the casilla-05 identity
requires.

The expected anchor sets are enumerated by hand per target quarter (an
INDEPENDENT enumeration), never derived from the span function under test,
per aeat-quality-gates.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from .....core import CasillaId, validated_casilla_id
from .....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from .. import (
    CasillaObservation,
    DataBindingDefinition,
    ModeloRevision,
    RegistryModeloObservation,
    previous_filing_observation_requirements,
    resolve_previous_filing_binding_values,
    same_ejercicio_prior_quarter_anchors,
    source_presence_gaps,
)
from .._bindings_previous_filing import PreviousModeloSelector, is_direct_previous_filing_binding
from ..errors import RegistryValidationError
from .._schema import BindingSelectorMap, PeriodSelector

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REFERENCE_LEGAL_ID = "rd-439-2007:art-110"
_REFERENCE_SOURCE_ID = "aeat-modelo-130-instructions"
_M130_PAGO_FRACCIONADO_CASILLA: CasillaId = validated_casilla_id(
    "07",
    surface="_M130_PAGO_FRACCIONADO_CASILLA",
)
_M130_MINORACION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_MINORACION_CASILLA")


def _revision(*, bindings: tuple[DataBindingDefinition, ...]) -> ModeloRevision:
    return ModeloRevision(
        id="test-previous-filing-revision",
        localization_key="test.schema.revision.test-previous-filing.label",
        valid_from=date(2025, 1, 1),
        period_selector=PeriodSelector(years=(2025,), periods=("1T", "2T", "3T", "4T")),
        legal_refs=(_REFERENCE_LEGAL_ID,),
        source_refs=(_REFERENCE_SOURCE_ID,),
        bindings=bindings,
    )


def _span_binding(
    *,
    source_casilla_ids: tuple[CasillaId, ...],
    selector: dict[str, object] | None = None,
    aggregation: BindingAggregation | None = None,
) -> DataBindingDefinition:
    selector_payload = cast(
        BindingSelectorMap,
        selector
        or {
            "source_modelo": "130",
            "source_casilla_ids": tuple(source_casilla_ids),
            "prior_quarter_expanding_span": True,
            "max_year_delta": 0,
        },
    )
    return DataBindingDefinition(
        id="modelo-130-test-span-binding",
        source=BindingSourceKind.PREVIOUS_FILING,
        selector=selector_payload,
        aggregation=aggregation or BindingAggregation(op=BindingAggregationOp.SUM),
        legal_refs=(_REFERENCE_LEGAL_ID,),
        source_refs=(_REFERENCE_SOURCE_ID,),
    )


def _source_observation(
    period: str,
    *casilla_values: tuple[CasillaId, Decimal],
    year: int = 2025,
) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="130",
        filing_year=year,
        period=period,
        observations=tuple(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                legal_refs=(_REFERENCE_LEGAL_ID,),
                source_refs=(_REFERENCE_SOURCE_ID,),
            )
            for casilla_id, value in casilla_values
        ),
    )


def test_required_source_casillas_must_be_unique_and_canonical_candidates() -> None:
    with pytest.raises(ValidationError, match="required_source_casilla_ids entries must be unique"):
        PreviousModeloSelector(
            source_modelo="100",
            period="0A",
            source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA, _M130_MINORACION_CASILLA),
            required_source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA, _M130_PAGO_FRACCIONADO_CASILLA),
        )

    outside = validated_casilla_id("99", surface="test required source presence")
    with pytest.raises(ValidationError, match="must be a subset of source casillas"):
        PreviousModeloSelector(
            source_modelo="100",
            period="0A",
            source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA, _M130_MINORACION_CASILLA),
            required_source_casilla_ids=(outside,),
        )


def test_omitted_required_source_policy_keeps_all_candidates_mandatory() -> None:
    selector = PreviousModeloSelector(
        source_modelo="100",
        period="0A",
        source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA, _M130_MINORACION_CASILLA),
    )

    assert selector.required_source_casilla_ids is None


def test_coalesced_optional_bindings_preserve_each_registry_presence_group() -> None:
    first = _span_binding(
        source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA,),
        selector={
            "source_modelo": "130",
            "source_casilla_ids": (_M130_PAGO_FRACCIONADO_CASILLA,),
            "required_source_casilla_ids": (),
            "period": "1T",
        },
    )
    second = _span_binding(
        source_casilla_ids=(_M130_MINORACION_CASILLA,),
        selector={
            "source_modelo": "130",
            "source_casilla_ids": (_M130_MINORACION_CASILLA,),
            "required_source_casilla_ids": (),
            "period": "1T",
        },
    ).model_copy(update={"id": "modelo-130-test-second-optional-binding"})

    requirement = previous_filing_observation_requirements(
        _revision(bindings=(first, second)),
        filing_year=2025,
        period="2T",
    )[0]

    assert requirement.required_source_casilla_ids == ()
    assert requirement.source_presence_groups == (
        (_M130_PAGO_FRACCIONADO_CASILLA,),
        (_M130_MINORACION_CASILLA,),
    )
    missing_required, missing_groups = source_presence_gaps(
        required_source_casilla_ids=requirement.enforced_source_casilla_ids,
        source_presence_groups=requirement.source_presence_groups,
        observed_source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA,),
    )
    assert missing_required == ()
    assert missing_groups == ((_M130_MINORACION_CASILLA,),)
    assert source_presence_gaps(
        required_source_casilla_ids=requirement.enforced_source_casilla_ids,
        source_presence_groups=requirement.source_presence_groups,
        observed_source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA, _M130_MINORACION_CASILLA),
    ) == ((), ())


def _resolve_binding(
    binding: DataBindingDefinition,
    observations: tuple[RegistryModeloObservation, ...],
    *,
    target_period: str,
) -> Decimal:
    resolved = resolve_previous_filing_binding_values(
        _revision(bindings=(binding,)),
        observations,
        filing_year=2025,
        period=target_period,
    )
    return resolved[binding.id]


# Independently enumerated expected anchor sets (hand-written per target
# quarter from the AEAT "trimestres anteriores del mismo ejercicio" rule),
# NOT derived from the span function under test.
_EXPECTED_SPAN_ANCHORS: dict[str, tuple[tuple[int, str], ...]] = {
    "1T": (),
    "2T": ((0, "1T"),),
    "3T": ((0, "1T"), (0, "2T")),
    "4T": ((0, "1T"), (0, "2T"), (0, "3T")),
}


@pytest.mark.parametrize("target_period", ["1T", "2T", "3T", "4T"])
def test_same_ejercicio_prior_quarter_sequence_matches_independent_aeat_anchors(target_period: str) -> None:
    """The registry sequence is the hand-enumerated same-ejercicio span.

    The expected anchors are declared above from the Modelo 130
    ``trimestres anteriores del mismo ejercicio`` rule, not produced by the
    offset primitive under test.
    """
    assert same_ejercicio_prior_quarter_anchors(target_period) == _EXPECTED_SPAN_ANCHORS[target_period]


@pytest.mark.parametrize("target_period", ["1T", "2T", "3T", "4T"])
def test_expanding_span_emits_independently_enumerated_anchor_set(target_period: str) -> None:
    revision = _revision(bindings=(_span_binding(source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA,)),))
    requirements = previous_filing_observation_requirements(revision, filing_year=2025, period=target_period)
    assert (
        tuple((item.filing_year - 2025, item.periods[0]) for item in requirements)
        == _EXPECTED_SPAN_ANCHORS[target_period]
    )


def test_expanding_span_first_quarter_is_empty() -> None:
    """1T has no same-ejercicio prior quarter; the span is empty (absent-by-design)."""
    revision = _revision(bindings=(_span_binding(source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA,)),))
    assert previous_filing_observation_requirements(revision, filing_year=2025, period="1T") == ()


def test_expanding_span_classified_direct_previous_filing_binding() -> None:
    """The span carry stays a DIRECT previous_filing binding (source_casilla_ids anchor).

    The relation-source collision gate (validate_slot_source_hygiene) and the
    requirement-derivation path both route through this predicate; the span mode
    must classify direct so it needs no carve-out.
    """
    binding = _span_binding(source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA,))
    requirements = previous_filing_observation_requirements(
        _revision(bindings=(binding,)),
        filing_year=2025,
        period="2T",
    )
    assert [(item.source_modelo, item.periods, item.source_casilla_ids) for item in requirements] == [
        ("130", ("1T",), (_M130_PAGO_FRACCIONADO_CASILLA,))
    ]
    assert requirements[0].legal_refs == (_REFERENCE_LEGAL_ID,)
    assert requirements[0].source_refs == (_REFERENCE_SOURCE_ID,)


def test_previous_filing_requirement_rejects_ungrounded_binding_snapshot() -> None:
    binding = _span_binding(source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA,)).model_copy(
        update={"legal_refs": (), "source_refs": ()},
    )

    with pytest.raises(ValidationError) as exc_info:
        previous_filing_observation_requirements(
            _revision(bindings=(binding,)),
            filing_year=2025,
            period="2T",
        )

    error_fields = {tuple(error["loc"]) for error in exc_info.value.errors()}
    assert ("legal_refs",) in error_fields
    assert ("source_refs",) in error_fields


def test_expanding_span_mutually_exclusive_with_offset() -> None:
    with pytest.raises(ValidationError, match="mutually exclusive"):
        _span_binding(
            source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA,),
            selector={
                "source_modelo": "130",
                "source_casilla_ids": (_M130_PAGO_FRACCIONADO_CASILLA,),
                "prior_quarter_expanding_span": True,
                "source_period_offset_from_target": -1,
            },
        )


def test_expanding_span_mutually_exclusive_with_source_periods() -> None:
    with pytest.raises(ValidationError, match="mutually exclusive"):
        _span_binding(
            source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA,),
            selector={
                "source_modelo": "130",
                "source_casilla_ids": (_M130_PAGO_FRACCIONADO_CASILLA,),
                "prior_quarter_expanding_span": True,
                "source_periods": ("1T", "2T"),
            },
        )


def test_expanding_span_rejects_non_quarterly_target() -> None:
    with pytest.raises(RegistryValidationError, match="only quarterly codes"):
        previous_filing_observation_requirements(
            _revision(bindings=(_span_binding(source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA,)),)),
            filing_year=2025,
            period="0A",
        )


def _prior_pagos_binding() -> DataBindingDefinition:
    return DataBindingDefinition(
        id="modelo-130-pagos-fraccionados-anteriores",
        source=BindingSourceKind.PREVIOUS_FILING,
        selector={
            "source_modelo": "130",
            "source_casilla_ids": (_M130_PAGO_FRACCIONADO_CASILLA, _M130_MINORACION_CASILLA),
            "prior_quarter_expanding_span": True,
            "max_year_delta": 0,
        },
        aggregation=BindingAggregation(op=BindingAggregationOp.PRIOR_PAGOS_FRACCIONADOS),
        legal_refs=(_REFERENCE_LEGAL_ID,),
        source_refs=(_REFERENCE_SOURCE_ID,),
    )


def test_prior_pagos_fraccionados_op_computes_positive_07_minus_16() -> None:
    """casilla 05 = Σ max(0, 07_q) − Σ 16_q from per-anchor [07_q, 16_q] pairs.

    Three prior quarters (1T, 2T, 3T) for a 4T target. The expected value is
    computed in-test from the per-quarter inputs via the verbatim AEAT identity
    (positive-part per quarter, then minus the sum of casilla 16) - a different
    code path than the op under test, and the fixture is chosen so the identity
    (480) does NOT equal the raw-07 sum (450), so a binding that skipped the
    per-quarter max-0 OR dropped the minus-16 term fails loudly rather than
    coinciding.
    """
    binding = _prior_pagos_binding()
    # Per-quarter (07, 16) pairs. 2T is a loss (negative 07 -> contributes 0).
    quarters = (
        (Decimal("300"), Decimal("40")),
        (Decimal("-100"), Decimal("0")),
        (Decimal("250"), Decimal("30")),
    )
    expected = sum((max(Decimal("0"), c07) for c07, _c16 in quarters), Decimal("0")) - sum(
        (c16 for _c07, c16 in quarters), Decimal("0")
    )
    raw_07_sum = sum((c07 for c07, _c16 in quarters), Decimal("0"))
    assert expected != raw_07_sum, "fixture must make the identity differ from a raw-07 sum"

    result = _resolve_binding(
        binding,
        tuple(
            _source_observation(
                period,
                (_M130_PAGO_FRACCIONADO_CASILLA, c07),
                (_M130_MINORACION_CASILLA, c16),
            )
            for period, (c07, c16) in zip(("1T", "2T", "3T"), quarters, strict=True)
        ),
        target_period="4T",
    )
    assert result == expected


def test_prior_pagos_fraccionados_op_negative_07_contributes_zero_not_value() -> None:
    """Anti-regression: a single negative prior 07 must contribute 0, not its value.

    One prior quarter, 07=-500, 16=0. The identity gives max(0,-500) − 0 = 0.
    A raw sum would give -500, so a non-zero (negative) result fails loudly.
    """
    binding = _prior_pagos_binding()
    result = _resolve_binding(
        binding,
        (
            _source_observation(
                "1T",
                (_M130_PAGO_FRACCIONADO_CASILLA, Decimal("-500")),
                (_M130_MINORACION_CASILLA, Decimal("0")),
            ),
        ),
        target_period="2T",
    )
    assert result == Decimal("0")


def test_prior_pagos_fraccionados_op_subtracts_nonzero_minoracion() -> None:
    """Anti-regression: a non-zero prior 16 is subtracted (minoración never dropped).

    One prior quarter, 07=+700, 16=120. Identity: 700 − 120 = 580.
    """
    binding = _prior_pagos_binding()
    result = _resolve_binding(
        binding,
        (
            _source_observation(
                "1T",
                (_M130_PAGO_FRACCIONADO_CASILLA, Decimal("700")),
                (_M130_MINORACION_CASILLA, Decimal("120")),
            ),
        ),
        target_period="2T",
    )
    assert result == Decimal("580")


def test_prior_pagos_fraccionados_op_requires_two_source_casilla_ids() -> None:
    with pytest.raises(RegistryValidationError, match="requires exactly two source casillas"):
        binding = _span_binding(
            source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA,),
            aggregation=BindingAggregation(op=BindingAggregationOp.PRIOR_PAGOS_FRACCIONADOS),
        )
        _resolve_binding(
            binding,
            (
                _source_observation(
                    "1T",
                    (_M130_PAGO_FRACCIONADO_CASILLA, Decimal("100")),
                ),
            ),
            target_period="2T",
        )


def test_is_direct_previous_filing_binding_true_for_plural_source_casilla_ids() -> None:
    """The legitimate path: a real plural-casilla direct selector resolves True."""
    binding = _span_binding(source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA,))
    assert is_direct_previous_filing_binding(binding)


def test_is_direct_previous_filing_binding_true_for_scalar_casilla_with_period() -> None:
    """The legitimate path: a real scalar-casilla-plus-period selector resolves True."""
    binding = DataBindingDefinition(
        id="modelo-130-test-scalar-period-binding",
        source=BindingSourceKind.PREVIOUS_FILING,
        selector=cast(
            BindingSelectorMap,
            {
                "source_modelo": "130",
                "source_casilla_id": _M130_PAGO_FRACCIONADO_CASILLA,
                "period": "1T",
            },
        ),
        aggregation=BindingAggregation(op=BindingAggregationOp.COPY),
        legal_refs=(_REFERENCE_LEGAL_ID,),
        source_refs=(_REFERENCE_SOURCE_ID,),
    )
    assert is_direct_previous_filing_binding(binding)


def test_previous_modelo_selector_permits_a_period_less_scalar_casilla_and_the_predicate_is_the_only_guard() -> None:
    """PIN THE COMPENSATION. Do not remove this predicate's scalar branch as
    apparently-redundant "the model already validates the selector" cleanup --
    this test is what would catch that regression.

    ``PreviousModeloSelector``'s own build-time invariant
    (``_missing_period_selector_failure``) checks ``bool(source_casilla_ids)``
    -- the PLURAL field -- but never references the scalar
    ``source_casilla_id`` sibling. So a selector declaring a scalar casilla
    with NO period-selection axis (no ``period``, ``source_periods``,
    ``source_period_offset_from_target``, or ``prior_quarter_expanding_span``)
    constructs CLEANLY -- the model does not enforce that this shape needs a
    period anchor, and this is asserted directly below, not inferred.

    ``is_direct_previous_filing_binding`` is the ONLY thing that still
    catches it, by independently re-checking the same condition for the
    scalar case and returning ``False``.

    This is deliberate, not an unfinished fix: closing the gap in the model
    would narrow what the predicate's ``False`` return means, conflating
    "lacking a period anchor" with "relation-targeted" (no source casilla at
    all) -- a distinction its four call sites currently rely on. See the
    campaign finding classifying this as a compensated latent asymmetry, not
    a live defect.
    """
    selector = PreviousModeloSelector(source_modelo="130", source_casilla_id=_M130_PAGO_FRACCIONADO_CASILLA)
    assert selector.source_casilla_id == _M130_PAGO_FRACCIONADO_CASILLA
    assert selector.period is None
    assert not selector.source_periods
    assert selector.source_period_offset_from_target is None
    assert not selector.prior_quarter_expanding_span

    binding = DataBindingDefinition(
        id="modelo-130-test-unanchored-binding",
        source=BindingSourceKind.PREVIOUS_FILING,
        selector=cast(
            BindingSelectorMap,
            {"source_modelo": "130", "source_casilla_id": _M130_PAGO_FRACCIONADO_CASILLA},
        ),
        aggregation=BindingAggregation(op=BindingAggregationOp.COPY),
        legal_refs=(_REFERENCE_LEGAL_ID,),
        source_refs=(_REFERENCE_SOURCE_ID,),
    )
    assert not is_direct_previous_filing_binding(binding)


def test_a_misspelled_previous_filing_selector_key_is_refused_not_silently_treated_as_indirect() -> None:
    """The bite proof: a drifted selector must fail loud, never silently
    register a direct binding as non-direct.

    Before the fix, ``is_direct_previous_filing_binding`` read
    ``_selector_as_dict(binding).get("source_casilla_id")`` /
    ``.get("source_casilla_ids")`` by string literal. Every real caller is
    pre-filtered to ``source == BindingSourceKind.PREVIOUS_FILING``
    (``previous_filing_observation_requirements``,
    ``_aggregate_previous_filing_binding``,
    ``_validate_relation_sources.py``'s slot-source gate), so a field rename
    on ``PreviousModeloSelector`` would keep passing construction-time
    validation (the NEW name) while this string-literal read silently,
    permanently returned False for a binding that IS direct -- and that
    predicate backs a registry-build REFUSAL (a ``previous_filing`` binding
    without a direct selector must declare ``relation_prefill`` instead), so
    a wrongly-False result makes that gate go quiet rather than fire.
    ``model_construct`` bypasses the constructor's own validator to stand in
    for that drift, and the fixed read -- through ``_previous_filing_selector``,
    the exact helper the direct-True paths above already resolve through --
    fails loud instead via that helper's own ``RegistryValidationError``.
    Asserted on that helper's own cause-unique message, not a bare
    "an exception was raised", so a coincidentally-matching different
    refusal upstream cannot pass this proof for the wrong reason.
    """
    drifted = DataBindingDefinition.model_construct(
        id="modelo-130-test-drift-binding",
        source=BindingSourceKind.PREVIOUS_FILING,
        selector={
            "source_modelo": "130",
            "source_casill_id": _M130_PAGO_FRACCIONADO_CASILLA,  # deliberate typo of source_casilla_id
            "period": "1T",
        },
        aggregation=BindingAggregation(op=BindingAggregationOp.COPY),
        legal_refs=(_REFERENCE_LEGAL_ID,),
        source_refs=(_REFERENCE_SOURCE_ID,),
    )

    with pytest.raises(RegistryValidationError, match="malformed previous-filing selector"):
        is_direct_previous_filing_binding(drifted)
