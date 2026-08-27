"""CLI tests for ``aeat app registry diff-revisions``.

Grounds every assertion against the two *real* Modelo 303 revisions selected
by the bundled authority for the historical filing years; the expected
identifiers are read from those snapshots, per
:mod:`cadrumo.application.registry.tests.test_diff`.
"""

from __future__ import annotations

import json

import pytest

from ....application.registry import RegistryRevisionDiffReport
from ....domain.calculations.registry.authority import bundled_authority
from ._registry_cli_fixtures import (
    _isolated_registry_cli_backend,
    _isolated_secure_backend,
)
from ._registry_cli_support import _REGISTRY_ROOT, invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_REGISTRY_CLI_FIXTURES = (_isolated_registry_cli_backend, _isolated_secure_backend)

_M303_PRE_YEAR = 2022
_M303_POST_YEAR = 2023


def _m303_revision_for(filing_year: int) -> str:
    return str(bundled_authority().snapshot("303", filing_year=filing_year, period="1T").revision.id)


def _diff_cli_args(*, from_year: int, to_year: int, output_format: str = "json") -> list[str]:
    return [
        "--format",
        output_format,
        "app",
        "registry",
        "diff-revisions",
        "303",
        "--from-year",
        str(from_year),
        "--to-year",
        str(to_year),
        "--registry-root",
        str(_REGISTRY_ROOT),
    ]


def test_diff_revisions_cli_reports_json_envelope_for_real_revision_pair() -> None:
    result = invoke_cached_cli(_diff_cli_args(from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR))

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "registry.diff_revisions"
    payload = RegistryRevisionDiffReport.model_validate(envelope["result"])

    assert payload.same_revision is False
    assert payload.from_revision_id == _m303_revision_for(_M303_PRE_YEAR)
    assert payload.to_revision_id == _m303_revision_for(_M303_POST_YEAR)
    added_ids = {casilla.id for casilla in payload.added_casillas}
    assert "iva.autoconsumo.promotor.base" in added_ids
    changed_formula_ids = {formula.id for formula in payload.changed_formulas}
    assert "modelo-303-iva-resultado" in changed_formula_ids
    added_binding_ids = {binding.id for binding in payload.added_bindings}
    assert "modelo-303-autoconsumo-promotor-base" in added_binding_ids


def test_diff_revisions_cli_reports_same_revision_for_years_in_one_window() -> None:
    result = invoke_cached_cli(_diff_cli_args(from_year=2015, to_year=2020))

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    payload = RegistryRevisionDiffReport.model_validate(envelope["result"])

    assert payload.same_revision is True
    expected_revision = _m303_revision_for(2015)
    assert payload.from_revision_id == payload.to_revision_id == expected_revision
    assert payload.added_casillas == ()
    assert payload.changed_formulas == ()


def test_diff_revisions_cli_text_output_names_both_revision_ids() -> None:
    result = invoke_cached_cli(_diff_cli_args(from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR, output_format="text"))

    assert result.exit_code == 0, result.output
    assert _m303_revision_for(_M303_PRE_YEAR) in result.output
    assert _m303_revision_for(_M303_POST_YEAR) in result.output
    assert "added_casilla" in result.output


def test_diff_revisions_cli_refuses_a_year_no_revision_covers() -> None:
    result = invoke_cached_cli(_diff_cli_args(from_year=1999, to_year=_M303_POST_YEAR))

    assert result.exit_code != 0
    assert "1999" in result.output


def test_diff_revisions_cli_rejects_an_unregistered_modelo_argument() -> None:
    result = invoke_cached_cli(
        [
            "app",
            "registry",
            "diff-revisions",
            "999-nonexistent",
            "--from-year",
            "2020",
            "--to-year",
            "2023",
            "--registry-root",
            str(_REGISTRY_ROOT),
        ],
    )

    # The modelo argument is a closed-choice Click type; parse-time refusal
    # lists the accepted set rather than a bare "value invalid".
    assert result.exit_code != 0
    assert "999-nonexistent" in result.output
