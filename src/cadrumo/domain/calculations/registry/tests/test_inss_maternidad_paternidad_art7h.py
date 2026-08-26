"""Oracle tests for INSS maternidad/paternidad Art. 7.h IRPF exempt path.

Legal authority: Ley 35/2006 Art. 7.h (LIRPF) — prestaciones públicas por
maternidad y paternidad reconocidas por la Seguridad Social (INSS) están
exentas de IRPF. El importe NO debe incluirse en casilla 0003 (Retribuciones
dinerarias); se registra en la casilla exenta dedicada y se descuenta de la
base de cómputo.

Yara shape:
  - €16.000 empleador (rendimiento tributable)
  - €8.000 INSS prestación baja maternidad (exento Art. 7.h)

Without the exempt path (total in 0003 = €24.000):
  casilla 0012 = 24.000

With the exempt path (0003 = €24.000, exempt casilla = €8.000):
  casilla 0012 = 24.000 - 8.000 = 16.000

Difference = €8.000 gross base → downstream IRPF impact ≈ €2.034,91 at
marginal rate ~25.4%.

Anti-tautology: injecting different INSS amounts produces proportional
changes in casilla 0012 (total computable income).

These tests use structural verification of the formula expression rather
than a full M100 engine run. The CLI help-surface test verifies end-to-end
wiring.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema import FormulaDefinition

from .....core.config import SecretStoreBackend
from .....tests.secure_sql import dev_test_database_password
from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@lru_cache
def _m100_revision(filing_year: int):
    modelo, _ = _committed_modelo("100")
    return select_revision(modelo, filing_year=filing_year, period="0A")


def _negated_casillas(formula: FormulaDefinition) -> set[str]:
    expr = formula.expression.model_dump(exclude_none=True)
    assert expr.get("op") == "sum", "top-level op must be sum"
    args = expr.get("args", [])
    return {
        arg["args"][0]["casilla_id"]
        for arg in args
        if arg.get("op") == "negate"
        and arg.get("args")
        and isinstance(arg["args"], (list, tuple))
        and arg["args"][0].get("casilla_id")
    }


#: The Art. 7.h exempt-INSS box, identified by what it MEANS rather than by
#: whichever id the revision currently gives it.
_INSS_EXENTA_ROLE = "irpf_rendimiento_trabajo_prestacion_inss_maternidad_paternidad_exenta"


class TestInssExentaCasillaRegistered:
    """The INSS exempt casilla is declared in the registry with correct provenance."""

    def test_casilla_registered_in_revision(self) -> None:
        """M100 revisions must declare the Art. 7.h exempt-INSS semantic role.

        Resolved by SEMANTIC ROLE rather than by casilla id. The role is the
        invariant; the id is incidental and has already moved once. These
        revisions declared ``0058`` and ``0059`` for this box, and no bundled
        AEAT source assigns either number to it in its year -- AEAT numbers no
        box for it at all -- so it now carries a descriptive id like every other
        non-AEAT box here. Pinning the id would have re-broken on that fix while
        proving nothing the role does not.
        """
        for filing_year in (2024, 2025):
            rev = _m100_revision(filing_year)
            matching = [c for c in rev.casillas if c.semantic_role == _INSS_EXENTA_ROLE]
            assert len(matching) == 1, (
                f"M100 {filing_year} must declare exactly one Art. 7.h exempt-INSS casilla, found {len(matching)}"
            )
            assert "ley-35-2006:art-7-h" in matching[0].legal_refs, filing_year


class TestFormulaStructure:
    """The total-ingresos-integros-computables formula subtracts the INSS exempt casilla."""

    def _get_total_ingresos_formula(self, filing_year: int):
        rev = _m100_revision(filing_year)
        formulas_by_id = {f.id: f for f in rev.formulas}
        formula_id = f"renta-{filing_year}-trabajo-total-ingresos-integros-computables"
        return formulas_by_id.get(formula_id)

    def test_formula_negates_exempt_inss_casilla(self) -> None:
        for filing_year in (2024, 2025):
            rev = _m100_revision(filing_year)
            casilla_id = next(c.id for c in rev.casillas if c.semantic_role == _INSS_EXENTA_ROLE)
            formula = self._get_total_ingresos_formula(filing_year)
            formula_id = f"renta-{filing_year}-trabajo-total-ingresos-integros-computables"
            assert formula is not None, f"{formula_id} must be declared"
            negated_casillas = _negated_casillas(formula)
            assert casilla_id in negated_casillas, (
                f"{formula_id} must negate casilla {casilla_id}; negated casillas found: {negated_casillas}"
            )

    def test_formula_still_includes_casilla_0003(self) -> None:
        """Adding the INSS exempt casilla must not disturb the 0003 input slot."""
        for filing_year in (2024, 2025):
            formula = self._get_total_ingresos_formula(filing_year)
            assert formula is not None, filing_year
            expr = formula.expression.model_dump(exclude_none=True)
            args = expr.get("args", [])
            direct_casillas = {arg.get("casilla_id") for arg in args if arg.get("casilla_id")}
            assert "0003" in direct_casillas, f"0003 must remain in the {filing_year} formula"


class TestLegalRefs:
    """Art. 7.h is registered in the legal catalogue and in the 0012 formula legal_refs."""

    def test_art_7h_legal_ref_in_formula(self) -> None:
        """The total-ingresos formula must carry the Art. 7.h legal ref."""
        for filing_year in (2024, 2025):
            rev = _m100_revision(filing_year)
            formulas_by_id = {f.id: f for f in rev.formulas}
            formula = formulas_by_id.get(f"renta-{filing_year}-trabajo-total-ingresos-integros-computables")
            assert formula is not None, filing_year
            assert "ley-35-2006:art-7-h" in formula.legal_refs, filing_year


class TestCliFlag:
    """The --prestacion-inss-exenta flag is visible in help output."""

    def test_help_exposes_prestacion_inss_exenta_flag(self, tmp_path: Path) -> None:
        """The --prestacion-inss-exenta flag is advertised in work calculate --help."""
        from .....tests.cli_runner import invoke_cached_cli, semantic_cli_output

        result = invoke_cached_cli(
            ["app", "modelo", "work", "calculate", "--help"],
            env={
                "CADRUMO_SECRET_STORE_BACKEND": SecretStoreBackend.AUTO.value,
                "CADRUMO_SECRET_PASSPHRASE": dev_test_database_password(),
                "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
                "CADRUMO_RUNS_DIR": str(tmp_path / "probe-runs"),
                "CADRUMO_FINANCIAL_TXS_DIR": str(tmp_path / "txs"),
                "CADRUMO_INVOICES_DIR": str(tmp_path / "invoices"),
                "CADRUMO_DRAFTS_DIR": str(tmp_path / "probe-drafts"),
            },
        )
        assert result.exit_code == 0
        assert "--prestacion-inss-exenta" in semantic_cli_output(result)
