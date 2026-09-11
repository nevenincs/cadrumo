"""Fail while modelo-routing branches embed numeric product policy."""

from __future__ import annotations

from dev.registry.analysis.modelo_regulatory_literal_scan import derive_regulatory_literal_findings


def main() -> None:
    """Print every current finding and exit non-zero until the set is empty."""
    findings = derive_regulatory_literal_findings()
    if not findings:
        return
    print(f"modelo regulatory-literal coverage: {len(findings)} finding(s); expected zero")
    for finding in findings:
        print(
            f"  + {finding.module}::{finding.symbol} "
            f"modelos={','.join(finding.modelo_codes)} literals={','.join(map(str, finding.literals))}"
        )
    raise SystemExit(1)


if __name__ == "__main__":
    main()
