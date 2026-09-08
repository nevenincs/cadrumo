"""Zero-target gate for regulatory literals embedded in modelo branches."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..analysis.modelo_regulatory_literal_scan import derive_regulatory_literal_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_no_modelo_branch_embeds_a_regulatory_literal() -> None:
    findings = derive_regulatory_literal_findings()
    rendered = [
        f"{finding.module}::{finding.symbol} modelos={finding.modelo_codes} literals={finding.literals}"
        for finding in findings
    ]
    assert not rendered, "modelo branches with embedded numeric policy:\n" + "\n".join(f"  + {row}" for row in rendered)


def test_detector_bites_when_a_modelo_branch_pins_a_year(tmp_path: Path) -> None:
    package = tmp_path / "src" / "pkg"
    package.mkdir(parents=True)
    (package / "route.py").write_text(
        "def choose(modelo, filing_year):\n"
        "    if modelo == Modelo.M100 and filing_year == 2025:\n"
        "        return True\n",
        encoding="utf-8",
    )

    findings = derive_regulatory_literal_findings(package, package / "registry")

    assert len(findings) == 1
    assert findings[0].modelo_codes == ("M100",)
    assert findings[0].literals == (2025,)
