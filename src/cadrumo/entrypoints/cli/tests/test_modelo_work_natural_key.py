"""Natural-key CLI workflow coverage for modelo work commands."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core import STR_KEYED_MAPPING_ADAPTER
from ....tests.cli_envelope import unwrap_envelope_notices as _notices
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from ....tests.user_profile import register_cli_profile
from ._m130_source_support import seed_m130_expense_transaction, seed_m130_income_transaction
from ._modelo_work_ux_support import _seed_m111_retencion_observation

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _envelope_status(output: str) -> str:
    """Return the outer envelope ``status`` field from a CLI ``--json`` document."""
    status = STR_KEYED_MAPPING_ADAPTER.validate_json(output)["status"]
    assert isinstance(status, str)
    return status


def _create_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator",
            "identity.surnames": "Natural Key",
            "activities.description": "design",
            "tax_residence.jurisdiction_scope": "common_regime",
        },
    )


def _create_first_year_activity_profile() -> None:
    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": "12345678Z",
            "identity.name": "Daniel",
            "identity.surnames": "Persona",
            "activities.description": "consultoria",
            "censo.activity_start_date": "2025-01-01",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "irpf.estimation_regime": "directa_simplificada",
            "iva.regime": "GENERAL",
            "fiscal_residency.status": "resident_irpf",
            "tax_residence.ccaa": "madrid",
        },
    )


def _create_autonoma_2024_activity_profile() -> None:
    register_cli_profile(
        label="autonoma",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": "12345678Z",
            "identity.name": "Ana",
            "identity.surnames": "Persona",
            "activities.description": "consultoria",
            "censo.activity_start_date": "2024-01-01",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "irpf.estimation_regime": "directa_simplificada",
            "iva.regime": "GENERAL",
            "fiscal_residency.status": "resident_irpf",
            "tax_residence.ccaa": "madrid",
        },
    )


def test_modelo_111_calculate_verify_export_without_copied_ids(tmp_path: Path) -> None:
    """Create, calculate, verify, and export through natural keys."""

    _create_profile()
    created = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    work_unit_id = _payload(created.output)["work_unit_id"]
    _seed_m111_retencion_observation()

    status = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "status",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert status.exit_code == 0, status.output
    status_notice = next(
        notice for notice in _notices(status.output) if notice["code"] == "modelo.work.status.next_action"
    )
    assert status_notice["action"]["action"] == {
        "action_id": "operator.modelo.work.calculate",
        "target_command_key": "modelo.work.calculate",
        "cli_path": ["app", "modelo", "work", "calculate"],
    }
    assert status_notice["action"]["argument_bindings"][0]["value"] == work_unit_id

    calculated = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0, calculated.output
    calculation_revision_id = _payload(calculated.output)["calculation_revision_id"]
    assert _payload(calculated.output)["work_unit_id"] == work_unit_id

    verified = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "verify",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert verified.exit_code == 0, verified.output
    assert _payload(verified.output)["calculation_revision_id"] == calculation_revision_id
    assert _payload(verified.output)["granted_verificado_completo"] is True
    # A granted verification has no recovery action or speculative next-step
    # notice: export requires additional material input that this verifier does
    # not own.
    assert _envelope_status(verified.output) == "success", verified.output
    granted_notices = _notices(verified.output)
    assert granted_notices == [], verified.output

    out = tmp_path / "modelo-111.txt"
    exported = _invoke(
        [
            "--format", "json",
            "app", "modelo", "export",
            "--modelo", "111", "--year", "2025", "--period", "1T",
            "--output", str(out),
        ],
    )  # fmt: skip
    assert exported.exit_code == 0, exported.output
    payload = _payload(exported.output)
    assert payload["work_unit_id"] == work_unit_id
    assert payload["calculation_revision_id"] == calculation_revision_id
    assert out.exists()
    assert out.stat().st_size > 0


def test_modelo_verify_is_idempotent_across_both_addressing_modes() -> None:
    """Re-verifying an already-verified revision is a guarded no-op in both addressing modes.

    aeat-cli-contract: the verb must NOT refuse a
    re-verify. Whether addressed by natural key (work-addressed) or by explicit
    calculation-revision id (revision-addressed), the second call returns exit 0,
    the SAME verification report id (no duplicate report), and surfaces the
    ``modelo.work.verify.idempotent_noop`` info notice. This exercises the real
    ``work verify`` verb end to end, guarding against the resolver refusing a
    non-draft revision upstream of the collapse.
    """
    _create_profile()
    created = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    _seed_m111_retencion_observation()
    calculated = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0, calculated.output
    calculation_revision_id = _payload(calculated.output)["calculation_revision_id"]

    first = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "verify",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert first.exit_code == 0, first.output
    assert _payload(first.output)["granted_verificado_completo"] is True, first.output
    report_id = _payload(first.output)["verification_report_id"]
    # The first verify grants and carries no idempotent-no-op notice.
    assert "modelo.work.verify.idempotent_noop" not in [n["code"] for n in _notices(first.output)], first.output

    # Work-addressed re-verify (natural key): collapses to the existing report.
    work_addressed = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "verify",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert work_addressed.exit_code == 0, work_addressed.output
    assert _payload(work_addressed.output)["verification_report_id"] == report_id, work_addressed.output
    assert _payload(work_addressed.output)["calculation_revision_id"] == calculation_revision_id, work_addressed.output
    work_addressed_noop = next(
        n for n in _notices(work_addressed.output) if n["code"] == "modelo.work.verify.idempotent_noop"
    )
    assert work_addressed_noop["severity"] == "info", work_addressed.output
    assert work_addressed_noop["context"]["verification_report_id"] == report_id, work_addressed.output

    # Revision-addressed re-verify (explicit id): collapses to the SAME report.
    revision_addressed = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "verify", calculation_revision_id,
        ],
    )  # fmt: skip
    assert revision_addressed.exit_code == 0, revision_addressed.output
    assert _payload(revision_addressed.output)["verification_report_id"] == report_id, revision_addressed.output
    assert "modelo.work.verify.idempotent_noop" in [n["code"] for n in _notices(revision_addressed.output)], (
        revision_addressed.output
    )


def test_modelo_130_verify_by_natural_key_refuses_without_clean_cross_period_state() -> None:
    """Modelo 130 cannot be verified as complete without upstream clean-state proof."""

    _create_profile()
    seed_m130_income_transaction(
        amount=Decimal("12000.00"),
        filing_year=2025,
        source_key="natural-key",
    )
    created = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    work_unit_id = _payload(created.output)["work_unit_id"]

    # Casilla 02 (gastos) is bucket-bound (aggregated from deductible ledger
    # rows) and cannot be supplied via --casilla; with no expense seeded it
    # resolves to 0, which is immaterial to this cross-period clean-state check.
    calculated = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--binding", "irpf.previous_year_economic_activity_net_income=13000",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0, calculated.output
    calculation_revision_id = _payload(calculated.output)["calculation_revision_id"]
    assert _payload(calculated.output)["work_unit_id"] == work_unit_id

    verified = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "verify",
            "--modelo", "130", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert verified.exit_code == 1, verified.output
    payload = _payload(verified.output)
    assert payload["calculation_revision_id"] == calculation_revision_id
    assert payload["granted_verificado_completo"] is False
    assert payload["findings"][0]["kind"] == "cross_period_dependency_unclean"
    finding_action = payload["findings"][0]["action"]
    assert finding_action["action"] is None
    assert finding_action["conditionality"] == "not_applicable"
    assert finding_action["missing_argument_names"] == []
    assert finding_action["no_recovery_outcome"] == "operator_decision"
    assert "next_action" not in payload["findings"][0]

    # The shared-spine contract: a verify carrying a blocking finding must NOT
    # read status "success" with an empty notices list while exit code is 1.
    # The blocking finding is projected onto the notices channel and the
    # envelope status derives to "warning" in lock-step with the exit-1
    # (NoticeSeverity has no ERROR member; a non-granted verify must read a
    # non-success status).
    assert _envelope_status(verified.output) == "warning", verified.output
    notices = _notices(verified.output)
    assert notices, verified.output
    blocking = next(
        notice for notice in notices if notice["code"] == "modelo.work.verify.finding.cross_period_dependency_unclean"
    )
    # The finding's true severity survives onto a non-action notice; the
    # blocking-vs-advisory distinction lives on the context while the result
    # carries the application-owned typed recovery verdict.
    assert blocking["severity"] == "warning"
    assert blocking["context"]["severity"] == "blocking"
    assert blocking["context"]["kind"] == "cross_period_dependency_unclean"
    assert blocking["context"]["blocker_codes"]
    assert all(blocker_code for blocker_code in blocking["context"]["blocker_codes"].split("|"))
    assert blocking["action"] is None


def test_autonoma_m130_2024_1t_calculate_by_natural_key_from_blank_ledger_state() -> None:
    """The reported first-quarter blank-state ledger flow stays on the public CLI path.

    The expected casillas come from the acceptance evidence, not from
    reimplementing the Modelo 130 formulas in the test: ledger income 3000,
    deductible expense 600, and first-year activity blank prior state produce
    the accepted 1T draft values 01=3000, 02=600, 03=2400, 19=380.
    """

    _create_autonoma_2024_activity_profile()
    seed_m130_income_transaction(
        amount=Decimal("3000.00"),
        filing_year=2024,
        source_key="autonoma-blank-1t",
    )
    seed_m130_expense_transaction(
        amount=Decimal("600.00"),
        filing_year=2024,
        source_key="autonoma-blank-1t",
    )
    created = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2024", "--period", "1T",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output

    calculated = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate",
            "--modelo", "130", "--year", "2024", "--period", "1T",
            "--by", "Ana",
        ],
    )  # fmt: skip

    assert calculated.exit_code == 0, calculated.output
    assert "validate_construct_closure() missing" not in calculated.output
    assert "Traceback" not in calculated.output
    casillas = _payload(calculated.output)["casilla_values"]
    assert Decimal(casillas["01"]) == Decimal("3000.00")
    assert Decimal(casillas["02"]) == Decimal("600.00")
    assert Decimal(casillas["03"]) == Decimal("2400.00")
    assert Decimal(casillas["19"]) == Decimal("380.00")


def test_modelo_130_first_year_activity_can_file_late_by_natural_key() -> None:
    """A verified M130 first-year activity revision can seed later local carry."""

    _create_first_year_activity_profile()
    seed_m130_income_transaction(
        amount=Decimal("4000.00"),
        filing_year=2025,
        source_key="first-year-file",
    )
    created = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output

    calculated = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--binding", "irpf.previous_year_economic_activity_net_income=0",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0, calculated.output
    calculation_revision_id = _payload(calculated.output)["calculation_revision_id"]

    verified = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "verify",
            "--modelo", "130", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert verified.exit_code == 0, verified.output
    verify_payload = _payload(verified.output)
    assert verify_payload["calculation_revision_id"] == calculation_revision_id
    assert verify_payload["granted_verificado_completo"] is True

    filed = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "file",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--select", "current",
            "--by", "Daniel",
            "--notes", "local-only first-year M130 filing",
        ],
    )  # fmt: skip
    assert filed.exit_code == 0, filed.output
    file_payload = _payload(filed.output)
    assert file_payload["calculation_revision_id"] == calculation_revision_id
    assert file_payload["aeat_accepted"] is False


def test_work_create_refuses_conflicting_registry_revision_for_visible_target() -> None:
    """A second registry revision for the same active visible target is refused."""

    _create_profile()
    first = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert first.exit_code == 0, first.output

    result = _invoke(
        [
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "conflicting-registry-revision",
        ],
    )  # fmt: skip
    assert result.exit_code != 0
    assert "2019-y-siguientes" in result.output
    assert "conflicting-registry-revision" in result.output
    assert "Traceback" not in result.output

    listed = _invoke(["--format", "json", "app", "modelo", "work", "list"])
    assert listed.exit_code == 0, listed.output
    assert _payload(listed.output)["work_unit_count"] == 1


def test_adjacent_work_commands_resolve_visible_targets() -> None:
    """Adjacent work commands share the natural-key selector where applicable."""

    _create_profile()
    created = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    work_unit_id = _payload(created.output)["work_unit_id"]
    _seed_m111_retencion_observation()

    renamed = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "rename",
            "--modelo", "111", "--year", "2025", "--period", "1T",
            "--name", "Natural Target",
        ],
    )  # fmt: skip
    assert renamed.exit_code == 0, renamed.output
    assert _payload(renamed.output)["work_unit_id"] == work_unit_id
    assert _payload(renamed.output)["name"] == "Natural Target"

    calculated = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0, calculated.output
    calculation_revision_id = _payload(calculated.output)["calculation_revision_id"]

    shown_revision = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "revision",
            "--modelo", "111", "--year", "2025", "--period", "1T",
            "--select", "current",
        ],
    )  # fmt: skip
    assert shown_revision.exit_code == 0, shown_revision.output
    assert _payload(shown_revision.output)["calculation_revision_id"] == calculation_revision_id

    history = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "history",
            "--modelo", "111", "--year", "2025", "--period", "1T",
        ],
    )  # fmt: skip
    assert history.exit_code == 0, history.output
    assert _payload(history.output)["work_unit_id"] == work_unit_id
    assert _payload(history.output)["event_count"] >= 2
    history_notice = next(
        notice for notice in _notices(history.output) if notice["code"] == "modelo.work.history.next_action"
    )
    assert history_notice["action"]["action"] == {
        "action_id": "operator.modelo.work.status",
        "target_command_key": "modelo.work.status",
        "cli_path": ["app", "modelo", "work", "status"],
    }
    assert history_notice["action"]["argument_bindings"][0]["value"] == work_unit_id

    discarded = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "discard",
            "--modelo", "111", "--year", "2025", "--period", "1T",
            "--reason", "natural-key test",
            "--yes",
        ],
    )  # fmt: skip
    assert discarded.exit_code == 0, discarded.output
    assert _payload(discarded.output)["work_unit_id"] == work_unit_id
    assert _payload(discarded.output)["state"] == "descartado"


def test_reconcile_commands_advertise_natural_target_options() -> None:
    """Reconcile commands keep exact ids but advertise natural-key targeting."""

    for args in (
        ["app", "modelo", "reconcile", "pull", "--help"],
        ["app", "modelo", "reconcile", "file", "--help"],
    ):
        result = _invoke(args)
        assert result.exit_code == 0, result.output
        assert "--modelo" in result.output
        assert "--year" in result.output
        assert "--period" in result.output
