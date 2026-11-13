"""A declaration holding a value nobody entered is held back by verify, export and local filing alike.

The work form marks a box the calculation holds and nobody is recorded as entering as an
assumed value, and withholds the file on it. The registered stages read that same
selection, so the return is neither verified complete, exported nor recorded as filed
until the filer states the box. Real encrypted store, calculation, edit executor,
verification stage, filing and export services over the published authority: the seeded
Modelo 130 holds a figure in its operator-entered box 06 that only the calculation was
given.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.modelo.assumed_value_gate import (
    ModeloAssumedValueUnconfirmedError,
    assumed_value_verification_findings,
    unconfirmed_assumed_fields,
)
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.edit_models import (
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloScalarEditIntentV1,
)
from cadrumo.application.modelo.export import export_modelo_revision
from cadrumo.application.modelo.export_contracts import ModeloExportCommand
from cadrumo.application.modelo.filing_actions import file_modelo_revision
from cadrumo.application.modelo.preconditions import ModeloPreconditionFailure
from cadrumo.application.modelo.verification_model_findings import append_readable_model_findings
from cadrumo.application.modelo.verification_preconditions import project_verification_findings
from cadrumo.application.modelo.verification_report_facts import classify_verification_outcome
from cadrumo.application.modelo.work_form_assumed import assumed_fields
from cadrumo.application.modelo.work_form_field_vocabulary import ModeloFormCasillaAddressV1
from cadrumo.application.modelo.work_form_header import export_hold
from cadrumo.application.modelo.work_form_next_step import confirm_count
from cadrumo.application.modelo.work_form_service import load_modelo_work_form
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.errors.error_codes import get_registered_error_code, resolve_error_message
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import lookup_translation
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from cadrumo.entrypoints.adapter_composition_work_ports import (
    build_filing_action_ports,
    build_verification_repository_bundle,
)

from .modelo_gate_bucket_support import ready_workflow_profile
from .modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork, seeded_operator_work
from .profile_persistence.verification_repository_support import build_test_certificate_secret_backend_factory

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BOX = validated_casilla_id("06")
_HELD = Decimal("100")
_FINDING_KEY = "application.modelo.findings.assumed_value_unconfirmed"
_LOCALES = ("en", "es", "ca", "hu")
_PRIOR_BINDINGS = (
    "modelo-130-pagos-fraccionados-anteriores",
    "modelo-130-resultados-negativos-anteriores",
    "irpf.previous_year_economic_activity_net_income",
)
_CONFIRM_DOOR = "operator.modelo.work.set_value"


@contextmanager
def _assumed_work(tmp_path: Path) -> Generator[SeededOperatorWork]:
    """A calculated Modelo 130 whose box 06 holds a figure only the calculation was given."""
    with seeded_operator_work(tmp_path) as work:
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id,
            ports=work.ports,
            clock=SEEDED_AT,
            casilla_inputs={_BOX: _HELD},
            binding_values=dict.fromkeys(_PRIOR_BINDINGS, Decimal(0)),
        )
        yield work


def _assumed(work: SeededOperatorWork) -> tuple[str, ...]:
    repos = build_verification_repository_bundle(work.work_unit.bucket_id, operation=work.operation)
    fields = unconfirmed_assumed_fields(
        work.work_unit,
        work_unit_repository=repos.work_unit,
        calculation_repository=repos.calculation,
        verification_repository=repos.verification,
        credit_resolutions=repos.credit_resolution,
        operation=work.operation,
    )
    return tuple(field.address.casilla_id for field in fields if isinstance(field.address, ModeloFormCasillaAddressV1))


def _confirm(work: SeededOperatorWork) -> None:
    """Confirm the held figure the way a filer does: state it, through the production edit executor."""
    applied = work.apply(
        scalar=(
            ModeloScalarEditIntentV1(
                address=ModeloEditScalarAddressV1(casilla_id=_BOX),
                kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                value=_HELD,
            ),
        )
    )
    assert applied.refusal is None, applied.refusal


def _verification_stage(
    work: SeededOperatorWork,
) -> tuple[list[ModeloVerificationFinding], dict[int, ModeloPreconditionFailure]]:
    """Run verification's model-finding stage over the stored revision, as the m390 gate's proof does."""
    target = work.require_head()
    findings: list[ModeloVerificationFinding] = []
    failures: dict[int, ModeloPreconditionFailure] = {}
    repos = build_verification_repository_bundle(work.work_unit.bucket_id, operation=work.operation)
    append_readable_model_findings(
        findings,
        failures,
        work.work_unit,
        target,
        repos,
        work.operation,
        calculation_catalogue=repos.calculation.load_revisioned(operation=work.operation)[0],
    )
    return findings, failures


def _assumed_findings(findings: list[ModeloVerificationFinding]) -> list[ModeloVerificationFinding]:
    return [finding for finding in findings if finding.message_locale_key == _FINDING_KEY]


def test_the_form_and_the_gate_read_the_same_assumed_boxes(tmp_path: Path) -> None:
    """The gate's selection is the form's own: its count is the CONFIRM step's, and the boxes are the held one."""
    with _assumed_work(tmp_path) as work:
        repos = build_verification_repository_bundle(work.work_unit.bucket_id, operation=work.operation)
        form = load_modelo_work_form(
            work.work_unit.bucket_id,
            work.work_unit.modelo,
            work.work_unit.filing_year,
            work.work_unit.period,
            operation=work.operation,
            work_unit_repository=repos.work_unit,
            calculation_repository=repos.calculation,
            verification_repository=repos.verification,
            admission=None,
            language=OutputLanguage.EN,
        ).form
        gated = _assumed(work)

    assert gated == (_BOX,)
    assert len(assumed_fields(form)) == confirm_count(form) == 1
    hold = export_hold(form, OutputLanguage.EN, verified=False, recorded=False)
    assert hold is not None


def test_verification_reports_each_unconfirmed_box_and_withholds_a_complete_verdict(tmp_path: Path) -> None:
    """One blocking finding per box names it and the confirm door, carries no value, and blocks the grant."""
    with _assumed_work(tmp_path) as work:
        findings, failures = _verification_stage(work)

    (finding,) = _assumed_findings(findings)
    assert finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.casilla_id == _BOX
    assert dict(finding.message_facts) == {"box": _BOX}
    failure = failures[id(finding)]
    assert failure.subject_leaf_key == "modelo.work.verify"
    assert failure.verdict.action is not None
    assert failure.verdict.action.action_id == _CONFIRM_DOOR
    (projection,) = (
        item
        for item in project_verification_findings(findings, failures_by_finding_id=failures)
        if item.finding is finding
    )
    assert projection.precondition_failure == failure
    assert str(_HELD) not in repr(finding.message_facts)
    assert str(_HELD) not in repr(failure)
    completeness, granted = classify_verification_outcome(findings=findings, missing_required=[])
    assert granted is False
    assert completeness is VerificationCompletenessStatus.BLOCKED
    for locale in _LOCALES:
        words = lookup_translation(_FINDING_KEY, locale=locale)
        assert words is not None
        assert words.strip()
        assert "%{box}" in words


def test_a_confirmed_box_lifts_the_finding(tmp_path: Path) -> None:
    """Once the filer states the box, nothing is assumed and verification reports no such finding."""
    with _assumed_work(tmp_path) as work:
        _confirm(work)
        findings, _ = _verification_stage(work)
        assumed = _assumed(work)

    assert assumed == ()
    assert _assumed_findings(findings) == []


def test_the_finding_builder_makes_one_finding_per_box(tmp_path: Path) -> None:
    with _assumed_work(tmp_path) as work:
        repos = build_verification_repository_bundle(work.work_unit.bucket_id, operation=work.operation)
        fields = unconfirmed_assumed_fields(
            work.work_unit,
            work_unit_repository=repos.work_unit,
            calculation_repository=repos.calculation,
            verification_repository=repos.verification,
            credit_resolutions=repos.credit_resolution,
            operation=work.operation,
        )
        pairs = assumed_value_verification_findings(work.work_unit, fields)

    assert len(pairs) == len(fields) == 1


def test_export_and_filing_refuse_with_the_typed_code_the_door_and_no_value(tmp_path: Path) -> None:
    """Both stages refuse before any lifecycle check or write, naming the box and the door, in four languages."""
    export_path = tmp_path / "modelo-130.txt"
    with _assumed_work(tmp_path) as work:
        head = work.require_head()
        with pytest.raises(ModeloAssumedValueUnconfirmedError) as file_info:
            file_modelo_revision(
                head.calculation_revision_id,
                approved_verification_report_id="0" * 64,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                operator_scope_ports=build_operator_scope_ports(),
                ports=build_filing_action_ports(bucket_id=work.work_unit.bucket_id, operation=work.operation),
                actor="test",
                workflow_profile=ready_workflow_profile(),
                operation=work.operation,
            )
        with pytest.raises(ModeloAssumedValueUnconfirmedError) as export_info:
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=head.calculation_revision_id, output_path=export_path, actor="test"
                ),
                workflow_profile=ready_workflow_profile(),
                export_ports=modelo_export_ports_for_test(bucket_id=work.work_unit.bucket_id),
                operation=work.operation,
            )

    for error, leaf in ((file_info.value, "modelo.work.file"), (export_info.value, "modelo.export")):
        failure = error.precondition_failure
        assert failure is not None
        assert failure.subject_leaf_key == leaf
        assert failure.scenario_id == f"{leaf}.assumed_value.unconfirmed"
        assert failure.verdict.failed_condition_id == f"{leaf}.assumed_value.confirmed"
        assert failure.verdict.action is not None
        assert failure.verdict.action.action_id == _CONFIRM_DOOR
        assert get_registered_error_code(error).code == "REFUSED_MODELO_ASSUMED_VALUE_UNCONFIRMED"
        assert str(_HELD) not in repr(error.context) and str(_HELD) not in repr(failure)
        for locale in _LOCALES:
            message = resolve_error_message(error, locale=locale)
            assert message
            assert "%{" not in message
            assert "errors." not in message
            assert _BOX in message
            assert str(_HELD) not in message
    assert not export_path.exists()


def _sealed(work: SeededOperatorWork) -> str:
    """Stand the stored revision where a granting verification leaves it, so only the stage under test judges it."""
    head = work.require_head()
    sealed = head.model_copy(
        update={"state": CalculationRevisionState.VERIFICADO_COMPLETO, "verified_at": SEEDED_AT, "verified_by": "test"}
    )
    work.ports.calculation_repository.save(
        upsert_calculation_revision(work.ports.calculation_repository.load(), sealed)
    )
    return sealed.calculation_revision_id


def _export(work: SeededOperatorWork, revision_id: str, path: Path) -> None:
    export_modelo_revision(
        ModeloExportCommand(calculation_revision_id=revision_id, output_path=path, actor="test"),
        workflow_profile=ready_workflow_profile(),
        export_ports=modelo_export_ports_for_test(bucket_id=work.work_unit.bucket_id),
        operation=work.operation,
    )


def test_a_verified_revision_holding_an_assumed_value_is_not_exported(tmp_path: Path) -> None:
    """A grant that predates the gate does not release the value: export still refuses on the unconfirmed box."""
    with _assumed_work(tmp_path) as work:
        revision_id = _sealed(work)
        with pytest.raises(ModeloAssumedValueUnconfirmedError):
            _export(work, revision_id, tmp_path / "modelo-130.txt")


def test_export_moves_past_the_assumed_value_once_the_box_is_confirmed(tmp_path: Path) -> None:
    """After the filer states the box the assumed-value refusal is gone; this synthetic 130 is then judged by its own calculation notes."""
    with _assumed_work(tmp_path) as work:
        _confirm(work)
        revision_id = _sealed(work)
        outcome: CadrumoError | None = None
        try:
            _export(work, revision_id, tmp_path / "modelo-130.txt")
        except CadrumoError as refused:
            outcome = refused

    assert not isinstance(outcome, ModeloAssumedValueUnconfirmedError), outcome
