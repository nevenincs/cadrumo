"""Import graph summary."""

from __future__ import annotations

import re
from collections import Counter
from typing import Final

from .import_health_models import GraphSummary

ANALYZED_RE: Final[re.Pattern[str]] = re.compile(r"^Analyzed (\d+) files, (\d+) dependencies\.$")


CONTRACT_RE: Final[re.Pattern[str]] = re.compile(r"^(.+?) (KEPT|BROKEN)$")


def graph_summary(output: str) -> GraphSummary:
    """Parse native graph census and contract status diagnostics."""
    files = 0
    dependencies = 0
    contracts: Counter[str] = Counter()
    broken: list[str] = []
    contract_status: dict[str, str] = {}
    for line in output.splitlines():
        analyzed = ANALYZED_RE.fullmatch(line.strip())
        if analyzed:
            files = int(analyzed.group(1))
            dependencies = int(analyzed.group(2))
            continue
        contract = CONTRACT_RE.fullmatch(line.strip())
        if contract:
            status = contract.group(2).lower()
            contracts[status] += 1
            contract_status[contract.group(1)] = status
            if status == "broken":
                broken.append(contract.group(1))
    return {
        "contracts_broken": contracts["broken"],
        "contracts_kept": contracts["kept"],
        "contracts_total": sum(contracts.values()),
        "broken_contract_names": broken,
        "contract_status": dict(sorted(contract_status.items())),
        "dependencies": dependencies,
        "files": files,
    }
