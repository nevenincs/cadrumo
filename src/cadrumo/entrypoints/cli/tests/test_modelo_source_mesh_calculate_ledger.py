"""CLI roundtrip coverage for ledger source-mesh observations and the IVA advisories of modelo calculation."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend,
)
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.iva_deduction_fact import IvaDeductionFactKind
from cadrumo.core.period import Period
from cadrumo.core.redaction.rules import redact_for_cli_output
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.iva.schema import EUMemberState, IvaCategory
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import TransactionCatalogue
from cadrumo.tests.cli_envelope import unwrap_envelope_notices, unwrap_schema_envelope

from .ordinary_m303_scenarios import joint_return_options
from .source_mesh_calculate_transactions import (
    ledger_transaction,
)

__all__ = ["isolated_cli_backend"]

# Seeded rows and stored records decode against registry facts, so the test
# body holds the same authority lease a CLI invocation holds. Every command runs
# through the registered profile's native worker, as an operator's CLI does.
from .source_mesh_calculate_support import (
    ACTIVITY_YEAR,
    IVA_WALLET_DECIDED_AT,
    PROFILE_LABEL,
    cli,
    create_303_work_unit,
    opened_profile,
    operator_profile,
    seed_zero_iva_wallet_decision,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.usefixtures("authority_operation"),
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


def _seed_ledger_and_zero_wallet_decision(bucket_id, sale, purchase):
    from cadrumo.adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
    from cadrumo.domain.iva_compensation.reconciliation import (
        IvaCompensationAuthoritySource,
        IvaCompensationReconciliationDecision,
    )

    TransactionCatalogueRepository(bucket_id=bucket_id).save(
        TransactionCatalogue.from_transactions((sale, purchase)),
    )
    decision = IvaCompensationReconciliationDecision(
        taxpayer_nif="12345678Z",
        target_year=ACTIVITY_YEAR,
        target_period=Period.from_year_and_code(ACTIVITY_YEAR, "1T"),
        target_registry_snapshot_ref=published_snapshot("303", filing_year=ACTIVITY_YEAR, period="1T").snapshot_ref,
        source_registry_snapshot_refs=(published_snapshot("303", filing_year=ACTIVITY_YEAR, period="1T").snapshot_ref,),
        selected_authority="local_recurrence",
        selected_amount=Decimal("0"),
        wallet_amount=None,
        local_recurrence_amount=Decimal("0"),
        authority_sources=(
            IvaCompensationAuthoritySource(
                source_kind="local_recurrence",
                amount=Decimal("0"),
                source_locator=f"test:local-recurrence:{ACTIVITY_YEAR}:1T",
                source_modelo="303",
                source_filing_year=ACTIVITY_YEAR,
                source_periods=(Period.from_year_and_code(ACTIVITY_YEAR, "1T"),),
                registry_snapshot_refs=(
                    published_snapshot("303", filing_year=ACTIVITY_YEAR, period="1T").snapshot_ref,
                ),
            ),
        ),
        override_amount=None,
        divergence="wallet_missing",
        blocked=False,
        stale_wallet=False,
        reason_identity="first_period_zero_aeat_wallet",
        decided_at=IVA_WALLET_DECIDED_AT,
    )
    IvaWalletDecisionRepository().save_decision(decision)


def _assert_calculated_source_mesh(payload, persisted, sale, purchase):
    payload_provenance = payload["source_provenance"]
    assert payload_provenance, "calculate JSON must carry the persisted source-mesh trace"
    # CLI output carries the profile id as its paste-safe placeholder, so the
    # persisted refs are compared as that output renders them.
    assert {row["source_ref"] for row in payload_provenance} == {
        redact_for_cli_output(source.source_ref) for source in persisted.source_provenance
    }
    assert persisted.source_transaction_ids == tuple(sorted((sale.transaction_id, purchase.transaction_id)))
    assert Decimal(persisted.binding_overrides["modelo-303-iva-repercutido-general-cuota"]) == sale.iva_amount
    assert Decimal(persisted.binding_overrides["modelo-303-iva-soportado-interiores-cuota"]) == purchase.iva_amount
    observations = {observation.casilla_id: observation for observation in persisted.observations}
    output_observation = observations["iva.repercutido.general"]
    input_observation = observations["iva.soportado.interiores"]
    assert output_observation.formula_id is None
    assert input_observation.formula_id is None
    assert output_observation.legal_refs
    assert input_observation.legal_refs
    assert output_observation.source_refs
    assert input_observation.source_refs
    payload_observations = {observation["casilla_id"]: observation for observation in payload["observations"]}
    assert payload_observations["iva.repercutido.general"]["source_refs"] == list(output_observation.source_refs)
    assert payload_observations["iva.soportado.interiores"]["source_refs"] == list(input_observation.source_refs)
    return output_observation, input_observation


def _assert_observations_command_payload(
    observations_result, revision_id, work_unit, payload, output_observation, input_observation
):
    assert observations_result.exit_code == 0, observations_result.output
    observations_payload = unwrap_schema_envelope(observations_result.output)
    assert observations_payload["operation"] == "modelo.work.observations"
    assert observations_payload["calculation_revision_id"] == revision_id
    assert observations_payload["work_unit_id"] == work_unit["work_unit_id"]
    assert observations_payload["observation_count"] == len(payload["observations"])
    command_observations = {
        observation["casilla_id"]: observation for observation in observations_payload["observations"]
    }
    assert command_observations["iva.repercutido.general"]["legal_refs"] == list(output_observation.legal_refs)
    assert command_observations["iva.repercutido.general"]["source_refs"] == list(output_observation.source_refs)
    assert command_observations["iva.soportado.interiores"]["legal_refs"] == list(input_observation.legal_refs)
    assert command_observations["iva.soportado.interiores"]["source_refs"] == list(input_observation.source_refs)


def _assert_observations_text_output(text_observations, revision_id, output_observation):
    assert text_observations.exit_code == 0, text_observations.output
    assert "operation\tmodelo.work.observations" in text_observations.output
    assert f"calculation_revision_id\t{revision_id}" in text_observations.output
    assert "iva.repercutido.general" in text_observations.output
    assert output_observation.legal_refs[0] in text_observations.output
    assert output_observation.source_refs[0] in text_observations.output


def _assert_wizard_emits_source_mesh_provenance(capsys, native_profile, operation, work_unit, persisted):
    # The wizard's success emitter receives the same persisted calculation
    # result as calculate. Exercise its real JSON envelope with this
    # source-mesh-backed revision, rather than a hand-built payload, so a
    # future mapper exclusion cannot make its provenance disappear.
    import typer
    import typer.main

    from cadrumo.application.modelo.calculate_input import ModeloWorkCalculationServiceResult
    from cadrumo.application.modelo.calculation_operation import calculation_public_result
    from cadrumo.entrypoints.cli.modelo_work_wizard_cli import emit_wizard_result

    from .modelo_work_scenarios import load_work_unit_by_id

    wizard_app = typer.Typer()

    @wizard_app.command()
    def _noop() -> None: ...

    wizard_context = typer.Context(typer.main.get_command(wizard_app), obj={"format": "json"})
    authenticate_profile_for_invocation(
        name=PROFILE_LABEL,
        passphrase_callback=lambda: native_profile.passphrase,
        profile_decode_context=operation.profile_decode_context(),
    )
    wizard_work_unit = load_work_unit_by_id(work_unit_id=work_unit["work_unit_id"])
    emit_wizard_result(
        wizard_context,
        calculation_public_result(
            ModeloWorkCalculationServiceResult(revision=persisted, work_unit=wizard_work_unit, revision_published=True),
            operation=operation,
        ),
        (),
        language=OutputLanguage.EN,
    )
    wizard_payload = unwrap_schema_envelope(capsys.readouterr().out)
    assert wizard_payload["source_provenance"], "wizard JSON must carry the persisted source-mesh trace"
    assert {row["source_ref"] for row in wizard_payload["source_provenance"]} == {
        redact_for_cli_output(source.source_ref) for source in persisted.source_provenance
    }


def test_work_calculate_persists_ledger_source_mesh_observations(
    capsys: pytest.CaptureFixture[str],
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    with operator_profile(tmp_path) as native_profile:
        work_unit = create_303_work_unit(native_profile)
        sale = ledger_transaction(
            "sale-general",
            direction=TransactionDirection.INCOMING,
            amount=Decimal("121.00"),
            taxable_base=Decimal("100.00"),
            iva_amount=Decimal("21.00"),
        )
        purchase = ledger_transaction(
            "purchase-general",
            direction=TransactionDirection.OUTGOING,
            amount=Decimal("60.50"),
            taxable_base=Decimal("50.00"),
            iva_amount=Decimal("10.50"),
            deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_current"),
            deduction_locator=f"invoice:purchase-general-{ACTIVITY_YEAR}-1T",
        )

        # Seed ledger data and a zero-amount IVA wallet decision after password
        # authentication has opened the registered profile's actual encrypted
        # bucket.  The test-only synthetic DEK helper cannot reopen a retired
        # registered-profile session.
        # The IVA wallet decision is required by the Modelo 303 reconciliation
        # guard: it blocks calculation when ``compensacion-pendiente-anteriores``
        # is supplied without a persisted decision, even when the amount is zero.
        # A local_recurrence decision with selected_amount=0 satisfies the guard
        # while leaving the ledger mesh assertions meaningful.
        # The CLI JSON output redacts ``bucket_id``, so seeding takes it from the
        # password login that opens the registered profile's encrypted bucket.
        bucket_id = authenticate_profile_for_invocation(
            name=PROFILE_LABEL,
            passphrase_callback=lambda: native_profile.passphrase,
            profile_decode_context=operation.profile_decode_context(),
        ).bucket_id
        _seed_ledger_and_zero_wallet_decision(bucket_id, sale, purchase)
        result = cli(
            native_profile,
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            *joint_return_options(),
        )
        assert result.exit_code == 0, result.output
        payload = unwrap_schema_envelope(result.output)
        revision_id = payload["calculation_revision_id"]

        authenticate_profile_for_invocation(
            name=PROFILE_LABEL,
            passphrase_callback=lambda: native_profile.passphrase,
            profile_decode_context=operation.profile_decode_context(),
        )
        persisted = CalculationRevisionCatalogueRepository().load().revisions[revision_id]

        output_observation, input_observation = _assert_calculated_source_mesh(payload, persisted, sale, purchase)
        observations_result = cli(
            native_profile,
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "observations",
            revision_id,
        )
        _assert_observations_command_payload(
            observations_result, revision_id, work_unit, payload, output_observation, input_observation
        )
        text_observations = cli(
            native_profile,
            "app",
            "modelo",
            "work",
            "observations",
            revision_id,
        )
        _assert_observations_text_output(text_observations, revision_id, output_observation)
        _assert_wizard_emits_source_mesh_provenance(capsys, native_profile, operation, work_unit, persisted)


def test_work_calculate_suppresses_advisory_for_cuota_less_intra_community_supply(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """An INTRA_COMMUNITY_SUPPLY observation is cuota-less, so it raises NO advisory.

    Per the ``aeat-ledger-contract`` rule, an
    exempt entrega intracomunitaria (Ley 37/1992 art. 25) is base-only with no
    cuota to route: it is a member of ``CUOTA_LESS_M303_IVA_CATEGORIES`` and
    MUST NEVER fire the unconsumed-declarable-IVA advisory. Flagging it would be
    a false positive that trains operators to ignore the alert, so the advisory
    only earns trust if every fire is a genuine unrouted cuota. This test pins
    that suppression on the operator-facing calculate surface across both the
    JSON ``notices`` channel and the human text output.
    """
    # A consumed domestic sale (matches the repercutido-general binding) ...
    domestic_sale = ledger_transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    # ... plus a cuota-less intra-community supply (exempt, base-only) that no
    # M303 cuota binding selects and that must NOT raise a source advisory.
    cuota_less_supply = ledger_transaction(
        "intra-community-supply",
        direction=TransactionDirection.INCOMING,
        # Base-only, as an exempt supply is: LIVA art. 25 exempts the operation,
        # so no cuota arises and the invoice total IS the base. The fixture
        # previously declared 242,00 against a 200,00 base with 42,00 of cuota at
        # the default 0,21 tipo -- a row the law does not admit, which the
        # aggregation guard correctly refused. The advisory was right; the data
        # was wrong.
        amount=Decimal("200.00"),
        taxable_base=Decimal("200.00"),
        iva_rate=Decimal("0"),
        iva_amount=Decimal("0"),
        iva_category=IvaCategory("intra_community_supply"),
        counterparty_country="DE",
        # Established AND IVA-identified in Germany, which is the ordinary case.
        # Art. 25 exempts on the IDENTIFICATION, so the supply is refused at
        # preflight without it however clear the establishment is; declaring
        # only the establishment is what this fixture used to do.
        counterparty_identification_state=EUMemberState.from_registry("de"),
    )
    with operator_profile(tmp_path) as profile:
        work_unit = create_303_work_unit(profile)
        with opened_profile(profile, authority_operation) as bucket_id:
            TransactionCatalogueRepository(bucket_id=bucket_id).save(
                TransactionCatalogue.from_transactions((domestic_sale, cuota_less_supply)),
            )
            seed_zero_iva_wallet_decision()

        result = cli(
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
        # Text mode likewise emits no source ADVISORY line for the cuota-less supply.
        # Re-run in text mode against the same seeded bucket; the calculate verb is
        # idempotent over the ledger substrate (it persists a new draft revision but
        # the cuota-less supply stays advisory-free on both transports).
        text_result = cli(
            profile,
            "--language",
            "en",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            *joint_return_options(),
        )
    assert result.exit_code == 0, result.output

    notices = unwrap_envelope_notices(result.output)
    source_advisories = [notice for notice in notices if notice["code"] == "modelo.work.calculate.source_advisory"]
    assert source_advisories == [], (
        f"INTRA_COMMUNITY_SUPPLY is cuota-less and must not raise a source advisory; got {source_advisories}"
    )

    assert text_result.exit_code == 0, text_result.output
    # Pinned to English because "ADVISORY:" is the ENGLISH prefix. The ambient
    # test locale is Spanish, which renders the same notice as "AVISO:", so
    # this absence claim was satisfied by every run whether or not an
    # advisory was surfaced -- the one thing the test exists to detect.
    assert "ADVISORY:" not in text_result.output


def test_work_calculate_emits_no_advisory_when_all_iva_consumed(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """#64 converse: an all-consumed IVA observation set surfaces ZERO advisories.

    Anti-tautology guard for the advisory test above: only observations no
    binding selects produce a diagnostic. A domestic sale matched by the
    repercutido-general binding must leave ``source_advisories`` empty and emit
    no ADVISORY line.
    """
    domestic_sale = ledger_transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    with operator_profile(tmp_path) as profile:
        work_unit = create_303_work_unit(profile)
        with opened_profile(profile, authority_operation) as bucket_id:
            TransactionCatalogueRepository(bucket_id=bucket_id).save(
                TransactionCatalogue.from_transactions((domestic_sale,)),
            )
            seed_zero_iva_wallet_decision()

        result = cli(
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
        # Text mode emits no ADVISORY line either: only an unrouted declarable
        # observation produces one, and every observation here was consumed.
        text_result = cli(
            profile,
            "--language",
            "en",
            "app",
            "modelo",
            "work",
            "calculate",
            str(work_unit["work_unit_id"]),
            *joint_return_options(),
        )
    assert result.exit_code == 0, result.output

    notices = unwrap_envelope_notices(result.output)
    assert [n for n in notices if n["code"] == "modelo.work.calculate.source_advisory"] == []

    assert text_result.exit_code == 0, text_result.output
    # Pinned to English because "ADVISORY:" is the ENGLISH prefix. The ambient
    # test locale is Spanish, which renders the same notice as "AVISO:", so
    # this absence claim was satisfied by every run whether or not an
    # advisory was surfaced -- the one thing the test exists to detect.
    assert "ADVISORY:" not in text_result.output
