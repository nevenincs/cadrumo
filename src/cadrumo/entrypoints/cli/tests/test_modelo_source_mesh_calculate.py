"""CLI roundtrip coverage for source mesh-backed modelo calculation."""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.inventory import InventoryLedgerRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend,
)
from cadrumo.core.type_adapters import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.authored_editions import revision_selected_for
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.contribuyente.inventory.records import InventoryLedgerDocument
from cadrumo.domain.invoices.catalogue import InvoiceCatalogue
from cadrumo.domain.transactions.models import TransactionCatalogue
from cadrumo.tests.cli_envelope import unwrap_envelope_notices, unwrap_schema_envelope

from .cli_fixture_worlds import RegisteredCliProfile
from .ordinary_m303_scenarios import joint_return_options
from .source_mesh_calculate_transactions import (
    classified_rent_transaction,
    m100_activity_expense_transaction,
    m100_activity_income_transaction,
    zero_stock_inventory_ledger,
)

__all__ = ["isolated_cli_backend"]

# Seeded rows and stored records decode against registry facts, so the test
# body holds the same authority lease a CLI invocation holds. Every command runs
# through the registered profile's native worker, as an operator's CLI does.
from .source_mesh_calculate_support import (
    ACTIVITY_YEAR,
    M100_FACTS,
    PROFILE_LABEL,
    capture_m115_invoice_withholding,
    cli,
    create_111_work_unit,
    create_115_work_unit,
    create_180_work_unit,
    create_303_work_unit,
    m100_exercise,
    opened_profile,
    operator_profile,
    seed_prior_m100_zero_carry,
    seed_zero_iva_wallet_decision,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.usefixtures("authority_operation"),
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


def test_work_calculate_modelo_115_uses_retenciones_aggregation_observation(tmp_path: Path) -> None:
    """M115 CLI calculation consumes persisted URBAN_RENTAL retención evidence."""

    with operator_profile(tmp_path) as profile:
        work_unit = create_115_work_unit(profile, year=ACTIVITY_YEAR)
        capture_m115_invoice_withholding(profile)

        calculated = cli(
            profile,
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            "--casilla",
            "04=0",
        )
    assert calculated.exit_code == 0, calculated.output
    casilla_values = unwrap_schema_envelope(calculated.output)["casilla_values"]
    assert Decimal(casilla_values["01"]) == Decimal("1")
    assert Decimal(casilla_values["02"]) == Decimal("2700.00")
    assert Decimal(casilla_values["03"]) == Decimal("513.00")
    assert Decimal(casilla_values["05"]) == Decimal("513.00")


def test_reusing_a_verified_calculation_keeps_the_newer_draft_current(tmp_path: Path) -> None:
    """A real historical duplicate is readable without replacing the current draft."""
    with operator_profile(tmp_path) as profile:
        work_unit = create_115_work_unit(profile, year=ACTIVITY_YEAR)
        capture_m115_invoice_withholding(profile)
        calculate = (
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
        )
        original = cli(profile, *calculate, "--casilla", "04=0")
        assert original.exit_code == 0, original.output
        original_id = str(unwrap_schema_envelope(original.output)["calculation_revision_id"])
        verified = cli(profile, "--format", "json", "app", "modelo", "work", "verify", original_id)
        assert verified.exit_code == 0, verified.output
        assert unwrap_schema_envelope(verified.output)["granted_verificado_completo"] is True

        changed = cli(profile, *calculate, "--casilla", "04=1")
        assert changed.exit_code == 0, changed.output
        changed_id = str(unwrap_schema_envelope(changed.output)["calculation_revision_id"])
        assert changed_id != original_id

        repeated = cli(profile, *calculate, "--casilla", "04=0")
        assert repeated.exit_code == 0, repeated.output
        result = unwrap_schema_envelope(repeated.output)
        assert result["calculation_revision_id"] == original_id
        assert result["state"] == "verificado_completo"
        notice = next(
            item
            for item in unwrap_envelope_notices(repeated.output)
            if item["code"] == "modelo.work.calculate.reused_sealed_revision"
        )
        assert notice["context"] == {
            "calculation_revision_id": original_id,
            "current_calculation_revision_id": changed_id,
            "revision_published": "false",
        }
        assert "No new draft was created" in notice["message"]
        assert result["saved_confirmation"] == notice["message"]
        status = cli(profile, "--format", "json", "app", "modelo", "work", "status", str(work_unit["work_unit_id"]))
        assert status.exit_code == 0, status.output
        assert unwrap_schema_envelope(status.output)["current_calculation_revision_id"] == changed_id


def test_work_calculate_modelo_100_routes_autonoma_auto_ledger_expenses(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """An operator's public CLI M100 path carries ledger income through 0171/0180/0224."""
    exercise = m100_exercise()
    expense_rows = (
        m100_activity_expense_transaction(
            "m100-expense-office",
            value_date=date(exercise, 2, 20),
            category=SpendingCategory.from_registry("material_oficina"),
            taxable_base=Decimal("500.00"),
        ),
        m100_activity_expense_transaction(
            "m100-expense-software",
            value_date=date(exercise, 5, 22),
            category=SpendingCategory.from_registry("software_suscripcion"),
            taxable_base=Decimal("700.00"),
        ),
        m100_activity_expense_transaction(
            "m100-expense-phone",
            value_date=date(exercise, 8, 12),
            category=SpendingCategory.from_registry("telefonia_movil"),
            taxable_base=Decimal("300.00"),
        ),
        m100_activity_expense_transaction(
            "m100-expense-advisory",
            value_date=date(exercise, 11, 8),
            category=SpendingCategory.from_registry("asesoria_fiscal"),
            taxable_base=Decimal("900.00"),
        ),
    )
    with operator_profile(tmp_path, M100_FACTS) as profile:
        work_unit = cli(
            profile,
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "100",
            "--year",
            str(exercise),
            "--period",
            "0A",
            "--revision",
            revision_selected_for("100", exercise, "0A").id,
        )
        assert work_unit.exit_code == 0, work_unit.output
        work_unit_payload = unwrap_schema_envelope(work_unit.output)
        with opened_profile(profile, authority_operation) as bucket_id:
            seed_prior_m100_zero_carry(exercise)
            TransactionCatalogueRepository(bucket_id=bucket_id).save(
                TransactionCatalogue.from_transactions((m100_activity_income_transaction(), *expense_rows)),
            )
            InvoiceCatalogueRepository(bucket_id=bucket_id).save(InvoiceCatalogue())
            InventoryLedgerRepository().save(
                InventoryLedgerDocument(ledgers=(zero_stock_inventory_ledger("actividad", year=exercise),))
            )

        # The profile is in estimacion directa normal without Codigo de Comercio
        # accounting, so RIRPF art. 7.2 imputes activity income on cobros y pagos.
        imputation = cli(
            profile,
            "config",
            "profile",
            "edit",
            PROFILE_LABEL,
            "--quiet",
            "--irpf-activity-income-imputation-criterion",
            "cobros_y_pagos",
            "--irpf-activity-income-imputation-year",
            str(exercise),
            "--no-irpf-codigo-comercio-accounting",
        )
        assert imputation.exit_code == 0, imputation.output

        calculated = cli(
            profile,
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit_payload["work_unit_id"]),
        )
    assert calculated.exit_code == 0, calculated.output
    casilla_values = unwrap_schema_envelope(calculated.output)["casilla_values"]

    assert Decimal(casilla_values["0171"]) == Decimal("12000.00")
    assert Decimal(casilla_values["0180"]) == Decimal("12000.00")
    assert Decimal(casilla_values["0218"]) == Decimal("2400.00")
    assert Decimal(casilla_values["0220"]) == Decimal("2400.00")
    assert Decimal(casilla_values["0224"]) == Decimal("9600.00")


def test_work_calculate_modelo_111_no_retenciones_quarter_names_profile_attestation_path(tmp_path: Path) -> None:
    """A no-observation M111 quarter is not filed blank; the CLI names the attestation path."""

    # Modelo 111 readiness demands an explicit colegio-concertado attestation
    # (preflight.py:280), and the export producer refuses without it
    # (_producer_snapshot.py:1548). Declare it so the run reaches the
    # no-retenciones attestation path this test is about.
    with operator_profile(tmp_path, {"withholding.colegio_concertado": "false"}) as profile:
        create_111_work_unit(profile)

        calculated = cli(
            profile,
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            "--modelo",
            "111",
            "--year",
            str(ACTIVITY_YEAR),
            "--period",
            "2T",
            "--by",
            "Javier",
        )
        attested = cli(
            profile,
            "config",
            "profile",
            "edit",
            PROFILE_LABEL,
            "--quiet",
            "--modelo-111-no-retenciones-periods",
            f"{ACTIVITY_YEAR}:2T,{ACTIVITY_YEAR}:3T,{ACTIVITY_YEAR}:4T",
        )
        shown = cli(profile, "config", "profile", "view", PROFILE_LABEL)

    assert calculated.exit_code != 0, calculated.output
    error = json.loads(calculated.output)["error"]
    _assert_empty_retenciones_window_refusal(error, modelo="111", period="2T")
    # The words offer the profile answer rather than naming a command.
    assert "--" not in error["message"]

    assert attested.exit_code == 0, attested.output
    assert shown.exit_code == 0, shown.output
    assert (
        f"withholding.modelo_111_no_retenciones_periods\t{ACTIVITY_YEAR}:2T,{ACTIVITY_YEAR}:3T,{ACTIVITY_YEAR}:4T"
        in shown.output
    )


def test_work_calculate_modelo_115_explicit_no_relevant_payment_attestation_materialises_zero(
    tmp_path: Path,
) -> None:
    """Public Q3/Q4 profile evidence materialises local M115 zero history."""
    with operator_profile(tmp_path) as profile:
        q3_work_unit = create_115_work_unit(profile, year=ACTIVITY_YEAR, period="3T")
        q4_work_unit = create_115_work_unit(profile, year=ACTIVITY_YEAR, period="4T")

        refused = cli(
            profile,
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(q3_work_unit["work_unit_id"]),
        )
        assert refused.exit_code != 0, refused.output
        _assert_empty_retenciones_window_refusal(json.loads(refused.output)["error"], modelo="115", period="3T")

        attested = cli(
            profile,
            "config",
            "profile",
            "edit",
            PROFILE_LABEL,
            "--quiet",
            "--modelo-115-no-relevant-payment-periods",
            f"{ACTIVITY_YEAR}:3T,{ACTIVITY_YEAR}:4T",
        )
        assert attested.exit_code == 0, attested.output
        shown = cli(profile, "config", "profile", "view", PROFILE_LABEL)
        assert shown.exit_code == 0, shown.output
        assert (
            f"withholding.modelo_115_no_relevant_payment_periods\t{ACTIVITY_YEAR}:3T,{ACTIVITY_YEAR}:4T" in shown.output
        )

        for period, work_unit in (("3T", q3_work_unit), ("4T", q4_work_unit)):
            calculated = cli(
                profile,
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "calculate",
                str(work_unit["work_unit_id"]),
            )
            assert calculated.exit_code == 0, calculated.output
            payload = unwrap_schema_envelope(calculated.output)
            assert Decimal(payload["casilla_values"]["01"]) == Decimal("0")
            assert Decimal(payload["casilla_values"]["02"]) == Decimal("0")
            assert Decimal(payload["casilla_values"]["03"]) == Decimal("0")
            assert Decimal(payload["casilla_values"]["05"]) == Decimal("0")
            assert any(
                "explicit no-relevant-payment attestation" in notice.get("context", {}).get("detail", "")
                for notice in unwrap_envelope_notices(calculated.output)
                if notice["code"] == "modelo.work.calculate.source_advisory"
            )
            calculation_revision_id = payload["calculation_revision_id"]
            assert isinstance(calculation_revision_id, str)
            verified = cli(profile, "--format", "json", "app", "modelo", "work", "verify", calculation_revision_id)
            assert verified.exit_code == 0, verified.output
            output = tmp_path / f"modelo-115-{ACTIVITY_YEAR}-{period}.boe"
            exported = cli(
                profile,
                "--format",
                "json",
                "app",
                "modelo",
                "export",
                "--revision",
                calculation_revision_id,
                "--output",
                str(output),
            )
            assert exported.exit_code == 0, exported.output
            export_payload = unwrap_schema_envelope(exported.output)
            assert export_payload["calculation_revision_id"] == calculation_revision_id
            assert export_payload["modelo"] == "115"
            assert output.exists()
            assert output.stat().st_size > 0


def test_work_calculate_modelo_115_classified_rent_row_requires_perceptor_evidence(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """A classified rent ledger row alone must hard-stop instead of producing zeros."""
    rent = classified_rent_transaction()
    with operator_profile(tmp_path) as profile:
        work_unit = create_115_work_unit(profile, year=rent.raw.booked_date.year)
        with opened_profile(profile, authority_operation) as bucket_id:
            TransactionCatalogueRepository(bucket_id=bucket_id).save(
                TransactionCatalogue.from_transactions((rent,)),
            )

        calculated = cli(
            profile,
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            "--casilla",
            "04=0",
        )

    assert calculated.exit_code != 0, calculated.output
    # A ledger rent row is not a retención: without the perceptor's evidence the
    # window holds none, so it is refused rather than calculated as zero.
    _assert_empty_retenciones_window_refusal(json.loads(calculated.output)["error"], modelo="115", period="1T")


def test_work_calculate_refuses_invalid_supplied_input_before_an_empty_retenciones_window(tmp_path: Path) -> None:
    """A malformed supplied value is reported as such, not hidden behind the empty-window refusal."""
    with operator_profile(tmp_path) as profile:
        work_unit = create_115_work_unit(profile, year=ACTIVITY_YEAR)
        calculated = cli(
            profile,
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            "--casilla",
            "99=1",
        )

    assert calculated.exit_code != 0, calculated.output
    error = json.loads(calculated.output)["error"]
    assert error["code"] == "REFUSED_MODELO_CALCULATE_CASILLA_INPUT", error
    assert error["context"]["effect"] == "none"


def _assert_empty_retenciones_window_refusal(error: dict[str, object], *, modelo: str, period: str) -> None:
    """Assert the typed refusal of a withholding period that holds no retención."""
    assert error["code"] == "REFUSED_RETENCIONES_WINDOW_EMPTY", error
    assert error["category"] == "REFUSED"
    context = STR_KEYED_MAPPING_ADAPTER.validate_python(error["context"])
    assert context["modelo"] == modelo
    assert context["effect"] == "none"
    action = STR_KEYED_MAPPING_ADAPTER.validate_python(error["action"])
    assert action["failed_condition_id"] == "aggregation.retenciones.observations.present"
    assert action["no_recovery_outcome"] == "operator_decision"
    assert action["action"] is None
    (evidence,) = OBJECT_TUPLE_ADAPTER.validate_python(action["evidence"])
    values = STR_KEYED_MAPPING_ADAPTER.validate_python(STR_KEYED_MAPPING_ADAPTER.validate_python(evidence)["values"])
    assert values["modelo"] == modelo
    assert values["period"] == period
    assert values["source_kind"] == "retenciones_aggregation"
    assert modelo in str(error["message"])


def test_work_calculate_modelo_180_refuses_a_perceptor_row_field_before_parsing_its_value(tmp_path: Path) -> None:
    """A casilla the perceptor record fills once per row is refused for being a row field.

    The value is a NIF, not a decimal, so the refusal must come from the
    row-field rule rather than the decimal parser, and it names the casilla and
    the record whose detail rows carry it.
    """

    with operator_profile(tmp_path) as profile:
        work_unit = create_180_work_unit(profile)

        calculated = cli(
            profile,
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            "--casilla",
            "perc.nif=B12345678",
        )

    assert calculated.exit_code != 0, calculated.output
    envelope = json.loads(calculated.output)
    assert envelope["error"]["code"] == "REFUSED_MODELO_CALCULATE_CASILLA_INPUT"
    assert envelope["error"]["context"]["casilla_ids"] == "perc.nif"
    assert envelope["error"]["context"]["record_ids"]
    # Which detail rows to supply is the operator's call, so the refusal is a
    # typed operator decision rather than prose naming a command.
    action = envelope["error"]["action"]
    assert action["failed_condition_id"] == "modelo.work.calculate.caller_overrides.casilla_scalar"
    assert action["no_recovery_outcome"] == "operator_decision"
    assert action["action"] is None
    assert "aeat" not in envelope["error"]["message"]


_M303_ONLY_SHA256 = "a" * 64


def _m100_work_unit(profile: RegisteredCliProfile) -> str:
    exercise = m100_exercise()
    result = cli(
        profile,
        "--format",
        "json",
        "app",
        "modelo",
        "work",
        "create",
        "--modelo",
        "100",
        "--year",
        str(exercise),
        "--period",
        "0A",
        "--revision",
        revision_selected_for("100", exercise, "0A").id,
    )
    assert result.exit_code == 0, result.output
    return str(unwrap_schema_envelope(result.output)["work_unit_id"])


def _current_calculation_head(profile: RegisteredCliProfile, work_unit_id: str) -> object:
    status = cli(profile, "--format", "json", "app", "modelo", "work", "status", work_unit_id)
    assert status.exit_code == 0, status.output
    return unwrap_schema_envelope(status.output)["current_calculation_revision_id"]


@pytest.mark.parametrize(
    ("option_arguments", "named_option"),
    (
        pytest.param(("--joint-return-elected",), "--joint-return-elected", id="joint-return-elected"),
        pytest.param(("--no-joint-return-elected",), "--joint-return-elected", id="no-joint-return-elected"),
        pytest.param(
            ("--m303-exonerado-390-sha256", _M303_ONLY_SHA256),
            "--m303-exonerado-390-sha256",
            id="exonerado-390-sha256",
        ),
    ),
)
@pytest.mark.parametrize("address_by_work_unit_id", (True, False), ids=("by-work-unit-id", "by-modelo-address"))
def test_work_calculate_refuses_a_modelo_303_option_on_modelo_100_at_the_boundary(
    tmp_path: Path, option_arguments: tuple[str, ...], named_option: str, address_by_work_unit_id: bool
) -> None:
    """A Modelo 303 filing-evidence option on a Modelo 100 calculation ends at the CLI, naming the option."""
    with operator_profile(tmp_path, M100_FACTS) as profile:
        work_unit_id = _m100_work_unit(profile)
        address = (
            (work_unit_id,)
            if address_by_work_unit_id
            else (
                "--modelo",
                "100",
                "--year",
                str(m100_exercise()),
                "--period",
                "0A",
                "--revision",
                revision_selected_for("100", m100_exercise(), "0A").id,
            )
        )
        refused = cli(profile, "--language", "en", "app", "modelo", "work", "calculate", *address, *option_arguments)
        head = _current_calculation_head(profile, work_unit_id)

    assert refused.exit_code != 0, refused.output
    assert named_option in refused.output
    assert "belong to Modelo 303 only" in refused.output
    assert "Modelo 100 takes none of these options" in refused.output
    assert "nothing was calculated" in refused.output
    # A refusal the application raised would carry a runtime operation id and a
    # filing-evidence condition; this one never reached the runtime.
    assert "Operation id" not in refused.output
    assert "m303_filing_evidence" not in refused.output
    assert head in ("", None)


def test_work_calculate_modelo_100_without_a_modelo_303_option_is_unaffected(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """Modelo 100 still calculates when none of the Modelo 303 options is supplied."""
    exercise = m100_exercise()
    with operator_profile(tmp_path, M100_FACTS) as profile:
        work_unit_id = _m100_work_unit(profile)
        with opened_profile(profile, authority_operation) as bucket_id:
            seed_prior_m100_zero_carry(exercise)
            TransactionCatalogueRepository(bucket_id=bucket_id).save(
                TransactionCatalogue.from_transactions((m100_activity_income_transaction(),)),
            )
            InvoiceCatalogueRepository(bucket_id=bucket_id).save(InvoiceCatalogue())
        imputation = cli(
            profile,
            "config",
            "profile",
            "edit",
            PROFILE_LABEL,
            "--quiet",
            "--irpf-activity-income-imputation-criterion",
            "cobros_y_pagos",
            "--irpf-activity-income-imputation-year",
            str(exercise),
            "--no-irpf-codigo-comercio-accounting",
        )
        assert imputation.exit_code == 0, imputation.output
        calculated = cli(profile, "--format", "json", "app", "modelo", "work", "calculate", work_unit_id)
        head = _current_calculation_head(profile, work_unit_id)

    assert calculated.exit_code == 0, calculated.output
    assert head == unwrap_schema_envelope(calculated.output)["calculation_revision_id"]


def test_work_calculate_modelo_303_still_takes_the_joint_return_option(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The option on the modelo that declares it passes the boundary and calculates."""
    with operator_profile(tmp_path) as profile:
        work_unit = create_303_work_unit(profile)
        with opened_profile(profile, authority_operation) as bucket_id:
            TransactionCatalogueRepository(bucket_id=bucket_id).save(TransactionCatalogue.from_transactions(()))
            seed_zero_iva_wallet_decision()
        calculated = cli(
            profile,
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            *joint_return_options(),
        )
    assert calculated.exit_code == 0, calculated.output
