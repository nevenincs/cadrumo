"""The observed-casilla accessor refuses to read a non-numeric casilla as an amount.

No gate covers this. The string-to-Decimal enrollment gate governs ``entrypoints/``
and ``application/`` only, so this adapter is outside its scope, and its matcher
resolves no attribute types so it would not see an attribute read even in scope.
The type checker does not help either: every member of a ``Decimal | str | bool``
union satisfies ``Decimal.__new__``, so a consumer that skipped the migration
compiles clean. These tests are the enforcement.

The two text cases are not invented. They were measured on the real redacted
Modelo 100 2023 artefact, where the tokens for casilla ``0065`` (clave) and
``0167`` (epígrafe IAE) both convert to plausible wrong numbers.
"""

from __future__ import annotations

import ast
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pytest

from ......core import CasillaValueKind, validated_casilla_id
from ......core.directory_scan import scan_directory
from .._declarations_observations import _observed_value_kind, non_numeric_observed_casillas
from .._schema import ObservedCasillaSkip, ObservedCasillaValue
from ..errors import SedeValidationError
from ._declarations_support import _filed_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SRC_ROOT = Path(__file__).resolve().parents[5]
_M100_NUMERIC_CASILLA = validated_casilla_id("0224", surface="test_observed_casilla_value_kind")


def _carrier(value: str, kind: CasillaValueKind) -> ObservedCasillaValue:
    return ObservedCasillaValue(
        casilla_id=validated_casilla_id("0224", surface="test_observed_casilla_value_kind"),
        value=value,
        value_kind=kind,
        source_artefact_kind="submitted_file",
        source_locator="field:0224",
        confidence=1.0,
    )


def test_numeric_casilla_reads_as_its_amount() -> None:
    assert _carrier("1234.56", CasillaValueKind.NUMERIC).decimal_value() == Decimal("1234.56")


@pytest.mark.parametrize("token", ["15", "22"])
def test_text_casilla_that_looks_numeric_refuses(token: str) -> None:
    """A clave and an epígrafe IAE parse cleanly and mean nothing as numbers.

    This is the assertion the whole discriminator exists for: `Decimal("15")`
    succeeds, so only the declared kind can refuse it.
    """
    with pytest.raises(SedeValidationError, match="not numeric"):
        _carrier(token, CasillaValueKind.TEXT).decimal_value()


@pytest.mark.parametrize("token", ["S", "N", "1", "0"])
def test_boolean_casilla_refuses_including_the_digit_spellings(token: str) -> None:
    """A yes/no marker is never an amount, and ``1``/``0`` are the dangerous pair.

    A bare ``Decimal(True)`` returns ``Decimal('1')``, so a boolean read as a
    number does not fail -- it silently becomes the quantity one.
    """
    with pytest.raises(SedeValidationError, match="not numeric"):
        _carrier(token, CasillaValueKind.BOOLEAN).decimal_value()


def test_numeric_casilla_with_an_unreadable_token_still_raises() -> None:
    """The kind guard does not suppress a genuine parse failure."""
    with pytest.raises(InvalidOperation):
        _carrier("no-decimal", CasillaValueKind.NUMERIC).decimal_value()


def test_kind_and_token_rules_agree_on_what_a_boolean_is() -> None:
    """The kind and the stored spelling answer one question and must not diverge.

    A value spelled with the artefact's own boolean token while labelled numeric
    is exactly the disagreement the kind exists to prevent.
    """
    assert _observed_value_kind(True) is CasillaValueKind.BOOLEAN
    assert _observed_value_kind(False) is CasillaValueKind.BOOLEAN
    assert _observed_value_kind(Decimal("1")) is CasillaValueKind.NUMERIC
    assert _observed_value_kind(1) is CasillaValueKind.NUMERIC
    assert _observed_value_kind("CL SANITIZADA") is CasillaValueKind.TEXT


def _decimal_on_dot_value_sites(tree: ast.AST) -> list[int]:
    """Return line numbers of ``Decimal(<expr>.value)`` calls."""
    found: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "Decimal" or len(node.args) != 1:
            continue
        argument = node.args[0]
        if isinstance(argument, ast.Attribute) and argument.attr == "value":
            found.append(node.lineno)
    return found


def test_skip_row_model_declares_no_value_field() -> None:
    """The skip record must never gain a value field.

    Its rows name the non-numeric casillas, which on Modelo 100 include a
    referencia catastral and the taxpayer's street address, and the rows exist to
    be rendered to an operator. A value field would put personal data on that
    surface, so this asserts the shape rather than trusting the docstring.
    """
    fields = set(ObservedCasillaSkip.model_fields)
    assert fields == {"casilla_id", "label", "value_kind", "reason"}
    assert "value" not in fields


def test_skip_query_returns_empty_when_every_casilla_is_numeric() -> None:
    """An all-numeric observation reports nothing, so a caller can trust silence."""
    observation = _filed_observation(
        modelo="100",
        ejercicio=2025,
        period="0A",
        casilla_values={_M100_NUMERIC_CASILLA: Decimal("1234.56")},
    )

    assert non_numeric_observed_casillas(observation) == ()


def test_skip_query_names_a_text_casilla_without_disclosing_its_value() -> None:
    """The row identifies the casilla and its label, never what it holds."""
    filed_address = "CL SANITIZADA 0000 LOCALIDAD"
    observation = _filed_observation(
        modelo="100",
        ejercicio=2025,
        period="0A",
        casilla_values={_M100_NUMERIC_CASILLA: filed_address},
    )

    skips = non_numeric_observed_casillas(observation)

    assert len(skips) == 1
    assert skips[0].casilla_id == _M100_NUMERIC_CASILLA
    assert skips[0].reason == "not_numeric"
    assert skips[0].label
    assert filed_address not in str(skips[0].model_dump())
    assert "SANITIZADA" not in str(skips[0].model_dump())


def test_skip_query_reports_a_numeric_casilla_whose_token_will_not_parse() -> None:
    """A numeric casilla with an unreadable token is a distinct, named reason."""
    observation = _filed_observation(
        modelo="100",
        ejercicio=2025,
        period="0A",
        casilla_values={_M100_NUMERIC_CASILLA: "no-decimal"},
        value_kind=CasillaValueKind.NUMERIC,
    )

    skips = non_numeric_observed_casillas(observation)

    assert len(skips) == 1
    assert skips[0].reason == "unreadable_numeric_token"


_CARRIER_NAMES = ("ObservedCasillaValue", "ObservedCasillaValueProtocol")


def _carrier_consuming_modules() -> list[Path]:
    """Return production modules that name the carrier or its port.

    The scan is deliberately scoped rather than tree-wide. Matching
    ``Decimal(<expr>.value)`` by attribute NAME across the whole tree reports
    unrelated carriers that merely share the attribute -- a registry rate bracket
    and a range-guarded ``ModeloValue`` both do -- which is the false-positive
    class that makes a gate untrustworthy. Inside a module that handles observed
    casillas, a ``.value`` converted to a Decimal is the read this rule governs.
    """
    modules: list[Path] = []
    for path in scan_directory(_SRC_ROOT, pattern="*.py", recursive=True):
        parts = path.relative_to(_SRC_ROOT).parts
        if "tests" in parts or parts[0] == "_data":
            continue
        if any(name in path.read_text(encoding="utf-8") for name in _CARRIER_NAMES):
            modules.append(path)
    return modules


def test_carrier_migration_scan_is_not_vacuous() -> None:
    """The scan must have subjects and must detect the thing it looks for.

    A completeness gate that silently scanned nothing, or whose matcher never
    fired, would report a clean migration forever.
    """
    assert _carrier_consuming_modules(), "no production module names the carrier; the scan below is vacuous"
    planted = ast.parse("from decimal import Decimal\ndef read(row):\n    return Decimal(row.value)\n")
    assert _decimal_on_dot_value_sites(planted) == [3], "the matcher does not detect a direct carrier read"


def test_no_production_module_reads_a_carrier_value_as_a_decimal_directly() -> None:
    """Every amount read goes through the accessor; none re-derives the type.

    This is the migration-completeness signal, and it has to be a test because
    nothing else reports one: the enrollment gate does not scan this layer and
    cannot resolve attribute types anyway, and the type checker accepts the
    direct conversion. Without this, a consumer left behind is silent.
    """
    offenders: list[str] = []
    for path in _carrier_consuming_modules():
        sites = _decimal_on_dot_value_sites(ast.parse(path.read_text(encoding="utf-8")))
        offenders.extend(f"{path.relative_to(_SRC_ROOT).as_posix()}:{line}" for line in sites)

    assert offenders == [], (
        "a module that handles observed casillas converts a `.value` attribute straight to Decimal:\n  "
        + "\n  ".join(offenders)
        + "\n\nRead an observed casilla amount through ObservedCasillaValue.decimal_value(), "
        "which refuses a casilla whose declared kind is not numeric."
    )
