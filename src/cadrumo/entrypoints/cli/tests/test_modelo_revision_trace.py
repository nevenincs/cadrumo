"""End-to-end CLI verification for the inline formula trace on draft review.

Issue #220 (acceptance journey wall 18): when an operator reviews a stored draft
revision with ``aeat app modelo work revision``, every computed casilla must
render its formula trace inline as ``op(refs) = op(values) = value`` - the
review moment is the highest-value place for the trace, and it must be sourced
from the already-computed engine entries on the revision rather than a second
compute command path. ``--verbose`` additionally exposes the full per-casilla
:class:`~cadrumo.domain.calculations.registry.CasillaObservation` (op, formula_id,
operand refs and operand values). Input / bound casillas without a formula keep
rendering their value only.

The test drives the real ``cadrumo`` CLI against an isolated encrypted backend
through the documented Modelo 130 estimación directa path; the casilla 07
resultado-parcial trace is the issue's worked example.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ._m130_source_support import seed_m130_expense_transaction, seed_m130_income_transaction
from ._modelo_work_ux_support import _create_profile, _invoke
from ._modelo_work_ux_support import _isolated_cli_backend as _isolated_cli_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FILING_YEAR = 2026


def _calculate_m130_draft() -> str:
    """Create, seed and calculate a Modelo 130 1T draft; return its revision id.

    Mirrors the documented estimación directa oracle case: ingresos 12.000 EUR,
    gastos 4.000 EUR, prior-year income 13.000 EUR (minoración = 0), so casilla
    07 (resultado parcial apartado I) = 20 % x 8.000 = 1.600,00 EUR.
    """

    created = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", str(_FILING_YEAR), "--period", "1T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    created_payload = STR_KEYED_MAPPING_ADAPTER.validate_python(_payload(created.output))
    work_unit_id = created_payload["work_unit_id"]
    assert isinstance(work_unit_id, str)

    seed_m130_income_transaction(amount=Decimal("12000.00"), filing_year=_FILING_YEAR, source_key="trace")
    seed_m130_expense_transaction(amount=Decimal("4000.00"), filing_year=_FILING_YEAR, source_key="trace")

    calculated = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "05=0.00",
            "--casilla", "06=0.00",
            "--binding", "irpf.previous_year_economic_activity_net_income=13000",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0, calculated.output
    payload = STR_KEYED_MAPPING_ADAPTER.validate_python(_payload(calculated.output))
    casilla_values = STR_KEYED_MAPPING_ADAPTER.validate_python(payload["casilla_values"])
    assert casilla_values["07"] == "1600.00", casilla_values
    revision_id = payload["calculation_revision_id"]
    assert isinstance(revision_id, str)
    return revision_id


def test_work_revision_renders_inline_formula_trace_for_computed_casilla(
    _isolated_cli_backend: Path,
) -> None:
    """`work revision` shows the formula trace inline for a computed casilla.

    Casilla 07 = subtract(04, 05, 06); its operand values are 1.600,00 / 0,00 /
    0,00 and its result is 1.600,00. The trace must read
    ``subtract(04, 05, 06) = subtract(1600.00, 0.00, 0.00) = 1600.00`` on the
    default review surface, sourced from the stored engine entry.
    """

    _create_profile()
    revision_id = _calculate_m130_draft()

    shown = _invoke(["app", "modelo", "work", "revision", revision_id])
    assert shown.exit_code == 0, shown.output
    assert "Traceback" not in shown.output

    casilla_07_line = next(line for line in shown.output.splitlines() if line.startswith("casilla\t07\t"))
    assert "subtract(04, 05, 06) = subtract(1600.00, 0.00, 0.00) = 1600.00" in casilla_07_line


def test_work_revision_input_casilla_renders_value_without_trace(
    _isolated_cli_backend: Path,
) -> None:
    """An input / bound casilla with no formula renders its value only.

    Casilla 01 (ingresos) is a source-bound input - it carries no formula, so
    its review line stays the bare ``casilla<TAB>01<TAB>value`` row with no
    ``= ... =`` trace appended.
    """

    _create_profile()
    revision_id = _calculate_m130_draft()

    shown = _invoke(["app", "modelo", "work", "revision", revision_id])
    assert shown.exit_code == 0, shown.output

    casilla_01_line = next(line for line in shown.output.splitlines() if line.startswith("casilla\t01\t"))
    assert casilla_01_line == "casilla\t01\t12000.00"
    assert " = " not in casilla_01_line


def test_work_revision_verbose_exposes_full_ledger_entry(
    _isolated_cli_backend: Path,
) -> None:
    """`work revision --verbose` exposes the full per-casilla trace entry.

    Beneath casilla 07's row, --verbose emits a single line carrying the
    complete CasillaObservation: op, formula_id, operand_refs,
    operand_casilla_refs and operand_values.
    """

    _create_profile()
    revision_id = _calculate_m130_draft()

    verbose = _invoke(["app", "modelo", "work", "revision", revision_id, "--verbose"])
    assert verbose.exit_code == 0, verbose.output

    trace_line = next(line for line in verbose.output.splitlines() if line.lstrip().startswith("trace\t07\t"))
    assert "op=subtract" in trace_line
    assert "formula_id=modelo-130-resultado-apartado-i" in trace_line
    assert "operand_refs=04,05,06" in trace_line
    assert "operand_casilla_refs=04,05,06" in trace_line
    assert "operand_values=1600.00,0.00,0.00" in trace_line

    # The verbose entry line appears only under --verbose; the default surface
    # carries the inline trace but not the expanded entry row.
    default = _invoke(["app", "modelo", "work", "revision", revision_id])
    assert default.exit_code == 0, default.output
    assert not any(line.lstrip().startswith("trace\t07\t") for line in default.output.splitlines())


def test_work_revision_json_observation_carries_formula_op(
    _isolated_cli_backend: Path,
) -> None:
    """The JSON observation for a computed casilla carries the typed ``op``.

    The trace is always reconstructible from the typed JSON payload (op +
    operand_refs + operand_values + value); ``--verbose`` is only a text-surface
    affordance, so the structured contract never depends on it.
    """

    _create_profile()
    revision_id = _calculate_m130_draft()

    shown = _invoke(["--format", "json", "app", "modelo", "work", "revision", revision_id])
    assert shown.exit_code == 0, shown.output
    payload = _payload(shown.output)

    observation_07 = next(obs for obs in payload["observations"] if obs["casilla_id"] == "07")
    assert observation_07["op"] == "subtract"
    assert observation_07["operand_refs"] == ["04", "05", "06"]
    assert observation_07["operand_values"] == ["1600.00", "0.00", "0.00"]
    assert observation_07["formula_id"] == "modelo-130-resultado-apartado-i"
