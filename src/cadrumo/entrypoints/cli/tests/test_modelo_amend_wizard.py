"""Contract coverage for ``aeat app modelo work amend-wizard``.

The amend wizard is a guided front end over the flow substrate: it asks
which casillas changed through a CHECKBOX page, then a second definition
of one DECIMAL page per selected casilla plus the amendment-kind SELECT
and the required reason, and files through the exact same
:func:`~application.modelo.amend_modelo_revision` composition path
``work amend`` uses. On a real terminal it renders the line-mode frontend;
a non-interactive host refuses with the substrate's
typed unsupported-console error rather than blocking. So these tests
exercise the wizard at the surfaces a non-terminal test process can
honestly reach:

* the substrate's scripted driver
  (:func:`~cadrumo.application.flows.scripted.run_scripted_flow`) walking the
  wizard's own projected selection and values/kind/reason definitions,
  then feeding those answers through the identical ``work amend``
  composition the wizard uses, and
* the non-interactive refusal (a piped caller with an amendable baseline),
  plus the period-awareness of the amendment-kind SELECT.

Nothing is mocked, stubbed, or patched: the real registry engine, the real
AEAT-attested baseline (imported through ``filing-record import``, the same
production path an operator uses before amending), and the real
bucket-scoped storage answer behind the scripted drive and the CLI amend.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import NamedTuple
from uuid import UUID

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from cadrumo.adapters.inbound.pdf.source_provenance import source_pdf_reference_path
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.adapters.persistence.profile.tests.modelo_303_filed_disposition import modelo_303_filed_disposition
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend,
)
from cadrumo.application.calculations.tests.filing_evidence import general_m303_filing_evidence
from cadrumo.application.flows.definition import FlowPage
from cadrumo.application.flows.errors import FlowAnswerError
from cadrumo.application.flows.scripted import run_scripted_flow
from cadrumo.application.modelo.action_errors import amendment_evidence_missing_precondition
from cadrumo.application.modelo.amendment_context_operation import ModeloWorkAmendmentContextProjection
from cadrumo.application.modelo.calculation_projection import ModeloCalculationSnapshot
from cadrumo.application.modelo.calculation_repository import calculation_revision_catalogue_repository
from cadrumo.application.modelo.calculation_revision_queries import get_calculation_revision
from cadrumo.application.modelo.external_import_actions import import_external_filing_evidence
from cadrumo.application.modelo.filing_projection import ModeloFilingRecordSnapshot
from cadrumo.application.modelo.filing_repository import modelo_record_catalogue_repository
from cadrumo.application.modelo.metadata_projection import ModeloWorkMetadataSnapshot
from cadrumo.application.modelo.registry_discovery import registry_casillas_for_registry_scope
from cadrumo.application.modelo.work_amend_correction import amendable_casilla_rows, filed_casilla_values
from cadrumo.application.modelo.work_lifecycle import get_work_unit
from cadrumo.application.modelo.work_unit_repository import work_unit_catalogue_repository
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.flows import FlowMode
from cadrumo.core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from cadrumo.domain.calculations.registry.amendment_regime_policy import permitted_amendment_kind_values_for_period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.query_reports import ModeloCasillaRow
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.justificante.schema import Justificante
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.calculation_revision_amendment import (
    AMENDMENT_DECLARATION_KINDS,
    m303_rectificativa_motive_is_applicable,
)
from cadrumo.domain.modelos.filing_record import ExternalEvidenceKind, FilingDeclarationKind
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.adapter_composition_work_ports import build_calculation_action_ports, build_filing_action_ports
from cadrumo.entrypoints.cli.modelo_amend_wizard_commands import (
    ACTIVE_RUNS,
    KIND_PAGE_ID,
    MOTIVE_PAGE_ID,
    REASON_PAGE_ID,
    modelo_amend_wizard_commands_selection_definition,
    selected_rows,
    value_page_id,
    values_kind_reason_definition,
)
from cadrumo.entrypoints.tests.filing_record_read_support import persisted_filing_record
from cadrumo.tests.aeat_literal_fixtures import justificante_cotejo_url
from cadrumo.tests.cli_envelope import unwrap_schema_envelope

from .cli_fixture_worlds import HumanProbeSession, ProfileSeeder, invoke_joined_cli
from .modelo_cli import create_modelo_work_unit_via_cli
from .modelo_work_scenarios import create_m130_work_unit, create_m303_work_unit, load_work_unit_by_id

__all__ = ["isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]


def test_amend_wizard_missing_evidence_offers_the_justificante_import() -> None:
    """An unattested amendment baseline is opened by importing its AEAT evidence for the same work unit."""
    failure = amendment_evidence_missing_precondition(
        subject_leaf_key="modelo.work.amend_wizard", work_unit_id="a" * 64, filing_record_id="b" * 64
    )

    verdict = failure.verdict
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.filing_record.import"
    assert {binding.argument_name: binding.value for binding in verdict.argument_bindings} == {"work_unit_id": "a" * 64}
    assert verdict.no_recovery_outcome is None


_TAX_ID = "12345678Z"
_YEAR = filing_year_envelope().horizon

# M130 1T has no required-manual casillas (casilla 02 is `required = true` but
# `input_kind = "bound"`); a baseline carrying only casillas 01 (ingresos) and
# 02 (gastos) is a legitimate amendable AEAT-attested filing.
_BASELINE_INGRESOS = Decimal("1000.00")
_BASELINE_GASTOS = Decimal("250.00")
_CORRECTED_INGRESOS = Decimal("1100.00")

# That baseline records casilla values only. Correcting casilla 01 reaches casilla 02
# and every figure after it, whose formulas read box sources the imported filing never
# recorded and a historical correction never reads from today's profile or ledger, so
# the correction states each of them. The normal modality carries no RIRPF art. 30.2.4a
# provision, so the restated accumulated expenses keep casilla 02 at the filed amount.
_M130_UNRECORDED_BINDINGS = {
    "modelo-130-estimacion-directa-modalidad": "directa_normal",
    "modelo-130-actividad-economica-gastos-cumulative": str(_BASELINE_GASTOS),
    "modelo-130-retenciones-agrarias": "0",
    "modelo-130-volumen-ingresos-agrario": "0",
    "irpf.previous_year_economic_activity_net_income": "20000.00",
}

# M303 casilla 07 is the régimen-general 21% base imponible; the authority-selected
# revision declares no required-manual casillas, so a baseline carrying 07 alone is
# a legitimate amendable AEAT-attested filing. The correction LOWERS the declared
# base: under the pre-rectificativa dual regime that direction is a solicitud de
# rectificación (LGT art. 120.3) that a self-filed complementaria cannot carry, so
# only the unified rectificativa mechanism can file it.
_M303_BASELINE_BASE_GENERAL = Decimal("10000.00")
_M303_CORRECTED_BASE_GENERAL = Decimal("9000.00")
_M303_RECTIFICATIVA_MOTIVE = "rectificaciones"


def _m303_revision_id(*, filing_year: int, period: str) -> str:
    return str(published_snapshot("303", filing_year=filing_year, period=period).revision.id)


def _context_amendment_options(
    *, unit: WorkUnit, baseline_revision: CalculationRevision, operation: PinnedAuthorityOperation
) -> tuple[tuple[FilingDeclarationKind, ...], bool]:
    """Read legal kind and M303 motive options from the pinned authority."""
    with validating_governed_facts(operation):
        permitted_values = permitted_amendment_kind_values_for_period(str(unit.modelo), unit.period)
    permitted_kinds = tuple(kind for kind in AMENDMENT_DECLARATION_KINDS if kind.value in permitted_values)

    motive_applicable = False
    evidence = baseline_revision.filing_instance_evidence
    if evidence is not None and str(unit.modelo) == "303":
        regimen = evidence.m303.regimen_simplificado.regimen_snapshot
        motive_applicable = m303_rectificativa_motive_is_applicable(
            registry_revision_id=regimen.registry_revision_id,
            record_design=regimen.record_design,
            operation=operation,
        )
    return permitted_kinds, motive_applicable


def _context_projection(
    *,
    baseline,
    unit: WorkUnit,
    baseline_revision: CalculationRevision,
    operation: PinnedAuthorityOperation,
) -> ModeloWorkAmendmentContextProjection:
    """Project real stored facts and registry rows through the worker context contract."""
    permitted_kinds, motive_applicable = _context_amendment_options(
        unit=unit, baseline_revision=baseline_revision, operation=operation
    )
    registry_rows = registry_casillas_for_registry_scope(
        str(unit.modelo),
        filing_year=unit.filing_year,
        period=unit.period.registry_token,
        operation=operation,
    ).rows
    return ModeloWorkAmendmentContextProjection(
        profile_id=UUID(unit.bucket_id),
        record=ModeloFilingRecordSnapshot.from_record(baseline),
        unit=ModeloWorkMetadataSnapshot.from_work_unit(unit),
        calculation=ModeloCalculationSnapshot.from_revision(
            baseline_revision,
            work_unit=unit,
            operation=operation,
        ),
        casilla_rows=registry_rows,
        permitted_amendment_kinds=permitted_kinds,
        m303_rectificativa_motive_applicable=motive_applicable,
    )


# The fields whose values must be identical for the same amendment expressed
# through either surface (the wizard-derived inputs and a hand-built ``work
# amend``). Deliberately excluded: the fields that identify the individual
# filing and so differ by construction (`amends_filing_record_id`,
# `filing_record_id`, `work_unit_id`, `calculation_revision_id`, `period`,
# `filed_at`) -- each asserted separately.
_AMEND_PARITY_SPINE = (
    "amendment_kind",
    "m303_rectificativa_motive",
    "status",
    "external_evidence",
    "kind",
    "live_submission",
    "aeat_accepted",
    "modelo",
    "filing_year",
    "bucket_id",
    "filed_by",
    "notes",
    "superseded_at",
    "superseded_by_filing_record_id",
)


def _invoke(args: list[str], *, runtime_profile: HumanProbeSession | None = None):
    return invoke_joined_cli(args) if runtime_profile is None else runtime_profile.invoke(args)


def _payload_string(output: str, key: str) -> str:
    value = STR_KEYED_MAPPING_ADAPTER.validate_python(unwrap_schema_envelope(output))[key]
    assert isinstance(value, str)
    return value


def _casilla_observation(revision_payload, casilla_id: str):
    """Return the single persisted observation for ``casilla_id``."""
    rows = [row for row in revision_payload["observations"] if row["casilla_id"] == casilla_id]
    assert len(rows) == 1, f"expected exactly one observation for casilla {casilla_id}, got {len(rows)}"
    return rows[0]


def _operator_profile_facts() -> dict[str, str]:
    """Return the synthetic profile facts required by amendment command tests."""
    return {
        "taxpayer_type.entity_type": "natural_person",
        "taxpayer_type.irpf_income_categories": "actividad_economica",
        "identity.tax_id": _TAX_ID,
        "identity.name": "Operator",
        "identity.surnames": "Amend",
        "activities.description": "design",
    }


def _create_profile(seed_profile: ProfileSeeder) -> HumanProbeSession:
    """Register genuine password custody and retain the joined human runtime."""
    return seed_profile(label="operator", facts=_operator_profile_facts())


@pytest.fixture
def _operator_profile(seed_profile: ProfileSeeder) -> HumanProbeSession:
    return _create_profile(seed_profile)


def _profile_amend_catalogue_state(
    *,
    runtime_profile: HumanProbeSession,
    bucket_id: str,
) -> tuple[object, object, object]:
    """Read the retained encrypted setup oracle independently of frontend admission."""
    with bundled_indexed_authority().operation() as operation:
        assert str(runtime_profile.profile_id) == bucket_id
        return (
            work_unit_catalogue_repository(bucket_id=bucket_id).load(),
            modelo_record_catalogue_repository(bucket_id=bucket_id).load(),
            calculation_revision_catalogue_repository(bucket_id=bucket_id, operation=operation).load(),
        )


def _seed_justificante(*, bucket_id: str, csv: str, work_unit_id: str, modelo: str = "130") -> None:
    """Persist the stored receipt metadata a justificante-bound evidence import requires.

    The receipt names the work unit's own filing year and period and is presented
    after that period closes, so it attests exactly the import target.
    """
    unit = load_work_unit_by_id(work_unit_id=work_unit_id)
    body = f"{csv}-pdf".encode()
    source_pdf_sha256 = hashlib.sha256(body).hexdigest()
    presented_on = unit.period.end_date + timedelta(days=15)
    presented_at = datetime(presented_on.year, presented_on.month, presented_on.day, 9, 30, tzinfo=UTC)
    receipt = Justificante(
        csv=csv,
        modelo=modelo,
        period=unit.period,
        ejercicio=str(unit.filing_year),
        presentation_id="1234567890123",
        presented_at=presented_at,
        tax_id=_TAX_ID,
        total_a_ingresar=None,
        total_a_devolver=None,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
        source_pdf_path=source_pdf_reference_path(source_pdf_sha256),
        source_pdf_sha256=source_pdf_sha256,
        parsed_at=presented_at + timedelta(days=1),
    )
    JustificanteRepository(bucket_id=bucket_id).save(receipt)


def _import_external_baseline(work_unit_id: str, *, csv: str = "JUST20251301TAMENDWIZARD") -> str:
    """Import an AEAT-attested M130 baseline filing and return its filing_record_id."""
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with open_test_profile_session(bucket_id):
        _seed_justificante(bucket_id=bucket_id, csv=csv, work_unit_id=work_unit_id)
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "filing-record", "import", work_unit_id,
            "--evidence-kind", "aeat_justificante_pdf",
            "--evidence-id", csv,
            "--set", f"01={_BASELINE_INGRESOS}",
            "--set", f"02={_BASELINE_GASTOS}",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _payload_string(result.output, "filing_record_id")


def _import_external_m303_baseline(
    work_unit_id: str,
    *,
    csv: str = "JUST20253031TAMENDWIZARD",
    runtime_profile: HumanProbeSession | None = None,
) -> str:
    """Import an AEAT-attested M303 baseline filing and return its filing_record_id.

    A Modelo 303 import must carry typed filing-instance evidence and the
    declaration-type header, which the ``filing-record import`` verb has no
    input for, so the baseline is imported through the application service the
    verb delegates to. It arrives as a register entry, the channel that records
    the period's observation and with it the result disposition an amendment
    of that period carries forward.
    """
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    casilla_values, source_headers = modelo_303_filed_disposition(
        {validated_casilla_id("07", surface="amend wizard m303 baseline"): _M303_BASELINE_BASE_GENERAL},
        source_locator=csv,
    )
    with bundled_indexed_authority().operation() as operation, ExitStack() as sessions:
        if runtime_profile is not None:
            assert str(runtime_profile.profile_id) == bucket_id
        sessions.enter_context(open_test_profile_session(bucket_id))
        _seed_justificante(bucket_id=bucket_id, csv=csv, work_unit_id=work_unit_id, modelo="303")
        ports = build_calculation_action_ports(bucket_id=bucket_id, operation=operation)
        work_unit = get_work_unit(work_unit_id, ports=ports.work_lifecycle_ports)
        record = import_external_filing_evidence(
            work_unit_id=work_unit_id,
            casilla_values=casilla_values,
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id=csv,
            filing_instance_evidence=general_m303_filing_evidence(work_unit.period, reference=csv, operation=operation),
            actor="aeat-import",
            expected_tax_id=_TAX_ID,
            work_unit_repository=ports.work_unit_repository,
            calculation_repository=ports.calculation_repository,
            filing_repository=ports.filing_repository,
            observation_repository=ports.observation_repository,
            source_headers=source_headers,
        ).filing_record
    return record.filing_record_id


class _AmendableBaseline(NamedTuple):
    """The work unit, its worker context and the casillas its filed figures let a correction restate."""

    unit: WorkUnit
    context: ModeloWorkAmendmentContextProjection
    baseline_values: dict[str, Decimal]
    amendable: tuple[ModeloCasillaRow, ...]


def _amendable_baseline(work_unit_id: str, *, bucket_id: str) -> _AmendableBaseline:
    """Resolve the unit's AEAT-attested baseline and its amendable rows; call inside an open profile session."""
    unit = load_work_unit_by_id(work_unit_id=work_unit_id)
    assert unit.current_filing_record_id is not None
    with bundled_indexed_authority().operation() as operation:
        baseline = persisted_filing_record(
            unit.current_filing_record_id,
            ports=build_filing_action_ports(bucket_id=bucket_id, operation=operation),
        )
        baseline_revision = get_calculation_revision(
            baseline.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=bucket_id, operation=operation),
        )
        context = _context_projection(
            baseline=baseline,
            unit=unit,
            baseline_revision=baseline_revision,
            operation=operation,
        )
    baseline_values = filed_casilla_values(context.calculation)
    return _AmendableBaseline(
        unit, context, baseline_values, amendable_casilla_rows(context.casilla_rows, baseline_values)
    )


def _scripted_amend(
    work_unit_id: str,
    *,
    change_numbers: list[str],
    corrected_by_number: dict[str, str],
    kind: str,
    motive: str | None = None,
    reason: str,
) -> tuple[dict[str, str], str, str | None, str]:
    """Drive the wizard's own two-round definitions through the scripted substrate.

    Reproduces exactly what the wizard does -- resolve the unit and its
    AEAT-attested baseline, discover the amendable casilla rows, project the
    selection and values/kind/reason definitions -- then walks them through
    :func:`run_scripted_flow` (the substrate's frontend-free scripted driver)
    instead of the interactive frontend a non-terminal test process cannot
    host. Returns the ``{casilla_id: corrected_value}`` override map plus the
    kind and reason, read back off the engine state exactly as the wizard
    reads them.
    """
    run_id = "test-amend-scripted"
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with open_test_profile_session(bucket_id):
        baseline = _amendable_baseline(work_unit_id, bucket_id=bucket_id)
        unit, context = baseline.unit, baseline.context
        baseline_values, amendable = baseline.baseline_values, baseline.amendable
        by_number = {row.number: row for row in amendable}
        selected_ids = [by_number[number].casilla_id for number in change_numbers]
        ACTIVE_RUNS[run_id] = {}
        try:
            selection_definition = modelo_amend_wizard_commands_selection_definition(
                amendable=amendable,
                baseline_values=baseline_values,
                unit=unit,
                run_token=run_id,
            )
            selection_state, selection_projection = run_scripted_flow(
                selection_definition,
                [",".join(selected_ids)],
                mode=FlowMode.CREATE,
            )
            assert selection_projection.submit_eligible
            selected = selected_rows(amendable=amendable, unit=unit, state=selection_state)

            corrections_definition = values_kind_reason_definition(
                selected=selected,
                baseline_values=baseline_values,
                permitted_amendment_kinds=context.permitted_amendment_kinds,
                m303_rectificativa_motive_applicable=context.m303_rectificativa_motive_applicable,
                run_token=run_id,
            )
            has_motive_page = any(
                page.id == MOTIVE_PAGE_ID for section in corrections_definition.sections for page in section.items
            )
            tokens = [corrected_by_number[row.number] for row in selected] + [kind]
            if has_motive_page and kind == "rectificativa":
                tokens.append(motive or "")
            tokens.append(reason)
            corrections_state, corrections_projection = run_scripted_flow(
                corrections_definition,
                tokens,
                mode=FlowMode.CREATE,
            )
            assert corrections_projection.submit_eligible
            overrides: dict[str, str] = {}
            for row in selected:
                casilla_id = row.casilla_id
                assert isinstance(casilla_id, str)
                overrides[casilla_id] = (corrections_state.answers.get(value_page_id(casilla_id)) or "").strip()
            derived_kind = (corrections_state.answers.get(KIND_PAGE_ID) or "").strip()
            derived_motive = (corrections_state.answers.get(MOTIVE_PAGE_ID) or "").strip() or None
            derived_reason = (corrections_state.answers.get(REASON_PAGE_ID) or "").strip()
            return overrides, derived_kind, derived_motive, derived_reason
        finally:
            ACTIVE_RUNS.pop(run_id, None)


def _amend_via_shared_path(
    *,
    from_filing_record_id: str,
    overrides: dict[str, str],
    kind: str,
    runtime_profile: HumanProbeSession,
    motive: str | None = None,
    reason: str,
    bindings: dict[str, str] | None = None,
):
    """Invoke ``work amend`` -- the shared composition path the wizard delegates to."""
    set_flags: list[str] = []
    for casilla_id, value in overrides.items():
        set_flags += ["--set", f"{casilla_id}={value}"]
    for binding_id, value in (bindings or {}).items():
        set_flags += ["--binding", f"{binding_id}={value}"]
    motive_flags = ["--m303-rectificativa-motive", motive] if motive is not None else []
    return _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "amend",
            "--from-filing-record", from_filing_record_id,
            "--kind", kind,
            *motive_flags,
            "--reason", reason,
            *set_flags,
        ],
        runtime_profile=runtime_profile,
    )  # fmt: skip


def _permitted_kind_choice_values(
    work_unit_id: str,
    *,
    change_numbers: list[str],
) -> tuple[str, ...]:
    """Return the amendment-kind SELECT's offered choice values for a baseline.

    Projects the wizard's own second-round definition and reads the kind
    page's closed choice set, so the test asserts period-awareness against
    the exact choices an operator is offered.
    """
    run_id = "test-amend-kind-choices"
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with open_test_profile_session(bucket_id):
        baseline = _amendable_baseline(work_unit_id, bucket_id=bucket_id)
        context = baseline.context
        baseline_values, amendable = baseline.baseline_values, baseline.amendable
        by_number = {row.number: row for row in amendable}
        selected = tuple(by_number[number] for number in change_numbers)
        ACTIVE_RUNS[run_id] = {}
        try:
            definition = values_kind_reason_definition(
                selected=selected,
                baseline_values=baseline_values,
                permitted_amendment_kinds=context.permitted_amendment_kinds,
                m303_rectificativa_motive_applicable=context.m303_rectificativa_motive_applicable,
                run_token=run_id,
            )
            kind_page = next(
                page for section in definition.sections for page in section.items if page.id == KIND_PAGE_ID
            )
            assert isinstance(kind_page, FlowPage)
            return tuple(choice.value for choice in kind_page.choices)
        finally:
            ACTIVE_RUNS.pop(run_id, None)


def test_amend_wizard_scripted_sequence_files_m130_complementaria(
    _operator_profile: HumanProbeSession,
) -> None:
    """The wizard's scripted definitions, fed to the shared amend path, file the correction.

    The substrate's scripted driver walks the wizard's own selection CHECKBOX
    (casilla 01) and its values/kind/reason round (corrected value, kind,
    reason), and those exact answers -- fed through the identical
    ``work amend`` composition the wizard uses -- supersede the imported
    AEAT-attested baseline with the corrected casilla value.
    """
    work_unit_id = create_m130_work_unit()
    baseline_filing_id = _import_external_baseline(work_unit_id)

    overrides, kind, motive, reason = _scripted_amend(
        work_unit_id,
        change_numbers=["01"],
        corrected_by_number={"01": str(_CORRECTED_INGRESOS)},
        kind="complementaria",
        reason="under-reported turnover",
    )
    assert motive is None
    assert kind == "complementaria"
    assert reason == "under-reported turnover"
    assert overrides == {"01": str(_CORRECTED_INGRESOS)}

    result = _amend_via_shared_path(
        from_filing_record_id=baseline_filing_id,
        overrides=overrides,
        kind=kind,
        motive=motive,
        reason=reason,
        runtime_profile=_operator_profile,
        bindings=_M130_UNRECORDED_BINDINGS,
    )
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output

    payload = unwrap_schema_envelope(result.output)
    assert payload["work_unit_id"] == work_unit_id
    assert payload["amendment_kind"] == "complementaria"
    assert payload["status"] == "vigente"
    # The new record is an internal filing envelope, not an AEAT-attested one.
    assert payload["external_evidence"] is None
    assert payload["amends_filing_record_id"] == baseline_filing_id

    # The correction is persisted, not merely reported.
    revision = unwrap_schema_envelope(
        _invoke(
            ["--format", "json", "app", "modelo", "work", "revision", payload["calculation_revision_id"]],
            runtime_profile=_operator_profile,
        ).output,
    )
    assert Decimal(revision["casilla_values"]["01"]) == _CORRECTED_INGRESOS
    assert Decimal(revision["casilla_values"]["02"]) == _BASELINE_GASTOS


def test_amend_m130_without_stated_bindings_refuses_naming_each_unrecorded_one(
    _operator_profile: HumanProbeSession,
) -> None:
    """Without the box sources the filing never recorded, the correction refuses and names them.

    The refusal is the recalculation's own: it lists every unrecorded binding the
    reached formulas read and points at the option that states them. Stating only
    some of them leaves the rest named, so a partial statement is no way around it.
    """
    work_unit_id = create_m130_work_unit()
    baseline_filing_id = _import_external_baseline(work_unit_id)
    partial = dict(list(_M130_UNRECORDED_BINDINGS.items())[:2])
    for bindings, expected_missing in (
        (None, set(_M130_UNRECORDED_BINDINGS)),
        (partial, set(_M130_UNRECORDED_BINDINGS) - set(partial)),
    ):
        result = _amend_via_shared_path(
            from_filing_record_id=baseline_filing_id,
            overrides={"01": str(_CORRECTED_INGRESOS)},
            kind="complementaria",
            reason="under-reported turnover",
            runtime_profile=_operator_profile,
            bindings=bindings,
        )
        assert result.exit_code != 0, result.output
        error = json.loads(result.output)["error"]
        assert error["code"] == "ERROR_CALCULATIONS_REGISTRY_VALIDATION"
        assert set(error["context"]["binding_ids"].split(", ")) == expected_missing
        assert "--binding" in error["message"]


def test_amend_m130_refuses_an_unknown_stated_binding(
    _operator_profile: HumanProbeSession,
) -> None:
    """A stated binding the pinned revision does not declare refuses as it does on calculate."""
    work_unit_id = create_m130_work_unit()
    baseline_filing_id = _import_external_baseline(work_unit_id)
    result = _amend_via_shared_path(
        from_filing_record_id=baseline_filing_id,
        overrides={"01": str(_CORRECTED_INGRESOS)},
        kind="complementaria",
        reason="under-reported turnover",
        runtime_profile=_operator_profile,
        bindings={**_M130_UNRECORDED_BINDINGS, "modelo-130-no-such-binding": "1"},
    )
    assert result.exit_code != 0, result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "REFUSED_MODELO_CALCULATE_BINDING_INPUT"
    assert error["context"]["key"] == "modelo-130-no-such-binding"


def test_amend_wizard_scripted_sequence_files_m303_rectificativa(
    _operator_profile: HumanProbeSession,
) -> None:
    """An Autoliquidación Rectificativa on M303 files through the wizard's scripted drive.

    Modelo 303 adopts the unified ``autoliquidación rectificativa`` (LGT art.
    120.4, Orden HAC/819/2024) from 2024 periods 09/3T onward, so the horizon year's 1T is
    rectificativa-effective. The correction LOWERS the declared base imponible
    -- a direction a self-filed complementaria could not lawfully carry -- so a
    rectificativa is the only mechanism that can file it. The wizard's scripted
    selection + values/kind/reason answers file it through the shared amend
    path.
    """
    work_unit_id = create_m303_work_unit()
    baseline_filing_id = _import_external_m303_baseline(work_unit_id)

    overrides, kind, motive, reason = _scripted_amend(
        work_unit_id,
        change_numbers=["07"],
        corrected_by_number={"07": str(_M303_CORRECTED_BASE_GENERAL)},
        kind="rectificativa",
        motive=_M303_RECTIFICATIVA_MOTIVE,
        reason="overstated base imponible",
    )
    assert kind == "rectificativa"
    assert motive == _M303_RECTIFICATIVA_MOTIVE

    result = _amend_via_shared_path(
        from_filing_record_id=baseline_filing_id,
        overrides=overrides,
        kind=kind,
        motive=motive,
        reason=reason,
        runtime_profile=_operator_profile,
    )
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output

    payload = unwrap_schema_envelope(result.output)
    assert payload["amendment_kind"] == "rectificativa"
    assert payload["m303_rectificativa_motive"] == _M303_RECTIFICATIVA_MOTIVE
    assert payload["status"] == "vigente"
    assert payload["external_evidence"] is None
    assert payload["amends_filing_record_id"] == baseline_filing_id

    revision = unwrap_schema_envelope(
        _invoke(
            ["--format", "json", "app", "modelo", "work", "revision", payload["calculation_revision_id"]],
            runtime_profile=_operator_profile,
        ).output,
    )
    assert Decimal(revision["casilla_values"]["07"]) == _M303_CORRECTED_BASE_GENERAL


def test_work_amend_m303_rectificativa_missing_motive_refuses_before_persistence(
    _operator_profile: HumanProbeSession,
) -> None:
    """The public command cannot infer the motive from kind, casilla, result, or reason."""
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="303",
        filing_year=_YEAR,
        period="1T",
        revision=_m303_revision_id(filing_year=_YEAR, period="1T"),
    )
    baseline_filing_id = _import_external_m303_baseline(work_unit_id, runtime_profile=_operator_profile)
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    before = _profile_amend_catalogue_state(runtime_profile=_operator_profile, bucket_id=bucket_id)

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "amend",
            "--from-filing-record",
            baseline_filing_id,
            "--kind",
            "rectificativa",
            "--reason",
            "rectificaciones with a lower result must not be inferred",
            "--set",
            f"07={_M303_CORRECTED_BASE_GENERAL}",
        ],
        runtime_profile=_operator_profile,
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "REFUSED_MODELO_M303_RECTIFICATIVA_MOTIVE", result.output
    context = error["context"]
    assert context["modelo"] == "303", result.output
    assert context["amendment_kind"] == "rectificativa", result.output
    assert context["motive_applicable"] == "true", result.output
    assert context["motive_present"] == "false", result.output
    assert context["terminal_condition"] == "refused", result.output
    # Refused before the amendment writes anything: nothing may have changed.
    assert context["effect"] == "none", result.output
    assert _profile_amend_catalogue_state(runtime_profile=_operator_profile, bucket_id=bucket_id) == before


def test_work_amend_refuses_free_text_m303_rectificativa_motive_at_the_public_parser() -> None:
    """The CLI accepts only the two domain-enum tokens, never arbitrary prose."""
    result = _invoke(
        [
            "app",
            "modelo",
            "work",
            "amend",
            "--from-filing-record",
            "f" * 64,
            "--kind",
            "rectificativa",
            "--m303-rectificativa-motive",
            "operator prose",
            "--reason",
            "operator prose",
            "--set",
            "07=1.00",
        ],
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_amend_wizard_scripted_inputs_match_hand_built_work_amend(
    _operator_profile: HumanProbeSession,
) -> None:
    """Wizard-derived amend inputs and a hand-built ``work amend`` agree exactly.

    Two independently-seeded M303 horizon-year baselines (different quarters, both
    rectificativa-effective) are amended identically: one through the wizard's
    scripted-derived inputs, one through the raw ``work amend`` flag grammar.
    Both must resolve to the same persisted outcome -- proof the wizard is a
    guided front end over the one ``amend_modelo_revision`` path
    (``aeat-architecture-boundaries``), not a second,
    independently-derived amendment surface.
    """
    wizard_unit_id = create_m303_work_unit()
    wizard_baseline_filing_id = _import_external_m303_baseline(
        wizard_unit_id,
        csv="JUST20253031TRECTWIZARD",
    )
    overrides, kind, motive, reason = _scripted_amend(
        wizard_unit_id,
        change_numbers=["07"],
        corrected_by_number={"07": str(_M303_CORRECTED_BASE_GENERAL)},
        kind="rectificativa",
        motive=_M303_RECTIFICATIVA_MOTIVE,
        reason="wizard-driven rectificativa",
    )
    hand_unit_id = create_modelo_work_unit_via_cli(
        modelo="303",
        filing_year=_YEAR,
        period="2T",
        revision=_m303_revision_id(filing_year=_YEAR, period="2T"),
    )
    hand_baseline_filing_id = _import_external_m303_baseline(
        hand_unit_id,
        csv="JUST20253032TRECTHANDBUILT",
    )
    wizard_result = _amend_via_shared_path(
        from_filing_record_id=wizard_baseline_filing_id,
        overrides=overrides,
        kind=kind,
        motive=motive,
        reason=reason,
        runtime_profile=_operator_profile,
    )
    assert wizard_result.exit_code == 0, wizard_result.output
    wizard_payload = unwrap_schema_envelope(wizard_result.output)

    hand_built_result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "amend",
            "--from-filing-record", hand_baseline_filing_id,
            "--kind", "rectificativa",
            "--m303-rectificativa-motive", _M303_RECTIFICATIVA_MOTIVE,
            "--reason", "hand-built rectificativa",
            "--set", f"07={_M303_CORRECTED_BASE_GENERAL}",
        ],
        runtime_profile=_operator_profile,
    )  # fmt: skip
    assert hand_built_result.exit_code == 0, f"{hand_built_result.output}"
    hand_built_payload = unwrap_schema_envelope(hand_built_result.output)

    # The wizard-derived override set is exactly the hand-typed one.
    assert overrides == {"07": str(_M303_CORRECTED_BASE_GENERAL)}

    assert wizard_payload["amendment_kind"] == hand_built_payload["amendment_kind"] == "rectificativa"
    assert wizard_payload["amends_filing_record_id"] == wizard_baseline_filing_id
    assert hand_built_payload["amends_filing_record_id"] == hand_baseline_filing_id
    for field in _AMEND_PARITY_SPINE:
        assert wizard_payload[field] == hand_built_payload[field], field

    # The persisted revisions agree -- the parity claim is about stored state.
    wizard_revision = unwrap_schema_envelope(
        _invoke(
            ["--format", "json", "app", "modelo", "work", "revision", wizard_payload["calculation_revision_id"]],
            runtime_profile=_operator_profile,
        ).output,
    )
    hand_built_revision = unwrap_schema_envelope(
        _invoke(
            [
                "--format", "json",
                "app", "modelo", "work", "revision", hand_built_payload["calculation_revision_id"],
            ],
            runtime_profile=_operator_profile,
        ).output,
    )  # fmt: skip
    assert wizard_revision["casilla_values"]["07"] == hand_built_revision["casilla_values"]["07"]
    assert Decimal(wizard_revision["casilla_values"]["07"]) == _M303_CORRECTED_BASE_GENERAL

    # The corrected casilla carries identical legal grounding through both
    # surfaces -- the persisted observation is where that grounding actually
    # has to survive (``aeat-calculation-grounding``).
    wizard_obs = _casilla_observation(wizard_revision, "07")
    hand_built_obs = _casilla_observation(hand_built_revision, "07")
    assert wizard_obs["value"] == hand_built_obs["value"]
    assert Decimal(wizard_obs["value"]) == _M303_CORRECTED_BASE_GENERAL
    assert wizard_obs["legal_refs"], "corrected casilla must carry legal_refs"
    assert wizard_obs["legal_refs"] == hand_built_obs["legal_refs"]
    assert wizard_obs["source_refs"] == hand_built_obs["source_refs"]


def test_amend_wizard_kind_select_offers_only_period_permitted_kinds(seed_profile: ProfileSeeder) -> None:
    """The amendment-kind SELECT is period-aware: it offers only the legally-available kinds.

    M303 horizon-year 1T is post-unification, so the kind SELECT offers ``rectificativa``
    and NOT ``complementaria`` (the rectificativa has replaced it for ordinary
    corrections); M130 has no rectificativa regime, so its SELECT offers
    ``complementaria`` and NOT ``rectificativa``. Asserted on the projected
    choice set the operator is actually offered, not on any localized prose.
    """
    _create_profile(seed_profile)

    m303_unit_id = create_m303_work_unit()
    _import_external_m303_baseline(m303_unit_id)
    m303_kinds = _permitted_kind_choice_values(m303_unit_id, change_numbers=["07"])
    assert "rectificativa" in m303_kinds
    assert "complementaria" not in m303_kinds

    m130_unit_id = create_m130_work_unit(period="2T")
    _import_external_baseline(m130_unit_id, csv="JUST20251302TKINDS")
    m130_kinds = _permitted_kind_choice_values(m130_unit_id, change_numbers=["01"])
    assert "complementaria" in m130_kinds
    assert "rectificativa" not in m130_kinds


def test_amend_wizard_scripting_a_non_permitted_kind_is_refused(seed_profile: ProfileSeeder) -> None:
    """Scripting a kind the SELECT does not offer is refused by the substrate, nothing filed.

    ``complementaria`` is not a permitted M303 horizon-year kind, so it is not a choice
    on the amendment-kind SELECT; the scripted driver rejects the unknown token
    with the substrate's typed answer-rejected error rather than filing it.
    """
    _create_profile(seed_profile)
    work_unit_id = create_m303_work_unit()
    _import_external_m303_baseline(work_unit_id)

    with pytest.raises(FlowAnswerError):
        _scripted_amend(
            work_unit_id,
            change_numbers=["07"],
            corrected_by_number={"07": str(_M303_CORRECTED_BASE_GENERAL)},
            kind="complementaria",
            reason="should not file",
        )


def test_amend_wizard_blank_selection_yields_no_corrections(seed_profile: ProfileSeeder) -> None:
    """A blank CHECKBOX selection reads back as no selected casillas.

    The selection page is optional, so a scripted blank answer submits with an
    empty selection -- the wizard turns that into the no-corrections refusal
    before any value is asked. Proven at the substrate level the wizard reads.
    """
    _create_profile(seed_profile)
    work_unit_id = create_m130_work_unit()
    _import_external_baseline(work_unit_id)

    run_id = "test-amend-blank"
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with open_test_profile_session(bucket_id):
        baseline = _amendable_baseline(work_unit_id, bucket_id=bucket_id)
        unit = baseline.unit
        baseline_values, amendable = baseline.baseline_values, baseline.amendable
        ACTIVE_RUNS[run_id] = {}
        try:
            definition = modelo_amend_wizard_commands_selection_definition(
                amendable=amendable,
                baseline_values=baseline_values,
                unit=unit,
                run_token=run_id,
            )
            state, projection = run_scripted_flow(definition, [""], mode=FlowMode.CREATE)
            assert projection.submit_eligible
            assert selected_rows(amendable=amendable, unit=unit, state=state) == ()
        finally:
            ACTIVE_RUNS.pop(run_id, None)


def test_amend_wizard_non_interactive_host_refuses_with_the_typed_console_error(
    _operator_profile: HumanProbeSession,
) -> None:
    """A non-TTY caller with an amendable baseline gets the substrate's typed refusal.

    The test process is non-interactive, so the wizard -- which has a CHECKBOX
    selection page to present -- must refuse through the flow substrate's
    unsupported-console error rather than block. Asserted structurally on the
    envelope error code, never on localized prose.
    """
    work_unit_id = create_m130_work_unit()
    _import_external_baseline(work_unit_id)

    result = _invoke(
        ["--format", "json", "app", "modelo", "work", "amend-wizard", work_unit_id],
        runtime_profile=_operator_profile,
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "REFUSED_FLOW_UNSUPPORTED_CONSOLE"


def test_amend_wizard_refuses_without_evidence_baseline(seed_profile: ProfileSeeder) -> None:
    """A local work unit cannot enter the external-filing amendment path.

    The evidence check runs before any flow is constructed, so the refusal is a
    plain instructive parameter error, never the console refusal.
    """
    _create_profile(seed_profile)
    work_unit_id = create_m130_work_unit()

    result = _invoke(["--format", "json", "app", "modelo", "work", "amend-wizard", work_unit_id])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
