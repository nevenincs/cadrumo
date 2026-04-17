"""Unit tests for :mod:`aeat.schema._models`."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

from ..models import ModeloCode
from . import (
    BinaryFormulaOp,
    BinaryOp,
    Casilla,
    CasillaDataType,
    CasillaRef,
    CompareOp,
    CrossCasillaRule,
    EnumRule,
    FormulaNode,
    LiteralFormula,
    Modelo,
    RangeRule,
    RegexRule,
    SchemaEvaluationError,
    SchemaProvenance,
    SchemaSource,
    SchemaValidationError,
    SchemaVersion,
    SumFormula,
    ValidationRule,
    evaluate,
    validate_period_for_modelo,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]

_SHA = "a" * 64


def _provenance() -> SchemaProvenance:
    return SchemaProvenance(
        source=SchemaSource.BOE_ORDEN,
        origin_url=TypeAdapter(AnyHttpUrl).validate_python("https://www.boe.es/example.pdf"),
        document_ref="BOE-A-2023-15412",
        sha256=_SHA,
        content_length=2048,
        fetched_at=datetime(2026, 4, 17, 9, 0, tzinfo=UTC),
    )


def _minimal_casilla(
    *,
    casilla_id: str = "01",
    label: str = "Base imponible 1T",
    formula: FormulaNode | None = None,
    refs: tuple[str, ...] = (),
    source_page: int | None = 2,
) -> Casilla:
    return Casilla(
        casilla_id=casilla_id,
        label={"es": label},
        data_type=CasillaDataType.CURRENCY_EUR,
        required=formula is None,
        computed=formula is not None,
        formula=formula,
        references_casillas=refs,
        source_page=source_page,
    )


class TestFormulaAst:
    def test_literal_round_trip(self) -> None:
        node: FormulaNode = LiteralFormula(value=Decimal("42.50"))
        adapter = TypeAdapter(FormulaNode)
        restored = adapter.validate_json(adapter.dump_json(node, by_alias=True))
        assert restored == node

    def test_discriminator_round_trip_all_variants(self) -> None:
        nodes: tuple[FormulaNode, ...] = (
            LiteralFormula(value=Decimal("1")),
            CasillaRef(casilla_id="07"),
            BinaryOp(
                op=BinaryFormulaOp.SUB,
                left=CasillaRef(casilla_id="01"),
                right=CasillaRef(casilla_id="03"),
            ),
            SumFormula(
                terms=(
                    CasillaRef(casilla_id="01"),
                    CasillaRef(casilla_id="03"),
                ),
            ),
        )
        adapter = TypeAdapter(FormulaNode)
        for node in nodes:
            restored = adapter.validate_json(adapter.dump_json(node, by_alias=True))
            assert restored == node

    def test_casilla_ref_rejects_bad_id(self) -> None:
        with pytest.raises(ValidationError):
            CasillaRef(casilla_id="abc")


class TestEvaluate:
    def test_literal(self) -> None:
        assert evaluate(LiteralFormula(value=Decimal("7.50")), {}) == Decimal("7.50")

    def test_ref_lookup(self) -> None:
        node = CasillaRef(casilla_id="01")
        assert evaluate(node, {"01": Decimal("100")}) == Decimal("100")

    def test_ref_missing_raises_evaluation_error(self) -> None:
        with pytest.raises(SchemaEvaluationError):
            evaluate(CasillaRef(casilla_id="99"), {})

    def test_div_by_zero_includes_casilla_id(self) -> None:
        zero = BinaryOp(
            op=BinaryFormulaOp.DIV,
            left=LiteralFormula(value=Decimal("10")),
            right=LiteralFormula(value=Decimal("0")),
        )
        with pytest.raises(SchemaEvaluationError, match="'71'"):
            evaluate(zero, {}, casilla_id="71")

    def test_binop_add_sub_mul(self) -> None:
        values = {"01": Decimal("200"), "03": Decimal("60")}
        sub = BinaryOp(
            op=BinaryFormulaOp.SUB,
            left=CasillaRef(casilla_id="01"),
            right=CasillaRef(casilla_id="03"),
        )
        assert evaluate(sub, values) == Decimal("140")
        mul = BinaryOp(
            op=BinaryFormulaOp.MUL,
            left=CasillaRef(casilla_id="01"),
            right=LiteralFormula(value=Decimal("0.2")),
        )
        assert evaluate(mul, values) == Decimal("40.0")
        add = BinaryOp(
            op=BinaryFormulaOp.ADD,
            left=CasillaRef(casilla_id="01"),
            right=CasillaRef(casilla_id="03"),
        )
        assert evaluate(add, values) == Decimal("260")

    def test_binop_div_quantises_and_rejects_zero(self) -> None:
        values = {"10": Decimal("10"), "20": Decimal("3"), "30": Decimal("0")}
        div = BinaryOp(
            op=BinaryFormulaOp.DIV,
            left=CasillaRef(casilla_id="10"),
            right=CasillaRef(casilla_id="20"),
        )
        assert evaluate(div, values) == Decimal("3.33")
        zero = BinaryOp(
            op=BinaryFormulaOp.DIV,
            left=CasillaRef(casilla_id="10"),
            right=CasillaRef(casilla_id="30"),
        )
        with pytest.raises(SchemaEvaluationError):
            evaluate(zero, values)

    def test_sum(self) -> None:
        values = {"01": Decimal("10"), "03": Decimal("20"), "07": Decimal("5")}
        node = SumFormula(
            terms=(
                CasillaRef(casilla_id="01"),
                CasillaRef(casilla_id="03"),
                CasillaRef(casilla_id="07"),
            ),
        )
        assert evaluate(node, values) == Decimal("35")


class TestValidationRules:
    def test_range_rule_requires_a_bound(self) -> None:
        with pytest.raises(ValidationError):
            RangeRule()  # type: ignore[call-arg]

    def test_range_rule_alias_round_trip(self) -> None:
        rule: ValidationRule = RangeRule(min_=Decimal("0"), max_=Decimal("100"))
        adapter = TypeAdapter(ValidationRule)
        dumped = adapter.dump_json(rule, by_alias=True)
        assert b'"min"' in dumped
        assert b'"max"' in dumped
        restored = adapter.validate_json(dumped)
        assert restored == rule

    def test_range_rule_min_exceeds_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RangeRule(min_=Decimal("5"), max_=Decimal("1"))

    def test_regex_rule_rejects_bad_pattern(self) -> None:
        with pytest.raises(ValidationError):
            RegexRule(pattern="(")

    def test_enum_rule_requires_unique_non_empty_values(self) -> None:
        with pytest.raises(ValidationError):
            EnumRule(values=("a", "a"))
        with pytest.raises(ValidationError):
            EnumRule(values=("",))

    def test_cross_casilla_rule_round_trip(self) -> None:
        rule = CrossCasillaRule(
            expression=CasillaRef(casilla_id="71"),
            compare=CompareOp.GTE,
            rhs=LiteralFormula(value=Decimal("0")),
        )
        adapter = TypeAdapter(ValidationRule)
        restored = adapter.validate_json(adapter.dump_json(rule, by_alias=True))
        assert restored == rule


class TestCasillaValidators:
    def test_formula_and_computed_must_agree(self) -> None:
        with pytest.raises(ValidationError):
            Casilla(
                casilla_id="01",
                label={"es": "x"},
                data_type=CasillaDataType.CURRENCY_EUR,
                computed=True,
                formula=None,
                source_page=1,
            )
        with pytest.raises(ValidationError):
            Casilla(
                casilla_id="01",
                label={"es": "x"},
                data_type=CasillaDataType.CURRENCY_EUR,
                computed=False,
                formula=LiteralFormula(value=Decimal("1")),
                source_page=1,
            )

    def test_references_must_cover_formula_refs(self) -> None:
        formula = BinaryOp(
            op=BinaryFormulaOp.SUB,
            left=CasillaRef(casilla_id="01"),
            right=CasillaRef(casilla_id="03"),
        )
        with pytest.raises(ValidationError):
            Casilla(
                casilla_id="07",
                label={"es": "x"},
                data_type=CasillaDataType.CURRENCY_EUR,
                computed=True,
                formula=formula,
                references_casillas=("01",),
                source_page=1,
            )

    def test_authoritative_spanish_required(self) -> None:
        with pytest.raises(ValidationError):
            Casilla(
                casilla_id="01",
                label={"en": "only english"},  # type: ignore[typeddict-item]
                data_type=CasillaDataType.CURRENCY_EUR,
                source_page=1,
            )


def _build_modelo(
    *,
    modelo_code: ModeloCode = ModeloCode.MODELO_130,
    period: str = "2025Q4",
    casillas: tuple[Casilla, ...] | None = None,
) -> Modelo:
    return Modelo(
        modelo_code=modelo_code,
        portal=None,
        period=period,
        casillas=casillas if casillas is not None else (_minimal_casilla(),),
        provenance=_provenance(),
        extracted_at=datetime(2026, 4, 17, 9, 5, tzinfo=UTC),
        schema_version=SchemaVersion(boe_ref="BOE-A-2023-15412"),
    )


class TestModeloValidators:
    def test_happy_path(self) -> None:
        modelo = _build_modelo()
        assert modelo.modelo_code is ModeloCode.MODELO_130

    def test_period_must_match_cadence(self) -> None:
        with pytest.raises(ValidationError):
            _build_modelo(period="2025")

    def test_annual_cadence_accepts_year_only(self) -> None:
        modelo = _build_modelo(modelo_code=ModeloCode.MODELO_390, period="2025")
        assert modelo.period == "2025"

    def test_boe_orden_requires_source_page(self) -> None:
        with pytest.raises(ValidationError):
            _build_modelo(casillas=(_minimal_casilla(source_page=None),))

    def test_duplicate_casilla_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _build_modelo(
                casillas=(
                    _minimal_casilla(casilla_id="01"),
                    _minimal_casilla(casilla_id="01"),
                ),
            )

    def test_dangling_reference_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _build_modelo(
                casillas=(
                    _minimal_casilla(
                        casilla_id="07",
                        formula=CasillaRef(casilla_id="99"),
                        refs=("99",),
                    ),
                ),
            )

    def test_circular_formula_graph_rejected(self) -> None:
        casillas = (
            _minimal_casilla(
                casilla_id="01",
                formula=CasillaRef(casilla_id="03"),
                refs=("03",),
            ),
            _minimal_casilla(
                casilla_id="03",
                formula=CasillaRef(casilla_id="01"),
                refs=("01",),
            ),
        )
        with pytest.raises(ValidationError, match="cycle"):
            _build_modelo(casillas=casillas)

    def test_boe_orden_requires_schema_version_boe_ref(self) -> None:
        with pytest.raises(ValidationError, match="schema_version"):
            Modelo(
                modelo_code=ModeloCode.MODELO_130,
                portal=None,
                period="2025Q4",
                casillas=(_minimal_casilla(),),
                provenance=_provenance(),
                extracted_at=datetime(2026, 4, 17, 9, 5, tzinfo=UTC),
                schema_version=SchemaVersion(),
            )


class TestSchemaProvenanceSourceGate:
    @pytest.mark.parametrize(
        "reserved_source",
        [
            SchemaSource.PORTAL_HTML_PROBE,
            SchemaSource.MANUAL_LLM_DRAFT,
            SchemaSource.XSD_WIRE,
        ],
    )
    def test_reserved_sources_rejected_in_v1(self, reserved_source: SchemaSource) -> None:
        with pytest.raises(ValidationError, match="reserved enum slot"):
            SchemaProvenance(
                source=reserved_source,
                origin_url=TypeAdapter(AnyHttpUrl).validate_python("https://www.boe.es/x.pdf"),
                document_ref="BOE-A-FAKE",
                sha256="a" * 64,
                content_length=1,
                fetched_at=datetime(2026, 4, 17, tzinfo=UTC),
            )


class TestValidatePeriodWhitespace:
    def test_rejects_surrounding_whitespace(self) -> None:
        with pytest.raises(SchemaValidationError, match="whitespace"):
            validate_period_for_modelo(ModeloCode.MODELO_130, " 2025Q4")


class TestValidatePeriodForModelo:
    def test_quarterly_accepts_period(self) -> None:
        validate_period_for_modelo(ModeloCode.MODELO_130, "2025Q4")

    def test_quarterly_rejects_annual(self) -> None:
        with pytest.raises(SchemaValidationError):
            validate_period_for_modelo(ModeloCode.MODELO_130, "2025")

    def test_annual_accepts_year(self) -> None:
        validate_period_for_modelo(ModeloCode.MODELO_390, "2025")

    def test_annual_rejects_quarterly(self) -> None:
        with pytest.raises(SchemaValidationError):
            validate_period_for_modelo(ModeloCode.MODELO_390, "2025Q4")

    def test_ad_hoc_accepts_year(self) -> None:
        validate_period_for_modelo(ModeloCode.MODELO_036, "2025")

    def test_rejects_garbage(self) -> None:
        with pytest.raises(SchemaValidationError):
            validate_period_for_modelo(ModeloCode.MODELO_130, "not-a-period")
