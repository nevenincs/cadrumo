"""Detector teeth for the deduction-kind partition refusal.

Modelo 303 declares the corrientes box pair [28]/[29] and the bienes de
inversión pair [30]/[31] over the same category, rate and flow; the only thing
keeping a bien de inversión out of [28] is the corrientes bindings naming the
complementary deduction kinds. Losing that filter declares the investment twice
and nothing downstream notices, so the registry validation refuses it.

Each defect is planted in a COPY of the live modelo in a temporary tree, the
bundled corpus is never written and no production module is patched, and the
clean copy is checked in the same suite.
"""

from __future__ import annotations

import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from cadrumo.domain.calculations.registry.binding_targets import casillas_by_binding
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
    invoice_ledger_screen_bindings,
    resolve_ledger_iva_aggregation_binding_values,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from cadrumo.domain.iva.flow import IvaFlowDirection
from cadrumo.domain.iva.schema import IvaCategory, IvaLedgerObservationRole, IvaRateKind

from ..compiler.loader import load_modelo_directory
from ..compiler.validate_bindings import validate_binding_registration_section

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_MODELOS_ROOT = Path(__file__).resolve().parents[3] / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"
_FRAGMENT = Path("revisions") / "2022" / "bindings" / "0001-declarations.toml"
_REVISION = "2025"
_CORRIENTES_KINDS = 'deduction_fact_kinds = ["domestic_current", "rectification"], '
_CORRIENTES_BASE = "modelo-303-iva-soportado-interiores-base"
_INVESTMENT_BASE = "modelo-303-iva-soportado-interiores-bienes-inversion-base"
_CORRIENTES_CUOTA = "modelo-303-iva-soportado-interiores-cuota"
_INVESTMENT_CUOTA = "modelo-303-iva-soportado-interiores-bienes-inversion-cuota"


def _copy_303(tmp_path: Path) -> Path:
    destination = tmp_path / "303"
    shutil.copytree(_MODELOS_ROOT / "303", destination)
    return destination


def _replace_on_provider(tree: Path, *, fact: str, old: str, new: str) -> None:
    """Rewrite the corrientes interiores selector drawing ``fact``, and nothing else."""
    fragment = tree / _FRAGMENT
    text = fragment.read_text(encoding="utf-8")
    anchor = f'flow_direction = "soportado", fact = "{fact}", {old}'
    lines = [line for line in text.splitlines() if anchor in line and '"domestic_current"' in line]
    assert len(lines) == 1, f"expected one corrientes {fact} selector in the copied fragment, got {len(lines)}"
    fragment.write_text(text.replace(lines[0], lines[0].replace(old, new)), encoding="utf-8")


def _revision(tree: Path) -> ModeloRevision:
    return load_modelo_directory(tree).revisions[_REVISION]


def _failures(tree: Path) -> list[str]:
    return [
        failure
        for failure in validate_binding_registration_section(
            prefix=f"modelo 303 revision {_REVISION}", revision=_revision(tree)
        )
        if "deduction kind" in failure
    ]


def _investment_row() -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id="ordenador",
        transaction_date=date(2025, 2, 15),
        category=IvaCategory("domestic_general"),
        rate_kind=IvaRateKind("general"),
        flow_direction=IvaFlowDirection.from_registry("soportado"),
        base_amount=Decimal("4000.00"),
        iva_amount=Decimal("840.00"),
        deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_investment"),
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
            source_locator="invoice:ordenador",
            evidence_digest="c" * 64,
        ),
        investment_asset_id="BI-ORDENADOR",
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def test_the_live_split_is_accepted_and_routes_the_investment_to_its_own_box(tmp_path: Path) -> None:
    tree = _copy_303(tmp_path)
    revision = _revision(tree)

    values = resolve_ledger_iva_aggregation_binding_values(revision, (_investment_row(),))

    assert _failures(tree) == []
    assert casillas_by_binding(revision)[_CORRIENTES_BASE] == ("28",)
    assert casillas_by_binding(revision)[_INVESTMENT_BASE] == ("30",)
    assert values[_CORRIENTES_BASE] == Decimal("0")
    assert values[_INVESTMENT_BASE] == Decimal("4000.00")


def test_an_investment_row_routed_to_box_28_is_refused(tmp_path: Path) -> None:
    """Dropping the corrientes base filter puts the ordenador in [28] as well as [30]."""
    tree = _copy_303(tmp_path)
    _replace_on_provider(tree, fact="base_amount_sum", old=_CORRIENTES_KINDS, new="")

    values = resolve_ledger_iva_aggregation_binding_values(_revision(tree), (_investment_row(),))
    failures = _failures(tree)

    # The defect is real, not only structural: one row, both boxes.
    assert values[_CORRIENTES_BASE] == Decimal("4000.00")
    assert values[_INVESTMENT_BASE] == Decimal("4000.00")
    assert len(failures) == 1, failures
    assert _CORRIENTES_BASE in failures[0]
    assert _INVESTMENT_BASE in failures[0]
    assert "every kind" in failures[0]


def test_a_corrientes_cuota_that_also_names_the_investment_kind_is_refused(tmp_path: Path) -> None:
    """An overlapping kind set is the same double declaration, on [29] and [31]."""
    tree = _copy_303(tmp_path)
    _replace_on_provider(
        tree,
        fact="iva_amount_sum",
        old=_CORRIENTES_KINDS,
        new='deduction_fact_kinds = ["domestic_current", "domestic_investment", "rectification"], ',
    )
    revision = _revision(tree)

    failures = _failures(tree)

    assert len(failures) == 1, failures
    assert _CORRIENTES_CUOTA in failures[0]
    assert _INVESTMENT_CUOTA in failures[0]
    assert "['domestic_investment']" in failures[0]
    # The invoice screen compares each binding of the split slot against the
    # ledger, so it refuses an overlap that would compare one row twice.
    with pytest.raises(RegistryValidationError, match="invoice IVA screen shape is duplicate"):
        invoice_ledger_screen_bindings(revision, modelo="303")
