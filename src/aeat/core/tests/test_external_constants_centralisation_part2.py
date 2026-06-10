"""Centralisation contract tests (part 2): IVA rate, modelo-ID groups, and renta deduction/amortizacion constants."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# contract — DEFAULT_IVA_GENERAL_RATE_PCT centralisation tests
# ---------------------------------------------------------------------------


def test_default_iva_general_rate_pct_value() -> None:
    """``DEFAULT_IVA_GENERAL_RATE_PCT`` equals 21.00 per LIVA art. 90 Uno."""

    from decimal import Decimal

    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    assert Decimal("21.00") == DEFAULT_IVA_GENERAL_RATE_PCT


def test_default_iva_general_rate_pct_is_final_decimal() -> None:
    """``DEFAULT_IVA_GENERAL_RATE_PCT`` is a ``Decimal`` instance (typed ``Final[Decimal]``)."""

    from decimal import Decimal

    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    assert isinstance(DEFAULT_IVA_GENERAL_RATE_PCT, Decimal)


def test_default_iva_general_rate_pct_matches_registry() -> None:
    """``DEFAULT_IVA_GENERAL_RATE_PCT`` equals the IVA-registry general rate for Spain on 2026-01-01.

    Binds the default to the dated :func:`aeat.domain.iva.lookup_rate` registry so
    it cannot silently drift when AEAT publishes a rate change.
    """

    from datetime import date

    from ...domain.iva import EUMemberState, IvaRateKind, lookup_rate
    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    registry_rate = lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, date(2026, 1, 1))
    assert registry_rate.pct == DEFAULT_IVA_GENERAL_RATE_PCT


def test_inventory_service_imports_default_iva_general_rate_pct_from_core() -> None:
    """``application/inventory/_service.py`` imports ``DEFAULT_IVA_GENERAL_RATE_PCT`` from core."""

    import importlib

    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    mod = importlib.import_module("aeat.application.inventory._service")

    assert hasattr(mod, "DEFAULT_IVA_GENERAL_RATE_PCT"), (
        "_service must import DEFAULT_IVA_GENERAL_RATE_PCT from aeat.core.external_constants"
    )
    assert mod.DEFAULT_IVA_GENERAL_RATE_PCT is DEFAULT_IVA_GENERAL_RATE_PCT


def test_ledger_inventory_cli_imports_default_iva_general_rate_pct_from_core() -> None:
    """``entrypoints/cli/_ledger_inventory_cli.py`` imports ``DEFAULT_IVA_GENERAL_RATE_PCT`` from core."""

    import importlib

    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    mod = importlib.import_module("aeat.entrypoints.cli._ledger_inventory_cli")

    assert hasattr(mod, "DEFAULT_IVA_GENERAL_RATE_PCT"), (
        "_ledger_inventory_cli must import DEFAULT_IVA_GENERAL_RATE_PCT from aeat.core.external_constants"
    )
    assert mod.DEFAULT_IVA_GENERAL_RATE_PCT is DEFAULT_IVA_GENERAL_RATE_PCT


def test_contribuyente_assets_imports_default_iva_general_rate_pct_from_core() -> None:
    """``domain/contribuyente/assets/__init__.py`` imports ``DEFAULT_IVA_GENERAL_RATE_PCT`` from core."""

    import importlib

    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    mod = importlib.import_module("aeat.domain.contribuyente.assets")

    assert hasattr(mod, "DEFAULT_IVA_GENERAL_RATE_PCT"), (
        "aeat.domain.contribuyente.assets must import DEFAULT_IVA_GENERAL_RATE_PCT from aeat.core.external_constants"
    )
    assert mod.DEFAULT_IVA_GENERAL_RATE_PCT is DEFAULT_IVA_GENERAL_RATE_PCT


def test_contribuyente_inventory_imports_default_iva_general_rate_pct_from_core() -> None:
    """``domain/contribuyente/inventory/__init__.py`` imports ``DEFAULT_IVA_GENERAL_RATE_PCT`` from core."""

    import importlib

    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    mod = importlib.import_module("aeat.domain.contribuyente.inventory")

    assert hasattr(mod, "DEFAULT_IVA_GENERAL_RATE_PCT"), (
        "aeat.domain.contribuyente.inventory must import DEFAULT_IVA_GENERAL_RATE_PCT from aeat.core.external_constants"
    )
    assert mod.DEFAULT_IVA_GENERAL_RATE_PCT is DEFAULT_IVA_GENERAL_RATE_PCT


def test_no_bare_iva_rate_decimal_literal_in_inventory_service() -> None:
    """No bare ``Decimal("21.00")`` literal in ``application/inventory/_service.py``.

    Anti-tautology: parses the real AST so any future re-introduction triggers failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/application/inventory/_service.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "21.00":
            offenders.append(f"_service.py:{node.lineno}: bare Decimal('21.00'); use DEFAULT_IVA_GENERAL_RATE_PCT")

    assert offenders == [], (
        "Local IVA 21.00 literals found; import DEFAULT_IVA_GENERAL_RATE_PCT from core instead:\n"
        + "\n".join(offenders)
    )


def test_no_bare_iva_rate_decimal_literal_in_contribuyente_assets() -> None:
    """No bare ``Decimal("21.00")`` literal in ``domain/contribuyente/assets/__init__.py``."""

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/domain/contribuyente/assets/__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "21.00":
            offenders.append(
                f"assets/__init__.py:{node.lineno}: bare Decimal('21.00'); use DEFAULT_IVA_GENERAL_RATE_PCT"
            )

    assert offenders == [], (
        "Local IVA 21.00 literals found in assets; import DEFAULT_IVA_GENERAL_RATE_PCT from core instead:\n"
        + "\n".join(offenders)
    )


def test_no_bare_iva_rate_decimal_literal_in_contribuyente_inventory() -> None:
    """No bare ``Decimal("21.00")`` literal in ``domain/contribuyente/inventory/__init__.py``."""

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/domain/contribuyente/inventory/__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "21.00":
            offenders.append(
                f"inventory/__init__.py:{node.lineno}: bare Decimal('21.00'); use DEFAULT_IVA_GENERAL_RATE_PCT"
            )

    assert offenders == [], (
        "Local IVA 21.00 literals found in inventory; import DEFAULT_IVA_GENERAL_RATE_PCT from core instead:\n"
        + "\n".join(offenders)
    )


def test_no_bare_iva_rate_string_literal_in_ledger_inventory_cli() -> None:
    """No bare ``"21.00"`` string literal as a typer Option default in ``_ledger_inventory_cli.py``.

    Anti-tautology: parses the AST and fails if the literal is re-introduced as a
    bare Option default instead of ``str(DEFAULT_IVA_GENERAL_RATE_PCT)``.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/entrypoints/cli/_ledger_inventory_cli.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        # Look for string constants with value "21.00" that are NOT inside str(...) calls.
        if not isinstance(node, ast.Constant) or node.value != "21.00":
            continue
        offenders.append(
            f"_ledger_inventory_cli.py:{node.lineno}: bare '21.00' string literal; "
            f"use str(DEFAULT_IVA_GENERAL_RATE_PCT)"
        )

    assert offenders == [], (
        "Bare '21.00' string literals found; use str(DEFAULT_IVA_GENERAL_RATE_PCT) instead:\n" + "\n".join(offenders)
    )


def test_no_bare_jsonl_or_xlsx_mime_literal_in_tabular() -> None:
    """No bare JSONL/XLSX MIME literals in ``_tabular.py`` argument positions."""

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/application/export/_tabular.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    guarded_literals = {
        "application/x-ndjson": "_JSONL_MIME_TYPE",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "_XLSX_MIME_TYPE",
    }
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        expected = guarded_literals.get(node.value)
        if expected is None:
            continue
        offenders.append(f"_tabular.py:{node.lineno}: bare {node.value!r} literal; use {expected}")

    assert offenders == [], "Bare JSONL/XLSX MIME literals found:\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# contract — modelo-ID group tuples centralisation tests
# ---------------------------------------------------------------------------


def test_retenciones_modelos_value() -> None:
    """``RETENCIONES_MODELOS`` equals the withholding/retention filing modelo set."""

    from ..external_constants import RETENCIONES_MODELOS

    assert RETENCIONES_MODELOS == ("111", "115", "123", "180", "190", "193")


def test_retenciones_modelos_is_tuple_of_str() -> None:
    """``RETENCIONES_MODELOS`` is a ``tuple`` whose elements are ``str`` instances."""

    from ..external_constants import RETENCIONES_MODELOS

    assert isinstance(RETENCIONES_MODELOS, tuple)
    assert all(isinstance(code, str) for code in RETENCIONES_MODELOS)


def test_counterpart_modelos_value() -> None:
    """``COUNTERPART_MODELOS`` equals the third-party declaration filing modelo set."""

    from ..external_constants import COUNTERPART_MODELOS

    assert COUNTERPART_MODELOS == ("347", "349")


def test_counterpart_modelos_is_tuple_of_str() -> None:
    """``COUNTERPART_MODELOS`` is a ``tuple`` whose elements are ``str`` instances."""

    from ..external_constants import COUNTERPART_MODELOS

    assert isinstance(COUNTERPART_MODELOS, tuple)
    assert all(isinstance(code, str) for code in COUNTERPART_MODELOS)


def test_foreign_asset_modelos_value() -> None:
    """``FOREIGN_ASSET_MODELOS`` equals the overseas-asset declaration modelo set."""

    from ..external_constants import FOREIGN_ASSET_MODELOS

    assert FOREIGN_ASSET_MODELOS == ("720",)


def test_foreign_asset_modelos_is_tuple_of_str() -> None:
    """``FOREIGN_ASSET_MODELOS`` is a ``tuple`` whose elements are ``str`` instances."""

    from ..external_constants import FOREIGN_ASSET_MODELOS

    assert isinstance(FOREIGN_ASSET_MODELOS, tuple)
    assert all(isinstance(code, str) for code in FOREIGN_ASSET_MODELOS)


def test_iva_regime_modelos_value() -> None:
    """``IVA_REGIME_MODELOS`` equals the IVA-regime gating grupo modelo set."""

    from ..external_constants import IVA_REGIME_MODELOS

    assert IVA_REGIME_MODELOS == ("303", "390")


def test_iva_regime_modelos_is_tuple_of_str() -> None:
    """``IVA_REGIME_MODELOS`` is a ``tuple`` whose elements are ``str`` instances."""

    from ..external_constants import IVA_REGIME_MODELOS

    assert isinstance(IVA_REGIME_MODELOS, tuple)
    assert all(isinstance(code, str) for code in IVA_REGIME_MODELOS)


def test_aggregation_service_retenciones_modelos_is_central_constant() -> None:
    """``_service._RETENCIONES_MODELOS`` is the central ``RETENCIONES_MODELOS`` constant."""

    import importlib

    from ..external_constants import RETENCIONES_MODELOS

    mod = importlib.import_module("aeat.application.aggregation._service")

    assert hasattr(mod, "_RETENCIONES_MODELOS"), (
        "_service must alias RETENCIONES_MODELOS from aeat.core.external_constants"
    )
    assert mod._RETENCIONES_MODELOS is RETENCIONES_MODELOS


def test_aggregation_service_counterpart_modelos_is_central_constant() -> None:
    """``_service._COUNTERPART_MODELOS`` is the central ``COUNTERPART_MODELOS`` constant."""

    import importlib

    from ..external_constants import COUNTERPART_MODELOS

    mod = importlib.import_module("aeat.application.aggregation._service")

    assert hasattr(mod, "_COUNTERPART_MODELOS"), (
        "_service must alias COUNTERPART_MODELOS from aeat.core.external_constants"
    )
    assert mod._COUNTERPART_MODELOS is COUNTERPART_MODELOS


def test_aggregation_service_foreign_asset_modelos_is_central_constant() -> None:
    """``_service._FOREIGN_ASSET_MODELOS`` is the central ``FOREIGN_ASSET_MODELOS`` constant."""

    import importlib

    from ..external_constants import FOREIGN_ASSET_MODELOS

    mod = importlib.import_module("aeat.application.aggregation._service")

    assert hasattr(mod, "_FOREIGN_ASSET_MODELOS"), (
        "_service must alias FOREIGN_ASSET_MODELOS from aeat.core.external_constants"
    )
    assert mod._FOREIGN_ASSET_MODELOS is FOREIGN_ASSET_MODELOS


def test_calendar_iva_regime_modelos_is_central_constant() -> None:
    """``_calendar._IVA_REGIME_MODELOS`` is the central ``IVA_REGIME_MODELOS`` constant."""

    import importlib

    from ..external_constants import IVA_REGIME_MODELOS

    mod = importlib.import_module("aeat.application.overview._calendar")

    assert hasattr(mod, "_IVA_REGIME_MODELOS"), (
        "_calendar must alias IVA_REGIME_MODELOS from aeat.core.external_constants"
    )
    assert mod._IVA_REGIME_MODELOS is IVA_REGIME_MODELOS


def _ast_contains_modelo_group_tuple(source: str, expected_elts: tuple[str, ...]) -> bool:
    """Return True if the AST contains a bare tuple literal whose string elements equal ``expected_elts``."""
    tree = ast.parse(source)
    target_set = set(expected_elts)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Tuple):
            continue
        if len(node.elts) != len(expected_elts):
            continue
        if not all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts):
            continue
        if {e.value for e in node.elts if isinstance(e, ast.Constant)} == target_set:
            return True
    return False


def test_no_bare_retenciones_modelos_tuple_literal_in_service() -> None:
    """No bare retenciones-grupo tuple literal in ``application/aggregation/_service.py``.

    Anti-tautology: parses the real AST so any future re-introduction of the
    local constant triggers immediate failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/application/aggregation/_service.py").read_text(encoding="utf-8")

    assert not _ast_contains_modelo_group_tuple(source, ("111", "115", "123", "180", "190", "193")), (
        "Bare retenciones-modelos tuple literal found in _service.py; use RETENCIONES_MODELOS from core"
    )


def test_no_bare_counterpart_modelos_tuple_literal_in_service() -> None:
    """No bare counterpart-grupo tuple literal in ``application/aggregation/_service.py``.

    Anti-tautology: parses the real AST so any future re-introduction triggers failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/application/aggregation/_service.py").read_text(encoding="utf-8")

    assert not _ast_contains_modelo_group_tuple(source, ("347", "349")), (
        "Bare counterpart-modelos tuple literal found in _service.py; use COUNTERPART_MODELOS from core"
    )


def test_no_bare_foreign_asset_modelos_tuple_literal_in_service() -> None:
    """No bare foreign-assets-grupo tuple literal in ``application/aggregation/_service.py``.

    Anti-tautology: parses the real AST so any future re-introduction triggers failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/application/aggregation/_service.py").read_text(encoding="utf-8")

    assert not _ast_contains_modelo_group_tuple(source, ("720",)), (
        "Bare foreign-asset-modelos tuple literal found in _service.py; use FOREIGN_ASSET_MODELOS from core"
    )


def test_no_bare_iva_regime_modelos_tuple_literal_in_calendar() -> None:
    """No bare IVA-regime-grupo tuple literal in ``application/overview/_calendar.py``.

    Anti-tautology: parses the real AST so any future re-introduction triggers failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/application/overview/_calendar.py").read_text(encoding="utf-8")

    assert not _ast_contains_modelo_group_tuple(source, ("303", "390")), (
        "Bare IVA-regime-modelos tuple literal found in _calendar.py; use IVA_REGIME_MODELOS from core"
    )


# ---------------------------------------------------------------------------
# contract — DEDUCCION_MATERNIDAD_MENSUAL_EUR / DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR
# ---------------------------------------------------------------------------


def test_deduccion_maternidad_mensual_eur_value() -> None:
    """``DEDUCCION_MATERNIDAD_MENSUAL_EUR`` equals 100 per Art. 81 LIRPF (Ley 35/2006)."""

    from ..external_constants import DEDUCCION_MATERNIDAD_MENSUAL_EUR

    assert DEDUCCION_MATERNIDAD_MENSUAL_EUR == 100


def test_deduccion_maternidad_anual_cap_eur_value() -> None:
    """``DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR`` equals 1200 per Art. 81 LIRPF (Ley 35/2006)."""

    from ..external_constants import DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR

    assert DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR == 1200


def test_deduccion_maternidad_mensual_eur_is_int() -> None:
    """``DEDUCCION_MATERNIDAD_MENSUAL_EUR`` is an ``int`` (casilla 0611 carries no decimal places)."""

    from ..external_constants import DEDUCCION_MATERNIDAD_MENSUAL_EUR

    assert isinstance(DEDUCCION_MATERNIDAD_MENSUAL_EUR, int)


def test_deduccion_maternidad_anual_cap_eur_is_int() -> None:
    """``DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR`` is an ``int`` (casilla 0611 carries no decimal places)."""

    from ..external_constants import DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR

    assert isinstance(DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR, int)


def test_deduccion_maternidad_monthly_times_12_equals_annual_cap() -> None:
    """12 monthly accruals sum to the annual cap: consistency guard."""

    from ..external_constants import (
        DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR,
        DEDUCCION_MATERNIDAD_MENSUAL_EUR,
    )

    assert DEDUCCION_MATERNIDAD_MENSUAL_EUR * 12 == DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR


def test_deduccion_maternidad_module_imports_mensual_from_core() -> None:
    """``domain/contribuyente/_deduccion_maternidad.py`` reads ``DEDUCCION_MATERNIDAD_MENSUAL_EUR`` from core."""

    import importlib

    from ..external_constants import DEDUCCION_MATERNIDAD_MENSUAL_EUR

    mod = importlib.import_module("aeat.domain.contribuyente._deduccion_maternidad")

    assert hasattr(mod, "DEDUCCION_MATERNIDAD_MENSUAL_EUR"), (
        "_deduccion_maternidad must import DEDUCCION_MATERNIDAD_MENSUAL_EUR from aeat.core.external_constants"
    )
    assert mod.DEDUCCION_MATERNIDAD_MENSUAL_EUR is DEDUCCION_MATERNIDAD_MENSUAL_EUR


def test_deduccion_maternidad_module_imports_anual_cap_from_core() -> None:
    """``domain/contribuyente/_deduccion_maternidad.py`` reads ``DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR`` from core."""

    import importlib

    from ..external_constants import DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR

    mod = importlib.import_module("aeat.domain.contribuyente._deduccion_maternidad")

    assert hasattr(mod, "DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR"), (
        "_deduccion_maternidad must import DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR from aeat.core.external_constants"
    )
    assert mod.DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR is DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR


def test_family_module_imports_deduccion_maternidad_constants_from_core() -> None:
    """``domain/contribuyente/family.py`` reads both maternidad constants from core."""

    import importlib

    from ..external_constants import (
        DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR,
        DEDUCCION_MATERNIDAD_MENSUAL_EUR,
    )

    mod = importlib.import_module("aeat.domain.contribuyente.family")

    assert hasattr(mod, "DEDUCCION_MATERNIDAD_MENSUAL_EUR"), (
        "family must import DEDUCCION_MATERNIDAD_MENSUAL_EUR from aeat.core.external_constants"
    )
    assert hasattr(mod, "DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR"), (
        "family must import DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR from aeat.core.external_constants"
    )
    assert mod.DEDUCCION_MATERNIDAD_MENSUAL_EUR is DEDUCCION_MATERNIDAD_MENSUAL_EUR
    assert mod.DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR is DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR


def test_no_bare_1200_maternidad_cap_literal_in_family() -> None:
    """No bare ``1200`` integer literal as a ``min()`` argument in ``family.py``.

    Anti-tautology: parses the real AST so any re-introduction of the local literal triggers failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/domain/contribuyente/family.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "min":
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and arg.value == 1200:
                offenders.append(
                    f"family.py:{node.lineno}: bare 1200 literal in min(); use DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR"
                )

    assert offenders == [], "Bare 1200 maternidad cap literals found in family.py:\n" + "\n".join(offenders)


def test_no_bare_1200_maternidad_cap_literal_in_deduccion_maternidad() -> None:
    """No bare ``1200`` integer literal as a ``min()`` argument in ``_deduccion_maternidad.py``.

    Anti-tautology: parses the real AST so any re-introduction triggers failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/domain/contribuyente/_deduccion_maternidad.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "min":
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and arg.value == 1200:
                offenders.append(
                    f"_deduccion_maternidad.py:{node.lineno}: bare 1200 literal in min(); "
                    f"use DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR"
                )

    assert offenders == [], "Bare 1200 maternidad cap literals found in _deduccion_maternidad.py:\n" + "\n".join(
        offenders
    )


# ---------------------------------------------------------------------------
# contract — INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR centralisation tests
# ---------------------------------------------------------------------------


def test_incremento_guarderia_por_hijo_cap_eur_value() -> None:
    """``INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR`` equals 1000 per Art. 81 LIRPF (Ley 35/2006)."""

    from ..external_constants import INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR

    assert INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR == 1000


def test_incremento_guarderia_por_hijo_cap_eur_is_int() -> None:
    """``INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR`` is an ``int`` (casilla 0613 carries no decimal places)."""

    from ..external_constants import INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR

    assert isinstance(INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR, int)


def test_family_module_imports_incremento_guarderia_cap_from_core() -> None:
    """``domain/contribuyente/family.py`` reads ``INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR`` from core."""

    import importlib

    from ..external_constants import INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR

    mod = importlib.import_module("aeat.domain.contribuyente.family")

    assert hasattr(mod, "INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR"), (
        "family must import INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR from aeat.core.external_constants"
    )
    assert mod.INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR is INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR


def test_no_bare_1000_guarderia_cap_literal_in_family() -> None:
    """No bare ``1000`` integer literal as a ``min()`` argument in ``family.py``.

    Anti-tautology: parses the real AST so any re-introduction of the local literal triggers failure.
    Scoped to ``min()`` calls to avoid false positives from unrelated integer constants.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/domain/contribuyente/family.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "min":
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and arg.value == 1000:
                offenders.append(
                    f"family.py:{node.lineno}: bare 1000 literal in min(); use INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR"
                )

    assert offenders == [], "Bare 1000 guarderia cap literals found in family.py:\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# contract — AMORTIZACION_INMUEBLE_RATE centralisation tests
# ---------------------------------------------------------------------------


def test_amortizacion_inmueble_rate_value() -> None:
    """``AMORTIZACION_INMUEBLE_RATE`` equals 0.03 per RD 439/2007 (RIRPF) art. 14.2.a."""

    from decimal import Decimal

    from ..external_constants import AMORTIZACION_INMUEBLE_RATE

    assert Decimal("0.03") == AMORTIZACION_INMUEBLE_RATE


def test_amortizacion_inmueble_rate_is_final_decimal() -> None:
    """``AMORTIZACION_INMUEBLE_RATE`` is a ``Decimal`` instance (typed ``Final[Decimal]``)."""

    from decimal import Decimal

    from ..external_constants import AMORTIZACION_INMUEBLE_RATE

    assert isinstance(AMORTIZACION_INMUEBLE_RATE, Decimal)


def test_amortization_ledger_imports_amortizacion_inmueble_rate_from_core() -> None:
    """``domain/fincas/_amortization_ledger.py`` reads ``AMORTIZACION_INMUEBLE_RATE`` from core."""

    import importlib

    from ..external_constants import AMORTIZACION_INMUEBLE_RATE

    mod = importlib.import_module("aeat.domain.fincas._amortization_ledger")

    assert hasattr(mod, "AMORTIZACION_INMUEBLE_RATE"), (
        "_amortization_ledger must import AMORTIZACION_INMUEBLE_RATE from aeat.core.external_constants"
    )
    assert mod.AMORTIZACION_INMUEBLE_RATE is AMORTIZACION_INMUEBLE_RATE


def test_amortization_ledger_art_23_alias_equals_core_constant() -> None:
    """``ART_23_1_F_RATE`` in ``_amortization_ledger.py`` is identical to ``AMORTIZACION_INMUEBLE_RATE``."""

    import importlib

    from ..external_constants import AMORTIZACION_INMUEBLE_RATE

    mod = importlib.import_module("aeat.domain.fincas._amortization_ledger")

    assert hasattr(mod, "ART_23_1_F_RATE"), "_amortization_ledger must expose ART_23_1_F_RATE alias"
    assert mod.ART_23_1_F_RATE is AMORTIZACION_INMUEBLE_RATE


def test_no_bare_amortizacion_decimal_literal_in_amortization_ledger() -> None:
    """No bare ``Decimal("0.03")`` literal in ``domain/fincas/_amortization_ledger.py``.

    Anti-tautology: parses the real AST so any re-introduction triggers failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/domain/fincas/_amortization_ledger.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "0.03":
            offenders.append(
                f"_amortization_ledger.py:{node.lineno}: bare Decimal('0.03'); use AMORTIZACION_INMUEBLE_RATE"
            )

    assert offenders == [], (
        "Bare Decimal('0.03') amortization literals found; import AMORTIZACION_INMUEBLE_RATE from core instead:\n"
        + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# contract — REBECA_MARITIME_EXEMPTION_FRACTION centralisation tests
# ---------------------------------------------------------------------------


def test_rebeca_maritime_exemption_fraction_value() -> None:
    """``REBECA_MARITIME_EXEMPTION_FRACTION`` equals 0.50 per Ley 19/1994 arts. 73/75."""

    from decimal import Decimal

    from ..external_constants import REBECA_MARITIME_EXEMPTION_FRACTION

    assert Decimal("0.50") == REBECA_MARITIME_EXEMPTION_FRACTION


def test_rebeca_maritime_exemption_fraction_is_final_decimal() -> None:
    """``REBECA_MARITIME_EXEMPTION_FRACTION`` is a ``Decimal`` instance (typed ``Final[Decimal]``)."""

    from decimal import Decimal

    from ..external_constants import REBECA_MARITIME_EXEMPTION_FRACTION

    assert isinstance(REBECA_MARITIME_EXEMPTION_FRACTION, Decimal)


def test_maritime_exemption_imports_rebeca_fraction_from_core() -> None:
    """``domain/renta/_maritime_exemption.py`` reads ``REBECA_MARITIME_EXEMPTION_FRACTION`` from core."""

    import importlib

    from ..external_constants import REBECA_MARITIME_EXEMPTION_FRACTION

    mod = importlib.import_module("aeat.domain.renta._maritime_exemption")

    assert hasattr(mod, "REBECA_MARITIME_EXEMPTION_FRACTION"), (
        "_maritime_exemption must import REBECA_MARITIME_EXEMPTION_FRACTION from aeat.core.external_constants"
    )
    assert mod.REBECA_MARITIME_EXEMPTION_FRACTION is REBECA_MARITIME_EXEMPTION_FRACTION


def test_no_bare_rebeca_fraction_decimal_literal_in_maritime_exemption() -> None:
    """No bare ``Decimal("0.50")`` literal in ``domain/renta/_maritime_exemption.py``.

    Anti-tautology: parses the real AST so any re-introduction of the local literal triggers failure.
    Scoped to the REBECA calculation; does not flag Decimal("0") or other unrelated values.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/domain/renta/_maritime_exemption.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "0.50":
            offenders.append(
                f"_maritime_exemption.py:{node.lineno}: bare Decimal('0.50'); use REBECA_MARITIME_EXEMPTION_FRACTION"
            )

    assert offenders == [], (
        "Bare Decimal('0.50') REBECA literals found; import REBECA_MARITIME_EXEMPTION_FRACTION from core instead:\n"
        + "\n".join(offenders)
    )
