"""Registry CLI envelopes project the canonical reports, not loose dictionaries.

Four registry ``--json`` payloads re-declared already-typed report structures as
``dict[str, object]`` / ``list[dict[str, object]]`` with bare-string scalars and
``extra="allow"``, then validated only that shell after dumping the canonical
report. The canonical models enforce bounded identities, closed modes and
statuses, unique casilla ids, non-negative counts and typed provenance; the
shells enforced none of it, so the wire contract was strictly weaker than the
report it claimed to mirror and an operator or downstream reader could not rely
on it.

Each case below is a mutation the canonical model rejects. Before the payloads
were retyped every one of them was accepted by the CLI shell, so these
assertions fail against the pre-fix models rather than merely being reached.
The valid case is asserted too: a refusal-only gate would still pass if the
payload rejected everything.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry import CrossReferenceApplicabilityDeclaracion
from .._registry_payloads import (
    RegistryAuditOraclesResult,
    RegistryParityReplayResult,
    RegistryParityRunResult,
    RegistryVerifyFiledStateResult,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


# ---------------------------------------------------------------------------
# registry.audit_oracles
# ---------------------------------------------------------------------------


def test_audit_oracles_refuses_a_negative_failure_count() -> None:
    with pytest.raises(ValidationError):
        RegistryAuditOraclesResult(environment="live", failure_count=-1)


def test_audit_oracles_refuses_a_malformed_applicability_declaration() -> None:
    """Blank identities, an out-of-set mode, and non-string predicate fields."""
    with pytest.raises(ValidationError):
        RegistryAuditOraclesResult.model_validate(
            {
                "environment": "live",
                "failure_count": 0,
                "applicability_declarations": [
                    {
                        "modelo_id": "",
                        "revision_id": "",
                        "cross_reference_id": "",
                        "applicability_condition_mode": "bogus",
                        "predicate_fields": [42],
                    },
                ],
            },
        )


def test_audit_oracles_refuses_an_unknown_field() -> None:
    with pytest.raises(ValidationError):
        RegistryAuditOraclesResult.model_validate(
            {"environment": "live", "failure_count": 0, "unknown": True},
        )


def test_audit_oracles_accepts_a_well_formed_declaration() -> None:
    """The typed declaration survives the boundary with its fields intact."""
    declaration = CrossReferenceApplicabilityDeclaracion(
        modelo_id="303",
        revision_id="2025-y-siguientes",
        cross_reference_id="modelo-303-sede-consulta",
        applicability_condition_mode="all",
        predicate_fields=("irpf_regime",),
    )

    result = RegistryAuditOraclesResult(
        environment="live",
        registered_oracle_ids=["oracle-a"],
        failure_count=0,
        applicability_declarations=[declaration],
    )

    assert result.applicability_declarations == [declaration]
    assert result.applicability_declarations[0].applicability_condition_mode == "all"
    assert result.applicability_declarations[0].predicate_fields == ("irpf_regime",)


# ---------------------------------------------------------------------------
# registry.verify_filed_state
# ---------------------------------------------------------------------------


def test_verify_filed_state_refuses_an_empty_comparison() -> None:
    """The comparison is a typed verdict, not an arbitrary mapping."""
    with pytest.raises(ValidationError):
        RegistryVerifyFiledStateResult.model_validate(
            {"observation_path": "obs.json", "comparison": {}},
        )


def test_verify_filed_state_refuses_a_malformed_comparison() -> None:
    """An out-of-set status, blank revision, and duplicate casilla ids."""
    with pytest.raises(ValidationError):
        RegistryVerifyFiledStateResult.model_validate(
            {
                "observation_path": "obs.json",
                "comparison": {
                    "modelo": "303",
                    "revision": "",
                    "filing_year": 1899,
                    "period": "1T",
                    "status": "bogus",
                    "compared_casilla_ids": ["01", "01"],
                },
            },
        )


# ---------------------------------------------------------------------------
# registry.parity.run / registry.parity.replay
# ---------------------------------------------------------------------------


def test_parity_run_refuses_a_non_datetime_created_at_and_empty_nested_reports() -> None:
    with pytest.raises(ValidationError):
        RegistryParityRunResult.model_validate(
            {
                "created_at": "not-a-date",
                "scenario": {},
                "workbook": {},
                "runner": {},
                "report": {},
            },
        )


def test_parity_run_refuses_an_unknown_field() -> None:
    with pytest.raises(ValidationError):
        RegistryParityRunResult.model_validate(
            {
                "created_at": "2026-05-19T10:00:00Z",
                "scenario": {},
                "workbook": {},
                "runner": {},
                "report": {},
                "unknown": True,
            },
        )


def test_parity_replay_refuses_an_out_of_set_status() -> None:
    with pytest.raises(ValidationError):
        RegistryParityReplayResult.model_validate(
            {
                "tape_path": "tape.json",
                "scenario_id": "scenario-a",
                "status": "bogus",
                "stored": {},
                "current": {},
            },
        )


def test_parity_replay_refuses_empty_stored_and_current_tapes() -> None:
    with pytest.raises(ValidationError):
        RegistryParityReplayResult.model_validate(
            {
                "tape_path": "tape.json",
                "scenario_id": "scenario-a",
                "status": "match",
                "stored": {},
                "current": {},
            },
        )
