"""The workbench generation reader decides Modelo 232 from the stated records exactly as the CLI overview does.

The door under test is the production one, bound to the real encrypted Modelo 232
store; the other stores are the in-memory doubles the generation contract tests use,
because the question here is whether the stated records reach the workbench calendar
and invalidate its cached work. Records, identifiers and amounts are synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest

from .....application.aggregation.m232_registry_parameters import modelo_232_thresholds
from .....application.aggregation.m232_related_party_repository import (
    Modelo232PinnedWriteAuthority,
    Modelo232RelatedPartyWritePorts,
    state_m232_none,
    state_m232_operation,
    state_m232_turnover,
    withdraw_m232_none,
)
from .....application.overview.applicability_evidence import (
    bind_filing_year_applicability_evidence,
    loaded_invoice_source_ports,
)
from .....application.overview.calendar import build_overview_calendar
from .....application.overview.home import HomeAccountSession, HomeSessionPosture
from .....application.tests.workbench_generation_support import calendar_builds
from .....application.user_profile.projections import projection_for_taxpayer
from .....application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from .....application.workbench_capture_memory import WorkbenchCaptureMemory
from .....application.workbench_generation_reader import SecureProfileWorkbenchGenerationReadDoorV1
from .....core.modelo import Modelo
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.invoices.tests.catalogue_support import build_invoice_catalogue
from .....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from .....domain.modelos.filing_record import ModeloRecordCatalogue
from .....domain.modelos.m232_related_party import (
    Modelo232Direction,
    Modelo232NoneStatement,
    Modelo232Operation,
    Modelo232OperationKind,
    Modelo232TurnoverSource,
    Modelo232TurnoverStatement,
)
from .....domain.modelos.work_unit import WorkUnitCatalogue
from .....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from ...storage.runtime_repository import secure_object_repository_for_active_bucket
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..m232_related_party_records import Modelo232RelatedPartyStoreAdapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_MODELO = Modelo("232")
_PROFILE_ID = "11111111-1111-4111-8111-111111111111"
_YEAR = filing_year_envelope().horizon
_NOW = datetime(_YEAR + 1, 2, 3, 10, 30, tzinfo=UTC)
_TAX_ID = "B99999991"


@dataclass
class _Store[ValueT]:
    value: ValueT
    revision: str = "revision-1"

    def load(self, *_args: object) -> ValueT:
        return self.value

    def load_revisioned(self, *, operation: object | None = None) -> tuple[ValueT, str]:
        return self.value, self.revision


def _company_record(operation: PinnedAuthorityOperation) -> UserProfileRecord:
    return create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value="B00015016"),
                UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            )
        ),
    )


def _door(
    operation: PinnedAuthorityOperation,
    record: UserProfileRecord,
    memory: WorkbenchCaptureMemory | None,
    *,
    bound: bool = True,
) -> SecureProfileWorkbenchGenerationReadDoorV1:
    return SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_PROFILE_ID,
        operation=operation,
        profile_repository=cast(Any, _Store(record)),
        work_unit_repository=cast(Any, _Store(WorkUnitCatalogue())),
        calculation_repository=cast(Any, _Store(CalculationRevisionCatalogue())),
        filing_repository=cast(Any, _Store(ModeloRecordCatalogue())),
        clock=lambda: _NOW,
        account_session_reader=lambda: HomeAccountSession(
            posture=HomeSessionPosture.ACTIVE, profile_label="Perfil local", expires_at=_NOW + timedelta(hours=1)
        ),
        capture_memory=memory,
        related_party_records=(
            Modelo232RelatedPartyStoreAdapter(objects=secure_object_repository_for_active_bucket()) if bound else None
        ),
    )


def _ports(operation: PinnedAuthorityOperation) -> Modelo232RelatedPartyWritePorts:
    return Modelo232RelatedPartyWritePorts(
        store=Modelo232RelatedPartyStoreAdapter(objects=secure_object_repository_for_active_bucket()),
        authority=Modelo232PinnedWriteAuthority(operation),
    )


def _stated_at(ejercicio: int) -> datetime:
    return datetime(ejercicio, 4, 2, 9, 0, tzinfo=UTC)


def _operation(ejercicio: int, amount: Decimal) -> Modelo232Operation:
    return Modelo232Operation(
        operation_id=uuid4().hex,
        ejercicio=ejercicio,
        operation_kind=Modelo232OperationKind.RELATED_PARTY,
        counterparty_tax_id=_TAX_ID,
        counterparty_name="Synthetic Related Holding",
        counterparty_country="DE",
        tipo_vinculacion="D",
        tipo_operacion="06",
        valuation_method="1A",
        direction=Modelo232Direction.PAGO,
        amount_eur=amount,
        stated_at=_stated_at(ejercicio),
    )


def _turnover(ejercicio: int, amount: Decimal) -> Modelo232TurnoverStatement:
    return Modelo232TurnoverStatement(
        statement_id=uuid4().hex,
        ejercicio=ejercicio,
        turnover_eur=amount,
        source=Modelo232TurnoverSource.ANNUAL_ACCOUNTS,
        source_reference="Synthetic ref",
        stated_at=_stated_at(ejercicio),
    )


def _none(ejercicio: int) -> Modelo232NoneStatement:
    return Modelo232NoneStatement(
        statement_id=uuid4().hex, ejercicio=ejercicio, note="Synthetic note", stated_at=_stated_at(ejercicio)
    )


def _workbench_view(
    door: SecureProfileWorkbenchGenerationReadDoorV1,
) -> tuple[set[int], bool, bool]:
    """Return the ejercicios the workbench lists for 232, and whether 232 is advised or confidently excluded."""
    calendar = door.read_declaration_list_inputs().calendar
    listed = {entry.period.filing_year for entry in calendar.entries if entry.modelo == _MODELO.value}
    return (
        listed,
        _MODELO.value in calendar.coverage.advised_modelos,
        _MODELO.value in calendar.coverage.confidently_excluded,
    )


def test_the_workbench_decides_232_as_the_cli_overview_does_and_a_new_statement_invalidates_its_cache(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    record = _company_record(operation)
    schema = operation.profile_decode_context().schema
    thresholds = modelo_232_thresholds(_YEAR, operation=operation, modelo=_MODELO, period="0A")
    over = thresholds.same_related_party_eur + Decimal("0.01")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        ports = _ports(operation)
        memory = WorkbenchCaptureMemory()

        undecided = _workbench_view(_door(operation, record, memory))
        unbound = _workbench_view(_door(operation, record, None, bound=False))
        cached_builds = calendar_builds(lambda: _door(operation, record, memory).read_declaration_list_inputs())

        state_m232_operation(_operation(_YEAR, over), ports=ports)
        state_m232_turnover(_turnover(_YEAR, over * 4), ports=ports)
        rebuilt_builds = calendar_builds(lambda: _door(operation, record, memory).read_declaration_list_inputs())
        owed = _workbench_view(_door(operation, record, memory))

        evidence = bind_filing_year_applicability_evidence(
            record=record,
            schema=schema,
            bucket_id=_PROFILE_ID,
            invoice_source_ports=loaded_invoice_source_ports(build_invoice_catalogue(())),
            operation=operation,
            today=_NOW.date(),
            related_party_records=Modelo232RelatedPartyStoreAdapter(
                objects=secure_object_repository_for_active_bucket()
            ),
        )
        workbench_range = _door(operation, record, None).read_declaration_list_inputs().calendar.query_range
        cli = build_overview_calendar(
            projection_for_taxpayer(record, schema=schema),
            workbench_range,
            operation=operation,
            today=_NOW.date(),
            applicability_evidence=evidence,
        )
        cli_listed = {entry.period.filing_year for entry in cli.entries if entry.modelo == _MODELO.value}

        statement = state_m232_none(_none(_YEAR - 1), ports=ports)
        after_none = calendar_builds(lambda: _door(operation, record, memory).read_declaration_list_inputs())
        withdraw_m232_none(
            _YEAR - 1, at=_stated_at(_YEAR - 1) + timedelta(days=1), ports=ports, expected_revision_id=statement
        )
        after_withdrawal = calendar_builds(lambda: _door(operation, record, memory).read_declaration_list_inputs())

    assert undecided[0] == set()
    assert undecided[1] is True
    assert unbound == undecided
    assert cached_builds == 0, "an unchanged capture reuses the cached calendar"
    assert rebuilt_builds > 0, "a new statement must invalidate the cached calendar"
    assert owed[0] == cli_listed
    assert _YEAR in owed[0]
    assert after_none > 0, "a new none statement must invalidate the cached calendar"
    assert after_withdrawal > 0, "a withdrawn statement must invalidate the cached calendar"
