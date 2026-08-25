"""A reviewed revision that cannot file must yield a ledger, not abort the audit.

``audit_registry_model_law_coverage`` and ``audit_registry_construct_evidence`` ask
the same question of every revision: is this reviewed, and if so, build its
filing-grade snapshot. Review state and filing CAPABILITY are different conditions,
and the first does not imply the second -- a revision may be fully reviewed at
``applicability`` grade and still declare no export layout, because AEAT publishes
no diseño de registro from which one could be authored.

The model-law audit has always known this and catches the capability refusal,
recording it so the ledger can tell "reviewed but cannot file" apart from "nobody
reviewed it" -- both otherwise read ``inspection_only``. Its sibling made the same
call unguarded, and the consequence was not a cosmetic difference: stamping an
applicability-grade revision ``agent_reviewed`` made the whole corpus audit raise
``RegistryValidationError``, so the registry stopped loading. Reviewing such a
revision was therefore impossible, and that is why no applicability-grade stub was
ever stamped.

Modelo 038 is the worked case: two informational declaration-header casillas, twelve
monthly deadline windows, no formulas, no export layout, and nothing to build one
from.
"""

from __future__ import annotations

import pytest

from ..authority import bundled_authority
from ..coverage import ConstructEvidenceLedger, audit_registry_construct_evidence

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


def _audit() -> tuple[ConstructEvidenceLedger, ...]:
    return audit_registry_construct_evidence(bundled_authority()).ledgers


def test_a_reviewed_revision_without_an_export_layout_still_produces_a_ledger() -> None:
    """The audit must fold over the whole corpus rather than raise on one revision."""
    ledgers = _audit()

    assert ledgers, "the construct-evidence audit produced no ledgers at all"


def test_a_capability_fallback_is_recorded_rather_than_silently_demoted() -> None:
    """A demoted ledger must say why, or it reads as a revision nobody reviewed."""
    ledgers = _audit()

    demoted = [ledger for ledger in ledgers if ledger.reviewed_but_not_filing_capable]

    for ledger in demoted:
        assert ledger.authority_scope == "inspection_only", (
            f"{ledger.modelo}/{ledger.revision}: a capability fallback must not keep filing scope"
        )
        reason = ledger.authority_fallback_reason
        assert reason is not None
        assert "filing artifact" in reason, (
            f"{ledger.modelo}/{ledger.revision}: the recorded reason must name the refusal, got {reason!r}"
        )


def test_an_unreviewed_revision_is_distinguishable_from_a_demoted_one() -> None:
    """Both read inspection_only; only the demoted one carries a reason."""
    ledgers = _audit()

    inspection_only = [ledger for ledger in ledgers if ledger.authority_scope == "inspection_only"]
    assert inspection_only, "no inspection-scope ledger exists, so this proves nothing"

    unreviewed = [ledger for ledger in inspection_only if not ledger.reviewed_but_not_filing_capable]
    assert unreviewed, (
        "every inspection-scope ledger carries a fallback reason, so the distinction this records would be vacuous"
    )
