"""Surface contract for the ``ledger participation`` verb and ``track`` extension.

Introspects the live Typer command tree (without invoking the CLI runtime) to
assert the participation verb and the ``rebuild`` subcommand are registered, that
no dead ``--include-borradores`` flag is shipped, and that ``LedgerTrackResult``
carries the ``participated_in`` field. Also exercises the read action end-to-end
against a real participation index built from a real revision lifecycle.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.ledger.participation_read import get_transaction_participation
from ....core.config import override_settings
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.participation_index import (
    TransactionRevisionParticipation,
    TransactionRevisionParticipationIndex,
)
from .._ledger_payloads import LedgerTrackResult, LedgerTransactionParticipationPayload
from ..command_spec import ArgumentSpec, OptionSpec
from ..command_specs import COMMAND_GRAPH
from ._runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]


def test_participation_verb_declares_subject_argument() -> None:
    """The participation group declares the transaction-id subject argument."""
    spec = COMMAND_GRAPH.resolve_path(("aeat", "app", "ledger", "participation"))
    assert any(
        isinstance(parameter, ArgumentSpec) and parameter.name == "transaction_id" for parameter in spec.parameters
    )


def test_participation_verb_carries_no_dead_borradores_flag() -> None:
    """The unbuilt ``--include-borradores`` flag is removed, not shipped dead.

    The participation index records only finalized-revision participations;
    borrador (draft) participation tracking is unbuilt. A dead operator-facing
    flag whose help admitted "no effect yet" was removed rather than shipped, so
    this guards against its re-introduction.
    """
    spec = COMMAND_GRAPH.resolve_path(("aeat", "app", "ledger", "participation"))
    declared_opts = {
        declaration
        for parameter in spec.parameters
        if isinstance(parameter, OptionSpec)
        for declaration in parameter.declarations
    }
    assert "--include-borradores" not in declared_opts


def test_participation_rebuild_subcommand_is_registered() -> None:
    """The participation group exposes the ``rebuild`` subcommand."""
    children = {node.spec.token for node in COMMAND_GRAPH.nodes() if node.spec.parent_key == "app_ledger_participation"}
    assert "rebuild" in children


def _invoke_participation(profile: NativeCliProfileFixture, *args: str) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_cached_cli(
            [
                "--language",
                "en",
                "--profile",
                profile.label,
                "--profile-secrets-stdin",
                "app",
                "ledger",
                "participation",
                *args,
            ],
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
    assert profile.passphrase not in result.output
    return result


def _seed_transaction_id(profile: NativeCliProfileFixture) -> str:
    assert profile.label is not None
    close_active_bucket_session()
    result = invoke_cached_cli(
        [
            "--profile",
            profile.label,
            "--profile-secrets-stdin",
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-05-02",
            "--amount",
            "121.00",
            "--direction",
            "OUTGOING",
            "--description",
            "participation lookup seed",
            "--counterparty",
            "Proveedor SL",
            "--idempotency-key",
            "participation-lookup-seed",
        ],
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert result.exit_code == 0, result.output
    assert profile.passphrase not in result.output
    envelope = json.loads(result.output)
    transaction_id = envelope["result"]["transaction_id"]
    assert isinstance(transaction_id, str)
    return transaction_id


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_participation_rebuild_dispatches_not_swallowed_as_id(tmp_path: Path) -> None:
    """``participation rebuild`` dispatches the subcommand, not the lookup.

    Regression for audit B4: the group used ``invoke_without_command=True`` with
    an optional positional ``transaction_id``, so Click bound the literal
    ``rebuild`` token to ``transaction_id`` and the lookup tried to hex-validate
    it instead of regenerating the index. The fix forwards a reserved
    subcommand name to its command. Asserts the rebuild action runs to a
    success exit (the typed rebuild counts), never the hex-validation failure.
    """
    facts = {
        "taxpayer_type.entity_type": "natural_person",
        "identity.name": "Participation",
        "identity.surnames": "Rebuilder",
        "activities.description": "design",
        "censo.activity_start_date": "2025-01-01",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.regime": "GENERAL",
        "iva.m303_regime_composition": "general",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    }
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-participation-rebuild", facts=facts)
        close_active_bucket_session()
        result = _invoke_participation(profile, "rebuild")

    assert result.exit_code == 0, result.output
    assert "no hexadecimales" not in result.output
    assert "revision_count" in result.output


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_participation_lookup_still_works_for_transaction_id(tmp_path: Path) -> None:
    """``participation <transaction-id>`` keeps its documented lookup UX.

    A 64-hex id that is not a reserved subcommand name reaches the lookup action
    and emits the typed participation payload (empty participations for an
    untracked transaction), proving the reserved-name guard does not divert
    genuine lookup ids.
    """
    facts = {
        "taxpayer_type.entity_type": "natural_person",
        "identity.name": "Participation",
        "identity.surnames": "Lookup",
        "activities.description": "design",
        "censo.activity_start_date": "2025-01-01",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.regime": "GENERAL",
        "iva.m303_regime_composition": "general",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    }
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-participation-lookup", facts=facts)
        close_active_bucket_session()
        transaction_id = _seed_transaction_id(profile)
        result = _invoke_participation(profile, transaction_id)

    assert result.exit_code == 0, result.output
    assert transaction_id in result.output


def test_ledger_track_result_schema_carries_participated_in() -> None:
    """``LedgerTrackResult`` declares the ``participated_in`` field."""
    assert "participated_in" in LedgerTrackResult.model_fields
    # The field is optional (omitted for transactions with no finalized participations).
    assert LedgerTrackResult.model_fields["participated_in"].is_required() is False


def test_participation_payload_schema_shape() -> None:
    """``LedgerTransactionParticipationPayload`` carries the transaction id and entries."""
    fields = LedgerTransactionParticipationPayload.model_fields
    assert "transaction_id" in fields
    assert "participations" in fields


def test_get_transaction_participation_reads_real_index(tmp_path: Path) -> None:
    """The read action returns the persisted participations for a transaction."""
    bucket_id = "44440003-0000-4000-8000-000000000003"
    bucket_label = "participation read"
    transaction_id = "a" * 64
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id, label=bucket_label):
        repo = TransactionParticipationIndexRepository(bucket_id=bucket_id)
        index = TransactionRevisionParticipationIndex(
            transaction_id=transaction_id,
            participations=(
                TransactionRevisionParticipation(
                    calculation_revision_id="b" * 64,
                    work_unit_id="c" * 64,
                    modelo=ModeloCode("303"),
                    filing_year=2024,
                    period=Period.from_year_and_code(2024, "2T"),
                    revision_state="presentado",
                    filing_record_id="d" * 64,
                ),
            ),
        )
        repo.save(index)

        loaded = get_transaction_participation(transaction_id=transaction_id, bucket_id=bucket_id)

    assert loaded.transaction_id == transaction_id
    (entry,) = loaded.participations
    assert entry.modelo == "303"
    assert entry.revision_state == "presentado"
    assert entry.filing_record_id == "d" * 64


def test_get_transaction_participation_empty_for_unknown(tmp_path: Path) -> None:
    """A transaction with no finalized participation returns an empty index, not an error."""
    bucket_id = "44440004-0000-4000-8000-000000000004"
    bucket_label = "participation read empty"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id, label=bucket_label):
        loaded = get_transaction_participation(transaction_id="9" * 64, bucket_id=bucket_id)

    assert loaded.participations == ()
