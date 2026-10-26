"""Independent installed annual artifact and official XSD observations."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, cast

from .installed_tui_child import (
    InstalledTuiChildError,
)
from .scenario import IncomeTaxScenario
from .tui_xsd_validation import validate_modelo_100_xsd

if TYPE_CHECKING:
    pass


def _validate_annual_artifact(
    *, xml_path: Path, xsd_path: Path, scenario: IncomeTaxScenario
) -> tuple[dict[str, str], dict[str, object]]:
    """Read financial XML meaning independently, then validate the official structure."""
    from decimal import Decimal

    from lxml import etree

    document = etree.parse(str(xml_path), parser=etree.XMLParser(resolve_entities=False, no_network=True)).getroot()
    expected = {
        "E1INGRESO": scenario.annual_oracle.activity_income,
        "E1NGD": scenario.annual_oracle.deductible_expenses,
        "E1RN": scenario.annual_oracle.activity_net_income,
        "PAGOS": scenario.annual_oracle.m130_payments,
    }
    observed: dict[str, str] = {}
    for tag, amount in expected.items():
        nodes = document.findall(f".//{tag}")
        if len(nodes) != 1 or nodes[0].text is None or Decimal(nodes[0].text) != amount:
            raise InstalledTuiChildError(f"installed Modelo 100 artifact mismatched annual oracle at {tag}")
        observed[tag] = f"{amount:.2f}"
    validation = validate_modelo_100_xsd(xml_path=xml_path, xsd_path=xsd_path)
    if not validation.xsd_valid or validation.error_identities:
        raise InstalledTuiChildError("installed Modelo 100 artifact failed local official-XSD validation")
    return observed, cast("dict[str, object]", asdict(validation))
