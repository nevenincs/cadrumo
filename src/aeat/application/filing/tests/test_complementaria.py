"""Tests for complementaria registry-boundary behaviour."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import Period
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.filing import (
    ModeloAmendmentError,
    ModeloBuilderError,
    ModeloDraft,
    ModeloValue,
    ModeloValueKind,
)
from ....domain.submission import ModeloDraftStatus, ModeloPresentado, SubmissionAttempt, SubmissionStatus
from .. import (
    ModeloInputs,
    build_complementaria,
    build_draft,
    build_runtime_schema_provider,
    load_amendment,
)
from ..testing import ModeloTestProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_PAGOS_PREVIOS_CASILLA: CasillaId = validated_casilla_id("05", surface="_M130_PAGOS_PREVIOS_CASILLA")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_AGRARIAN_VOLUME_CASILLA")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_AGRARIAN_WITHHELD_CASILLA")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_HOME_DEDUCTION_CASILLA")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RETURN_CASILLA")
_M130_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_RESULTADO_FINAL_CASILLA")
_UNSUPPORTED_M999_SOURCE_CASILLA: CasillaId = validated_casilla_id("69", surface="_UNSUPPORTED_M999_SOURCE_CASILLA")
_UNSUPPORTED_M999_UPDATE_BASE_CASILLA: CasillaId = validated_casilla_id(
    "07",
    surface="_UNSUPPORTED_M999_UPDATE_BASE_CASILLA",
)
_UNSUPPORTED_M999_UPDATE_CUOTA_CASILLA: CasillaId = validated_casilla_id(
    "29",
    surface="_UNSUPPORTED_M999_UPDATE_CUOTA_CASILLA",
)
_UNSUPPORTED_M998_SOURCE_CASILLA: CasillaId = validated_casilla_id("109", surface="_UNSUPPORTED_M998_SOURCE_CASILLA")
_UNSUPPORTED_M998_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "01",
    surface="_UNSUPPORTED_M998_EJERCICIO_CASILLA",
)


def _persist_original_draft(draft: ModeloDraft) -> None:
    from ....domain.filing import ModeloDraftRepository

    ModeloDraftRepository().save(draft)


def _persisted_amendment_ids() -> tuple[str, ...]:
    from ....domain.filing import ModeloAmendmentRepository

    return ModeloAmendmentRepository().list_amendment_ids()


def _submitted_filing(
    draft: ModeloDraft,
    *,
    submission_id: str = "sub-1",
    justificante_csv: str | None = None,
) -> ModeloPresentado:
    now = datetime(2026, 4, 13, 8, 0, tzinfo=UTC)
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        status=SubmissionStatus.PRESENTADA,
        justificante_csv=justificante_csv if justificante_csv is not None else f"CSV-{submission_id}",
        justificante_pdf_path=None,
        submitted_at=now,
        acknowledged_at=None,
        attempts=(
            SubmissionAttempt(
                attempt_id=f"{submission_id}.1",
                started_at=now,
                ended_at=now,
                status=SubmissionStatus.PRESENTADA,
            ),
        ),
    )


def _draft(modelo: str, period: Period, casillas: dict[CasillaId, Decimal]) -> ModeloDraft:
    now = datetime(2026, 4, 13, 8, 0, tzinfo=UTC)
    values = tuple(
        ModeloValue(
            casilla_id=casilla_id,
            value=value,
            kind=ModeloValueKind.LITERAL,
            source="input",
        )
        for casilla_id, value in sorted(casillas.items())
    )
    return ModeloDraft(
        draft_id=f"unsupported-{modelo}-{period.registry_token}",
        modelo=modelo,
        period=period,
        profile_tax_id="00000000T",
        status=ModeloDraftStatus.PRESENTADA,
        values=values,
        created_at=now,
        updated_at=now,
        schema_version=f"registry:{modelo}:missing",
    )


def _registry_draft(*, inputs: ModeloInputs) -> ModeloDraft:
    return build_draft(
        modelo="130",
        period=Period.from_year_and_code(2024, "1T"),
        profile=ModeloTestProfile(
            tax_id="00000000T",
            display_name="Complementaria registry test",
        ),
        inputs=inputs,
        schema_provider=build_runtime_schema_provider(),
    )


class TestBuildComplementaria:
    def test_modelo_130_builds_and_persists_complementaria(self) -> None:
        original_draft = _registry_draft(
            inputs={
                _M130_INGRESOS_CASILLA: Decimal("10000"),
                _M130_GASTOS_CASILLA: Decimal("4000"),
                _M130_PAGOS_PREVIOS_CASILLA: Decimal("250"),
                _M130_RETENCIONES_CASILLA: Decimal("100"),
                _M130_AGRARIAN_VOLUME_CASILLA: Decimal("2000"),
                _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("10"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
                "modelo-130-pagos-fraccionados-anteriores": Decimal("250"),
                # Casilla 15 omitted: M130 carry-forward must flow
                # through binding_values via
                # `modelo-130-resultados-negativos-anteriores`, not as
                # a direct casilla input. Same pattern as the M130
                # binding-id fix from #71/#95.
                _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
                _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
            },
        )
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft)

        amendment = build_complementaria(
            original,
            {
                _M130_INGRESOS_CASILLA: Decimal("13000"),
                _M130_GASTOS_CASILLA: Decimal("3500"),
                _M130_PAGOS_PREVIOS_CASILLA: Decimal("400"),
                _M130_RETENCIONES_CASILLA: Decimal("0"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
                "modelo-130-pagos-fraccionados-anteriores": Decimal("400"),
            },
            schema_provider=build_runtime_schema_provider(),
        )

        changed = {change.casilla_id: change for change in amendment.delta}
        assert amendment.original_model == "130"
        assert amendment.amendment_kind.value == "complementaria"
        assert changed[_M130_RESULTADO_FINAL_CASILLA].new_value == Decimal("1530.00")
        assert load_amendment(amendment.amendment_id).amendment_id == amendment.amendment_id

    def test_load_amendment_rejects_traversal_id(self) -> None:
        with pytest.raises(ModeloAmendmentError, match="path separators"):
            load_amendment("../escape")

    def test_complementaria_requires_official_justificante_csv(self) -> None:
        original_draft = _registry_draft(
            inputs={
                _M130_INGRESOS_CASILLA: Decimal("10000"),
                _M130_GASTOS_CASILLA: Decimal("4000"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            },
        )
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft, justificante_csv="")

        with pytest.raises(ModeloBuilderError, match="official justificante CSV"):
            build_complementaria(
                original,
                {_M130_INGRESOS_CASILLA: Decimal("11000")},
                schema_provider=build_runtime_schema_provider(),
            )
        assert _persisted_amendment_ids() == ()

    def test_complementaria_requires_original_registry_snapshot(self) -> None:
        original_draft = _registry_draft(
            inputs={
                _M130_INGRESOS_CASILLA: Decimal("10000"),
                _M130_GASTOS_CASILLA: Decimal("4000"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            },
        ).model_copy(update={"schema_version": "registry:130:wrong-revision"})
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft)

        with pytest.raises(ModeloBuilderError, match="active registry snapshot"):
            build_complementaria(
                original,
                {_M130_INGRESOS_CASILLA: Decimal("11000")},
                schema_provider=build_runtime_schema_provider(),
            )
        assert _persisted_amendment_ids() == ()

    def test_unknown_modelo_requires_registry_definition(self) -> None:
        original_draft = _draft(
            "999",
            Period.from_year_and_code(2024, "2T"),
            {_UNSUPPORTED_M999_SOURCE_CASILLA: Decimal("1900.00")},
        )
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft, submission_id="sub-999")

        with pytest.raises(ModeloBuilderError, match="not present in the calculation registry"):
            build_complementaria(
                original,
                {
                    _UNSUPPORTED_M999_UPDATE_BASE_CASILLA: Decimal("11000.00"),
                    _UNSUPPORTED_M999_UPDATE_CUOTA_CASILLA: Decimal("200.00"),
                },
                schema_provider=build_runtime_schema_provider(),
            )
        assert _persisted_amendment_ids() == ()

    def test_unknown_annual_modelo_requires_registry_definition(self) -> None:
        original_draft = _draft(
            "998",
            Period.from_year_and_code(2024, "0A"),
            {_UNSUPPORTED_M998_SOURCE_CASILLA: Decimal("8400.00")},
        )
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft, submission_id="sub-998")

        with pytest.raises(ModeloBuilderError, match="not present in the calculation registry"):
            build_complementaria(
                original,
                {_UNSUPPORTED_M998_EJERCICIO_CASILLA: 2024},
                schema_provider=build_runtime_schema_provider(),
            )
        assert _persisted_amendment_ids() == ()
