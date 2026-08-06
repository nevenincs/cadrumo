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

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry import (
    CrossReferenceApplicabilityDeclaracion,
    WorkbookArtefactReport,
    WorkbookKind,
    WorkbookModeloCoverage,
    WorkbookRunnerAvailability,
    WorkbookScanStatus,
)
from .._registry_payloads import (
    RegistryAuditOraclesResult,
    RegistryParityReplayResult,
    RegistryParityRunResult,
    RegistryVerifyFiledStateResult,
    RegistryWorkbooksVerifyResult,
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
# registry.workbooks.verify
# ---------------------------------------------------------------------------


def _workbook_verification_models() -> tuple[
    WorkbookRunnerAvailability,
    WorkbookArtefactReport,
    WorkbookModeloCoverage,
]:
    runner = WorkbookRunnerAvailability(
        status="available",
        engine="libreoffice-headless",
        executable="soffice",
        detail="LibreOffice runner available.",
    )
    report = WorkbookArtefactReport(
        path="modelo-303/2025.xlsx",
        modelo="303",
        extension=".xlsx",
        bytes=1,
        sha256="0" * 64,
        sheets=("Liquidacion",),
        formula_cells=1,
        workbook_kind=WorkbookKind.FORMULA_FORM,
        evidence_tier=None,
        scan_status=WorkbookScanStatus.SCANNED,
        elapsed_seconds=Decimal("0.1"),
    )
    coverage = WorkbookModeloCoverage(
        modelo="303",
        workbook_count=1,
        formula_workbook_count=1,
        unsupported_xls_count=0,
        failed_count=0,
    )
    return runner, report, coverage


def _workbooks_verify_result() -> RegistryWorkbooksVerifyResult:
    runner, report, coverage = _workbook_verification_models()
    return RegistryWorkbooksVerifyResult(
        root="registry-workbooks",
        workbook_count=1,
        scanned_count=1,
        formula_workbook_count=1,
        unsupported_xls_count=0,
        failed_count=0,
        runner=runner,
        reports=[report],
        modelo_coverage=[coverage],
    )


def test_workbooks_verify_accepts_the_canonical_verification_models() -> None:
    """The transport payload carries the domain models without dictionary weakening."""
    runner, report, coverage = _workbook_verification_models()

    result = _workbooks_verify_result()

    assert result.runner == runner
    assert result.reports == [report]
    assert result.modelo_coverage == [coverage]


@pytest.mark.parametrize(
    "mutation",
    (
        {"runner": {"status": "available", "engine": "unsupported", "detail": "invalid runner"}},
        {"reports": [{}]},
        {
            "modelo_coverage": [
                {
                    "modelo": "303",
                    "workbook_count": -1,
                    "formula_workbook_count": 0,
                    "unsupported_xls_count": 0,
                    "failed_count": 0,
                },
            ],
        },
        {"unknown_extra_key": "x"},
    ),
)
def test_workbooks_verify_refuses_malformed_canonical_models(mutation: dict[str, object]) -> None:
    payload = _workbooks_verify_result().model_dump(mode="python")
    payload.update(mutation)

    with pytest.raises(ValidationError):
        RegistryWorkbooksVerifyResult.model_validate(payload)


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
