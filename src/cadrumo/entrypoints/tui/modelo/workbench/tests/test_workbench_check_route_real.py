"""A calculation note only the check can decide sends the filer to the check, then gives way to what it found.

A Modelo 190 whose per-perceptor detail store is empty is calculated in real
encrypted storage, and the calculation notes the empty detail. Whether that
blocks filing is the check's to say: the filer may have attested that no
quarter of the year carried a retención. So before the check the workbench's
next action is the check, F8 runs it and filing stays withheld. Once the
current calculation is checked the note defers to the check's own finding of
the same cause: with every quarter attested the check accepts the empty detail,
says so, and nothing blocks on it; without the attestation the check
refuses and its finding blocks.

The declaration is read through the production reader over real storage, and
the check is the application's own verification of the stored calculation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import pytest
from textual.pilot import Pilot

from ......adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ......adapters.persistence.profile.tests.operator_scope_fakes import (
    build_inward_operator_scope_ports_for_active_route,
)
from ......application.calculations.m111_no_retenciones import M111_NO_RETENCIONES_PROFILE_PATH
from ......application.modelo.declarations_workspace import DeclarationsWorkspaceDeclarationRefV1
from ......application.modelo.edit_preflight import preflight_modelo_edit
from ......application.modelo.verification_actions import verify_modelo_revision
from ......application.modelo.work_form_models import ModeloFormAttention, ModeloWorkForm
from ......application.modelo.work_form_service import ModeloWorkFormLoadV1
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ......domain.deadlines.models import IVARegime, TaxpayerProfile
from ......domain.modelos.verification_report import VerificationReport
from ......domain.user_profile.values import UserProfileFact
from ......tests.env_scope import ready_clave_settings
from .....tests.modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from .....tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)
from ....components.host import ScreenHostApp
from ...lifecycle import ModeloWorkspaceLifecycleDoor
from ..installed import InstalledModeloWorkbench, LifecycleDoorFactory, WorkbenchRepositories
from ..progress import NextAction, WorkbenchProgress, next_action_text, workbench_progress
from ..screen import ModeloWorkbenchScreen
from .workbench_fixture import FakeActions

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_YEAR = 2025
_REASON = "withholding_detail_absent"
_ATTESTED = "application.modelo.findings.withholding_detail_absent_attested"
_UNPROVEN = "application.modelo.findings.withholding_detail_absent_unproven"
_EVERY_QUARTER = UserProfileFact(
    path=M111_NO_RETENCIONES_PROFILE_PATH, value=",".join(f"{_YEAR}:{quarter}" for quarter in ("1T", "2T", "3T", "4T"))
)


@contextmanager
def _declaration(tmp_path: Path, *, attested: bool) -> Generator[tuple[SeededOperatorWork, InstalledModeloWorkbench]]:
    with seeded_operator_work(
        tmp_path, modelo="190", filing_year=_YEAR, period_code="0A", extra_facts=(_EVERY_QUARTER,) if attested else ()
    ) as work:
        unit = work.work_unit
        installed = InstalledModeloWorkbench(
            bucket_id=unit.bucket_id,
            declaration=DeclarationsWorkspaceDeclarationRefV1(
                work_unit_id=unit.work_unit_id,
                modelo=unit.modelo,
                filing_year=unit.filing_year,
                period=unit.period,
                state=unit.state,
                has_current_calculation=False,
                has_current_filing=False,
            ),
            operation=work.operation,
            repositories=WorkbenchRepositories(
                work_units=work.ports.work_unit_repository,
                calculations=work.ports.calculation_repository,
                verifications=VerificationReportCatalogueRepository(bucket_id=unit.bucket_id),
            ),
            door=_door(work),
        )
        work.recalculate()
        yield work, installed


def _door(work: SeededOperatorWork) -> LifecycleDoorFactory:
    """The declaration's lifecycle door, for the edit admission the reader asks it for."""

    def door(calculation_revision_id: str | None, verification_report_id: str | None) -> ModeloWorkspaceLifecycleDoor:
        return ModeloWorkspaceLifecycleDoor(
            services=cast(Any, object()),
            work_unit_id=work.work_unit_id,
            calculation_revision_id=calculation_revision_id,
            verification_report_id=verification_report_id,
            edit_admission=work.admit,
            edit_renewal=work.renew,
            edit_preflight=lambda submission: preflight_modelo_edit(
                submission,
                work_catalogue=work.ports.work_unit_repository.load(),
                calculation_catalogue=work.ports.calculation_repository.load(),
                tax_id_format=runtime_tax_id_format(authority=work.operation),
            ),
        )

    return door


def _check(work: SeededOperatorWork) -> VerificationReport:
    """Run the application's check of the stored current calculation, as the check operation does."""
    tax_id = "12345678Z"
    return verify_modelo_revision(
        work.require_head().calculation_revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        verification_repositories=build_test_verification_repository_bundle(),
        actor="operator:test",
        workflow_profile=TaxpayerProfile(tax_id=tax_id, iva_regime=IVARegime("GENERAL")),
        settings=ready_clave_settings(tax_id),
        operator_scope_ports=build_inward_operator_scope_ports_for_active_route(),
        operation=work.operation,
    )


def _progress(load: ModeloWorkFormLoadV1) -> WorkbenchProgress:
    return workbench_progress(load.form, staged=0, verified=load.verified, filed=load.filed)


def _blocking_on_the_cause(form: ModeloWorkForm) -> list[str]:
    notes = [note.reason for note in form.blocking_calculation_notes if note.reason == _REASON]
    findings = [
        issue.finding.message_locale_key
        for issue in form.issues
        if issue.attention is ModeloFormAttention.BLOCKS and issue.finding.message_locale_key in {_ATTESTED, _UNPROVEN}
    ]
    return notes + findings


async def _press_f8(installed: InstalledModeloWorkbench, actions: FakeActions) -> None:
    screen = ModeloWorkbenchScreen(installed, actions=actions)
    app = ScreenHostApp(screen)
    async with app.run_test(size=(160, 48)) as pilot:
        await _opened(pilot, screen)
        await pilot.press("f8")
        for _ in range(50):
            await pilot.pause()
            if actions.requested:
                break
        app.exit(None)


async def _opened(pilot: Pilot[None], screen: ModeloWorkbenchScreen) -> None:
    for _ in range(200):
        await pilot.pause()
        if screen.form is not None:
            return
    raise AssertionError("the workbench never finished reading its declaration")


@pytest.mark.timeout(300)
def test_an_attested_empty_detail_sends_the_filer_to_the_check_and_then_no_longer_blocks(tmp_path: Path) -> None:
    actions = FakeActions()
    with _declaration(tmp_path, attested=True) as (work, installed), override_settings(cadrumo_output_language="en"):
        before = installed.load(OutputLanguage.EN)
        progress_before = _progress(before)
        next_line = next_action_text(progress_before, OutputLanguage.EN)
        asyncio.run(_press_f8(installed, actions))
        report = _check(work)
        after = installed.load(OutputLanguage.EN)
        progress_after = _progress(after)

    assert _REASON in {note.reason for note in before.form.blocking_calculation_notes}
    assert before.form.verification is None
    assert progress_before.next_action is NextAction.VERIFY, "only the check can say whether the empty detail stands"
    assert next_line == "Check the declaration"
    assert progress_before.filing_withheld, "filing stays withheld until the check has spoken"
    assert actions.requested == ["verify"], "F8 runs the check"

    assert _ATTESTED in {finding.message_locale_key for finding in report.findings}
    assert after.form.verification is not None
    assert _REASON not in {note.reason for note in after.form.calculation_notes}, "the note gives way to the check"
    attested = [issue for issue in after.form.issues if issue.finding.message_locale_key == _ATTESTED]
    assert len(attested) == 1, "the check's acceptance of the attestation is shown in the note's place"
    assert attested[0].attention is not ModeloFormAttention.BLOCKS
    assert _blocking_on_the_cause(after.form) == []
    assert progress_after.next_action is not NextAction.VERIFY


@pytest.mark.timeout(300)
def test_an_unattested_empty_detail_stays_blocked_by_the_checks_own_finding(tmp_path: Path) -> None:
    with _declaration(tmp_path, attested=False) as (work, installed), override_settings(cadrumo_output_language="en"):
        before = installed.load(OutputLanguage.EN)
        progress_before = _progress(before)
        report = _check(work)
        after = installed.load(OutputLanguage.EN)
        progress_after = _progress(after)

    assert progress_before.next_action is NextAction.VERIFY
    assert progress_before.filing_withheld
    assert not report.granted_verificado_completo
    assert _REASON not in {note.reason for note in after.form.calculation_notes}
    assert _blocking_on_the_cause(after.form) == [_UNPROVEN], "the check refused, and its finding is what blocks"
    assert progress_after.next_action is NextAction.RESOLVE
    assert progress_after.filing_withheld
