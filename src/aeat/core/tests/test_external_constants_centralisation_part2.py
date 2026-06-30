"""Centralisation contract tests (part 2): IVA rate, modelo-ID groups, and renta deduction/amortizacion constants."""

from __future__ import annotations

import ast
import importlib
from decimal import Decimal
from pathlib import Path

import pytest

from ...tests._inventory import leaf_name

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_REPO_ROOT = Path(__file__).parents[4]


def _repo_source(relative_path: str) -> str:
    return (_REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _repo_tree(relative_path: str) -> ast.AST:
    return ast.parse(_repo_source(relative_path))


def _assert_module_constant_identity(
    *,
    module_name: str,
    attr_name: str,
    expected: object,
    import_message: str,
) -> None:
    mod = importlib.import_module(module_name)

    assert hasattr(mod, attr_name), import_message
    assert getattr(mod, attr_name) is expected


def _decimal_call_literal_offenders(
    *,
    relative_path: str,
    display_path: str,
    literal: str,
    replacement: str,
) -> list[str]:
    offenders: list[str] = []
    for node in ast.walk(_repo_tree(relative_path)):
        if not isinstance(node, ast.Call):
            continue
        if leaf_name(node.func) != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == literal:
            offenders.append(f"{display_path}:{node.lineno}: bare Decimal({literal!r}); use {replacement}")
    return offenders


def _min_arg_literal_offenders(
    *,
    relative_path: str,
    display_path: str,
    literal: int,
    replacement: str,
) -> list[str]:
    offenders: list[str] = []
    for node in ast.walk(_repo_tree(relative_path)):
        if not isinstance(node, ast.Call):
            continue
        if leaf_name(node.func) != "min":
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and arg.value == literal:
                offenders.append(f"{display_path}:{node.lineno}: bare {literal} literal in min(); use {replacement}")
    return offenders


_DEFAULT_IVA_IMPORT_CASES: tuple[tuple[str, str], ...] = (
    (
        "aeat.application.inventory._service",
        "_service must import DEFAULT_IVA_GENERAL_RATE_PCT from aeat.core.external_constants",
    ),
    (
        "aeat.entrypoints.cli._ledger_inventory_cli",
        "_ledger_inventory_cli must import DEFAULT_IVA_GENERAL_RATE_PCT from aeat.core.external_constants",
    ),
    (
        "aeat.domain.contribuyente.assets",
        "aeat.domain.contribuyente.assets must import DEFAULT_IVA_GENERAL_RATE_PCT from aeat.core.external_constants",
    ),
    (
        "aeat.domain.contribuyente.inventory",
        "contribuyente.inventory must import DEFAULT_IVA_GENERAL_RATE_PCT from aeat.core.external_constants",
    ),
)
_DEFAULT_IVA_IMPORT_IDS = (
    "inventory-service",
    "ledger-inventory-cli",
    "contribuyente-assets",
    "contribuyente-inventory",
)

_IVA_DECIMAL_LITERAL_CASES: tuple[tuple[str, str, str], ...] = (
    (
        "src/aeat/application/inventory/_service.py",
        "_service.py",
        "DEFAULT_IVA_GENERAL_RATE_PCT",
    ),
    (
        "src/aeat/domain/contribuyente/assets/__init__.py",
        "assets/__init__.py",
        "DEFAULT_IVA_GENERAL_RATE_PCT",
    ),
    (
        "src/aeat/domain/contribuyente/inventory/__init__.py",
        "inventory/__init__.py",
        "DEFAULT_IVA_GENERAL_RATE_PCT",
    ),
)
_IVA_DECIMAL_LITERAL_IDS = ("inventory-service", "contribuyente-assets", "contribuyente-inventory")

_MODELO_GROUP_CASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("RETENCIONES_MODELOS", ("111", "115", "123", "180", "190", "193")),
    ("COUNTERPART_MODELOS", ("347", "349")),
    ("FOREIGN_ASSET_MODELOS", ("720",)),
    ("IVA_REGIME_MODELOS", ("303", "390")),
)
_MODELO_GROUP_IDS = ("retenciones", "counterpart", "foreign-asset", "iva-regime")

_MODELO_GROUP_ALIAS_CASES: tuple[tuple[str, str, str, str], ...] = (
    (
        "aeat.application.aggregation._service",
        "_RETENCIONES_MODELOS",
        "RETENCIONES_MODELOS",
        "_service must alias RETENCIONES_MODELOS from aeat.core.external_constants",
    ),
    (
        "aeat.application.aggregation._service",
        "_COUNTERPART_MODELOS",
        "COUNTERPART_MODELOS",
        "_service must alias COUNTERPART_MODELOS from aeat.core.external_constants",
    ),
    (
        "aeat.application.aggregation._service",
        "_FOREIGN_ASSET_MODELOS",
        "FOREIGN_ASSET_MODELOS",
        "_service must alias FOREIGN_ASSET_MODELOS from aeat.core.external_constants",
    ),
    (
        "aeat.application.overview._calendar",
        "_IVA_REGIME_MODELOS",
        "IVA_REGIME_MODELOS",
        "_calendar must alias IVA_REGIME_MODELOS from aeat.core.external_constants",
    ),
)

_MODELO_GROUP_LITERAL_CASES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "src/aeat/application/aggregation/_service.py",
        ("111", "115", "123", "180", "190", "193"),
        "Bare retenciones-modelos tuple literal found in _service.py; use RETENCIONES_MODELOS from core",
    ),
    (
        "src/aeat/application/aggregation/_service.py",
        ("347", "349"),
        "Bare counterpart-modelos tuple literal found in _service.py; use COUNTERPART_MODELOS from core",
    ),
    (
        "src/aeat/application/aggregation/_service.py",
        ("720",),
        "Bare foreign-asset-modelos tuple literal found in _service.py; use FOREIGN_ASSET_MODELOS from core",
    ),
    (
        "src/aeat/application/overview/_calendar.py",
        ("303", "390"),
        "Bare IVA-regime-modelos tuple literal found in _calendar.py; use IVA_REGIME_MODELOS from core",
    ),
)

_IRPF_INT_CONSTANT_CASES: tuple[tuple[str, int], ...] = (
    ("DEDUCCION_MATERNIDAD_MENSUAL_EUR", 100),
    ("DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR", 1200),
    ("INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR", 1000),
)
_IRPF_INT_CONSTANT_IDS = ("maternidad-mensual", "maternidad-anual-cap", "guarderia-cap")

_IRPF_INT_ALIAS_CASES: tuple[tuple[str, str, str, str], ...] = (
    (
        "aeat.domain.contribuyente._deduccion_maternidad",
        "DEDUCCION_MATERNIDAD_MENSUAL_EUR",
        "DEDUCCION_MATERNIDAD_MENSUAL_EUR",
        "_deduccion_maternidad must import DEDUCCION_MATERNIDAD_MENSUAL_EUR from aeat.core.external_constants",
    ),
    (
        "aeat.domain.contribuyente._deduccion_maternidad",
        "DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR",
        "DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR",
        "_deduccion_maternidad must import DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR from aeat.core.external_constants",
    ),
    (
        "aeat.domain.contribuyente.family",
        "DEDUCCION_MATERNIDAD_MENSUAL_EUR",
        "DEDUCCION_MATERNIDAD_MENSUAL_EUR",
        "family must import DEDUCCION_MATERNIDAD_MENSUAL_EUR from aeat.core.external_constants",
    ),
    (
        "aeat.domain.contribuyente.family",
        "DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR",
        "DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR",
        "family must import DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR from aeat.core.external_constants",
    ),
    (
        "aeat.domain.contribuyente.family",
        "INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR",
        "INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR",
        "family must import INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR from aeat.core.external_constants",
    ),
)
_IRPF_INT_ALIAS_IDS = (
    "deduccion-maternidad-mensual",
    "deduccion-maternidad-anual-cap",
    "family-maternidad-mensual",
    "family-maternidad-anual-cap",
    "family-guarderia-cap",
)

_MIN_LITERAL_CASES: tuple[tuple[str, str, int, str, str], ...] = (
    (
        "src/aeat/domain/contribuyente/family.py",
        "family.py",
        1200,
        "DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR",
        "Bare 1200 maternidad cap literals found in family.py",
    ),
    (
        "src/aeat/domain/contribuyente/_deduccion_maternidad.py",
        "_deduccion_maternidad.py",
        1200,
        "DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR",
        "Bare 1200 maternidad cap literals found in _deduccion_maternidad.py",
    ),
    (
        "src/aeat/domain/contribuyente/family.py",
        "family.py",
        1000,
        "INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR",
        "Bare 1000 guarderia cap literals found in family.py",
    ),
)
_MIN_LITERAL_IDS = ("family-maternidad", "deduccion-maternidad", "family-guarderia")

_DECIMAL_CONSTANT_CASES: tuple[tuple[str, str], ...] = (
    ("DEFAULT_IVA_GENERAL_RATE_PCT", "21.00"),
    ("AMORTIZACION_INMUEBLE_RATE", "0.03"),
    ("REBECA_MARITIME_EXEMPTION_FRACTION", "0.50"),
)
_DECIMAL_CONSTANT_IDS = ("default-iva-general-rate", "amortizacion-inmueble-rate", "rebeca-maritime-fraction")

_DECIMAL_ALIAS_CASES: tuple[tuple[str, str, str, str], ...] = (
    (
        "aeat.domain.fincas._amortization_ledger",
        "AMORTIZACION_INMUEBLE_RATE",
        "AMORTIZACION_INMUEBLE_RATE",
        "_amortization_ledger must import AMORTIZACION_INMUEBLE_RATE from aeat.core.external_constants",
    ),
    (
        "aeat.domain.fincas._amortization_ledger",
        "ART_23_1_F_RATE",
        "AMORTIZACION_INMUEBLE_RATE",
        "_amortization_ledger must expose ART_23_1_F_RATE alias",
    ),
    (
        "aeat.domain.renta._maritime_exemption",
        "REBECA_MARITIME_EXEMPTION_FRACTION",
        "REBECA_MARITIME_EXEMPTION_FRACTION",
        "_maritime_exemption must import REBECA_MARITIME_EXEMPTION_FRACTION from aeat.core.external_constants",
    ),
)
_DECIMAL_ALIAS_IDS = ("amortization-rate", "amortization-art-23-alias", "rebeca-fraction")

_DECIMAL_LITERAL_CASES: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "src/aeat/domain/fincas/_amortization_ledger.py",
        "_amortization_ledger.py",
        "0.03",
        "AMORTIZACION_INMUEBLE_RATE",
        "Bare Decimal('0.03') amortization literals found",
    ),
    (
        "src/aeat/domain/renta/_maritime_exemption.py",
        "_maritime_exemption.py",
        "0.50",
        "REBECA_MARITIME_EXEMPTION_FRACTION",
        "Bare Decimal('0.50') REBECA literals found",
    ),
)
_DECIMAL_LITERAL_IDS = ("amortization-rate", "rebeca-fraction")


# ---------------------------------------------------------------------------
# contract — DEFAULT_IVA_GENERAL_RATE_PCT centralisation tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("constant_name", "expected"), _DECIMAL_CONSTANT_CASES, ids=_DECIMAL_CONSTANT_IDS)
def test_decimal_external_constant_values(constant_name: str, expected: str) -> None:
    """Decimal external constants equal their legal scalar values."""

    from .. import external_constants

    assert Decimal(expected) == getattr(external_constants, constant_name)


@pytest.mark.parametrize(("constant_name", "expected"), _DECIMAL_CONSTANT_CASES, ids=_DECIMAL_CONSTANT_IDS)
def test_decimal_external_constants_are_decimal(constant_name: str, expected: str) -> None:
    """Decimal external constants are ``Decimal`` instances."""

    from .. import external_constants

    value = getattr(external_constants, constant_name)
    assert isinstance(value, Decimal)
    assert value == Decimal(expected)


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


@pytest.mark.parametrize(
    ("module_name", "message"),
    _DEFAULT_IVA_IMPORT_CASES,
    ids=_DEFAULT_IVA_IMPORT_IDS,
)
def test_modules_import_default_iva_general_rate_pct_from_core(
    module_name: str,
    message: str,
) -> None:
    """Known consumers import ``DEFAULT_IVA_GENERAL_RATE_PCT`` from core."""

    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    _assert_module_constant_identity(
        module_name=module_name,
        attr_name="DEFAULT_IVA_GENERAL_RATE_PCT",
        expected=DEFAULT_IVA_GENERAL_RATE_PCT,
        import_message=message,
    )


@pytest.mark.parametrize(
    ("relative_path", "display_path", "replacement"),
    _IVA_DECIMAL_LITERAL_CASES,
    ids=_IVA_DECIMAL_LITERAL_IDS,
)
def test_no_bare_iva_rate_decimal_literal_in_consumers(
    relative_path: str,
    display_path: str,
    replacement: str,
) -> None:
    """No bare ``Decimal("21.00")`` literal in IVA rate consumers."""

    offenders = _decimal_call_literal_offenders(
        relative_path=relative_path,
        display_path=display_path,
        literal="21.00",
        replacement=replacement,
    )

    assert offenders == [], (
        f"Local IVA 21.00 literals found in {display_path}; import DEFAULT_IVA_GENERAL_RATE_PCT from core instead:\n"
        + "\n".join(offenders)
    )


def test_no_bare_iva_rate_string_literal_in_ledger_inventory_cli() -> None:
    """No bare ``"21.00"`` string literal as a typer Option default in ``_ledger_inventory_cli.py``.

    Anti-tautology: parses the AST and fails if the literal is re-introduced as a
    bare Option default instead of ``str(DEFAULT_IVA_GENERAL_RATE_PCT)``.
    """

    tree = _repo_tree("src/aeat/entrypoints/cli/_ledger_inventory_cli.py")

    offenders: list[str] = []
    for node in ast.walk(tree):
        # Look for string constants with value "21.00" that are NOT inside str(...) calls.
        if not isinstance(node, ast.Constant) or node.value != "21.00":
            continue
        offenders.append(
            f"_ledger_inventory_cli.py:{node.lineno}: bare '21.00' string literal; "
            f"use str(DEFAULT_IVA_GENERAL_RATE_PCT)",
        )

    assert offenders == [], (
        "Bare '21.00' string literals found; use str(DEFAULT_IVA_GENERAL_RATE_PCT) instead:\n" + "\n".join(offenders)
    )


def test_no_bare_jsonl_or_xlsx_mime_literal_in_tabular() -> None:
    """No bare JSONL/XLSX MIME literals in ``_tabular.py`` argument positions."""

    tree = _repo_tree("src/aeat/application/export/_tabular.py")

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


@pytest.mark.parametrize(("constant_name", "expected"), _MODELO_GROUP_CASES, ids=_MODELO_GROUP_IDS)
def test_modelo_group_values(constant_name: str, expected: tuple[str, ...]) -> None:
    """Modelo group constants equal their authoritative modelo tuples."""

    from .. import external_constants

    assert getattr(external_constants, constant_name) == expected


@pytest.mark.parametrize(("constant_name", "expected"), _MODELO_GROUP_CASES, ids=_MODELO_GROUP_IDS)
def test_modelo_groups_are_tuples_of_str(constant_name: str, expected: tuple[str, ...]) -> None:
    """Modelo group constants are tuples whose elements are strings."""

    from .. import external_constants

    value = getattr(external_constants, constant_name)
    assert isinstance(value, tuple)
    assert all(isinstance(code, str) for code in value)
    assert len(value) == len(expected)


@pytest.mark.parametrize(
    ("module_name", "module_attr", "constant_name", "message"),
    _MODELO_GROUP_ALIAS_CASES,
    ids=_MODELO_GROUP_IDS,
)
def test_modelo_group_consumers_alias_central_constants(
    module_name: str,
    module_attr: str,
    constant_name: str,
    message: str,
) -> None:
    """Known consumers alias modelo group constants from core."""

    from .. import external_constants

    _assert_module_constant_identity(
        module_name=module_name,
        attr_name=module_attr,
        expected=getattr(external_constants, constant_name),
        import_message=message,
    )


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


@pytest.mark.parametrize(
    ("relative_path", "expected_elts", "message"),
    _MODELO_GROUP_LITERAL_CASES,
    ids=_MODELO_GROUP_IDS,
)
def test_no_bare_modelo_group_tuple_literals_in_consumers(
    relative_path: str,
    expected_elts: tuple[str, ...],
    message: str,
) -> None:
    """No bare modelo group tuple literals in consumers."""

    assert not _ast_contains_modelo_group_tuple(_repo_source(relative_path), expected_elts), message


# ---------------------------------------------------------------------------
# contract — DEDUCCION_MATERNIDAD_MENSUAL_EUR / DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("constant_name", "expected"), _IRPF_INT_CONSTANT_CASES, ids=_IRPF_INT_CONSTANT_IDS)
def test_irpf_int_constant_values(constant_name: str, expected: int) -> None:
    """IRPF integer constants equal their legal scalar values."""

    from .. import external_constants

    assert getattr(external_constants, constant_name) == expected


@pytest.mark.parametrize(("constant_name", "expected"), _IRPF_INT_CONSTANT_CASES, ids=_IRPF_INT_CONSTANT_IDS)
def test_irpf_int_constants_are_int(constant_name: str, expected: int) -> None:
    """IRPF euro constants are ``int`` values because the target casillas carry no decimals."""

    from .. import external_constants

    value = getattr(external_constants, constant_name)
    assert isinstance(value, int)
    assert value == expected


def test_deduccion_maternidad_monthly_times_12_equals_annual_cap() -> None:
    """12 monthly accruals sum to the annual cap: consistency guard."""

    from ..external_constants import (
        DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR,
        DEDUCCION_MATERNIDAD_MENSUAL_EUR,
    )

    assert DEDUCCION_MATERNIDAD_MENSUAL_EUR * 12 == DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR


@pytest.mark.parametrize(
    ("module_name", "module_attr", "constant_name", "message"),
    _IRPF_INT_ALIAS_CASES,
    ids=_IRPF_INT_ALIAS_IDS,
)
def test_irpf_int_constant_consumers_alias_core_constants(
    module_name: str,
    module_attr: str,
    constant_name: str,
    message: str,
) -> None:
    """Known consumers alias IRPF integer constants from core."""

    from .. import external_constants

    _assert_module_constant_identity(
        module_name=module_name,
        attr_name=module_attr,
        expected=getattr(external_constants, constant_name),
        import_message=message,
    )


# ---------------------------------------------------------------------------
# contract — INCREMENTO_GUARDERIA_POR_HIJO_CAP_EUR centralisation tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("relative_path", "display_path", "literal", "replacement", "message"),
    _MIN_LITERAL_CASES,
    ids=_MIN_LITERAL_IDS,
)
def test_no_bare_irpf_cap_literals_in_min_calls(
    relative_path: str,
    display_path: str,
    literal: int,
    replacement: str,
    message: str,
) -> None:
    """No bare IRPF cap literals appear as ``min()`` arguments in consumers."""

    offenders = _min_arg_literal_offenders(
        relative_path=relative_path,
        display_path=display_path,
        literal=literal,
        replacement=replacement,
    )

    assert offenders == [], message + ":\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# contract — Decimal-rate consumer centralisation tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("module_name", "module_attr", "constant_name", "message"),
    _DECIMAL_ALIAS_CASES,
    ids=_DECIMAL_ALIAS_IDS,
)
def test_decimal_constant_consumers_alias_core_constants(
    module_name: str,
    module_attr: str,
    constant_name: str,
    message: str,
) -> None:
    """Known consumers alias Decimal constants from core."""

    from .. import external_constants

    _assert_module_constant_identity(
        module_name=module_name,
        attr_name=module_attr,
        expected=getattr(external_constants, constant_name),
        import_message=message,
    )


@pytest.mark.parametrize(
    ("relative_path", "display_path", "literal", "replacement", "message"),
    _DECIMAL_LITERAL_CASES,
    ids=_DECIMAL_LITERAL_IDS,
)
def test_no_bare_decimal_literals_in_consumers(
    relative_path: str,
    display_path: str,
    literal: str,
    replacement: str,
    message: str,
) -> None:
    """No bare Decimal literals in Decimal-constant consumers."""

    offenders = _decimal_call_literal_offenders(
        relative_path=relative_path,
        display_path=display_path,
        literal=literal,
        replacement=replacement,
    )

    assert offenders == [], message + ":\n" + "\n".join(offenders)
