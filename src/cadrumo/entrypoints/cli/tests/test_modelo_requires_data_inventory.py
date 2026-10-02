"""Data-inventory checklist proof for ``aeat app modelo requires``.

``requires`` composes the registry snapshot for one
``(modelo, filing_year, period)`` into an operator-facing checklist: which
casillas must be hand-entered, which are optional, which the bucket ledger
populates automatically, and which come from the active taxpayer profile
(warning when a profile-derivable coefficient is still unset). This module
proves the classification against committed, non-trivial bindings in the REAL
bundled registry for Modelos 100, 130, and 390, plus the profile-coefficient
warning against a REAL partial taxpayer profile. Expected rows are anchored to
those registry declarations rather than produced by a second implementation
of the classifier under test.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import unwrap_envelope_notices, unwrap_schema_envelope
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_M130_MODELO = "130"
_M130_YEAR = 2024
_M130_PERIOD = "2T"

_M100_MODELO = "100"
_M100_YEAR = 2025
_M100_PERIOD = "0A"

_M390_MODELO = "390"
_M390_YEAR = 2025
_M390_PERIOD = "0A"


@pytest.fixture
def invoke_requires(tmp_path: Path) -> Iterator[Callable[[list[str]], Result]]:
    """Serve the real registered inventory reader for a partial taxpayer profile."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(
            label="native-requires",
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.tax_id": "12345678Z",
                "identity.name": "Operator",
                "identity.surnames": "Example",
                "activities.description": "design",
                "censo.activity_start_date": "2024-01-01",
                "contact.postcode": "28013",
                "tax_residence.jurisdiction_scope": "common_regime",
                "tax_residence.ccaa": "cataluna",
                "renta_filing.declaration_type": "1",
                "renta_taxpayer.birth_date": "1980-03-15",
                "renta_family.minor_children_in_unit": "false",
                "iva.regime": "GENERAL",
                "iva.m303_regime_composition": "general",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            },
        )

        def invoke(args: list[str]) -> Result:
            assert profile.label is not None
            close_active_bucket_session()
            return invoke_cached_cli(
                ("--language", "en", "--profile", profile.label, "--profile-secrets-stdin", *args),
                input=json.dumps({"profile_passphrase": profile.passphrase}),
            )

        yield invoke


def _numbers_by_section(result: dict[str, list[dict[str, str]]]) -> dict[str, set[str]]:
    return {
        section: {row["number"] for row in result[section]}
        for section in ("required_manual", "optional_manual", "ledger_derivable", "profile_derivable")
    }


def test_requires_classifies_real_m130_sources_with_bound_profile(
    invoke_requires: Callable[[list[str]], Result],
) -> None:
    """``requires`` exposes committed manual, ledger, and prior-filing rows.

    The registered read uses the exact selected profile while retaining the
    registry's required, optional, ledger, and prior-filing classification.
    """
    invocation = invoke_requires(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "requires",
            _M130_MODELO,
            "--year",
            str(_M130_YEAR),
            "--period",
            _M130_PERIOD,
        ],
    )
    assert invocation.exit_code == 0, invocation.output
    result = unwrap_schema_envelope(invocation.output)

    assert result["modelo"] == _M130_MODELO
    assert result["filing_year"] == _M130_YEAR
    assert result["period"] == _M130_PERIOD
    sections = _numbers_by_section(result)
    assert {"01", "02"} <= sections["ledger_derivable"]
    assert result["optional_manual"]

    # Ledger-derivable rows carry their binding provenance for the checklist.
    ledger_rows = {row["number"]: row["binding_source"] for row in result["ledger_derivable"]}
    assert ledger_rows["01"] == "ledger_renta_income_aggregation"
    assert ledger_rows["02"] == "ledger_renta_gastos_pago_fraccionado_aggregation"
    assert {(row["number"], row["binding_source"]) for row in result["previous_filing"]} >= {
        ("05", "previous_filing"),
    }

    assert result["profile_checked"] is True


def test_requires_reads_relation_prefill_alternates_and_advises_on_unbucketed_sources(
    invoke_requires: Callable[[list[str]], Result],
) -> None:
    """Real M100 alternates remain visible instead of collapsing to the primary."""
    invocation = invoke_requires(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "requires",
            _M100_MODELO,
            "--year",
            str(_M100_YEAR),
            "--period",
            _M100_PERIOD,
        ],
    )
    assert invocation.exit_code == 0, invocation.output
    result = unwrap_schema_envelope(invocation.output)
    relation_pairs = {(row["binding_id"], row["binding_source"]) for row in result["relation_prefill"]}
    assert {
        ("renta-modelo-130-pagos-fraccionados", "relation_prefill"),
        ("renta-modelo-131-pagos-fraccionados", "relation_prefill"),
    } <= relation_pairs
    unbucketed_pairs = {(row["binding_id"], row["binding_source"]) for row in result["unbucketed_sources"]}
    assert ("renta-certificado-trabajo-retenciones", "manual_input") in unbucketed_pairs

    notices = unwrap_envelope_notices(invocation.output)
    advisory = next(notice for notice in notices if notice["code"] == "modelo.requires.unbucketed_binding_source")
    assert advisory["severity"] == "warning"
    assert advisory["action"] is None
    assert "manual_input" in advisory["context"]["source_kinds"]
    assert "renta-certificado-trabajo-retenciones" in advisory["context"]["binding_ids"]


def test_requires_buckets_local_register_resolvers_as_live_observations(
    invoke_requires: Callable[[list[str]], Result],
) -> None:
    """M390 exposes its committed local-state resolver bindings without claiming a remote read."""
    invocation = invoke_requires(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "requires",
            _M390_MODELO,
            "--year",
            str(_M390_YEAR),
            "--period",
            _M390_PERIOD,
        ],
    )
    assert invocation.exit_code == 0, invocation.output
    result = unwrap_schema_envelope(invocation.output)

    live_pairs = {(row["number"], row["binding_source"]) for row in result["live_observation"]}
    assert {
        ("63", "bienes_inversion_regularizacion"),
        ("97", "iva_compensation_annual_partition"),
        ("662", "iva_compensation_annual_partition"),
    } <= live_pairs


def test_requires_warns_about_unresolved_profile_coefficients(
    invoke_requires: Callable[[list[str]], Result], operation: PinnedAuthorityOperation
) -> None:
    """With an active but incomplete profile, unresolved coefficients surface as a warning.

    Modelo 100 declares dozens of ``source = "profile"`` bindings (marital
    status, spouse identity, descendant/ascendant rows, ...). The seeded
    profile resolves only a proper subset (tax residence, declaration type,
    birth date, minor children count); every other profile-derivable binding
    must be reported as unresolved so the operator knows exactly which
    coefficient is still owed -- never a silent gap.
    """
    resolved = {
        "renta-profile-tax-residence-ccaa",
        "renta-profile-declaration-type",
        "renta-profile-taxpayer-birth-date",
    }
    invocation = invoke_requires(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "requires",
            _M100_MODELO,
            "--year",
            str(_M100_YEAR),
            "--period",
            _M100_PERIOD,
        ],
    )
    assert invocation.exit_code == 0, invocation.output
    result = unwrap_schema_envelope(invocation.output)

    assert result["profile_checked"] is True
    assert result["authority_generation"] == operation.generation.logical_generation
    profile_binding_ids = {row["binding_id"] for row in result["profile_derivable"]}
    assert profile_binding_ids, "fixture expectation must be non-trivial"
    # The seeded resolved bindings must actually be declared bindings for
    # this revision (otherwise the fixture proves nothing).
    assert resolved <= profile_binding_ids

    unresolved = set(result["unresolved_profile_bindings"])
    assert unresolved, "a proper subset must leave real gaps"
    # The bindings the profile explicitly resolved must not be reported as
    # unresolved.
    assert unresolved.isdisjoint(resolved)
    # Every unresolved id must be a genuinely declared profile binding for
    # this revision (never an invented id).
    assert unresolved <= profile_binding_ids

    notices = unwrap_envelope_notices(invocation.output)
    warning = next(notice for notice in notices if notice["code"] == "modelo.requires.missing_profile_coefficient")
    assert warning["severity"] == "warning"
    assert warning["action"] is None
    # The runtime owns profile facts; the cold CLI still owes their grounded labels.
    assert "renta-profile-marital-status" in unresolved
    assert "renta_taxpayer.marital_status" in result["unresolved_profile_keys"]
    assert "Marital status" in warning["message"]
    assert "orden-hac-277-2026:art-3" in warning["message"]
    for binding_id in unresolved:
        assert binding_id in warning["context"]["missing_bindings"]

    assert unwrap_schema_envelope('{"schema_version": "2", "command": "x", "status": "warning", "result": {}}') == {}
