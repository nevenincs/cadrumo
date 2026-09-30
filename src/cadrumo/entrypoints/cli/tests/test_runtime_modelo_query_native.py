"""Native profile-worker acceptance for the complete modelo query journey."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.modelo.registry_discovery import registry_casillas_for_registry_scope
from ....application.state_projection import CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS
from ....core.aggregation import BindingSourceKind
from ....core.config import override_settings
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import unwrap_cli_result
from ._runtime_profile_cli_fixture import NativeCliProfileFixture, RuntimeFailureObservation, native_cli_profile_scope
from .cli_runner import invoke_cached_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def _invoke(profile: NativeCliProfileFixture, *command: str, language: str = "en") -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    result = invoke_cached_cli(
        ("--language", language, "--format", "json", "--profile", profile.label, "--profile-secrets-stdin", *command),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


def test_native_modelo_binding_preview_inventory_and_readiness(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """All four parser routes retain grounding, override semantics and readiness axes."""
    with native_cli_profile_scope(tmp_path) as profile:
        failures: list[RuntimeFailureObservation] = []
        profile.failure_observer = failures.append
        profile.register(
            label="native-modelo-query",
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.name": "Native",
                "identity.surnames": "Query",
                "activities.description": "design",
                "censo.activity_start_date": "2025-01-01",
                "contact.postcode": "28013",
                "tax_residence.jurisdiction_scope": "common_regime",
                "iva.regime": "GENERAL",
                "iva.m303_regime_composition": "general",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            },
        )
        scope = ("--modelo", "303", "--year", "2025", "--period", "1T")
        listed = _invoke(profile, "app", "modelo", "bindings", "list", *scope)
        assert listed.exit_code == 0, listed.output
        listing = unwrap_cli_result(listed)
        rows = listing["bindings"]
        assert isinstance(rows, list) and rows
        with override_settings(cadrumo_output_language="en"):
            for row in rows:
                assert isinstance(row, dict)
                assert row["readiness"] == tr(
                    CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS[BindingSourceKind(row["source"])]
                )
        first = rows[0]
        assert isinstance(first, dict)
        binding_id = first["binding_id"]
        assert isinstance(binding_id, str)
        resolved = _invoke(
            profile,
            "app",
            "modelo",
            "bindings",
            "resolve",
            *scope,
            "--binding",
            f"{binding_id}=0.25",
            "--binding",
            f"{binding_id}=0.75",
        )
        assert resolved.exit_code == 0, resolved.output
        preview = unwrap_cli_result(resolved)
        assert preview["override_count"] == 1
        preview_rows = preview["bindings"]
        assert isinstance(preview_rows, list) and len(preview_rows) == len(rows)
        for source, target in zip(rows, preview_rows, strict=True):
            assert isinstance(source, dict) and isinstance(target, dict)
            for key in (
                "binding_id",
                "source",
                "readiness",
                "typed_enum",
                "legal_refs",
                "source_refs",
                "relation_inputs",
                "encoded_options",
            ):
                assert target[key] == source[key]
            assert target["override"] == ("0.75" if target["binding_id"] == binding_id else None)
        inventory_result = _invoke(profile, "app", "modelo", "requires", "303", "--year", "2025", "--period", "1T")
        assert inventory_result.exit_code == 0, inventory_result.output
        inventory = unwrap_cli_result(inventory_result)
        assert inventory["profile_checked"] is True
        for bucket in (
            "required_manual",
            "optional_manual",
            "detail_row_fields",
            "ledger_derivable",
            "profile_derivable",
            "previous_filing",
            "relation_prefill",
            "live_observation",
            "unbucketed_sources",
        ):
            entries = inventory[bucket]
            assert isinstance(entries, list)
            for entry in entries:
                assert isinstance(entry, dict)
                assert entry["legal_refs"] and entry["source_refs"]
        readiness_result = _invoke(profile, "app", "modelo", "readiness", *scope)
        assert readiness_result.exit_code in {0, 2}, readiness_result.output
        readiness = unwrap_cli_result(readiness_result)
        assert readiness_result.exit_code == (0 if readiness["ready"] else 2)
        assert readiness["revision_id"] == preview["revision"] == inventory["revision"]
        assert readiness["ledger_period"] is not None
        assert isinstance(readiness["missing_bindings"], list)
        assert isinstance(readiness["missing"], list)
        relisted = _invoke(profile, "app", "modelo", "bindings", "list", *scope)
        assert relisted.exit_code == 0, relisted.output
        assert unwrap_cli_result(relisted) == listing
        hungarian = _invoke(profile, "app", "modelo", "bindings", "list", *scope, language="hu")
        assert hungarian.exit_code == 0, (hungarian.output, failures)
        hungarian_rows = unwrap_cli_result(hungarian)["bindings"]
        assert isinstance(hungarian_rows, list) and len(hungarian_rows) == len(rows)
        with override_settings(cadrumo_output_language="hu"):
            for row in hungarian_rows:
                assert isinstance(row, dict)
                assert row["readiness"] == tr(
                    CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS[BindingSourceKind(row["source"])]
                )
        hungarian_inventory_result = _invoke(
            profile, "app", "modelo", "requires", "303", "--year", "2025", "--period", "1T", language="hu"
        )
        assert hungarian_inventory_result.exit_code == 0, hungarian_inventory_result.output
        hungarian_inventory = unwrap_cli_result(hungarian_inventory_result)
        with override_settings(cadrumo_output_language="hu"):
            canonical_casillas = registry_casillas_for_registry_scope(
                "303", filing_year=2025, period="1T", operation=operation
            )
        labels = {row.casilla_id: row.label for row in canonical_casillas.rows}
        for bucket in (
            "required_manual",
            "optional_manual",
            "detail_row_fields",
            "ledger_derivable",
            "profile_derivable",
            "previous_filing",
            "relation_prefill",
            "live_observation",
            "unbucketed_sources",
        ):
            entries = hungarian_inventory[bucket]
            assert isinstance(entries, list)
            for entry in entries:
                assert isinstance(entry, dict)
                assert entry["label"] == labels[entry["casilla_id"]]
