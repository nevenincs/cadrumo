"""A statement export whose column-naming role cannot be run refuses with the service's typed verdict.

The import runs through the real provider detection, the mapped tabular lane,
the composed column-role mapper, the production client and agent adapter and
the application import action, against a recording stand-in for the agent
service behind the model-run port. What the person receives is the operation's
refusal, so the cases assert the projected operation error detail as well as
the raised error: the verdict names the refused run and the role, and no other
lane or model is tried.

The control is the same file under a mapper that answered and established
nothing: that stays the unsupported-file refusal and names no component.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from .....application.cli_exception_preconditions import nested_terminal_precondition_verdict
from .....application.ledger.actions_import import prepare_ledger_source_import
from .....application.ledger.column_roles import ColumnRoleReaderUnavailable, bind_column_role_mapping_resolver
from .....application.ledger.import_ports import LedgerImportReaderUnavailableError
from .....application.ledger.models import LedgerSourceImportCommand
from .....application.operations.error_detail import build_operation_error_detail
from .....core.model_roles import ModelRole
from .....core.tabular import NormalizedTable
from .....domain.transactions.errors import TransactionValidationError
from .....tests.fixtures.settings import EnvFileFreeSettings
from .....tests.inventory import FIXTURES_DIR
from ....outbound.llm.client import LLMClient
from ....outbound.llm.column_role_mapping import ColumnRoleProposal, SemanticColumnRoleMapper, resolve_column_roles
from ....outbound.llm.tests.model_run_support import ON_HOST_LANE, serving_agent
from ..ledger_import import build_ledger_import_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_inbound_adapter]

#: An expenses-app export whose header vocabulary no exact provider reads, so
#: only the mapping lane can read it.
_UNKNOWN_FORMAT_FIXTURE = FIXTURES_DIR / "financial" / "tabular-dialects" / "expenses_app_export_2026.csv"


@contextmanager
def _composed_mapper(tmp_path: Path) -> Generator[None]:
    """Bind the production column-role resolver over the production client."""
    settings = EnvFileFreeSettings(
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_record_dir=tmp_path / "run-record",
    )

    def resolve(table: NormalizedTable) -> ColumnRoleProposal | ColumnRoleReaderUnavailable | None:
        mapper = SemanticColumnRoleMapper(client=LLMClient(settings=settings), settings=settings)
        return resolve_column_roles(table, mapper=mapper)

    with bind_column_role_mapping_resolver(resolve):
        yield


def _import_unknown_export() -> None:
    prepare_ledger_source_import(
        LedgerSourceImportCommand(path=_UNKNOWN_FORMAT_FIXTURE, provider="auto", dry_run=True),
        ports=build_ledger_import_ports(),
    )


def _assert_refusal_names(error: LedgerImportReaderUnavailableError, code: ModelRunRefusalCode) -> None:
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "llm.agent.model_run_completed"
    assert verdict.evidence[0].values["model_run_refusal"] == code.value
    assert verdict.evidence[0].values["model_role"] == ModelRole.COLUMN_ROLE_MAPPING.value
    assert nested_terminal_precondition_verdict(error) == verdict

    detail = build_operation_error_detail(error)
    assert detail is not None
    assert detail.error_code == "REFUSED_LEDGER_IMPORT_READER"
    projected = detail.precondition_verdict()
    assert projected is not None
    assert projected.failed_condition_id == verdict.failed_condition_id


def test_a_role_with_no_selection_refuses_the_import_with_its_typed_verdict(tmp_path: Path) -> None:
    with (
        serving_agent(lane=ON_HOST_LANE, lookup_refusal=ModelRunRefusalCode.NO_SELECTION) as service,
        _composed_mapper(tmp_path),
        pytest.raises(LedgerImportReaderUnavailableError) as raised,
    ):
        _import_unknown_export()

    _assert_refusal_names(raised.value, ModelRunRefusalCode.NO_SELECTION)
    assert isinstance(raised.value, TransactionValidationError), "callers handling import refusals keep handling it"
    assert service.runs == []


def test_no_running_service_refuses_the_import_as_service_unavailable(tmp_path: Path) -> None:
    with _composed_mapper(tmp_path), pytest.raises(LedgerImportReaderUnavailableError) as raised:
        _import_unknown_export()

    _assert_refusal_names(raised.value, ModelRunRefusalCode.SERVICE_UNAVAILABLE)


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
