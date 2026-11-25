"""The CLI renders a party-kind finding in served words without the party's identifier.

The identifier is synthetic. The finding itself comes from the canonical kernel; this file asserts only the command line's payload and notice.
"""

from __future__ import annotations

import pytest

from ....application.ledger.counterparty_filing_name_kind_findings import (
    FILING_NAME_KIND_CONTRADICTS_FORM_FINDING,
    filing_name_kind_findings,
)
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.filing.declared_party_name import DeclaredPartyKind
from ..ledger_counterparty_filing_name_commands import filing_name_finding_notices, filing_name_finding_payloads

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_DNI = "12345678Z"


def test_the_cli_renders_the_finding_in_served_words_without_the_party() -> None:
    with bundled_indexed_authority().operation() as operation:
        findings = filing_name_kind_findings(
            tax_identifier=_DNI, country_code=None, declared_kind="entity", operation=operation
        )
    (payload,) = filing_name_finding_payloads(findings)
    assert (payload.code, payload.declared_kind, payload.observed_form) == (
        FILING_NAME_KIND_CONTRADICTS_FORM_FINDING,
        DeclaredPartyKind.ENTITY,
        DeclaredPartyKind.NATURAL_PERSON,
    )
    (notice,) = filing_name_finding_notices(findings)
    assert notice.code == f"ledger.counterparty.{FILING_NAME_KIND_CONTRADICTS_FORM_FINDING}"
    assert notice.severity.value == "warning"
    assert "{" not in notice.message
    assert "cli.ledger" not in notice.message
    assert _DNI not in notice.message
    assert _DNI not in str(notice.context)
