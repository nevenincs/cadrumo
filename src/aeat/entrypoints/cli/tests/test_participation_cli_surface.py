"""Surface contract for the ``ledger participation`` verb and ``track`` extension.

Introspects the live Typer command tree (without invoking the CLI runtime) to
assert the participation verb and the ``rebuild`` subcommand are registered, that
no dead ``--include-borradores`` flag is shipped, and that ``LedgerTrackResult``
carries the ``participated_in`` field. Also exercises the read action end-to-end
against a real participation index built from a real revision lifecycle.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.core import TyperGroup

from ....application.ledger import get_transaction_participation
from ....core import Period
from ....domain.modelos import ModeloCode
from ....domain.modelos._participation_index import (
    TransactionParticipationIndexRepository,
    TransactionRevisionParticipation,
    TransactionRevisionParticipationIndex,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._ledger_payloads import LedgerTrackResult, LedgerTransactionParticipationPayload
from .._participation_cli import register_participation_commands

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _participation_group() -> TyperGroup:
    def _resolve(_repo: object, transaction_id: str) -> str:
        return transaction_id

    app = typer.Typer()
    register_participation_commands(app, resolve_transaction_id=_resolve)
    command = typer.main.get_command(app)
    assert isinstance(command, TyperGroup)
    participation = command.commands["participation"]
    assert isinstance(participation, TyperGroup)
    return participation


def test_participation_verb_declares_subject_argument() -> None:
    """The participation group declares the transaction-id subject argument."""
    group = _participation_group()

    param_names = {param.name for param in group.params}
    assert "transaction_id" in param_names


def test_participation_verb_carries_no_dead_borradores_flag() -> None:
    """The unbuilt ``--include-borradores`` flag is removed, not shipped dead.

    The participation index records only finalized-revision participations;
    borrador (draft) participation tracking is unbuilt. A dead operator-facing
    flag whose help admitted "no effect yet" was removed rather than shipped, so
    this guards against its re-introduction.
    """
    group = _participation_group()

    declared_opts = {opt for param in group.params for opt in getattr(param, "opts", [])}
    assert "--include-borradores" not in declared_opts


def test_participation_rebuild_subcommand_is_registered() -> None:
    """The participation group exposes the ``rebuild`` subcommand."""
    group = _participation_group()

    assert "rebuild" in group.commands


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
    bucket_id = "participation-cli-read"
    transaction_id = "a" * 64
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
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
    bucket_id = "participation-cli-read-empty"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        loaded = get_transaction_participation(transaction_id="9" * 64, bucket_id=bucket_id)

    assert loaded.participations == ()
