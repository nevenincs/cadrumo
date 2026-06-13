"""Natural-key CLI workflow coverage for modelo work commands."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ._m130_source_support import seed_m130_income_transaction
from .envelope_helpers import unwrap_envelope_notices as _notices
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        try:
            yield
        finally:
            dispose_engine()


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _envelope_status(output: str) -> str:
    """Return the outer envelope ``status`` field from a CLI ``--json`` document."""
    import json

    return json.loads(output)["status"]


def _create_profile() -> None:
    result = _invoke(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--surnames", "Natural Key",
            "--activity", "design",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


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
    # A granted (clean) verify stays on the success spine with no notices, in
    # lock-step with its exit-0.
    assert _envelope_status(verified.output) == "success", verified.output
    assert _notices(verified.output) == [], verified.output

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

    calculated = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--casilla", "02=3000.00",
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
    assert (
        "aeat app live filed pull-sources --modelo 130 --year 2025 --period 1T" in payload["findings"][0]["next_action"]
    )
    assert "aeat app modelo reconcile file WORK_UNIT_ID --file PATH" in payload["findings"][0]["next_action"]

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
    # The finding's true severity and its next-step action survive onto the
    # notice; the blocking-vs-advisory distinction lives on the context.
    assert blocking["severity"] == "warning"
    assert blocking["context"]["severity"] == "blocking"
    assert blocking["context"]["kind"] == "cross_period_dependency_unclean"
    assert blocking["suggestion"] == payload["findings"][0]["next_action"]


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
