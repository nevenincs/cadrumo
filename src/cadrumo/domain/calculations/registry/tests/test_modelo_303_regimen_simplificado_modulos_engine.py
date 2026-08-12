"""M303 simplified-regime runtime consumes only immutable S58/S59 evidence."""

from __future__ import annotations

import ast
import tomllib
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.resources import bundled_path
from .....domain.iva import (
    ActividadOrdenAnual,
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
)
from .. import (
    _formula_runtime,
    bundled_authority,
    resolve_m303_regimen_simplificado_snapshot,
)
from .._errors import RegistryValidationError
from .._formula_operator_contracts import FORMULA_OPERATOR_ARITIES
from .._formula_runtime import calculate_registry_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _snapshot(year: int):
    return bundled_authority().snapshot("303", filing_year=year, period="4T")


def _general_scope() -> M303RegimenSimplificadoScopeDecision:
    return M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )


def _calculate_general_m303(
    year: int,
    *,
    inputs: dict[str, Decimal] | None = None,
    text_inputs: dict[str, str] | None = None,
):
    snapshot = _snapshot(year)
    assert snapshot.filing_period is not None
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs or {},
        text_inputs=text_inputs or {},
        m303_regimen_simplificado_scope=_general_scope(),
        binding_values={"modelo-303-compensacion-pendiente-anteriores": Decimal("0")},
        date_context={"filing_period": snapshot.filing_period.end_date},
        m303_annual_orden=None,
    )


@pytest.mark.parametrize("year", (2023, 2025, 2026))
def test_general_scope_neutralises_internal_regimen_simplificado_formulas(year: int) -> None:
    result = _calculate_general_m303(year)

    assert result.values["modulos-iva-cuota-devengada"] == Decimal("0")
    assert result.values["modulos-iva-cuota-derivada"] == Decimal("0")


@pytest.mark.parametrize(
    ("inputs", "text_inputs"),
    (
        ({"modulos-iva-1-unidades": Decimal("0")}, {}),
        ({"modulos-iva-1-unidades": Decimal("1")}, {}),
        ({}, {"modulos-iva-orden-id": "m303:2025:iva:c56cf8ab2f45c4040323"}),
    ),
)
def test_general_scope_rejects_any_orden_or_module_row(
    inputs: dict[str, Decimal],
    text_inputs: dict[str, str],
) -> None:
    with pytest.raises(RegistryValidationError, match="general Modelo 303 scope rejects"):
        _calculate_general_m303(2025, inputs=inputs, text_inputs=text_inputs)


def test_evidence_required_scope_calculates_with_exact_canonical_orden() -> None:
    snapshot = _snapshot(2025)
    assert snapshot.filing_period is not None
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED,
    )

    resolved = resolve_m303_regimen_simplificado_snapshot(registry_snapshot=snapshot, scope_decision=scope)
    activity = resolved.orden.activities[0]
    result = calculate_registry_snapshot(
        snapshot,
        inputs={"modulos-iva-1-unidades": Decimal("1")},
        text_inputs={"modulos-iva-orden-id": activity.orden_id},
        binding_values={"modelo-303-compensacion-pendiente-anteriores": Decimal("0")},
        date_context={"filing_period": snapshot.filing_period.end_date},
        m303_regimen_simplificado_scope=scope,
        m303_annual_orden=resolved.orden,
    )

    assert result.values["modulos-iva-cuota-devengada"] > Decimal("0")


def test_evidence_required_scope_rejects_missing_or_wrong_orden() -> None:
    snapshot = _snapshot(2025)
    assert snapshot.filing_period is not None
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED,
    )
    resolved = resolve_m303_regimen_simplificado_snapshot(registry_snapshot=snapshot, scope_decision=scope)
    with pytest.raises(RegistryValidationError, match="requires the canonical annual-Orden"):
        calculate_registry_snapshot(
            snapshot,
            inputs={},
            binding_values={"modelo-303-compensacion-pendiente-anteriores": Decimal("0")},
            date_context={"filing_period": snapshot.filing_period.end_date},
            m303_regimen_simplificado_scope=scope,
            m303_annual_orden=None,
        )
    wrong = resolved.orden.model_copy(update={"registry_revision_id": "2026-y-siguientes"})
    with pytest.raises(RegistryValidationError, match="exact scope-selected registry snapshot"):
        calculate_registry_snapshot(
            snapshot,
            inputs={},
            binding_values={"modelo-303-compensacion-pendiente-anteriores": Decimal("0")},
            date_context={"filing_period": snapshot.filing_period.end_date},
            m303_regimen_simplificado_scope=scope,
            m303_annual_orden=wrong,
        )


def test_general_scope_rejects_annual_orden_even_without_module_inputs() -> None:
    snapshot = _snapshot(2025)
    resolved = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=snapshot,
        scope_decision=_general_scope(),
    )
    with pytest.raises(RegistryValidationError, match="rejects annual-Orden and simplified-regime module inputs"):
        calculate_registry_snapshot(
            snapshot,
            inputs={},
            binding_values={"modelo-303-compensacion-pendiente-anteriores": Decimal("0")},
            date_context={"filing_period": snapshot.filing_period.end_date},
            m303_regimen_simplificado_scope=_general_scope(),
            m303_annual_orden=resolved.orden,
        )


def test_evidence_required_scope_uses_the_captured_annual_orden_snapshot() -> None:
    snapshot = _snapshot(2025)
    assert snapshot.filing_period is not None
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED,
    )
    resolved = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=snapshot,
        scope_decision=scope,
    )
    activity = resolved.orden.activities[0]

    result = calculate_registry_snapshot(
        snapshot,
        inputs={"modulos-iva-1-unidades": Decimal("1")},
        text_inputs={"modulos-iva-orden-id": activity.orden_id},
        binding_values={"modelo-303-compensacion-pendiente-anteriores": Decimal("0")},
        date_context={"filing_period": snapshot.filing_period.end_date},
        m303_regimen_simplificado_scope=scope,
        m303_annual_orden=resolved.orden,
    )

    assert result.values["modulos-iva-cuota-devengada"] == activity.modulos[0].coefficient


def test_missing_scope_blocks_any_m303_calculation() -> None:
    snapshot = _snapshot(2025)
    assert snapshot.filing_period is not None

    with pytest.raises(RegistryValidationError, match="explicit simplified-regime scope decision"):
        calculate_registry_snapshot(
            snapshot,
            inputs={},
            date_context={"filing_period": snapshot.filing_period.end_date},
            m303_regimen_simplificado_scope=None,
            m303_annual_orden=None,
        )


def test_2009_general_scope_computes_official_c47_c48_to_neutral_zero() -> None:
    result = _calculate_general_m303(2022)

    assert result.values["47"] == Decimal("0")
    assert result.values["48"] == Decimal("0")


def test_2009_general_scope_rejects_operator_c47_input() -> None:
    with pytest.raises(RegistryValidationError, match="computed registry casillas"):
        _calculate_general_m303(2022, inputs={"47": Decimal("1")})


def test_canonical_selector_stays_revision_exact_for_s58() -> None:
    snapshot = _snapshot(2025)
    resolved = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=snapshot,
        scope_decision=_general_scope(),
    )
    assert resolved.orden is not None
    selected = next(
        item
        for item in snapshot.m303_annual_orden.projections
        if item.registry_revision_id == resolved.orden.registry_revision_id
    )
    mismatched = selected.model_copy(update={"registry_revision_id": "2026-y-siguientes"})
    authority = snapshot.m303_annual_orden.model_copy(
        update={
            "projections": tuple(
                mismatched if item == selected else item for item in snapshot.m303_annual_orden.projections
            ),
        },
    )
    snapshot_with_mismatch = snapshot.model_copy(update={"m303_annual_orden": authority})

    with pytest.raises(RegistryValidationError, match="has no projection"):
        resolve_m303_regimen_simplificado_snapshot(
            registry_snapshot=snapshot_with_mismatch,
            scope_decision=_general_scope(),
        )


@pytest.mark.parametrize(
    ("module_index", "module_update", "message"),
    (
        (0, {"order": 2}, "complete and ordered"),
        (0, {"coefficient": Decimal("0")}, "positive coefficient"),
    ),
)
def test_authority_rejects_reordered_or_uncoefficiented_module(
    module_index: int,
    module_update: dict[str, int | Decimal],
    message: str,
) -> None:
    resolved = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=_snapshot(2025),
        scope_decision=_general_scope(),
    )
    assert resolved.orden is not None
    activity = resolved.orden.activities[0]
    corrupted_module = activity.modulos[module_index].model_copy(update=module_update)
    payload = activity.model_dump()
    payload["modulos"] = (corrupted_module, *activity.modulos[1:])

    with pytest.raises(ValidationError, match=message):
        ActividadOrdenAnual.model_validate(payload)


def test_formula_runtime_and_registry_fragments_cannot_reintroduce_retired_dispatch_or_advisories() -> None:
    runtime_tree = ast.parse(Path(_formula_runtime.__file__).read_text(encoding="utf-8"))
    function_names = {node.name for node in ast.walk(runtime_tree) if isinstance(node, ast.FunctionDef)}
    assert "_m303_resolve_modulos_iva_cuota_devengada_args" not in function_names
    assert "_m303_resolve_modulos_iva_cuota_minima_pct_args" not in function_names
    assert "M303RegimenSimplificadoEvidenceRequiredError" not in Path(_formula_runtime.__file__).read_text(encoding="utf-8")
    assert FORMULA_OPERATOR_ARITIES["m303_resolve_modulos_iva_cuota_devengada"].minimum == 8
    assert FORMULA_OPERATOR_ARITIES["m303_resolve_modulos_iva_cuota_devengada"].maximum == 8
    assert FORMULA_OPERATOR_ARITIES["m303_resolve_modulos_iva_cuota_minima_pct"].minimum == 1
    assert FORMULA_OPERATOR_ARITIES["m303_resolve_modulos_iva_cuota_minima_pct"].maximum == 1

    revision_ids = ("2023", "2024-hasta-08-y-2t", "2024-desde-09-y-3t", "2025", "2026-y-siguientes")
    revision_root = bundled_path("registry", "aeat", "modelos", "303", "revisions")
    for revision_id in revision_ids:
        revision_root_path = revision_root / revision_id
        assert not (revision_root_path / "parameters" / "0001-modulos-coeficientes.toml").exists()
        assert not (
            revision_root_path / "casillas" / "cmodulos-iva-epigrafe__cmodulos-iva-cuota-derivada.toml"
        ).exists()
        assert (revision_root_path / "casillas" / "cmodulos-iva-orden-id__cmodulos-iva-cuota-derivada.toml").is_file()
        assert not (
            revision_root_path / "verification_expectations" / "0004-regimen-simplificado-orden-authority-refusal.toml"
        ).exists()
        document = tomllib.loads(
            (revision_root_path / "formulas" / "0002-modulos-engine.toml").read_text(encoding="utf-8"),
        )
        formulas = document["revisions"][revision_id]["formulas"]
        devengada = next(
            formula for formula in formulas if formula["expression"]["op"] == "m303_resolve_modulos_iva_cuota_devengada"
        )
        assert len(devengada["expression"]["args"]) == 8
        assert devengada["expression"]["args"][0] == {"casilla_id": "modulos-iva-orden-id"}
        assert "modulos-iva-epigrafe" not in str(document)
        assert "m303-modulos-iva-cuota-devengada-coeficiente" not in str(document)
        assert "m303-modulos-iva-cuota-minima-pct" not in str(document)


def test_production_registry_runtime_caller_census_keeps_m303_scope_explicit() -> None:
    """New runtime callers require a deliberate M303 scope decision."""
    source_root = Path(__file__).parents[4]

    def calls_registry_runtime(source: Path) -> bool:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        return any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"calculate_registry_snapshot", "_calculate_registry_snapshot"}
            for node in ast.walk(tree)
        )

    callers = {
        source.relative_to(source_root).as_posix()
        for source in source_root.rglob("*.py")
        if "/tests/" not in source.as_posix() and calls_registry_runtime(source)
    }
    assert callers == {
        "application/filing/__init__.py",
        "application/modelo/_calculation_actions.py",
        "application/modelo/_calculation_source_staging.py",
        "application/modelo/_projection.py",
        "application/modelo/_taxation_comparison.py",
        "application/registry/__init__.py",
        "application/storage/calc_sheets/_parity_harness.py",
        "adapters/outbound/google/_calc_sheets_pull.py",
    }
    assert "m303_regimen_simplificado_scope=" in (source_root / "application/filing/__init__.py").read_text(
        encoding="utf-8"
    )
    omissions: list[str] = []
    for relative_path in sorted(callers):
        tree = ast.parse((source_root / relative_path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"calculate_registry_snapshot", "_calculate_registry_snapshot"}
                and not all(
                    any(keyword.arg == required for keyword in node.keywords)
                    for required in ("m303_regimen_simplificado_scope", "m303_annual_orden")
                )
            ):
                omissions.append(f"{relative_path}:{node.lineno}")
    assert omissions == []
