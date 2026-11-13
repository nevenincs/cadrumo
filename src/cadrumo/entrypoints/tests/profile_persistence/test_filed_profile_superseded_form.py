"""Real-path tests for the form's finding on a filed declaration whose profile facts were edited.

A filed declaration's bytes are what was filed, and verify returns its sealed
report unchanged, so the profile-drift gate cannot reach the filer there. The
form that shows the filed declaration serves the finding instead: a warning
whose door is the amendment. The probe is the file-flow Modelo 130, calculated
from bucket sources, verified and filed locally through the production
actions, then shown through the production form loader.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.profile_drift_gate import PROFILE_SUPERSEDED_FILED_KEY
from ....application.modelo.work_form_findings import ModeloFormAttention, ModeloFormIssue
from ....application.modelo.work_form_service import load_modelo_work_form
from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ....domain.modelos.profile_read_fingerprint import ProfileReadScope, ProfileReadSource
from ....domain.modelos.verification_report import ModeloVerificationFindingSeverity
from ....domain.modelos.work_unit import WorkUnit
from ....domain.user_profile.values import UserProfileFact
from ...adapter_composition_work_ports import build_calculation_action_ports
from .file_flow_test_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    T1,
    T2,
    T3,
    Repos,
    file_revision,
    seed_work_unit,
    verify_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: The home's floor area, which the ledger reads for the home-office afectación (LIRPF art. 30.2.5ª).
_READ = "vivienda_office.total_m2"
#: A profile fact no Modelo 130 calculation reads: the operator's contact email.
_UNREAD = "identity.email"


def _filed(repos: Repos) -> tuple[WorkUnit, CalculationRevision]:
    """Calculate, verify and file the Modelo 130 through the production actions."""
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    with bundled_indexed_authority().operation() as operation:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            actor="operator-A",
            casilla_inputs={**DEFAULT_130_BASELINE_INPUTS},
            binding_values=DEFAULT_130_BINDING_VALUES,
            clock=T1,
        ).revision
    report = verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )
    assert report.granted_verificado_completo is True
    file_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T3,
    )
    filed = cr_repo.load().get(revision.calculation_revision_id)
    assert filed is not None
    assert filed.state is CalculationRevisionState.PRESENTADO
    return work_unit, filed


def _record_paths(revision: CalculationRevision) -> frozenset[str]:
    fingerprint = revision.profile_read_fingerprint
    assert fingerprint is not None
    return frozenset(
        entry.selector
        for entry in fingerprint.entries
        if entry.source is ProfileReadSource.RECORD and entry.scope is ProfileReadScope.PATH
    )


def _superseded(repos: Repos, work_unit: WorkUnit) -> list[ModeloFormIssue]:
    wu_repo, cr_repo, _fr_repo, vr_repo, _bv_repo = repos
    with bundled_indexed_authority().operation() as operation:
        form = load_modelo_work_form(
            work_unit.bucket_id,
            work_unit.modelo,
            work_unit.filing_year,
            work_unit.period,
            operation=operation,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            admission=None,
            language=OutputLanguage.EN,
        ).form
    return [issue for issue in form.issues if issue.finding.message_locale_key == PROFILE_SUPERSEDED_FILED_KEY]


def test_an_edited_read_fact_serves_the_amendment_door_on_the_filed_form(repos: Repos) -> None:
    work_unit, filed = _filed(repos)
    assert _READ in _record_paths(filed)
    assert not _superseded(repos, work_unit)

    upsert_test_profile_facts(work_unit.bucket_id, (UserProfileFact(path=_READ, value=Decimal("95")),))
    (issue,) = _superseded(repos, work_unit)

    assert issue.door_action_id == "operator.modelo.work.amend"
    assert issue.action_locale_key == "application.modelo.work_form.finding_action.amend_filed_declaration"
    # The filed bytes stand: the finding asks for a check, it does not block.
    assert issue.finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert issue.attention is ModeloFormAttention.CHECK


def test_an_edit_to_a_fact_the_filing_did_not_read_serves_nothing(repos: Repos) -> None:
    work_unit, filed = _filed(repos)
    assert _UNREAD not in _record_paths(filed)

    upsert_test_profile_facts(work_unit.bucket_id, (UserProfileFact(path=_UNREAD, value="otra.persona@example.test"),))

    assert not _superseded(repos, work_unit)
