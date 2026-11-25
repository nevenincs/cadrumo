"""M210 / IRNR formula-runtime contract tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from .....core.time.clock import frozen_clock
from ..authority import PinnedAuthorityOperation
from ..errors import RegistryValidationError
from ..facts.resolution import GovernedFactQuery, ResolvedGovernedFact
from ..formula_expression import EvalContext
from ..formula_runtime import calculate_registry_snapshot
from ..formula_runtime_irnr import (
    evaluate_m210_resolve_base_imponible,
    irnr_resolve_tipo_gravamen_args,
    m210_allows_art_24_6_expenses,
)
from ..formula_runtime_ops import (
    RegistryUnresolvedOutcomeReason,
    resolve_keyed_bracket,
)
from ..governed_fact_scope import validating_governed_facts
from ..irnr_tipo_renta import resolve_tipo_renta_irnr_catalogue, tipo_renta_ue_residente_token
from ..schema import FormulaDefinition, RegistrySnapshot
from ..schema_formula import FormulaExpression
from ..schema_references import TemporalSupportEnvelope
from .authored_editions import filing_year_envelope
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_YEAR = filing_year_envelope().horizon

_M210_COUNTRY_BINDING = "m210-profile-country-of-fiscal-residence"
_M210_TIPO_RENTA_CASILLA = "tipo_renta"
_M210_RENDIMIENTOS_INTEGROS_CASILLA = "rendimientos_integros"
_M210_GASTOS_DEDUCIBLES_CASILLA = "gastos_deducibles"
_M210_RETENCION_PRACTICADA_CASILLA = "retencion_practicada"
_M210_TIPO_GRAVAMEN_CASILLA = "tipo_gravamen"


def _current_m210_snapshot() -> RegistrySnapshot:
    return published_snapshot("210", filing_year=_YEAR, period="EVENT-1")


def _current_m210_rate_formula() -> FormulaDefinition:
    revision = _current_m210_snapshot().revision
    return next(
        formula
        for formula in revision.formulas
        if formula.target_casilla_id == _M210_TIPO_GRAVAMEN_CASILLA
        and formula.expression.op == "irnr_resolve_tipo_gravamen"
    )


def _current_m210_rate_expression() -> FormulaExpression:
    return _current_m210_rate_formula().expression


def test_art_24_6_expense_branch_uses_the_registry_declared_resident_token() -> None:
    effective_date = date(_YEAR, 1, 1)
    resident_token = tipo_renta_ue_residente_token(effective_date=effective_date)
    other_token = next(
        token
        for token in resolve_tipo_renta_irnr_catalogue(effective_date=effective_date).all_tokens
        if token != resident_token
    )

    assert m210_allows_art_24_6_expenses(
        tipo_renta=resident_token,
        country_code="ZW",
        effective_date=effective_date,
    )
    assert not m210_allows_art_24_6_expenses(
        tipo_renta=other_token,
        country_code="ZW",
        effective_date=effective_date,
    )


class _DateRecordingSource:
    """Delegate every governed-fact read to the pinned operation, keeping the date each one asked for."""

    def __init__(self, inner: PinnedAuthorityOperation) -> None:
        self._inner = inner
        self.asked: list[date] = []

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        self.asked.append(query.effective_date)
        return self._inner.resolve_governed_fact(query)

    def supported_filing_years(self) -> TemporalSupportEnvelope:
        return self._inner.supported_filing_years()


def test_art_24_6_expense_branch_reads_eu_eea_membership_at_the_devengo_not_the_run_date(
    operation: PinnedAuthorityOperation,
) -> None:
    devengo = date(_YEAR, 3, 1)
    other_token = next(
        token
        for token in resolve_tipo_renta_irnr_catalogue(effective_date=devengo).all_tokens
        if token != tipo_renta_ue_residente_token(effective_date=devengo)
    )
    recorder = _DateRecordingSource(operation)
    outside_the_envelope = datetime(filing_year_envelope().floor - 3, 6, 15, 12, tzinfo=UTC)

    with frozen_clock(outside_the_envelope), validating_governed_facts(recorder):
        allows_eu = m210_allows_art_24_6_expenses(tipo_renta=other_token, country_code="FR", effective_date=devengo)
        allows_third_country = m210_allows_art_24_6_expenses(
            tipo_renta=other_token, country_code="ZW", effective_date=devengo
        )

    assert allows_eu
    assert not allows_third_country
    assert recorder.asked
    assert set(recorder.asked) == {devengo}


def test_m210_base_imponible_without_a_devengo_date_is_refused() -> None:
    expression = next(
        formula.expression
        for formula in _current_m210_snapshot().revision.formulas
        if formula.expression.op == "m210_resolve_base_imponible"
    )
    context = EvalContext(
        values={},
        binding_values={},
        parameters={},
        date_context={},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=[],
        operand_casilla_refs=[],
        operand_values=[],
        enum_binding_values={},
        date_binding_values={},
        filing_year=_YEAR,
    )

    with pytest.raises(RegistryValidationError, match=r"^M210 base imponible requires a filing_period devengo date$"):
        evaluate_m210_resolve_base_imponible(expression, context)


def test_irnr_resolve_tipo_gravamen_args_accepts_current_five_arg_contract() -> None:
    args = irnr_resolve_tipo_gravamen_args(_current_m210_rate_expression())

    assert args.tipo_casilla_id == "tipo_renta"
    assert args.base_casilla_id == "base_imponible"
    assert args.baseline_parameter == "m210-tipo-gravamen"
    assert args.pension_tariff_parameter == "m210-pension-tarifa"
    assert args.country_binding == _M210_COUNTRY_BINDING


def test_irnr_resolve_tipo_gravamen_args_rejects_retired_convenio_parameter_contract() -> None:
    # The retired six-arg contract carried an M210-local convenio-rates parameter
    # leaf at args[3]; the generalised op reads treaty overrides from the
    # ConvenioAuthority snapshot projection instead, so the arg count is now 5.
    #
    # FormulaExpression.model_validate() now enforces op arity centrally
    # (require_formula_operator_arity, at construction), so a 6-arg expression
    # can no longer reach this resolver's own arity check via normal
    # validation. model_construct() bypasses that model-level validator to
    # exercise this function's defense-in-depth check directly.
    retired_expression = FormulaExpression.model_construct(
        op="irnr_resolve_tipo_gravamen",
        args=(
            FormulaExpression.model_validate({"casilla_id": "tipo_renta"}),
            FormulaExpression.model_validate({"casilla_id": "base_imponible"}),
            FormulaExpression.model_validate({"parameter": "m210-tipo-gravamen"}),
            FormulaExpression.model_validate({"parameter": "m210-convenio-rates"}),
            FormulaExpression.model_validate({"parameter": "m210-pension-tarifa"}),
            FormulaExpression.model_validate({"binding": _M210_COUNTRY_BINDING}),
        ),
    )

    with pytest.raises(RegistryValidationError, match=r"expects 5 args, got 6"):
        irnr_resolve_tipo_gravamen_args(retired_expression)


def test_irnr_resolve_tipo_gravamen_reports_unresolved_rate_as_typed_outcome() -> None:
    snapshot = _current_m210_snapshot()

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _M210_RENDIMIENTOS_INTEGROS_CASILLA: Decimal("12000"),
            _M210_GASTOS_DEDUCIBLES_CASILLA: Decimal("0"),
            _M210_RETENCION_PRACTICADA_CASILLA: Decimal("0"),
        },
        enum_binding_values={_M210_COUNTRY_BINDING: "ZW"},
        text_inputs={_M210_TIPO_RENTA_CASILLA: "general"},
        date_context={"filing_period": date(_YEAR, 12, 31)},
    )

    assert _M210_TIPO_GRAVAMEN_CASILLA not in result.values
    assert all(value not in {Decimal("-1"), Decimal("-2")} for value in result.values.values())
    assert len(result.unresolved_outcomes) == 1
    outcome = result.unresolved_outcomes[0]
    assert outcome.casilla_id == _M210_TIPO_GRAVAMEN_CASILLA
    assert outcome.reason is RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING
    assert outcome.formula_id == _current_m210_rate_formula().id
    assert outcome.operand_refs == (
        _M210_TIPO_RENTA_CASILLA,
        "m210-tipo-gravamen",
        _M210_COUNTRY_BINDING,
    )
    assert outcome.operand_casilla_refs == (_M210_TIPO_RENTA_CASILLA,)
    assert outcome.legal_refs
    assert outcome.source_refs
    assert outcome.context["tipo_renta"] == "general"
    assert outcome.context["country"] == "ZW"


def test_irnr_resolve_tipo_gravamen_resolves_dividend_baseline_rate() -> None:
    """Art. 25.1.f.1º dividends resolve the unconditional 19% baseline, not a blocking refusal.

    Before the ``dividend`` tipo_renta category was added to the registry
    baseline table, a non-resident with Spanish-source dividend income (a
    routine M210 category) had no matching bracket row and hit the
    fail-closed ``m210-baseline-tipo-deferred`` unresolved outcome. This
    proves the engine now computes the rate directly with no treaty
    country declared (the baseline branch), producing a real
    ``tipo_gravamen`` value rather than an ``unresolved_outcomes`` entry.
    """
    snapshot = _current_m210_snapshot()

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _M210_RENDIMIENTOS_INTEGROS_CASILLA: Decimal("1000"),
            _M210_GASTOS_DEDUCIBLES_CASILLA: Decimal("0"),
            _M210_RETENCION_PRACTICADA_CASILLA: Decimal("0"),
        },
        enum_binding_values={},
        text_inputs={_M210_TIPO_RENTA_CASILLA: "dividend"},
        date_context={"filing_period": date(_YEAR, 12, 31)},
    )

    assert result.unresolved_outcomes == ()
    assert result.values[_M210_TIPO_GRAVAMEN_CASILLA] == Decimal("0.19")
    assert result.values["cuota_integra"] == Decimal("190.00")


def test_irnr_resolve_tipo_gravamen_retains_selected_treaty_fact_provenance() -> None:
    """A dated treaty lookup is visible in the computed formula lineage."""
    snapshot = _current_m210_snapshot()

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _M210_RENDIMIENTOS_INTEGROS_CASILLA: Decimal("1000"),
            _M210_GASTOS_DEDUCIBLES_CASILLA: Decimal("0"),
            _M210_RETENCION_PRACTICADA_CASILLA: Decimal("0"),
        },
        enum_binding_values={_M210_COUNTRY_BINDING: "BE"},
        text_inputs={_M210_TIPO_RENTA_CASILLA: "dividend"},
        date_context={"filing_period": date(_YEAR, 12, 31)},
    )

    assert result.values[_M210_TIPO_GRAVAMEN_CASILLA] == Decimal("0.15")
    entry = next(entry for entry in result.entries if entry.target_casilla_id == _M210_TIPO_GRAVAMEN_CASILLA)
    assert any(ref.startswith("irnr.convenio.override:") for ref in entry.operand_refs)


def test_keyed_bracket_resolution_rejects_overlapping_official_m210_rate_windows() -> None:
    """A contradictory rate row must not silently replace Art. 25.1.f's 19% dividend rate."""
    snapshot = _current_m210_snapshot()
    parameter = next(parameter for parameter in snapshot.revision.parameters if parameter.id == "m210-tipo-gravamen")
    dividend = next(entry for entry in parameter.keyed_brackets if entry.key == "dividend")

    assert resolve_keyed_bracket(parameter, key="dividend", filing_year=_YEAR) == Decimal("0.19")

    overlapping = parameter.model_copy(
        update={
            "keyed_brackets": (
                *parameter.keyed_brackets,
                dividend.model_copy(update={"value": Decimal("0.24"), "valid_from": date(_YEAR, 6, 1)}),
            )
        }
    )
    with pytest.raises(RegistryValidationError, match="expected exactly one keyed bracket") as exc_info:
        resolve_keyed_bracket(overlapping, key="dividend", filing_year=_YEAR)

    assert exc_info.value.context == {
        "parameter_id": "m210-tipo-gravamen",
        "key": "dividend",
        "filing_year": str(_YEAR),
        "match_count": "2",
    }
