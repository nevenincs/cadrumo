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

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingAggregation, BindingAggregationOp
from .....core.casilla_id import CasillaId, validated_casilla_id
from ..binding_temporal import (
    BindingTemporalKind,
    PriorQuarterExpandingSpan,
    SameFilingYearPeriods,
    SameTargetContext,
    temporal_selector_from_previous_modelo_fields,
)
from ..binding_value_contract import (
    BindingDataType,
    BindingValueChannel,
    BindingValueContract,
)
from ..bindings import CasillaObservation, RegistryModeloObservation
from ..bindings_previous_filing import (
    PreviousFilingProvider,
    is_direct_previous_filing_binding,
    previous_filing_observation_requirements,
    resolve_previous_filing_binding_values,
)
from ..errors import RegistryValidationError
from ..period_offset_math import same_ejercicio_prior_quarter_anchors
from ..relations import source_presence_gaps
from ..schema import BindingDefinition, ModeloRevision
from ..schema_references import PeriodSelector

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REFERENCE_LEGAL_ID = "rd-439-2007:art-110"
_REFERENCE_SOURCE_ID = "aeat-modelo-130-instructions"
_M130_PAGO_FRACCIONADO_CASILLA: CasillaId = validated_casilla_id(
    "07",
    surface="_M130_PAGO_FRACCIONADO_CASILLA",
)
_M130_MINORACION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_MINORACION_CASILLA")
_MONEY_VALUE = BindingValueContract(data_type=BindingDataType.MONEY, channel=BindingValueChannel.DECIMAL)
# ``kind`` is stated explicitly on every temporal member, exactly as the authored
# corpus states it: the provider round-trip that ``is_direct_previous_filing_binding``
# performs dumps only the fields a declaration actually set, so a discriminator left
# on its default would not survive back into the union.
_PRIOR_QUARTER_SPAN = PriorQuarterExpandingSpan(kind=BindingTemporalKind.PRIOR_QUARTER_EXPANDING_SPAN)


def _same_year_periods(*periods: str) -> SameFilingYearPeriods:
    return SameFilingYearPeriods(kind=BindingTemporalKind.SAME_FILING_YEAR_PERIODS, source_periods=periods)


def _revision(*, bindings: tuple[BindingDefinition, ...]) -> ModeloRevision:
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
    provider: PreviousFilingProvider | None = None,
    aggregation: BindingAggregation | None = None,
) -> BindingDefinition:
    return BindingDefinition(
        id="modelo-130-test-span-binding",
        provider=provider
        or PreviousFilingProvider(
            source_modelo="130",
            source_casilla_ids=tuple(source_casilla_ids),
            temporal=_PRIOR_QUARTER_SPAN,
        ),
        value=_MONEY_VALUE,
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
        PreviousFilingProvider(
            source_modelo="100",
            temporal=_same_year_periods("0A"),
            source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA, _M130_MINORACION_CASILLA),
            required_source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA, _M130_PAGO_FRACCIONADO_CASILLA),
        )

    outside = validated_casilla_id("99", surface="test required source presence")
    with pytest.raises(ValidationError, match="must be a subset of source casillas"):
        PreviousFilingProvider(
            source_modelo="100",
            temporal=_same_year_periods("0A"),
            source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA, _M130_MINORACION_CASILLA),
            required_source_casilla_ids=(outside,),
        )


def test_omitted_required_source_policy_keeps_all_candidates_mandatory() -> None:
    selector = PreviousFilingProvider(
        source_modelo="100",
        temporal=_same_year_periods("0A"),
        source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA, _M130_MINORACION_CASILLA),
    )

    assert selector.required_source_casilla_ids is None


def test_coalesced_optional_bindings_preserve_each_registry_presence_group() -> None:
    first = _span_binding(
        source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA,),
        provider=PreviousFilingProvider(
            source_modelo="130",
            source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA,),
            required_source_casilla_ids=(),
            temporal=_same_year_periods("1T"),
        ),
    )
    second = _span_binding(
        source_casilla_ids=(_M130_MINORACION_CASILLA,),
        provider=PreviousFilingProvider(
            source_modelo="130",
            source_casilla_ids=(_M130_MINORACION_CASILLA,),
            required_source_casilla_ids=(),
            temporal=_same_year_periods("1T"),
        ),
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
    binding: BindingDefinition,
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
    with pytest.raises(RegistryValidationError, match="mutually exclusive"):
        temporal_selector_from_previous_modelo_fields(
            prior_quarter_expanding_span=True,
            source_period_offset_from_target=-1,
        )


def test_expanding_span_mutually_exclusive_with_source_periods() -> None:
    with pytest.raises(RegistryValidationError, match="mutually exclusive"):
        temporal_selector_from_previous_modelo_fields(
            prior_quarter_expanding_span=True,
            source_periods=("1T", "2T"),
        )


def test_expanding_span_rejects_non_quarterly_target() -> None:
    with pytest.raises(RegistryValidationError, match="only quarterly codes"):
        previous_filing_observation_requirements(
            _revision(bindings=(_span_binding(source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA,)),)),
            filing_year=2025,
            period="0A",
        )


def _prior_pagos_binding() -> BindingDefinition:
    return BindingDefinition(
        id="modelo-130-pagos-fraccionados-anteriores",
        provider=PreviousFilingProvider(
            source_modelo="130",
            source_casilla_ids=(_M130_PAGO_FRACCIONADO_CASILLA, _M130_MINORACION_CASILLA),
            temporal=_PRIOR_QUARTER_SPAN,
        ),
        value=_MONEY_VALUE,
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
    binding = BindingDefinition(
        id="modelo-130-test-scalar-period-binding",
        provider=PreviousFilingProvider(
            source_modelo="130",
            source_casilla_id=_M130_PAGO_FRACCIONADO_CASILLA,
            temporal=_same_year_periods("1T"),
        ),
        value=_MONEY_VALUE,
        aggregation=BindingAggregation(op=BindingAggregationOp.COPY),
        legal_refs=(_REFERENCE_LEGAL_ID,),
        source_refs=(_REFERENCE_SOURCE_ID,),
    )
    assert is_direct_previous_filing_binding(binding)


def test_unanchored_scalar_casilla_is_now_refused_by_the_model_not_only_by_the_predicate() -> None:
    """The former compensation is gone: the model itself refuses the shape.

    A scalar ``source_casilla_id`` with no source window used to construct
    cleanly -- the build-time invariant checked only the PLURAL
    ``source_casilla_ids`` -- leaving ``is_direct_previous_filing_binding`` as
    the single guard against a binding that named no period anchor. The
    temporal union closed that gap at the declaration: ``same_target_context``
    is meaningful only for the ``per_grupo_member`` fold, and any other use is
    refused where it is written.

    Both halves are asserted here so neither can regress silently: the refusal
    below, and the predicate's surviving ``False`` branch for the one shape
    that ``same_target_context`` legitimately describes -- which is what keeps
    "lacking a period anchor" distinguishable from "relation-targeted" at the
    predicate's call sites.
    """
    with pytest.raises(ValidationError, match="same_target_context reads the target's own period"):
        PreviousFilingProvider(
            source_modelo="130",
            source_casilla_id=_M130_PAGO_FRACCIONADO_CASILLA,
            temporal=SameTargetContext(kind=BindingTemporalKind.SAME_TARGET_CONTEXT),
        )

    per_grupo = PreviousFilingProvider(
        source_modelo="130",
        source_casilla_id=_M130_PAGO_FRACCIONADO_CASILLA,
        temporal=SameTargetContext(kind=BindingTemporalKind.SAME_TARGET_CONTEXT),
        grouping="per_grupo_member",
    )
    assert per_grupo.required_periods == ()

    binding = BindingDefinition(
        id="modelo-130-test-unanchored-binding",
        provider=per_grupo,
        value=_MONEY_VALUE,
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
    on ``PreviousFilingProvider`` would keep passing construction-time
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
    drifted = BindingDefinition.model_construct(
        id="modelo-130-test-drift-binding",
        provider=PreviousFilingProvider.model_construct(
            # ``source_modelo`` deliberately absent: the provider no longer
            # round-trips into its own model, standing in for a field drift.
            source_casilla_id=_M130_PAGO_FRACCIONADO_CASILLA,
            temporal=_same_year_periods("1T"),
        ),
        value=_MONEY_VALUE,
        aggregation=BindingAggregation(op=BindingAggregationOp.COPY),
        legal_refs=(_REFERENCE_LEGAL_ID,),
        source_refs=(_REFERENCE_SOURCE_ID,),
    )

    with pytest.raises(RegistryValidationError, match="malformed previous-filing selector"):
        is_direct_previous_filing_binding(drifted)
