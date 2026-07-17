"""Modelo list ``--domain`` tax-family filter tests."""

from __future__ import annotations

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from .envelope_helpers import unwrap_schema_envelope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_domain_filter_narrows_listing_to_chosen_family() -> None:
    json_result = invoke_cached_cli(["--format", "json", "app", "modelo", "list", "--domain", "iva"])
    assert json_result.exit_code == 0, json_result.output
    payload = unwrap_schema_envelope(json_result.output)

    assert payload["domain_filter"] == "iva"
    rows = payload["modelos"]
    assert isinstance(rows, list)
    assert rows, "expected at least one IVA modelo in the catalogue"
    assert all(row["tax_domain"] == "iva" for row in rows), payload
    codes = {row["code"] for row in rows}
    assert "303" in codes  # M303 is the canonical IVA self-assessment
    assert "100" not in codes  # M100 is IRPF, must be excluded by the IVA filter


def test_domain_filter_is_a_strict_subset_of_the_unfiltered_listing() -> None:
    full = unwrap_schema_envelope(
        invoke_cached_cli(["--format", "json", "app", "modelo", "list"]).output,
    )
    irpf = unwrap_schema_envelope(
        invoke_cached_cli(["--format", "json", "app", "modelo", "list", "--domain", "irpf"]).output,
    )

    full_codes = {row["code"] for row in full["modelos"]}
    irpf_codes = {row["code"] for row in irpf["modelos"]}

    assert irpf_codes, "expected at least one IRPF modelo"
    assert irpf_codes < full_codes, (irpf_codes, full_codes)
    assert len(irpf["modelos"]) < len(full["modelos"])
    assert all(row["tax_domain"] == "irpf" for row in irpf["modelos"])


def test_invalid_domain_is_refused_with_the_accepted_set() -> None:
    result = invoke_cached_cli(["app", "modelo", "list", "--domain", "not-a-family"])
    assert result.exit_code != 0
    # Typer renders the closed TaxDomain enum as a click Choice, so the
    # accepted-value set is surfaced on the parse failure.
    assert "iva" in result.output
    assert "irpf" in result.output


def test_domain_composes_with_year_filter() -> None:
    payload = unwrap_schema_envelope(
        invoke_cached_cli(
            ["--format", "json", "app", "modelo", "list", "--domain", "iva", "--year", "2025"],
        ).output,
    )
    assert payload["domain_filter"] == "iva"
    assert payload["year_filter"] == 2025
    assert all(row["tax_domain"] == "iva" for row in payload["modelos"]), payload
