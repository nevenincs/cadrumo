"""A calculation note that withholds a filed figure refuses export and filing through the CLI.

Drives the real ``aeat`` CLI against isolated encrypted storage. A Modelo 130
declaration is calculated and verified through the CLI; the calculation the
declaration then points at carries one persisted blocking note, planted through
the real repositories under its content-derived id. ``modelo export`` and
``modelo work file`` both refuse it with the calculation-blocked code, name the
note's reason and write no file. A recalculation through the CLI makes a
calculation without the note current again, and the export succeeds. A control
in a fresh backend plants the identical calculation minus only the note and
exports it, so the note alone is what refuses.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from ....adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from ....core.aggregation import BindingSourceKind
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.config import override_settings
from ....core.i18n.render import tr
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevisionState,
    CalculationSourceIssue,
    derive_calculation_revision_id_from_revision,
)
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnitCatalogue
from ....tests.cli_envelope import require_error_document
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ._modelo_work_ux_support import operator_profile_facts
from .cli_runner import invoke_cached_cli
from .modelo_profile_seed import ProfileSeeder, seed_profile

__all__ = ["_isolated_cli_backend", "seed_profile"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_YEAR = "2025"
_PERIOD = "4T"
_REASON = "unrouted_declarable_quantity"
_BLOCKED_CODE = "REFUSED_MODELO_CALCULATION_BLOCKED"
# The prior-year net income only varies so that the clearing recalculation is a
# new calculation: calculations are content addressed, and an unchanged input set
# would resolve to the earlier clean calculation instead of a newer one.
_FIRST_PRIOR_YEAR_INCOME = "13000"
_LATER_PRIOR_YEAR_INCOME = "14000"


def _calculate_options(prior_year_income: str) -> tuple[str, ...]:
    return (
        "--casilla", "05=0.00",
        "--casilla", "06=0.00",
        "--binding", f"irpf.previous_year_economic_activity_net_income={prior_year_income}",
        "--binding", "modelo-130-resultados-negativos-anteriores=0",
    )  # fmt: skip


_BLOCKING_ISSUE = CalculationSourceIssue(
    reason=_REASON,
    binding_source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
    message="a synthetic withheld amount reached no box of the declaration",
    source_ref="ledger_transaction:synthetic-unrouted-row",
)


def _english_sentence() -> str:
    with override_settings(cadrumo_output_language="en"):
        return tr(f"application.modelo.calc_diagnostic.{_REASON}.what")


def _calculate_and_verify() -> tuple[str, str]:
    """Create, calculate and verify the Modelo 130 declaration through the CLI."""
    created = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", _YEAR, "--period", _PERIOD,
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    work_unit_id = _payload(created.output)["work_unit_id"]
    assert isinstance(work_unit_id, str)
    revision_id = _recalculate(work_unit_id, _FIRST_PRIOR_YEAR_INCOME)
    return work_unit_id, revision_id


def _recalculate(work_unit_id: str, prior_year_income: str) -> str:
    calculated = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id, *_calculate_options(prior_year_income)]
    )
    assert calculated.exit_code == 0, calculated.output
    verified = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "verify",
            "--modelo", "130", "--year", _YEAR, "--period", _PERIOD,
        ],
    )  # fmt: skip
    assert verified.exit_code == 0, verified.output
    verified_payload = _payload(verified.output)
    assert verified_payload["granted_verificado_completo"] is True
    revision_id = verified_payload["calculation_revision_id"]
    assert isinstance(revision_id, str)
    return revision_id


def _plant_current(work_unit_id: str, base_revision_id: str, issues: tuple[CalculationSourceIssue, ...]) -> str:
    """Persist ``base_revision_id`` carrying exactly ``issues`` and make it the declaration's current calculation.

    The planted calculation differs from the base only in its notes; its id is
    re-derived from its full content, as a calculation that recorded those
    notes would carry.
    """
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with open_test_profile_session(bucket_id):
        calculations = CalculationRevisionCatalogueRepository()
        base = calculations.load().get(base_revision_id)
        assert base is not None
        assert base.state is CalculationRevisionState.VERIFICADO_COMPLETO
        assert base.source_issues == ()
        with_issues = base.model_copy(update={"source_issues": issues})
        planted = with_issues.model_copy(
            update={"calculation_revision_id": derive_calculation_revision_id_from_revision(with_issues)}
        )
        calculations.save(upsert_calculation_revision(calculations.load(), planted))

        def advance(catalogue: WorkUnitCatalogue) -> WorkUnitCatalogue:
            unit = catalogue.get(work_unit_id)
            assert unit is not None
            return upsert_work_unit(
                catalogue, unit.model_copy(update={"current_calculation_revision_id": planted.calculation_revision_id})
            )

        work_units = WorkUnitCatalogueRepository()
        work_units.mutate(advance)
        unit = work_units.load().get(work_unit_id)
        assert unit is not None
        assert unit.current_calculation_revision_id == planted.calculation_revision_id
        stored = calculations.load().get(planted.calculation_revision_id)
        assert stored is not None
        assert tuple(stored.source_issues) == issues
    return planted.calculation_revision_id


def _export(work_unit_id: str, output: Path) -> tuple[int, str]:
    exported = invoke_cached_cli(
        ["--format", "json", "--language", "en", "app", "modelo", "export", work_unit_id, "--output", str(output)],
    )
    return exported.exit_code, exported.output


def _assert_blocked(exit_code: int, output: str, *, revision_id: str, action: str) -> None:
    assert exit_code != 0, output
    error = require_error_document(output)["error"]
    assert error["code"] == _BLOCKED_CODE, output
    assert error["context"]["reason"] == _REASON, output
    assert error["context"]["action"] == action, output
    assert error["context"]["calculation_revision_id"] == revision_id, output
    assert _english_sentence() in str(error["message"]), output


def test_a_blocking_note_refuses_export_and_filing_until_a_recalculation_clears_it(
    seed_profile: ProfileSeeder, tmp_path: Path
) -> None:
    seed_profile(label="operator", facts=operator_profile_facts(activity_start_date="2025-10-01"))
    work_unit_id, clean_revision_id = _calculate_and_verify()
    blocked_revision_id = _plant_current(work_unit_id, clean_revision_id, (_BLOCKING_ISSUE,))
    assert blocked_revision_id != clean_revision_id

    refused_output = tmp_path / "modelo-130-blocked.txt"
    exit_code, output = _export(work_unit_id, refused_output)
    _assert_blocked(exit_code, output, revision_id=blocked_revision_id, action="export")
    assert not refused_output.exists()

    filed = invoke_cached_cli(
        ["--format", "json", "--language", "en", "app", "modelo", "work", "file", blocked_revision_id],
    )
    _assert_blocked(filed.exit_code, filed.output, revision_id=blocked_revision_id, action="file")
    status = invoke_cached_cli(["--format", "json", "app", "modelo", "work", "status", work_unit_id])
    assert status.exit_code == 0, status.output
    assert _payload(status.output)["filed_calculation_revision_id"] is None

    cleared_revision_id = _recalculate(work_unit_id, _LATER_PRIOR_YEAR_INCOME)
    assert cleared_revision_id not in {blocked_revision_id, clean_revision_id}
    status = invoke_cached_cli(["--format", "json", "app", "modelo", "work", "status", work_unit_id])
    assert status.exit_code == 0, status.output
    assert _payload(status.output)["current_calculation_revision_id"] == cleared_revision_id

    cleared_output = tmp_path / "modelo-130-cleared.txt"
    exit_code, output = _export(work_unit_id, cleared_output)
    assert exit_code == 0, output
    assert _payload(output)["calculation_revision_id"] == cleared_revision_id
    assert cleared_output.stat().st_size > 0


def test_the_identical_calculation_without_the_note_exports(seed_profile: ProfileSeeder, tmp_path: Path) -> None:
    """Teeth for the refusal above: the same planted calculation minus only its note is exported."""
    seed_profile(label="operator", facts=operator_profile_facts(activity_start_date="2025-10-01"))
    work_unit_id, clean_revision_id = _calculate_and_verify()
    planted_revision_id = _plant_current(work_unit_id, clean_revision_id, ())
    assert planted_revision_id == clean_revision_id

    output_path = tmp_path / "modelo-130-control.txt"
    exit_code, output = _export(work_unit_id, output_path)

    assert exit_code == 0, output
    assert _payload(output)["calculation_revision_id"] == planted_revision_id
    assert output_path.stat().st_size > 0
    assert json.loads(output)["status"] != "error"
