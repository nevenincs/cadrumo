"""Real-behavior CLI tests for ``aeat app overview pipeline``.

Drives the real ``cadrumo`` CLI against an isolated encrypted backend to pin the
cross-domain pipeline-health dashboard's operator contract from #238:

* a fresh profile with no ledger data and no modelo work units for the
  period reports ``ready=False`` with an empty ``modelos`` list and a
  ``0``-count ledger section;
* a period with one imported-but-unclassified transaction surfaces the
  pending-review count and keeps the report ``ready=False``;
* a modelo work unit driven through calculate/verify/file for the period
  reports its readiness row as ``filed``, and a clean, fully-filed period
  reports ``ready=True``;
* the command is read-only and safe to run repeatedly.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.overview.pipeline_health import ModeloReadinessState
from ....application.user_profile.login_session import login_profile, resolve_login_target
from ....core.config import override_settings
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.verification_report import (
    VerificationCompletenessStatus,
    VerificationReport,
    derive_verification_report_id,
)
from ....domain.modelos.verification_repository import upsert_verification_report
from ....tests.cli_envelope import unwrap_envelope_notices as _notices
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from .._overview_payloads import OverviewPipelineModeloPayload
from ._runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NATIVE_FIXTURE: ContextVar[NativeCliProfileFixture] = ContextVar("pipeline_native_fixture")
_AUTHORITY_PIN: ContextVar[PinnedAuthorityOperation] = ContextVar("pipeline_authority_pin")
_LABEL = "Native pipeline operator"


@pytest.fixture
def _native_backend(tmp_path: Path, authority_operation: PinnedAuthorityOperation) -> Iterator[None]:
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture_token = _NATIVE_FIXTURE.set(fixture)
        pin_token = _AUTHORITY_PIN.set(authority_operation)
        try:
            yield
        finally:
            _AUTHORITY_PIN.reset(pin_token)
            _NATIVE_FIXTURE.reset(fixture_token)


def _facts(*, activity_start_date: str | None = None) -> dict[str, str]:
    return {
        "taxpayer_type.entity_type": "natural_person",
        "identity.tax_id": "12345678Z",
        "identity.name": "Native",
        "identity.surnames": "Pipeline",
        "activities.description": "design",
        "censo.activity_start_date": activity_start_date or "2025-01-01",
        "taxpayer_type.irpf_income_categories": "actividad_economica",
        "irpf.estimation_regime": "directa_normal",
        "taxpayer_type.fiscal_residency": "resident_irpf",
        "tax_residence.ccaa": "madrid",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.regime": "GENERAL",
        "iva.m303_regime_composition": "general",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    }


def _create_profile(*, activity_start_date: str | None = None) -> None:
    _NATIVE_FIXTURE.get().register(label=_LABEL, facts=_facts(activity_start_date=activity_start_date))
    close_active_bucket_session()


def _invoke(arguments: list[str]):
    fixture = _NATIVE_FIXTURE.get()
    assert fixture.label == _LABEL
    close_active_bucket_session()
    with override_settings(cadrumo_cli_reveal_identifiers=False):
        result = invoke_cached_cli(
            ["--language", "en", "--profile", fixture.label, "--profile-secrets-stdin", *arguments],
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )
    assert fixture.passphrase not in result.output
    return result


def _create_complete_pipeline_profile() -> None:
    _create_profile(activity_start_date="2025-10-01")


@pytest.mark.usefixtures("_native_backend")
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_pipeline_fresh_profile_reports_not_ready_with_empty_modelos() -> None:
    """A brand-new profile with no ledger data and no work units for the
    period: zero ledger rows, an empty modelo list, and an honest
    ``ready=False`` — there is nothing to be ready about yet."""

    _create_profile()

    result = _invoke(
        ["--format", "json", "app", "overview", "pipeline", "--year", "2025", "--period", "1T"],
    )
    assert result.exit_code == 0
    payload = _payload(result.output)

    assert payload["filing_year"] == 2025
    assert payload["period"] == "1T"
    assert payload["ledger"]["total_count"] == 0
    assert payload["modelos"] == []
    assert payload["total_blocking_findings"] == 0
    assert payload["total_warning_findings"] == 0
    assert payload["ready"] is False


@pytest.mark.usefixtures("_native_backend")
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_pipeline_surfaces_unclassified_ledger_pending_count() -> None:
    """A manually-added transaction with no classification shows up as a
    pending-review row in the ledger section and keeps the period unready."""

    _create_profile()
    added = _invoke(
        [
            "app", "ledger", "add",
            "--date", "2025-02-10", "--amount", "1000.00",
            "--direction", "INCOMING", "--description", "Factura cliente A",
        ],
    )  # fmt: skip
    assert added.exit_code == 0

    result = _invoke(
        ["--format", "json", "app", "overview", "pipeline", "--year", "2025", "--period", "1T"],
    )
    assert result.exit_code == 0
    payload = _payload(result.output)

    assert payload["ledger"]["total_count"] == 1
    assert payload["ledger"]["pending_review_count"] == 1
    assert payload["ready"] is False


@pytest.mark.usefixtures("_native_backend")
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_pipeline_shows_filed_modelo_readiness_row_and_reports_ready() -> None:
    """A Modelo 130 work unit driven through calculate/verify/file for the
    period reports a ``filed`` readiness row with zero outstanding
    findings; with a clean ledger for the same period the overall pipeline
    is honestly ``ready``."""

    _create_profile(activity_start_date="2025-10-01")
    created = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "4T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert created.exit_code == 0
    work_unit_id = _payload(created.output)["work_unit_id"]

    calculated = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "05=0.00",
            "--casilla", "06=0.00",
            "--binding", "irpf.previous_year_economic_activity_net_income=13000",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0

    verified = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "verify",
            "--modelo", "130", "--year", "2025", "--period", "4T",
        ],
    )  # fmt: skip
    assert verified.exit_code == 0
    assert _payload(verified.output)["granted_verificado_completo"] is True

    filed = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "file",
            "--modelo", "130", "--year", "2025", "--period", "4T",
        ],
    )  # fmt: skip
    assert filed.exit_code == 0

    result = _invoke(
        ["--format", "json", "app", "overview", "pipeline", "--year", "2025", "--period", "4T"],
    )
    assert result.exit_code == 0
    payload = _payload(result.output)

    assert payload["ledger"]["total_count"] == 0
    matching = [row for row in payload["modelos"] if row["modelo"] == "130"]
    assert len(matching) == 1
    row = matching[0]
    assert row["work_unit_id"] == work_unit_id
    assert row["state"] == "filed"
    assert row["blocking_finding_count"] == 0

    # A clean ledger (no rows to review) plus every modelo filed: the
    # composed pipeline verdict is honestly ready.
    assert payload["ready"] is True


@pytest.mark.usefixtures("_native_backend")
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_pipeline_calculated_but_unverified_unit_is_not_ready() -> None:
    """A modelo whose current revision is calculated but not yet verified
    reports the ``calculated`` state and keeps the pipeline unready."""

    _create_profile(activity_start_date="2025-10-01")
    created = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "4T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert created.exit_code == 0
    work_unit_id = _payload(created.output)["work_unit_id"]

    calculated = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "05=0.00",
            "--casilla", "06=0.00",
            "--binding", "irpf.previous_year_economic_activity_net_income=13000",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0

    result = _invoke(
        ["--format", "json", "app", "overview", "pipeline", "--year", "2025", "--period", "4T"],
    )
    assert result.exit_code == 0
    payload = _payload(result.output)

    matching = [row for row in payload["modelos"] if row["modelo"] == "130"]
    assert len(matching) == 1
    assert matching[0]["state"] == "calculated"
    assert payload["ready"] is False
    readiness_notices = [
        notice for notice in _notices(result.output) if notice["code"] == "overview.pipeline.modelo.calculated"
    ]
    assert readiness_notices
    assert all(
        notice["action"]
        == {
            "action": {
                "action_id": "operator.modelo.work.verify",
                "target_command_key": "modelo.work.verify",
                "cli_path": ["app", "modelo", "work", "verify"],
            },
            "argument_bindings": [
                {
                    "argument_name": "work_unit_id",
                    "status": "resolved",
                    "value": work_unit_id,
                    "source": "operator_action.verdict_context",
                    "source_key": "work_unit_id",
                    "source_evidence_id": None,
                },
            ],
        }
        for notice in readiness_notices
    )


@pytest.mark.usefixtures("_native_backend")
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_pipeline_distinguishes_persisted_incomplete_from_never_verified() -> None:
    """The latest persisted completeness outcome, not findings or revision state,
    decides readiness.

    A real calculated revision first renders ``calculated`` because no report
    exists. Persisting an ``INCOMPLETE`` report with zero findings then makes
    the exact CLI render ``incomplete``. This pins both distinctions and proves
    finding severity is not a shadow verification authority.
    """

    _create_complete_pipeline_profile()
    created = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "4T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert created.exit_code == 0
    work_unit_id = _payload(created.output)["work_unit_id"]

    calculated = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "05=0.00",
            "--casilla", "06=0.00",
            "--binding", "irpf.previous_year_economic_activity_net_income=13000",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0
    calculation_revision_id = _payload(calculated.output)["calculation_revision_id"]

    before = _invoke(
        ["--format", "json", "app", "overview", "pipeline", "--year", "2025", "--period", "4T"],
    )
    assert before.exit_code == 0
    before_row = next(row for row in _payload(before.output)["modelos"] if row["modelo"] == "130")
    assert before_row["state"] == ModeloReadinessState.CALCULATED.value
    assert before_row["summary"] != "Modelo 130: verification incomplete."

    run_at = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    report_id = derive_verification_report_id(
        calculation_revision_id=calculation_revision_id,
        completeness_status=VerificationCompletenessStatus.INCOMPLETE,
        findings=(),
        verified_by="pipeline-parity-test",
    )
    report = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=calculation_revision_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="130",
            revision_id="2019-y-siguientes",
            modelo_year=2025,
            period="4T",
        ),
        completeness_status=VerificationCompletenessStatus.INCOMPLETE,
        findings=(),
        missing_required_casilla_ids=(),
        run_at=run_at,
        verified_by="pipeline-parity-test",
        granted_verificado_completo=False,
    )
    bucket_id = resolve_login_target(_LABEL).bucket_id
    fixture = _NATIVE_FIXTURE.get()
    operation = _AUTHORITY_PIN.get()
    close_active_bucket_session()
    login = login_profile(
        name=_LABEL,
        passphrase_callback=lambda: fixture.passphrase,
        profile_decode_context=operation.profile_decode_context(),
    )
    assert login.bucket_id == bucket_id
    try:
        revision = (
            CalculationRevisionCatalogueRepository(bucket_id=bucket_id)
            .load(operation=operation)
            .get(calculation_revision_id)
        )
        assert revision is not None and revision.work_unit_id == work_unit_id
        repository = VerificationReportCatalogueRepository(bucket_id=bucket_id)
        repository.save(upsert_verification_report(repository.load(operation=operation), report), operation=operation)
    finally:
        close_active_bucket_session()

    after = _invoke(
        ["--format", "json", "app", "overview", "pipeline", "--year", "2025", "--period", "4T"],
    )
    assert after.exit_code == 0
    payload = _payload(after.output)
    after_row = next(row for row in payload["modelos"] if row["modelo"] == "130")
    assert after_row["state"] == ModeloReadinessState.INCOMPLETO.value
    assert after_row["blocking_finding_count"] == 0
    assert after_row["summary"] == "Modelo 130: verification incomplete."
    assert payload["ready"] is False
    assert any(notice["code"] == "overview.pipeline.modelo.incomplete" for notice in _notices(after.output))


@pytest.mark.usefixtures("_native_backend")
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_pipeline_is_read_only_and_safe_to_run_repeatedly() -> None:
    """Running the report twice in a row must be a pure read: the second
    invocation reports identical state, proving no mutation occurred."""

    _create_profile()

    first = _invoke(
        ["--format", "json", "app", "overview", "pipeline", "--year", "2025", "--period", "1T"],
    )
    second = _invoke(
        ["--format", "json", "app", "overview", "pipeline", "--year", "2025", "--period", "1T"],
    )
    assert first.exit_code == 0
    assert second.exit_code == 0
    assert _payload(first.output) == _payload(second.output)


def test_pipeline_modelo_row_enforces_the_canonical_readiness_contract() -> None:
    """The transport row must refuse what :class:`ModeloHealthRow` refuses.

    ``state`` is a closed ``ModeloReadinessState`` and both finding counts are
    cardinalities. The CLI row redeclared them as a free string and unbounded
    integers, so a bogus readiness state or a negative count could cross the
    ``overview.pipeline`` envelope.
    """
    row = OverviewPipelineModeloPayload(
        modelo="130",
        state=ModeloReadinessState.NOT_STARTED,
        summary="nothing calculated yet",
    )
    assert json.loads(row.model_dump_json())["state"] == ModeloReadinessState.NOT_STARTED.value

    base = {
        "modelo": "130",
        "state": ModeloReadinessState.NOT_STARTED,
        "summary": "s",
    }
    for label, override in (
        ("unknown readiness state", {"state": "bogus"}),
        ("negative blocking count", {"blocking_finding_count": -1}),
        ("negative warning count", {"warning_finding_count": -1}),
    ):
        try:
            OverviewPipelineModeloPayload.model_validate(base | override)
        except ValidationError:
            continue
        pytest.fail(f"{label} was accepted by the transport row")
