"""CLI tests for ``aeat app registry diff-revisions``.

Grounds every assertion against the two *real* Modelo 303 registry revisions
shipped in the bundled tree (``2009-y-siguientes`` covering 2009-2022,
``2023-y-siguientes`` covering 2023 onward); the expected identifiers were
read directly off the diff service against this known real revision pair, per
:mod:`cadrumo.application.registry.tests.test_diff`.
"""

from __future__ import annotations

import json

import pytest

from ....application.registry import RegistryRevisionDiffReport
from ._registry_cli_fixtures import (
    _isolated_registry_cli_backend,
    _isolated_secure_backend,
)
from ._registry_cli_support import _REGISTRY_ROOT, invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_REGISTRY_CLI_FIXTURES = (_isolated_registry_cli_backend, _isolated_secure_backend)

_M303_PRE_YEAR = 2022
_M303_POST_YEAR = 2023


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
    assert payload.from_revision_id == "2009-y-siguientes"
    assert payload.to_revision_id == "2023-y-siguientes"
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
    assert payload.from_revision_id == payload.to_revision_id == "2009-y-siguientes"
    assert payload.added_casillas == ()
    assert payload.changed_formulas == ()


def test_diff_revisions_cli_text_output_names_both_revision_ids() -> None:
    result = invoke_cached_cli(_diff_cli_args(from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR, output_format="text"))

    assert result.exit_code == 0, result.output
    assert "2009-y-siguientes" in result.output
    assert "2023-y-siguientes" in result.output
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
