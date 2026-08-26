"""``aeat app modelo support-matrix`` verb tests.

See Also:
    :func:`~entrypoints.cli._modelo_discovery_cli._register_support_matrix_command`
        Typer registration for the operator-facing command covered here.
    :func:`~entrypoints.cli._modelo_discovery_cli._support_matrix_entry_payload`
        Transport mapper from registry rows to CLI payload rows.
    :class:`~entrypoints.cli._modelo_support_matrix_payloads.ModeloSupportMatrixResult`
        Registered JSON result schema asserted by the envelope checks.
    :func:`~application.modelo.registry_discovery.registry_support_matrix`
        Application query called by the CLI command.
    :mod:`~domain.calculations.registry.tests.test_support_matrix`
        Domain support-matrix coverage for the same row semantics.
"""

from __future__ import annotations

import pytest

from ....tests.cli_envelope import unwrap_schema_envelope
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_support_matrix_returns_one_row_per_registry_modelo_sorted_by_id() -> None:
    payload = unwrap_schema_envelope(
        invoke_cached_cli(["--format", "json", "app", "modelo", "support-matrix"]).output,
    )

    entries = payload["entries"]
    assert payload["modelo_count"] == len(entries)
    assert entries, "expected at least one modelo entry"
    assert [entry["modelo_id"] for entry in entries] == sorted(entry["modelo_id"] for entry in entries)


def test_support_matrix_modelo_303_reports_calc_grade_and_fichero_boe_export() -> None:
    payload = unwrap_schema_envelope(
        invoke_cached_cli(["--format", "json", "app", "modelo", "support-matrix"]).output,
    )
    entries_by_id = {entry["modelo_id"]: entry for entry in payload["entries"]}

    m303 = entries_by_id["303"]
    assert m303["calc_grade"] is True
    assert m303["has_completeness_manifest"] is True
    assert m303["has_fixed_width_export"] is True


def test_support_matrix_modelo_100_carries_typed_renames_and_portal_refs() -> None:
    payload = unwrap_schema_envelope(
        invoke_cached_cli(["--format", "json", "app", "modelo", "support-matrix"]).output,
    )
    entries_by_id = {entry["modelo_id"]: entry for entry in payload["entries"]}

    m100 = entries_by_id["100"]
    assert m100["renames"], "expected modelo 100's latest revision to declare casilla renames"
    first_rename = m100["renames"][0]
    assert {"continuidad_id", "from_revision", "to_revision", "evolution_kind"} <= set(first_rename)
    assert m100["portal_compatibility_refs"], "expected modelo 100 to declare a live AEAT-portal cross-reference"
    first_ref = m100["portal_compatibility_refs"][0]
    assert {"id", "surface", "evidence_tier"} <= set(first_ref)


def test_support_matrix_text_output_lists_every_modelo() -> None:
    result = invoke_cached_cli(["app", "modelo", "support-matrix"])
    assert result.exit_code == 0, result.output
    assert "303" in result.output
    assert "100" in result.output
