"""CLI tests for read-only registry verification commands."""

from __future__ import annotations

import json

import click
import pytest

from ....application.registry.tree import RegistryTreeReport
from ....core.resources._boundary import bundled_path
from ....tests.cli_runner import cadrumo_click_command
from ._registry_cli_fixtures import (
    _isolated_registry_cli_backend,
    _isolated_secure_backend,
)
from ._registry_cli_support import (
    _REGISTRY_ROOT,
    _registry_application_surfaces,
    _registry_modelos,
    invoke_cached_cli,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_REGISTRY_CLI_FIXTURES = (_isolated_registry_cli_backend, _isolated_secure_backend)


@pytest.fixture(scope="module")
def _registry_inspect_payload() -> RegistryTreeReport:
    """Run ``app registry inspect --format json`` once per module.

    Reused across every test_registry_inspect_* assertion so the CLI
    invocation (registry load + walk + payload synthesis) is paid
    once instead of per-assertion. Module scope is the correct
    bound: nothing in this file mutates the registry under
    ``_REGISTRY_ROOT``. Validating the emitted JSON back into
    ``RegistryTreeReport`` also asserts the CLI payload roundtrips
    against its declared schema.
    """
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "registry",
            "inspect",
            "--registry-root",
            str(_REGISTRY_ROOT),
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "registry.inspect"
    return RegistryTreeReport.model_validate(envelope["result"])


def test_registry_inspect_cli_reports_unverified_state(_registry_inspect_payload: RegistryTreeReport) -> None:
    assert _registry_inspect_payload.verified is False


def test_registry_inspect_cli_lists_every_registry_modelo(_registry_inspect_payload: RegistryTreeReport) -> None:
    registry_modelos = _registry_modelos()
    assert _registry_inspect_payload.modelos == registry_modelos
    assert _registry_inspect_payload.modelo_count == len(registry_modelos)


_INSPECT_PAYLOAD_NON_ZERO_COUNT_KEYS = (
    "casilla_count",
    "formula_count",
    "extraction_profile_count",
    "cross_reference_count",
    "workbook_parity_ref_count",
    "verification_expectation_count",
    "application_link_count",
    "relation_count",
    "filing_schedule_count",
)


@pytest.mark.parametrize("count_key", _INSPECT_PAYLOAD_NON_ZERO_COUNT_KEYS)
def test_registry_inspect_cli_reports_non_zero_count(
    _registry_inspect_payload: RegistryTreeReport,
    count_key: str,
) -> None:
    count = getattr(_registry_inspect_payload, count_key)
    assert count > 0, f"{count_key}={count!r}"


def test_registry_inspect_cli_reports_at_least_one_revision(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    assert _registry_inspect_payload.revision_count >= 1


def test_registry_inspect_cli_advertises_expected_relation_role(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    assert "periodic_to_annual_summary" in _registry_inspect_payload.relation_dependency_roles


def test_registry_inspect_cli_matches_registry_application_surfaces(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    assert set(_registry_inspect_payload.application_link_surfaces) == _registry_application_surfaces()


def test_registry_inspect_cli_revision_details_match_revision_count(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    assert len(_registry_inspect_payload.revision_details) == _registry_inspect_payload.revision_count


def test_registry_inspect_cli_first_revision_resolves_against_modelo_list(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    revision = _registry_inspect_payload.revision_details[0]
    assert revision.modelo in _registry_inspect_payload.modelos
    assert revision.revision


def test_registry_inspect_cli_first_revision_carries_legal_and_source_refs(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    revision = _registry_inspect_payload.revision_details[0]
    assert revision.legal_refs
    assert revision.source_refs


_REVISION_COUNT_PAIRS = (
    ("export_layout_count", "export_layout_ids"),
    ("deadline_window_count", "deadline_periods"),
    ("relation_count", "relation_ids"),
    ("filing_schedule_count", "filing_schedule_ids"),
)


@pytest.mark.parametrize(("count_key", "ids_key"), _REVISION_COUNT_PAIRS)
def test_registry_inspect_cli_first_revision_count_matches_id_list(
    _registry_inspect_payload: RegistryTreeReport,
    count_key: str,
    ids_key: str,
) -> None:
    revision = _registry_inspect_payload.revision_details[0]
    assert getattr(revision, count_key) == len(getattr(revision, ids_key))


def test_registry_inspect_cli_first_revision_has_workbook_parity(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    assert _registry_inspect_payload.revision_details[0].workbook_parity


def test_registry_inspect_cli_export_revision_has_record_and_field_counts(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    export_revision = next(
        detail for detail in _registry_inspect_payload.revision_details if detail.export_field_count > 0
    )
    assert export_revision.export_record_count > 0


def test_registry_inspect_cli_guarded_revision_lists_portal_guard_policies(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    guarded_revision = next(
        detail for detail in _registry_inspect_payload.revision_details if detail.portal_guard_policy_ids
    )
    assert guarded_revision.portal_guard_policy_ids


def test_registry_inspect_cli_workbook_reference_resolves_against_revision(
    _registry_inspect_payload: RegistryTreeReport,
) -> None:
    revision = _registry_inspect_payload.revision_details[0]
    workbook_reference = revision.workbook_parity[0]
    assert workbook_reference.id
    assert workbook_reference.workbook_source in revision.source_refs
    assert workbook_reference.formula_coverage
    assert workbook_reference.runner_required is False or workbook_reference.output_cell_count > 0


def test_registry_verify_cli_validates_sources_and_catalogues() -> None:
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "registry",
            "verify",
            "--registry-root",
            str(_REGISTRY_ROOT),
            "--source-root",
            str(bundled_path()),
        ],
    )

    assert result.exit_code == 0, f"CLI command failed:\n{result.output}"
    envelope = json.loads(result.output)
    assert envelope["command"] == "registry.verify"
    payload = envelope["result"]
    registry_surfaces = _registry_application_surfaces()
    assert payload["verified"] is True
    assert payload["verified_invariant_families"] == [
        "catalogue_and_corpus_integrity",
        "revision_section_contracts",
        "relation_source_coordinate_coverage",
    ]
    assert payload["unverified_invariant_families"] == [
        "export_layout_population",
        "published_design_span_attribution",
    ]
    assert payload["source_reference_count"] > 0
    assert set(payload["application_link_surfaces"]) == registry_surfaces
    assert payload["relation_count"] > 0
    assert "periodic_to_annual_summary" in payload["relation_dependency_roles"]
    assert payload["filing_schedule_count"] > 0
    assert any(detail["export_field_count"] > 0 for detail in payload["revision_details"])
    modelo_180 = next(detail for detail in payload["revision_details"] if detail["modelo"] == "180")
    assert modelo_180["relation_count"] > 0
    assert modelo_180["relation_dependency_roles"] == ["periodic_to_annual_summary"]


def test_registry_verify_cli_fails_fast_on_missing_corpus_source(tmp_path) -> None:
    result = invoke_cached_cli(
        [
            "app",
            "registry",
            "verify",
            "--registry-root",
            str(_REGISTRY_ROOT),
            "--source-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "missing corpus file" in result.output


def test_registry_retained_commands_reject_command_local_json_flag() -> None:
    result = invoke_cached_cli(
        [
            "app",
            "registry",
            "inspect",
            "--registry-root",
            str(_REGISTRY_ROOT),
            "--json",
        ],
    )

    assert result.exit_code != 0
    assert "No such option" in result.output


def test_rejected_json_flag_does_not_switch_a_text_invocation_to_json() -> None:
    """The rejected ``--json`` token is not read back as an output-mode request.

    ``--json`` is retired as a command-local flag, so the token can only ever
    reach the terminal boundary as an unknown option. It must not make a
    text-mode operator receive an error document, and an explicit
    ``--format json`` elsewhere in argv must still be honoured.
    """
    base = ["app", "registry", "inspect", "--registry-root", str(_REGISTRY_ROOT), "--json"]

    text_mode = invoke_cached_cli(base)
    assert text_mode.exit_code != 0
    assert not text_mode.output.lstrip().startswith("{")

    json_mode = invoke_cached_cli(["--format", "json", *base])
    assert json_mode.exit_code != 0
    payload = json.loads(json_mode.output)
    assert payload["status"] == "error"
    assert payload["error"]["context"]["option"] == "--json"


def test_root_output_format_is_typed_and_refuses_invalid_values_before_dispatch() -> None:
    command = cadrumo_click_command()
    # ``get_help`` RETURNS the rendered help; the CLI disables Rich rendering
    # globally, so nothing is written to stdout for a capture to read.
    parser_help = command.get_help(click.Context(command))
    assert "<text|json>" in parser_help
    assert "Formato de salida: text, json." in parser_help

    result = invoke_cached_cli(
        [
            "--format",
            "xml",
            "app",
            "registry",
            "inspect",
            "--registry-root",
            str(_REGISTRY_ROOT),
        ],
    )

    assert result.exit_code == 2
    assert "Invalid value" in result.output
    assert "'text'" in result.output and "'json'" in result.output
    assert "Refused." not in result.output
