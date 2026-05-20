"""Opt-in live end-to-end check for the GROI oracle Protocol flow.

Drives the full :class:`GroiOracle` Protocol path against live AEAT:

1. ``planned_operations`` enumerates the form-GET, open-form, per-NIF
   check, discard sequence.
2. The remote-state guard pre-flights every operation against a real
   :class:`RemoteStateGuardPolicy` host-pinned to the GROI subdomain.
3. ``GroiSedeDriver.collect_observation`` opens a BrowserSession,
   navigates to the GROI form, queries each declared NIF, and
   returns a flat ``{nif: verdict}`` mapping.
4. The oracle compares observed verdicts against caller-declared
   expected verdicts and returns a :class:`ParityResult`.

Runs only when ``AEAT_LIVE_TESTS_ENABLED=1`` and a fresh cl@ve-movil
session is loaded at ``settings.aeat_token_dir``. Probes a public,
known ROI-registered Spanish NIF (Telefónica's A28015865) so the
expected verdict is stable across runs.
"""

from __future__ import annotations

import pytest

from aeat.adapters.outbound.aeat.sede._groi_check import GroiSedeDriver
from aeat.domain.calculations.registry import (
    AEAT_WRITE_FORBIDDEN_ACTIONS,
    GROI_ORACLE_ID,
    GroiOracle,
    RemoteStateGuardPolicy,
)
from aeat.tests.live_gate import requires_live_enabled

pytestmark = [pytest.mark.live_read, pytest.mark.domain_outbound]

# Telefónica SA — public ROI-registered Spanish corporate NIF.
_PROBE_NIF = "A28015865"


def _live_policy() -> RemoteStateGuardPolicy:
    """The live policy enforces the read-only mandate via the canonical AEAT
    write-class forbidden_actions set. AEAT writes are PERMANENTLY FORBIDDEN;
    every test that exercises the GROI oracle does so with this guard active.
    """

    return RemoteStateGuardPolicy(
        id="modelo-349-groi-spanish-roi-check",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        allowed_hosts=("www2.agenciatributaria.gob.es",),
        forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS,
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def test_groi_oracle_returns_match_for_registered_telefonica_nif() -> None:
    """Full Protocol flow returns verdict=match for a known ROI-registered Spanish NIF."""

    requires_live_enabled()
    oracle = GroiOracle(driver=GroiSedeDriver())

    result = oracle.verify_payload(
        _live_policy(),
        b"",
        expected={_PROBE_NIF: "valid"},
    )

    assert result.verdict == "match", result
    assert result.oracle_id == GROI_ORACLE_ID
    assert result.cross_reference_id == "modelo-349-groi-spanish-roi-check"
    assert len(result.fields) == 1
    field = result.fields[0]
    assert field.name == _PROBE_NIF
    assert field.verdict == "match"
    assert field.expected == "valid"
    assert field.observed == "valid"
    assert result.raw_evidence_locator is not None
    assert "agenciatributaria.gob.es" in result.raw_evidence_locator


def test_groi_oracle_returns_mismatch_when_expected_differs_from_live_observation() -> None:
    """If the caller declares an expected verdict that disagrees with AEAT's response, oracle reports mismatch."""

    requires_live_enabled()
    oracle = GroiOracle(driver=GroiSedeDriver())

    result = oracle.verify_payload(
        _live_policy(),
        b"",
        # Lying about Telefónica's status: AEAT will report it valid, we expected invalid.
        expected={_PROBE_NIF: "invalid"},
    )

    assert result.verdict == "mismatch", result
    field = result.fields[0]
    assert field.name == _PROBE_NIF
    assert field.verdict == "mismatch"
    assert field.expected == "invalid"
    assert field.observed == "valid"


def test_groi_oracle_blocks_when_policy_pins_wrong_host() -> None:
    """Guard preflight rejects the live navigation before any browser action runs."""

    requires_live_enabled()
    oracle = GroiOracle(driver=GroiSedeDriver())
    wrong_host_policy = RemoteStateGuardPolicy(
        id="wrong-host-policy",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        # GROI lives on www2; this policy pins sede only.
        allowed_hosts=("sede.agenciatributaria.gob.es",),
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )

    result = oracle.verify_payload(wrong_host_policy, b"", expected={_PROBE_NIF: "valid"})

    assert result.verdict == "blocked", result
    assert result.cross_reference_id == "wrong-host-policy"
    assert "blocked by remote-state guard" in result.narrative
    assert result.fields == ()
