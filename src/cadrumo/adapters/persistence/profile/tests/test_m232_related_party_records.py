"""Modelo 232 related-party statements through the real encrypted store and guarded write path.

All identifiers, names, notes and amounts are synthetic. The years come from the
registry's support envelope. Operations, "none" statements and turnover
statements round-trip through the store, stay readable only through their own
kind, never reach disk or logs in plaintext, keep their history when restated,
and cannot be written by two writers of one ejercicio at once.
"""

from __future__ import annotations

import base64
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import override
from uuid import uuid4

import pytest

from .....application.aggregation.m232_registry_parameters import always_specific_operation_types
from .....application.aggregation.m232_related_party_repository import (
    Modelo232PinnedWriteAuthority,
    Modelo232RelatedPartyRefusedError,
    Modelo232RelatedPartyRevisionConflictError,
    Modelo232RelatedPartyWritePorts,
    Modelo232Row,
    Modelo232YearView,
    m232_guard_key,
    m232_none_key,
    m232_operation_key,
    m232_turnover_key,
    state_m232_none,
    state_m232_operation,
    state_m232_turnover,
    withdraw_m232_none,
    withdraw_m232_operation,
    withdraw_m232_turnover,
)
from .....core.external_constants import UTF_8_ENCODING
from .....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from .....core.storage_taxonomy import StorageCustodyProfile
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.form_codes import resolve_form_codes
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.modelos.m232_related_party import (
    Modelo232Direction,
    Modelo232Exclusion,
    Modelo232NoneStatement,
    Modelo232Operation,
    Modelo232OperationKind,
    Modelo232TurnoverSource,
    Modelo232TurnoverStatement,
    Modelo232YearGuard,
)
from ...storage.profile_custody_carry import collect_profile_custody_carry
from ...storage.runtime_repository import secure_object_repository_for_active_bucket
from ...storage.secure_object_namespaces import MODELO_232_RELATED_PARTY_NAMESPACE
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..m232_related_party_records import (
    Modelo232GuardRepositoryAdapter,
    Modelo232NoneRepositoryAdapter,
    Modelo232OperationRepositoryAdapter,
    Modelo232RelatedPartyStoreAdapter,
    Modelo232TurnoverRepositoryAdapter,
    m232_related_party_row_kind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_EJERCICIO = filing_year_envelope().horizon
_AT = datetime(_EJERCICIO, 4, 2, 9, 0, tzinfo=UTC)
_LATER = _AT + timedelta(days=1)
_TAX_ID = "B99999991"
_NAME = "Synthetic Related Holding"
_NOTE = "Synthetic note: the partners confirmed no group dealings."
_REFERENCE = "Synthetic ref: accounts filed with the registry, page 7."
_AMOUNT = Decimal("312345.67")
_TURNOVER = Decimal("987654.32")
_ABSENT = ABSENT_SECURE_OBJECT_REVISION_ID


def _ports(operation: PinnedAuthorityOperation) -> Modelo232RelatedPartyWritePorts:
    return Modelo232RelatedPartyWritePorts(
        store=Modelo232RelatedPartyStoreAdapter(objects=secure_object_repository_for_active_bucket()),
        authority=Modelo232PinnedWriteAuthority(operation),
    )


def _store() -> Modelo232RelatedPartyStoreAdapter:
    return Modelo232RelatedPartyStoreAdapter(objects=secure_object_repository_for_active_bucket())


def _operation(ejercicio: int = _EJERCICIO, /, **overrides: object) -> Modelo232Operation:
    fields: dict[str, object] = {
        "operation_id": uuid4().hex,
        "ejercicio": ejercicio,
        "operation_kind": Modelo232OperationKind.RELATED_PARTY,
        "counterparty_tax_id": _TAX_ID,
        "counterparty_name": _NAME,
        "counterparty_country": "DE",
        "tipo_vinculacion": "D",
        "tipo_operacion": "06",
        "valuation_method": "1A",
        "direction": Modelo232Direction.PAGO,
        "amount_eur": _AMOUNT,
        "stated_at": _AT,
    }
    fields.update(overrides)
    return Modelo232Operation.model_validate(fields)


def _none(ejercicio: int = _EJERCICIO) -> Modelo232NoneStatement:
    return Modelo232NoneStatement(statement_id=uuid4().hex, ejercicio=ejercicio, note=_NOTE, stated_at=_AT)


def _turnover(ejercicio: int = _EJERCICIO, amount: Decimal = _TURNOVER) -> Modelo232TurnoverStatement:
    return Modelo232TurnoverStatement(
        statement_id=uuid4().hex,
        ejercicio=ejercicio,
        turnover_eur=amount,
        source=Modelo232TurnoverSource.ANNUAL_ACCOUNTS,
        source_reference=_REFERENCE,
        stated_at=_AT,
    )


def test_every_kind_round_trips_through_the_store_and_none_of_it_is_plaintext_on_disk(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    stated = _operation(specific_operation=True, exclusion=Modelo232Exclusion.CONSOLIDATION_GROUP)
    haven = _operation(
        operation_kind=Modelo232OperationKind.TAX_HAVEN_HOLDING,
        counterparty_tax_id=None,
        tipo_vinculacion=None,
        tipo_operacion=None,
        valuation_method=None,
        direction=None,
        counterparty_country="KY",
        participation_percent=Decimal("30.00"),
    )
    turnover = _turnover()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        ports = _ports(operation)
        operation_revision = state_m232_operation(stated, ports=ports)
        state_m232_operation(haven, ports=ports)
        turnover_revision = state_m232_turnover(turnover, ports=ports)
        store = _store()
        read_back = store.load_operations(_EJERCICIO)
        view = store.read_year(_EJERCICIO)
        other_year = store.load_operations(_EJERCICIO - 1)
        none_statements = store.load_none_statements(_EJERCICIO)
        on_disk = b"".join(path.read_bytes() for path in profile.storage_root.rglob("*") if path.is_file())

    assert {item.operation_id: item for item in read_back} == {stated.operation_id: stated, haven.operation_id: haven}
    assert dict((item.operation_id, rev) for item, rev in view.operations)[stated.operation_id] == operation_revision
    assert view.turnovers == ((turnover, turnover_revision),)
    assert view.guard is not None
    assert view.guard.counter == 3
    assert any(item.excluded for item in read_back)
    assert none_statements == ()
    assert other_year == ()
    for secret in (_TAX_ID, _NAME, _REFERENCE, str(_AMOUNT), str(_TURNOVER)):
        assert secret.encode(UTF_8_ENCODING) not in on_disk


def test_the_namespace_rows_carry_their_own_kind_and_each_write_advances_the_year_guard(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        state_m232_turnover(_turnover(), ports=ports)
        before = _store().read_year(_EJERCICIO)
        state_m232_operation(_operation(), ports=ports)
        after = _store().read_year(_EJERCICIO)
        records = secure_object_repository_for_active_bucket().list_records(
            MODELO_232_RELATED_PARTY_NAMESPACE.namespace,
            expected_class=MODELO_232_RELATED_PARTY_NAMESPACE.sensitivity,
            max_supported_version=MODELO_232_RELATED_PARTY_NAMESPACE.schema_version,
        )
        kinds = sorted(str(m232_related_party_row_kind(record.payload)) for record in records)
    assert kinds == ["m232_operation", "m232_turnover_statement", "m232_year_guard"]
    assert before.guard is not None
    assert after.guard is not None
    assert (before.guard.counter, after.guard.counter) == (1, 2)
    assert after.guard_revision_id not in (before.guard_revision_id, _ABSENT)
    assert m232_related_party_row_kind(b"not json") is None
    assert m232_related_party_row_kind(b'{"payload": 3}') is None


def test_a_none_statement_withdrawn_returns_the_year_to_undecided_and_a_restatement_keeps_both_rows(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    first = _none()
    second = _none()
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        revision = state_m232_none(first, ports=ports)
        with pytest.raises(Modelo232RelatedPartyRefusedError) as stands:
            state_m232_none(_none(), ports=ports)
        withdrawn, _withdrawn_revision = withdraw_m232_none(
            _EJERCICIO, at=_LATER, ports=ports, expected_revision_id=revision
        )
        after_withdrawal = _store().load_none_statements(_EJERCICIO)
        with pytest.raises(Modelo232RelatedPartyRefusedError) as again:
            withdraw_m232_none(_EJERCICIO, at=_LATER, ports=ports, expected_revision_id=_ABSENT)
        state_m232_none(second, ports=ports)
        restated = _store().load_none_statements(_EJERCICIO)

    assert stands.value.reason == "already_stated"
    assert withdrawn == first.withdrawn(_LATER)
    assert after_withdrawal == (withdrawn,)
    assert not any(item.active for item in after_withdrawal)
    assert again.value.reason == "not_stated"
    assert {item.statement_id: item.active for item in restated} == {
        first.statement_id: False,
        second.statement_id: True,
    }


def test_a_restated_turnover_keeps_the_withdrawn_one_beside_it(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    first = _turnover()
    second = _turnover(amount=Decimal("1.00"))
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        revision = state_m232_turnover(first, ports=ports)
        with pytest.raises(Modelo232RelatedPartyRefusedError) as active:
            state_m232_turnover(second, ports=ports)
        withdraw_m232_turnover(_EJERCICIO, at=_LATER, ports=ports, expected_revision_id=revision)
        state_m232_turnover(second, ports=ports)
        rows = _store().load_turnover_statements(_EJERCICIO)

    assert active.value.reason == "already_stated"
    assert {item.statement_id: (item.active, item.turnover_eur) for item in rows} == {
        first.statement_id: (False, _TURNOVER),
        second.statement_id: (True, Decimal("1.00")),
    }


def test_a_withdrawn_operation_is_kept_and_a_second_statement_of_it_is_refused(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    stated = _operation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        revision = state_m232_operation(stated, ports=ports)
        with pytest.raises(Modelo232RelatedPartyRefusedError) as repeated:
            state_m232_operation(stated, ports=ports)
        withdrawn, withdrawn_revision = withdraw_m232_operation(
            stated.identity, at=_LATER, ports=ports, expected_revision_id=revision
        )
        (kept, kept_revision) = _store().read_year(_EJERCICIO).operations[0]
        with pytest.raises(Modelo232RelatedPartyRefusedError) as twice:
            withdraw_m232_operation(stated.identity, at=_LATER, ports=ports, expected_revision_id=withdrawn_revision)

    assert repeated.value.reason == "already_stated"
    assert twice.value.reason == "not_stated"
    assert (kept, kept_revision) == (withdrawn, withdrawn_revision)
    assert kept.withdrawn_at == _LATER


def test_a_write_under_a_stale_revision_or_guard_is_refused_and_stores_nothing(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    stated = _operation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        revision = state_m232_operation(stated, ports=ports)
        with pytest.raises(Modelo232RelatedPartyRevisionConflictError):
            withdraw_m232_operation(stated.identity, at=_LATER, ports=ports, expected_revision_id=_ABSENT)
        with pytest.raises(Modelo232RelatedPartyRevisionConflictError):
            state_m232_operation(_operation(), ports=ports, expected_guard_revision_id=_ABSENT)
        view = _store().read_year(_EJERCICIO)
    assert view.operations == ((stated, revision),)
    assert view.guard is not None
    assert view.guard.counter == 1


class _CompetingFirst(Modelo232RelatedPartyStoreAdapter):
    """A real store whose next commit runs a competing writer first, as a second process would."""

    def __init__(self, competitor: Callable[[], object]) -> None:
        super().__init__(objects=secure_object_repository_for_active_bucket())
        self._competitor: Callable[[], object] | None = competitor

    @override
    def commit(self, view: Modelo232YearView, row: Modelo232Row, *, row_expected_revision_id: str) -> str:
        competitor, self._competitor = self._competitor, None
        if competitor is not None:
            competitor()
        return super().commit(view, row, row_expected_revision_id=row_expected_revision_id)


def test_an_operation_and_a_none_statement_written_at_once_cannot_both_commit(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    authority = Modelo232PinnedWriteAuthority(operation)
    with isolated_runtime_profile(tmp_path=tmp_path):
        plain = _ports(operation)
        slow = Modelo232RelatedPartyWritePorts(
            store=_CompetingFirst(lambda: state_m232_none(_none(), ports=plain)), authority=authority
        )
        with pytest.raises(Modelo232RelatedPartyRevisionConflictError):
            state_m232_operation(_operation(), ports=slow)
        first = _store().read_year(_EJERCICIO)

    with isolated_runtime_profile(tmp_path=tmp_path / "second"):
        plain = _ports(operation)
        slow = Modelo232RelatedPartyWritePorts(
            store=_CompetingFirst(lambda: state_m232_operation(_operation(), ports=plain)), authority=authority
        )
        with pytest.raises(Modelo232RelatedPartyRevisionConflictError):
            state_m232_none(_none(), ports=slow)
        second = _store().read_year(_EJERCICIO)

    assert [item.active for item, _revision in first.nones] == [True]
    assert first.operations == ()
    assert [item.active for item, _revision in second.operations] == [True]
    assert second.nones == ()


def test_the_guard_serialises_a_turnover_write_with_every_other_write_of_its_year(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    authority = Modelo232PinnedWriteAuthority(operation)
    with isolated_runtime_profile(tmp_path=tmp_path):
        plain = _ports(operation)
        slow = Modelo232RelatedPartyWritePorts(
            store=_CompetingFirst(lambda: state_m232_turnover(_turnover(), ports=plain)), authority=authority
        )
        with pytest.raises(Modelo232RelatedPartyRevisionConflictError):
            state_m232_turnover(_turnover(), ports=slow)
        rows = _store().load_turnover_statements(_EJERCICIO)
    assert len(rows) == 1


def test_an_operation_and_a_none_statement_of_one_year_refuse_each_other(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        none_revision = state_m232_none(_none(), ports=ports)
        with pytest.raises(Modelo232RelatedPartyRefusedError) as operation_refused:
            state_m232_operation(_operation(), ports=ports)
        withdraw_m232_none(_EJERCICIO, at=_LATER, ports=ports, expected_revision_id=none_revision)
        state_m232_operation(_operation(), ports=ports)
        with pytest.raises(Modelo232RelatedPartyRefusedError) as none_refused:
            state_m232_none(_none(), ports=ports)
        statements = _store().load_none_statements(_EJERCICIO)

    assert operation_refused.value.reason == "none_stated"
    assert none_refused.value.reason == "operations_present"
    assert [item.active for item in statements] == [False]


def test_a_withdrawn_operation_does_not_contradict_a_none_statement(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    stated = _operation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        revision = state_m232_operation(stated, ports=ports)
        withdraw_m232_operation(stated.identity, at=_LATER, ports=ports, expected_revision_id=revision)
        state_m232_none(_none(), ports=ports)
        statements = _store().load_none_statements(_EJERCICIO)
    assert [item.active for item in statements] == [True]


def test_an_unsupported_ejercicio_is_refused_before_storage(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    unsupported = filing_year_envelope().floor - 1
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        refused = []
        for write in (
            lambda: state_m232_operation(_operation(unsupported), ports=ports),
            lambda: state_m232_none(_none(unsupported), ports=ports),
            lambda: state_m232_turnover(_turnover(unsupported), ports=ports),
        ):
            with pytest.raises(Modelo232RelatedPartyRefusedError) as error:
                write()
            refused.append(error.value.reason)
        view = _store().read_year(unsupported)
    assert refused == ["ejercicio_unsupported"] * 3
    assert view.guard is None
    assert view.operations == ()


@pytest.mark.parametrize(
    "overrides",
    [{"tipo_vinculacion": "Z"}, {"tipo_operacion": "99"}, {"valuation_method": "9Z"}],
    ids=lambda overrides: ",".join(overrides),
)
def test_a_code_the_pinned_design_does_not_publish_is_refused_at_write(
    tmp_path: Path, operation: PinnedAuthorityOperation, overrides: dict[str, str]
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        with pytest.raises(Modelo232RelatedPartyRefusedError) as refused:
            state_m232_operation(_operation(**overrides), ports=ports)
        view = _store().read_year(_EJERCICIO)
    assert refused.value.reason == "code_unknown"
    assert view.operations == ()
    assert view.guard is None


def test_every_code_the_design_publishes_is_accepted_at_write(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    codes = resolve_form_codes("form-row-codes", authority=operation)
    always_specific = always_specific_operation_types(_EJERCICIO, operation=operation)
    stated = (
        [_operation(tipo_vinculacion=code) for code in codes.ordered_codes("m232.tipo_vinculacion.codes")]
        + [
            _operation(tipo_operacion=code, specific_operation=code in always_specific)
            for code in codes.ordered_codes("m232.tipo_operacion.codes")
        ]
        + [_operation(valuation_method=code) for code in codes.ordered_codes("m232.metodo_valoracion.codes")]
    )
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        for item in stated:
            state_m232_operation(item, ports=ports)
        stored = _store().load_operations(_EJERCICIO)
    assert {item.operation_id for item in stored} == {item.operation_id for item in stated}


def test_a_stored_row_with_an_unpublished_code_never_stops_a_read_of_any_year(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    odd = _operation(tipo_operacion="99")
    good = _operation(_EJERCICIO - 1)
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        state_m232_operation(good, ports=ports)
        store = _store()
        store.commit(store.read_year(_EJERCICIO), odd, row_expected_revision_id=_ABSENT)
        same_year = store.load_operations(_EJERCICIO)
        other_year = store.load_operations(_EJERCICIO - 1)
        withdrawn, _revision = withdraw_m232_operation(
            odd.identity, at=_LATER, ports=ports, expected_revision_id=store.read_year(_EJERCICIO).operations[0][1]
        )
    assert same_year == (odd,)
    assert other_year == (good,)
    assert withdrawn.tipo_operacion == "99"


def test_a_withdrawn_payload_cannot_be_stated(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path), pytest.raises(Modelo232RelatedPartyRefusedError) as refused:
        state_m232_operation(_operation().withdrawn(_LATER), ports=_ports(operation))
    assert refused.value.reason == "not_stated"


def test_no_content_of_a_statement_reaches_log_output_or_an_error(
    tmp_path: Path, operation: PinnedAuthorityOperation, caplog: pytest.LogCaptureFixture
) -> None:
    stated = _operation()
    errors: list[str] = []
    with caplog.at_level(logging.DEBUG), isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        revision = state_m232_operation(stated, ports=ports)
        state_m232_turnover(_turnover(), ports=ports)
        for refused in (
            lambda: state_m232_none(_none(), ports=ports),
            lambda: withdraw_m232_operation(stated.identity, at=_LATER, ports=ports, expected_revision_id=_ABSENT),
        ):
            with pytest.raises(
                (Modelo232RelatedPartyRefusedError, Modelo232RelatedPartyRevisionConflictError)
            ) as error:
                refused()
            errors.append(f"{error.value} {error.value.context!r}")
        withdraw_m232_operation(stated.identity, at=_LATER, ports=ports, expected_revision_id=revision)
        _store().load_operations(_EJERCICIO)

    assert caplog.records
    for secret in (_TAX_ID, _NAME, _NOTE, _REFERENCE, str(_AMOUNT), str(_TURNOVER)):
        assert secret not in caplog.text
        assert all(secret not in message for message in errors)


def test_the_row_keys_name_the_year_and_never_a_counterparty() -> None:
    stated = _operation()
    statement = _none()
    assert m232_operation_key(stated.identity) == f"operation:{_EJERCICIO}:{stated.operation_id}"
    assert m232_none_key(statement.identity) == f"none:{_EJERCICIO}:{statement.statement_id}"
    assert m232_turnover_key((_EJERCICIO, "a" * 32)) == f"turnover:{_EJERCICIO}:{'a' * 32}"
    assert m232_guard_key(_EJERCICIO) == f"year:{_EJERCICIO}"
    assert _TAX_ID not in m232_operation_key(stated.identity)


def _key_of(row: Modelo232Operation | Modelo232NoneStatement | Modelo232TurnoverStatement | Modelo232YearGuard) -> str:
    if isinstance(row, Modelo232Operation):
        return m232_operation_key(row.identity)
    if isinstance(row, Modelo232NoneStatement):
        return m232_none_key(row.identity)
    if isinstance(row, Modelo232TurnoverStatement):
        return m232_turnover_key(row.identity)
    return m232_guard_key(row.identity)


def test_every_carried_row_kind_decodes_back_into_its_payload_under_its_own_key(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    stated = _operation()
    none_statement = _none(_EJERCICIO - 1)
    turnover = _turnover()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        ports = _ports(operation)
        state_m232_operation(stated, ports=ports)
        state_m232_turnover(turnover, ports=ports)
        state_m232_none(none_statement, ports=ports)
        material = collect_profile_custody_carry(
            bucket_id=profile.bucket_id,
            profile=StorageCustodyProfile.STRUCTURED,
            profile_decode_context=operation.profile_decode_context(),
        )
        objects = secure_object_repository_for_active_bucket()
        decoders = (
            Modelo232OperationRepositoryAdapter(objects=objects),
            Modelo232NoneRepositoryAdapter(objects=objects),
            Modelo232TurnoverRepositoryAdapter(objects=objects),
            Modelo232GuardRepositoryAdapter(objects=objects),
        )
        carried = [
            item for item in material.carried_objects if item.namespace == MODELO_232_RELATED_PARTY_NAMESPACE.namespace
        ]
        restored: dict[str, object] = {}
        for item in carried:
            payload = base64.b64decode(item.payload_b64)
            kind = m232_related_party_row_kind(payload)
            (decoder,) = [candidate for candidate in decoders if candidate.row_kind == kind]
            decoded = decoder.decode_row(payload)
            assert _key_of(decoded) == item.object_key
            restored[item.object_key] = decoded

    guards = {m232_guard_key(_EJERCICIO), m232_guard_key(_EJERCICIO - 1)}
    assert set(restored) == {
        m232_operation_key(stated.identity),
        m232_turnover_key(turnover.identity),
        m232_none_key(none_statement.identity),
        *guards,
    }
    assert restored[m232_operation_key(stated.identity)] == stated
    assert restored[m232_none_key(none_statement.identity)] == none_statement
    assert MODELO_232_RELATED_PARTY_NAMESPACE.namespace in material.carried_namespaces
