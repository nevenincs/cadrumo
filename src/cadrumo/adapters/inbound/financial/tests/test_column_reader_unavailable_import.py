"""A statement export whose column-naming model is missing refuses with the local AI setup.

The import runs through the real provider detection, the mapped tabular lane,
the composed column-role mapper and the application import action, against an
Ollama-shaped loopback runtime. What the person receives is the operation's
refusal, so the cases assert the projected operation error detail as well as the
raised error: the verdict, with ``operator.provision.local_ai`` as its action,
is what every surface routes to setup.

The control is the same file under a mapper that answered and established
nothing: that stays the unsupported-file refusal and names no component.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import override

import pytest

from .....application.cli_exception_preconditions import nested_terminal_precondition_verdict
from .....application.ledger.actions_import import prepare_ledger_source_import
from .....application.ledger.column_roles import ColumnRoleReaderUnavailable, bind_column_role_mapping_resolver
from .....application.ledger.import_ports import LedgerImportReaderUnavailableError
from .....application.ledger.models import LedgerSourceImportCommand
from .....application.operations.error_detail import build_operation_error_detail
from .....application.provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID, ProvisioningPreconditionCondition
from .....core.config import override_settings
from .....core.tabular import NormalizedTable
from .....domain.transactions.errors import TransactionValidationError
from .....tests.fixtures.settings import EnvFileFreeSettings
from .....tests.inventory import FIXTURES_DIR
from .....tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_json_response
from ....outbound.llm.column_role_mapping import ColumnRoleProposal, SemanticColumnRoleMapper, resolve_column_roles
from ..ledger_import import build_ledger_import_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_inbound_adapter]

#: An expenses-app export whose header vocabulary no exact provider reads, so
#: only the mapping lane can read it.
_UNKNOWN_FORMAT_FIXTURE = FIXTURES_DIR / "financial" / "tabular-dialects" / "expenses_app_export_2026.csv"

#: A port nothing listens on, so the runtime genuinely does not answer.
_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"


@contextmanager
def _runtime_without_models() -> Generator[str]:
    """Serve a runtime that answers and holds no model at all."""

    class _Runtime(SilentLoopbackHandler):
        @override
        def do_GET(self) -> None:
            if self.path == "/api/tags":
                write_json_response(self, {"models": []}, status=HTTPStatus.OK)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

    with serving_loopback(_Runtime, path="/api/chat") as endpoint:
        yield endpoint


@contextmanager
def _composed_mapper(tmp_path: Path, endpoint: str) -> Generator[None]:
    """Bind the production column-role resolver against the runtime at ``endpoint``."""
    settings = EnvFileFreeSettings(
        cadrumo_llm_ollama_chat_url=endpoint,
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_record_dir=tmp_path / "run-record",
    )

    def resolve(table: NormalizedTable) -> ColumnRoleProposal | ColumnRoleReaderUnavailable | None:
        return resolve_column_roles(table, mapper=SemanticColumnRoleMapper(settings=settings))

    with override_settings(cadrumo_llm_ollama_chat_url=endpoint), bind_column_role_mapping_resolver(resolve):
        yield


def _import_unknown_export() -> None:
    prepare_ledger_source_import(
        LedgerSourceImportCommand(path=_UNKNOWN_FORMAT_FIXTURE, provider="auto", dry_run=True),
        ports=build_ledger_import_ports(),
    )


def _assert_refusal_offers_setup(error: LedgerImportReaderUnavailableError, condition: str) -> None:
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == condition
    assert verdict.action is not None
    assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    assert nested_terminal_precondition_verdict(error) == verdict

    detail = build_operation_error_detail(error)
    assert detail is not None
    assert detail.error_code == "REFUSED_LEDGER_IMPORT_READER"
    projected = detail.precondition_verdict()
    assert projected is not None
    assert projected.action is not None
    assert projected.action.action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_a_missing_mapping_model_refuses_the_import_with_the_local_ai_setup(tmp_path: Path) -> None:
    with (
        _runtime_without_models() as endpoint,
        _composed_mapper(tmp_path, endpoint),
        pytest.raises(LedgerImportReaderUnavailableError) as raised,
    ):
        _import_unknown_export()

    _assert_refusal_offers_setup(raised.value, ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED.value)
    assert isinstance(raised.value, TransactionValidationError), "callers handling import refusals keep handling it"


def test_an_unanswering_runtime_refuses_the_import_with_the_local_ai_setup(tmp_path: Path) -> None:
    with _composed_mapper(tmp_path, _CLOSED_ENDPOINT), pytest.raises(LedgerImportReaderUnavailableError) as raised:
        _import_unknown_export()

    _assert_refusal_offers_setup(raised.value, ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value)


def test_a_mapper_that_established_nothing_stays_an_unsupported_file() -> None:
    """Control: a decline is not a missing component, so it names no setup."""

    def decline(table: NormalizedTable) -> ColumnRoleProposal | None:
        del table
        return None

    with bind_column_role_mapping_resolver(decline), pytest.raises(TransactionValidationError) as raised:
        _import_unknown_export()

    assert not isinstance(raised.value, LedgerImportReaderUnavailableError)
    detail = build_operation_error_detail(raised.value)
    assert detail is not None
    assert detail.precondition_verdict() is None
