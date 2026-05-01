"""Unit tests for Modelo 303 + Modelo 390 builders and reconciliation.

The module carries ``pytestmark = [pytest.mark.unit, pytest.mark.domain_application]`` per the project rule.
No mocks, patches, fakes, or stubs — every test double is a
hand-written strict pydantic model that conforms to the relevant
Protocol via duck typing.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from . import (
    QUARTERLY_303_INPUT_KEY,
    FilingComputationError,
    FilingDraft,
    FilingDraftStatus,
    FilingFindingSeverity,
    FilingValue,
    FilingValueKind,
    Modelo303Builder,
    Modelo390Builder,
    build_draft,
    validate_draft,
)
from .testing import (
    SyntheticProfile,
    default_schema_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _profile() -> SyntheticProfile:
    return SyntheticProfile(
        tax_id="12345678Z",
        display_name="Test Autónomo IVA",
        applicable_modelos=("303", "390"),
    )


def _quarterly_inputs(
    *,
    base_21: str = "10000.00",
    deducible_29: str = "200.00",
) -> dict[str, object]:
    return {
        "07": Decimal(base_21),
        "29": Decimal(deducible_29),
    }


def _build_303(quarter: int, inputs: dict[str, object] | None = None) -> FilingDraft:
    return build_draft(
        modelo="303",
        period=f"2025Q{quarter}",
        profile=_profile(),
        inputs=inputs if inputs is not None else _quarterly_inputs(),
        schema_provider=default_schema_provider(),
    )


class TestModelo303Builder:
    """Hand-calculated arithmetic and validation for Modelo 303."""

    def test_21_percent_only_happy_path(self) -> None:
        draft = _build_303(1, {"07": Decimal("10000.00"), "29": Decimal("200.00")})
        by_id = {v.casilla_id: v for v in draft.values}
        # 10000 x 0.21 = 2100
        assert by_id["09"].value == Decimal("2100.0000")
        assert by_id["09"].kind is FilingValueKind.COMPUTED
        assert by_id["09"].formula_trace == ("07",)
        assert by_id["44"].formula_trace == (
            "29",
            "31",
            "33",
            "35",
            "37",
            "39",
            "40",
            "41",
            "42",
            "43",
        )
        # 45 = (0 + 0 + 2100) - 200 = 1900
        assert by_id["45"].value == Decimal("1900.00")
        assert by_id["45"].formula_trace == ("03", "06", "09", "44")
        # 66 = 1900 x 100 / 100 = 1900
        assert by_id["66"].value == Decimal("1900.00")
        assert by_id["71"].value == Decimal("1900.00")
        assert draft.status is FilingDraftStatus.READY_TO_SUBMIT

    def test_all_three_rates_compute(self) -> None:
        draft = _build_303(
            2,
            {
                "01": Decimal("1000.00"),
                "04": Decimal("2000.00"),
                "07": Decimal("3000.00"),
                "29": Decimal("0.00"),
            },
        )
        by_id = {v.casilla_id: v for v in draft.values}
        assert by_id["03"].value == Decimal("40.0000")
        assert by_id["06"].value == Decimal("200.000")
        assert by_id["09"].value == Decimal("630.0000")
        # Sum of cuotas - 0 deducible
        assert by_id["45"].value == Decimal("870.0000")

    def test_default_rates_are_carried_as_defaults(self) -> None:
        draft = _build_303(1)
        by_id = {v.casilla_id: v for v in draft.values}
        assert by_id["02"].kind is FilingValueKind.DEFAULT
        assert by_id["02"].value == Decimal("4")
        assert by_id["05"].value == Decimal("10")
        assert by_id["08"].value == Decimal("21")
        assert by_id["65"].value == Decimal("100")
        assert by_id["67"].value == Decimal("0")

    def test_missing_required_casilla_yields_error_finding(self) -> None:
        draft = _build_303(1, {})
        # Base 07 is required — missing triggers a validator error.
        error_codes = {f.code for f in draft.findings if f.severity is FilingFindingSeverity.ERROR}
        assert "casilla-required-missing" in error_codes
        assert draft.status is FilingDraftStatus.DRAFT

    def test_out_of_range_65_percent(self) -> None:
        draft = _build_303(1, {"07": Decimal("1000"), "65": Decimal("150"), "29": Decimal("0")})
        codes = {(f.code, f.casilla_id) for f in draft.findings}
        assert ("casilla-out-of-range", "65") in codes

    def test_user_literal_on_computed_casilla_is_divergence(self) -> None:
        # If the caller supplies a value for a formula casilla, the builder
        # still computes it — but a caller who hand-mutates via model_copy
        # triggers formula-divergence. We simulate the latter here.
        clean = _build_303(1, {"07": Decimal("10000"), "29": Decimal("0")})
        # Build a tampered draft where casilla 09 is a LITERAL with the wrong trace.
        tampered_values = tuple(
            FilingValue(
                casilla_id=v.casilla_id,
                value=Decimal("9999"),
                kind=FilingValueKind.LITERAL,
                source="tampered",
                formula_trace=None,
            )
            if v.casilla_id == "09"
            else v
            for v in clean.values
        )
        tampered = clean.model_copy(update={"values": tampered_values})
        revalidated = validate_draft(
            tampered,
            schema_provider=default_schema_provider(),
        )
        divergences = {f.code for f in revalidated.findings}
        assert "formula-divergence" in divergences

    def test_stable_draft_id_across_builds(self) -> None:
        first = _build_303(3)
        second = _build_303(3)
        assert first.draft_id == second.draft_id

    def test_json_round_trip(self) -> None:
        draft = _build_303(4)
        restored = FilingDraft.model_validate_json(draft.model_dump_json())
        assert restored.draft_id == draft.draft_id
        assert restored.modelo == "303"
        assert restored.values == draft.values

    def test_builder_is_registered(self) -> None:
        assert Modelo303Builder.modelo_id == "303"
        # Dispatch via build_draft works for 303.
        draft = build_draft(
            modelo="303",
            period="2025Q1",
            profile=_profile(),
            inputs={"07": Decimal("100")},
            schema_provider=default_schema_provider(),
        )
        assert draft.modelo == "303"


class TestModelo390Builder:
    """Hand-calculated arithmetic for Modelo 390."""

    def test_annual_totals_are_sum_of_quarterly(self) -> None:
        quarterly = tuple(_build_303(q) for q in (1, 2, 3, 4))
        annual = build_draft(
            modelo="390",
            period="2025",
            profile=_profile(),
            inputs={"01": 2025, QUARTERLY_303_INPUT_KEY: quarterly},
            schema_provider=default_schema_provider(),
        )
        by_id = {v.casilla_id: v for v in annual.values}
        assert by_id["108"].value == Decimal("40000.00")
        assert by_id["108"].kind is FilingValueKind.INHERITED
        # 4 x 2100 = 8400
        assert by_id["109"].value == Decimal("8400.0000")
        assert by_id["191"].value == Decimal("800.00")
        # 84 = 0 + 0 + 8400
        assert by_id["84"].value == Decimal("8400.0000")
        assert by_id["84"].kind is FilingValueKind.COMPUTED
        assert by_id["85"].value == Decimal("800.00")
        assert by_id["86"].value == Decimal("7600.0000")
        assert by_id["95"].value == Decimal("7600.0000")
        assert annual.status is FilingDraftStatus.READY_TO_SUBMIT

    def test_missing_quarterly_drafts_raises(self) -> None:
        with pytest.raises(FilingComputationError, match="quarterly Modelo 303"):
            build_draft(
                modelo="390",
                period="2025",
                profile=_profile(),
                inputs={"01": 2025},
                schema_provider=default_schema_provider(),
            )

    def test_wrong_number_of_quarterly_drafts_raises(self) -> None:
        quarterly = tuple(_build_303(q) for q in (1, 2, 3))
        with pytest.raises(FilingComputationError, match="exactly 4"):
            build_draft(
                modelo="390",
                period="2025",
                profile=_profile(),
                inputs={"01": 2025, QUARTERLY_303_INPUT_KEY: quarterly},
                schema_provider=default_schema_provider(),
            )

    def test_quarterly_year_mismatch_raises(self) -> None:
        quarterly = tuple(_build_303(q) for q in (1, 2, 3, 4))
        with pytest.raises(FilingComputationError, match="must cover"):
            build_draft(
                modelo="390",
                period="2024",
                profile=_profile(),
                inputs={"01": 2024, QUARTERLY_303_INPUT_KEY: quarterly},
                schema_provider=default_schema_provider(),
            )

    def test_builder_is_registered(self) -> None:
        assert Modelo390Builder.modelo_id == "390"

    def test_ejercicio_required(self) -> None:
        quarterly = tuple(_build_303(q) for q in (1, 2, 3, 4))
        with pytest.raises(FilingComputationError, match="ejercicio"):
            build_draft(
                modelo="390",
                period="2025",
                profile=_profile(),
                inputs={QUARTERLY_303_INPUT_KEY: quarterly},
                schema_provider=default_schema_provider(),
            )

    def test_stable_draft_id_across_builds(self) -> None:
        quarterly = tuple(_build_303(q) for q in (1, 2, 3, 4))
        first = build_draft(
            modelo="390",
            period="2025",
            profile=_profile(),
            inputs={"01": 2025, QUARTERLY_303_INPUT_KEY: quarterly},
            schema_provider=default_schema_provider(),
        )
        second = build_draft(
            modelo="390",
            period="2025",
            profile=_profile(),
            inputs={"01": 2025, QUARTERLY_303_INPUT_KEY: quarterly},
            schema_provider=default_schema_provider(),
        )
        assert first.draft_id == second.draft_id

    def test_json_round_trip(self) -> None:
        quarterly = tuple(_build_303(q) for q in (1, 2, 3, 4))
        annual = build_draft(
            modelo="390",
            period="2025",
            profile=_profile(),
            inputs={"01": 2025, QUARTERLY_303_INPUT_KEY: quarterly},
            schema_provider=default_schema_provider(),
        )
        restored = FilingDraft.model_validate_json(annual.model_dump_json())
        assert restored.draft_id == annual.draft_id
        assert restored.values == annual.values


class TestModelo390CrossValidation:
    """Cross-validation rules between 390 and its four 303 drafts."""

    def test_clean_reconciliation_has_no_mismatch_findings(self) -> None:
        quarterly = tuple(_build_303(q) for q in (1, 2, 3, 4))
        annual = build_draft(
            modelo="390",
            period="2025",
            profile=_profile(),
            inputs={"01": 2025, QUARTERLY_303_INPUT_KEY: quarterly},
            schema_provider=default_schema_provider(),
        )
        codes = {f.code for f in annual.findings}
        assert "filing-390-303-mismatch" not in codes
        assert "filing-303-internal-mismatch" not in codes

    def test_mismatched_annual_value_emits_mismatch(self) -> None:
        quarterly = tuple(_build_303(q) for q in (1, 2, 3, 4))
        annual = build_draft(
            modelo="390",
            period="2025",
            profile=_profile(),
            inputs={"01": 2025, QUARTERLY_303_INPUT_KEY: quarterly},
            schema_provider=default_schema_provider(),
        )
        # Poison the stored annual 109 value to diverge from the quarterly sum.
        tampered_values = tuple(
            FilingValue(
                casilla_id=v.casilla_id,
                value=Decimal("999999"),
                kind=FilingValueKind.INHERITED,
                source="tampered",
                formula_trace=None,
            )
            if v.casilla_id == "109"
            else v
            for v in annual.values
        )
        tampered = annual.model_copy(update={"values": tampered_values})
        # Re-run full validation via the low-level validator to thread the
        # quarterly drafts explicitly — validate_draft cannot because it
        # constructs its own validator without them.
        from . import FilingValidator, apply_validation

        validator = FilingValidator(
            schema_provider=default_schema_provider(),
            quarterly_303_drafts=quarterly,
        )
        findings = validator.validate(tampered)
        refreshed = apply_validation(tampered, findings)
        mismatches = [f for f in refreshed.findings if f.code == "filing-390-303-mismatch" and f.casilla_id == "109"]
        assert len(mismatches) == 1
        assert mismatches[0].severity is FilingFindingSeverity.ERROR

    def test_poisoned_303_internal_triggers_self_consistency_finding(self) -> None:
        quarterly_list = [_build_303(q) for q in (1, 2, 3, 4)]
        # Poison Q2's casilla 09 to diverge from 07 x 0.21.
        q2 = quarterly_list[1]
        tampered_values = tuple(
            FilingValue(
                casilla_id=v.casilla_id,
                value=Decimal("1.00"),
                kind=FilingValueKind.LITERAL,
                source="tampered",
                formula_trace=None,
            )
            if v.casilla_id == "09"
            else v
            for v in q2.values
        )
        quarterly_list[1] = q2.model_copy(update={"values": tampered_values})
        quarterly = tuple(quarterly_list)
        # Build a 390 that matches the tampered quarterly index so
        # the 390→303 reconciliation rule stays clean and only the
        # self-consistency rule fires.
        annual = Modelo390Builder().build(
            period="2025",
            profile=_profile(),
            inputs={"01": 2025, QUARTERLY_303_INPUT_KEY: quarterly},
            schema_provider=default_schema_provider(),
        )
        from . import FilingValidator

        validator = FilingValidator(
            schema_provider=default_schema_provider(),
            quarterly_303_drafts=quarterly,
        )
        findings = validator.validate(annual)
        internal = [f for f in findings if f.code == "filing-303-internal-mismatch"]
        assert internal, f"expected self-consistency finding, got {[f.code for f in findings]}"
        assert internal[0].severity is FilingFindingSeverity.ERROR
        assert internal[0].casilla_id == "09"

    def test_trilingual_message_keys_present(self) -> None:
        quarterly = tuple(_build_303(q) for q in (1, 2, 3, 4))
        annual = build_draft(
            modelo="390",
            period="2025",
            profile=_profile(),
            inputs={"01": 2025, QUARTERLY_303_INPUT_KEY: quarterly},
            schema_provider=default_schema_provider(),
        )
        tampered_values = tuple(
            FilingValue(
                casilla_id=v.casilla_id,
                value=Decimal("42"),
                kind=FilingValueKind.INHERITED,
                source="tampered",
                formula_trace=None,
            )
            if v.casilla_id == "109"
            else v
            for v in annual.values
        )
        tampered = annual.model_copy(update={"values": tampered_values})
        from . import FilingValidator

        validator = FilingValidator(
            schema_provider=default_schema_provider(),
            quarterly_303_drafts=quarterly,
        )
        findings = validator.validate(tampered)
        mismatch = next(f for f in findings if f.code == "filing-390-303-mismatch")
        assert set(mismatch.message.keys()) == {"es", "en", "hu"}
